"""Load test for POST /api/chat. Run via loadtest/run.sh (API started with
LLM_STUB=1 and LOADTEST=1, so no Groq tokens are used and the per-session
rate limit is off).

Every simulated user asks questions from eval/dataset.jsonl in the
eval-test-user chat (documents already ingested by the eval): about 80%
document questions, 20% spreadsheet questions, 2-5 s apart.
"""
import json
import os
import random
import time
from pathlib import Path

from locust import HttpUser, between, task

ROOT = Path(__file__).resolve().parent.parent
ROWS = [json.loads(line) for line in (ROOT / "eval" / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
SHEET_QUESTIONS = [r["question"] for r in ROWS if r["type"] == "aggregation"]
DOC_QUESTIONS = [r["question"] for r in ROWS if r["type"] != "aggregation" and "shipment" not in r["question"].lower()]

CHAT_ID = "eval-test-user"   # chat whose documents the eval ingested
SESSION_ID = "loadtest"      # run.sh makes this session the owner of CHAT_ID
# One row per request: route, total ms, fake-LLM ms (from the API header), so
# the system's own time = total - fake LLM. Path set by run.sh.
RAW = open(os.environ["RAW_CSV"], "w", encoding="utf-8") if os.environ.get("RAW_CSV") else None
if RAW:
    RAW.write("route,total_ms,llm_stub_ms\n")


class ChatUser(HttpUser):
    wait_time = between(2, 5)

    @task
    def ask(self) -> None:
        sheet = random.random() < 0.2
        question = random.choice(SHEET_QUESTIONS if sheet else DOC_QUESTIONS)
        started = time.perf_counter()
        with self.client.post(
            "/api/chat",
            json={"question": question, "chat_id": CHAT_ID},
            headers={"X-Session-Id": SESSION_ID},
            name="spreadsheet" if sheet else "documents",
            timeout=120,
            catch_response=True,
        ) as response:
            # Without ownership the API silently answers in a new, empty chat,
            # which would make the numbers look better than they are.
            if response.ok and response.json().get("chat_id") != CHAT_ID:
                response.failure("answered outside the eval-test-user chat")
            elif response.ok and RAW and "X-LLM-Stub-Ms" in response.headers:
                total_ms = (time.perf_counter() - started) * 1000
                RAW.write(f"{'spreadsheet' if sheet else 'documents'},{total_ms:.0f},{response.headers['X-LLM-Stub-Ms']}\n")
                RAW.flush()
