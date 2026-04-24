from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    nba_team_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    abbreviation: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)

    players: Mapped[list["Player"]] = relationship(back_populates="team")


class Player(Base, TimestampMixin):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"))
    external_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    position: Mapped[str | None] = mapped_column(String(12))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    team: Mapped[Team | None] = relationship(back_populates="players")


class Game(Base, TimestampMixin):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("home_team_id", "away_team_id", "starts_at", name="uq_games_matchup_start"),
        Index("ix_games_starts_at", "starts_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    nba_game_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    season: Mapped[str | None] = mapped_column(String(12))

    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id])


class Bookmaker(Base, TimestampMixin):
    __tablename__ = "bookmakers"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_browser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refresh_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)


class OddsMarket(Base, TimestampMixin):
    __tablename__ = "odds_markets"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    stat_key: Mapped[str] = mapped_column(String(40), nullable=False)
    fanteam_scoring_weight: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RefreshRun(Base, TimestampMixin):
    __tablename__ = "refresh_runs"
    __table_args__ = (Index("ix_refresh_runs_source_started", "source_key", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class RawOdd(Base, TimestampMixin):
    __tablename__ = "raw_odds"
    __table_args__ = (
        CheckConstraint("side in ('over', 'under', 'yes', 'no')", name="ck_raw_odds_side"),
        Index("ix_raw_odds_player_game_market", "player_id", "game_id", "market_id"),
        Index("ix_raw_odds_bookmaker_collected", "bookmaker_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id", ondelete="CASCADE"))
    market_id: Mapped[int] = mapped_column(ForeignKey("odds_markets.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"))
    refresh_run_id: Mapped[int | None] = mapped_column(ForeignKey("refresh_runs.id", ondelete="SET NULL"))
    line: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    american_odds: Mapped[int | None] = mapped_column(Integer)
    decimal_odds: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    implied_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    source_event_id: Mapped[str | None] = mapped_column(String(160))
    source_player_name: Mapped[str | None] = mapped_column(String(160))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AggregatedOdd(Base, TimestampMixin):
    __tablename__ = "aggregated_odds"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", "market_id", "line", name="uq_aggregated_odds_slice"),
        Index("ix_aggregated_odds_player_game", "player_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"))
    market_id: Mapped[int] = mapped_column(ForeignKey("odds_markets.id", ondelete="CASCADE"))
    line: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    over_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    under_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Projection(Base, TimestampMixin):
    __tablename__ = "projections"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", "projection_date", name="uq_projections_player_game_date"),
        Index("ix_projections_projection_date", "projection_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"))
    projection_date: Mapped[date] = mapped_column(Date, nullable=False)
    points: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    threes_made: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    rebounds: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    assists: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    steals: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    blocks: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    turnovers: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    double_double_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    triple_double_probability: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    fantasy_points: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SourceHealth(Base, TimestampMixin):
    __tablename__ = "source_health"

    id: Mapped[int] = mapped_column(primary_key=True)
    bookmaker_id: Mapped[int] = mapped_column(ForeignKey("bookmakers.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disabled_reason: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
