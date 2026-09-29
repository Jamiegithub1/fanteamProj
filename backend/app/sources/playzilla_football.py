"""
Playzilla – Football World Cup 2026 adapter.

Inherits Altenar WSDK discovery from PlayzillaAdapter and overrides payload
fetching / parsing for football.  The same api_base_url and integration_key
are used; only sport_id and champ_id differ.

Event-level markets (1X2, Total Goals, BTTS, Clean Sheet) are stored with
the team or match name as the "player_name" so the existing source_runner
pipeline can persist them unchanged.

Player-level markets (Anytime Scorer, First Scorer, …) are stored with the
actual player name from Altenar's childMarkets.childName field.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import urljoin

from app.config import Settings, get_settings
from app.sources.base import OddSide, SourceOdd, SourceResult
from app.sources.football_markets import (
    ALTENAR_ANYTIME_SCORER_TYPE_IDS,
    ALTENAR_AWAY_WIN_SELECTION_TYPE_ID,
    ALTENAR_BTTS_TYPE_ID,
    ALTENAR_CARDS_TYPE_IDS,
    ALTENAR_CLEAN_SHEET_AWAY_TYPE_ID,
    ALTENAR_CLEAN_SHEET_HOME_TYPE_ID,
    ALTENAR_COMBINED_GOALSCORER_TYPE_ID,
    ALTENAR_DRAW_SELECTION_TYPE_ID,
    ALTENAR_FIRST_SCORER_TYPE_IDS,
    ALTENAR_GOALSCORER_ANYTIME_SELECTION_ID,
    ALTENAR_GOALSCORER_FIRST_SELECTION_ID,
    ALTENAR_GOALSCORER_LAST_SELECTION_ID,
    ALTENAR_HOME_WIN_SELECTION_TYPE_ID,
    ALTENAR_MATCH_RESULT_TYPE_ID,
    ALTENAR_OVER_SELECTION_TYPE_ID,
    ALTENAR_PLAYER_ASSISTS_TYPE_IDS,
    ALTENAR_SHOTS_ON_TARGET_TYPE_IDS,
    ALTENAR_TEAM_GOALS_AWAY_TYPE_ID,
    ALTENAR_TEAM_GOALS_HOME_TYPE_ID,
    ALTENAR_TOTAL_GOALS_TYPE_ID,
    ALTENAR_UNDER_SELECTION_TYPE_ID,
    identify_football_market,
)
from app.sources.playzilla import (
    PlayzillaAdapter,
    PlayzillaDiscovery,
    _clean_player_name,
    _dedupe_source_odds,
    _first_decimal,
    _first_int,
    _first_text,
    _flatten_odd_ids,
    _parse_altenar_datetime,
    _side_from_altenar_odd,
    _sv_decimal,
)

# Altenar football sport ID on the Playzilla/BiaHosted instance.
# GetAllSports confirmed: Football id=66, Basketball id=67.
PLAYZILLA_FOOTBALL_SPORT_ID = 66

# Name fragments used to auto-discover the WM championship when
# PLAYZILLA_WM_CHAMP_ID is not set via ENV.
WM_NAME_FRAGMENTS = (
    "world cup",
    "wm 2026",
    "fifa world cup",
    "weltmeisterschaft",
    "coupe du monde",
    "copa del mundo",
)

# Altenar widget endpoints used during championship discovery
_CHAMP_BY_SPORT_PATH = "widget/GetChampsByCountry"
_EVENTS_BY_CHAMP_PATH = "widget/GetEventsByChamp"
_EVENT_DETAILS_PATH = "widget/GetEventDetails"


class PlayzillaFootballWMAdapter(PlayzillaAdapter):
    """Fetches FIFA World Cup 2026 odds from Playzilla (Altenar WSDK)."""

    source_key = "playzilla_wm"
    source_name = "Playzilla – Football WM"

    def __init__(self, settings: Settings | None = None, client=None) -> None:
        super().__init__(settings, client)
        self.refresh_interval_seconds = self.settings.playzilla_wm_refresh_interval_seconds

    # ------------------------------------------------------------------
    # Public interface (overrides parent)
    # ------------------------------------------------------------------

    def fetch(self) -> SourceResult:
        started = perf_counter()
        if not self.settings.playzilla_wm_enabled:
            return SourceResult(
                source_key=self.source_key,
                status="degraded",
                latency_ms=0,
                message="Football WM source is disabled by PLAYZILLA_WM_ENABLED.",
            )
        try:
            discovery = self.discover()
            champ_id = self._resolve_champ_id(discovery)
            if champ_id is None:
                return SourceResult(
                    source_key=self.source_key,
                    odds=(),
                    status="degraded",
                    latency_ms=int((perf_counter() - started) * 1000),
                    message=(
                        "No WM championship ID found. "
                        "Set PLAYZILLA_WM_CHAMP_ID in your .env or wait until "
                        "Playzilla publishes the tournament."
                    ),
                    metadata=self._metadata(discovery),
                )
            payloads = self._fetch_football_payloads(discovery, champ_id)
            odds = tuple(odd for payload in payloads for odd in self._parse_football_payload(payload))
            latency_ms = int((perf_counter() - started) * 1000)
            if not payloads:
                return SourceResult(
                    source_key=self.source_key,
                    odds=(),
                    status="degraded",
                    latency_ms=latency_ms,
                    message=f"No events returned for WM champ_id={champ_id}.",
                    metadata=self._metadata(discovery),
                )
            if not odds:
                return SourceResult(
                    source_key=self.source_key,
                    odds=(),
                    status="degraded",
                    latency_ms=latency_ms,
                    message="WM events found but no parseable odds in payloads.",
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

    # ------------------------------------------------------------------
    # Championship ID resolution
    # ------------------------------------------------------------------

    def _resolve_champ_id(self, discovery: PlayzillaDiscovery) -> int | None:
        """Return configured champ_id or auto-discover from Altenar."""
        if self.settings.playzilla_wm_champ_id:
            return self.settings.playzilla_wm_champ_id
        return self._discover_wm_champ_id(discovery)

    def _discover_wm_champ_id(self, discovery: PlayzillaDiscovery) -> int | None:
        """
        Auto-discover WM championship ID by fetching all football competitions
        and searching for World Cup name fragments.  Returns None when the
        tournament is not yet listed.
        """
        if not discovery.api_base_url or not discovery.integration_key:
            return None
        params = self._altenar_params(discovery.integration_key)
        try:
            response = self.client.get(
                urljoin(discovery.api_base_url, _CHAMP_BY_SPORT_PATH),
                params={**params, "sportId": PLAYZILLA_FOOTBALL_SPORT_ID},
                headers={"Accept": "application/json", "Referer": discovery.resolved_url},
            )
            if response.status_code not in {200}:
                return None
            data = response.json()
        except Exception:
            return None

        return self._find_wm_champ_id_in_data(data)

    def _find_wm_champ_id_in_data(self, data: Any) -> int | None:
        """Walk the championship list JSON looking for a WM-named entry."""
        if isinstance(data, dict):
            for value in data.values():
                result = self._find_wm_champ_id_in_data(value)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = _first_text(item, ("name", "champName", "competitionName", "caption"))
                    champ_id = _first_int(item, ("id", "champId", "competitionId"))
                    if name and champ_id and self._is_wm_name(name):
                        return champ_id
                    result = self._find_wm_champ_id_in_data(item)
                    if result is not None:
                        return result
        return None

    @staticmethod
    def _is_wm_name(name: str) -> bool:
        lower = name.lower()
        return any(fragment in lower for fragment in WM_NAME_FRAGMENTS)

    # ------------------------------------------------------------------
    # Payload fetching (football version)
    # ------------------------------------------------------------------

    def _fetch_football_payloads(
        self, discovery: PlayzillaDiscovery, champ_id: int
    ) -> tuple[dict[str, Any], ...]:
        if not discovery.api_base_url or not discovery.integration_key:
            return ()

        params = self._altenar_params(discovery.integration_key)
        response = self.client.get(
            urljoin(discovery.api_base_url, _EVENTS_BY_CHAMP_PATH),
            params={
                **params,
                "sportId": PLAYZILLA_FOOTBALL_SPORT_ID,
                "champIds": champ_id,
            },
            headers={"Accept": "application/json", "Referer": discovery.resolved_url},
        )
        if response.status_code in {401, 403, 555}:
            return ()
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return ()

        event_meta: dict[int, dict[str, Any]] = {
            event["id"]: event
            for event in data.get("events", [])
            if isinstance(event, dict) and event.get("id")
        }

        payloads: list[dict[str, Any]] = []
        # Fetch up to 32 WM matches (max group-stage + knockout)
        for event_id in list(event_meta)[:32]:
            detail_response = self.client.get(
                urljoin(discovery.api_base_url, _EVENT_DETAILS_PATH),
                params={
                    **params,
                    "sportId": PLAYZILLA_FOOTBALL_SPORT_ID,
                    "eventId": event_id,
                },
                headers={"Accept": "application/json", "Referer": discovery.resolved_url},
            )
            if detail_response.status_code in {401, 403, 555}:
                continue
            detail_response.raise_for_status()
            detail_data = detail_response.json()
            if isinstance(detail_data, dict):
                meta = event_meta[event_id]
                for date_key in ("startDate", "startTime", "kickOffDate", "date"):
                    if date_key in meta and "_startDate" not in detail_data:
                        detail_data["_startDate"] = meta[date_key]
                payloads.append(detail_data)
        return tuple(payloads)

    # ------------------------------------------------------------------
    # Payload parsing (football version)
    # ------------------------------------------------------------------

    def _parse_football_payload(self, payload: dict[str, Any]) -> tuple[SourceOdd, ...]:
        collected_at = datetime.now(UTC)
        event_id = str(payload.get("id")) if payload.get("id") is not None else None
        event_name = _first_text(payload, ("name", "eventName", "caption"))
        event_starts_at = _parse_altenar_datetime(
            payload.get("_startDate")
            or payload.get("startDate")
            or payload.get("startTime")
            or payload.get("kickOffDate")
        )

        home_team, away_team = _parse_football_teams(event_name)

        # Build competitorId → team_name map from the event's competitors array
        competitor_id_to_team: dict[int, str] = {}
        for comp in payload.get("competitors", []):
            if isinstance(comp, dict) and comp.get("id") and comp.get("name"):
                raw = comp["name"].strip().upper()
                clean = "".join(c if (c.isalpha() or c in " -") else "" for c in raw).strip()
                competitor_id_to_team[int(comp["id"])] = clean or raw

        # Build odds lookup (same structure as NBA: list of odd dicts with id)
        odds_by_id: dict[int, dict[str, Any]] = {}
        raw_odds = payload.get("odds", [])
        if isinstance(raw_odds, list):
            for odd in raw_odds:
                if isinstance(odd, dict) and odd.get("id") is not None:
                    odds_by_id[int(odd["id"])] = odd
        elif isinstance(raw_odds, dict):
            for k, odd in raw_odds.items():
                if isinstance(odd, dict):
                    odds_by_id[int(k)] = odd

        source_odds: list[SourceOdd] = []

        # --- event-level markets ------------------------------------------
        markets = payload.get("markets") or []
        if not isinstance(markets, list):
            markets = []

        for market in markets:
            if not isinstance(market, dict):
                continue
            source_odds.extend(
                self._parse_event_market(
                    market,
                    odds_by_id,
                    home_team,
                    away_team,
                    event_id,
                    event_name,
                    event_starts_at,
                    collected_at,
                )
            )

        # --- player-level markets (childMarkets) ---------------------------
        if payload.get("childMarkets"):
            source_odds.extend(
                self._parse_player_markets(
                    payload,
                    odds_by_id,
                    home_team,
                    away_team,
                    competitor_id_to_team,
                    event_id,
                    event_name,
                    event_starts_at,
                    collected_at,
                )
            )

        return tuple(_dedupe_source_odds(source_odds))

    # ------------------------------------------------------------------
    # Event-level market parsing
    # ------------------------------------------------------------------

    def _parse_event_market(
        self,
        market: dict[str, Any],
        odds_by_id: dict[int, dict[str, Any]],
        home_team: str,
        away_team: str,
        event_id: str | None,
        event_name: str,
        event_starts_at: datetime | None,
        collected_at: datetime,
    ) -> list[SourceOdd]:
        type_id = _first_int(market, ("typeId", "type_id"))
        market_name = _first_text(market, ("name", "marketName", "caption"))

        # Collect selection-like objects: may be inline or referenced by ID
        selections = self._collect_selections(market, odds_by_id)

        # Match Result (1X2)
        if type_id == ALTENAR_MATCH_RESULT_TYPE_ID or _is_match_result(market_name):
            return self._parse_match_result(
                selections, home_team, away_team, event_id, event_name, event_starts_at, collected_at
            )

        # Total Goals (Over/Under)
        if type_id == ALTENAR_TOTAL_GOALS_TYPE_ID or _is_total_goals(market_name):
            return self._parse_over_under(
                selections,
                "wm_total_goals",
                "WM Total Goals",
                f"{home_team} vs {away_team}",
                event_id, event_name, event_starts_at, collected_at,
            )

        # Home Team Goals
        if type_id == ALTENAR_TEAM_GOALS_HOME_TYPE_ID:
            return self._parse_over_under(
                selections,
                "wm_team_goals",
                "WM Team Goals",
                home_team,
                event_id, event_name, event_starts_at, collected_at,
            )

        # Away Team Goals
        if type_id == ALTENAR_TEAM_GOALS_AWAY_TYPE_ID:
            return self._parse_over_under(
                selections,
                "wm_team_goals",
                "WM Team Goals",
                away_team,
                event_id, event_name, event_starts_at, collected_at,
            )

        # Both Teams to Score
        if type_id == ALTENAR_BTTS_TYPE_ID or _is_btts(market_name):
            return self._parse_yes_no(
                selections,
                "wm_btts",
                "WM Both Teams to Score",
                f"{home_team} vs {away_team}",
                event_id, event_name, event_starts_at, collected_at,
            )

        # Clean Sheet — detect home/away by typeId first, then team name in text
        cs_team = _detect_clean_sheet_team(type_id, market_name, home_team, away_team)
        if cs_team is not None:
            return self._parse_yes_no(
                selections, "wm_clean_sheet", "WM Clean Sheet",
                cs_team, event_id, event_name, event_starts_at, collected_at,
            )

        # Generic text-based fallback for any market matching football aliases
        market_def = identify_football_market(market_name)
        if market_def:
            if market_def.key == "wm_total_goals":
                return self._parse_over_under(
                    selections, market_def.key, market_def.name,
                    f"{home_team} vs {away_team}",
                    event_id, event_name, event_starts_at, collected_at,
                )
            if market_def.key == "wm_btts":
                return self._parse_yes_no(
                    selections, market_def.key, market_def.name,
                    f"{home_team} vs {away_team}",
                    event_id, event_name, event_starts_at, collected_at,
                )
            if market_def.key == "wm_clean_sheet":
                cs_team = _detect_clean_sheet_team(type_id, market_name, home_team, away_team)
                if cs_team:
                    return self._parse_yes_no(
                        selections, market_def.key, market_def.name,
                        cs_team, event_id, event_name, event_starts_at, collected_at,
                    )

        return []

    def _collect_selections(
        self, market: dict[str, Any], odds_by_id: dict[int, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Collect selection-like objects for a market.
        Altenar can embed them as 'odds', 'selections', or reference them by ID.
        """
        for key in ("odds", "selections", "outcomes", "prices"):
            value = market.get(key)
            if isinstance(value, list) and value:
                return [item for item in value if isinstance(item, dict)]

        # Some Altenar formats store IDs in oddIds / selectionIds / desktopOddIds
        for id_key in ("oddIds", "selectionIds", "desktopOddIds", "oddid"):
            ids = market.get(id_key)
            if ids:
                flat = _flatten_odd_ids(ids)
                result = [odds_by_id[i] for i in flat if i in odds_by_id]
                if result:
                    return result

        return []

    # ------------------------------------------------------------------
    # Parsers for specific market shapes
    # ------------------------------------------------------------------

    def _parse_match_result(
        self,
        selections: list[dict[str, Any]],
        home_team: str,
        away_team: str,
        event_id: str | None,
        event_name: str,
        event_starts_at: datetime | None,
        collected_at: datetime,
    ) -> list[SourceOdd]:
        odds: list[SourceOdd] = []
        for sel in selections:
            if sel.get("oddStatus") not in {None, 0}:
                continue
            type_id = _first_int(sel, ("typeId", "selectionTypeId"))
            price = _first_decimal(sel, ("price", "decimalOdds", "decimal", "odds", "coefficient"))
            if price is None:
                continue

            if type_id == ALTENAR_HOME_WIN_SELECTION_TYPE_ID or _is_home_selection(sel, home_team):
                odds.append(self._make_yes_odd(
                    player_name=home_team,
                    market_key="wm_team_win",
                    market_name="WM Team Win",
                    decimal_odds=price,
                    event_id=event_id, event_name=event_name,
                    event_starts_at=event_starts_at, collected_at=collected_at,
                ))
            elif type_id == ALTENAR_DRAW_SELECTION_TYPE_ID or _is_draw_selection(sel):
                odds.append(self._make_yes_odd(
                    player_name=f"{home_team} vs {away_team}",
                    market_key="wm_match_draw",
                    market_name="WM Match Draw",
                    decimal_odds=price,
                    event_id=event_id, event_name=event_name,
                    event_starts_at=event_starts_at, collected_at=collected_at,
                ))
            elif type_id == ALTENAR_AWAY_WIN_SELECTION_TYPE_ID or _is_away_selection(sel, away_team):
                odds.append(self._make_yes_odd(
                    player_name=away_team,
                    market_key="wm_team_win",
                    market_name="WM Team Win",
                    decimal_odds=price,
                    event_id=event_id, event_name=event_name,
                    event_starts_at=event_starts_at, collected_at=collected_at,
                ))
        return odds

    def _parse_over_under(
        self,
        selections: list[dict[str, Any]],
        market_key: str,
        market_name: str,
        player_name: str,
        event_id: str | None,
        event_name: str,
        event_starts_at: datetime | None,
        collected_at: datetime,
    ) -> list[SourceOdd]:
        odds: list[SourceOdd] = []
        for sel in selections:
            if sel.get("oddStatus") not in {None, 0}:
                continue
            side = _football_side_from_selection(sel)
            if not side:
                continue
            price = _first_decimal(sel, ("price", "decimalOdds", "decimal", "odds", "coefficient"))
            if price is None:
                continue
            line = _sv_decimal(sel.get("sv")) or _line_from_name(
                _first_text(sel, ("name", "selectionName", "caption"))
            )
            odds.append(SourceOdd(
                source_key=self.source_key,
                bookmaker_key=self.source_key,
                bookmaker_name=self.source_name,
                player_name=player_name,
                market_key=market_key,
                market_name=market_name,
                side=side,
                line=line,
                decimal_odds=price,
                event_id=event_id,
                event_name=event_name,
                event_starts_at=event_starts_at,
                collected_at=collected_at,
            ))
        return odds

    def _parse_yes_no(
        self,
        selections: list[dict[str, Any]],
        market_key: str,
        market_name: str,
        player_name: str,
        event_id: str | None,
        event_name: str,
        event_starts_at: datetime | None,
        collected_at: datetime,
    ) -> list[SourceOdd]:
        odds: list[SourceOdd] = []
        for sel in selections:
            if sel.get("oddStatus") not in {None, 0}:
                continue
            side = _yes_no_side_from_selection(sel)
            if not side:
                continue
            price = _first_decimal(sel, ("price", "decimalOdds", "decimal", "odds", "coefficient"))
            if price is None:
                continue
            odds.append(SourceOdd(
                source_key=self.source_key,
                bookmaker_key=self.source_key,
                bookmaker_name=self.source_name,
                player_name=player_name,
                market_key=market_key,
                market_name=market_name,
                side=side,
                line=None,
                decimal_odds=price,
                event_id=event_id,
                event_name=event_name,
                event_starts_at=event_starts_at,
                collected_at=collected_at,
            ))
        return odds

    def _make_yes_odd(
        self,
        player_name: str,
        market_key: str,
        market_name: str,
        decimal_odds: Decimal,
        event_id: str | None,
        event_name: str,
        event_starts_at: datetime | None,
        collected_at: datetime,
    ) -> SourceOdd:
        return SourceOdd(
            source_key=self.source_key,
            bookmaker_key=self.source_key,
            bookmaker_name=self.source_name,
            player_name=player_name,
            market_key=market_key,
            market_name=market_name,
            side="yes",
            line=None,
            decimal_odds=decimal_odds,
            event_id=event_id,
            event_name=event_name,
            event_starts_at=event_starts_at,
            collected_at=collected_at,
        )

    # ------------------------------------------------------------------
    # Player-level markets (childMarkets)
    # ------------------------------------------------------------------

    def _parse_player_markets(
        self,
        payload: dict[str, Any],
        odds_by_id: dict[int, dict[str, Any]],
        home_team: str,
        away_team: str,
        competitor_id_to_team: dict[int, str],
        event_id: str | None,
        event_name: str,
        event_starts_at: datetime | None,
        collected_at: datetime,
    ) -> list[SourceOdd]:
        odds: list[SourceOdd] = []
        for child_market in payload.get("childMarkets", []):
            if not isinstance(child_market, dict):
                continue
            market_key, market_name = self._resolve_player_market(child_market)
            if not market_key:
                continue

            player_name = _clean_player_name(
                _first_text(child_market, ("childName", "shortName", "name"))
            )
            if not player_name:
                continue

            # Determine the player's team via competitorId from the event's
            # competitors array; fall back to parsing the name "(ABBR)" suffix.
            raw_competitor_id = child_market.get("competitorId")
            player_team: str | None = None
            if raw_competitor_id is not None:
                player_team = competitor_id_to_team.get(int(raw_competitor_id))
            if not player_team:
                player_team = _extract_team_from_player_name(
                    _first_text(child_market, ("name",)), home_team, away_team
                )

            child_type_id = _first_int(child_market, ("typeId",))
            line = _sv_decimal(child_market.get("sv"))

            for odd_id in _flatten_odd_ids(
                child_market.get("desktopOddIds") or child_market.get("mobileOddIds") or []
            ):
                odd = odds_by_id.get(odd_id)
                if not odd or odd.get("oddStatus") not in {None, 0}:
                    continue
                price = _first_decimal(odd, ("price",))
                if price is None:
                    continue

                # Combined Goalscorer market: per-odd typeId determines variant
                if child_type_id == ALTENAR_COMBINED_GOALSCORER_TYPE_ID:
                    sel_type = _first_int(odd, ("typeId",))
                    if sel_type == ALTENAR_GOALSCORER_LAST_SELECTION_ID:
                        continue  # skip last-scorer
                    if sel_type == ALTENAR_GOALSCORER_FIRST_SELECTION_ID:
                        eff_key, eff_name = "wm_first_scorer", "WM First Goalscorer"
                    elif sel_type == ALTENAR_GOALSCORER_ANYTIME_SELECTION_ID:
                        eff_key, eff_name = "wm_anytime_scorer", "WM Anytime Scorer"
                    else:
                        eff_key, eff_name = market_key, market_name
                else:
                    eff_key, eff_name = market_key, market_name

                # Player goalscorer markets are binary yes/no
                side: OddSide = _side_from_altenar_odd(odd) or "yes"
                # Overline markets (shots, assists) use over/under
                if eff_key in {"wm_shots_on_target", "wm_player_assists"}:
                    side = _side_from_altenar_odd(odd) or "over"

                odds.append(SourceOdd(
                    source_key=self.source_key,
                    bookmaker_key=self.source_key,
                    bookmaker_name=self.source_name,
                    player_name=player_name,
                    market_key=eff_key,
                    market_name=eff_name,
                    side=side,
                    line=line,
                    decimal_odds=price,
                    event_id=event_id,
                    event_name=event_name,
                    event_starts_at=event_starts_at,
                    collected_at=collected_at,
                    team_name=player_team,
                ))
        return odds

    def _resolve_player_market(
        self, child_market: dict[str, Any]
    ) -> tuple[str | None, str]:
        type_id = _first_int(child_market, ("typeId",))
        market_name = _first_text(child_market, ("name", "marketName", "caption"))

        if type_id in ALTENAR_ANYTIME_SCORER_TYPE_IDS:
            return "wm_anytime_scorer", "WM Anytime Scorer"
        if type_id in ALTENAR_FIRST_SCORER_TYPE_IDS:
            return "wm_first_scorer", "WM First Goalscorer"
        if type_id == ALTENAR_COMBINED_GOALSCORER_TYPE_ID:
            # Variant resolved per-odd in _parse_player_markets; placeholder here
            return "wm_anytime_scorer", "WM Anytime Scorer"
        if type_id in ALTENAR_SHOTS_ON_TARGET_TYPE_IDS:
            return "wm_shots_on_target", "WM Shots on Target"
        if type_id in ALTENAR_PLAYER_ASSISTS_TYPE_IDS:
            return "wm_player_assists", "WM Player Assists"
        if type_id in ALTENAR_CARDS_TYPE_IDS:
            return "wm_cards", "WM Cards"

        # Text fallback
        if market_name:
            market_def = identify_football_market(market_name)
            if market_def:
                return market_def.key, market_def.name

        return None, ""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _parse_football_teams(event_name: str) -> tuple[str, str]:
    """
    Extract (home_team, away_team) from an Altenar football event name.

    Altenar football format is usually 'Home v Away' or 'Home vs Away'.
    Falls back to generic parsing when no separator is found.
    Returns ('UNKNOWN_HOME', 'UNKNOWN_AWAY') rather than crashing.
    """
    name = event_name.strip()
    for sep, home_idx, away_idx in (
        (" v ", 0, 1),
        (" vs ", 0, 1),
        (" vs. ", 0, 1),
        (" @ ", 1, 0),
    ):
        if sep in name:
            parts = name.split(sep, 1)
            home = _team_abbr(parts[home_idx])
            away = _team_abbr(parts[away_idx])
            return home, away
    return "UNKNOWN_HOME", "UNKNOWN_AWAY"


