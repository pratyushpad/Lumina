"""Chunking strategies: fixed-size, recursive (paragraph/sentence-aware), and semantic.

All strategies share the same block/table/image handling; they differ only in how a
text block is split. The strategy name is stored on every chunk so the eval harness
can compare corpora chunked different ways side by side.
"""
import re
from dataclasses import dataclass

from app.config import settings
from app.utils.text_utils import estimate_tokens


@dataclass
class ChunkData:
    chunk_id: str
    document_id: str
    text: str
    page_num: int
    chunk_index: int
    block_type: str
    char_count: int
    token_estimate: int
    filename: str
    has_associated_image: bool = False
    image_path: str | None = None
    chunking_strategy: str = "recursive"


class BaseChunker:
    strategy = "base"

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def split(self, text: str) -> list[str]:
        raise NotImplementedError

    def chunk(
        self,
        text_blocks: list[dict],
        extracted_images: list[dict],
        document_id: str,
        filename: str,
    ) -> list[ChunkData]:
        out: list[ChunkData] = []
        idx = 0
        prev_tail = ""

        for block in text_blocks:
            text = block["text"]
            page_num = block["page_num"]
            block_type = block["block_type"]

            if block_type == "table":
                # Keep table as single chunk (do not split)
                chunk_text = text
                if prev_tail:
                    chunk_text = prev_tail + "\n\n" + chunk_text
                out.append(self._build_chunk(chunk_text, document_id, filename, page_num, idx, "table"))
                prev_tail = chunk_text[-self.chunk_overlap :]
                idx += 1
                continue

            for piece in self.split(text):
                stripped = piece.strip()
                if len(stripped) < 50:
                    continue
                final_text = (prev_tail + "\n" + stripped) if prev_tail else stripped
                out.append(
                    self._build_chunk(final_text, document_id, filename, page_num, idx, "text")
                )
                prev_tail = final_text[-self.chunk_overlap :]
                idx += 1

        # Image-caption chunks
        for img in extracted_images:
            page_num = img["page_num"]
            text = f"[IMAGE on page {page_num} of {filename}] {img.get('caption', '')}".strip()
            out.append(
                ChunkData(
                    chunk_id=f"{document_id}_chunk_{idx}",
                    document_id=document_id,
                    text=text,
                    page_num=page_num,
                    chunk_index=idx,
                    block_type="image_caption",
                    char_count=len(text),
                    token_estimate=estimate_tokens(text),
                    filename=filename,
                    has_associated_image=True,
                    image_path=img["image_path"],
                    chunking_strategy=self.strategy,
                )
            )
            idx += 1

        return out

    def _build_chunk(
        self, text: str, document_id: str, filename: str, page_num: int, idx: int, block_type: str
    ) -> ChunkData:
        return ChunkData(
            chunk_id=f"{document_id}_chunk_{idx}",
            document_id=document_id,
            text=text,
            page_num=page_num,
            chunk_index=idx,
            block_type=block_type,
            char_count=len(text),
            token_estimate=estimate_tokens(text),
            filename=filename,
            chunking_strategy=self.strategy,
        )

    def _hard_split(self, text: str, size: int) -> list[str]:
        result: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            result.append(text[start:end])
            if end >= len(text):
                break
            start = end - self.chunk_overlap
        return result


class FixedChunker(BaseChunker):
    """Fixed-size character windows with overlap; ignores structure entirely."""

    strategy = "fixed"

    def split(self, text: str) -> list[str]:
        return self._hard_split(text, self.chunk_size)


class RecursiveChunker(BaseChunker):
    """Recursive split preserving paragraph/sentence boundaries with overlap."""

    strategy = "recursive"

    def split(self, text: str) -> list[str]:
        return self._split_recursive(text, self.chunk_size)

    def _split_recursive(self, text: str, size: int) -> list[str]:
        if len(text) <= size:
            return [text]
        for sep in ["\n\n", "\n", ". "]:
            if sep in text:
                parts = text.split(sep)
                result: list[str] = []
                buf = ""
                for p in parts:
                    candidate = (buf + sep + p) if buf else p
                    if len(candidate) <= size:
                        buf = candidate
                    else:
                        if buf:
                            result.append(buf)
                        if len(p) > size:
                            result.extend(self._split_recursive(p, size))
                            buf = ""
                        else:
                            buf = p
                if buf:
                    result.append(buf)
                return result
        return self._hard_split(text, size)


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class SemanticChunker(BaseChunker):
    """Split at embedding-similarity breakpoints between adjacent sentences.

    Sentences are embedded (MiniLM); a boundary is placed where the cosine similarity
    between consecutive sentences drops below the corpus 25th percentile, then groups
    are merged up to chunk_size. Falls back to recursive splitting for short blocks.
    """

    strategy = "semantic"
    _BREAKPOINT_PERCENTILE = 25

    def split(self, text: str) -> list[str]:
        sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
        if len(sentences) < 4:
            return RecursiveChunker(self.chunk_size, self.chunk_overlap).split(text)

        import numpy as np

        from app.services.embedding.embedder import EmbeddingService

        embeddings = np.array(EmbeddingService.get().embed_texts(sentences))
        # Cosine similarity between consecutive sentences (embeddings are normalized)
        sims = (embeddings[:-1] * embeddings[1:]).sum(axis=1)
        threshold = float(np.percentile(sims, self._BREAKPOINT_PERCENTILE))

        groups: list[list[str]] = [[sentences[0]]]
        for sent, sim in zip(sentences[1:], sims, strict=True):
            if sim < threshold:
                groups.append([sent])
            else:
                groups[-1].append(sent)

        # Merge groups into chunks up to chunk_size (hard-split any oversized group)
        chunks: list[str] = []
        buf = ""
        for group in groups:
            piece = " ".join(group)
            candidate = (buf + " " + piece) if buf else piece
            if len(candidate) <= self.chunk_size:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf)
                if len(piece) > self.chunk_size:
                    chunks.extend(self._hard_split(piece, self.chunk_size))
                    buf = ""
                else:
                    buf = piece
        if buf:
            chunks.append(buf)
        return chunks


_STRATEGIES = {c.strategy: c for c in (FixedChunker, RecursiveChunker, SemanticChunker)}


def get_chunker(
    strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> BaseChunker:
    name = strategy or settings.CHUNKING_STRATEGY
    if name not in _STRATEGIES:
        raise ValueError(f"Unknown chunking strategy: {name!r} (choose from {sorted(_STRATEGIES)})")
    return _STRATEGIES[name](chunk_size, chunk_overlap)


# Backwards-compatible alias (pre-strategy-refactor name)
TextChunker = RecursiveChunker
