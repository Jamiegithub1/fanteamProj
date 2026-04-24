from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.aggregation import refresh_aggregated_odds
from app.config import get_settings
from app.db import database_ready, get_session
from app.models import Bookmaker, SourceHealth
from app.projections import refresh_projections
from app.scheduler import RefreshScheduler
from app.source_runner import refresh_source
from app.sources.draftkings import DraftKingsAdapter
from app.sources.playzilla import PlayzillaAdapter

settings = get_settings()
scheduler = RefreshScheduler(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

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


@app.post("/sources/draftkings/refresh")
def refresh_draftkings() -> dict[str, str | int | None]:
    with get_session() as session:
        result = refresh_source(session, DraftKingsAdapter(settings=settings))
        return {
            "source": result.source_key,
            "status": result.status,
            "rows_found": len(result.odds),
            "latency_ms": result.latency_ms,
            "message": result.message,
        }


@app.post("/aggregations/refresh")
def refresh_aggregations() -> dict[str, int]:
    with get_session() as session:
        summary = refresh_aggregated_odds(session)
        return {"groups_seen": summary.groups_seen, "rows_written": summary.rows_written}


@app.post("/projections/refresh")
def refresh_projection_rows() -> dict[str, int]:
    with get_session() as session:
        summary = refresh_projections(session)
        return {"players_seen": summary.players_seen, "rows_written": summary.rows_written}


@app.post("/refresh/run")
async def run_refresh_cycle() -> dict[str, int | str]:
    summary = await scheduler.run_once()
    if summary is None:
        return {"status": "already_running"}
    return {
        "status": "ok",
        "sources_refreshed": summary.sources_refreshed,
        "aggregation_rows": summary.aggregation_rows,
        "projection_rows": summary.projection_rows,
    }
