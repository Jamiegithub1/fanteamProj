from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, Bookmaker, RawOdd, SourceHealth
from app.source_runner import refresh_source
from app.sources.base import SourceOdd, SourceResult


@dataclass
class FakeAdapter:
    source_key: str = "playzilla"
    source_name: str = "Playzilla"
    requires_browser: bool = False
    refresh_interval_seconds: int = 900

    def fetch(self) -> SourceResult:
        return SourceResult(
            source_key=self.source_key,
            odds=(
                SourceOdd(
                    source_key=self.source_key,
                    player_name="Jayson Tatum",
                    market_key="points",
                    market_name="Points",
                    side="over",
                    line=Decimal("24.5"),
                    decimal_odds=Decimal("1.91"),
                    event_id="evt-1",
                    event_name="LAL @ BOS",
                    collected_at=datetime.now(UTC),
                ),
            ),
            status="success",
            latency_ms=25,
        )


def test_refresh_source_persists_bookmaker_market_raw_odd_and_health() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        result = refresh_source(session, FakeAdapter())
        session.commit()

        bookmaker = session.scalar(select(Bookmaker).where(Bookmaker.key == "playzilla"))
        raw_odd = session.scalar(select(RawOdd))
        health = session.scalar(select(SourceHealth))

    assert result.status == "success"
    assert bookmaker is not None
    assert bookmaker.requires_browser is False
    assert raw_odd is not None
    assert raw_odd.source_player_name == "Jayson Tatum"
    assert raw_odd.implied_probability == Decimal("0.523560")
    assert health is not None
    assert health.status == "success"
    assert health.consecutive_failures == 0
