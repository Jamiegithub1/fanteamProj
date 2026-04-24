from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AggregatedOdd, RawOdd
from app.odds_math import aggregate_values, expected_value_from_over_under, remove_vig


@dataclass(frozen=True)
class AggregationSummary:
    groups_seen: int
    rows_written: int


@dataclass(frozen=True)
class _RawSlice:
    player_id: int
    game_id: int | None
    market_id: int
    line: Decimal | None


def refresh_aggregated_odds(session: Session) -> AggregationSummary:
    raw_odds = session.scalars(select(RawOdd)).all()
    grouped: dict[_RawSlice, list[RawOdd]] = defaultdict(list)
    for odd in raw_odds:
        grouped[
            _RawSlice(
                player_id=odd.player_id,
                game_id=odd.game_id,
                market_id=odd.market_id,
                line=odd.line,
            )
        ].append(odd)

    session.execute(delete(AggregatedOdd))
    calculated_at = datetime.now(UTC)
    rows_written = 0
    for raw_slice, odds in grouped.items():
        aggregated = aggregate_raw_slice(raw_slice, odds, calculated_at)
        if aggregated is None:
            continue
        session.add(aggregated)
        rows_written += 1
    session.flush()
    return AggregationSummary(groups_seen=len(grouped), rows_written=rows_written)


def aggregate_raw_slice(
    raw_slice: _RawSlice,
    odds: list[RawOdd],
    calculated_at: datetime,
) -> AggregatedOdd | None:
    over_probabilities: list[Decimal] = []
    under_probabilities: list[Decimal] = []
    expected_values: list[Decimal] = []

    by_bookmaker: dict[int, list[RawOdd]] = defaultdict(list)
    for odd in odds:
        by_bookmaker[odd.bookmaker_id].append(odd)

    for bookmaker_odds in by_bookmaker.values():
        over = _latest_side(bookmaker_odds, "over") or _latest_side(bookmaker_odds, "yes")
        under = _latest_side(bookmaker_odds, "under") or _latest_side(bookmaker_odds, "no")
        if over and under and over.implied_probability is not None and under.implied_probability is not None:
            normalized_over, normalized_under = remove_vig(over.implied_probability, under.implied_probability)
            over_probabilities.append(normalized_over)
            under_probabilities.append(normalized_under)
            if raw_slice.line is not None and over.side == "over":
                expected_values.append(expected_value_from_over_under(raw_slice.line, normalized_over, normalized_under))
            continue
        single = over or under
        if single and single.implied_probability is not None:
            probability = single.implied_probability
            if single.side in {"over", "yes"}:
                over_probabilities.append(probability)
            else:
                under_probabilities.append(probability)

    if not over_probabilities and not under_probabilities:
        return None

    over_agg = aggregate_values(over_probabilities) if over_probabilities else None
    under_agg = aggregate_values(under_probabilities) if under_probabilities else None
    ev_agg = aggregate_values(expected_values) if expected_values else None
    confidence_inputs = [agg.confidence_score for agg in (over_agg, under_agg, ev_agg) if agg is not None]
    confidence = sum(confidence_inputs, Decimal(0)) / Decimal(len(confidence_inputs)) if confidence_inputs else None

    return AggregatedOdd(
        player_id=raw_slice.player_id,
        game_id=raw_slice.game_id,
        market_id=raw_slice.market_id,
        line=raw_slice.line,
        expected_value=ev_agg.mean if ev_agg else None,
        over_probability=over_agg.mean if over_agg else None,
        under_probability=under_agg.mean if under_agg else None,
        source_count=len(by_bookmaker),
        confidence_score=confidence,
        calculated_at=calculated_at,
    )


def _latest_side(odds: list[RawOdd], side: str) -> RawOdd | None:
    matching = [odd for odd in odds if odd.side == side]
    if not matching:
        return None
    return max(matching, key=lambda odd: odd.collected_at)
