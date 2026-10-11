# Load test: POST /api/chat

Simulated users ask questions from `eval/dataset.jsonl` in the `eval-test-user` chat: about 80% document questions and 20% spreadsheet questions, 2–5 s apart. The API runs with two test-only settings, both off by default:
- `LLM_STUB=1`: every LLM call returns a fake reply after 1–2 s, so no Groq tokens are used.
- `LOADTEST=1`: the per-session chat rate limit is off.

Everything else is the real system: 2 uvicorn workers, local embeddings, Pinecone, BM25 and Redis.

```bash
bash loadtest/run.sh        # 10, 25, 50, 100 users, 2 min each; writes loadtest/results/
```

## Results

Measured on a laptop: Docker with 8 CPUs and 7.6 GB of memory, and Pinecone serverless in `us-east-1`. "API CPU" is per core, so 800% means all 8 cores are busy.

| Users | Requests | Req/s | p50 | p95 | Errors | API CPU (median) | API memory |
|---|---|---|---|---|---|---|---|
| 10 | 148 | 1.3 | 4.0 s | 5.5 s | 0% | 20% | 1.6 GiB |
| 25 | 380 | 3.2 | 3.8 s | 5.3 s | 0% | 40% | 1.6 GiB |
| 50 | 749 | 6.3 | 3.9 s | 5.4 s | 0% | 117% | 1.7 GiB |
| 100 | 962 | 8.2 | 5.8 s | 15 s | 0% | 249% | 1.7 GiB |
| 100 (rerun) | 1536 | 12.9 | 3.8 s | 5.2 s | 0% | not sampled | not sampled |

Full table: [`results/summary.md`](results/summary.md). Raw Locust and `docker stats` output is in [`results/`](results/).

About 3 s of each request is the stubbed LLM: 2 calls of 1–2 s each, the router's classify plus the answer. So the system's own share is the time above that.

## Where the time goes

Each stage was measured on its own ([`stage_timing.txt`](results/stage_timing.txt)), in parallel ([`concurrency_probe.txt`](results/concurrency_probe.txt)), and during the 100-user rerun ([`probe_under_load.txt`](results/probe_under_load.txt)):

| Stage | Idle | Under 100-user load | When run in parallel |
|---|---|---|---|
| Pinecone query | 272 ms | **434 ms p50, 1.1 s max** | flat at about 240 ms; throughput grows with parallel calls |
| Pinecone list (`has_chunks`) | 240 ms | 216 ms | — |
| Embed question (CPU) | 36 ms | 19 ms | **92 → 30 calls/s** at 8 in parallel |
| BM25 search | 4 ms | 3 ms | about 600 calls/s |
| Redis round trip | 1 ms | — | Redis CPU at most 2.3% |

**Bottleneck: Pinecone round trips.** Each document question makes two Pinecone calls one after the other: a `list` to check that the chat has documents, then the query. That's about 0.5 s with no load, and 0.6–0.7 s at 100 users once query latency rises. This is most of the system's own share of each request, and it's network time to `us-east-1`, so adding CPU or workers won't reduce it.

**Not the bottleneck (yet):**
- **Uvicorn workers and CPU:** at 100 users the API used a median of 249% of 800%, so neither the 2 workers nor the cores were maxed out.
- **The embedding model:** each call uses 4 PyTorch threads, so calls running in parallel compete for the cores. Its throughput drops from 92 to 30 calls/s per process, and each call takes up to 50 times longer (519 ms at 16 in parallel). With 2 workers that limit is roughly 60 questions/s, well above the 13 measured, but it's the first local limit the system will hit.
- **BM25 and Redis:** both have far more capacity than this test used.

**The first 100-user run's tail didn't repeat.** In that run, p95 reached 15 s (max 19 s) and throughput fell to 3–4 req/s for the second half of the step, with CPU not maxed out. The rerun reached 12.9 req/s with p95 5.2 s. The cause wasn't confirmed: the API logs were lost when the container restarted. Candidates are Pinecone latency spikes (single queries took up to 1.1 s under load) and other load on the same laptop.

**The real-world limit is the LLM, not this system.** The stub hides Groq. On Groq's free tier (8,000 tokens per minute, about 3,500 tokens per question), the real app can answer about 2 questions per minute in total.

## After removing the extra Pinecone call

Each chat now has a `has_documents` flag in Redis. Ingestion sets it, and deleting the chat clears it. Chats created before the flag existed check Pinecone once, then save the answer. Document questions now make **one** Pinecone call instead of two.

Each step was run twice with `LLM_STUB=1` (`LABEL=flag STEPS="50 50 100 100" bash loadtest/run.sh`). The system's own time is each request's total minus its fake-LLM sleep, which the API reports in an `X-LLM-Stub-Ms` header only when `LLM_STUB=1`.

| Users | Run | Req/s | p50 | p95 | Errors | System time p50 / p95 (documents) | System time p50 / p95 (spreadsheet) |
|---|---|---|---|---|---|---|---|
| 50 | before | 6.3 | 3.9 s | 5.4 s | 0% | not measured | not measured |
| 50 | after, run 1 | 6.8 | 3.4 s | 4.9 s | 0% | 290 / 528 ms | 50 / 82 ms |
| 50 | after, run 2 | 6.8 | 3.4 s | 4.9 s | 0% | 291 / 399 ms | 51 / 81 ms |
| 100 | before (run 1) | 8.2 | 5.8 s | 15 s | 0% | not measured | not measured |
| 100 | before (rerun) | 12.9 | 3.8 s | 5.2 s | 0% | not measured | not measured |
| 100 | after, run 1 | 13.6 | 3.4 s | 4.9 s | 0% | 295 / 523 ms | 56 / 102 ms |
| 100 | after, run 2 | 13.6 | 3.4 s | 5.0 s | 0% | 293 / 497 ms | 51 / 102 ms |

- **p50 dropped by about 0.4–0.5 s** at both 50 and 100 users, and p95 dropped by about 0.3–0.5 s. Both repeats agree.
- **The system's own time is now about 0.3 s for a document question**, mostly the single Pinecone query (about 240 ms with no load). It stays the same from 50 to 100 users, so the system isn't saturating at 100 users. The rest of each request is the fake LLM: about 3.0 s for documents and 4.5 s for spreadsheets, whose 3 LLM calls are all stubbed.
- **Spreadsheet questions take about 50 ms** of the system's own time, because they don't call Pinecone at all.

## Pinecone usage

The test uses reads only; the index has 825 vectors before and after. Estimated use is about 7,000 read units: 2 per document question (list + query), 1 per spreadsheet question, plus probes. That's under 1% of the free Starter plan's monthly read allowance; the Pinecone console has the exact figure.

## Not tested

More than 100 users, uploads and ingestion under load, and the frontend.
