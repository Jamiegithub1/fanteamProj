from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import Settings, get_settings
from app.sources.base import SourceOdd, SourceResult
from app.sources.balldontlie import VENDOR_NAMES


MARKET_MAP = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_threes": "threes_made",
    "player_steals": "steals",
    "player_blocks": "blocks",
    "player_turnovers": "turnovers",
    "player_double_double": "double_double",
    "player_triple_double": "triple_double",
}


class PropLineAdapter:
    source_key = "propline"
    source_name = "PropLine"
    requires_browser = False

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.refresh_interval_seconds = self.settings.propline_refresh_interval_seconds
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=self.settings.propline_timeout_seconds,
            headers={"Accept": "application/json"},
        )

    def fetch(self) -> SourceResult:
        started = perf_counter()
        if not self.settings.propline_enabled:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="PropLine source is disabled by PROPLINE_ENABLED.",
            )
        if not self.settings.propline_api_key:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="PROPLINE_API_KEY is not configured.",
            )
        try:
            events_response = self.client.get(
                urljoin(self.settings.propline_base_url, "/v1/sports/basketball_nba/events"),
                params={"apiKey": self.settings.propline_api_key},
            )
            events_response.raise_for_status()
            odds: list[SourceOdd] = []
            for event in events_response.json():
                event_id = str(event.get("id") or "")
                if not event_id:
                    continue
                odds.extend(self.fetch_event_odds(event_id))
            if not odds:
                return SourceResult(
                    source_key=self.source_key,
                    status="degraded",
                    latency_ms=int((perf_counter() - started) * 1000),
                    message="PropLine returned no supported NBA player props.",
                )
            return SourceResult(
                source_key=self.source_key,
                odds=tuple(odds),
                status="success",
                latency_ms=int((perf_counter() - started) * 1000),
            )
        except httpx.HTTPStatusError as exc:
            return SourceResult(
                source_key=self.source_key,
                status="failed",
                latency_ms=int((perf_counter() - started) * 1000),
                message=f"PropLine HTTP {exc.response.status_code}",
            )
        except Exception as exc:
            return SourceResult(
                source_key=self.source_key,
                status="failed",
                latency_ms=int((perf_counter() - started) * 1000),
                message=str(exc),
            )

    def fetch_event_odds(self, event_id: str) -> tuple[SourceOdd, ...]:
        response = self.client.get(
            urljoin(self.settings.propline_base_url, f"/v1/sports/basketball_nba/events/{event_id}/odds"),
            params={
                "apiKey": self.settings.propline_api_key,
                "markets": ",".join(MARKET_MAP),
                "oddsFormat": "american",
            },
        )
        response.raise_for_status()
        return self.parse_odds(response.json())

    def parse_odds(self, payload: dict[str, Any]) -> tuple[SourceOdd, ...]:
        collected_at = datetime.now(UTC)
        odds: list[SourceOdd] = []
        event_id = str(payload.get("id") or payload.get("event_id") or "")
        for bookmaker in payload.get("bookmakers", []):
            bookmaker_key = _bookmaker_key(bookmaker)
            if not bookmaker_key:
                continue
            for market in bookmaker.get("markets", []):
                market_key = MARKET_MAP.get(str(market.get("key") or ""))
                if not market_key:
                    continue
                for outcome in market.get("outcomes", []):
                    side = _side(outcome)
                    player_name = str(outcome.get("description") or outcome.get("player") or outcome.get("name") or "").strip()
                    american_odds = _int(outcome.get("price") or outcome.get("odds"))
                    line = _decimal(outcome.get("point") or outcome.get("line"))
                    if not side or not player_name or american_odds is None:
                        continue
                    odds.append(
                        SourceOdd(
                            source_key=self.source_key,
                            bookmaker_key=bookmaker_key,
                            bookmaker_name=VENDOR_NAMES.get(bookmaker_key, bookmaker_key.title()),
                            player_name=player_name,
                            market_key=market_key,
                            market_name=str(market.get("key") or market_key).replace("_", " ").title(),
                            side=side,
                            line=line,
                            american_odds=american_odds,
                            event_id=event_id or None,
                            collected_at=collected_at,
                        )
                    )
        return tuple(odds)


def _bookmaker_key(bookmaker: dict[str, Any]) -> str:
    return str(bookmaker.get("key") or bookmaker.get("title") or bookmaker.get("name") or "").lower().replace(" ", "")


def _side(outcome: dict[str, Any]) -> str | None:
    name = str(outcome.get("name") or outcome.get("side") or "").lower()
    if name.startswith("over"):
        return "over"
    if name.startswith("under"):
        return "under"
    if name == "yes":
        return "yes"
    if name == "no":
        return "no"
    return None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
