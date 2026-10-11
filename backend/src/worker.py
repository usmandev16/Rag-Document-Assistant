"""Celery worker: document ingestion off the request path.

Run:  celery -A src.worker worker --loglevel=info --concurrency=2
      (Windows local dev: add --pool=solo)
"""
from datetime import datetime
from pathlib import Path

from celery import Celery
from redis import Redis

from src.chat_store import docs_key
from src.loaders import extract_chunks
from src.sheets import STORAGE_DIR, save_sheets
from src.redis_client import REDIS_URL
from src.vectorstore import add_chunks

# Uploads wait here until ingestion: the API writes them, the worker reads and
# deletes them. On the storage volume both containers share.
UPLOAD_DIR = STORAGE_DIR / "uploads"


def upload_path(file_id: str) -> Path:
    # Name only, so a queued task can never point outside the uploads folder.
    return UPLOAD_DIR / Path(file_id).name


celery_app = Celery("rag_doc_chat", broker=REDIS_URL, backend=REDIS_URL)
# Celery tasks are synchronous, so they use a sync Redis client.
_redis = Redis.from_url(REDIS_URL, decode_responses=True)
celery_app.conf.update(
    task_track_started=True,        # lets the status endpoint report "started"
    task_acks_late=True,            # a crashed worker's task gets redelivered
    worker_prefetch_multiplier=1,   # ingestion is heavy; don't hoard tasks
    result_expires=3600,
)


def _ingest_file(chat_id: str, session_id: str, name: str, data: bytes) -> dict:
    pieces = extract_chunks(name, data)
    # Excel/CSV: also keep the full sheet(s) as parquet for the pandas
    # route (src/router.py); no-op for other file types.
    save_sheets(chat_id, name, data)
    chunks = [text for text, _ in pieces]
    add_chunks(
        chunks, source=name, chat_id=chat_id, session_id=session_id,
        extra_metadata=[meta for _, meta in pieces],
    )
    preview = chunks[0][:140] + ("..." if len(chunks[0]) > 140 else "") if chunks else ""
    return {"name": name, "chunks": len(chunks), "preview": preview, "uploaded_at": datetime.now().isoformat()}


@celery_app.task(name="ingest_documents")
def ingest_documents(chat_id: str, session_id: str, files: list[dict]) -> dict:
    """files: [{"name": original file name, "file": id in UPLOAD_DIR}].
    The uploaded files are deleted afterwards, whether ingestion worked or not."""
    try:
        indexed = [_ingest_file(chat_id, session_id, f["name"], upload_path(f["file"]).read_bytes()) for f in files]
    finally:
        for f in files:
            upload_path(f["file"]).unlink(missing_ok=True)
    total_chunks = sum(d["chunks"] for d in indexed)
    if total_chunks:
        # The chat route reads this flag instead of asking Pinecone each question.
        _redis.set(docs_key(chat_id), "1")
    return {
        "indexed": indexed,
        "total_chunks": total_chunks,
        "session_id": session_id,  # status endpoint only shows results to their owner
    }
