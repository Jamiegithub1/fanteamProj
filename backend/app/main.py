from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from app.aggregation import refresh_aggregated_odds
from app.config import get_settings
from app.db import database_ready, get_session
from app.models import AggregatedOdd, Bookmaker, Player, Projection, SourceHealth, Team
from app.projections import refresh_projections
from app.scheduler import RefreshScheduler
from app.security import require_auth
from app.source_catalog import SOURCE_CATALOG
from app.source_runner import refresh_source
from app.sources.balldontlie import BallDontLieAdapter
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
def sources_health(_: str = Depends(require_auth)) -> list[dict[str, str | int | None]]:
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


@app.get("/sources/catalog")
def sources_catalog(_: str = Depends(require_auth)) -> list[dict[str, str | int]]:
    return [
        {
            "key": source.key,
            "name": source.name,
            "role": source.role,
            "status": source.status,
            "cost": source.cost,
            "access": source.access,
            "coverage": source.coverage,
            "server_load": source.server_load,
            "reliability_notes": source.reliability_notes,
            "implementation_notes": source.implementation_notes,
            "priority": source.priority,
        }
        for source in SOURCE_CATALOG
    ]


@app.get("/projections")
def list_projections(_: str = Depends(require_auth)) -> list[dict[str, str | int | float | None]]:
    with get_session() as session:
        source_counts = dict(
            session.execute(
                select(AggregatedOdd.player_id, func.coalesce(func.sum(AggregatedOdd.source_count), 0)).group_by(
                    AggregatedOdd.player_id
                )
            ).all()
        )
        rows = session.execute(
            select(Projection, Player, Team)
            .join(Player, Projection.player_id == Player.id)
            .outerjoin(Team, Player.team_id == Team.id)
            .order_by(Projection.fantasy_points.desc())
        ).all()
        return [
            {
                "player_id": player.id,
                "player_name": player.name,
                "team": team.abbreviation if team else None,
                "projection_date": projection.projection_date.isoformat(),
                "points": _float(projection.points),
                "threes_made": _float(projection.threes_made),
                "rebounds": _float(projection.rebounds),
                "assists": _float(projection.assists),
                "steals": _float(projection.steals),
                "blocks": _float(projection.blocks),
                "turnovers": _float(projection.turnovers),
                "double_double_probability": _float(projection.double_double_probability),
                "triple_double_probability": _float(projection.triple_double_probability),
                "fantasy_points": _float(projection.fantasy_points),
                "confidence_score": _float(projection.confidence_score),
                "source_count": int(source_counts.get(player.id, 0)),
                "calculated_at": projection.calculated_at.isoformat(),
            }
            for projection, player, team in rows
        ]


@app.post("/sources/playzilla/refresh")
def refresh_playzilla(_: str = Depends(require_auth)) -> dict[str, str | int | None]:
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
def refresh_draftkings(_: str = Depends(require_auth)) -> dict[str, str | int | None]:
    with get_session() as session:
        result = refresh_source(session, DraftKingsAdapter(settings=settings))
        return {
            "source": result.source_key,
            "status": result.status,
            "rows_found": len(result.odds),
            "latency_ms": result.latency_ms,
            "message": result.message,
        }


@app.post("/sources/balldontlie/refresh")
def refresh_balldontlie(_: str = Depends(require_auth)) -> dict[str, str | int | None]:
    with get_session() as session:
        result = refresh_source(session, BallDontLieAdapter(settings=settings))
        return {
            "source": result.source_key,
            "status": result.status,
            "rows_found": len(result.odds),
            "latency_ms": result.latency_ms,
            "message": result.message,
        }


@app.post("/aggregations/refresh")
def refresh_aggregations(_: str = Depends(require_auth)) -> dict[str, int]:
    with get_session() as session:
        summary = refresh_aggregated_odds(session)
        return {"groups_seen": summary.groups_seen, "rows_written": summary.rows_written}


@app.post("/projections/refresh")
def refresh_projection_rows(_: str = Depends(require_auth)) -> dict[str, int]:
    with get_session() as session:
        summary = refresh_projections(session)
        return {"players_seen": summary.players_seen, "rows_written": summary.rows_written}


@app.post("/refresh/run")
async def run_refresh_cycle(_: str = Depends(require_auth)) -> dict[str, int | str]:
    summary = await scheduler.run_once()
    if summary is None:
        return {"status": "already_running"}
    return {
        "status": "ok",
        "sources_refreshed": summary.sources_refreshed,
        "aggregation_rows": summary.aggregation_rows,
        "projection_rows": summary.projection_rows,
    }


@app.get("/auth/check")
def auth_check(username: str = Depends(require_auth)) -> dict[str, str]:
    return {"status": "ok", "username": username}


def _float(value) -> float | None:
    return float(value) if value is not None else None
