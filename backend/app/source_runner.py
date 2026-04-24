from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bookmaker, OddsMarket, Player, RawOdd, RefreshRun, SourceHealth
from app.odds_math import american_to_probability, decimal_to_probability
from app.sources.base import SourceAdapter, SourceOdd, SourceResult
from app.sources.markets import MARKETS


def refresh_source(session: Session, adapter: SourceAdapter) -> SourceResult:
    bookmaker = ensure_bookmaker(session, adapter)
    ensure_markets(session)

    started_at = datetime.now(UTC)
    run = RefreshRun(source_key=adapter.source_key, status="running", started_at=started_at)
    session.add(run)
    session.flush()

    result = adapter.fetch()
    run.finished_at = datetime.now(UTC)
    run.rows_found = len(result.odds)
    run.status = result.status
    run.error_message = result.message

    if result.status in {"success", "degraded"}:
        for odd in result.odds:
            raw_bookmaker = bookmaker
            if odd.bookmaker_key and odd.bookmaker_key != bookmaker.key:
                raw_bookmaker = ensure_vendor_bookmaker(session, odd, adapter)
            persist_raw_odd(session, raw_bookmaker, run, odd)

    update_source_health(session, bookmaker, result)
    session.flush()
    return result


def ensure_bookmaker(session: Session, adapter: SourceAdapter) -> Bookmaker:
    bookmaker = session.scalar(select(Bookmaker).where(Bookmaker.key == adapter.source_key))
    if bookmaker is None:
        bookmaker = Bookmaker(
            key=adapter.source_key,
            name=adapter.source_name,
            requires_browser=adapter.requires_browser,
            refresh_interval_seconds=adapter.refresh_interval_seconds,
            is_enabled=True,
        )
        session.add(bookmaker)
        session.flush()
    else:
        bookmaker.requires_browser = adapter.requires_browser
        bookmaker.refresh_interval_seconds = adapter.refresh_interval_seconds
    return bookmaker


def ensure_markets(session: Session) -> None:
    existing = set(session.scalars(select(OddsMarket.key)).all())
    for market in MARKETS:
        if market.key in existing:
            continue
        session.add(
            OddsMarket(
                key=market.key,
                name=market.name,
                stat_key=market.stat_key,
                fanteam_scoring_weight=market.scoring_weight,
                is_enabled=True,
            )
        )


def ensure_vendor_bookmaker(session: Session, odd: SourceOdd, adapter: SourceAdapter) -> Bookmaker:
    if not odd.bookmaker_key:
        raise ValueError("Vendor bookmaker key is required")
    bookmaker = session.scalar(select(Bookmaker).where(Bookmaker.key == odd.bookmaker_key))
    if bookmaker is None:
        bookmaker = Bookmaker(
            key=odd.bookmaker_key,
            name=odd.bookmaker_name or odd.bookmaker_key.title(),
            requires_browser=False,
            refresh_interval_seconds=adapter.refresh_interval_seconds,
            is_enabled=True,
        )
        session.add(bookmaker)
        session.flush()
    return bookmaker


def persist_raw_odd(session: Session, bookmaker: Bookmaker, run: RefreshRun, odd: SourceOdd) -> RawOdd:
    player = ensure_player(session, odd)
    market = session.scalar(select(OddsMarket).where(OddsMarket.key == odd.market_key))
    if market is None:
        raise ValueError(f"Unknown odds market: {odd.market_key}")
    raw_odd = RawOdd(
        bookmaker_id=bookmaker.id,
        market_id=market.id,
        player_id=player.id,
        refresh_run_id=run.id,
        line=odd.line,
        side=odd.side,
        american_odds=odd.american_odds,
        decimal_odds=odd.decimal_odds,
        implied_probability=implied_probability(odd),
        source_event_id=odd.event_id,
        source_player_name=odd.player_name,
        collected_at=odd.collected_at,
    )
    session.add(raw_odd)
    return raw_odd


def ensure_player(session: Session, odd: SourceOdd) -> Player:
    external_id = f"{odd.source_key}:{slugify(odd.player_name)}"
    player = session.scalar(select(Player).where(Player.external_id == external_id))
    if player is None:
        player = Player(external_id=external_id, name=odd.player_name, is_active=True)
        session.add(player)
        session.flush()
    return player


def update_source_health(session: Session, bookmaker: Bookmaker, result: SourceResult) -> SourceHealth:
    health = session.scalar(select(SourceHealth).where(SourceHealth.bookmaker_id == bookmaker.id))
    now = datetime.now(UTC)
    if health is None:
        health = SourceHealth(bookmaker_id=bookmaker.id, status=result.status, consecutive_failures=0)
        session.add(health)

    health.status = result.status
    health.latency_ms = result.latency_ms
    if result.status == "success":
        health.last_success_at = now
        health.consecutive_failures = 0
        health.disabled_reason = None
    else:
        health.last_failure_at = now
        health.consecutive_failures = (health.consecutive_failures or 0) + 1
        health.disabled_reason = result.message
    return health


def implied_probability(odd: SourceOdd) -> Decimal | None:
    if odd.american_odds is not None:
        return american_to_probability(odd.american_odds)
    if odd.decimal_odds is not None:
        return decimal_to_probability(odd.decimal_odds)
    return None


def slugify(value: str) -> str:
    return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())
