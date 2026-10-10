"""Time the documents-path retrieval (no LLM calls, no Groq tokens).

Runs query_chunks + the token budget for the factual/table/paraphrased
questions in the eval namespace and prints p50/p95. Use it before and after a
retrieval change to compare latency.

    docker compose run --rm -T -v "./eval:/app/eval" worker python eval/time_retrieval.py --label before
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" if (ROOT / "backend").is_dir() else ROOT))

from main import fit_to_budget  # noqa: E402
from src.vectorstore import query_chunks  # noqa: E402

NAMESPACE = "eval-test-user"
TYPES = {"factual", "table", "paraphrased"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    args = parser.parse_args()

    rows = [json.loads(line) for line in (ROOT / "eval" / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = [r["question"] for r in rows if r["type"] in TYPES]

    query_chunks("warm-up", NAMESPACE, 40)  # load models / open connections outside the timing
    times = []
    for q in questions:
        start = time.perf_counter()
        fit_to_budget(query_chunks(q, NAMESPACE, 40))
        times.append((time.perf_counter() - start) * 1000)

    times.sort()
    p95 = times[min(len(times) - 1, int(round(0.95 * len(times))) - 1)]
    print(f"[{args.label}] retrieval latency over {len(times)} questions: "
          f"p50 {statistics.median(times):.0f} ms, p95 {p95:.0f} ms, max {times[-1]:.0f} ms")


if __name__ == "__main__":
    main()
