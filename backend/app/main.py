from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.db import database_ready, get_session
from app.models import Bookmaker, SourceHealth
from app.source_runner import refresh_source
from app.sources.playzilla import PlayzillaAdapter

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}


@app.get("/health/db")
def db_health() -> dict[str, str]:
    return {"status": "ok" if database_ready() else "unavailable"}


@app.get("/sources/health")
def sources_health() -> list[dict[str, str | int | None]]:
    with get_session() as session:
        rows = session.execute(select(Bookmaker, SourceHealth).join(SourceHealth)).all()
        return [
            {
                "source": bookmaker.key,
                "name": bookmaker.name,
                "status": health.status,
                "consecutive_failures": health.consecutive_failures,
                "disabled_reason": health.disabled_reason,
                "latency_ms": health.latency_ms,
            }
            for bookmaker, health in rows
        ]


@app.post("/sources/playzilla/refresh")
def refresh_playzilla() -> dict[str, str | int | None]:
    with get_session() as session:
        result = refresh_source(session, PlayzillaAdapter(settings=settings))
        return {
            "source": result.source_key,
            "status": result.status,
            "rows_found": len(result.odds),
            "latency_ms": result.latency_ms,
            "message": result.message,
        }
