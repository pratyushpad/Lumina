"""Sparse retrievers behind one interface: true BM25 (in-process) and Postgres FTS.

BM25 notes:
- Chunk token lists are cached in memory per document and the BM25Okapi index is
  built over the *session-scoped* subset (filtering happens BEFORE scoring), so
  IDF statistics never leak across sessions. Built indexes are cached per
  document-id set and invalidated on ingest/delete.
- This is correct and fast for Lumina's corpus size (dozens–hundreds of chunks per
  session). It assumes a single backend worker; at larger scale switch to an
  FTS-prefilter → BM25-rerank scheme or a Postgres BM25 extension (see README).
"""
import logging
import re
from typing import Optional

from rank_bm25 import BM25Okapi

logger = logging.getLogger("lumina.sparse")

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Minimal english stopword list — shared by index and query sides.
_STOPWORDS = frozenset(
    "a an and are as at be but by for from has have if in into is it its of on or "
    "that the their there these this to was were will with".split()
)


def tokenize(text: str) -> list[str]:
    """The single shared tokenizer for BM25 index AND query."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


def bm25_rank_corpus(
    query: str, corpus: list[tuple[str, list[str]]], top_k: int
) -> list[tuple[str, float]]:
    """Score a (chunk_id, tokens) corpus against a query. Pure — unit-tested.

    Returns (chunk_id, bm25_score) sorted descending, only positive-scoring entries.
    """
    if not corpus:
        return []
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    bm25 = BM25Okapi([tokens for _, tokens in corpus])
    scores = bm25.get_scores(q_tokens)
    ranked = sorted(
        ((corpus[i][0], float(s)) for i, s in enumerate(scores) if s > 0),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return ranked[:top_k]


class BM25Index:
    """In-memory token cache + per-document-set BM25 ranking."""

    _instance: Optional["BM25Index"] = None

    def __init__(self):
        # document_id -> list[(chunk_id, tokens)]
        self._doc_tokens: dict[str, list[tuple[str, list[str]]]] = {}

    @classmethod
    def get(cls) -> "BM25Index":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def invalidate(self, document_id: str) -> None:
        self._doc_tokens.pop(document_id, None)

    async def _ensure_loaded(self, document_ids: list[str]) -> None:
        missing = [d for d in document_ids if d not in self._doc_tokens]
        if not missing:
            return
        from app.services.vectorstore.pgvector import PgVectorStore

        store = PgVectorStore.get()
        rows = await store.get_chunk_texts(missing)
        loaded: dict[str, list[tuple[str, list[str]]]] = {d: [] for d in missing}
        for chunk_id, doc_id, text in rows:
            loaded[doc_id].append((chunk_id, tokenize(text)))
        self._doc_tokens.update(loaded)
        logger.info("BM25 cache loaded %d documents", len(missing))

    async def rank(
        self, query: str, document_ids: list[str], top_k: int
    ) -> list[tuple[str, float]]:
        if not document_ids:
            return []
        await self._ensure_loaded(document_ids)
        corpus: list[tuple[str, list[str]]] = []
        for d in sorted(document_ids):  # sorted for deterministic corpus order
            corpus.extend(self._doc_tokens.get(d, []))
        return bm25_rank_corpus(query, corpus, top_k)
