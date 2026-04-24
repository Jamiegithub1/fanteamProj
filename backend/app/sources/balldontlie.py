from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import Settings, get_settings
from app.sources.base import SourceOdd, SourceResult


PROP_MARKET_MAP = {
    "points": "points",
    "threes": "threes_made",
    "rebounds": "rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
    "double_double": "double_double",
    "triple_double": "triple_double",
}

VENDOR_NAMES = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "caesars": "Caesars",
    "betmgm": "BetMGM",
    "fanatics": "Fanatics",
    "betrivers": "BetRivers",
    "betway": "Betway",
    "ballybet": "Bally Bet",
    "betparx": "BetParx",
    "rebet": "Rebet",
}


class BallDontLieAdapter:
    source_key = "balldontlie"
    source_name = "BALLDONTLIE Odds"
    requires_browser = False

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.refresh_interval_seconds = self.settings.balldontlie_refresh_interval_seconds
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=self.settings.balldontlie_timeout_seconds,
            headers={"Authorization": self.settings.balldontlie_api_key, "Accept": "application/json"},
        )

    def fetch(self) -> SourceResult:
        started = perf_counter()
        if not self.settings.balldontlie_enabled:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="BALLDONTLIE source is disabled by BALLDONTLIE_ENABLED.",
            )
        if not self.settings.balldontlie_api_key:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="BALLDONTLIE_API_KEY is not configured.",
            )
        try:
            game_ids = self.fetch_game_ids(date.today())
            odds: list[SourceOdd] = []
            for game_id in game_ids:
                odds.extend(self.fetch_game_props(game_id))
            if not odds:
                return SourceResult(
                    source_key=self.source_key,
                    status="degraded",
                    latency_ms=int((perf_counter() - started) * 1000),
                    message="BALLDONTLIE returned no supported NBA player props.",
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
                message=f"BALLDONTLIE HTTP {exc.response.status_code}",
            )
        except Exception as exc:
            return SourceResult(
                source_key=self.source_key,
                status="failed",
                latency_ms=int((perf_counter() - started) * 1000),
                message=str(exc),
            )

    def fetch_game_ids(self, target_date: date) -> tuple[str, ...]:
        response = self.client.get(
            urljoin(self.settings.balldontlie_base_url, "/v2/odds"),
            params={"dates[]": target_date.isoformat(), "per_page": 100},
        )
        response.raise_for_status()
        payload = response.json()
        return tuple({str(item["game_id"]) for item in payload.get("data", []) if item.get("game_id")})

    def fetch_game_props(self, game_id: str) -> tuple[SourceOdd, ...]:
        response = self.client.get(
            urljoin(self.settings.balldontlie_base_url, "/v2/odds/player_props"),
            params={"game_id": game_id},
        )
        response.raise_for_status()
        return self.parse_player_props(response.json())

    def parse_player_props(self, payload: dict[str, Any]) -> tuple[SourceOdd, ...]:
        collected_at = datetime.now(UTC)
        odds: list[SourceOdd] = []
        for item in payload.get("data", []):
            prop_type = item.get("prop_type")
            market_key = PROP_MARKET_MAP.get(prop_type)
            market = item.get("market") or {}
            vendor = str(item.get("vendor") or "").lower()
            player_name = _player_name(item)
            if not market_key or not vendor or not player_name:
                continue
            line = _decimal(item.get("line_value"))
            game_id = str(item.get("game_id")) if item.get("game_id") is not None else None
            if market.get("type") == "over_under":
                over_odds = _int(market.get("over_odds"))
                under_odds = _int(market.get("under_odds"))
                if over_odds is not None:
                    odds.append(
                        _odd(item, market_key, "over", player_name, vendor, collected_at, line, game_id, over_odds)
                    )
                if under_odds is not None:
                    odds.append(
                        _odd(item, market_key, "under", player_name, vendor, collected_at, line, game_id, under_odds)
                    )
            elif market.get("type") == "milestone":
                yes_odds = _int(market.get("odds"))
                if yes_odds is not None:
                    odds.append(
                        _odd(item, market_key, "yes", player_name, vendor, collected_at, line, game_id, yes_odds)
                    )
        return tuple(odds)


def _odd(
    item: dict[str, Any],
    market_key: str,
    side: str,
    player_name: str,
    vendor: str,
    collected_at: datetime,
    line: Decimal | None,
    game_id: str | None,
    american_odds: int,
) -> SourceOdd:
    return SourceOdd(
        source_key="balldontlie",
        bookmaker_key=vendor,
        bookmaker_name=VENDOR_NAMES.get(vendor, vendor.title()),
        player_name=player_name,
        market_key=market_key,
        market_name=str(item.get("prop_type") or market_key).replace("_", " ").title(),
        side=side,  # type: ignore[arg-type]
        line=line,
        american_odds=american_odds,
        event_id=game_id,
        collected_at=collected_at,
    )


def _player_name(item: dict[str, Any]) -> str:
    player = item.get("player")
    if isinstance(player, dict):
        first_name = str(player.get("first_name") or "").strip()
        last_name = str(player.get("last_name") or "").strip()
        return " ".join(part for part in (first_name, last_name) if part)
    return str(item.get("player_name") or item.get("player_id") or "").strip()


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
