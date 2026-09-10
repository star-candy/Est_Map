"""로그인 없이 사용하는 로컬 포인트 원장과 MVP 리더보드."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ATTENDANCE_POINTS = 50
DISTANCE_UNIT_M = 100.0
CARBON_UNIT_G = 20.0
LOCAL_USER_ID = "local-user"
LOCAL_USER_NAME = "나"


@dataclass(frozen=True, slots=True)
class PointAward:
    awarded: bool
    points: int
    total_points: int
    distance_points: int = 0
    carbon_points: int = 0


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    rank: int
    name: str
    points: int
    is_current_user: bool
    is_sample: bool


def calculate_walking_points(distance_m: float, carbon_saved_g: float) -> tuple[int, int, int]:
    """거리와 탄소 감축량을 각각 내림해 중복 과장 없이 포인트로 변환한다."""
    distance_points = int(max(0.0, distance_m) // DISTANCE_UNIT_M)
    carbon_points = int(max(0.0, carbon_saved_g) // CARBON_UNIT_G)
    return distance_points + carbon_points, distance_points, carbon_points


def environmental_encouragement(distance_m: float, carbon_saved_g: float) -> str:
    """실제 과학적 환산으로 오해되지 않는 작은 환경 응원 문구를 만든다."""
    if distance_m >= 3_000:
        image = "펭귄 가족이 쉬어갈 빙하 길을 한 뼘 지킨 것 같은"
    elif carbon_saved_g >= 200:
        image = "펭귄이 살 수 있는 빙하가 1cm 늘어난 것 같은"
    else:
        image = "도시의 공기가 한 모금 맑아진 것 같은"
    return f"걸어서 이동해 {image} 변화를 만들었어요!"


class PointStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS point_events (
                event_key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                points INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                distance_m REAL NOT NULL DEFAULT 0,
                carbon_saved_g REAL NOT NULL DEFAULT 0
            )
            """
        )
        return connection

    def total_points(self, user_id: str = LOCAL_USER_ID) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(points), 0) FROM point_events WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row[0])

    def attendance_claimed(self, attended_at: datetime, user_id: str = LOCAL_USER_ID) -> bool:
        event_key = f"attendance:{user_id}:{attended_at.date().isoformat()}"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM point_events WHERE event_key = ?", (event_key,)
            ).fetchone()
        return row is not None

    def claim_attendance(
        self, attended_at: datetime, user_id: str = LOCAL_USER_ID
    ) -> PointAward:
        event_key = f"attendance:{user_id}:{attended_at.date().isoformat()}"
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO point_events (
                    event_key, user_id, event_type, points, created_at
                ) VALUES (?, ?, 'attendance', ?, ?)
                """,
                (event_key, user_id, ATTENDANCE_POINTS, attended_at.isoformat()),
            )
            awarded = cursor.rowcount == 1
        return PointAward(
            awarded=awarded,
            points=ATTENDANCE_POINTS if awarded else 0,
            total_points=self.total_points(user_id),
        )

    def award_walking_trip(
        self,
        trip_id: str,
        distance_m: float,
        carbon_saved_g: float,
        completed_at: datetime,
        user_id: str = LOCAL_USER_ID,
    ) -> PointAward:
        points, distance_points, carbon_points = calculate_walking_points(
            distance_m, carbon_saved_g
        )
        event_key = f"walking:{user_id}:{trip_id}"
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO point_events (
                    event_key, user_id, event_type, points, created_at,
                    distance_m, carbon_saved_g
                ) VALUES (?, ?, 'walking', ?, ?, ?, ?)
                """,
                (
                    event_key,
                    user_id,
                    points,
                    completed_at.isoformat(),
                    max(0.0, distance_m),
                    max(0.0, carbon_saved_g),
                ),
            )
            awarded = cursor.rowcount == 1
        return PointAward(
            awarded=awarded,
            points=points if awarded else 0,
            total_points=self.total_points(user_id),
            distance_points=distance_points if awarded else 0,
            carbon_points=carbon_points if awarded else 0,
        )

    def leaderboard(self, user_id: str = LOCAL_USER_ID) -> tuple[LeaderboardEntry, ...]:
        demo_users = (
            ("초록발걸음", 1_420),
            ("한강산책러", 980),
            ("뚜벅이서울", 610),
            ("나무늘보", 280),
        )
        rows = [(*entry, False, True) for entry in demo_users]
        rows.append((LOCAL_USER_NAME, self.total_points(user_id), True, False))
        rows.sort(key=lambda item: (-item[1], item[0]))
        return tuple(
            LeaderboardEntry(index, name, points, current, sample)
            for index, (name, points, current, sample) in enumerate(rows, start=1)
        )
