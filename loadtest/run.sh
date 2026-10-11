#!/usr/bin/env bash
# Load test of POST /api/chat in 4 steps (10, 25, 50, 100 users, 2 min each).
# Run from the repo root:  bash loadtest/run.sh
# Needs the eval-test-user documents already ingested (python eval/run_eval.py).
set -euo pipefail
export MSYS_NO_PATHCONV=1                  # Git Bash on Windows: keep /mnt/... paths as-is
ROOT="$(pwd -W 2>/dev/null || pwd)"
OUT=loadtest/results
STEPS="${STEPS:-10 25 50 100}"
mkdir -p "$OUT"

# Fake LLM (no Groq tokens) and no per-session rate limit, for the API only.
LLM_STUB=1 LOADTEST=1 docker compose up -d --build api
until curl -sf localhost:8000/api/status >/dev/null; do sleep 3; done

# Always (even if Locust fails): remove the test chat record only, not the
# eval data, so the stale-chat cleanup can never delete the eval-test-user
# documents; then restart the API with both test settings back off.
cleanup() {
  # Requests still in flight when Locust stops would re-create the chat record
  # when they save their answer, so restart the API first, then delete it.
  docker compose up -d api
  docker compose exec -T redis redis-cli DEL chat:eval-test-user chat:eval-test-user:msgs session:loadtest:chats >/dev/null
  docker compose exec -T redis redis-cli ZREM chats:updated eval-test-user >/dev/null
  echo "test chat keys left: $(docker compose exec -T redis redis-cli EXISTS chat:eval-test-user chat:eval-test-user:msgs session:loadtest:chats)"
}
trap cleanup EXIT

# The test session must own the eval-test-user chat, or the API would answer
# in a new, empty chat.
docker compose exec -T api python -c "import asyncio; from src.chat_store import _save_new; asyncio.run(_save_new('eval-test-user', 'loadtest'))"

# Warm-up (not recorded): each uvicorn worker loads the embedding model and
# builds the BM25 index on its first request, which adds ~10 s.
docker run --rm --network ragdocchat_default -v "$ROOT:/mnt/repo" locustio/locust \
  -f /mnt/repo/loadtest/locustfile.py --headless --only-summary -u 4 -r 4 -t 20s --host http://api:8000 >/dev/null

for users in $STEPS; do
  echo "=== $users users"
  stats="$OUT/docker_stats_${users}.csv"
  : > "$stats"
  (while true; do docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' >> "$stats"; sleep 5; done) &
  sampler=$!
  docker run --rm --network ragdocchat_default -v "$ROOT:/mnt/repo" locustio/locust \
    -f /mnt/repo/loadtest/locustfile.py --headless --only-summary \
    -u "$users" -r "$(( users / 10 > 0 ? users / 10 : 1 ))" -t 2m \
    --host http://api:8000 --csv "/mnt/repo/$OUT/step_${users}" || echo "locust exited with $?"
  kill "$sampler"
done

python loadtest/summarize.py
