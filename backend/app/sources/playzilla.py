from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import Settings, get_settings
from app.sources.base import OddSide, SourceOdd, SourceResult
from app.sources.markets import identify_market, normalize_text


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class PlayzillaDiscovery:
    resolved_url: str
    wsdk_url: str | None
    api_base_url: str | None
    integration_key: str | None


class PlayzillaAdapter:
    source_key = "playzilla"
    source_name = "Playzilla"
    requires_browser = False

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None) -> None:
        self.settings = settings or get_settings()
        self.refresh_interval_seconds = self.settings.playzilla_refresh_interval_seconds
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=self.settings.playzilla_timeout_seconds,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
        )

    def fetch(self) -> SourceResult:
        started = perf_counter()
        if not self.settings.playzilla_enabled:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="Playzilla source is disabled by PLAYZILLA_ENABLED.",
            )
        try:
            discovery = self.discover()
            payloads = self.fetch_payloads(discovery)
            odds = tuple(odd for payload in payloads for odd in self.parse_payload(payload))
            latency_ms = int((perf_counter() - started) * 1000)
            if not payloads:
                return SourceResult(
                    source_key=self.source_key,
                    odds=(),
                    status="degraded",
                    latency_ms=latency_ms,
                    message="Playzilla uses an Altenar WSDK validation token; no lightweight unauthenticated odds payload was available.",
                    metadata=self._metadata(discovery),
                )
            if not odds:
                return SourceResult(
                    source_key=self.source_key,
                    odds=(),
                    status="degraded",
                    latency_ms=latency_ms,
                    message="Playzilla discovery succeeded, but no NBA player prop odds were present in the lightweight payload.",
                    metadata=self._metadata(discovery),
                )
            return SourceResult(
                source_key=self.source_key,
                odds=odds,
                status="success",
                latency_ms=latency_ms,
                metadata=self._metadata(discovery),
            )
        except Exception as exc:
            return SourceResult(
                source_key=self.source_key,
                status="failed",
                latency_ms=int((perf_counter() - started) * 1000),
                message=str(exc),
            )

    def discover(self) -> PlayzillaDiscovery:
        response = self.client.get(self.settings.playzilla_base_url)
        response.raise_for_status()
        html = response.text
        resolved_url = str(response.url)
        wsdk_url = self._find_wsdk_url(html, resolved_url)
        integration_key = self._find_integration_key(html)
        if not wsdk_url or not integration_key:
            script_wsdk_url, script_integration_key = self._inspect_app_scripts(html, resolved_url)
            wsdk_url = wsdk_url or script_wsdk_url
            integration_key = integration_key or script_integration_key

        api_base_url = None

        if wsdk_url:
            wsdk_response = self.client.get(wsdk_url, headers={"Accept": "application/javascript,*/*;q=0.8"})
            wsdk_response.raise_for_status()
            api_base_url = self._find_altenar_web_origin(wsdk_response.text)

        return PlayzillaDiscovery(
            resolved_url=resolved_url,
            wsdk_url=wsdk_url,
            api_base_url=api_base_url,
            integration_key=integration_key,
        )

    def fetch_payloads(self, discovery: PlayzillaDiscovery) -> tuple[dict[str, Any], ...]:
        if not discovery.api_base_url or not discovery.integration_key:
            return ()

        params = {
            "ge3F6uCFVIZiI": discovery.integration_key,
            "culture": "en-GB",
            "timezoneOffset": "0",
            "deviceType": "1",
            "numFormat": "en-GB",
            "integration": discovery.integration_key,
            "sportTypeId": "12",
        }
        response = self.client.get(
            urljoin(discovery.api_base_url, "Widget/GetSportInfo"),
            params=params,
            headers={"Accept": "application/json", "Referer": discovery.resolved_url},
        )
        if response.status_code in {401, 403, 555}:
            return ()
        response.raise_for_status()
        data = response.json()
        return (data,) if isinstance(data, dict) else ()

    def parse_payload(self, payload: dict[str, Any]) -> tuple[SourceOdd, ...]:
        collected_at = datetime.now(UTC)
        odds: list[SourceOdd] = []
        for market in _iter_market_nodes(payload):
            market_name = _first_text(market, ("name", "marketName", "caption", "displayName"))
            market_def = identify_market(market_name)
            if not market_def:
                continue

            event_id = _first_text(market, ("eventId", "eventID", "matchId", "fixtureId", "id"))
            event_name = _first_text(market, ("eventName", "matchName", "fixtureName"))
            default_line = _first_decimal(market, ("line", "spov", "specialOddValue", "points"))
            selections = _extract_selections(market)
            for selection in selections:
                side = _side_from_selection(selection)
                if not side:
                    continue
                player_name = _player_name(selection, market)
                if not player_name:
                    continue
                decimal_odds = _first_decimal(selection, ("decimalOdds", "decimal", "price", "odds", "coefficient"))
                american_odds = _first_int(selection, ("americanOdds", "american", "usOdds"))
                if decimal_odds is None and american_odds is None:
                    continue
                odds.append(
                    SourceOdd(
                        source_key=self.source_key,
                        player_name=player_name,
                        market_key=market_def.key,
                        market_name=market_def.name,
                        side=side,
                        line=_first_decimal(selection, ("line", "spov", "specialOddValue", "points")) or default_line,
                        american_odds=american_odds,
                        decimal_odds=decimal_odds,
                        event_id=event_id,
                        event_name=event_name,
                        collected_at=collected_at,
                    )
                )
        return tuple(odds)

    def _find_wsdk_url(self, html: str, base_url: str) -> str | None:
        match = re.search(r"https://[^\"']*altenarWSDK\.js", html)
        if match:
            return match.group(0)
        match = re.search(r"src=[\"']([^\"']*altenarWSDK\.js)[\"']", html)
        return urljoin(base_url, match.group(1)) if match else None

    def _find_altenar_web_origin(self, script: str) -> str | None:
        match = re.search(r'"web"\s*:\s*"(https://[^"]+/api/)"', script)
        return match.group(1) if match else None

    def _inspect_app_scripts(self, html: str, base_url: str) -> tuple[str | None, str | None]:
        wsdk_url = None
        integration_key = None
        for script_url in re.findall(r"src=[\"']([^\"']+\.js)[\"']", html):
            if "runtime" in script_url or "polyfills" in script_url or "vendor" in script_url:
                continue
            try:
                response = self.client.get(urljoin(base_url, script_url), headers={"Accept": "application/javascript"})
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            wsdk_url = wsdk_url or self._find_wsdk_url(response.text, str(response.url))
            integration_key = integration_key or self._find_integration_key(response.text)
            if wsdk_url and integration_key:
                break
        return wsdk_url, integration_key

    def _find_integration_key(self, text: str) -> str | None:
        patterns = (
            r"integration(?:Name|Key)?[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_-]{3,80})[\"']",
            r"altenarWSDK\.(?:init|set)\(\{[^}]*integration[\"']?\s*:\s*[\"']([A-Za-z0-9_-]{3,80})[\"']",
            r"skinName[\"']?\s*[:=]\s*[\"']([A-Za-z0-9_-]{3,80})[\"']",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _metadata(self, discovery: PlayzillaDiscovery) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "resolved_url": discovery.resolved_url,
                "wsdk_url": discovery.wsdk_url,
                "api_base_url": discovery.api_base_url,
                "integration_key": discovery.integration_key,
            }.items()
            if value
        }


