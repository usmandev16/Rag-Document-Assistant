"""Evaluate the RAG pipeline against eval/dataset.jsonl.

Usage (from the repo root):
    python eval/run_eval.py                 # ingest the 4 test documents, then evaluate
    python eval/run_eval.py --reuse         # skip ingestion, reuse the eval namespace
    python eval/run_eval.py --limit 5       # first 5 questions only (smoke test)
    python eval/run_eval.py --reingest Mid_Year_FY2025_26.pdf --out after_ocr
                                            # replace one document's chunks, then evaluate;
                                            # the summary is printed next to baseline.jsonl

Inside the worker image (same Tesseract/OCR setup as production), from the repo root:
    docker compose run --rm -v "./eval:/app/eval" -v "./Test documents:/app/Test documents" \\
        worker python eval/run_eval.py --reingest Mid_Year_FY2025_26.pdf --out after_ocr

dataset.jsonl, one JSON object per line:
    {"id": "q1", "type": "factual" | "table" | "paraphrased" | "aggregation" | "unanswerable",
     "question": "...", "expected_answer": "..." | null, "evidence": "..." | null}

Calls the pipeline functions directly (no HTTP, no Redis): the same ingestion
task the Celery worker runs, then the same retrieve -> token budget -> answer ->
citation steps as POST /api/chat, so the exact chunks sent to the LLM are
recorded. Needs PINECONE_API_KEY and GROQ_API_KEY in backend/.env.
"""
import argparse
import asyncio
import base64
import json
import os
import re
import sys
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Repo checkout: the code lives in ROOT/backend. Worker container: the backend
# folder IS /app, with eval/ mounted at /app/eval.
sys.path.insert(0, str(ROOT / "backend" if (ROOT / "backend").is_dir() else ROOT))

from groq import AsyncGroq  # noqa: E402

from main import context_line, fit_to_budget  # noqa: E402
from src.llm import answer_question, answer_with_web_search, keep_cited, needs_web_search  # noqa: E402
from src.router import route_question, sources_for  # noqa: E402
from src.sheets import delete_sheets  # noqa: E402
from src.vectorstore import _all_chunks, delete_chat_chunks, get_index, query_chunks  # noqa: E402
from src.worker import ingest_documents  # noqa: E402

DATASET = ROOT / "eval" / "dataset.jsonl"
RESULTS_DIR = ROOT / "eval" / "results"
DOCS_DIR = ROOT / "Test documents"
NAMESPACE = "eval-test-user"   # the test user's chat namespace in Pinecone
SESSION_ID = "eval-test-user"
N_CTX = 40                     # same candidate count as POST /api/chat
TYPES = ["factual", "table", "paraphrased", "aggregation", "unanswerable"]

# The requested judge isn't available on this Groq key; fall back when Groq
# says model_not_found. Override with JUDGE_MODEL.
JUDGE_MODELS = [os.environ.get("JUDGE_MODEL", "llama-3.1-8b-instant"), "openai/gpt-oss-20b"]
PAUSE_SECONDS = 30
RETRY_SECONDS = 60

REFUSAL_RE = re.compile(
    r"i (?:do not|don't) know|not (?:in|mentioned in|found in|available in|provided in) the "
    r"(?:context|documents?)|no information|cannot (?:find|answer|determine)|unable to (?:find|answer|determine)"
)


def normalize(text: str) -> str:
    return " ".join(text.replace("’", "'").lower().split())


def compact(text: str) -> str:
    """For evidence matching: lowercase with ALL whitespace removed, so PDF
    and OCR spacing quirks ("GFR -14" vs "GFR-14") still match."""
    return "".join(normalize(text).split())


def is_refusal(answer: str) -> bool:
    return bool(REFUSAL_RE.search(normalize(answer)))


async def with_retry(make_call):
    """Run a Groq call; on 429 wait RETRY_SECONDS and retry once."""
    try:
        return await make_call()
    except Exception as exc:
        if getattr(exc, "status_code", None) != 429:
            raise
        print(f"  429 rate limited, retrying in {RETRY_SECONDS}s")
        await asyncio.sleep(RETRY_SECONDS)
        return await make_call()


