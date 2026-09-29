from decimal import Decimal
from types import SimpleNamespace

import httpx

from app.sources.playzilla import PlayzillaAdapter, PLAYZILLA_NBA_SPORT_ID, PLAYZILLA_NBA_CHAMP_ID


def _make_altenar_payload(champ_id: int = PLAYZILLA_NBA_CHAMP_ID) -> dict:
    """Minimal valid Altenar GetEventDetails payload with NBA player props."""
    return {
        "id": 99,
        "name": "LAL @ BOS",
        "childMarkets": [
            {
                "typeId": 768,
                "childName": "Jayson Tatum",
                "shortName": "Jayson Tatum (BOS)",
                "sv": "27.5|sa:player:nba-1234|BOS",
                "desktopOddIds": [[1001, 1002]],
                "mobileOddIds": [[1001, 1002]],
            }
        ],
        "odds": [
            {"id": 1001, "typeId": 2501, "price": 1.91, "oddStatus": 0, "sv": "27.5"},
            {"id": 1002, "typeId": 2502, "price": 1.91, "oddStatus": 0, "sv": "27.5"},
        ],
    }


def _discovery_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url == "https://playzilla.test/":
        return httpx.Response(200, html='<script src="/main.js"></script>', request=request)
    if url == "https://playzilla.test/main.js":
        return httpx.Response(
            200,
            text='const cfg={altenarWidgetsConfig:{scriptUrl:"https://cdn.test/altenarWSDK.js",skinName:"playzilla_demo"}};',
            request=request,
        )
    if url == "https://cdn.test/altenarWSDK.js":
        return httpx.Response(
            200,
            text='window.origins={"web":"https://api.test/api/"};',
            request=request,
        )
    raise AssertionError(f"Unexpected request: {url}")


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


def test_playzilla_parser_handles_altenar_childmarkets_with_pipe_sv() -> None:
    """sv field like '27.5|sa:player:nba-1234|BOS' must parse the line correctly."""
    payload = _make_altenar_payload()
    odds = PlayzillaAdapter().parse_payload(payload)

    assert len(odds) == 2
    assert odds[0].player_name == "Jayson Tatum"
    assert odds[0].market_key == "points"
    assert odds[0].line == Decimal("27.5")
    assert {o.side for o in odds} == {"over", "under"}


def test_playzilla_discovery_reads_wsdk_from_app_bundle() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://playzilla.test/":
            return httpx.Response(200, html='<script src="/main.js"></script>', request=request)
        if str(request.url) == "https://playzilla.test/main.js":
            return httpx.Response(
                200,
                text='const x="https://cdn.test/altenarWSDK.js";const cfg={skinName:"playzilla_demo"};',
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


def test_playzilla_fetch_degrades_when_get_events_returns_auth_error() -> None:
    """401/403 from GetEventsByChamp must degrade gracefully, not crash."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://playzilla.test/":
            return httpx.Response(200, html='<script src="/main.js"></script>', request=request)
        if url == "https://playzilla.test/main.js":
            return httpx.Response(
                200,
                text='const x="https://cdn.test/altenarWSDK.js";const cfg={skinName:"demo"};',
                request=request,
            )
        if url == "https://cdn.test/altenarWSDK.js":
            return httpx.Response(200, text='{"web":"https://api.test/api/"}', request=request)
        if "GetEventsByChamp" in url:
            return httpx.Response(401, request=request)
        raise AssertionError(f"Unexpected request: {url}")

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


def test_playzilla_fetch_degrades_when_no_player_props_in_payload() -> None:
    """If events exist but contain no player prop childMarkets, status is degraded."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://playzilla.test/":
            return httpx.Response(200, html='<script src="/main.js"></script>', request=request)
        if url == "https://playzilla.test/main.js":
            return httpx.Response(
                200,
                text='const x="https://cdn.test/altenarWSDK.js";const cfg={skinName:"demo"};',
                request=request,
            )
        if url == "https://cdn.test/altenarWSDK.js":
            return httpx.Response(200, text='{"web":"https://api.test/api/"}', request=request)
        if "GetEventsByChamp" in url:
            return httpx.Response(200, json={"events": [{"id": 99}]}, request=request)
        if "GetEventDetails" in url:
            return httpx.Response(200, json={"id": 99, "childMarkets": [], "odds": []}, request=request)
        raise AssertionError(f"Unexpected request: {url}")

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
