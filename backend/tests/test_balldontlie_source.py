from decimal import Decimal
from types import SimpleNamespace

from app.sources.balldontlie import BallDontLieAdapter


def test_balldontlie_parser_maps_multiple_vendor_props_to_source_odds() -> None:
    payload = {
        "data": [
            {
                "game_id": 18447073,
                "player": {"first_name": "LeBron", "last_name": "James"},
                "vendor": "fanduel",
                "prop_type": "points",
                "line_value": "27.5",
                "market": {"type": "over_under", "over_odds": -112, "under_odds": -108},
            },
            {
                "game_id": 18447073,
                "player": {"first_name": "Nikola", "last_name": "Jokic"},
                "vendor": "caesars",
                "prop_type": "triple_double",
                "line_value": "1",
                "market": {"type": "milestone", "odds": 750},
            },
        ]
    }

    odds = BallDontLieAdapter().parse_player_props(payload)

    assert len(odds) == 3
    assert odds[0].bookmaker_key == "fanduel"
    assert odds[0].market_key == "points"
    assert odds[0].side == "over"
    assert odds[0].line == Decimal("27.5")
    assert odds[1].side == "under"
    assert odds[2].bookmaker_key == "caesars"
    assert odds[2].market_key == "triple_double"
    assert odds[2].side == "yes"


def test_balldontlie_fetch_degrades_without_api_key() -> None:
    settings = SimpleNamespace(
        balldontlie_enabled=True,
        balldontlie_api_key="",
        balldontlie_base_url="https://api.test",
        balldontlie_timeout_seconds=5,
        balldontlie_refresh_interval_seconds=900,
    )

    result = BallDontLieAdapter(settings=settings).fetch()

    assert result.status == "degraded"
    assert "API_KEY" in result.message
