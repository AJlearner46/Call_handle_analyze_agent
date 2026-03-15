# AI Healthcare Call Center Agent + Call Intelligence Platform

This repo is a pragmatic backend scaffold for the AI healthcare call agent and post call intelligence you described. It includes:

- FastAPI service with call webhooks and appointment APIs
- LangGraph-ready conversation agent flow with LLM intent detection and slot filling
- Call storage, transcript, and analysis pipeline
- PostgreSQL ready models with SQLite default for local dev
- Analytics endpoints for the dashboard

It is designed so you can plug in real STT, TTS, and LLM providers later.

## Quick Start

1. Create a virtual environment and install dependencies.
2. Copy `.env.example` to `.env` and adjust values.
3. Start the API.

Example:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Environment

- `DATABASE_URL` default is SQLite for local dev. Use a Postgres URL in production.
- `PUBLIC_BASE_URL` is required for Twilio webhooks (must be publicly reachable).
- `GEMINI_API_KEY` used for LLM calls (stubbed in this scaffold).
- `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` used for telephony integrations.
- `STT_PROVIDER` and `TTS_PROVIDER` control which local providers to use.
- `CALL_MODE=gather` uses Twilio Gather (simple). `CALL_MODE=stream` enables Media Streams + local STT.
- `ENABLE_LANGGRAPH=true` toggles LangGraph orchestration.

## Core Endpoints

- `POST /call/incoming` Twilio webhook for new calls
- `POST /call/stream` Call turns (Twilio Gather or JSON for local testing)
- `WS /call/media-stream` Twilio Media Streams for audio streaming
- `POST /call/end` Call completed
- `GET /api/doctors` List doctors
- `GET /api/slots` Check slots
- `POST /api/appointments` Book appointment
- `DELETE /api/appointments/{appointment_id}` Cancel appointment
- `GET /api/analytics/summary` Dashboard metrics
- `GET /api/analytics/recent` Recent calls

## Notes on STT and TTS

The scaffold uses provider interfaces and does not force a paid API. You can wire in:

- STT: Vosk or Whisper (open source)
- TTS: Piper or Coqui TTS

The current Twilio Gather flow uses Twilio speech recognition which is not free. For a fully free STT path, use Twilio Media Streams and route audio to your own STT in `stt_service.py`.

## Frontend

The `frontend/` app is a small React + Vite UI that calls the analytics endpoints. Start it with:

```bash
cd frontend
npm install
npm run dev
```

## Call Simulator

Use the "Call Simulator" panel in the UI to test the conversation flow locally without Twilio.
It uses:

- `POST /api/simulator/start`
- `POST /api/simulator/turn`
- `POST /api/simulator/turn-audio` (WAV upload for local STT)
- `POST /api/simulator/end`

To enable local STT/TTS in the simulator, set:

- `STT_PROVIDER=vosk` and `VOSK_MODEL_PATH=...`
- `TTS_PROVIDER=piper` and `PIPER_MODEL_PATH=...`

## Next Steps

- Implement real LangGraph flow in `app/services/agent_service.py`
- Add Gemini API calls in `app/agents/call_agent.py` and `app/agents/analysis_agent.py`
- Build the React dashboard in a separate `dashboard/` app
- Replace stub STT and TTS with local models
