"""BM25 keyword search over a chat's chunks: the lexical half of hybrid search.

At ingestion every chunk's id, text and metadata (the same as in Pinecone) is
saved as JSONL in the chat's storage folder, one file per document, next to
the spreadsheet parquet files. Deleting the chat folder removes them too.
"""
import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.sheets import _chat_dir

CHUNKS_DIR = "chunks"
_TOKEN_RE = re.compile(r"\w+")

# chat_id -> (file signature, records, BM25 index). The signature (file names
# + mtimes) changes when a document is added or replaced, which rebuilds it.
# rebuilt in memory per process; fine for per-chat uploads of a few
# thousand chunks, switch to a persistent index if chats get much bigger.
_cache: dict[str, tuple[tuple, list[dict], BM25Okapi | None]] = {}


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _source_file(chat_id: str, source: str) -> Path:
    # Hashed name: any upload filename maps to a safe, stable file.
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]
    return _chat_dir(chat_id) / CHUNKS_DIR / f"{digest}.jsonl"


def save_chunks(chat_id: str, source: str, records: list[dict]) -> None:
    """records: [{"id", "text", "metadata"}]. Replaces that document's chunks."""
    path = _source_file(chat_id, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    tmp.replace(path)  # atomic: a query never reads a half-written file


def delete_source(chat_id: str, source: str) -> None:
    _source_file(chat_id, source).unlink(missing_ok=True)


def _index(chat_id: str) -> tuple[list[dict], BM25Okapi | None]:
    folder = _chat_dir(chat_id) / CHUNKS_DIR
    files = sorted(folder.glob("*.jsonl")) if folder.is_dir() else []
    signature = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    cached = _cache.get(chat_id)
    if cached and cached[0] == signature:
        return cached[1], cached[2]
    records = [json.loads(line) for f in files for line in f.read_text(encoding="utf-8").splitlines() if line]
    bm25 = BM25Okapi([tokenize(r["text"]) for r in records]) if records else None
    _cache[chat_id] = (signature, records, bm25)
    return records, bm25


def search(chat_id: str, query: str, k: int, keep: Callable[[dict], bool] = lambda meta: True) -> list[dict]:
    """Top-k records by BM25 score (only those with a positive score and
    whose metadata passes `keep`), best first."""
    records, bm25 = _index(chat_id)
    terms = tokenize(query)
    if bm25 is None or not terms:
        return []
    scores = bm25.get_scores(terms)
    hits = []
    for i in sorted(range(len(records)), key=lambda i: scores[i], reverse=True):
        if scores[i] <= 0 or len(hits) == k:
            break
        if keep(records[i]["metadata"]):
            hits.append(records[i])
    return hits
