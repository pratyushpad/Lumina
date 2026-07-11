"""Config-driven retrieval pipeline: transform → (dense | sparse | hybrid RRF) → rerank.

Every stage is selectable via RetrievalConfig so the eval harness can run ablations
(dense-only → +hybrid → +rerank → +query-rewrite) against the exact production code path.
"""
import logging
from typing import Literal, Optional

from pydantic import BaseModel

from app.config import settings
from app.services.embedding.embedder import EmbeddingService
from app.services.retrieval import query_transform
from app.services.retrieval.fusion import rrf_fuse
from app.services.retrieval.reranker import Reranker
from app.services.retrieval.sparse import BM25Index
from app.services.retrieval.types import RetrievalResult
from app.services.vectorstore.pgvector import PgVectorStore

logger = logging.getLogger("lumina.pipeline")


class RetrievalConfig(BaseModel):
    query_transform: Literal["none", "multi_query", "hyde"] = "none"
    mode: Literal["dense", "sparse", "hybrid_rrf"] = "hybrid_rrf"
    sparse_method: Literal["bm25", "fts"] = "bm25"
    rrf_k: int = 60
    top_k_candidates: int = 50
    rerank: bool = True
    top_k_final: int = 5

    @classmethod
    def from_settings(cls) -> "RetrievalConfig":
        return cls(
            query_transform=settings.QUERY_TRANSFORM,
            mode=settings.RETRIEVAL_MODE,
            sparse_method=settings.SPARSE_METHOD,
            rrf_k=settings.RRF_K,
            top_k_candidates=settings.TOP_K_CANDIDATES,
            top_k_final=settings.TOP_K_RERANKED,
        )


class RetrievalPipeline:
    def __init__(self, config: Optional[RetrievalConfig] = None):
        self.config = config or RetrievalConfig.from_settings()
        self.store = PgVectorStore.get()
        self.embedder = EmbeddingService.get()

    async def run(self, query: str, document_ids: list[str]) -> list[RetrievalResult]:
        cfg = self.config
        if not document_ids:
            return []

        queries = [query]
        if cfg.query_transform == "multi_query":
            queries = await query_transform.multi_query(query)

        # Fast path: single query, hybrid over FTS → one fused SQL statement.
        if (
            len(queries) == 1
            and cfg.mode == "hybrid_rrf"
            and cfg.sparse_method == "fts"
            and cfg.query_transform != "hyde"
        ):
            q_vec = self.embedder.embed_query(query)
            candidates = await self.store.hybrid_fts_query(
                q_vec, query, document_ids, cfg.top_k_candidates, cfg.rrf_k
            )
        else:
            ranked_lists: list[list[str]] = []
            for q in queries:
                ranked_lists.extend(await self._ranked_lists_for(q, document_ids))
            fused = rrf_fuse(ranked_lists, k=cfg.rrf_k)[: cfg.top_k_candidates]
            by_id = await self.store.fetch_chunks([cid for cid, _ in fused])
            candidates = []
            for cid, score in fused:
                r = by_id.get(cid)
                if r:
                    r.relevance_score = score
                    candidates.append(r)

        if cfg.rerank:
            # Rerank always uses the ORIGINAL query — transforms only widen recall.
            return Reranker.get().rerank(query, candidates, top_k=cfg.top_k_final)
        return candidates[: cfg.top_k_final]

    async def _ranked_lists_for(self, q: str, document_ids: list[str]) -> list[list[str]]:
        """Ranked chunk-id lists for one query under the configured mode."""
        cfg = self.config
        lists: list[list[str]] = []

        if cfg.mode in ("dense", "hybrid_rrf"):
            embed_text = q
            if cfg.query_transform == "hyde":
                embed_text = await query_transform.hyde(q)
            q_vec = self.embedder.embed_query(embed_text)
            dense = await self.store.dense_query(q_vec, document_ids, cfg.top_k_candidates)
            lists.append([r.chunk_id for r in dense])

        if cfg.mode in ("sparse", "hybrid_rrf"):
            # Sparse always matches on the raw query (HyDE applies to embeddings only).
            if cfg.sparse_method == "bm25":
                ranked = await BM25Index.get().rank(q, document_ids, cfg.top_k_candidates)
            else:
                ranked = await self.store.fts_query(q, document_ids, cfg.top_k_candidates)
            lists.append([cid for cid, _ in ranked])

        return lists
