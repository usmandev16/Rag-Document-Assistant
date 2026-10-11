"""How each retrieval stage behaves when calls run in parallel threads, the
way the API runs them (asyncio.to_thread). Run inside the api container:

    docker compose exec -T api python - < loadtest/concurrency_probe.py
"""
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import torch

from src import lexical
from src.embeddings import embed_texts
from src.vectorstore import HYBRID_K, build_filter, get_index

NAMESPACE = "eval-test-user"
QUESTION = "What was the policy rate as of December 2025?"
CALLS_PER_THREAD = 3

vector = embed_texts([QUESTION])[0]
index = get_index()
flt = build_filter(NAMESPACE)
stages = {
    "embed question": lambda: embed_texts([QUESTION]),
    "Pinecone query": lambda: index.query(vector=vector, top_k=HYBRID_K, namespace=NAMESPACE, filter=flt,
                                          include_metadata=True),
    "BM25 search": lambda: lexical.search(NAMESPACE, QUESTION, HYBRID_K),
}
print(f"torch intra-op threads per call: {torch.get_num_threads()}")
for name, fn in stages.items():
    fn()  # warm-up
    for threads in (1, 4, 8, 16):
        def timed(_):
            start = time.perf_counter()
            fn()
            return (time.perf_counter() - start) * 1000

        wall = time.perf_counter()
        with ThreadPoolExecutor(threads) as pool:
            times = list(pool.map(timed, range(threads * CALLS_PER_THREAD)))
        wall = time.perf_counter() - wall
        print(f"{name:<15} {threads:>2} parallel: p50 {statistics.median(times):7.1f} ms per call, "
              f"{len(times) / wall:6.1f} calls/s")
