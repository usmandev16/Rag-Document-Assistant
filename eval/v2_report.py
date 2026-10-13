"""Build eval/results/v2_heldout_report.md from the held-out (v2) run.

    python eval/v2_report.py

Reads eval/dataset_v2.jsonl, eval/results/v2_heldout.jsonl and
eval/results/v2_retrieval.json. Does not call the pipeline or any API.

Retrieval hit (v2 definition): the question's evidence is in a chunk that was
sent to the LLM and comes from one of its source_files, compared
case-insensitively with all whitespace collapsed to single spaces.
"""
import collections
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
SMALL = 10  # groups below this are marked "too small to conclude"

REFUSAL_RE = re.compile(
    r"i (?:do not|don't) know|not (?:in|mentioned in|found in|available in|provided in) the "
    r"(?:context|documents?)|no information|cannot (?:find|answer|determine)|unable to (?:find|answer|determine)"
)  # same pattern as eval/run_eval.py

# Failure categories set by hand after reading each failed question (answer,
# cited chunk, documents the sent chunks came from, route); these override the
# automatic first pass below.
TABLE = "Fact is only in a Word table, which the loader does not ingest."
MANUAL: dict[str, tuple[str, str]] = {
    "q001": ("generation_error", "Right chunk sent; gives the amount but not the form (pay order / bank draft)."),
    "q002": ("retrieval_miss", "Evidence chunk was candidate 20 of 34; only the top 15 fit the token budget."),
    "q003": ("retrieval_miss", TABLE),
    "q004": ("retrieval_miss", TABLE),
    "q005": ("retrieval_miss", TABLE),
    "q006": ("wrong_document", TABLE + " Answered from the FBR bidding document instead."),
    "q007": ("wrong_document", TABLE + " Answered from the COMSATS bidding document instead."),
    "q009": ("generation_error", "Right chunk sent; gives the panel warranties but leaves out the inverter and project warranties."),
    "q011": ("retrieval_miss", "Evidence chunk was candidate 14 of 36; 13 were sent. Partial answer (currency only) from another part."),
    "q014": ("retrieval_miss", "Evidence chunk was not among the 33 retrieved candidates."),
    "q018": ("generation_error", "Right chunk sent; gives the date but not the time and room."),
    "q021": ("retrieval_miss", "Evidence chunk was candidate 35 of 37; 14 were sent. Answered generally from other clauses."),
    "q023": ("generation_error", "Right chunk sent; date and time are right, but 'through EPADS v2.0' is missing."),
    "q029": ("retrieval_miss", "Evidence chunk was candidate 28 of 33; 15 were sent."),
    "q034": ("generation_error", "Right chunk sent; gives 5 ohms but not the two-electrode requirement."),
    "q041": ("retrieval_miss", TABLE + " Found '90 days' in another clause of the same document, with a different start point."),
    "q042": ("retrieval_miss", TABLE),
    "q043": ("retrieval_miss", TABLE),
    "q044": ("retrieval_miss", TABLE),
    "q046": ("retrieval_miss", TABLE),
    "q047": ("wrong_document", TABLE + " Answered from the COMSATS bidding document instead (PKR 100 million)."),
    "q048": ("retrieval_miss", TABLE),
    "q049": ("wrong_document", "12 of 15 sent chunks came from the AEDB guide, not the 2015 regulations; the right chunk was candidate 34 of 34."),
    "q051": ("false_refusal", "The roof-area table chunk was sent, but the system said it doesn't know."),
    "q058": ("retrieval_miss", TABLE),
    "q059": ("retrieval_miss", TABLE),
    "q063": ("retrieval_miss", "Evidence chunk was not among the 37 retrieved candidates."),
    "q068": ("generation_error", "Right chunk sent; gives the efficiency but not phase, IP rating or THD."),
    "q071": ("retrieval_miss", "Roman Urdu question; evidence chunk not in the top 100 of either search."),
    "q072": ("retrieval_miss", TABLE + " (Roman Urdu question.)"),
    "q075": ("retrieval_miss", "Roman Urdu question; evidence chunk was not among the 33 retrieved candidates."),
    "q090": ("generation_error", "Spreadsheet path: the plan filtered 'Indicator Name contains hydroelectric', which matched "
                                 "several indicators (135 rows, including kWh totals), so max(Value) was 840,000,000."),
    "q100": ("hallucination", "Gave a 26-degree tilt angle taken from the FBISE tender, a different document."),
}
MANUAL_CATEGORY = {k: v[0] for k, v in MANUAL.items()}
MANUAL_NOTE = {k: v[1] for k, v in MANUAL.items()}
NOT_INGESTED = {k for k, v in MANUAL.items() if v[1].startswith(TABLE)}
INCOMPLETE = {"q001", "q009", "q018", "q023", "q034", "q068"}
MISS_INGESTED = {"q002", "q011", "q014", "q021", "q029", "q049", "q063", "q071", "q075"}