def _team_abbr(value: str) -> str:
    """Return clean team name (first token stripped of punctuation, upper-cased)."""
    word = value.strip()
    if not word:
        return "UNKNOWN"
    # Keep multi-word names (e.g. "South Korea") – take the full left part
    clean = "".join(c if (c.isalpha() or c in " -") else "" for c in word).strip()
    return clean.upper() if clean else word.upper()


def _football_side_from_selection(sel: dict[str, Any]) -> OddSide | None:
    type_id = _first_int(sel, ("typeId", "selectionTypeId"))
    if type_id == ALTENAR_OVER_SELECTION_TYPE_ID:
        return "over"
    if type_id == ALTENAR_UNDER_SELECTION_TYPE_ID:
        return "under"
    # Fallback: read name
    name = _first_text(sel, ("name", "selectionName", "caption")).lower()
    if name.startswith("over") or "over " in name:
        return "over"
    if name.startswith("under") or "under " in name:
        return "under"
    return None


def _yes_no_side_from_selection(sel: dict[str, Any]) -> OddSide | None:
    name = _first_text(sel, ("name", "selectionName", "caption")).lower().strip()
    if name in {"yes", "y", "gg"}:
        return "yes"
    if name in {"no", "n", "ng"}:
        return "no"
    type_id = _first_int(sel, ("typeId", "selectionTypeId"))
    # Many Altenar operators use typeId 2501=yes, 2502=no for yes/no
    if type_id == 2501:
        return "yes"
    if type_id == 2502:
        return "no"
    return None


