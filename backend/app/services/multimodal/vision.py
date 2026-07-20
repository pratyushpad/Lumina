"""Gemini vision: describe images for multimodal retrieval."""
import base64
import logging
from typing import Optional

from google import genai
from google.genai import types

from app.config import settings
from app.services.retrieval.types import RetrievalResult
from app.utils.image_utils import encode_image_base64

logger = logging.getLogger("lumina.vision")


class VisionService:
    _instance: Optional["VisionService"] = None

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.cache: dict[str, str] = {}

    @classmethod
    def get(cls) -> "VisionService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def describe_image(self, image_path: str, context_query: str = "") -> str:
        if image_path in self.cache:
            return self.cache[image_path]
        try:
            b64, mime = encode_image_base64(image_path)
            img_bytes = base64.b64decode(b64)
            image_part = types.Part.from_bytes(data=img_bytes, mime_type=mime)

            prompt = (
                "Describe this image/figure/chart in detail. "
                "Include all numbers, labels, axes, and key findings visible."
            )
            if context_query:
                prompt += f" Focus on: {context_query}"

            resp = await self.client.aio.models.generate_content(
                model=settings.LLM_MODEL,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(max_output_tokens=512, temperature=0.2),
            )
            description = resp.text or ""
            self.cache[image_path] = description
            return description
        except Exception as e:
            logger.warning("Vision describe failed for %s: %s", image_path, e)
            return ""

    async def enrich_retrieval_results(
        self, results: list[RetrievalResult], query: str
    ) -> list[RetrievalResult]:
        for r in results:
            if r.has_associated_image and r.image_path:
                desc = await self.describe_image(r.image_path, query)
                if desc:
                    r.text = f"{r.text}\n\nImage description: {desc}"
        return results
