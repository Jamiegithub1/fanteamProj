from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import Settings, get_settings
from app.sources.base import OddSide, SourceOdd, SourceResult
from app.sources.markets import identify_market, normalize_text
from app.sources.playzilla import USER_AGENT


NBA_EVENTGROUP_ID = 42648


class DraftKingsAdapter:
    source_key = "draftkings"
    source_name = "DraftKings"
    requires_browser = False

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.refresh_interval_seconds = self.settings.draftkings_refresh_interval_seconds
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=self.settings.draftkings_timeout_seconds,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://sportsbook.draftkings.com/leagues/basketball/nba",
            },
        )

    def fetch(self) -> SourceResult:
        started = perf_counter()
        if not self.settings.draftkings_enabled:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="DraftKings source is disabled by DRAFTKINGS_ENABLED.",
            )
        try:
            response = self.client.get(self._eventgroup_url())
            if response.status_code in {401, 403, 451}:
                return SourceResult(
                    source_key=self.source_key,
                    status="degraded",
                    latency_ms=int((perf_counter() - started) * 1000),
                    message=f"DraftKings lightweight endpoint returned HTTP {response.status_code}.",
                )
            response.raise_for_status()
            payload = response.json()
            odds = self.parse_payload(payload)
            if not odds:
                return SourceResult(
                    source_key=self.source_key,
                    status="degraded",
                    latency_ms=int((perf_counter() - started) * 1000),
                    message="DraftKings payload contained no supported NBA player prop odds.",
                )
            return SourceResult(
                source_key=self.source_key,
                odds=odds,
                status="success",
                latency_ms=int((perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return SourceResult(
                source_key=self.source_key,
                status="failed",
                latency_ms=int((perf_counter() - started) * 1000),
                message=str(exc),
            )

    def parse_payload(self, payload: dict[str, Any]) -> tuple[SourceOdd, ...]:
        event_group = payload.get("eventGroup", payload)
        events = {
            str(event.get("eventId") or event.get("id")): event
            for event in event_group.get("events", [])
            if isinstance(event, dict)
        }
        collected_at = datetime.now(UTC)
        odds: list[SourceOdd] = []

        for offer in _iter_offers(event_group):
            market_name = _market_name(offer)
            market_def = identify_market(market_name)
            if not market_def:
                continue
            event_id = str(offer.get("eventId") or offer.get("eventID") or "")
            event = events.get(event_id, {})
            event_name = _event_name(event)
            default_line = _decimal(offer.get("line"))
            for outcome in offer.get("outcomes", []):
                if not isinstance(outcome, dict):
                    continue
                side = _side(outcome)
                player_name = _player_name(outcome, offer)
                if not side or not player_name:
                    continue
                american_odds = _int(outcome.get("oddsAmerican") or outcome.get("americanOdds"))
                decimal_odds = _decimal(
                    outcome.get("oddsDecimal")
                    or outcome.get("decimalOdds")
                    or outcome.get("trueOdds")
                    or outcome.get("odds")
                )
                if american_odds is None and decimal_odds is None:
                    continue
                odds.append(
                    SourceOdd(
                        source_key=self.source_key,
                        player_name=player_name,
                        market_key=market_def.key,
                        market_name=market_def.name,
                        side=side,
                        line=_decimal(outcome.get("line")) or default_line,
                        american_odds=american_odds,
                        decimal_odds=decimal_odds,
                        event_id=event_id or None,
                        event_name=event_name,
                        collected_at=collected_at,
                    )
                )
        return tuple(odds)

    def _eventgroup_url(self) -> str:
        path = f"/sites/{self.settings.draftkings_region}/api/v5/eventgroups/{NBA_EVENTGROUP_ID}"
        return urljoin(self.settings.draftkings_base_url, path)


def _iter_offers(node: Any) -> tuple[dict[str, Any], ...]:
    offers: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("outcomes"), list):
                offers.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(node.get("offerCategories", node) if isinstance(node, dict) else node)
    return tuple(offers)


def _market_name(offer: dict[str, Any]) -> str:
    for key in ("label", "name", "marketName", "subcategoryName"):
        value = offer.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _event_name(event: dict[str, Any]) -> str | None:
    name = event.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    team_names = [event.get("teamName1"), event.get("teamName2")]
    if all(isinstance(team, str) and team for team in team_names):
        return f"{team_names[0]} @ {team_names[1]}"
    return None


def _side(outcome: dict[str, Any]) -> OddSide | None:
    text = normalize_text(str(outcome.get("label") or outcome.get("name") or outcome.get("outcomeType") or ""))
    if text.startswith("over"):
        return "over"
    if text.startswith("under"):
        return "under"
    if text in {"yes", "y"}:
        return "yes"
    if text in {"no", "n"}:
        return "no"
    return None


def _player_name(outcome: dict[str, Any], offer: dict[str, Any]) -> str:
    for key in ("participant", "participantName", "playerName", "label"):
        value = outcome.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_player(value)
    for key in ("playerName", "participantName"):
        value = offer.get(key)
        if isinstance(value, str) and value.strip():
            return _clean_player(value)
    return ""


def _clean_player(value: str) -> str:
    words = [word for word in value.replace("-", " ").split() if normalize_text(word) not in {"over", "under", "yes", "no"}]
    return " ".join(word for word in words if _decimal(word) is None)


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
