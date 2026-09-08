"""정밀 위치 없이 집계값 중심으로 저장하는 로컬 SQLite 저장소."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.reporting.accounting import TripAccounting


@dataclass(frozen=True, slots=True)
class MonthlySummary:
    month: str
    trip_count: int
    distance_m: float
    carbon_saved_g: float
    taxi_saved_krw: int


class MonthlyReportStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS completed_trips (
                trip_id TEXT PRIMARY KEY,
                completed_at TEXT NOT NULL,
                month TEXT NOT NULL,
                route_kind TEXT NOT NULL,
                distance_m REAL NOT NULL,
                carbon_saved_g REAL NOT NULL,
                taxi_saved_krw INTEGER NOT NULL
            )
            """
        )
        return connection

    def record_trip(
        self,
        trip_id: str,
        route_kind: str,
        accounting: TripAccounting,
        completed_at: datetime,
    ) -> bool:
        """새 이동이면 저장하고, 같은 trip_id가 이미 있으면 False를 반환한다."""
        month = completed_at.strftime("%Y-%m")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO completed_trips (
                    trip_id, completed_at, month, route_kind,
                    distance_m, carbon_saved_g, taxi_saved_krw
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trip_id,
                    completed_at.isoformat(),
                    month,
                    route_kind,
                    accounting.distance_m,
                    accounting.carbon_saved_g,
                    accounting.taxi_saved_krw,
                ),
            )
            return cursor.rowcount == 1

    def monthly_summary(self, month: str) -> MonthlySummary:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(distance_m), 0),
                       COALESCE(SUM(carbon_saved_g), 0),
                       COALESCE(SUM(taxi_saved_krw), 0)
                FROM completed_trips WHERE month = ?
                """,
                (month,),
            ).fetchone()
        return MonthlySummary(
            month=month,
            trip_count=int(row[0]),
            distance_m=float(row[1]),
            carbon_saved_g=float(row[2]),
            taxi_saved_krw=int(row[3]),
        )

    def available_months(self) -> tuple[str, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT month FROM completed_trips ORDER BY month DESC"
            ).fetchall()
        return tuple(str(row[0]) for row in rows)
