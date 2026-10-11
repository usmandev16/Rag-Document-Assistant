"""Time single retrieval stages while a load test is running, to see which one
slows down under load. Run inside the api container during a load test:

    docker compose exec -T api python - < loadtest/probe_under_load.py
"""
import statistics
import time

from src import lexical
from src.embeddings import embed_texts
from src.vectorstore import HYBRID_K, build_filter, get_index

NAMESPACE = "eval-test-user"
QUESTION = "What was the policy rate as of December 2025?"
vector = embed_texts([QUESTION])[0]
index = get_index()
flt = build_filter(NAMESPACE)
stages = {
    "embed question": lambda: embed_texts([QUESTION]),
    "Pinecone query": lambda: index.query(vector=vector, top_k=HYBRID_K, namespace=NAMESPACE, filter=flt,
                                          include_metadata=True),
    "Pinecone list": lambda: index.list_paginated(namespace=NAMESPACE, limit=1),
    "BM25 search": lambda: lexical.search(NAMESPACE, QUESTION, HYBRID_K),
}
for name, fn in stages.items():
    times = []
    for _ in range(10):
        start = time.perf_counter()
        fn()
        times.append((time.perf_counter() - start) * 1000)
    print(f"{name:<15} under load: p50 {statistics.median(times):7.1f} ms, max {max(times):7.1f} ms")
