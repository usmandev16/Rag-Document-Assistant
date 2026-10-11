#!/usr/bin/env bash
# Load test of POST /api/chat, 2 minutes per step.
# Run from the repo root:
#   bash loadtest/run.sh                                   # 10, 25, 50, 100 users
#   LABEL=flag STEPS="50 50 100 100" bash loadtest/run.sh  # repeat a step: files get _run2
# Needs the eval-test-user documents already ingested (python eval/run_eval.py).
set -euo pipefail
export MSYS_NO_PATHCONV=1                  # Git Bash on Windows: keep /mnt/... paths as-is
ROOT="$(pwd -W 2>/dev/null || pwd)"
OUT=loadtest/results
STEPS="${STEPS:-10 25 50 100}"
LABEL="${LABEL:-step}"
mkdir -p "$OUT"

# Fake LLM (no Groq tokens) and no per-session rate limit, for the API only.
LLM_STUB=1 LOADTEST=1 docker compose up -d --build api
until curl -sf localhost:8000/api/status >/dev/null; do sleep 3; done

TEST_KEYS="chat:eval-test-user chat:eval-test-user:msgs chat:eval-test-user:has_docs session:loadtest:chats"

# Always (even if Locust fails): restart the API with both test settings off,
# then remove the test chat's Redis keys only (not the eval data), so the
# stale-chat cleanup can never delete the eval-test-user documents. Restart
# first: requests still in flight would re-create the chat record.
sampler=""
cleanup() {
  [ -n "$sampler" ] && kill "$sampler" 2>/dev/null || true   # never leave the docker stats loop running
  LLM_STUB=0 LOADTEST=0 docker compose up -d api
  until curl -sf localhost:8000/api/status >/dev/null; do sleep 3; done
  docker compose exec -T redis redis-cli DEL $TEST_KEYS >/dev/null
  docker compose exec -T redis redis-cli ZREM chats:updated eval-test-user >/dev/null
  echo "cleanup: LLM_STUB=$(docker compose exec -T api printenv LLM_STUB)" \
       "LOADTEST=$(docker compose exec -T api printenv LOADTEST)" \
       "test keys left=$(docker compose exec -T redis redis-cli EXISTS $TEST_KEYS)"
}
trap cleanup EXIT

# The test session must own the eval-test-user chat, or the API would answer
# in a new, empty chat.
docker compose exec -T api python -c "import asyncio; from src.chat_store import _save_new; asyncio.run(_save_new('eval-test-user', 'loadtest'))"

# Warm-up (not recorded): each uvicorn worker loads the embedding model and
# builds the BM25 index on its first request, which adds ~10 s.
docker run --rm --network ragdocchat_default -v "$ROOT:/mnt/repo" locustio/locust \
  -f /mnt/repo/loadtest/locustfile.py --headless --only-summary -u 4 -r 4 -t 20s --host http://api:8000 >/dev/null

declare -A seen=()
for users in $STEPS; do
  seen[$users]=$(( ${seen[$users]:-0} + 1 ))
  name="${LABEL}_${users}"
  [ "${seen[$users]}" -gt 1 ] && name="${name}_run${seen[$users]}"
  echo "=== $name: $users users"
  stats="$OUT/docker_stats_${name}.csv"
  : > "$stats"
  (while true; do docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' >> "$stats"; sleep 5; done) &
  sampler=$!
  docker run --rm --network ragdocchat_default -v "$ROOT:/mnt/repo" -e "RAW_CSV=/mnt/repo/$OUT/raw_${name}.csv" \
    locustio/locust -f /mnt/repo/loadtest/locustfile.py --headless --only-summary \
    -u "$users" -r "$(( users / 10 > 0 ? users / 10 : 1 ))" -t 2m \
    --host http://api:8000 --csv "/mnt/repo/$OUT/${name}" || echo "locust exited with $?"
  kill "$sampler"
done

python loadtest/summarize.py
