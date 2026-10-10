"""Cross-encoder reranking of the fused hybrid-search candidates.

A cross-encoder reads the question and each chunk together, so it scores
relevance more precisely than the separate embeddings / keyword overlap that
produced the candidate list. The token budget is applied to its order.
"""
import logging
import time

from sentence_transformers import CrossEncoder

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None

# Own handler so the per-query rerank time shows under uvicorn and celery.
log = logging.getLogger("rag.rerank")
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False


def get_model() -> CrossEncoder:
    # Loaded once per process (same pattern as embeddings._model).
    global _model
    if _model is None:
        _model = CrossEncoder(MODEL_NAME, device="cpu")
    return _model


def rerank(question: str, pairs: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """Reorder (doc, meta) pairs by cross-encoder score, best first."""
    if len(pairs) < 2:
        return pairs
    start = time.perf_counter()
    scores = get_model().predict([(question, doc) for doc, _ in pairs], show_progress_bar=False)
    ranked = [pair for _, pair in sorted(zip(scores, pairs), key=lambda sp: sp[0], reverse=True)]
    log.info("reranked %d chunks in %.0f ms", len(pairs), (time.perf_counter() - start) * 1000)
    return ranked
