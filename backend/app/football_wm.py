"""
Football WM – data retrieval and view building.

Reads aggregated_odds for wm_* market keys and builds structured team-level
and player-level views that the /football/wm API endpoint returns.

Design notes
------------
- Does NOT use the Projection model (NBA-specific).
- Reads directly from AggregatedOdd + Player + Game.
- For each team / player, only the NEXT upcoming game is used.
- Team entries (e.g. "Germany") are stored as Player records with
  external_id = "playzilla_wm:<slug>".
- Match entities (e.g. "Germany vs Scotland") are stored similarly.
- Odds probabilities are already vig-removed by the aggregation layer.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.models import AggregatedOdd, Game, OddsMarket, Player, Team
from app.sources.football_markets import PLAYER_LEVEL_MARKET_KEYS, TEAM_LEVEL_MARKET_KEYS

_DISPLAY_TZ = ZoneInfo("Europe/Berlin")

# Source key used by PlayzillaFootballWMAdapter
_WM_SOURCE_KEY = "playzilla_wm"

# Lines we expose as explicit probability fields in the team view
_GOAL_LINE_1_5 = Decimal("1.5")
_GOAL_LINE_2_5 = Decimal("2.5")
_GOAL_LINE_0_5 = Decimal("0.5")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_wm_overview(session: Session) -> dict[str, Any]:
    """
    Return {"teams": [...], "players": [...]} for the WM frontend tab.

    Returns empty lists (not an error) when no WM data has been fetched yet.
    """
    rows = _load_aggregated_wm_rows(session)
    if not rows:
        return {"teams": [], "players": []}

    game_map = _load_games(session, {r.game_id for r in rows if r.game_id})
    player_map = _load_players(session, {r.player_id for r in rows})
    market_map = _load_markets(session, {r.market_id for r in rows})
    team_id_map = _load_teams_by_id(session)

    # Group rows by (player_id, game_id) → list of AggregatedOdd
    groups: dict[tuple[int, int | None], list[AggregatedOdd]] = defaultdict(list)
    for row in rows:
        groups[(row.player_id, row.game_id)].append(row)

    # Find the next game per player
    next_game_ids = _next_game_per_player(
        {pid for pid, _ in groups},
        groups,
        game_map,
    )

    # Separate into team-level and player-level groups (by market_key)
    team_groups: dict[tuple[int, int | None], list[AggregatedOdd]] = {}
    player_groups: dict[tuple[int, int | None], list[AggregatedOdd]] = {}

    for (player_id, game_id), agg_odds in groups.items():
        if next_game_ids.get(player_id) != game_id:
            continue
        market_keys = {market_map.get(a.market_id, "") for a in agg_odds}
        if market_keys & TEAM_LEVEL_MARKET_KEYS:
            team_groups[(player_id, game_id)] = agg_odds
        elif market_keys & PLAYER_LEVEL_MARKET_KEYS:
            player_groups[(player_id, game_id)] = agg_odds

    # Build team and player rows
    team_rows = _build_team_rows(
        team_groups, player_map, game_map, market_map,
        # Pass ALL team-level groups for cross-match lookups (draw, loss prob)
        all_team_groups=team_groups,
        player_map_full=player_map,
    )
    player_rows = _build_player_rows(player_groups, player_map, game_map, market_map, team_groups, team_id_map)

    return {"teams": team_rows, "players": player_rows}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_aggregated_wm_rows(session: Session) -> list[AggregatedOdd]:
    """Load all aggregated odds whose players originate from playzilla_wm."""
    # Filter by external_id prefix so we only pick up football WM players
    wm_players = session.scalars(
        select(Player).where(Player.external_id.like(f"{_WM_SOURCE_KEY}:%"))
    ).all()
    if not wm_players:
        return []
    wm_player_ids = {p.id for p in wm_players}
    return session.scalars(
        select(AggregatedOdd).where(AggregatedOdd.player_id.in_(wm_player_ids))
    ).all()


def _load_games(session: Session, game_ids: set[int]) -> dict[int, Game]:
    if not game_ids:
        return {}
    games = session.scalars(select(Game).where(Game.id.in_(game_ids))).all()
    return {g.id: g for g in games}


def _load_players(session: Session, player_ids: set[int]) -> dict[int, Player]:
    if not player_ids:
        return {}
    players = session.scalars(select(Player).where(Player.id.in_(player_ids))).all()
    return {p.id: p for p in players}


def _load_markets(session: Session, market_ids: set[int]) -> dict[int, str]:
    """Returns {market_id: market_key}."""
    if not market_ids:
        return {}
    markets = session.scalars(select(OddsMarket).where(OddsMarket.id.in_(market_ids))).all()
    return {m.id: m.key for m in markets}


def _load_teams_by_id(session: Session) -> dict[int, str]:
    """Returns {team_id: team_name}."""
    teams = session.scalars(select(Team)).all()
    return {t.id: t.name for t in teams}


# ---------------------------------------------------------------------------
# Next-game logic
# ---------------------------------------------------------------------------

def _next_game_per_player(
    player_ids: set[int],
    groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    game_map: dict[int, Game],
) -> dict[int, int | None]:
    by_player: dict[int, list[int | None]] = defaultdict(list)
    for player_id, game_id in groups:
        by_player[player_id].append(game_id)

    now = datetime.now(UTC)
    next_game: dict[int, int | None] = {}
    for player_id in player_ids:
        game_ids = by_player.get(player_id, [])
        future = [
            gid for gid in game_ids
            if gid and gid in game_map and game_map[gid].starts_at > now
        ]
        if future:
            next_game[player_id] = min(future, key=lambda gid: game_map[gid].starts_at)
        elif game_ids:
            # No future game; fall back to the latest game we have
            real = [gid for gid in game_ids if gid and gid in game_map]
            if real:
                next_game[player_id] = max(real, key=lambda gid: game_map[gid].starts_at)
            else:
                next_game[player_id] = None
        else:
            next_game[player_id] = None
    return next_game


# ---------------------------------------------------------------------------
# Team row building
# ---------------------------------------------------------------------------

def _build_team_rows(
    team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    player_map: dict[int, Player],
    game_map: dict[int, Game],
    market_map: dict[int, str],
    all_team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    player_map_full: dict[int, Player],
) -> list[dict[str, Any]]:
    """
    Build one row per team per game.

    For draw / loss probabilities we look up the match entity ('{home} vs {away}')
    and the opponent's win entry from the same game.
    """
    # Index: game_id → {market_key → {player_id → AggregatedOdd list}}
    game_index = _build_game_index(all_team_groups, market_map)

    rows: list[dict[str, Any]] = []
    for (player_id, game_id), agg_odds in team_groups.items():
        player = player_map.get(player_id)
        if not player:
            continue

        market_vals = _extract_market_vals(agg_odds, market_map)

        # Skip match entities ('{home} vs {away}') – they are not teams
        if " VS " in player.name.upper() and "wm_team_win" not in market_vals:
            continue

        # Only process entries that have team-win odds (confirms this is a team)
        if "wm_team_win" not in market_vals:
            continue

        game = game_map.get(game_id) if game_id else None
        opponent = _find_opponent(game_id, player_id, all_team_groups, player_map_full, market_map)
        match_date = _game_date(game)
        match_name = _game_name(game, game_id, all_team_groups, player_map_full, market_map)

        win_prob = _yes_probability(market_vals.get("wm_team_win"))
        clean_sheet_prob = _yes_probability(market_vals.get("wm_clean_sheet"))

        # Draw and loss come from the match entity, not the team entity
        draw_prob = _get_draw_prob(game_id, game_index)
        loss_prob = _get_opponent_win_prob(player_id, game_id, all_team_groups, player_map_full, market_map)

        # Normalise win/draw/loss so they sum to ~1 (remove vig between them)
        win_prob, draw_prob, loss_prob = _normalise_1x2(win_prob, draw_prob, loss_prob)

        # Total goals from match entity
        total_goals_vals = _get_match_goals_vals(game_id, game_index)
        expected_goals = total_goals_vals.get("expected_goals")
        over_0_5 = total_goals_vals.get("over_0_5")
        over_1_5 = total_goals_vals.get("over_1_5")
        over_2_5 = total_goals_vals.get("over_2_5")
        btts_prob = total_goals_vals.get("btts")

        source_count = max((a.source_count for a in agg_odds), default=0)

        rows.append({
            "team_name": player.name,
            "opponent": opponent,
            "match_date": match_date,
            "match_name": match_name,
            "win_probability": _pct(win_prob),
            "draw_probability": _pct(draw_prob),
            "loss_probability": _pct(loss_prob),
            "clean_sheet_probability": _pct(clean_sheet_prob),
            "expected_goals_match": _round2(expected_goals),
            "over_0_5_probability": _pct(over_0_5),
            "over_1_5_probability": _pct(over_1_5),
            "over_2_5_probability": _pct(over_2_5),
            "btts_probability": _pct(btts_prob),
            "source_count": source_count,
            "game_id": game_id,
        })

    rows.sort(key=lambda r: (r["match_date"] or "", r["team_name"]))
    return rows


def _build_game_index(
    all_team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    market_map: dict[int, str],
) -> dict[int | None, dict[str, list[tuple[int, AggregatedOdd]]]]:
    """
    {game_id: {market_key: [(player_id, agg_odd), ...]}}
    Makes cross-team lookups fast.
    """
    index: dict[int | None, dict[str, list[tuple[int, AggregatedOdd]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (player_id, game_id), agg_odds in all_team_groups.items():
        for agg in agg_odds:
            key = market_map.get(agg.market_id, "")
            index[game_id][key].append((player_id, agg))
    return index


def _get_draw_prob(
    game_id: int | None,
    game_index: dict[int | None, dict[str, list[tuple[int, AggregatedOdd]]]],
) -> float | None:
    """Look up draw probability from the match entity for this game."""
    entries = game_index.get(game_id, {}).get("wm_match_draw", [])
    if not entries:
        return None
    _, agg = entries[0]
    return _yes_probability(agg)


def _get_opponent_win_prob(
    team_player_id: int,
    game_id: int | None,
    all_team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    player_map: dict[int, Player],
    market_map: dict[int, str],
) -> float | None:
    """Return the opponent team's win probability for this game."""
    for (pid, gid), agg_odds in all_team_groups.items():
        if gid != game_id or pid == team_player_id:
            continue
        vals = _extract_market_vals(agg_odds, market_map)
        if "wm_team_win" in vals:
            return _yes_probability(vals.get("wm_team_win"))
    return None