def _delete_source(source: str) -> int:
    """Delete one document's vectors from the eval namespace, keeping the rest."""
    index = get_index()
    ids = []
    for page in index.list(namespace=NAMESPACE):
        fetched = index.fetch(ids=[item.id for item in page.vectors], namespace=NAMESPACE)
        ids += [vid for vid, vec in fetched.vectors.items() if (vec.metadata or {}).get("source") == source]
    for start in range(0, len(ids), 1000):
        index.delete(ids=ids[start:start + 1000], namespace=NAMESPACE)
    return len(ids)


def ingest(only: list[str] | None = None) -> None:
    """Fresh namespace with the 4 test documents, via the Celery task's own
    code (chunks to Pinecone, spreadsheets also to parquet). With `only`,
    replace just those documents."""
    files = sorted(p for p in DOCS_DIR.iterdir() if p.is_file())
    if only:
        missing = set(only) - {p.name for p in files}
        if missing:
            sys.exit(f"not found in {DOCS_DIR}: {sorted(missing)}")
        files = [p for p in files if p.name in only]
        for name in only:
            print(f"Re-ingesting {name!r}: deleted {_delete_source(name)} old chunks")
        before = len(_all_chunks(NAMESPACE))
    else:
        print(f"Ingesting {len(files)} documents into namespace {NAMESPACE!r}...")
        delete_chat_chunks(NAMESPACE)
        delete_sheets(NAMESPACE)
        before = 0
    payload = [{"name": p.name, "data": base64.b64encode(p.read_bytes()).decode()} for p in files]
    result = ingest_documents(NAMESPACE, SESSION_ID, payload)  # runs in-process, not queued
    for doc in result["indexed"]:
        print(f"  {doc['name']}: {doc['chunks']} chunks")

    # Pinecone is eventually consistent: wait until every chunk is listable.
    expected = before + result["total_chunks"]
    for _ in range(60):
        if len(_all_chunks(NAMESPACE)) >= expected:
            return
        time.sleep(2)
    print(f"  warning: not all {expected} chunks visible yet, continuing")


async def run_pipeline(question: str) -> dict:
    """Mirror of POST /api/chat for a fresh chat (no history, no filters):
    the spreadsheet router first, then the documents pipeline."""
    routed = await with_retry(lambda: route_question(question, NAMESPACE))
    if routed["route"] == "spreadsheet":
        answer, cited = keep_cited(routed["answer"], sources_for(routed))
        return {"route": "spreadsheet", "chunks_sent": [], "answer": answer,
                "citations": [{"number": i, "source": m["source"]} for i, (_, m) in enumerate(cited, 1)],
                "plan": routed.get("plan"), "result": routed.get("result"), "plan_error": routed.get("error"),
                "tokens": routed["tokens"]}
    router_tokens = routed["tokens"]
    # Set when the router picked "spreadsheet" but the plan was rejected and it
    # fell back to the documents path.
    extra = {"router_fallback": routed["error"]} if routed.get("error") else {}

    started = time.perf_counter()
    results = fit_to_budget(await asyncio.to_thread(query_chunks, question, NAMESPACE, N_CTX))
    extra["retrieval_ms"] = round((time.perf_counter() - started) * 1000)
    context = [context_line(doc, meta) for doc, meta in results]
    chunks_sent = [{"source": m.get("source"), "chunk_index": m.get("chunk_index"), "page": m.get("page"),
                    "ocr": m.get("ocr"), "text": d} for d, m in results]

    if needs_web_search(question):
        answer, _trace, tokens = await with_retry(lambda: answer_with_web_search(question, context, []))
        return {**extra, "route": "web_search", "chunks_sent": chunks_sent, "answer": answer, "citations": [], "tokens": router_tokens + tokens}

    if not results:
        return {**extra, "route": "document", "chunks_sent": [], "answer": "I don't know. No documents have been indexed yet.",
                "citations": [], "tokens": router_tokens}

    raw, tokens = await with_retry(lambda: answer_question(question, context, []))
    answer, cited = keep_cited(raw, results)
    citations = [{"number": i, "source": m.get("source"), "chunk_index": m.get("chunk_index"), "page": m.get("page")}
                 for i, (_, m) in enumerate(cited, 1)]
    return {**extra, "route": "document", "chunks_sent": chunks_sent, "answer": answer, "citations": citations,
            "tokens": router_tokens + tokens}


