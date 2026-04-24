from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.aggregation import refresh_aggregated_odds
from app.models import Base, Bookmaker, OddsMarket, Player, Projection, RawOdd
from app.projections import refresh_projections


def test_raw_odds_to_projection_pipeline() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    collected_at = datetime.now(UTC)

    with Session(engine) as session:
        player = Player(name="Nikola Jokic", external_id="test:nikola-jokic")
        market = OddsMarket(
            key="points",
            name="Points",
            stat_key="points",
            fanteam_scoring_weight=Decimal("1.000"),
        )
        bookmaker = Bookmaker(key="playzilla", name="Playzilla")
        session.add_all([player, market, bookmaker])
        session.flush()
        session.add_all(
            [
                RawOdd(
                    bookmaker_id=bookmaker.id,
                    market_id=market.id,
                    player_id=player.id,
                    line=Decimal("25.5"),
                    side="over",
                    implied_probability=Decimal("0.540000"),
                    collected_at=collected_at,
                ),
                RawOdd(
                    bookmaker_id=bookmaker.id,
                    market_id=market.id,
                    player_id=player.id,
                    line=Decimal("25.5"),
                    side="under",
                    implied_probability=Decimal("0.500000"),
                    collected_at=collected_at,
                ),
            ]
        )

        aggregation = refresh_aggregated_odds(session)
        projection_summary = refresh_projections(session)
        session.commit()

        projection = session.scalar(select(Projection))

    assert aggregation.rows_written == 1
    assert projection_summary.rows_written == 1
    assert projection is not None
    assert projection.points == Decimal("25.5192")
    assert projection.fantasy_points == Decimal("25.5192")
