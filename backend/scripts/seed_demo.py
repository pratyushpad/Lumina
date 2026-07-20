"""CLI wrapper: `python scripts/seed_demo.py [--force]`.

The seeding itself lives in app/services/bootstrap.py so the app can call it at
startup without importing from scripts/.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.bootstrap import seed_demo  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(seed_demo(force="--force" in sys.argv))
