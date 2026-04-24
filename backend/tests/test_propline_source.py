from decimal import Decimal
from types import SimpleNamespace

from app.sources.propline import PropLineAdapter


def test_propline_parser_maps_the_odds_api_style_payload() -> None:
    payload = {
        "id": "evt-1",
        "bookmakers": [
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {"name": "Over", "description": "LeBron James", "price": -115, "point": 27.5},
                            {"name": "Under", "description": "LeBron James", "price": -105, "point": 27.5},
                        ],
                    }
                ],
            },
            {
                "key": "pinnacle",
                "markets": [
                    {
                        "key": "player_rebounds",
                        "outcomes": [
                            {"name": "Over", "description": "Nikola Jokic", "price": 100, "point": 12.5},
                        ],
                    }
                ],
            },
        ],
    }

    odds = PropLineAdapter().parse_odds(payload)

    assert len(odds) == 3
    assert {odd.bookmaker_key for odd in odds} == {"fanduel", "pinnacle"}
    assert odds[0].market_key == "points"
    assert odds[0].line == Decimal("27.5")
    assert odds[2].market_key == "rebounds"


def test_propline_fetch_degrades_without_api_key() -> None:
    settings = SimpleNamespace(
        propline_enabled=True,
        propline_api_key="",
        propline_base_url="https://api.test",
        propline_timeout_seconds=5,
        propline_refresh_interval_seconds=900,
    )

    result = PropLineAdapter(settings=settings).fetch()

    assert result.status == "degraded"
    assert "API_KEY" in result.message
