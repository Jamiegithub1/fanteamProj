from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx

from app.sources.playzilla import PlayzillaAdapter


def test_playzilla_parser_extracts_required_player_prop_markets() -> None:
    payload = {
        "events": [
            {
                "eventId": "evt-1",
                "eventName": "LAL @ BOS",
                "markets": [
                    {
                        "marketName": "Player Points",
                        "spov": "24.5",
                        "selections": [
                            {"playerName": "Jayson Tatum", "name": "Over", "decimalOdds": "1.91"},
                            {"playerName": "Jayson Tatum", "name": "Under", "decimalOdds": "1.91"},
                        ],
                    },
                    {
                        "marketName": "Player 3PT Made",
                        "line": "3.5",
                        "selections": [
                            {"playerName": "Jayson Tatum", "selectionTypeId": 12, "americanOdds": -115},
                            {"playerName": "Jayson Tatum", "selectionTypeId": 13, "americanOdds": -105},
                        ],
                    },
                    {
                        "marketName": "Triple Double",
                        "selections": [
                            {"playerName": "Nikola Jokic", "name": "Yes", "decimalOdds": "9.00"},
                            {"playerName": "Nikola Jokic", "name": "No", "decimalOdds": "1.04"},
                        ],
                    },
                ],
            }
        ]
    }

    odds = PlayzillaAdapter().parse_payload(payload)

    assert len(odds) == 6
    assert {odd.market_key for odd in odds} == {"points", "threes_made", "triple_double"}
    assert {odd.side for odd in odds} == {"over", "under", "yes", "no"}
    assert odds[0].player_name == "Jayson Tatum"
    assert odds[0].line == Decimal("24.5")
    assert odds[0].event_id == "evt-1"


def test_playzilla_discovery_reads_wsdk_from_app_bundle() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://playzilla.test/":
            return httpx.Response(200, html='<script src="/main.js"></script>', request=request)
        if str(request.url) == "https://playzilla.test/main.js":
            return httpx.Response(
                200,
                text='const x="https://cdn.test/altenarWSDK.js";const cfg={integration:"playzilla_demo"};',
                request=request,
            )
        if str(request.url) == "https://cdn.test/altenarWSDK.js":
            return httpx.Response(
                200,
                text='window.altenarWSDKOrigins={"web":"https://api.test/api/"};',
                request=request,
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    settings = SimpleNamespace(
        playzilla_enabled=True,
        playzilla_base_url="https://playzilla.test/",
        playzilla_timeout_seconds=5,
        playzilla_refresh_interval_seconds=900,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    discovery = PlayzillaAdapter(settings=settings, client=client).discover()

    assert discovery.wsdk_url == "https://cdn.test/altenarWSDK.js"
    assert discovery.api_base_url == "https://api.test/api/"
    assert discovery.integration_key == "playzilla_demo"


def test_playzilla_fetch_degrades_when_validation_blocks_lightweight_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://playzilla.test/":
            return httpx.Response(
                200,
                html=(
                    '<script src="https://cdn.test/altenarWSDK.js"></script>'
                    '<script>const cfg={integration:"playzilla_demo"};</script>'
                ),
                request=request,
            )
        if url == "https://cdn.test/altenarWSDK.js":
            return httpx.Response(
                200,
                text='window.altenarWSDKOrigins={"web":"https://api.test/api/"};',
                request=request,
            )
        if url.startswith("https://api.test/api/Widget/GetSportInfo"):
            return httpx.Response(401, request=request)
        raise AssertionError(f"Unexpected request: {request.url}")

    settings = SimpleNamespace(
        playzilla_enabled=True,
        playzilla_base_url="https://playzilla.test/",
        playzilla_timeout_seconds=5,
        playzilla_refresh_interval_seconds=900,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    result = PlayzillaAdapter(settings=settings, client=client).fetch()

    assert result.status == "degraded"
    assert result.odds == ()
    assert "validation token" in result.message


def test_playzilla_fetch_degrades_when_payload_has_no_player_props() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://playzilla.test/":
            return httpx.Response(
                200,
                html=(
                    '<script src="https://cdn.test/altenarWSDK.js"></script>'
                    '<script>const cfg={skinName:"playzilla"};</script>'
                ),
                request=request,
            )
        if url == "https://cdn.test/altenarWSDK.js":
            return httpx.Response(
                200,
                text='window.altenarWSDKOrigins={"web":"https://api.test/api/"};',
                request=request,
            )
        if url.startswith("https://api.test/api/Widget/GetSportInfo"):
            return httpx.Response(200, json={"sports": [{"id": 67, "typeId": 12}]}, request=request)
        raise AssertionError(f"Unexpected request: {request.url}")

    settings = SimpleNamespace(
        playzilla_enabled=True,
        playzilla_base_url="https://playzilla.test/",
        playzilla_timeout_seconds=5,
        playzilla_refresh_interval_seconds=900,
    )
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    result = PlayzillaAdapter(settings=settings, client=client).fetch()

    assert result.status == "degraded"
    assert result.odds == ()
    assert "no NBA player prop odds" in result.message