def _get_match_goals_vals(
    game_id: int | None,
    game_index: dict[int | None, dict[str, list[tuple[int, AggregatedOdd]]]],
) -> dict[str, float | None]:
    """Extract goal market probabilities from the match entity ('{home} vs {away}')."""
    result: dict[str, float | None] = {
        "expected_goals": None,
        "over_0_5": None,
        "over_1_5": None,
        "over_2_5": None,
        "btts": None,
    }
    goals_entries = game_index.get(game_id, {}).get("wm_total_goals", [])
    for _, agg in goals_entries:
        if agg.over_probability is None:
            continue
        p = float(agg.over_probability)
        line = agg.line
        if line == _GOAL_LINE_0_5:
            result["over_0_5"] = p
        elif line == _GOAL_LINE_1_5:
            result["over_1_5"] = p
        elif line == _GOAL_LINE_2_5:
            result["over_2_5"] = p
            # xG estimate from 2.5-line only (other lines give inflated values)
            if agg.expected_value is not None:
                result["expected_goals"] = float(agg.expected_value)

    btts_entries = game_index.get(game_id, {}).get("wm_btts", [])
    if btts_entries:
        _, agg = btts_entries[0]
        if agg.over_probability is not None:
            result["btts"] = float(agg.over_probability)

    # Approximate xG from over_2_5 if expected_goals not explicitly available
    if result["expected_goals"] is None and result["over_2_5"] is not None:
        # Rough Poisson-inversion: P(X>2.5) ≈ e^{-λ}(1 + λ + λ²/2) complement
        # For the range 0.3–0.8 of P(over 2.5), xG ≈ 2.5 + adjustment
        p = result["over_2_5"]
        result["expected_goals"] = round(2.5 + (p - 0.5) * 2.0, 2)

    return result


