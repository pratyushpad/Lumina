"""Postgres + pgvector store: dense ANN, FTS ranking, and in-SQL hybrid RRF."""
import logging
from typing import Optional

from sqlalchemy import bindparam, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.chunk import Chunk
from app.services.ingestion.chunker import ChunkData
from app.services.retrieval.types import RetrievalResult

logger = logging.getLogger("lumina.vectorstore")

# Dense + FTS + RRF fused in a single statement (used when sparse_method="fts").
# Both CTEs are scoped to the session's documents; RRF needs only ranks, so
# ts_rank_cd (not true BM25) is acceptable here — the true-BM25 path lives in
# services/retrieval/sparse.py.
_HYBRID_FTS_SQL = text(
    """
    WITH dense AS (
        SELECT chunk_id,
               ROW_NUMBER() OVER (ORDER BY embedding <=> CAST(:qvec AS vector)) AS r
        FROM chunks
        WHERE document_id IN :doc_ids
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :k
    ),
    sparse AS (
        SELECT chunk_id,
               ROW_NUMBER() OVER (
                   ORDER BY ts_rank_cd(tsv, plainto_tsquery('english', :q)) DESC
               ) AS r
        FROM chunks
        WHERE document_id IN :doc_ids
          AND tsv @@ plainto_tsquery('english', :q)
        LIMIT :k
    )
    SELECT COALESCE(d.chunk_id, s.chunk_id) AS chunk_id,
           COALESCE(1.0 / (:rrf_k + d.r), 0) + COALESCE(1.0 / (:rrf_k + s.r), 0) AS rrf_score
    FROM dense d
    FULL OUTER JOIN sparse s ON d.chunk_id = s.chunk_id
    ORDER BY rrf_score DESC
    LIMIT :k
    """
).bindparams(bindparam("doc_ids", expanding=True))

_FTS_SQL = text(
    """
    SELECT chunk_id,
           ts_rank_cd(tsv, plainto_tsquery('english', :q)) AS score
    FROM chunks
    WHERE document_id IN :doc_ids
      AND tsv @@ plainto_tsquery('english', :q)
    ORDER BY score DESC
    LIMIT :k
    """
).bindparams(bindparam("doc_ids", expanding=True))


def _to_result(c: Chunk, distance: float = 0.0) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=c.chunk_id,
        document_id=c.document_id,
        text=c.text,
        page_num=c.page_num or 0,
        filename=c.filename or "",
        distance=distance,
        has_associated_image=bool(c.has_associated_image),
        image_path=c.image_path,
        block_type=c.block_type or "text",
    )


def _vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


class PgVectorStore:
    _instance: Optional["PgVectorStore"] = None

    @classmethod
    def get(cls) -> "PgVectorStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def add_chunks(self, chunks: list[ChunkData], embeddings: list[list[float]]) -> int:
        if not chunks:
            return 0
        assert len(chunks) == len(embeddings), "chunks/embeddings length mismatch"
        rows = [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "chunk_index": c.chunk_index,
                "page_num": c.page_num,
                "block_type": c.block_type,
                "filename": c.filename,
                "has_associated_image": bool(c.has_associated_image),
                "image_path": c.image_path,
                "chunking_strategy": c.chunking_strategy,
                "text": c.text,
                "embedding": emb,
            }
            for c, emb in zip(chunks, embeddings)
        ]
        async with AsyncSessionLocal() as db:
            batch = 200
            for i in range(0, len(rows), batch):
                stmt = pg_insert(Chunk).values(rows[i : i + batch])
                stmt = stmt.on_conflict_do_update(
                    index_elements=[Chunk.chunk_id],
                    set_={
                        col: getattr(stmt.excluded, col)
                        for col in (
                            "document_id", "chunk_index", "page_num", "block_type",
                            "filename", "has_associated_image", "image_path",
                            "chunking_strategy", "text", "embedding",
                        )
                    },
                )
                await db.execute(stmt)
            await db.commit()
        return len(rows)

    async def dense_query(
        self, query_embedding: list[float], document_ids: list[str], top_k: int
    ) -> list[RetrievalResult]:
        if not document_ids:
            return []
        dist = Chunk.embedding.cosine_distance(query_embedding)
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(Chunk, dist.label("distance"))
                .where(Chunk.document_id.in_(document_ids))
                .order_by(dist)
                .limit(top_k)
            )
            return [_to_result(c, float(d)) for c, d in res.all()]

    async def fts_query(
        self, query_text: str, document_ids: list[str], top_k: int
    ) -> list[tuple[str, float]]:
        """Ranked (chunk_id, score) via Postgres full-text ts_rank_cd."""
        if not document_ids or not query_text.strip():
            return []
        async with AsyncSessionLocal() as db:
            res = await db.execute(_FTS_SQL, {"q": query_text, "doc_ids": document_ids, "k": top_k})
            return [(row.chunk_id, float(row.score)) for row in res.all()]

    async def hybrid_fts_query(
        self,
        query_embedding: list[float],
        query_text: str,
        document_ids: list[str],
        top_k: int,
        rrf_k: int = 60,
    ) -> list[RetrievalResult]:
        """Dense + FTS fused with RRF in one SQL statement."""
        if not document_ids:
            return []
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                _HYBRID_FTS_SQL,
                {
                    "qvec": _vec_literal(query_embedding),
                    "q": query_text,
                    "doc_ids": document_ids,
                    "k": top_k,
                    "rrf_k": rrf_k,
                },
            )
            scored = [(row.chunk_id, float(row.rrf_score)) for row in res.all()]
        by_id = await self.fetch_chunks([cid for cid, _ in scored])
        out = []
        for cid, score in scored:
            r = by_id.get(cid)
            if r:
                r.relevance_score = score
                out.append(r)
        return out

    async def fetch_chunks(self, chunk_ids: list[str]) -> dict[str, RetrievalResult]:
        if not chunk_ids:
            return {}
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Chunk).where(Chunk.chunk_id.in_(chunk_ids)))
            return {c.chunk_id: _to_result(c) for c in res.scalars().all()}

    async def get_chunk_texts(self, document_ids: list[str]) -> list[tuple[str, str, str]]:
        """(chunk_id, document_id, text) for the given documents — feeds the BM25 index."""
        if not document_ids:
            return []
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(Chunk.chunk_id, Chunk.document_id, Chunk.text)
                .where(Chunk.document_id.in_(document_ids))
                .order_by(Chunk.document_id, Chunk.chunk_index)
            )
            return [(row.chunk_id, row.document_id, row.text) for row in res.all()]

    async def delete_by_document_id(self, document_id: str) -> int:
        async with AsyncSessionLocal() as db:
            res = await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
            await db.commit()
            return res.rowcount or 0

    async def get_stats(self) -> dict:
        async with AsyncSessionLocal() as db:
            count = (await db.execute(select(func.count(Chunk.chunk_id)))).scalar() or 0
        return {"total_chunks": int(count), "store": "pgvector"}
