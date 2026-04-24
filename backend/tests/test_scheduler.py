from types import SimpleNamespace

from app import scheduler


def test_next_refresh_interval_uses_regular_interval(monkeypatch) -> None:
    settings = SimpleNamespace(
        scheduler_regular_interval_seconds=1800,
        scheduler_prelock_interval_seconds=300,
    )
    monkeypatch.setattr(scheduler, "has_game_near_lock", lambda _: False)

    assert scheduler.next_refresh_interval_seconds(settings) == 1800


def test_next_refresh_interval_uses_prelock_interval(monkeypatch) -> None:
    settings = SimpleNamespace(
        scheduler_regular_interval_seconds=1800,
        scheduler_prelock_interval_seconds=300,
    )
    monkeypatch.setattr(scheduler, "has_game_near_lock", lambda _: True)

    assert scheduler.next_refresh_interval_seconds(settings) == 300
