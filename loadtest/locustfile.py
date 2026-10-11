"""Load test for POST /api/chat. Run via loadtest/run.sh (API started with
LLM_STUB=1 and LOADTEST=1, so no Groq tokens are used and the per-session
rate limit is off).

Every simulated user asks questions from eval/dataset.jsonl in the
eval-test-user chat (documents already ingested by the eval): about 80%
document questions, 20% spreadsheet questions, 2-5 s apart.
"""
import json
import random
from pathlib import Path

from locust import HttpUser, between, task

ROOT = Path(__file__).resolve().parent.parent
ROWS = [json.loads(line) for line in (ROOT / "eval" / "dataset.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
SHEET_QUESTIONS = [r["question"] for r in ROWS if r["type"] == "aggregation"]
DOC_QUESTIONS = [r["question"] for r in ROWS if r["type"] != "aggregation" and "shipment" not in r["question"].lower()]

CHAT_ID = "eval-test-user"   # chat whose documents the eval ingested
SESSION_ID = "loadtest"      # run.sh makes this session the owner of CHAT_ID


class ChatUser(HttpUser):
    wait_time = between(2, 5)

    @task
    def ask(self) -> None:
        sheet = random.random() < 0.2
        question = random.choice(SHEET_QUESTIONS if sheet else DOC_QUESTIONS)
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
