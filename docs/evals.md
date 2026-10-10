# Running the evals

Both scripts run inside the worker image, so OCR and the other dependencies match production. Run them from the repo root.

On Windows with Git Bash, prefix each command with `MSYS_NO_PATHCONV=1` and use `$(pwd -W)` in the mount paths, for example `-v "$(pwd -W)/eval:/app/eval"`. Without that, Git Bash rewrites `/app/...` into a Windows path and the container can't find the files.

## End-to-end eval: `eval/run_eval.py`

Each question goes through the real pipeline (router, then retrieval, token budget, LLM and citations). The script records retrieval hits, LLM-judged accuracy, tokens and latency.

```bash
docker compose run --rm -v "./eval:/app/eval" -v "./Test documents:/app/Test documents" \
  worker python eval/run_eval.py --out my_run --compare final
```

| Flag | What it does |
|---|---|
| `--out NAME` | Save to `eval/results/NAME.jsonl` (default `baseline`). |
| `--compare NAME` | Print the summary next to `eval/results/NAME.jsonl`. |
| `--types a,b` | Run only these question types (`factual`, `table`, `paraphrased`, `aggregation`, `unanswerable`). |
| `--reuse` | Skip ingestion and use what is already in the `eval-test-user` namespace. |
| `--reingest FILE ...` | Replace only these documents, then evaluate. |
| `--retry-errors` | Re-run only the questions that errored in `--out` (for example after Groq's daily token limit) and merge them in. |
| `--limit N` | Run only the first N questions. |

Without `--reuse` or `--reingest`, the script clears the namespace and ingests every file in `Test documents/`.

Rate limits: the script waits 30 seconds between questions (Groq's free tier allows 8,000 tokens per minute) and retries once after a 429. When the daily token limit is reached, it stops, saves its progress, and the rest can be finished with `--retry-errors`.

Judge: `llama-3.1-8b-instant` is tried first. It isn't available on every Groq key, in which case the script uses `openai/gpt-oss-20b`; `JUDGE_MODEL` overrides it.

## Retrieval-only eval: `eval/time_retrieval.py`

This measures retrieval hit rate and latency for the factual, table and paraphrased questions. It makes no LLM calls, so it uses no Groq tokens.

```bash
docker compose run --rm -v "./eval:/app/eval" \
  worker python eval/time_retrieval.py --label my_change --compare default
```

Results are saved to `eval/results/retrieval_<label>.json`. `--compare` prints hits and latency side by side, along with the questions whose result changed.

## Synthetic spreadsheet

The eval's spreadsheet questions use `Test documents/shipments_synthetic.xlsx`, which `eval/make_synthetic_sheet.py` generates with a fixed seed. Running that script also prints the expected answers, computed directly with pandas.
