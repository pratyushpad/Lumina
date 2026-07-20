"""Document parser: extracts text blocks, images, and tables from PDF/text/image files."""
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

from app.config import settings
from app.utils.text_utils import normalize_whitespace

logger = logging.getLogger("lumina.parser")


@dataclass
class ParseResult:
    document_id: str
    text_chunks_raw: list[dict] = field(default_factory=list)
    extracted_images: list[dict] = field(default_factory=list)
    extracted_tables: list[dict] = field(default_factory=list)
    num_pages: int = 0
    has_images: bool = False
    metadata: dict = field(default_factory=dict)


class DocumentParser:
    def __init__(self, processed_dir: str | None = None):
        self.processed_dir = processed_dir or settings.PROCESSED_DIR
        self.images_dir = Path(self.processed_dir) / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    async def parse(self, file_path: str, document_id: str, file_type: str) -> ParseResult:
        if file_type == "pdf":
            return self._parse_pdf(file_path, document_id)
        if file_type == "image":
            return self._parse_image(file_path, document_id)
        if file_type in {"txt", "md"}:
            return self._parse_text(file_path, document_id)
        raise ValueError(f"Unsupported file type: {file_type}")

    def _parse_pdf(self, file_path: str, document_id: str) -> ParseResult:
        result = ParseResult(document_id=document_id)
        doc = fitz.open(file_path)
        result.num_pages = doc.page_count

        for page_idx in range(doc.page_count):
            page = doc[page_idx]
            page_num = page_idx + 1

            text_chars = 0
            blocks = page.get_text("blocks")
            for block in blocks:
                if len(block) < 7:
                    continue
                block_type = block[6]
                if block_type == 0:
                    text = normalize_whitespace(block[4] or "")
                    if text:
                        result.text_chunks_raw.append(
                            {"text": text, "page_num": page_num, "block_type": "text"}
                        )
                        text_chars += len(text)

            # Extract images
            page_images = page.get_images(full=True)
            for img_idx, img in enumerate(page_images):
                xref = img[0]
                try:
                    img_data = doc.extract_image(xref)
                    img_bytes = img_data["image"]
                    img_ext = img_data.get("ext", "png")
                    out_path = self.images_dir / f"{document_id}_{page_num}_{img_idx}.{img_ext}"
                    with open(out_path, "wb") as f:
                        f.write(img_bytes)
                    result.extracted_images.append(
                        {
                            "image_path": str(out_path),
                            "page_num": page_num,
                            "caption": f"Image on page {page_num}",
                            "image_heavy_page": text_chars < 100,
                        }
                    )
                    result.has_images = True
                except Exception as e:
                    logger.warning("Failed to extract image xref=%s: %s", xref, e)

        doc.close()

        # Tables via pdfplumber
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_num = page_idx + 1
                    tables = page.extract_tables() or []
                    for tbl in tables:
                        md = self._table_to_markdown(tbl)
                        if md:
                            result.extracted_tables.append(
                                {"table_text": md, "page_num": page_num}
                            )
                            result.text_chunks_raw.append(
                                {"text": md, "page_num": page_num, "block_type": "table"}
                            )
        except Exception as e:
            logger.warning("pdfplumber table extraction failed: %s", e)

        return result

    def _parse_image(self, file_path: str, document_id: str) -> ParseResult:
        result = ParseResult(document_id=document_id)
        ext = Path(file_path).suffix.lower().lstrip(".")
        dest = self.images_dir / f"{document_id}_1_0.{ext}"
        shutil.copy(file_path, dest)
        result.extracted_images.append(
            {
                "image_path": str(dest),
                "page_num": 1,
                "caption": Path(file_path).name,
                "image_heavy_page": True,
            }
        )
        result.has_images = True
        result.num_pages = 1
        return result

    def _parse_text(self, file_path: str, document_id: str) -> ParseResult:
        result = ParseResult(document_id=document_id)
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        content = normalize_whitespace(content)
        if content:
            result.text_chunks_raw.append({"text": content, "page_num": 1, "block_type": "text"})
        result.num_pages = 1
        return result

    @staticmethod
    def _table_to_markdown(table: list[list]) -> str:
        if not table:
            return ""
        rows = [["" if c is None else str(c).strip() for c in row] for row in table]
        if not rows or not rows[0]:
            return ""
        header = rows[0]
        sep = ["---"] * len(header)
        body = rows[1:]
        lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
        for row in body:
            # pad row to header length
            while len(row) < len(header):
                row.append("")
            lines.append("| " + " | ".join(row[: len(header)]) + " |")
        return "\n".join(lines)
