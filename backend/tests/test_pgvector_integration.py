"""Integration tests against a real Postgres (skipped when the DB is unreachable).

Covers: chunk upsert, dense ANN query, FTS ranking, single-SQL hybrid RRF,
document-id scoping in every path, and the BM25 index cache.
"""
import asyncio
import uuid

import pytest

from app.database import AsyncSessionLocal
from app.models import Document, Session
from app.services.ingestion.chunker import ChunkData
from app.services.retrieval.sparse import BM25Index
from app.services.vectorstore.pgvector import PgVectorStore


def _db_reachable() -> bool:
    async def probe():
        # Isolated engine: never touch the app engine's pool from this throwaway loop
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.config import settings

        probe_engine = create_async_engine(settings.DATABASE_URL)
        try:
            async with probe_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await probe_engine.dispose()

    try:
        asyncio.run(probe())
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not _db_reachable(), reason="Postgres not reachable"),
]


def _chunk(chunk_id: str, document_id: str, text: str, idx: int = 0) -> ChunkData:
    return ChunkData(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        page_num=1,
        chunk_index=idx,
        block_type="text",
        char_count=len(text),
        token_estimate=len(text) // 4,
        filename="test.txt",
    )


def _vec(seed: float) -> list[float]:
    """A distinct normalized-ish 384-dim vector."""
    v = [0.001] * 384
    v[int(seed) % 384] = 1.0
    return v


@pytest.fixture
async def seeded_docs():
    """Two documents with chunks; cleaned up after the test."""
    store = PgVectorStore.get()
    sid = f"test-sess-{uuid.uuid4().hex[:8]}"
    doc_a, doc_b = f"test-doc-a-{uuid.uuid4().hex[:8]}", f"test-doc-b-{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as db:
        db.add(Session(id=sid, name="itest"))
        await db.flush()
        db.add_all(
            [
                Document(id=doc_a, session_id=sid, filename="a.txt",
                         stored_path="/tmp/a.txt", file_type="text", status="ready"),
                Document(id=doc_b, session_id=sid, filename="b.txt",
                         stored_path="/tmp/b.txt", file_type="text", status="ready"),
            ]
        )
        await db.commit()

    chunks_a = [
        _chunk(f"{doc_a}_chunk_0", doc_a, "The pgvector extension provides vector similarity search.", 0),
        _chunk(f"{doc_a}_chunk_1", doc_a, "Reciprocal rank fusion combines multiple ranked lists.", 1),
    ]
    chunks_b = [
        _chunk(f"{doc_b}_chunk_0", doc_b, "Cats are excellent hunters and sleep during the day.", 0),
    ]
    await store.add_chunks(chunks_a, [_vec(1), _vec(2)])
    await store.add_chunks(chunks_b, [_vec(3)])

    yield store, sid, doc_a, doc_b

    async with AsyncSessionLocal() as db:
        sess = await db.get(Session, sid)
        if sess:
            await db.delete(sess)
            await db.commit()
    BM25Index.get().invalidate(doc_a)
    BM25Index.get().invalidate(doc_b)


async def test_upsert_and_stats(seeded_docs):
    store, _, doc_a, _ = seeded_docs
    stats = await store.get_stats()
    assert stats["total_chunks"] >= 3
    # Upsert same id with new text must not duplicate
    await store.add_chunks(
        [_chunk(f"{doc_a}_chunk_0", doc_a, "Updated text about pgvector similarity.", 0)],
        [_vec(1)],
    )
    by_id = await store.fetch_chunks([f"{doc_a}_chunk_0"])
    assert "Updated text" in by_id[f"{doc_a}_chunk_0"].text


async def test_dense_query_scoped_to_documents(seeded_docs):
    store, _, doc_a, doc_b = seeded_docs
    res = await store.dense_query(_vec(1), [doc_a], top_k=10)
    assert res and all(r.document_id == doc_a for r in res)
    assert res[0].chunk_id == f"{doc_a}_chunk_0"  # closest vector
    # doc_b chunk never leaks in
    assert all(r.document_id != doc_b for r in res)


async def test_fts_query_ranks_and_scopes(seeded_docs):
    store, _, doc_a, doc_b = seeded_docs
    ranked = await store.fts_query("rank fusion ranked lists", [doc_a, doc_b], top_k=10)
    assert ranked and ranked[0][0] == f"{doc_a}_chunk_1"
    # Scoped away from doc_a: fusion chunk must vanish
    ranked_b = await store.fts_query("rank fusion ranked lists", [doc_b], top_k=10)
    assert all(cid.startswith(doc_b) for cid, _ in ranked_b)


async def test_hybrid_fts_single_sql(seeded_docs):
    store, _, doc_a, doc_b = seeded_docs
    res = await store.hybrid_fts_query(
        _vec(2), "reciprocal rank fusion", [doc_a, doc_b], top_k=10, rrf_k=60
    )
    assert res
    # chunk_1 is rank-1 in BOTH dense (vec 2) and FTS → must be first
    assert res[0].chunk_id == f"{doc_a}_chunk_1"
    assert res[0].relevance_score > 0
    assert all(r.document_id in (doc_a, doc_b) for r in res)


async def test_bm25_index_scoping_and_invalidation(seeded_docs):
    store, _, doc_a, doc_b = seeded_docs
    idx = BM25Index.get()
    idx.invalidate(doc_a)
    idx.invalidate(doc_b)
    ranked = await idx.rank("reciprocal rank fusion", [doc_a, doc_b], top_k=10)
    assert ranked and ranked[0][0] == f"{doc_a}_chunk_1"
    # Scoping: only doc_b → no fusion chunk
    ranked_b = await idx.rank("reciprocal rank fusion", [doc_b], top_k=10)
    assert all(cid.startswith(doc_b) for cid, _ in ranked_b)


async def test_delete_by_document(seeded_docs):
    store, _, doc_a, _ = seeded_docs
    deleted = await store.delete_by_document_id(doc_a)
    assert deleted == 2
    assert await store.fetch_chunks([f"{doc_a}_chunk_0"]) == {}