RUN_INFO = """## Run record

- **System under test:** commit `473b6e76cdc504d113eff9008d42625b0f9b864a`, unchanged from start to end. Default
  config: hybrid search (BM25 + dense, 20 each, RRF), reranker off (`RERANK_TOP_K=0`), 3,000-token context budget.
  No prompt, retrieval setting, chunking or router code was changed before or during the run.
- **Models:** `openai/gpt-oss-120b` for answers, `openai/gpt-oss-20b` as judge (same as v1). Unanswerable questions
  are graded by the refusal check, as in v1.
- **Sessions:** 2, with 2 Groq API keys. Session 1 finished 58 questions and stopped at Groq's daily token limit;
  session 2 (`--retry-errors`) ran only the remaining 39. No question was run twice. About 359,000 tokens in total.
- **Documents:** 28 files (split from 12 source documents) in a fresh namespace: 7,385 chunks, of which 5,719 come
  from the two plant workbooks (all ~140,000 rows ingested, none dropped or sampled). 80 PDF pages went through
  the OCR fallback, 36 of them in `bidding-document_part1of5.pdf`. Per-file chunk counts and OCR'd page numbers:
  `v2_evidence_check.txt`.
- **Pre-run checks:** all 15 aggregation answers match an independent pandas calculation
  (`v2_aggregation_check.txt`). Evidence check: 56 of 72 evidence strings are in the ingested chunks. 4 evidence
  strings were updated to the text as ingested (q001, q018, q038, q056; listed in `v2_evidence_changes.json`).
  The other 16 are inside Word tables, which the loader does not ingest; their evidence was left unchanged.
"""



def norm(text: str) -> str:
    return " ".join(text.replace("’", "'").lower().split())


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def family(name: str) -> str:
    """Source document a part belongs to: 'x_part2of5.pdf' -> 'x'."""
    return re.sub(r"(_part\d+of\d+)?\.\w+$", "", name)


def retrieval_hit(q: dict, r: dict) -> bool | None:
    if not q.get("evidence") or q["type"] in ("aggregation", "unanswerable"):
        return None
    target = norm(q["evidence"])
    return any(c["source"] in q["source_files"] and target in norm(c["text"]) for c in r.get("chunks_sent", []))


def auto_category(q: dict, r: dict, hit: bool | None) -> str:
    refused = bool(REFUSAL_RE.search(norm(r.get("answer") or "")))
    route = r.get("route")
    if q["type"] == "unanswerable":
        return "hallucination"
    if (q["type"] == "aggregation") != (route == "spreadsheet"):
        return "router_misroute"
    if q["type"] == "aggregation":
        return "false_refusal" if refused else "generation_error"
    if hit:
        return "false_refusal" if refused else "generation_error"
    sent_families = {family(c["source"]) for c in r.get("chunks_sent", [])}
    own = {family(f) for f in q["source_files"]}
    if sent_families and not (sent_families & own) and not refused:
        return "wrong_document"
    return "retrieval_miss"


def rate(values: list[bool]) -> str:
    if not values:
        return "n/a"
    return f"{100 * sum(values) / len(values):.0f}% ({sum(values)}/{len(values)})"


def table(groups: list[tuple[str, list[dict]]], label: str) -> list[str]:
    lines = [f"| {label} | Questions | Retrieval hit rate | Answer accuracy | Note |", "|---|---|---|---|---|"]
    for name, rows in groups:
        hits = [r["_hit"] for r in rows if r["_hit"] is not None]
        acc = [bool(r["correct"]) for r in rows]
        note = "too small to conclude" if len(rows) < SMALL else ""
        lines.append(f"| {name} | {len(rows)} | {rate(hits)} | {rate(acc)} | {note} |")
    return lines


