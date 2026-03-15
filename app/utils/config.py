import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./dev.db")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    stt_provider: str = os.getenv("STT_PROVIDER", "stub")
    tts_provider: str = os.getenv("TTS_PROVIDER", "stub")
    call_mode: str = os.getenv("CALL_MODE", "gather")
    enable_langgraph: bool = _get_bool("ENABLE_LANGGRAPH", True)
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    vosk_model_path: str = os.getenv("VOSK_MODEL_PATH", "")
    piper_model_path: str = os.getenv("PIPER_MODEL_PATH", "")
    tts_cache_dir: str = os.getenv("TTS_CACHE_DIR", "app/static/tts")


settings = Settings()
