"""Held-out eval (v2): the v1 eval scripts, unchanged, pointed at the v2
dataset, the v2 documents and their own Pinecone namespace.

    python eval/run_eval_v2.py --out v2_heldout                 # ingest + all questions
    python eval/run_eval_v2.py --reuse --out v2_heldout          # questions only
    python eval/run_eval_v2.py --retry-errors --out v2_heldout   # resume after a rate limit
    python eval/run_eval_v2.py ingest                            # ingest only
    python eval/run_eval_v2.py retrieval --label v2              # retrieval-only timing
"""
import asyncio
import sys

import run_eval as ev

ev.DATASET = ev.ROOT / "eval" / "dataset_v2.jsonl"
ev.DOCS_DIR = ev.ROOT / "Test documents v2"
ev.NAMESPACE = ev.SESSION_ID = "eval-v2-heldout"

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "ingest":
        ev.ingest()
    elif mode == "retrieval":
        del sys.argv[1]
        import time_retrieval  # reads ev.NAMESPACE and ev.load_dataset at run time

        time_retrieval.main()
    else:
        asyncio.run(ev.main())
