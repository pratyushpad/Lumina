"""Orchestrates parsing + chunking for a single document."""
from typing import Optional

from app.services.ingestion.chunker import ChunkData, get_chunker
from app.services.ingestion.parser import DocumentParser, ParseResult


class IngestionPipeline:
    def __init__(
        self,
        chunking_strategy: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        self.parser = DocumentParser()
        self.chunker = get_chunker(chunking_strategy, chunk_size, chunk_overlap)

    async def process(
        self, file_path: str, document_id: str, file_type: str, filename: str
    ) -> tuple[ParseResult, list[ChunkData]]:
        parse_result = await self.parser.parse(file_path, document_id, file_type)
        chunks = self.chunker.chunk(
            parse_result.text_chunks_raw,
            parse_result.extracted_images,
            document_id,
            filename,
        )
        return parse_result, chunks
