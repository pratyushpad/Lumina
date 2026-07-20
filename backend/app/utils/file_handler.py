import os
import shutil
from pathlib import Path

import anyio
from fastapi import UploadFile


def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def get_file_type(filename: str) -> str:
    ext = get_file_extension(filename)
    if ext == ".pdf":
        return "pdf"
    if ext == ".txt":
        return "txt"
    if ext == ".md":
        return "md"
    if ext in {".png", ".jpg", ".jpeg"}:
        return "image"
    return "unknown"


async def save_upload_file(upload_file: UploadFile, destination: str) -> int:
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    bytes_written = 0
    chunk_size = 1024 * 1024
    # Async file IO: writing a multi-MB upload synchronously would block the
    # event loop, stalling every concurrent SSE stream on the single-worker
    # deployment for the duration of the write.
    async with await anyio.open_file(destination, "wb") as out:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            await out.write(chunk)
            bytes_written += len(chunk)
    return bytes_written


def cleanup_document_files(stored_path: str, document_id: str, processed_dir: str):
    try:
        if stored_path and os.path.exists(stored_path):
            os.remove(stored_path)
    except OSError:
        pass
    images_dir = Path(processed_dir) / "images"
    if images_dir.exists():
        for f in images_dir.glob(f"{document_id}_*"):
            try:
                f.unlink()
            except OSError:
                pass


def ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def rmtree_safe(path: str):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass
