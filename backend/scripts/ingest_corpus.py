"""CLI wrapper: deterministic eval-corpus ingestion (`make ingest`).

The ingest itself lives in app/services/ingestion/corpus.py so the app can reuse
it for demo seeding without importing from scripts/.
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ingestion.corpus import ingest  # noqa: E402

CORPUS_DIR_DEFAULT = Path(__file__).resolve().parents[2] / "eval" / "corpus"
SESSION_ID_DEFAULT = "eval-corpus"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Deterministic eval-corpus ingestion")
    ap.add_argument("--corpus", type=Path, default=CORPUS_DIR_DEFAULT)
    ap.add_argument("--session-id", default=SESSION_ID_DEFAULT)
    ap.add_argument("--strategy", default=None, help="fixed | recursive | semantic")
    args = ap.parse_args()
    asyncio.run(ingest(args.corpus, args.session_id, args.strategy))


if __name__ == "__main__":
    main()
