import asyncio
import base64
import os
from datetime import datetime
from typing import Literal

from celery.result import AsyncResult
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.llm import (
    LLM_STUB,
    answer_question,
    answer_with_web_search,
    estimate_tokens,
    generate_title,
    keep_cited,
    needs_web_search,
    stub_seconds,
)
from src.chat_store import (
    append_messages,
    create_chat,
    delete_chat,
    get_chat,
    has_documents,
    list_chats,
    needs_title,
    owns_chat,
    session_chat_ids,
    set_has_documents,
    stale_chat_ids,
)
from src.rate_limit import (
    CHAT_RATE_LIMIT_PER_MINUTE,
    UPLOAD_RATE_LIMIT_PER_MINUTE,
    add_tokens,
    check_tokens,
    hit,
)
from src.router import route_question, sources_for
from src.sheets import delete_sheets
from src.vectorstore import delete_chat_chunks, has_chunks, list_documents, query_chunks
from src.worker import celery_app, ingest_documents

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "20")) * 1024 * 1024
# Retrieved context sent to the LLM per question. The Groq free tier allows
# 8,000 tokens per minute, and the prompt, history, and answer need room too.
MAX_CONTEXT_TOKENS = int(os.environ.get("MAX_CONTEXT_TOKENS", "3000"))

GREETINGS = {
    "hi", "hello", "hey", "hii", "hiya", "yo", "howdy",
    "hi there", "hello there", "hey there",
    "good morning", "good afternoon", "good evening",
}

app = FastAPI(title="RAG Doc Chat API")

app.add_middleware(
    CORSMiddleware,
    # The frontend calls this API directly from its own origin (no nginx
    # proxy — see frontend/nginx.conf), and nothing here uses cookies, so a
    # wildcard is safe: no allow_credentials, so browsers never send any.
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # Retry-After isn't CORS-safelisted; without this the browser hides it.
    expose_headers=["Retry-After"],
)

if LLM_STUB:
    # Load tests only: report the fake LLM time, so the load test can
    # subtract it and measure this system's own time.
    @app.middleware("http")
    async def report_stub_time(request, call_next):
        spent = [0.0]
        stub_seconds.set(spent)
        response = await call_next(request)
        response.headers["X-LLM-Stub-Ms"] = str(round(spent[0] * 1000))
        return response


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []
    chat_id: str | None = None
    # Optional retrieval filters, ANDed with the chat_id filter in Pinecone.
    doc_type: Literal["pdf", "docx", "xlsx", "csv", "txt"] | None = None
    uploaded_after: datetime | None = None
    uploaded_before: datetime | None = None


def get_session_id(x_session_id: str | None = Header(default=None)) -> str:
    # Falls back to a fixed bucket if a client ever calls the API without
    # the header — the real frontend always sends its per-tab session id.
    return x_session_id or "anonymous"


async def chat_limits(session_id: str = Depends(get_session_id)) -> None:
    await hit("chat", session_id, CHAT_RATE_LIMIT_PER_MINUTE)
    await check_tokens(session_id)


async def upload_limits(session_id: str = Depends(get_session_id)) -> None:
    await hit("upload", session_id, UPLOAD_RATE_LIMIT_PER_MINUTE)


async def remove_chat(chat_id: str) -> None:
    # Pinecone's SDK is sync — keep it off the event loop.
    await asyncio.to_thread(delete_chat_chunks, chat_id)
    await asyncio.to_thread(delete_sheets, chat_id)
    await delete_chat(chat_id)


async def cleanup_stale_chats(max_age_hours: float = 6) -> None:
    """No login system, so this — not the per-tab session id alone — is what
    actually makes old chats and their indexed documents go away instead of
    accumulating forever."""
    for chat_id in await stale_chat_ids(max_age_hours):
        await remove_chat(chat_id)


async def wipe_session(session_id: str) -> None:
    for chat_id in await session_chat_ids(session_id):
        await remove_chat(chat_id)


RATE_LIMIT_MARKERS = ("rate_limit_exceeded", "tokens per minute", "Request too large")


def groq_error_reply(exc: Exception) -> dict:
    """Map a Groq failure to the chat reply. Only a 401 points at the API key
    (the frontend shows the key hint when error_status is 401); a 413/429 is
    a size or rate limit, not a key problem, so it gets a plain retry message
    and no error box."""
    status = getattr(exc, "status_code", None)
    if status in (413, 429) or any(marker in str(exc) for marker in RATE_LIMIT_MARKERS):
        return {"answer": "Request too large or rate limited, try again shortly."}
    reply = {"answer": "Sorry, I couldn't reach Groq to generate an answer.", "error": str(exc)}
    if status == 401:
        reply["error_status"] = 401
    return reply


