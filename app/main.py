from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import call_routes, appointment_routes, analytics_routes, simulator_routes
from app.db.database import engine
from app.db.models import Base
from app.utils.config import settings

app = FastAPI(title="AI Healthcare Call Center", version="0.1.0")

app.include_router(call_routes.router, prefix="/call", tags=["calls"])
app.include_router(appointment_routes.router, prefix="/api", tags=["appointments"])
app.include_router(analytics_routes.router, prefix="/api", tags=["analytics"])
app.include_router(simulator_routes.router, prefix="/api", tags=["simulator"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
