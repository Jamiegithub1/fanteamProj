from app.models import Base


def test_m2_tables_exist_in_metadata() -> None:
    expected_tables = {
        "players",
        "teams",
        "games",
        "bookmakers",
        "odds_markets",
        "raw_odds",
        "aggregated_odds",
        "projections",
        "source_health",
        "refresh_runs",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_raw_odds_has_source_and_safety_columns() -> None:
    raw_odds = Base.metadata.tables["raw_odds"]

    for column_name in (
        "bookmaker_id",
        "refresh_run_id",
        "source_event_id",
        "source_player_name",
        "collected_at",
    ):
        assert column_name in raw_odds.columns


def test_source_health_tracks_failures_and_disable_reason() -> None:
    source_health = Base.metadata.tables["source_health"]

    for column_name in (
        "status",
        "last_success_at",
        "last_failure_at",
        "consecutive_failures",
        "disabled_reason",
    ):
        assert column_name in source_health.columns
