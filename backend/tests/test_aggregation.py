from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.aggregation import refresh_aggregated_odds
from app.models import AggregatedOdd, Base, Bookmaker, OddsMarket, Player, RawOdd


def test_refresh_aggregated_odds_removes_vig_and_writes_consensus() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    collected_at = datetime.now(UTC)

    with Session(engine) as session:
        player = Player(name="Jayson Tatum", external_id="test:jayson-tatum")
        market = OddsMarket(
            key="points",
            name="Points",
            stat_key="points",
            fanteam_scoring_weight=Decimal("1.000"),
        )
        book_a = Bookmaker(key="book_a", name="Book A")
        book_b = Bookmaker(key="book_b", name="Book B")
        session.add_all([player, market, book_a, book_b])
        session.flush()
        session.add_all(
            [
                RawOdd(
                    bookmaker_id=book_a.id,
                    market_id=market.id,
                    player_id=player.id,
                    line=Decimal("24.5"),
                    side="over",
                    american_odds=-110,
                    implied_probability=Decimal("0.523810"),
                    collected_at=collected_at,
                ),
                RawOdd(
                    bookmaker_id=book_a.id,
                    market_id=market.id,
                    player_id=player.id,
                    line=Decimal("24.5"),
                    side="under",
                    american_odds=-110,
                    implied_probability=Decimal("0.523810"),
                    collected_at=collected_at,
                ),
                RawOdd(
                    bookmaker_id=book_b.id,
                    market_id=market.id,
                    player_id=player.id,
                    line=Decimal("24.5"),
                    side="over",
                    american_odds=-125,
                    implied_probability=Decimal("0.555556"),
                    collected_at=collected_at,
                ),
                RawOdd(
                    bookmaker_id=book_b.id,
                    market_id=market.id,
                    player_id=player.id,
                    line=Decimal("24.5"),
                    side="under",
                    american_odds=105,
                    implied_probability=Decimal("0.487805"),
                    collected_at=collected_at,
                ),
            ]
        )

        summary = refresh_aggregated_odds(session)
        session.commit()

        aggregated = session.scalar(select(AggregatedOdd))

    assert summary.groups_seen == 1
    assert summary.rows_written == 1
    assert aggregated is not None
    assert aggregated.source_count == 2
    assert aggregated.over_probability == Decimal("0.5162")
    assert aggregated.under_probability == Decimal("0.4838")
    assert aggregated.expected_value == Decimal("24.5163")
    assert aggregated.confidence_score is not None