def _iter_market_nodes(value: Any) -> tuple[dict[str, Any], ...]:
    found: list[dict[str, Any]] = []

    def visit(node: Any, event_context: dict[str, Any] | None = None) -> None:
        if isinstance(node, dict):
            next_context = event_context
            if _first_text(node, ("eventId", "eventID", "matchId", "fixtureId")) or _first_text(
                node, ("eventName", "matchName", "fixtureName")
            ):
                next_context = node
            if _looks_like_market(node):
                market = dict(node)
                if next_context:
                    for key in ("eventId", "eventID", "matchId", "fixtureId", "eventName", "matchName", "fixtureName"):
                        if key not in market and key in next_context:
                            market[key] = next_context[key]
                found.append(market)
            for child in node.values():
                visit(child, next_context)
        elif isinstance(node, list):
            for child in node:
                visit(child, event_context)

    visit(value)
    return tuple(found)


def _looks_like_market(node: dict[str, Any]) -> bool:
    name = _first_text(node, ("name", "marketName", "caption", "displayName"))
    if not name or not identify_market(name):
        return False
    return bool(_extract_selections(node))


def _extract_selections(node: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    for key in ("selections", "odds", "outcomes", "prices"):
        value = node.get(key)
        if isinstance(value, list):
            return tuple(item for item in value if isinstance(item, dict))
    return ()


def _first_text(node: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float, Decimal)):
            return str(value)
    return ""


def _first_decimal(node: dict[str, Any], keys: tuple[str, ...]) -> Decimal | None:
    for key in keys:
        value = node.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            decimal = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        return decimal
    return None


def _first_int(node: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = node.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _side_from_selection(selection: dict[str, Any]) -> OddSide | None:
    text = normalize_text(
        " ".join(
            _first_text(selection, keys)
            for keys in (("name", "selectionName", "caption", "displayName"), ("typeName", "side"))
        )
    )
    if text.startswith("over") or " over" in text:
        return "over"
    if text.startswith("under") or " under" in text:
        return "under"
    if text in {"yes", "y"} or " yes" in text:
        return "yes"
    if text in {"no", "n"} or " no" in text:
        return "no"

    selection_type = _first_int(selection, ("selectionTypeId", "typeId"))
    if selection_type == 12:
        return "over"
    if selection_type == 13:
        return "under"
    return None


def _player_name(selection: dict[str, Any], market: dict[str, Any]) -> str:
    for node in (selection, market):
        for key in ("playerName", "participantName", "competitorName", "name2"):
            value = _first_text(node, (key,))
            if value:
                return _clean_player_name(value)

    selection_name = _first_text(selection, ("name", "selectionName", "caption", "displayName"))
    market_name = _first_text(market, ("name", "marketName", "caption", "displayName"))
    cleaned = _clean_player_name(selection_name)
    for token in ("over", "under", "yes", "no"):
        cleaned = re.sub(rf"\b{token}\b", "", cleaned, flags=re.IGNORECASE)
    for alias in (market_name,):
        if alias:
            cleaned = cleaned.replace(alias, "")
    return " ".join(cleaned.split())


def _clean_player_name(value: str) -> str:
    cleaned = re.sub(r"\b(over|under|yes|no)\b", "", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", "", cleaned)
    return " ".join(cleaned.replace("-", " ").split())
