import pytest

from app.database import engine


@pytest.fixture(autouse=True)
async def _dispose_engine_per_test():
    """pytest-asyncio gives each test its own event loop; asyncpg connections are
    loop-bound, so drain the shared engine's pool after every test."""
    yield
    await engine.dispose()
