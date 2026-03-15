import io
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import get_db
from app.services import agent_service, storage_service
from app.services.analysis_service import AnalysisService
from app.services.stt_service import get_stt_service
from app.services.tts_service import get_tts_service
from app.utils.config import settings

router = APIRouter()


class SimulatorStartRequest(BaseModel):
    phone_number: str | None = None


class SimulatorStartResponse(BaseModel):
    call_id: str
    greeting: str


class SimulatorTurnRequest(BaseModel):
    call_id: str
    text: str


class SimulatorTurnResponse(BaseModel):
    response_text: str
    call_complete: bool
    audio_url: Optional[str] = None
    user_text: Optional[str] = None


class SimulatorEndRequest(BaseModel):
    call_id: str


def _tts_to_url(text: str, call_id: str) -> Optional[str]:
    if settings.tts_provider.lower() == "stub":
        return None
    tts = get_tts_service()
    audio_bytes = tts.synthesize(text)
    if not audio_bytes:
        return None
    cache_dir = Path(settings.tts_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{call_id}-{uuid.uuid4().hex}.wav"
    path = cache_dir / filename
    path.write_bytes(audio_bytes)
    return f"{settings.public_base_url.rstrip('/')}/static/tts/{filename}"


def _read_wav_bytes(audio_bytes: bytes) -> tuple[bytes, int]:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
        return frames, sample_rate


@router.post("/simulator/start", response_model=SimulatorStartResponse)
def simulator_start(payload: SimulatorStartRequest, db: Session = Depends(get_db)):
    call_id = str(uuid.uuid4())
    call = models.Call(
        id=call_id,
        phone_number=payload.phone_number or "",
        start_time=datetime.utcnow(),
        status="in_progress",
        transcript=[],
        actions=[],
        context={},
    )
    db.add(call)
    db.commit()

    greeting = "Thanks for calling. How can I help you today?"
    storage_service.append_transcript(call, "agent", greeting)
    db.commit()
    return SimulatorStartResponse(call_id=call_id, greeting=greeting)


@router.post("/simulator/turn", response_model=SimulatorTurnResponse)
def simulator_turn(payload: SimulatorTurnRequest, db: Session = Depends(get_db)):
    call = db.query(models.Call).filter(models.Call.id == payload.call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    text = payload.text.strip()
    if not text:
        return SimulatorTurnResponse(response_text="", call_complete=False)

    storage_service.append_transcript(call, "patient", text)
    result = agent_service.handle_user_text(call, text, db)
    storage_service.append_transcript(call, "agent", result.response_text)
    db.commit()

    audio_url = _tts_to_url(result.response_text, call.id)
    return SimulatorTurnResponse(
        response_text=result.response_text,
        call_complete=result.call_complete,
        audio_url=audio_url,
        user_text=text,
    )


@router.post("/simulator/turn-audio", response_model=SimulatorTurnResponse)
def simulator_turn_audio(
    call_id: str = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    call = db.query(models.Call).filter(models.Call.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    audio_bytes = audio.file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        pcm_bytes, sample_rate = _read_wav_bytes(audio_bytes)
    except wave.Error as exc:
        raise HTTPException(status_code=400, detail="Invalid WAV file") from exc

    stt = get_stt_service()
    text = stt.transcribe(pcm_bytes, sample_rate)
    if not text:
        return SimulatorTurnResponse(response_text="", call_complete=False)

    storage_service.append_transcript(call, "patient", text)
    result = agent_service.handle_user_text(call, text, db)
    storage_service.append_transcript(call, "agent", result.response_text)
    db.commit()

    audio_url = _tts_to_url(result.response_text, call.id)
    return SimulatorTurnResponse(
        response_text=result.response_text,
        call_complete=result.call_complete,
        audio_url=audio_url,
        user_text=text,
    )


@router.post("/simulator/end")
def simulator_end(payload: SimulatorEndRequest, db: Session = Depends(get_db)):
    call = db.query(models.Call).filter(models.Call.id == payload.call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.status != "completed":
        call.status = "completed"
    call.end_time = datetime.utcnow()
    db.commit()

    analysis_service = AnalysisService()
    analysis_service.run_by_id(call.id)
    return {"status": "ok"}
