from __future__ import annotations

import json
from dataclasses import dataclass

from app.utils.config import settings


class BaseSTTService:
    def transcribe(self, audio_bytes: bytes, sample_rate: int) -> str:
        raise NotImplementedError


class StubSTTService(BaseSTTService):
    def transcribe(self, audio_bytes: bytes, sample_rate: int) -> str:
        return ""


@dataclass
class VoskSTTService(BaseSTTService):
    model_path: str

    def __post_init__(self) -> None:
        try:
            from vosk import Model
        except ImportError as exc:
            raise RuntimeError("vosk is not installed") from exc
        if not self.model_path:
            raise RuntimeError("VOSK_MODEL_PATH is not configured")
        self._model = Model(self.model_path)

    def transcribe(self, audio_bytes: bytes, sample_rate: int) -> str:
        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(self._model, sample_rate)
        recognizer.AcceptWaveform(audio_bytes)
        result = recognizer.Result()
        payload = json.loads(result)
        return payload.get("text", "")


def get_stt_service() -> BaseSTTService:
    provider = settings.stt_provider.lower()
    if provider == "vosk":
        return VoskSTTService(settings.vosk_model_path)
    return StubSTTService()
