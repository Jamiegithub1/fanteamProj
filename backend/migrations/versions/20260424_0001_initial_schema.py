"""initial schema

Revision ID: 20260424_0001
Revises:
Create Date: 2026-04-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260424_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nba_team_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("abbreviation", sa.String(length=8), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("abbreviation"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("nba_team_id"),
    )
    op.create_table(
        "bookmakers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("requires_browser", sa.Boolean(), nullable=False),
        sa.Column("refresh_interval_seconds", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "odds_markets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("stat_key", sa.String(length=40), nullable=False),
        sa.Column("fanteam_scoring_weight", sa.Numeric(precision=8, scale=3), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "refresh_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_found", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_runs_source_started", "refresh_runs", ["source_key", "started_at"])
    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("position", sa.String(length=12), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), nullable=False),
        sa.Column("away_team_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nba_game_id", sa.String(length=120), nullable=True),
        sa.Column("season", sa.String(length=12), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["away_team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["home_team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("home_team_id", "away_team_id", "starts_at", name="uq_games_matchup_start"),
        sa.UniqueConstraint("nba_game_id"),
    )
    op.create_index("ix_games_starts_at", "games", ["starts_at"])
    op.create_table(
        "source_health",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bookmaker_id"),
    )
    op.create_table(
        "raw_odds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("refresh_run_id", sa.Integer(), nullable=True),
        sa.Column("line", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("american_odds", sa.Integer(), nullable=True),
        sa.Column("decimal_odds", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("implied_probability", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("source_event_id", sa.String(length=160), nullable=True),
        sa.Column("source_player_name", sa.String(length=160), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("side in ('over', 'under', 'yes', 'no')", name="ck_raw_odds_side"),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["market_id"], ["odds_markets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["refresh_run_id"], ["refresh_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_odds_bookmaker_collected", "raw_odds", ["bookmaker_id", "collected_at"])
    op.create_index("ix_raw_odds_player_game_market", "raw_odds", ["player_id", "game_id", "market_id"])
    op.create_table(
        "aggregated_odds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("line", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("expected_value", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("over_probability", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("under_probability", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["market_id"], ["odds_markets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "game_id", "market_id", "line", name="uq_aggregated_odds_slice"),
    )
    op.create_index("ix_aggregated_odds_player_game", "aggregated_odds", ["player_id", "game_id"])
    op.create_table(
        "projections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("projection_date", sa.Date(), nullable=False),
        sa.Column("points", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("threes_made", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("rebounds", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("assists", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("steals", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("blocks", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("turnovers", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("double_double_probability", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("triple_double_probability", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("fantasy_points", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "game_id", "projection_date", name="uq_projections_player_game_date"),
    )
    op.create_index("ix_projections_projection_date", "projections", ["projection_date"])


def downgrade() -> None:
    op.drop_index("ix_projections_projection_date", table_name="projections")
    op.drop_table("projections")
    op.drop_index("ix_aggregated_odds_player_game", table_name="aggregated_odds")
    op.drop_table("aggregated_odds")
    op.drop_index("ix_raw_odds_player_game_market", table_name="raw_odds")
    op.drop_index("ix_raw_odds_bookmaker_collected", table_name="raw_odds")
    op.drop_table("raw_odds")
    op.drop_table("source_health")
    op.drop_index("ix_games_starts_at", table_name="games")
    op.drop_table("games")
    op.drop_table("players")
    op.drop_index("ix_refresh_runs_source_started", table_name="refresh_runs")
    op.drop_table("refresh_runs")
    op.drop_table("odds_markets")
    op.drop_table("bookmakers")
    op.drop_table("teams")