def _line_from_name(name: str) -> Decimal | None:
    """Extract a numeric line from names like 'Over 2.5' → Decimal('2.5')."""
    match = re.search(r"\b(\d+(?:\.\d+)?)\b", name)
    if match:
        try:
            return Decimal(match.group(1))
        except (InvalidOperation, ValueError):
            pass
    return None


def _is_match_result(name: str) -> bool:
    n = name.lower()
    return any(tok in n for tok in ("match result", "1x2", "full time result", "result", "moneyline"))


def _is_total_goals(name: str) -> bool:
    n = name.lower()
    return any(tok in n for tok in ("total goals", "over under", "goals o/u", "match goals"))


def _is_btts(name: str) -> bool:
    n = name.lower()
    return any(tok in n for tok in ("both teams", "btts", "gg/ng", "gg ng"))


def _detect_clean_sheet_team(
    type_id: int | None,
    market_name: str,
    home_team: str,
    away_team: str,
) -> str | None:
    """
    Return the team name for a clean-sheet market, or None if not a clean sheet.

    Priority:
    1. typeId 31 = home clean sheet, typeId 32 = away clean sheet
    2. "home" / "away" keyword in market name
    3. Team name appearing at the start of market name (e.g. "Mexico clean sheet")
    """
    if type_id == ALTENAR_CLEAN_SHEET_HOME_TYPE_ID:
        return home_team
    if type_id == ALTENAR_CLEAN_SHEET_AWAY_TYPE_ID:
        return away_team

    n = market_name.lower()
    if "clean sheet" not in n:
        return None
    # Skip 1st/2nd-half variants — we only want full-match
    if "half" in n or "1st" in n or "2nd" in n:
        return None
    # Skip combined "or any clean sheet" markets
    if "or any" in n:
        return None

    if "home" in n:
        return home_team
    if "away" in n:
        return away_team

    # Check if the market name starts with the home or away team name
    name_lower = market_name.lower().strip()
    if name_lower.startswith(home_team.lower()):
        return home_team
    if name_lower.startswith(away_team.lower()):
        return away_team

    return None


