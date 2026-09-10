"""출석·걷기 포인트와 MVP 리더보드 테스트."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.rewards.points import (
    ATTENDANCE_POINTS,
    PointStore,
    calculate_walking_points,
    environmental_encouragement,
)

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")


def test_walking_points_use_distance_and_carbon() -> None:
    total, distance, carbon = calculate_walking_points(1_250.0, 240.0)

    assert distance == 12
    assert carbon == 12
    assert total == 24


def test_attendance_is_awarded_once_per_day(tmp_path: Path) -> None:
    store = PointStore(tmp_path / "points.sqlite3")
    now = datetime(2026, 9, 10, 9, 0, tzinfo=SEOUL_TIMEZONE)

    first = store.claim_attendance(now)
    duplicate = store.claim_attendance(now)

    assert first.awarded
    assert first.points == ATTENDANCE_POINTS
    assert not duplicate.awarded
    assert duplicate.points == 0
    assert store.total_points() == ATTENDANCE_POINTS


def test_walking_trip_points_are_not_duplicated(tmp_path: Path) -> None:
    store = PointStore(tmp_path / "points.sqlite3")
    completed_at = datetime(2026, 9, 10, 10, 0, tzinfo=SEOUL_TIMEZONE)

    first = store.award_walking_trip("trip-1", 1_000.0, 192.0, completed_at)
    duplicate = store.award_walking_trip("trip-1", 1_000.0, 192.0, completed_at)

    assert first.awarded
    assert first.points == 19
    assert first.distance_points == 10
    assert first.carbon_points == 9
    assert not duplicate.awarded
    assert duplicate.points == 0
    assert store.total_points() == 19


def test_leaderboard_only_updates_current_local_user(tmp_path: Path) -> None:
    store = PointStore(tmp_path / "points.sqlite3")
    before = store.leaderboard()
    store.claim_attendance(datetime(2026, 9, 10, tzinfo=SEOUL_TIMEZONE))
    after = store.leaderboard()

    before_demo = [(entry.name, entry.points) for entry in before if entry.is_sample]
    after_demo = [(entry.name, entry.points) for entry in after if entry.is_sample]
    current = next(entry for entry in after if entry.is_current_user)

    assert before_demo == after_demo
    assert current.points == ATTENDANCE_POINTS
    assert not current.is_sample


def test_environmental_message_uses_penguin_encouragement() -> None:
    message = environmental_encouragement(1_500.0, 288.0)

    assert "펭귄" in message
    assert "실제 환산값이 아닌" not in message
