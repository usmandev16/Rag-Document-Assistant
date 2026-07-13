import os
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.chunking import chunk_text
from src.llm import answer_question, answer_with_web_search, generate_title, needs_web_search
from src.loaders import extract_text
from src.chat_store import (
    append_messages,
    create_chat,
    delete_chat,
    get_chat,
    list_chats,
    needs_title,
    owns_chat,
    session_chat_ids,
    stale_chat_ids,
)
from src.vectorstore import add_chunks, chunk_count, delete_chat_chunks, list_documents, query_chunks

load_dotenv()

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
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []
    chat_id: str | None = None


def get_session_id(x_session_id: str | None = Header(default=None)) -> str:
    # Falls back to a fixed bucket if a client ever calls the API without
    # the header — the real frontend always sends its per-tab session id.
    return x_session_id or "anonymous"


def cleanup_stale_chats(max_age_hours: float = 6) -> None:
    """No login system, so this — not the per-tab session id alone — is what
    actually makes old chats and their indexed documents go away instead of
    accumulating on disk forever."""
    for chat_id in stale_chat_ids(max_age_hours):
        delete_chat_chunks(chat_id)
        delete_chat(chat_id)


def wipe_session(session_id: str) -> None:
    for chat_id in session_chat_ids(session_id):
        delete_chat_chunks(chat_id)
        delete_chat(chat_id)


RATE_LIMIT_MARKERS = ("rate_limit_exceeded", "tokens per minute", "Request too large")


def groq_error_answer(exc: Exception) -> str:
    """A generic "couldn't reach Groq" message hides what's actually wrong
    when it's a rate limit, which needs a different response from the user
    (wait, or ask something shorter) than a real connectivity failure."""
    if any(marker in str(exc) for marker in RATE_LIMIT_MARKERS):
        return (
            "This question needs more context than the current rate limit allows "
            "right now. Try a shorter question, or wait a minute and try again."
        )
    return "Sorry, I couldn't reach Groq to generate an answer."


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
def status():
    return {"groq_connected": bool(os.environ.get("GROQ_API_KEY"))}


@app.get("/api/documents")
def get_documents(chat_id: str):
    return list_documents(chat_id)


@app.get("/api/chats")
def get_chats(session_id: str = Depends(get_session_id)):
    cleanup_stale_chats()
    return list_chats(session_id)


@app.post("/api/chats")
def new_chat(session_id: str = Depends(get_session_id)):
    return create_chat(session_id)


@app.get("/api/chats/{chat_id}")
def get_chat_by_id(chat_id: str, session_id: str = Depends(get_session_id)):
    chat = get_chat(chat_id)
    if chat is None or not owns_chat(chat_id, session_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.delete("/api/session")
def clear_session(session_id: str = Depends(get_session_id)):
    """Called when the visitor leaves the chat (e.g. back to the homepage) —
    wipes their chats and indexed documents immediately, instead of waiting
    for the stale-chat TTL sweep."""
    wipe_session(session_id)
    return {"ok": True}


@app.post("/api/session/clear-beacon")
def clear_session_beacon(session_id: str):
    """Same as DELETE /api/session, but reads session_id from the query
    string instead of a header. navigator.sendBeacon() — the only browser
    API that reliably fires a request while a page is unloading (reload,
    tab close, navigating away) — can't set custom headers, so this is
    what the frontend's pagehide handler calls instead."""
    wipe_session(session_id)
    return {"ok": True}


@app.post("/api/documents")
def upload_documents(chat_id: str = Form(...), files: list[UploadFile] = File(...)):
    indexed = []
    for file in files:
        raw_text = extract_text(file.filename, file.file.read())
        chunks = chunk_text(raw_text, chunk_size=800, overlap=150)
        add_chunks(chunks, source=file.filename, chat_id=chat_id)
        preview = chunks[0][:140] + ("..." if len(chunks[0]) > 140 else "") if chunks else ""
        indexed.append({
            "name": file.filename,
            "chunks": len(chunks),
            "preview": preview,
            "uploaded_at": datetime.now().isoformat(),
        })
    return {"indexed": indexed, "total_chunks": sum(d["chunks"] for d in indexed)}


@app.post("/api/chat")
def chat(req: ChatRequest, session_id: str = Depends(get_session_id)):
    # A chat_id that's missing or belongs to someone else's session gets a
    # fresh chat instead of an error — same effect as opening the sidebar's
    # "New chat" button.
    chat_id = req.chat_id if req.chat_id and owns_chat(req.chat_id, session_id) else None
    chat_id = chat_id or create_chat(session_id)["id"]

    def respond(payload: dict, title: str | None = None) -> dict:
        append_messages(
            chat_id,
            {"role": "user", "content": req.question},
            {"role": "assistant", "content": payload["answer"]},
            title=title,
            session_id=session_id,
        )
        return {**payload, "chat_id": chat_id}

    def title_for(answer: str) -> str | None:
        # A greeting-truncated title ("hi") is a poor label; only worth the
        # extra Groq call once, on a chat's first real, grounded answer.
        if not needs_title(chat_id):
            return None
        try:
            return generate_title(req.question, answer)
        except Exception:
            return None

    total_chunks = chunk_count(chat_id)
    has_docs = total_chunks > 0
    history = req.history
    search_query = build_retrieval_query(req.question, history)
    # The model's 128k-token context window is not the real ceiling here —
    # this Groq account's "on_demand" service tier caps requests at 12000
    # tokens per minute. ~215 tokens/chunk observed, so 40 chunks is ~8600
    # tokens, leaving headroom for system prompt, history, and output while
    # still comfortably under the limit. A large document (e.g. 200+ pages)
    # produces far more chunks than this can ever cover in one question —
    # that's a hard ceiling from the rate tier, not something this number
    # alone fixes; see the "Limitations" note on the Technical Overview page.
    n_ctx = min(total_chunks, 40)

    if is_greeting(req.question):
        answer = (
            "Hello! What can I help you with?"
            if has_docs
            else "Hello! I don't have any documents to work with yet. Upload one to get started."
        )
        return respond({"answer": answer})

    if needs_web_search(req.question):
        results = query_chunks(search_query, chat_id, n_results=n_ctx) if has_docs else []
        context_chunks = [f"[From {meta.get('source', 'document')}]\n{doc}" for doc, meta in results]
        try:
            answer, trace = answer_with_web_search(req.question, context_chunks, [m.model_dump() for m in history])
        except Exception as exc:
            return respond({"answer": groq_error_answer(exc), "error": str(exc)})
        searched_at = trace.pop("searched_at", None)
        return respond({
            "answer": answer,
            "web_search": {
                **trace,
                "searched_at": searched_at.isoformat() if searched_at else None,
            },
        }, title=title_for(answer))

    results = query_chunks(search_query, chat_id, n_results=n_ctx)
    if not results:
        return respond({"answer": "I don't know. No documents have been indexed yet."})

    context_chunks = [f"[From {meta.get('source', 'document')}]\n{doc}" for doc, meta in results]
    try:
        answer = answer_question(req.question, context_chunks, [m.model_dump() for m in history])
    except Exception as exc:
        return respond({"answer": groq_error_answer(exc), "error": str(exc)})

    sources = [
        {
            "source": meta.get("source", "unknown"),
            "chunk_index": meta.get("chunk_index"),
            "text": doc[:300] + ("..." if len(doc) > 300 else ""),
        }
        for doc, meta in results
    ]
    return respond({"answer": answer, "sources": sources}, title=title_for(answer))
