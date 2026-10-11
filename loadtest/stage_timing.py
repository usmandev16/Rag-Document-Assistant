"""Time each stage of a documents-path request on its own (no LLM), and show
the Pinecone read units each call costs. Run inside the api container:

    docker compose exec -T api python - < loadtest/stage_timing.py
"""
import asyncio
import statistics
import time

from src import lexical
from src.embeddings import embed_texts
from src.redis_client import redis
from src.vectorstore import HYBRID_K, build_filter, get_index

NAMESPACE = "eval-test-user"
QUESTIONS = [
    "What was the policy rate as of December 2025?",
    "Under which major object is contingent expenditure classified?",
    "Which city was made the country's second capital?",
    "How much did overseas Pakistanis send home in the first half of FY2026?",
]
RUNS = 20


def p50(fn) -> float:
    times = []
    for i in range(RUNS):
        start = time.perf_counter()
        fn(QUESTIONS[i % len(QUESTIONS)])
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


embed_texts(["warm-up"])
vector = embed_texts([QUESTIONS[0]])[0]
index = get_index()
flt = build_filter(NAMESPACE)

query = index.query(vector=vector, top_k=HYBRID_K, namespace=NAMESPACE, filter=flt, include_metadata=True)
listing = index.list_paginated(namespace=NAMESPACE, limit=1)
print(f"Pinecone read units: query {getattr(query.usage, 'read_units', '?')}, "
      f"list (has_chunks) {getattr(listing.usage, 'read_units', '?')}")

rows = [
    ("embed question (MiniLM, CPU)", p50(lambda q: embed_texts([q]))),
    ("Pinecone dense query (top 20)", p50(lambda q: index.query(vector=vector, top_k=HYBRID_K, namespace=NAMESPACE,
                                                                filter=flt, include_metadata=True))),
    ("Pinecone list (has_chunks)", p50(lambda q: index.list_paginated(namespace=NAMESPACE, limit=1))),
    ("BM25 search (top 20)", p50(lambda q: lexical.search(NAMESPACE, q, HYBRID_K))),
]


async def redis_p50() -> float:
    times = []
    for _ in range(RUNS):
        start = time.perf_counter()
        await redis.hget("chat:eval-test-user", "session_id")
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


rows.append(("Redis round trip", asyncio.run(redis_p50())))
for name, ms in rows:
    print(f"{name:<32} p50 {ms:7.1f} ms")
