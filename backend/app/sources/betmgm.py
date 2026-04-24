from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import Settings, get_settings
from app.sources.base import SourceOdd, SourceResult
from app.sources.markets import identify_market


class BetMGMAdapter:
    source_key = "betmgm"
    source_name = "BetMGM"
    requires_browser = False

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.refresh_interval_seconds = self.settings.betmgm_refresh_interval_seconds
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=self.settings.betmgm_timeout_seconds,
            headers=self._headers(),
        )

    def fetch(self) -> SourceResult:
        started = perf_counter()
        if not self.settings.betmgm_enabled:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="BetMGM source is disabled by BETMGM_ENABLED.",
            )
        if not self.settings.betmgm_access_id or not self.settings.betmgm_access_token:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="BETMGM_ACCESS_ID and BETMGM_ACCESS_TOKEN are required by the documented Sports API.",
            )
        if not self.settings.betmgm_sport_id:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="BETMGM_SPORT_ID is not configured; run sports discovery before enabling fixture refresh.",
            )
        try:
            response = self.client.get(
                urljoin(
                    self.settings.betmgm_base_url,
                    f"/offer/api/{self.settings.betmgm_sport_id}/{self.settings.betmgm_country}/fixtures",
                ),
                params={"language": "en", "onlyMainMarkets": "false", "marketsFilterCriteria": "Visible"},
            )
            response.raise_for_status()
            odds = self.parse_fixtures(response.json())
            if not odds:
                return SourceResult(
                    source_key=self.source_key,
                    status="degraded",
                    latency_ms=int((perf_counter() - started) * 1000),
                    message="BetMGM returned no supported NBA player props.",
                )
            return SourceResult(
                source_key=self.source_key,
                odds=odds,
                status="success",
                latency_ms=int((perf_counter() - started) * 1000),
            )
        except httpx.HTTPStatusError as exc:
            return SourceResult(
                source_key=self.source_key,
                status="failed",
                latency_ms=int((perf_counter() - started) * 1000),
                message=f"BetMGM HTTP {exc.response.status_code}",
            )
        except Exception as exc:
            return SourceResult(
                source_key=self.source_key,
                status="failed",
                latency_ms=int((perf_counter() - started) * 1000),
                message=str(exc),
            )

    def parse_fixtures(self, payload: dict[str, Any]) -> tuple[SourceOdd, ...]:
        collected_at = datetime.now(UTC)
        odds: list[SourceOdd] = []
        for fixture in payload.get("items", []):
            event_id = _compound_id(fixture.get("id"))
            event_name = _translation(fixture.get("name"))
            for market in fixture.get("markets", []):
                market_name = _translation(market.get("name"))
                market_def = identify_market(market_name)
                if not market_def:
                    continue
                line = _decimal(market.get("value"))
                for option in market.get("options", []):
                    side = _side(_translation(option.get("name")))
                    player_name = _player_from_option(option, market_name)
                    american_odds = _price(option)
                    if not side or not player_name or american_odds is None:
                        continue
                    odds.append(
                        SourceOdd(
                            source_key=self.source_key,
                            bookmaker_key=self.source_key,
                            bookmaker_name=self.source_name,
                            player_name=player_name,
                            market_key=market_def.key,
                            market_name=market_def.name,
                            side=side,
                            line=line,
                            american_odds=american_odds,
                            event_id=event_id,
                            event_name=event_name,
                            collected_at=collected_at,
                        )
                    )
        return tuple(odds)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.settings.betmgm_access_id:
            headers["AccessId"] = self.settings.betmgm_access_id
        if self.settings.betmgm_access_token:
            headers["AccessIdToken"] = self.settings.betmgm_access_token
        return headers


def _translation(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("text"):
                return str(item["text"]).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _compound_id(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("full"):
                return str(item["full"])
    return None


def _side(value: str) -> str | None:
    normalized = value.lower()
    if normalized.startswith("over"):
        return "over"
    if normalized.startswith("under"):
        return "under"
    if normalized in {"yes", "no"}:
        return normalized
    return None


def _player_from_option(option: dict[str, Any], market_name: str) -> str:
    option_name = _translation(option.get("name"))
    for token in ("Over", "Under", "Yes", "No", market_name):
        option_name = option_name.replace(token, "")
    return " ".join(part for part in option_name.replace("-", " ").split() if _decimal(part) is None)


def _price(option: dict[str, Any]) -> int | None:
    prices = option.get("price")
    if isinstance(prices, list):
        for price in prices:
            if isinstance(price, dict):
                value = price.get("usOdds")
                if value is not None:
                    return int(value)
    return None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
