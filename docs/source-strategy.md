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

Decision: adapter is now implemented behind `BALLDONTLIE_ENABLED` and `BALLDONTLIE_API_KEY`. It maps vendor rows into real bookmaker keys such as `fanduel`, `draftkings`, and `caesars`, so one aggregate response can count as multiple independent sportsbook sources.

### 3. BetMGM

Role: direct major US sportsbook candidate.

Why it fits: unlike most major US books, BetMGM has public Sports API documentation. The documented API exposes sports, competitions, fixtures, markets, options, and prices through GET endpoints. That gives us a credible low-load path to inspect NBA fixture markets without browser scraping.

Risk: player-prop completeness is not proven until we inspect live NBA fixture markets. The adapter should start as discovery-only, then become a raw-odds adapter once market names are confirmed.

Decision: build next direct-book candidate after the API-key aggregate sources, or sooner if we want a no-key direct source.

### 4. PropLine

Role: recommended multi-book player-prop API.

Why it fits: free tier advertises 500 requests per day, 90-second refreshes, and multiple books in one response: Bovada, DraftKings, FanDuel, Pinnacle, plus PrizePicks-style projections. NBA markets include points, rebounds, assists, threes, PRA, and double-double.

Decision: strong second API source, especially for line shopping and redundancy.

### 5. SportsGameOdds

Role: broad aggregated odds API candidate.

Why it fits: NBA player props are available through a customizable REST API with filters by league, market, bookmaker, and player. It can reduce server load because one well-filtered request can replace several fragile book scrapers.

Decision: useful if free quota/key terms are acceptable.

### 6. SharpAPI

Role: fallback aggregated odds API.

Why it fits: permanent free tier, REST access, 12 requests per minute, two sportsbooks, major US sports. Its free tier may not provide enough book diversity by itself, but it is a useful stabilizer.

Decision: use only if the free books include the needed NBA player props.

## Major Bookmaker Findings

### Tipico

Tipico is relevant, but I did not find a stable official public developer API for current NBA player props. Tipico data appears available through commercial/aggregate odds APIs. Direct scraping should not be the first choice because it would likely be heavier and more fragile than the current server policy allows.

Decision: keep Tipico as research candidate; implement only if a lightweight JSON path is confirmed or if an aggregator provides Tipico rows in a free tier.

### FanDuel

FanDuel is one of the most important US player-prop books, but current research indicates there is no official public developer API. Several providers expose FanDuel data through normalized APIs.

Decision: do not direct-scrape first. Add FanDuel via BALLDONTLIE, PropLine, SportsGameOdds, or another stable aggregate API.

### DraftKings

DraftKings has known sportsbook JSON endpoint patterns and the existing adapter parses that style, but this server currently receives HTTP 403 from the public edge.

Decision: keep direct adapter disabled by default; prefer aggregate vendor rows.

### BetMGM

BetMGM has public Sports API documentation. This is the best large US direct-book target found so far.

Decision: add a discovery adapter next and inspect NBA market names.

### Caesars

Current Caesars sportsbook odds access does not appear to have a stable public odds API for individual developers. Some old Caesars developer portal material exists, but it should not be treated as a current sportsbook odds feed.

Decision: source Caesars through aggregate APIs.

### ESPN BET

No official public ESPN BET odds API was found. Internal endpoints may exist, but relying on them would be unstable.

Decision: source ESPN BET only through an aggregator.

## Skipped for Now

- Bet365 direct scraping: too heavy and fragile.
- Oddschecker direct scraping: likely HTML/browser-heavy for player props.
- FanDuel direct scraping: undocumented public API and often protected.
- Caesars direct scraping: no stable public current odds API found.
- ESPN BET direct scraping: no official public odds API found.

## Implementation Order

1. Keep Playzilla as required source and health signal.
2. Add BALLDONTLIE adapter as the first complete prop API source.
3. Add BetMGM discovery/direct adapter because public docs exist.
4. Add PropLine adapter as the second complete multi-book source.
5. Add SportsGameOdds if free quota is practical.
6. Add SharpAPI only as fallback or source-health redundancy.