def _extract_team_from_player_name(
    name: str,
    home_team: str,
    away_team: str,
) -> str | None:
    """
    Altenar names players as "Goalscorer - Erling Haaland (NOR)".
    If a 3-letter code in parentheses matches the start of home_team or away_team,
    return that team name.  Returns None when no match is found.
    """
    m = re.search(r"\(([A-Z]{2,4})\)\s*$", name.strip())
    if not m:
        return None
    code = m.group(1).upper()
    if home_team.upper().startswith(code[:3]) or code[:3] == home_team.upper()[:3]:
        return home_team
    if away_team.upper().startswith(code[:3]) or code[:3] == away_team.upper()[:3]:
        return away_team
    return None


def _is_home_selection(sel: dict[str, Any], home_team: str) -> bool:
    name = _first_text(sel, ("name", "selectionName")).lower()
    return name in {"1", "home", "h"} or home_team.lower() in name


def _is_draw_selection(sel: dict[str, Any]) -> bool:
    name = _first_text(sel, ("name", "selectionName")).lower()
    return name in {"x", "draw", "tie", "d"}


def _is_away_selection(sel: dict[str, Any], away_team: str) -> bool:
    name = _first_text(sel, ("name", "selectionName")).lower()
    return name in {"2", "away", "a"} or away_team.lower() in name
