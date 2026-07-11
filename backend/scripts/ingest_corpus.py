"""Deterministic ingestion of the eval corpus: `make ingest`.

Every run produces identical chunk ids for identical inputs:
- documents are processed in sorted filename order,
- document ids derive from sha256 of the filename (not a random uuid),
- chunk ids are `{document_id}_chunk_{index}` with deterministic chunking.

All documents land in a dedicated session (default id: eval-corpus), replacing any
previous ingest of the same corpus. A manifest of chunk ids per document is written
next to the corpus so the eval dataset can reference ground-truth chunks stably.
"""
import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("lumina.ingest")

CORPUS_DIR_DEFAULT = Path(__file__).resolve().parents[2] / "eval" / "corpus"
SESSION_ID_DEFAULT = "eval-corpus"


def doc_id_for(filename: str) -> str:
    return "doc-" + hashlib.sha256(filename.encode("utf-8")).hexdigest()[:16]


async def ingest(corpus_dir: Path, session_id: str, strategy: str | None) -> dict:
    from app.config import settings
    from app.database import AsyncSessionLocal
    from app.migrations import run_migrations
    from app.models import Document, Session
    from app.services.embedding.embedder import EmbeddingService
    from app.services.ingestion.extractor import IngestionPipeline
    from app.services.retrieval.sparse import BM25Index
    from app.services.vectorstore.pgvector import PgVectorStore
    from app.utils.file_handler import get_file_type

    await run_migrations()

    files = sorted(
        p for p in corpus_dir.iterdir()
        if p.is_file() and p.suffix.lower() in settings.ALLOWED_EXTENSIONS
    )
    if not files:
        raise SystemExit(f"No ingestible files in {corpus_dir}")

    pipeline = IngestionPipeline(chunking_strategy=strategy)
    embedder = EmbeddingService.get()
    store = PgVectorStore.get()
    manifest: dict = {
        "session_id": session_id,
        "chunking_strategy": pipeline.chunker.strategy,
        "chunk_size": pipeline.chunker.chunk_size,
        "chunk_overlap": pipeline.chunker.chunk_overlap,
        "embedding_model": settings.EMBEDDING_MODEL,
        "ingested_at": datetime.utcnow().isoformat(),
        "documents": {},
    }

    async with AsyncSessionLocal() as db:
        sess = await db.get(Session, session_id)
        if sess is None:
            db.add(Session(id=session_id, name="Eval Corpus"))
            await db.commit()

    for path in files:
        document_id = doc_id_for(path.name)
        file_type = get_file_type(path.name)
        logger.info("Ingesting %s as %s (%s)", path.name, document_id, file_type)

        await store.delete_by_document_id(document_id)
        BM25Index.get().invalidate(document_id)

        parse_result, chunks = await pipeline.process(
            str(path), document_id, file_type, path.name
        )
        if chunks:
            vectors = embedder.embed_texts([c.text for c in chunks])
            await store.add_chunks(chunks, vectors)

        async with AsyncSessionLocal() as db:
            doc = await db.get(Document, document_id)
            if doc is None:
                doc = Document(id=document_id, session_id=session_id,
                               filename=path.name, stored_path=str(path),
                               file_type=file_type)
                db.add(doc)
            doc.status = "ready"
            doc.num_chunks = len(chunks)
            doc.num_pages = parse_result.num_pages
            doc.has_images = parse_result.has_images
            doc.file_size_bytes = path.stat().st_size
            doc.processed_at = datetime.utcnow()
            await db.commit()

        manifest["documents"][path.name] = {
            "document_id": document_id,
            "num_chunks": len(chunks),
            "chunk_ids": [c.chunk_id for c in chunks],
        }

    manifest_path = corpus_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Wrote %s (%d documents)", manifest_path, len(files))
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic eval-corpus ingestion")
    ap.add_argument("--corpus", type=Path, default=CORPUS_DIR_DEFAULT)
    ap.add_argument("--session-id", default=SESSION_ID_DEFAULT)
    ap.add_argument("--strategy", default=None, help="fixed | recursive | semantic")
    args = ap.parse_args()
    asyncio.run(ingest(args.corpus, args.session_id, args.strategy))


if __name__ == "__main__":
    main()
