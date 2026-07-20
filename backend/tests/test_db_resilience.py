"""Connection-pool resilience against an auto-suspending managed Postgres.

Neon's free tier suspends compute after a few minutes idle, which kills pooled
connections without closing them cleanly. The first request after a quiet
period then checks out a dead connection and 500s — observed in production
before `pool_pre_ping` was enabled.
"""
import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.database import POOL_RECYCLE_SECONDS, connect_args_for, engine


def _db_reachable() -> bool:
    async def probe():
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


def test_pooler_endpoint_disables_statement_caches():
    """PgBouncer transaction mode breaks asyncpg's prepared-statement cache."""
    pooled = "postgresql+asyncpg://u:p@ep-x-123-pooler.us-east-2.aws.neon.tech/db"
    assert connect_args_for(pooled) == {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }


def test_direct_endpoint_keeps_statement_caches():
    direct = "postgresql+asyncpg://u:p@ep-x-123.us-east-2.aws.neon.tech/db"
    local = "postgresql+asyncpg://lumina:lumina@localhost:5433/lumina"
    assert connect_args_for(direct) == {}
    assert connect_args_for(local) == {}


def test_app_engine_has_stale_connection_protection():
    assert engine.pool._pre_ping is True
    # Must stay under the managed provider's idle-suspend window (~5 min).
    assert 0 < POOL_RECYCLE_SECONDS < 300
    assert engine.pool._recycle == POOL_RECYCLE_SECONDS


@pytest.mark.asyncio
@pytest.mark.skipif(not _db_reachable(), reason="Postgres not reachable")
async def test_dead_pooled_connection_is_replaced_not_raised():
    """Reproduces the production failure: a pooled connection killed underneath
    us (as auto-suspend does) must be transparently replaced, not surfaced."""
    resilient = create_async_engine(
        settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=POOL_RECYCLE_SECONDS
    )
    try:
        async with resilient.connect() as conn:
            await conn.execute(text("SELECT 1"))
        # Kill the socket and return the corpse to the pool.
        async with resilient.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.close()
        async with resilient.connect() as conn:
            assert (await conn.execute(text("SELECT 42"))).scalar() == 42
    finally:
        await resilient.dispose()
