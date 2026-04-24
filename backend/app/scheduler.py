from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.aggregation import refresh_aggregated_odds
from app.config import Settings
from app.db import get_session
from app.models import Game
from app.projections import refresh_projections
from app.source_runner import refresh_source
from app.sources.draftkings import DraftKingsAdapter
from app.sources.playzilla import PlayzillaAdapter


@dataclass(frozen=True)
class RefreshCycleSummary:
    sources_refreshed: int
    aggregation_rows: int
    projection_rows: int


class RefreshScheduler:
    def __init__(self, settings: Settings, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.settings = settings
        self.sleep = sleep
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if not self.settings.scheduler_enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def run_once(self) -> RefreshCycleSummary | None:
        if self._lock.locked():
            return None
        async with self._lock:
            return await asyncio.to_thread(run_refresh_cycle, self.settings)

    async def _loop(self) -> None:
        await self.sleep(self.settings.scheduler_initial_delay_seconds)
        while not self._stop_event.is_set():
            await self.run_once()
            interval = await asyncio.to_thread(next_refresh_interval_seconds, self.settings)
            await self.sleep(interval)


def run_refresh_cycle(settings: Settings) -> RefreshCycleSummary:
    with get_session() as session:
        source_count = _refresh_sources(session, settings)
        aggregation = refresh_aggregated_odds(session)
        projection = refresh_projections(session)
        return RefreshCycleSummary(
            sources_refreshed=source_count,
            aggregation_rows=aggregation.rows_written,
            projection_rows=projection.rows_written,
        )


def _refresh_sources(session: Session, settings: Settings) -> int:
    adapters = [PlayzillaAdapter(settings=settings), DraftKingsAdapter(settings=settings)]
    for adapter in adapters:
        refresh_source(session, adapter)
    return len(adapters)


def next_refresh_interval_seconds(settings: Settings) -> int:
    if has_game_near_lock(settings):
        return settings.scheduler_prelock_interval_seconds
    return settings.scheduler_regular_interval_seconds


def has_game_near_lock(settings: Settings) -> bool:
    now = datetime.now(UTC)
    window_end = now + timedelta(minutes=settings.scheduler_prelock_window_minutes)
    with get_session() as session:
        game = session.scalar(select(Game).where(Game.starts_at >= now, Game.starts_at <= window_end).limit(1))
        return game is not None
