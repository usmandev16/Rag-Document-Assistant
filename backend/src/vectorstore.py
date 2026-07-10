import re
import uuid
from datetime import datetime

import chromadb

from src.embeddings import embed_texts

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "documents"

_collection = None
_ID_TOKEN_RE = re.compile(r"\b\d{5,}\b")


def get_collection():
    # ponytail: PersistentClient() re-opens the on-disk store on every call —
    # cache it once (same pattern as embeddings._model) instead of paying
    # that cost per request.
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = client.get_or_create_collection(COLLECTION_NAME)
    return _collection


def add_chunks(chunks: list[str], source: str, chat_id: str) -> None:
    if not chunks:
        return
    collection = get_collection()
    embeddings = embed_texts(chunks)
    ids = [f"{source}-{uuid.uuid4().hex[:8]}-{i}" for i in range(len(chunks))]
    uploaded_at = datetime.now().isoformat()
    metadatas = [
        {"source": source, "chunk_index": i, "uploaded_at": uploaded_at, "chat_id": chat_id}
        for i in range(len(chunks))
    ]
    collection.add(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)


def _find_exact_matches(question: str, chat_id: str, collection) -> list[tuple[str, dict]]:
    """Vector similarity alone is unreliable for pulling out the one chunk
    holding a specific ID/reference number among many near-identical rows —
    embeddings don't discriminate well between numbers. If the question
    names a long number (e.g. a CN/tracking number), force-include any chunk
    that contains it verbatim.

    ponytail: scans every chunk for the chat on each such query (O(n)); fine
    at the row counts a single-chat spreadsheet upload produces, upgrade to
    a metadata token index if that stops being true.
    """
    tokens = _ID_TOKEN_RE.findall(question)
    if not tokens:
        return []
    result = collection.get(where={"chat_id": chat_id}, include=["documents", "metadatas"])
    return [
        (doc, meta)
        for doc, meta in zip(result["documents"], result["metadatas"])
        if any(token in doc for token in tokens)
    ]


def query_chunks(question: str, chat_id: str, n_results: int = 4) -> list[tuple[str, dict]]:
    collection = get_collection()
    count = chunk_count(chat_id)
    if count == 0:
        return []
    query_embedding = embed_texts([question])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, count),
        where={"chat_id": chat_id},
    )
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    pairs = list(zip(documents, metadatas))

    for doc, meta in _find_exact_matches(question, chat_id, collection):
        if not any(doc == existing for existing, _ in pairs):
            pairs.append((doc, meta))

    return pairs


def chunk_count(chat_id: str) -> int:
    return len(get_collection().get(where={"chat_id": chat_id}, include=[])["ids"])


def delete_chat_chunks(chat_id: str) -> None:
    get_collection().delete(where={"chat_id": chat_id})


def list_documents(chat_id: str) -> list[dict]:
    """Derive the indexed-document list straight from Chroma metadata, so it
    stays correct across server restarts instead of living in app memory."""
    collection = get_collection()
    result = collection.get(where={"chat_id": chat_id}, include=["metadatas", "documents"])
    if not result["ids"]:
        return []
    counts: dict[str, int] = {}
    previews: dict[str, str] = {}
    uploaded_at: dict[str, str] = {}
    for meta, doc in zip(result["metadatas"], result["documents"]):
        source = meta.get("source", "unknown")
        counts[source] = counts.get(source, 0) + 1
        if meta.get("chunk_index") == 0:
            previews[source] = doc[:140] + ("..." if len(doc) > 140 else "")
            uploaded_at[source] = meta.get("uploaded_at", "")
    return [
        {
            "name": name,
            "chunks": count,
            "preview": previews.get(name, ""),
            "uploaded_at": uploaded_at.get(name, ""),
        }
        for name, count in counts.items()
    ]
