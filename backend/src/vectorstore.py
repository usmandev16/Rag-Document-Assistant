import os
import re
import uuid
from datetime import datetime

from pinecone import NotFoundError, Pinecone

from src.embeddings import embed_texts

INDEX_NAME = os.environ.get("PINECONE_INDEX", "rag-doc-chat")
DIMENSION = 384  # all-MiniLM-L6-v2 output size

_index = None
_ID_TOKEN_RE = re.compile(r"\b\d{5,}\b")


def _client() -> Pinecone:
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY is not set. Add it to your .env file.")
    return Pinecone(api_key=api_key)


def ensure_index() -> None:
    """One-time setup: `python -m src.vectorstore`. Safe to re-run."""
    pc = _client()
    if pc.indexes.exists(INDEX_NAME):
        print(f"Index {INDEX_NAME!r} already exists.")
        return
    pc.indexes.create(
        name=INDEX_NAME,
        # "_values" is the reserved field the classic upsert(values=...) API
        # writes to, so records stay plain {id, values, metadata}.
        schema={"fields": {"_values": {"type": "dense_vector", "dimension": DIMENSION, "metric": "cosine"}}},
        deployment={
            "deployment_type": "managed",
            "cloud": os.environ.get("PINECONE_CLOUD", "aws"),
            "region": os.environ.get("PINECONE_REGION", "us-east-1"),
        },
    )
    print(f"Created index {INDEX_NAME!r}.")


def get_index():
    # ponytail: cached once, same pattern as embeddings._model.
    global _index
    if _index is None:
        _index = _client().index(name=INDEX_NAME)
    return _index


def _split(metadata) -> tuple[str, dict]:
    """Pinecone has no separate document field — the chunk text rides in
    metadata. Split it back out so callers keep getting (doc, meta) pairs."""
    meta = dict(metadata or {})
    if "chunk_index" in meta:
        meta["chunk_index"] = int(meta["chunk_index"])  # Pinecone returns numbers as floats
    return meta.pop("text", ""), meta


def add_chunks(chunks: list[str], source: str, chat_id: str, session_id: str) -> None:
    if not chunks:
        return
    embeddings = embed_texts(chunks)
    batch = uuid.uuid4().hex
    uploaded_at = datetime.now().isoformat()
    vectors = [
        {
            # Plain ASCII ids: filenames can hold characters Pinecone ids reject.
            "id": f"{batch}-{i}",
            "values": embedding,
            "metadata": {
                "text": chunk,
                "source": source,
                "chunk_index": i,
                "uploaded_at": uploaded_at,
                "chat_id": chat_id,
                "session_id": session_id,
            },
        }
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    # One namespace per chat: Pinecone can't "get all where chat_id=X" like
    # Chroma could, but it can list/delete a whole namespace.
    get_index().upsert(vectors=vectors, namespace=chat_id, batch_size=100, show_progress=False)


def _all_chunks(chat_id: str) -> list[tuple[str, dict]]:
    """ponytail: pages through every vector in the chat (O(n) reads). Fine
    for per-chat uploads; switch to a hybrid (sparse) index if chats get big."""
    index = get_index()
    pairs = []
    for page in index.list(namespace=chat_id):
        fetched = index.fetch(ids=[item.id for item in page.vectors], namespace=chat_id)
        pairs += [_split(vec.metadata) for vec in fetched.vectors.values()]
    return pairs


def _find_exact_matches(question: str, chat_id: str) -> list[tuple[str, dict]]:
    """Vector similarity alone is unreliable for pulling out the one chunk
    holding a specific ID/reference number among many near-identical rows —
    embeddings don't discriminate well between numbers. If the question
    names a long number (e.g. a CN/tracking number), force-include any chunk
    that contains it verbatim.
    """
    tokens = _ID_TOKEN_RE.findall(question)
    if not tokens:
        return []
    return [(doc, meta) for doc, meta in _all_chunks(chat_id) if any(token in doc for token in tokens)]


def query_chunks(question: str, chat_id: str, n_results: int = 4) -> list[tuple[str, dict]]:
    query_embedding = embed_texts([question])[0]
    results = get_index().query(
        vector=query_embedding,
        top_k=n_results,
        namespace=chat_id,
        # Belt and braces: the namespace already isolates the chat.
        filter={"chat_id": {"$eq": chat_id}},
        include_metadata=True,
    )
    pairs = [_split(match.metadata) for match in results.matches]

    for doc, meta in _find_exact_matches(question, chat_id):
        if not any(doc == existing for existing, _ in pairs):
            pairs.append((doc, meta))

    return pairs


def has_chunks(chat_id: str) -> bool:
    # ponytail: Pinecone reads are eventually consistent — a chunk upserted a
    # second ago may not be listed yet.
    return next(iter(get_index().list(namespace=chat_id, limit=1)), None) is not None


def delete_chat_chunks(chat_id: str) -> None:
    try:
        get_index().delete(delete_all=True, namespace=chat_id)
    except NotFoundError:
        pass  # chat never had documents, so its namespace doesn't exist


def list_documents(chat_id: str) -> list[dict]:
    """Derive the indexed-document list straight from Pinecone metadata, so it
    stays correct across server restarts instead of living in app memory."""
    counts: dict[str, int] = {}
    previews: dict[str, str] = {}
    uploaded_at: dict[str, str] = {}
    for doc, meta in _all_chunks(chat_id):
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


if __name__ == "__main__":
    ensure_index()
