from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from math import exp, factorial
from zoneinfo import ZoneInfo

_DISPLAY_TZ = ZoneInfo("Europe/Berlin")

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AggregatedOdd, Game, OddsMarket, Projection
from app.odds_math import quantize


@dataclass(frozen=True)
class ProjectionSummary:
    players_seen: int
    rows_written: int


@dataclass(frozen=True)
class _ProjectionSlice:
    player_id: int
    game_id: int | None


STAT_COLUMNS = {
    "points": "points",
    "threes_made": "threes_made",
    "rebounds": "rebounds",
    "assists": "assists",
    "steals": "steals",
    "blocks": "blocks",
    "turnovers": "turnovers",
}


_DD_TD_STATS = ["points", "rebounds", "assists", "steals", "blocks"]


def _poisson_ge_10(lam: float) -> float:
    if lam <= 0:
        return 0.0
    cdf = sum(exp(-lam) * lam**k / factorial(k) for k in range(10))
    return max(0.0, 1.0 - cdf)


def _estimate_dd_td(values: dict[str, Decimal | None]) -> tuple[Decimal, Decimal]:
    probs = [
        _poisson_ge_10(float(values[s])) if values.get(s) is not None else 0.0
        for s in _DD_TD_STATS
    ]
    n = len(probs)
    dd_prob = td_prob = 0.0
    for mask in range(1 << n):
        p = 1.0
        count = 0
        for i in range(n):
            if mask & (1 << i):
                p *= probs[i]
                count += 1
            else:
                p *= 1.0 - probs[i]
        if count >= 2:
            dd_prob += p
        if count >= 3:
            td_prob += p
    return Decimal(str(round(dd_prob, 6))), Decimal(str(round(td_prob, 6)))


def refresh_projections(session: Session) -> ProjectionSummary:
    all_market_weights: dict[str, Decimal] = {
        m.key: m.fanteam_scoring_weight
        for m in session.scalars(select(OddsMarket)).all()
    }

    rows = session.execute(select(AggregatedOdd, OddsMarket).join(OddsMarket)).all()
    grouped: dict[_ProjectionSlice, list[tuple[AggregatedOdd, OddsMarket]]] = defaultdict(list)
    for aggregated, market in rows:
        grouped[_ProjectionSlice(player_id=aggregated.player_id, game_id=aggregated.game_id)].append((aggregated, market))

    next_game_by_player = _next_game_by_player(session, grouped.keys())
    session.execute(delete(Projection))
    calculated_at = datetime.now(UTC)
    rows_written = 0
    for player_slice, markets in grouped.items():
        if next_game_by_player.get(player_slice.player_id) != player_slice.game_id:
            continue
        session.add(build_projection(session, player_slice, markets, calculated_at, all_market_weights))
        rows_written += 1
    session.flush()
    return ProjectionSummary(players_seen=len({key.player_id for key in grouped}), rows_written=rows_written)


def build_projection(
    session: Session,
    player_slice: _ProjectionSlice,
    markets: list[tuple[AggregatedOdd, OddsMarket]],
    calculated_at: datetime,
    all_market_weights: dict[str, Decimal] | None = None,
) -> Projection:
    values: dict[str, Decimal | None] = {column: None for column in STAT_COLUMNS.values()}
    double_double_probability = None
    triple_double_probability = None
    fantasy_points = Decimal("0")
    confidence_values: list[Decimal] = []

    market_weight: dict[str, Decimal] = {}
    for aggregated, market in markets:
        market_weight[market.key] = market.fanteam_scoring_weight
        if aggregated.confidence_score is not None:
            confidence_values.append(aggregated.confidence_score)
        if market.key in STAT_COLUMNS and aggregated.expected_value is not None:
            column = STAT_COLUMNS[market.key]
            values[column] = aggregated.expected_value
        elif market.key == "double_double" and aggregated.over_probability is not None:
            double_double_probability = aggregated.over_probability
        elif market.key == "triple_double" and aggregated.over_probability is not None:
            triple_double_probability = aggregated.over_probability

    effective_weights = dict(all_market_weights or {})
    effective_weights.update(market_weight)

    if double_double_probability is None or triple_double_probability is None:
        est_dd, est_td = _estimate_dd_td(values)
        if double_double_probability is None:
            double_double_probability = est_dd
        if triple_double_probability is None:
            triple_double_probability = est_td

    for stat_key, value in values.items():
        if value is not None and stat_key in effective_weights:
            fantasy_points += value * effective_weights[stat_key]
    if double_double_probability is not None and "double_double" in effective_weights:
        fantasy_points += double_double_probability * effective_weights["double_double"]
    if triple_double_probability is not None and "triple_double" in effective_weights:
        fantasy_points += triple_double_probability * effective_weights["triple_double"]

    projection_date = _projection_date(session, player_slice.game_id, calculated_at.date())
    confidence = None
    if confidence_values:
        confidence = quantize(sum(confidence_values, Decimal("0")) / Decimal(len(confidence_values)))

    return Projection(
        player_id=player_slice.player_id,
        game_id=player_slice.game_id,
        projection_date=projection_date,
        points=values["points"],
        threes_made=values["threes_made"],
        rebounds=values["rebounds"],
        assists=values["assists"],
        steals=values["steals"],
        blocks=values["blocks"],
        turnovers=values["turnovers"],
        double_double_probability=double_double_probability,
        triple_double_probability=triple_double_probability,
        fantasy_points=quantize(fantasy_points),
        confidence_score=confidence,
        calculated_at=calculated_at,
    )


def _next_game_by_player(session: Session, slices: set[_ProjectionSlice] | list[_ProjectionSlice]) -> dict[int, int | None]:
    by_player: dict[int, list[int | None]] = defaultdict(list)
    for player_slice in slices:
        by_player[player_slice.player_id].append(player_slice.game_id)

    game_ids = {game_id for game_ids_for_player in by_player.values() for game_id in game_ids_for_player if game_id}
    games = {
        game.id: game
        for game in session.scalars(select(Game).where(Game.id.in_(game_ids))).all()
    } if game_ids else {}

    next_game: dict[int, int | None] = {}
    for player_id, player_game_ids in by_player.items():
        real_game_ids = [g for g in player_game_ids if g is not None]
        if not real_game_ids:
            next_game[player_id] = None
            continue
        next_game[player_id] = min(real_game_ids, key=lambda game_id: games[game_id].starts_at if game_id in games else datetime.max)
    return next_game


def _projection_date(session: Session, game_id: int | None, fallback: date) -> date:
    if game_id is None:
        return fallback
    game = session.get(Game, game_id)
    if game is None:
        return fallback
    return game.starts_at.astimezone(_DISPLAY_TZ).date()
