"""Celery worker: document ingestion off the request path.

Run:  celery -A src.worker worker --loglevel=info --concurrency=2
      (Windows local dev: add --pool=solo)
"""
import base64
from datetime import datetime

from celery import Celery

from src.chunking import chunk_text
from src.loaders import extract_text
from src.redis_client import REDIS_URL
from src.vectorstore import add_chunks

celery_app = Celery("rag_doc_chat", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_track_started=True,        # lets the status endpoint report "started"
    task_acks_late=True,            # a crashed worker's task gets redelivered
    worker_prefetch_multiplier=1,   # ingestion is heavy; don't hoard tasks
    result_expires=3600,
)


@celery_app.task(name="ingest_documents")
def ingest_documents(chat_id: str, session_id: str, files: list[dict]) -> dict:
    """files: [{"name": str, "data": base64 str}].

    ponytail: file bytes travel base64 through Redis, so the API and worker
    need no shared disk. Ceiling is large files (Redis memory); upgrade path
    is upload to S3 and pass the object key instead.
    """
    indexed = []
    for file in files:
        raw_text = extract_text(file["name"], base64.b64decode(file["data"]))
        chunks = chunk_text(raw_text, chunk_size=800, overlap=150)
        add_chunks(chunks, source=file["name"], chat_id=chat_id, session_id=session_id)
        preview = chunks[0][:140] + ("..." if len(chunks[0]) > 140 else "") if chunks else ""
        indexed.append({
            "name": file["name"],
            "chunks": len(chunks),
            "preview": preview,
            "uploaded_at": datetime.now().isoformat(),
        })
    return {
        "indexed": indexed,
        "total_chunks": sum(d["chunks"] for d in indexed),
        "session_id": session_id,  # status endpoint only shows results to their owner
    }
