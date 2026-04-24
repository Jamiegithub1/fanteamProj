from decimal import Decimal
from types import SimpleNamespace

from app.sources.betmgm import BetMGMAdapter


def test_betmgm_parser_extracts_fixture_market_options() -> None:
    payload = {
        "items": [
            {
                "id": [{"full": "fixture-1"}],
                "name": [{"text": "Lakers at Celtics"}],
                "markets": [
                    {
                        "name": [{"text": "Player Points"}],
                        "value": 27.5,
                        "options": [
                            {
                                "name": [{"text": "Over LeBron James"}],
                                "price": [{"usOdds": -110}],
                            },
                            {
                                "name": [{"text": "Under LeBron James"}],
                                "price": [{"usOdds": -120}],
                            },
                        ],
                    }
                ],
            }
        ]
    }

    odds = BetMGMAdapter().parse_fixtures(payload)

    assert len(odds) == 2
    assert odds[0].bookmaker_key == "betmgm"
    assert odds[0].event_id == "fixture-1"
    assert odds[0].market_key == "points"
    assert odds[0].line == Decimal("27.5")
    assert odds[0].player_name == "LeBron James"


def test_betmgm_fetch_degrades_without_access_credentials() -> None:
    settings = SimpleNamespace(
        betmgm_enabled=True,
        betmgm_access_id="",
        betmgm_access_token="",
        betmgm_sport_id="",
        betmgm_base_url="https://api.test",
        betmgm_country="US",
        betmgm_timeout_seconds=5,
        betmgm_refresh_interval_seconds=900,
    )

    result = BetMGMAdapter(settings=settings).fetch()

    assert result.status == "degraded"
    assert "ACCESS_ID" in result.message
