from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

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


def refresh_projections(session: Session) -> ProjectionSummary:
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
        session.add(build_projection(session, player_slice, markets, calculated_at))
        rows_written += 1
    session.flush()
    return ProjectionSummary(players_seen=len({key.player_id for key in grouped}), rows_written=rows_written)


def build_projection(
    session: Session,
    player_slice: _ProjectionSlice,
    markets: list[tuple[AggregatedOdd, OddsMarket]],
    calculated_at: datetime,
) -> Projection:
    values: dict[str, Decimal | None] = {column: None for column in STAT_COLUMNS.values()}
    double_double_probability = None
    triple_double_probability = None
    fantasy_points = Decimal("0")
    confidence_values: list[Decimal] = []

    for aggregated, market in markets:
        if aggregated.confidence_score is not None:
            confidence_values.append(aggregated.confidence_score)
        if market.key in STAT_COLUMNS and aggregated.expected_value is not None:
            column = STAT_COLUMNS[market.key]
            value = aggregated.expected_value
            values[column] = value
            fantasy_points += value * market.fanteam_scoring_weight
        elif market.key == "double_double" and aggregated.over_probability is not None:
            double_double_probability = aggregated.over_probability
            fantasy_points += aggregated.over_probability * market.fanteam_scoring_weight
        elif market.key == "triple_double" and aggregated.over_probability is not None:
            triple_double_probability = aggregated.over_probability
            fantasy_points += aggregated.over_probability * market.fanteam_scoring_weight

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
        if None in player_game_ids:
            next_game[player_id] = None
            continue
        next_game[player_id] = min(player_game_ids, key=lambda game_id: games[game_id].starts_at if game_id in games else datetime.max)
    return next_game


def _projection_date(session: Session, game_id: int | None, fallback: date) -> date:
    if game_id is None:
        return fallback
    game = session.get(Game, game_id)
    if game is None:
        return fallback
    return game.starts_at.date()
