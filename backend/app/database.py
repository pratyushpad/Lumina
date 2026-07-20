"""Async SQLAlchemy engine and session factory.

Connection resilience is load-bearing in production. The hosted database (Neon
free tier) auto-suspends its compute after a few minutes of inactivity, which
kills pooled connections without closing them cleanly. Without `pool_pre_ping`
the first request after a quiet period checks out a dead connection and fails
with a 500; the pool then discards it, so the *next* request succeeds and the
fault looks transient. In practice that means every visitor arriving after an
idle gap gets an error page on first load.

`pool_pre_ping` makes SQLAlchemy validate (and transparently replace) a
connection at checkout, and `pool_recycle` keeps pooled connections younger
than the idle-suspend window so they are rotated before they can go stale.
"""
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.config import settings

# Below Neon's ~5 min idle-suspend window, so connections rotate before the
# compute can be suspended out from under them.
POOL_RECYCLE_SECONDS = 180


def connect_args_for(url: str) -> dict:
    """asyncpg connect args, adjusted for connection-pooler endpoints.

    Neon's pooled host (`…-pooler.…`) fronts Postgres with PgBouncer in
    transaction mode, where server-side prepared statements are not stable
    across checkouts — asyncpg then fails with "prepared statement
    __asyncpg_stmt_N__ already exists". Disable both the driver-level and
    dialect-level statement caches on that endpoint only; the direct endpoint
    keeps them for the speedup.
    """
    host = urlsplit(url).hostname or ""
    if "-pooler." in host:
        return {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
    return {}


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=POOL_RECYCLE_SECONDS,
    connect_args=connect_args_for(settings.DATABASE_URL),
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Schema is managed by Alembic (see app/migrations.py + backend/alembic/).
