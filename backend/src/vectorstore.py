import os
import re
import uuid
from datetime import datetime

from pinecone import NotFoundError, Pinecone

from src import lexical
from src.embeddings import embed_texts
from src.reranker import rerank

INDEX_NAME = os.environ.get("PINECONE_INDEX", "rag-docs")
DIMENSION = 384  # all-MiniLM-L6-v2 output size
HYBRID_K = 20   # results from each of dense and BM25 before fusion
RRF_K = 60      # Reciprocal Rank Fusion constant
# Fused candidates the cross-encoder reorders (up to 2 x HYBRID_K). Off by
# default: on CPU it fixed 1 of 30 eval questions but took p50 retrieval from
# ~300 ms to 2.5-3.4 s. Set RERANK_TOP_K=40 on faster hardware / a GPU.
RERANK_K = int(os.environ.get("RERANK_TOP_K", "0"))

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
    # cached once, same pattern as embeddings._model.
    global _index
    if _index is None:
        _index = _client().index(name=INDEX_NAME)
    return _index


def _split(metadata) -> tuple[str, dict]:
    """Pinecone has no separate document field — the chunk text rides in
    metadata. Split it back out so callers keep getting (doc, meta) pairs."""
    meta = dict(metadata or {})
    for key in ("chunk_index", "page"):
        if key in meta:
            meta[key] = int(meta[key])  # Pinecone returns numbers as floats
    return meta.pop("text", ""), meta


DateRange = tuple[datetime | None, datetime | None]


def doc_type_for(source: str) -> str:
    """pdf / docx / xlsx / csv from the extension; anything else is read as
    plain text by loaders.extract_text, so it's tagged "txt"."""
    ext = os.path.splitext(source)[1].lstrip(".").lower()
    return ext if ext in {"pdf", "docx", "xlsx", "csv"} else "txt"


def build_filter(chat_id: str, doc_type: str | None = None, date_range: DateRange | None = None) -> dict:
    """Pinecone metadata filter; multiple top-level keys are ANDed."""
    flt: dict = {"chat_id": {"$eq": chat_id}}
    if doc_type:
        flt["doc_type"] = {"$eq": doc_type}
    start, end = date_range or (None, None)
    ts_range = {}
    if start:
        ts_range["$gte"] = int(start.timestamp())
    if end:
        ts_range["$lte"] = int(end.timestamp())
    if ts_range:
        flt["uploaded_ts"] = ts_range
    return flt


def _passes(meta: dict, flt: dict) -> bool:
    """Same filter, applied in Python to chunks that didn't come from a
    Pinecone query (the exact-ID fallback). Supports only the operators
    build_filter emits."""
    checks = {"$eq": lambda v, x: v == x, "$gte": lambda v, x: v >= x, "$lte": lambda v, x: v <= x}
    for field, conditions in flt.items():
        value = meta.get(field)
        if value is None or not all(checks[op](value, arg) for op, arg in conditions.items()):
            return False
    return True


def add_chunks(
    chunks: list[str],
    source: str,
    chat_id: str,
    session_id: str,
    extra_metadata: list[dict] | None = None,
) -> None:
    """extra_metadata: optional per-chunk fields, e.g. {"page": 3, "ocr": True}."""
    if not chunks:
        return
    embeddings = embed_texts(chunks)
    batch = uuid.uuid4().hex
    now = datetime.now()
    doc_type = doc_type_for(source)
    vectors = [
        {
            # Plain ASCII ids: filenames can hold characters Pinecone ids reject.
            "id": f"{batch}-{i}",
            "values": embedding,
            "metadata": {
                "text": chunk,
                "source": source,
                "chunk_index": i,
                "doc_type": doc_type,
                "uploaded_at": now.isoformat(),  # for display
                # Pinecone's $gte/$lte only compare numbers, so date-range
                # filtering needs epoch seconds, not the ISO string above.
                "uploaded_ts": int(now.timestamp()),
                "chat_id": chat_id,
                "session_id": session_id,
                **(extra_metadata[i] if extra_metadata else {}),
            },
        }
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    # One namespace per chat: Pinecone can't "get all where chat_id=X" like
    # Chroma could, but it can list/delete a whole namespace.
    get_index().upsert(vectors=vectors, namespace=chat_id, batch_size=100, show_progress=False)
    # Same ids, text and metadata, kept locally for BM25 (hybrid search).
    lexical.save_chunks(chat_id, source, [
        {"id": v["id"], "text": v["metadata"]["text"],
         "metadata": {k: val for k, val in v["metadata"].items() if k != "text"}}
        for v in vectors
    ])


def _rrf(*rankings: list[str]) -> list[str]:
    """Reciprocal Rank Fusion: ids ordered by sum of 1 / (RRF_K + rank) over
    every ranking they appear in."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, id_ in enumerate(ranking, 1):
            scores[id_] = scores.get(id_, 0.0) + 1 / (RRF_K + rank)
    return sorted(scores, key=scores.__getitem__, reverse=True)


def _all_chunks(chat_id: str) -> list[tuple[str, dict]]:
    """pages through every vector in the chat (O(n) reads). Fine
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


def query_chunks(
    question: str,
    chat_id: str,
    n_results: int = 4,
    doc_type: str | None = None,
    date_range: DateRange | None = None,
) -> list[tuple[str, dict]]:
    """Hybrid search: dense (Pinecone) and BM25 (lexical), HYBRID_K each,
    merged with Reciprocal Rank Fusion; exact-ID matches stay on top.
    date_range = (start, end); either end may be None for open-ended."""
    flt = build_filter(chat_id, doc_type, date_range)
    query_embedding = embed_texts([question])[0]
    dense = get_index().query(
        vector=query_embedding,
        top_k=HYBRID_K,
        namespace=chat_id,
        # chat_id is belt and braces (the namespace already isolates the
        # chat); doc_type / uploaded_ts narrow it further when given.
        filter=flt,
        include_metadata=True,
    )
    by_id = {match.id: _split(match.metadata) for match in dense.matches}
    keyword = lexical.search(chat_id, question, HYBRID_K, keep=lambda meta: _passes(meta, flt))
    for hit in keyword:
        by_id.setdefault(hit["id"], (hit["text"], hit["metadata"]))
    fused = [by_id[id_] for id_ in _rrf([m.id for m in dense.matches], [h["id"] for h in keyword])]

    # Exact-ID matches go first: they're the most precise hits, and callers
    # trim this list to a token budget from the front.
    exact = [(doc, meta) for doc, meta in _find_exact_matches(question, chat_id) if _passes(meta, flt)]
    rest = [(doc, meta) for doc, meta in fused if not any(doc == existing for existing, _ in exact)]
    # The cross-encoder reorders the top fused candidates; callers apply the
    # token budget to this order, so the most relevant chunks are the ones sent.
    if RERANK_K > 0:
        rest = rerank(question, rest[:RERANK_K]) + rest[RERANK_K:]
    return exact + rest[:n_results]


def has_chunks(chat_id: str) -> bool:
    # Pinecone reads are eventually consistent — a chunk upserted a
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
