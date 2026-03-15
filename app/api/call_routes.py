import audioop
import base64
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Request, WebSocket
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.rest import Client

from app.db import models
from app.db.database import SessionLocal, get_db
from app.services import agent_service, storage_service
from app.services.analysis_service import AnalysisService
from app.services.stt_service import get_stt_service
from app.services.tts_service import get_tts_service
from app.utils.config import settings

router = APIRouter()


def _base_url() -> str:
    return settings.public_base_url.rstrip("/")


def _twilio_client() -> Client | None:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return None
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def _tts_to_url(text: str, call_id: str) -> str | None:
    tts = get_tts_service()
    audio_bytes = tts.synthesize(text)
    if not audio_bytes:
        return None
    cache_dir = Path(settings.tts_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{call_id}-{uuid.uuid4().hex}.wav"
    path = cache_dir / filename
    path.write_bytes(audio_bytes)
    return f"{_base_url()}/static/tts/{filename}"


def _render_twiml(text: str, call_id: str, gather: bool = True, hangup: bool = False) -> str:
    play_url = None
    if settings.tts_provider.lower() != "stub":
        try:
            play_url = _tts_to_url(text, call_id)
        except Exception:
            play_url = None

    say_or_play = f"<Play>{play_url}</Play>" if play_url else f"<Say>{text}</Say>"
    if hangup:
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Response>\n"
            f"  {say_or_play}\n"
            "  <Hangup />\n"
            "</Response>"
        )
    if gather:
        action_url = f"{_base_url()}/call/stream?call_id={call_id}"
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Response>\n"
            f"  {say_or_play}\n"
            f"  <Gather input=\"speech\" action=\"{action_url}\" method=\"POST\" speechTimeout=\"auto\" />\n"
            "</Response>"
        )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        f"  {say_or_play}\n"
        "</Response>"
    )


def _render_stream_twiml(prompt_text: str, call_id: str) -> str:
    base_url = _base_url()
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/call/media-stream?call_id={call_id}"
    play_url = None
    if settings.tts_provider.lower() != "stub":
        try:
            play_url = _tts_to_url(prompt_text, call_id)
        except Exception:
            play_url = None
    say_or_play = f"<Play>{play_url}</Play>" if play_url else f"<Say>{prompt_text}</Say>"
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<Response>\n"
        f"  <Start><Stream url=\"{stream_url}\" /></Start>\n"
        f"  {say_or_play}\n"
        "  <Pause length=\"60\" />\n"
        "</Response>"
    )


def _update_call(call_sid: str, text: str, call_id: str, hangup: bool = False) -> None:
    client = _twilio_client()
    if not client:
        return
    if hangup:
        twiml = _render_twiml(text, call_id, gather=False, hangup=True)
    else:
        twiml = _render_stream_twiml(text, call_id)
    client.calls(call_sid).update(twiml=twiml)


@router.post("/incoming")
async def incoming_call(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    from_number = form.get("From", "")
    call_id = str(uuid.uuid4())

    call = models.Call(
        id=call_id,
        phone_number=from_number,
        start_time=datetime.utcnow(),
        status="in_progress",
        transcript=[],
        actions=[],
        context={},
    )
    db.add(call)
    db.commit()

    if settings.call_mode == "stream":
        twiml = _render_stream_twiml("Thanks for calling. How can I help you today?", call_id)
    else:
        twiml = _render_twiml("Thanks for calling. How can I help you today?", call_id)
    return Response(content=twiml, media_type="text/xml")


@router.post("/stream")
async def call_stream(request: Request, db: Session = Depends(get_db)):
    call_id = request.query_params.get("call_id", "")
    call = db.query(models.Call).filter(models.Call.id == call_id).first()
    if not call:
        return Response(content="Call not found", status_code=404)

    text = ""
    if request.headers.get("content-type", "").startswith("application/json"):
        payload = await request.json()
        text = payload.get("text", "")
    else:
        form = await request.form()
        text = form.get("SpeechResult", "") or form.get("text", "")

    if not text:
        return Response(content="", status_code=204)

    storage_service.append_transcript(call, "patient", text)
    result = agent_service.handle_user_text(call, text, db)
    storage_service.append_transcript(call, "agent", result.response_text)

    db.commit()

    if result.call_complete:
        twiml = _render_twiml(result.response_text, call_id, gather=False, hangup=True)
    else:
        twiml = _render_twiml(result.response_text, call_id)

    return Response(content=twiml, media_type="text/xml")


@router.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    call_id = websocket.query_params.get("call_id", "")
    db = SessionLocal()
    try:
        call = db.query(models.Call).filter(models.Call.id == call_id).first()
        if not call:
            await websocket.close()
            return

        stt = get_stt_service()
        buffer = b""
        ratecv_state = None
        call_sid = None

        while True:
            message = await websocket.receive_json()
            event = message.get("event")

            if event == "start":
                call_sid = message.get("start", {}).get("callSid")
                if call_sid:
                    context = call.context or {}
                    context["call_sid"] = call_sid
                    call.context = context
                    db.commit()
                continue

            if event == "media":
                payload = message.get("media", {}).get("payload")
                if not payload:
                    continue
                audio_ulaw = base64.b64decode(payload)
                audio_pcm = audioop.ulaw2lin(audio_ulaw, 2)
                audio_pcm_16k, ratecv_state = audioop.ratecv(
                    audio_pcm, 2, 1, 8000, 16000, ratecv_state
                )
                buffer += audio_pcm_16k

                if len(buffer) < 16000 * 2 * 3:
                    continue

                text = stt.transcribe(buffer, 16000)
                buffer = b""
                if not text:
                    continue

                storage_service.append_transcript(call, "patient", text)
                result = agent_service.handle_user_text(call, text, db)
                storage_service.append_transcript(call, "agent", result.response_text)
                db.commit()

                if call_sid:
                    _update_call(call_sid, result.response_text, call.id, hangup=result.call_complete)
                if result.call_complete:
                    break

            if event == "stop":
                break
    finally:
        db.close()


@router.post("/end")
def end_call(
    call_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    call = db.query(models.Call).filter(models.Call.id == call_id).first()
    if not call:
        return {"status": "not_found"}

    call.status = call.status or "completed"
    call.end_time = datetime.utcnow()
    db.commit()

    analysis_service = AnalysisService()
    background_tasks.add_task(analysis_service.run_by_id, call.id)

    return {"status": "ok"}
