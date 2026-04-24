from decimal import Decimal
from types import SimpleNamespace

import httpx

from app.sources.draftkings import DraftKingsAdapter


def test_draftkings_parser_extracts_player_props() -> None:
    payload = {
        "eventGroup": {
            "events": [
                {
                    "eventId": 1001,
                    "teamName1": "Boston Celtics",
                    "teamName2": "Los Angeles Lakers",
                }
            ],
            "offerCategories": [
                {
                    "name": "Player Props",
                    "offerSubcategoryDescriptors": [
                        {
                            "name": "Points",
                            "offerSubcategory": {
                                "offers": [
                                    [
                                        {
                                            "eventId": 1001,
                                            "label": "Player Points",
                                            "line": "27.5",
                                            "outcomes": [
                                                {
                                                    "label": "Over",
                                                    "participant": "Jayson Tatum",
                                                    "oddsAmerican": -110,
                                                },
                                                {
                                                    "label": "Under",
                                                    "participant": "Jayson Tatum",
                                                    "oddsAmerican": -120,
                                                },
                                            ],
                                        }
                                    ]
                                ]
                            },
                        },
                        {
                            "name": "Blocks",
                            "offerSubcategory": {
                                "offers": [
                                    [
                                        {
                                            "eventId": 1001,
                                            "label": "Player Blocks",
                                            "outcomes": [
                                                {
                                                    "label": "Over 1.5",
                                                    "participant": "Anthony Davis",
                                                    "line": "1.5",
                                                    "oddsDecimal": "1.80",
                                                }
                                            ],
                                        }
                                    ]
                                ]
                            },
                        },
                    ],
                }
            ],
        }
    }

    odds = DraftKingsAdapter().parse_payload(payload)

    assert len(odds) == 3
    assert {odd.market_key for odd in odds} == {"points", "blocks"}
    assert odds[0].player_name == "Jayson Tatum"
    assert odds[0].line == Decimal("27.5")
    assert odds[0].event_id == "1001"
    assert odds[0].event_name == "Boston Celtics @ Los Angeles Lakers"


def test_draftkings_fetch_is_degraded_when_disabled() -> None:
    settings = SimpleNamespace(
        draftkings_enabled=False,
        draftkings_base_url="https://draftkings.test",
        draftkings_region="US-NJ-SB",
        draftkings_timeout_seconds=5,
        draftkings_refresh_interval_seconds=900,
    )

    result = DraftKingsAdapter(settings=settings).fetch()

    assert result.status == "degraded"
    assert "disabled" in result.message


def test_draftkings_fetch_handles_blocked_lightweight_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    settings = SimpleNamespace(
        draftkings_enabled=True,
        draftkings_base_url="https://draftkings.test",
        draftkings_region="US-NJ-SB",
        draftkings_timeout_seconds=5,
        draftkings_refresh_interval_seconds=900,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    result = DraftKingsAdapter(settings=settings, client=client).fetch()

    assert result.status == "degraded"
    assert "HTTP 403" in result.message