def context_line(doc: str, meta: dict) -> str:
    return f"[From {meta.get('source', 'document')}]\n{doc}"


def fit_to_budget(results: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Keep retrieved chunks in rank order until their estimated tokens reach
    MAX_CONTEXT_TOKENS; drop the rest. The top chunk is always kept (cut to
    the budget if it alone is too big) so a question never loses all context.
    Returns the chunks actually sent, so citations can only point at those."""
    kept, used = [], 0
    for doc, meta in results:
        cost = estimate_tokens(context_line(doc, meta))
        if used + cost > MAX_CONTEXT_TOKENS:
            if not kept:
                kept.append((doc[: MAX_CONTEXT_TOKENS * 4], meta))
            break
        kept.append((doc, meta))
        used += cost
    return kept


def is_greeting(text: str) -> bool:
    return text.strip().lower().strip("!.,? ") in GREETINGS


def build_retrieval_query(question: str, history: list[ChatMessage]) -> str:
    """Fold the previous user turn into the search query so follow-ups
    (e.g. "what about her skills?") still retrieve the right chunks."""
    last_user = next(
        (m.content for m in reversed(history) if m.role == "user"), None
    )
    return f"{last_user}\n{question}" if last_user else question


@app.get("/api/status")
async def status():
    return {"groq_connected": bool(os.environ.get("GROQ_API_KEY"))}


@app.get("/api/documents")
async def get_documents(chat_id: str, session_id: str = Depends(get_session_id)):
    if not await owns_chat(chat_id, session_id):
        return []
    return await asyncio.to_thread(list_documents, chat_id)


@app.get("/api/chats")
async def get_chats(session_id: str = Depends(get_session_id)):
    await cleanup_stale_chats()
    return await list_chats(session_id)


@app.post("/api/chats")
async def new_chat(session_id: str = Depends(get_session_id)):
    return await create_chat(session_id)


@app.get("/api/chats/{chat_id}")
async def get_chat_by_id(chat_id: str, session_id: str = Depends(get_session_id)):
    chat = await get_chat(chat_id)
    if chat is None or chat.get("session_id") != session_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.delete("/api/session")
async def clear_session(session_id: str = Depends(get_session_id)):
    """Called when the visitor leaves the chat (e.g. back to the homepage) —
    wipes their chats and indexed documents immediately, instead of waiting
    for the stale-chat TTL sweep."""
    await wipe_session(session_id)
    return {"ok": True}


@app.post("/api/session/clear-beacon")
async def clear_session_beacon(session_id: str):
    """Same as DELETE /api/session, but reads session_id from the query
    string instead of a header. navigator.sendBeacon() — the only browser
    API that reliably fires a request while a page is unloading (reload,
    tab close, navigating away) — can't set custom headers, so this is
    what the frontend's pagehide handler calls instead."""
    await wipe_session(session_id)
    return {"ok": True}


@app.post("/api/documents", status_code=202, dependencies=[Depends(upload_limits)])
async def upload_documents(
    chat_id: str = Form(...),
    files: list[UploadFile] = File(...),
    session_id: str = Depends(get_session_id),
):
    """Queue parse → chunk → embed → Pinecone on the Celery worker and return
    right away; the frontend polls /api/upload/status/{task_id}."""
    if not await owns_chat(chat_id, session_id):
        raise HTTPException(status_code=404, detail="Chat not found")

    payload, total = [], 0
    for file in files:
        data = await file.read()
        total += len(data)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
        payload.append({"name": file.filename, "data": base64.b64encode(data).decode()})

    task = await asyncio.to_thread(ingest_documents.delay, chat_id, session_id, payload)
    return {"task_id": task.id, "status": "queued"}


@app.get("/api/upload/status/{task_id}")
async def upload_status(task_id: str, session_id: str = Depends(get_session_id)):
    result = AsyncResult(task_id, app=celery_app)
    # .state / .result read the Celery backend with a sync Redis client.
    state, value = await asyncio.to_thread(lambda: (result.state, result.result))

    if state == "SUCCESS":
        if value.get("session_id") != session_id:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"task_id": task_id, "status": "success", "result": value}
    if state == "FAILURE":
        return {"task_id": task_id, "status": "failure", "error": str(value)}
    # PENDING (queued, or an unknown id — Celery can't tell them apart) / STARTED / RETRY
    return {"task_id": task_id, "status": state.lower()}


