"""Retrieval-only eval: hit rate and latency of the documents path, no LLM.

For the factual/table/paraphrased questions it runs query_chunks + the token
budget (exactly what the LLM would be sent), checks whether each question's
evidence is in those chunks (same check as run_eval.py), and times it. No Groq
calls, so it costs no tokens. Saves eval/results/retrieval_<label>.json.

    docker compose run --rm -T -v "./eval:/app/eval" worker \\
        python eval/time_retrieval.py --label rerank --compare hybrid
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import run_eval as ev  # noqa: E402  (also puts the backend on sys.path)
from main import fit_to_budget  # noqa: E402
from src.vectorstore import query_chunks  # noqa: E402

TYPES = ["factual", "table", "paraphrased"]


def p95(values: list[float]) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(round(0.95 * len(values))) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run", help="saved as eval/results/retrieval_<label>.json")
    parser.add_argument("--compare", help="label of an earlier run to compare against")
    args = parser.parse_args()

    rows = [r for r in ev.load_dataset(None) if r["type"] in TYPES]
    query_chunks("warm-up", ev.NAMESPACE, ev.N_CTX)  # load models / build indexes outside the timing

    results = []
    for r in rows:
        start = time.perf_counter()
        sent = fit_to_budget(query_chunks(r["question"], ev.NAMESPACE, ev.N_CTX))
        ms = (time.perf_counter() - start) * 1000
        hit = None if r.get("evidence") is None else any(ev.compact(r["evidence"]) in ev.compact(d) for d, _ in sent)
        results.append({"id": r["id"], "type": r["type"], "hit": hit, "ms": round(ms), "chunks_sent": len(sent)})

    out = ev.RESULTS_DIR / f"retrieval_{args.label}.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")

    base = None
    if args.compare:
        base = {r["id"]: r for r in json.loads((ev.RESULTS_DIR / f"retrieval_{args.compare}.json").read_text(encoding="utf-8"))}

    def hits(rs: list[dict]) -> str:
        scored = [r["hit"] for r in rs if r["hit"] is not None]
        return f"{sum(scored)}/{len(scored)}"

    arrow = f"{args.compare} -> {args.label}" if base else args.label
    print(f"\nRetrieval hit rate ({arrow}):")
    for t in TYPES + ["overall"]:
        rs = results if t == "overall" else [r for r in results if r["type"] == t]
        before = f"{hits([base[r['id']] for r in rs])} -> " if base else ""
        print(f"  {t:<12} {before}{hits(rs)}")
    if base:
        changed = {r["id"]: (base[r["id"]]["hit"], r["hit"]) for r in results if base[r["id"]]["hit"] != r["hit"]}
        print(f"  changed: {changed or 'none'}")

    ms = [r["ms"] for r in results]
    line = f"p50 {statistics.median(ms):.0f} ms, p95 {p95(ms):.0f} ms, max {max(ms):.0f} ms"
    if base:
        bms = [b["ms"] for b in base.values()]
        line = f"{args.compare}: p50 {statistics.median(bms):.0f} ms, p95 {p95(bms):.0f} ms  ->  {args.label}: {line}"
    print(f"Retrieval latency over {len(ms)} questions: {line}")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
