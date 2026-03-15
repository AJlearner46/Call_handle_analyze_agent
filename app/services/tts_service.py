from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
import tempfile

from app.utils.config import settings


class BaseTTSService:
    def synthesize(self, text: str) -> bytes:
        raise NotImplementedError


class StubTTSService(BaseTTSService):
    def synthesize(self, text: str) -> bytes:
        return b""


@dataclass
class PiperTTSService(BaseTTSService):
    model_path: str

    def synthesize(self, text: str) -> bytes:
        if not self.model_path:
            raise RuntimeError("PIPER_MODEL_PATH is not configured")
        Path(settings.tts_cache_dir).mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=settings.tts_cache_dir, suffix=".wav", delete=False) as tmp:
            output_path = Path(tmp.name)
        process = subprocess.run(
            ["piper", "--model", self.model_path, "--output_file", str(output_path)],
            input=text,
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(process.stderr or "Piper TTS failed")
        data = output_path.read_bytes()
        output_path.unlink(missing_ok=True)
        return data


def get_tts_service() -> BaseTTSService:
    provider = settings.tts_provider.lower()
    if provider == "piper":
        return PiperTTSService(settings.piper_model_path)
    return StubTTSService()