@app.post("/api/chat", dependencies=[Depends(chat_limits)])
async def chat(req: ChatRequest, session_id: str = Depends(get_session_id)):
    # A chat_id that's missing or belongs to someone else's session gets a
    # fresh chat instead of an error — same effect as opening the sidebar's
    # "New chat" button.
    chat_id = req.chat_id if req.chat_id and await owns_chat(req.chat_id, session_id) else None
    chat_id = chat_id or (await create_chat(session_id))["id"]

    async def respond(payload: dict, title: str | None = None) -> dict:
        await append_messages(
            chat_id,
            {"role": "user", "content": req.question},
            {"role": "assistant", "content": payload["answer"]},
            title=title,
            session_id=session_id,
        )
        return {**payload, "chat_id": chat_id}

    async def title_for(answer: str) -> str | None:
        # A greeting-truncated title ("hi") is a poor label; only worth the
        # extra Groq call once, on a chat's first real, grounded answer.
        if not await needs_title(chat_id):
            return None
        try:
            title, tokens = await generate_title(req.question, answer)
        except Exception:
            return None
        await add_tokens(session_id, tokens)
        return title

    has_docs = await has_documents(chat_id)
    if has_docs is None:
        # Chats from before the Redis flag existed: ask Pinecone once, then remember.
        has_docs = await asyncio.to_thread(has_chunks, chat_id)
        await set_has_documents(chat_id, has_docs)
    history = req.history
    search_query = build_retrieval_query(req.question, history)
    # Candidates to retrieve; fit_to_budget then keeps only as many as fit
    # MAX_CONTEXT_TOKENS (the real ceiling: Groq free tier is 8,000 tokens
    # per minute). Pinecone returns fewer than top_k when the chat has fewer.
    n_ctx = 40

    if is_greeting(req.question):
        answer = (
            "Hello! What can I help you with?"
            if has_docs
            else "Hello! I don't have any documents to work with yet. Upload one to get started."
        )
        return await respond({"answer": answer})

    # Spreadsheet counting/totals are computed with pandas over every row
    # (src/router.py); everything else falls through to the RAG pipeline below.
    if req.doc_type in (None, "xlsx", "csv"):
        try:
            routed = await route_question(req.question, chat_id)
        except Exception as exc:
            return await respond(groq_error_reply(exc))
        await add_tokens(session_id, routed.get("tokens", 0))
        if routed["route"] == "spreadsheet":
            answer, cited = keep_cited(routed["answer"], sources_for(routed))
            sources = [
                {"number": number, "source": meta["source"], "chunk_index": None, "text": doc}
                for number, (doc, meta) in enumerate(cited, 1)
            ]
            return await respond({"answer": answer, "sources": sources}, title=await title_for(answer))

    date_range = (req.uploaded_after, req.uploaded_before)
    results = await asyncio.to_thread(
        query_chunks, search_query, chat_id, n_ctx, req.doc_type, date_range
    ) if has_docs else []
    results = fit_to_budget(results)
    context_chunks = [context_line(doc, meta) for doc, meta in results]

    if needs_web_search(req.question):
        try:
            answer, trace, tokens = await answer_with_web_search(
                req.question, context_chunks, [m.model_dump() for m in history]
            )
        except Exception as exc:
            return await respond(groq_error_reply(exc))
        await add_tokens(session_id, tokens)
        searched_at = trace.pop("searched_at", None)
        return await respond({
            "answer": answer,
            "web_search": {
                **trace,
                "searched_at": searched_at.isoformat() if searched_at else None,
            },
        }, title=await title_for(answer))

    if not results:
        filtered = req.doc_type or req.uploaded_after or req.uploaded_before
        return await respond({"answer": (
            "I don't know. No documents match those filters."
            if has_docs and filtered
            else "I don't know. No documents have been indexed yet."
        )})

    try:
        answer, tokens = await answer_question(req.question, context_chunks, [m.model_dump() for m in history])
    except Exception as exc:
        return await respond(groq_error_reply(exc))
    await add_tokens(session_id, tokens)

    # Only the chunks the answer actually cites, numbered [1], [2]... to match
    # the markers in the answer. An "I don't know." cites nothing, so no sources.
    answer, cited = keep_cited(answer, results)
    sources = [
        {
            "number": number,
            "source": meta.get("source", "unknown"),
            "chunk_index": meta.get("chunk_index"),
            "text": doc[:300] + ("..." if len(doc) > 300 else ""),
        }
        for number, (doc, meta) in enumerate(cited, 1)
    ]
    return await respond({"answer": answer, "sources": sources}, title=await title_for(answer))
