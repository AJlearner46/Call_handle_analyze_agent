from datetime import datetime

from app.db import models


def append_transcript(call: models.Call, role: str, text: str) -> None:
    transcript = call.transcript or []
    transcript.append({"role": role, "text": text, "timestamp": datetime.utcnow().isoformat()})
    call.transcript = transcript


def append_action(call: models.Call, action: str, payload: dict | None = None) -> None:
    actions = call.actions or []
    actions.append({"action": action, "payload": payload or {}, "timestamp": datetime.utcnow().isoformat()})
    call.actions = actions