class Judge:
    def __init__(self) -> None:
        self.client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
        self.models = list(dict.fromkeys(JUDGE_MODELS))

    async def matches(self, question: str, expected: str, answer: str) -> tuple[bool, str]:
        prompt = (
            "Does this answer match the expected answer? Reply only YES or NO.\n\n"
            f"Question: {question}\nExpected answer: {expected}\nAnswer: {answer}"
        )
        while True:
            model = self.models[0]
            kwargs = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
            if model.startswith("openai/gpt-oss"):
                # Reasoning model: a tiny max_tokens gets spent on reasoning.
                kwargs.update(reasoning_effort="low", max_tokens=300)
            else:
                kwargs["max_tokens"] = 5
            try:
                response = await with_retry(lambda: self.client.chat.completions.create(**kwargs))
            except Exception as exc:
                if "model_not_found" in str(exc) and len(self.models) > 1:
                    print(f"  judge model {model!r} unavailable, using {self.models[1]!r}")
                    self.models.pop(0)
                    continue
                raise
            verdict = (response.choices[0].message.content or "").strip().upper()
            return verdict.startswith("YES"), model


def load_dataset(limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
    for i, row in enumerate(rows):
        row.setdefault("id", f"q{i + 1}")
        row["expected_answer"] = row.get("expected_answer", row.get("answer"))
    return rows[:limit] if limit else rows


def _stats(rows: list[dict]) -> tuple[list[bool], list[bool]]:
    hits = [r["retrieval_hit"] for r in rows if r["retrieval_hit"] is not None]
    correct = [r["correct"] for r in rows if r["correct"] is not None]
    return hits, correct


def _rate(values: list[bool]) -> str:
    return f"{sum(values) / len(values):6.1%} ({sum(values)}/{len(values)})" if values else "n/a"


def summarize(results: list[dict], baseline: list[dict] | None = None, label: str = "baseline") -> None:
    """Per-type table; with `baseline`, each metric is shown as <label> -> now."""
    types = TYPES + sorted({r["type"] for r in results} - set(TYPES))
    groups = [(t, [r for r in results if r["type"] == t]) for t in types] + [("overall", results)]

    def cell(name: str, rows: list[dict], metric: int) -> str:
        now = _rate(_stats(rows)[metric])
        if baseline is None:
            return now
        base_rows = baseline if name == "overall" else [r for r in baseline if r["type"] == name]
        return f"{_rate(_stats(base_rows)[metric])} -> {now}"

    width = max(38, len(label) + 26) if baseline else 22
    suffix = f" ({label} -> now)" if baseline else ""
    rule = "-" * (24 + 2 * width)
    print(f"\n{'type':<14}{'n':>4}   {'retrieval hit rate' + suffix:<{width}}   {'answer accuracy' + suffix}")
    print(rule)
    for name, rows in groups:
        if not rows:
            continue
        if name == "overall":
            print(rule)
        print(f"{name:<14}{len(rows):>4}   {cell(name, rows, 0):<{width}}   {cell(name, rows, 1)}")
    errors = sum(1 for r in results if r.get("error"))
    if errors:
        print(f"\n{errors} question(s) errored and are excluded from accuracy")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--reuse", action="store_true", help="skip ingestion, reuse the existing eval namespace")
    parser.add_argument("--limit", type=int, help="evaluate only the first N questions")
    parser.add_argument("--reingest", metavar="FILE", nargs="+", help="replace only these documents, then evaluate")
    parser.add_argument("--types", help="comma-separated question types to run, e.g. aggregation,unanswerable")
    parser.add_argument("--compare", default="baseline", help="results file to compare against (default: baseline)")
    parser.add_argument("--out", default="baseline", help="results file name in eval/results (default: baseline)")
    parser.add_argument("--retry-errors", action="store_true",
                        help="re-run only the questions that errored in --out and merge them in (no ingestion)")
    args = parser.parse_args()
    results_path = RESULTS_DIR / f"{args.out}.jsonl"
    baseline_path = RESULTS_DIR / f"{args.compare}.jsonl"

    if not DATASET.exists():
        sys.exit(f"Missing {DATASET}")
    dataset = load_dataset(args.limit)
    if args.types:
        wanted = {t.strip() for t in args.types.split(",")}
        dataset = [row for row in dataset if row["type"] in wanted]

    # Results by id, in dataset order. --retry-errors keeps every finished
    # record and only re-asks the ones that errored.
    done: dict[str, dict] = {}
    if args.retry_errors:
        if not results_path.exists():
            sys.exit(f"Nothing to retry: {results_path} doesn't exist")
        done = {r["id"]: r for r in map(json.loads, results_path.read_text(encoding="utf-8").splitlines())}
        todo = [row for row in dataset if row["id"] not in done or done[row["id"]].get("error")]
        print(f"Retrying {len(todo)} errored question(s) from {results_path.name}")
    else:
        todo = dataset
        if args.reingest:
            ingest(only=args.reingest)
        elif not args.reuse:
            ingest()

    def save() -> None:
        # Rewritten after every question so an interrupted run keeps its progress.
        rows = [done[row["id"]] for row in dataset if row["id"] in done]
        results_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    judge = Judge()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(todo):
        if i:
            await asyncio.sleep(PAUSE_SECONDS)  # stay under Groq's 8,000 tokens/minute
        qtype, question, expected, evidence = row["type"], row["question"], row["expected_answer"], row.get("evidence")
        print(f"[{i + 1}/{len(todo)}] ({qtype}) {question}")
        record = {"id": row["id"], "type": qtype, "question": question,
                  "expected_answer": expected, "evidence": evidence}
        try:
            started = time.perf_counter()
            record.update(await run_pipeline(question))
            record["total_ms"] = round((time.perf_counter() - started) * 1000)
            sent = [compact(c["text"]) for c in record["chunks_sent"]]
            record["retrieval_hit"] = None if evidence is None else any(compact(evidence) in s for s in sent)

            if qtype == "unanswerable" or expected is None:
                record["correct"], record["judge"] = is_refusal(record["answer"]), "refusal-check"
            else:
                record["correct"], record["judge"] = await judge.matches(question, expected, record["answer"])
        except Exception as exc:
            record.update(retrieval_hit=None, correct=None, error=f"{type(exc).__name__}: {exc}")
            print(f"  error: {record['error'][:200]}")
        else:
            print(f"  hit={record['retrieval_hit']} correct={record['correct']} answer={record['answer'][:100]!r}")
        done[row["id"]] = record
        save()
        if "tokens per day" in record.get("error", ""):
            # The daily quota won't recover within this run; every remaining
            # question would just fail after a 60s retry. Stop and keep them
            # marked as errors for the next --retry-errors.
            for rest in todo[i + 1:]:
                done.setdefault(rest["id"], {"id": rest["id"], "type": rest["type"], "question": rest["question"],
                                             "expected_answer": rest["expected_answer"], "evidence": rest.get("evidence"),
                                             "retrieval_hit": None, "correct": None, "error": record["error"]})
            save()
            print(f"\nDaily token limit reached; stopping. Re-run later with --retry-errors --out {args.out}")
            break
    results = [done[row["id"]] for row in dataset if row["id"] in done]

    baseline = None
    if results_path != baseline_path and baseline_path.exists():
        # Compare like with like: only questions that finished in this run
        # (errors and --limit would otherwise skew the baseline side).
        finished = {r["id"] for r in results if not r.get("error")}
        lines = baseline_path.read_text(encoding="utf-8").splitlines()
        baseline = [r for r in map(json.loads, lines) if r["id"] in finished]
        if len(finished) < len(results):
            print(f"\nComparing the {len(finished)} questions that finished; "
                  f"{len(results) - len(finished)} errored and are left out on both sides.")
        results = [r for r in results if r["id"] in finished]
    summarize(results, baseline, args.compare)
    # Latency of documents-path questions. total_ms includes the router and LLM
    # calls (and any 429 retry waits); retrieval_ms is search + token budget only.
    docs = [r for r in results if r.get("retrieval_ms") is not None]
    if docs:
        print(f"\nDocuments path, {len(docs)} questions: p50 retrieval "
              f"{statistics.median(r['retrieval_ms'] for r in docs):.0f} ms, "
              f"p50 end-to-end {statistics.median(r['total_ms'] for r in docs):.0f} ms")
    print(f"\nSaved {len(results)} results to {results_path}")


if __name__ == "__main__":
    asyncio.run(main())
