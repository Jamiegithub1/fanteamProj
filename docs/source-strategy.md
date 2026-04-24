# Source Strategy

## Goal

The projection table needs complete NBA player prop coverage for:

- Points
- 3PT Made
- Rebounds
- Assists
- Steals
- Blocks
- Turnovers
- Double-Double
- Triple-Double

The system should prefer stable, low-load HTTP APIs over browser scraping.

## Ranked Sources

### 1. Playzilla

Role: mandatory bookmaker source.

Current status: integrated, but degraded for live player props. Playzilla redirects to a current SPA domain and loads an Altenar WSDK. Lightweight discovery works and source health is stored, but the currently accessible unauthenticated payload does not contain the required NBA player props.

Decision: keep enabled, isolated, and low-load. Do not add heavy browser scraping unless no better source path exists.

### 2. BALLDONTLIE Odds

Role: recommended next API source.

Why it fits: the documented NBA player props endpoint supports the exact core markets this project needs, including points, rebounds, assists, threes, steals, blocks, double-double, and triple-double. It also exposes multiple sportsbook vendors including DraftKings, FanDuel, Caesars, and others.

Decision: best next implementation target once an API key is configured through ENV.

### 3. PropLine

Role: recommended multi-book player-prop API.

Why it fits: free tier advertises 500 requests per day, 90-second refreshes, and multiple books in one response: Bovada, DraftKings, FanDuel, Pinnacle, plus PrizePicks-style projections. NBA markets include points, rebounds, assists, threes, PRA, and double-double.

Decision: strong second API source, especially for line shopping and redundancy.

### 4. SportsGameOdds

Role: broad aggregated odds API candidate.

Why it fits: NBA player props are available through a customizable REST API with filters by league, market, bookmaker, and player. It can reduce server load because one well-filtered request can replace several fragile book scrapers.

Decision: useful if free quota/key terms are acceptable.

### 5. SharpAPI

Role: fallback aggregated odds API.

Why it fits: permanent free tier, REST access, 12 requests per minute, two sportsbooks, major US sports. Its free tier may not provide enough book diversity by itself, but it is a useful stabilizer.

Decision: use only if the free books include the needed NBA player props.

## Skipped for Now

- Bet365 direct scraping: too heavy and fragile.
- Oddschecker direct scraping: likely HTML/browser-heavy for player props.
- FanDuel direct scraping: undocumented public API and often protected.
- DraftKings direct endpoint: adapter exists, but this server receives HTTP 403 from the public sportsbook edge.
- BetMGM/Caesars direct scraping: no stable free public player-prop access confirmed.

## Implementation Order

1. Keep Playzilla as required source and health signal.
2. Add BALLDONTLIE adapter as the first complete prop API source.
3. Add PropLine adapter as the second complete multi-book source.
4. Add SportsGameOdds if free quota is practical.
5. Add SharpAPI only as fallback or source-health redundancy.
