"""Run Alembic migrations programmatically (used at startup and by scripts)."""
import asyncio
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _upgrade_head_sync() -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")


async def run_migrations() -> None:
    # Alembic's env.py drives its own asyncio.run(), so keep it off our event loop.
    await asyncio.to_thread(_upgrade_head_sync)
