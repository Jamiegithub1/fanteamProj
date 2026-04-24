from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import AggregatedOdd, Base, OddsMarket, Player, Projection
from app.projections import refresh_projections


def test_refresh_projections_calculates_fanteam_points() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        player = Player(name="Jayson Tatum", external_id="test:jayson-tatum")
        markets = [
            OddsMarket(key="points", name="Points", stat_key="points", fanteam_scoring_weight=Decimal("1.000")),
            OddsMarket(
                key="threes_made",
                name="3PT Made",
                stat_key="threes_made",
                fanteam_scoring_weight=Decimal("0.500"),
            ),
            OddsMarket(
                key="rebounds", name="Rebounds", stat_key="rebounds", fanteam_scoring_weight=Decimal("1.250")
            ),
            OddsMarket(key="assists", name="Assists", stat_key="assists", fanteam_scoring_weight=Decimal("1.500")),
            OddsMarket(
                key="turnovers", name="Turnovers", stat_key="turnovers", fanteam_scoring_weight=Decimal("-0.500")
            ),
            OddsMarket(
                key="double_double",
                name="Double-Double",
                stat_key="double_double_probability",
                fanteam_scoring_weight=Decimal("1.500"),
            ),
            OddsMarket(
                key="triple_double",
                name="Triple-Double",
                stat_key="triple_double_probability",
                fanteam_scoring_weight=Decimal("3.000"),
            ),
        ]
        session.add(player)
        session.add_all(markets)
        session.flush()
        market_by_key = {market.key: market for market in markets}
        session.add_all(
            [
                _aggregated(player.id, market_by_key["points"].id, Decimal("28.2")),
                _aggregated(player.id, market_by_key["threes_made"].id, Decimal("3.4")),
                _aggregated(player.id, market_by_key["rebounds"].id, Decimal("8.1")),
                _aggregated(player.id, market_by_key["assists"].id, Decimal("5.5")),
                _aggregated(player.id, market_by_key["turnovers"].id, Decimal("2.8")),
                _aggregated_probability(player.id, market_by_key["double_double"].id, Decimal("0.420000")),
                _aggregated_probability(player.id, market_by_key["triple_double"].id, Decimal("0.060000")),
            ]
        )

        summary = refresh_projections(session)
        session.commit()

        projection = session.scalar(select(Projection))

    assert summary.players_seen == 1
    assert summary.rows_written == 1
    assert projection is not None
    assert projection.points == Decimal("28.2000")
    assert projection.double_double_probability == Decimal("0.420000")
    assert projection.triple_double_probability == Decimal("0.060000")
    assert projection.fantasy_points == Decimal("47.6850")


def _aggregated(player_id: int, market_id: int, expected_value: Decimal) -> AggregatedOdd:
    return AggregatedOdd(
        player_id=player_id,
        market_id=market_id,
        line=expected_value,
        expected_value=expected_value,
        over_probability=Decimal("0.500000"),
        under_probability=Decimal("0.500000"),
        source_count=2,
        confidence_score=Decimal("0.4000"),
        calculated_at=datetime.now(UTC),
    )


def _aggregated_probability(player_id: int, market_id: int, probability: Decimal) -> AggregatedOdd:
    return AggregatedOdd(
        player_id=player_id,
        market_id=market_id,
        over_probability=probability,
        source_count=2,
        confidence_score=Decimal("0.4000"),
        calculated_at=datetime.now(UTC),
    )
