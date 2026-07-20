"""Startup seeding of the public demo session.

Runs the deterministic ingest against demo_docs/ (baked into the Docker image,
so the source PDFs survive ephemeral-storage restarts on HF Spaces). Chunks and
embeddings live in Postgres; if every demo document is already `ready` there
with chunks, seeding is a cheap no-op — safe to run on every boot.
"""
import logging
from pathlib import Path

from sqlalchemy import delete

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Document, Message
from app.services.ingestion.corpus import doc_id_for, ingest

logger = logging.getLogger("lumina.seed_demo")

DEMO_DOCS_DIR = Path(__file__).resolve().parents[2] / "demo_docs"
DEMO_SESSION_ID = "demo"
DEMO_SESSION_NAME = "Demo — ask these papers anything"


async def demo_already_seeded() -> bool:
    files = sorted(
        p.name
        for p in DEMO_DOCS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in settings.ALLOWED_EXTENSIONS
    )
    if not files:
        return True  # nothing to seed
    async with AsyncSessionLocal() as db:
        for name in files:
            doc = await db.get(Document, doc_id_for(name))
            if doc is None or doc.status != "ready" or not doc.num_chunks:
                return False
    return True


async def clear_demo_history() -> None:
    """Wipe the demo session's chat history on boot so visitors always land on
    the clean suggested-questions state."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(delete(Message).where(Message.session_id == DEMO_SESSION_ID))
        await db.commit()
        if result.rowcount:
            logger.info("Cleared %d messages from the demo session", result.rowcount)


async def seed_demo(force: bool = False) -> None:
    await clear_demo_history()
    if not force and await demo_already_seeded():
        logger.info("Demo session already seeded — skipping")
        return
    logger.info("Seeding demo session %r from %s", DEMO_SESSION_ID, DEMO_DOCS_DIR)
    manifest = await ingest(
        DEMO_DOCS_DIR, DEMO_SESSION_ID, strategy=None, session_name=DEMO_SESSION_NAME
    )
    logger.info("Demo seeded: %d documents", len(manifest["documents"]))
