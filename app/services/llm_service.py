import json
import re
from typing import Any

from app.utils.config import settings


class LLMService:
    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self):
        if self._client:
            return self._client
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError("google-generativeai is not installed") from exc

        genai.configure(api_key=settings.gemini_api_key)
        self._client = genai.GenerativeModel(settings.gemini_model)
        return self._client

    def generate(self, prompt: str) -> str:
        client = self._ensure_client()
        response = client.generate_content(prompt)
        return response.text or ""

    def generate_json(self, prompt: str, fallback: dict | None = None) -> dict[str, Any]:
        text = self.generate(prompt)
        extracted = _extract_json(text)
        if extracted is not None:
            return extracted
        return fallback or {}


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