def _find_opponent(
    game_id: int | None,
    team_player_id: int,
    all_team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    player_map: dict[int, Player],
    market_map: dict[int, str],
) -> str:
    for (pid, gid), agg_odds in all_team_groups.items():
        if gid != game_id or pid == team_player_id:
            continue
        vals = _extract_market_vals(agg_odds, market_map)
        if "wm_team_win" in vals:
            p = player_map.get(pid)
            if p:
                return p.name
    return "TBD"


def _normalise_1x2(
    win: float | None,
    draw: float | None,
    loss: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Normalise 1X2 probabilities so they sum to 1 (remove residual vig)."""
    vals = [v for v in (win, draw, loss) if v is not None]
    if not vals:
        return win, draw, loss
    total = sum(vals)
    if total <= 0:
        return win, draw, loss
    w = win / total if win is not None else None
    d = draw / total if draw is not None else None
    l = loss / total if loss is not None else None
    return w, d, l


# ---------------------------------------------------------------------------
# Player row building
# ---------------------------------------------------------------------------

def _build_player_rows(
    player_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    player_map: dict[int, Player],
    game_map: dict[int, Game],
    market_map: dict[int, str],
    team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    team_id_map: dict[int, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (player_id, game_id), agg_odds in player_groups.items():
        player = player_map.get(player_id)
        if not player:
            continue
        game = game_map.get(game_id) if game_id else None
        market_vals = _extract_market_vals(agg_odds, market_map)

        anytime_prob = _yes_probability(market_vals.get("wm_anytime_scorer"))
        first_prob = _yes_probability(market_vals.get("wm_first_scorer"))
        shots_ev = _over_expected_value(market_vals.get("wm_shots_on_target"))
        assists_prob = _yes_probability(market_vals.get("wm_player_assists"))
        cards_prob = _yes_probability(market_vals.get("wm_cards"))

        # Team from player.team_id (set during source refresh via competitorId)
        team_name: str | None = team_id_map.get(player.team_id) if player.team_id else None

        # Derive opponent as the other team in the game
        teams_in_game = _teams_from_game(game_id, team_groups, player_map, market_map)
        if team_name and len(teams_in_game) == 2:
            opponent = teams_in_game[1] if teams_in_game[0] == team_name else teams_in_game[0]
        elif len(teams_in_game) >= 2:
            opponent = teams_in_game[1]
        else:
            opponent = "TBD"

        source_count = max((a.source_count for a in agg_odds), default=0)

        rows.append({
            "player_name": player.name,
            "team": team_name,
            "opponent": opponent,
            "match_date": _game_date(game),
            "anytime_scorer_probability": _pct(anytime_prob),
            "first_scorer_probability": _pct(first_prob),
            "shots_on_target_line": _round2(shots_ev),
            "assists_probability": _pct(assists_prob),
            "cards_probability": _pct(cards_prob),
            "source_count": source_count,
            "game_id": game_id,
        })

    rows.sort(
        key=lambda r: (
            -(r["anytime_scorer_probability"] or 0),
            r["match_date"] or "",
        )
    )
    return rows


def _teams_from_game(
    game_id: int | None,
    team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    player_map: dict[int, Player],
    market_map: dict[int, str],
) -> list[str]:
    """Return [home_name, away_name] for the two teams in this game."""
    names: list[str] = []
    for (pid, gid), agg_odds in team_groups.items():
        if gid != game_id:
            continue
        vals = _extract_market_vals(agg_odds, market_map)
        if "wm_team_win" in vals:
            p = player_map.get(pid)
            if p and p.name not in names:
                names.append(p.name)
    return names


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _extract_market_vals(
    agg_odds: list[AggregatedOdd],
    market_map: dict[int, str],
) -> dict[str, AggregatedOdd]:
    """Return {market_key: best_aggregated_odd} for a player/game group."""
    result: dict[str, AggregatedOdd] = {}
    for agg in agg_odds:
        key = market_map.get(agg.market_id, "")
        if not key:
            continue
        # Prefer the row with higher confidence_score when duplicates exist
        existing = result.get(key)
        if existing is None or (
            agg.confidence_score or 0) > (existing.confidence_score or 0
        ):
            result[key] = agg
    return result


def _yes_probability(agg: AggregatedOdd | None) -> float | None:
    if agg is None:
        return None
    if agg.over_probability is not None:
        return float(agg.over_probability)
    return None


def _over_expected_value(agg: AggregatedOdd | None) -> float | None:
    if agg is None:
        return None
    if agg.expected_value is not None:
        return float(agg.expected_value)
    return None


def _game_date(game: Game | None) -> str | None:
    if game is None:
        return None
    return game.starts_at.astimezone(_DISPLAY_TZ).date().isoformat()


def _game_name(
    game: Game | None,
    game_id: int | None,
    all_team_groups: dict[tuple[int, int | None], list[AggregatedOdd]],
    player_map: dict[int, Player],
    market_map: dict[int, str],
) -> str:
    """Return 'GERMANY vs SCOTLAND' style name from stored players."""
    names = _teams_from_game(game_id, all_team_groups, player_map, market_map)
    if len(names) >= 2:
        return f"{names[0]} vs {names[1]}"
    if len(names) == 1:
        return names[0]
    if game:
        return f"Game {game.id}"
    return ""


def _pct(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _round2(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)
