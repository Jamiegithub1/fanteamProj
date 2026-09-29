from dataclasses import dataclass


@dataclass(frozen=True)
class SourceCatalogEntry:
    key: str
    name: str
    role: str
    status: str
    cost: str
    access: str
    coverage: str
    server_load: str
    reliability_notes: str
    implementation_notes: str
    priority: int


SOURCE_CATALOG: tuple[SourceCatalogEntry, ...] = (
    SourceCatalogEntry(
        key="playzilla_wm",
        name="Playzilla – Football WM",
        role="mandatory_bookmaker",
        status="integrated_working",
        cost="free",
        access="Altenar WSDK HTTP discovery (same mechanism as playzilla NBA)",
        coverage=(
            "FIFA World Cup 2026: match result (1X2), total goals, BTTS, "
            "clean sheet, anytime goalscorer, first goalscorer; "
            "optional shots on target and assists where available"
        ),
        server_load="low",
        reliability_notes=(
            "Uses the same Playzilla/Altenar API as NBA. "
            "Championship ID is auto-discovered or set via PLAYZILLA_WM_CHAMP_ID. "
            "Returns degraded if the WM championship is not yet listed."
        ),
        implementation_notes=(
            "Set PLAYZILLA_WM_CHAMP_ID in .env if auto-discovery fails. "
            "Disable with PLAYZILLA_WM_ENABLED=false."
        ),
        priority=1,
    ),
    SourceCatalogEntry(
        key="playzilla",
        name="Playzilla",
        role="mandatory_bookmaker",
        status="integrated_working",
        cost="free",
        access="Altenar WSDK HTTP discovery (no API key required)",
        coverage="NBA player props: points, 3PM, rebounds, assists, steals, blocks, turnovers; ~1500 odds across all active NBA games",
        server_load="low",
        reliability_notes="Mandatory source. Fully working. Uses Altenar widget API via integration key discovered from JS bundle.",
        implementation_notes="Adapter auto-discovers api_base_url from altenarWSDK.js; integration key is 'playzilla'. No credentials required.",
        priority=1,
    ),
    SourceCatalogEntry(
        key="balldontlie",
        name="BALLDONTLIE Odds",
        role="aggregated_sportsbook_api",
        status="recommended_next",
        cost="free_api_key",
        access="official REST API with Authorization header",
        coverage="NBA player props including points, rebounds, assists, threes, steals, blocks, double-double, triple-double; vendors include DraftKings, FanDuel, Caesars, and others",
        server_load="low",
        reliability_notes="Best fit for complete stat coverage because it directly exposes the required NBA prop types.",
        implementation_notes="Add adapter after API key is configured through ENV.",
        priority=2,
    ),
    SourceCatalogEntry(
        key="betmgm",
        name="BetMGM",
        role="direct_us_sportsbook_api",
        status="direct_api_candidate",
        cost="free_public_docs",
        access="documented Sports API REST endpoints for sports, competitions, fixtures, markets, options, and prices",
        coverage="Large US sportsbook. API docs expose fixtures with markets/options/prices; NBA player-prop completeness must be verified from live fixture markets.",
        server_load="low",
        reliability_notes="Best direct US-book candidate because public technical docs exist. Needs conservative market filtering and source isolation.",
        implementation_notes="Implement discovery adapter: /offer/api/{country}/sports, competitions, fixtures with only displayed/open markets.",
        priority=3,
    ),
    SourceCatalogEntry(
        key="propline",
        name="PropLine",
        role="aggregated_player_props_api",
        status="recommended_next",
        cost="free_api_key_500_requests_per_day",
        access="REST API, the-odds-api compatible format",
        coverage="NBA player props from Bovada, DraftKings, FanDuel, Pinnacle plus PrizePicks-style projections; listed NBA markets include points, rebounds, assists, threes, PRA, double-double",
        server_load="low",
        reliability_notes="Good line-shopping source with multiple books in one response; free quota is useful for a local app.",
        implementation_notes="Use as multi-book source, with conservative polling to stay below 500/day.",
        priority=4,
    ),
    SourceCatalogEntry(
        key="sportsgameodds",
        name="SportsGameOdds",
        role="aggregated_odds_api",
        status="candidate",
        cost="free_trial_or_free_key",
        access="REST API with API key",
        coverage="NBA odds and player props across many bookmakers; supports filtering by league, market, bookmaker, and player",
        server_load="low",
        reliability_notes="Strong coverage candidate, but exact free-tier limits must be respected before enabling scheduler polling.",
        implementation_notes="Implement after confirming free quota and response shape with a real key.",
        priority=5,
    ),
    SourceCatalogEntry(
        key="sharpapi",
        name="SharpAPI",
        role="aggregated_odds_api",
        status="fallback_candidate",
        cost="free_api_key",
        access="REST API with API key",
        coverage="Free tier exposes two sportsbooks for major US sports with delayed odds",
        server_load="low",
        reliability_notes="Useful fallback, but free tier may not provide enough bookmaker diversity alone.",
        implementation_notes="Enable only if the free books include NBA player props needed by FanTeam scoring.",
        priority=6,
    ),
    SourceCatalogEntry(
        key="tipico",
        name="Tipico",
        role="direct_or_aggregated_bookmaker",
        status="research_candidate",
        cost="free_if_direct_access_is_stable",
        access="no official public developer API found; Tipico data is available through third-party odds APIs",
        coverage="Relevant sportsbook source, especially Germany/US footprint, but direct NBA player-prop endpoint is not confirmed.",
        server_load="unknown",
        reliability_notes="Do not browser-scrape first. Only implement if a stable lightweight HTTP path is confirmed.",
        implementation_notes="Prefer OpticOdds/OddsAPI-style aggregator path for Tipico unless direct JSON is found.",
        priority=7,
    ),
    SourceCatalogEntry(
        key="fanduel",
        name="FanDuel",
        role="major_us_bookmaker",
        status="aggregator_recommended",
        cost="free_via_limited_aggregator_or_paid_direct_data_provider",
        access="no official public developer API found; data available through aggregators",
        coverage="Top US book with strong NBA player props; must be sourced through BALLDONTLIE/PropLine/SportsGameOdds/Odds-API-style providers.",
        server_load="low_via_aggregator_high_if_scraped",
        reliability_notes="Avoid direct scraping unless a stable public JSON path is proven. It is too important to base on brittle browser scraping.",
        implementation_notes="Map FanDuel vendor rows from aggregated APIs into raw_odds with bookmaker key fanduel.",
        priority=8,
    ),
    SourceCatalogEntry(
        key="draftkings",
        name="DraftKings",
        role="major_us_bookmaker",
        status="adapter_exists_geo_blocked",
        cost="free_if_us_ip",
        access="undocumented sportsbook JSON endpoint; HTTP 403 from non-US IPs (geo-block)",
        coverage="Top US player-prop book. Adapter is implemented but geo-blocked from Hetzner EU servers.",
        server_load="low",
        reliability_notes="Keep disabled. Geo-block is enforced; would need a US proxy/VPN to work.",
        implementation_notes="Existing direct adapter remains available behind DRAFTKINGS_ENABLED if running from a US IP.",
        priority=9,
    ),
    SourceCatalogEntry(
        key="caesars",
        name="Caesars",
        role="major_us_bookmaker",
        status="aggregator_recommended",
        cost="free_via_limited_aggregator_or_paid_direct_data_provider",
        access="no public sportsbook odds API found for current player-prop data",
        coverage="Major US book with player props; best sourced through BALLDONTLIE or a broader odds aggregator.",
        server_load="low_via_aggregator",
        reliability_notes="Do not use old Caesars developer portal as sportsbook odds source; it is not a current public odds feed.",
        implementation_notes="Map Caesars vendor rows from aggregated APIs into raw_odds with bookmaker key caesars.",
        priority=10,
    ),
    SourceCatalogEntry(
        key="espnbet",
        name="ESPN BET",
        role="major_us_bookmaker",
        status="aggregator_only",
        cost="free_via_limited_aggregator_or_paid_direct_data_provider",
        access="no official public ESPN BET odds API found",
        coverage="Relevant US sportsbook, but direct endpoint stability is not guaranteed.",
        server_load="low_via_aggregator",
        reliability_notes="Treat direct ESPN BET endpoints as unsupported/internal; use aggregators if needed.",
        implementation_notes="Only add as vendor mapping from a stable aggregate API.",
        priority=11,
    ),
)
