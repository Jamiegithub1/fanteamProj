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
        key="playzilla",
        name="Playzilla",
        role="mandatory_bookmaker",
        status="integrated_degraded",
        cost="free",
        access="lightweight Altenar WSDK HTTP discovery",
        coverage="NBA sportsbook source; current lightweight payload exposes sport metadata but no player props",
        server_load="low",
        reliability_notes="Mandatory source. It must stay isolated so Playzilla outages never crash the app.",
        implementation_notes="Integrated as first-party adapter with source_health and refresh_runs.",
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
        priority=3,
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
        priority=4,
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
        priority=5,
    ),
)