def esc(text: str, limit: int = 260) -> str:
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> None:
    dataset = {q["id"]: q for q in load(ROOT / "eval" / "dataset_v2.jsonl")}
    results = load(RESULTS / "v2_heldout.jsonl")
    pending = [r["id"] for r in results if r.get("error")] + [i for i in dataset if i not in {r["id"] for r in results}]
    done = [r for r in results if not r.get("error")]
    for r in done:
        q = dataset[r["id"]]
        r["_q"], r["_hit"] = q, retrieval_hit(q, r)
        r["_hit_v1_style"] = r.get("retrieval_hit")

    out = ["# Held-out eval (v2) report", ""]
    if pending:
        out += [f"**INCOMPLETE: {len(done)} of {len(dataset)} questions have a result; {len(pending)} are still pending "
                f"(rate limit). Numbers below cover only the finished questions.**", ""]

    hits = [r["_hit"] for r in done if r["_hit"] is not None]
    hits_v1 = [r["_hit_v1_style"] for r in done if r["_hit_v1_style"] is not None]
    acc = [bool(r["correct"]) for r in done]
    out += ["## 1. Overall", "",
            "| | v1 final (50 questions, 4 documents) | v2 held-out (97 questions, 28 files) |", "|---|---|---|",
            f"| Answer accuracy | 92% (46/50) | {rate(acc)} |",
            f"| Retrieval hit rate | 83% (25/30) | {rate(hits)} |", "",
            f"Retrieval hit uses the v2 definition (evidence in a sent chunk from one of the question's source files, "
            f"whitespace collapsed to single spaces). With the v1 script's own check (any sent chunk, all whitespace "
            f"removed) it is {rate(hits_v1)}.", ""]

    out += ["## 2. Breakdown", "", "### By question type", ""]
    types = ["factual", "table", "paraphrased", "aggregation", "unanswerable"]
    out += table([(t, [r for r in done if r["type"] == t]) for t in types], "Type") + [""]
    tags = sorted({t for q in dataset.values() for t in q.get("tags") or []})
    out += ["### By tag", ""] + table([(t, [r for r in done if t in (r["_q"].get("tags") or [])]) for t in tags], "Tag") + [""]
    files = sorted({f for q in dataset.values() for f in q["source_files"]})
    out += ["### By source file", "", "A question with several source files is counted under each of them. "
            "Unanswerable questions have no source file.", ""]
    out += table([(f, [r for r in done if f in r["_q"]["source_files"]]) for f in files], "Source file") + [""]
    fams = sorted({family(f) for f in files})
    out += ["### By source document (parts combined)", ""]
    out += table([(d, [r for r in done if d in {family(f) for f in r["_q"]["source_files"]}]) for d in fams], "Source document") + [""]

    retrieval = json.loads((RESULTS / "v2_retrieval.json").read_text(encoding="utf-8"))
    ms = sorted(r["ms"] for r in retrieval)
    p95 = ms[min(len(ms) - 1, int(round(0.95 * len(ms))) - 1)]
    tokens = [(r.get("tokens") or 0, r["id"]) for r in done]
    out += ["## 3. Latency and request size", "",
            f"- Retrieval latency (retrieval-only run, {len(ms)} questions, no LLM): p50 {statistics.median(ms):.0f} ms, "
            f"p95 {p95:.0f} ms, max {ms[-1]:.0f} ms.",
            f"- Largest request: {max(tokens)[0]} tokens ({max(tokens)[1]}); median {statistics.median(t for t, _ in tokens):.0f} tokens.", ""]

    failed = [r for r in done if not r["correct"]]
    counts = collections.Counter()
    out += [f"## 4. Failed questions ({len(failed)})", "",
            "| ID | Type | Question | Expected | System answer | Category | Note |", "|---|---|---|---|---|---|---|"]
    for r in failed:
        cat = MANUAL_CATEGORY.get(r["id"]) or auto_category(r["_q"], r, r["_hit"])
        counts[cat] += 1
        out.append(f"| {r['id']} | {r['type']} | {esc(r['question'])} | {esc(r['_q']['expected_answer'])} | "
                   f"{esc(r.get('answer'))} | `{cat}` | {esc(MANUAL_NOTE.get(r['id'], ''))} |")
    out += ["", "Failures by category: " + ", ".join(f"`{c}` {n}" for c, n in counts.most_common()) + ".", ""]
    out += ["No failure was a `router_misroute`. Three aggregation questions (q087, q088, q089) did go down the "
            "documents path instead of the spreadsheet path, and were answered correctly from retrieved chunks; "
            "q089's average was worked out by the LLM, which the prompt forbids, so that result is not dependable.", ""]

    failed_ids = {r["id"] for r in failed}
    p1, p2, p3 = sorted(NOT_INGESTED & failed_ids), sorted(MISS_INGESTED & failed_ids), sorted(INCOMPLETE & failed_ids)
    out += ["## 5. The three biggest problems", "",
            f"### 1. Word tables are not ingested: {len(p1)} questions",
            "", f"Questions: {', '.join(p1)}.", "",
            "The Word loader reads `document.paragraphs` only (`backend/src/loaders.py`), so everything inside a table "
            "is dropped at ingestion. In these tender documents the tables hold the key terms: bid security, validity, "
            "bill of quantities, payment terms. 16 questions asked for facts that exist only in tables; 15 failed "
            "(one was answered from a paragraph that says the same thing). Three of the 15 were answered confidently "
            "from a different tender, which is worse than saying \"I don't know\".", "",
            "**Suggested fix:** read tables as well as paragraphs, in document order, rendering each row as "
            "\"header: value\" text the way spreadsheet rows are handled. Re-ingest and re-run these questions.", "",
            f"### 2. The right chunk is retrieved but cut, or not retrieved: {len(p2)} questions",
            "", f"Questions: {', '.join(p2)}.", "",
            "The evidence was ingested, but did not reach the LLM. For 5 of them (q002, q011, q021, q029, q049) the "
            "right chunk was among the 33 to 37 retrieved candidates, but ranked below the 13 to 15 that fit the "
            "3,000-token budget (`v2_miss_ranks.json`). For the other 4 (q014, q063, q071, q075) it was not among the "
            "candidates at all; two of those are Roman Urdu questions, which share no words with the English text and "
            "are poorly served by the English embedding model. q049 is the near-duplicate case: 12 of the 15 chunks "
            "sent came from the AEDB guide, not the 2015 regulations the question names.", "",
            "**Suggested fix:** rerank the retrieved candidates before applying the token budget (the cross-encoder "
            "exists but is off because it takes about 2.5 s on CPU; a faster reranker or a GPU would be needed). For "
            "Roman Urdu, rewrite the question into English before retrieval. For near-duplicates, detect the document "
            "named in the question and filter or boost by source file.", "",
            f"### 3. Incomplete answers: {len(p3)} questions",
            "", f"Questions: {', '.join(p3)}.", "",
            "The right chunk was sent and the answer is correct as far as it goes, but it leaves out part of the "
            "expected answer (for example the amount without the form of payment, or the date without the time and "
            "place), and the judge marks it wrong. Some of the expected answers include details the question did not "
            "ask for, so part of this is judge strictness, as in v1.", "",
            "**Suggested fix:** tell the model to include the conditions and qualifiers stated with a fact (form, "
            "time, place, limits), and separately consider grading partial answers as partially correct.", "",
            "### Smaller problems", "",
            "- **False refusal (q051):** the table chunk with the roof areas was sent, but the system said it doesn't know.",
            "- **Wrong spreadsheet plan (q090):** a `contains` filter on the indicator name matched several indicators. "
            "Filtering on the indicator code, or checking that a filter leaves one indicator, would avoid it.",
            "- **Hallucination (q100):** an unanswerable question about one tender was answered with a value from "
            "another tender. The other 9 unanswerable questions were correctly refused.", ""]
    out[2:2] = RUN_INFO.splitlines() + [""]

    (RESULTS / "v2_heldout_report.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(out[: out.index("## 4. Failed questions (%d)" % len(failed)) + 1]))
    print("Failures by category:", dict(counts))
    if pending:
        print("PENDING:", len(pending), pending[:12], "...")


if __name__ == "__main__":
    main()
