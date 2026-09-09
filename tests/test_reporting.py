"""비용·탄소 계산과 로컬 월별 집계 테스트."""

import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from config.accounting import ACCOUNTING
from src.reporting.accounting import (
    calculate_trip_accounting,
    estimate_carbon_saved_g,
    estimate_taxi_fare_krw,
)
from src.reporting.briefing import (
    MonthlyReportChatbot,
    TemplateBriefingProvider,
)
from src.reporting.monthly import MonthlyReportStore, MonthlySummary
from src.ui.components import monthly_savings_delta

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")


def test_taxi_fare_boundaries() -> None:
    assert estimate_taxi_fare_krw(0) == 0
    assert estimate_taxi_fare_krw(1) == ACCOUNTING.taxi_base_fare_krw
    assert estimate_taxi_fare_krw(1_600) == ACCOUNTING.taxi_base_fare_krw
    assert estimate_taxi_fare_krw(1_601) == ACCOUNTING.taxi_base_fare_krw + 100


def test_taxi_savings_only_when_user_confirms_replacement() -> None:
    without_taxi = calculate_trip_accounting(2_000, taxi_replaced=False)
    with_taxi = calculate_trip_accounting(2_000, taxi_replaced=True)

    assert without_taxi.taxi_saved_krw == 0
    assert with_taxi.taxi_saved_krw > 0


def test_tmap_fare_override_is_saved_as_savings() -> None:
    accounting = calculate_trip_accounting(2_000, taxi_replaced=True, taxi_fare_krw=7_600)
    assert accounting.taxi_saved_krw == 7_600
    assert accounting.taxi_fare_source == "TMAP 예상 택시요금"


def test_carbon_calculation() -> None:
    assert estimate_carbon_saved_g(0) == 0
    assert estimate_carbon_saved_g(1_000) == pytest.approx(ACCOUNTING.passenger_car_co2_g_per_km)


def test_monthly_aggregation_and_duplicate_prevention(tmp_path: Path) -> None:
    store = MonthlyReportStore(tmp_path / "reports.sqlite3")
    january_trip = calculate_trip_accounting(2_000, taxi_replaced=True)
    february_trip = calculate_trip_accounting(1_000, taxi_replaced=False)

    assert store.record_trip(
        "trip-1", "일반 최단 경로", january_trip, datetime(2026, 1, 10, tzinfo=SEOUL_TIMEZONE)
    )
    assert not store.record_trip(
        "trip-1", "일반 최단 경로", january_trip, datetime(2026, 1, 10, tzinfo=SEOUL_TIMEZONE)
    )
    assert store.record_trip(
        "trip-2", "맞춤 경로", january_trip, datetime(2026, 1, 20, tzinfo=SEOUL_TIMEZONE)
    )
    assert store.record_trip(
        "trip-3", "일반 최단 경로", february_trip, datetime(2026, 2, 1, tzinfo=SEOUL_TIMEZONE)
    )

    january = store.monthly_summary("2026-01")
    february = store.monthly_summary("2026-02")
    assert january.trip_count == 2
    assert january.distance_m == pytest.approx(4_000)
    assert january.carbon_saved_g == pytest.approx(january_trip.carbon_saved_g * 2)
    assert january.taxi_saved_krw == january_trip.taxi_saved_krw * 2
    assert february.trip_count == 1
    assert february.taxi_saved_krw == 0
    assert store.available_months() == ("2026-02", "2026-01")
    assert store.previous_month_summary("2026-01").month == "2025-12"


def test_monthly_savings_delta_compares_previous_calendar_month() -> None:
    current = MonthlySummary("2026-02", 2, 2_000, 384, 5_000)
    previous = MonthlySummary("2026-01", 1, 1_000, 192, 4_800)
    assert monthly_savings_delta(current, previous) == 200


def test_database_does_not_store_coordinates_or_paths(tmp_path: Path) -> None:
    database_path = tmp_path / "reports.sqlite3"
    store = MonthlyReportStore(database_path)
    store.monthly_summary("2026-01")

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(completed_trips)").fetchall()
        }

    assert "latitude" not in columns
    assert "longitude" not in columns
    assert "origin" not in columns
    assert "destination" not in columns
    assert "path" not in columns


def test_template_briefing_uses_calculated_summary(tmp_path: Path) -> None:
    store = MonthlyReportStore(tmp_path / "reports.sqlite3")
    accounting = calculate_trip_accounting(2_000, taxi_replaced=True)
    store.record_trip(
        "trip-1", "맞춤 경로", accounting, datetime(2026, 3, 1, tzinfo=SEOUL_TIMEZONE)
    )

    briefing = TemplateBriefingProvider().generate(store.monthly_summary("2026-03"))

    assert "2.00km" in briefing
    assert f"{accounting.taxi_saved_krw:,}원" in briefing


def test_langchain_chatbot_uses_statistics_and_history(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        text = "지난달보다 이동이 늘었습니다. 다음 목표를 함께 정해볼까요?"
        content = text

    class FakeModel:
        def invoke(self, messages):
            captured["messages"] = messages
            return FakeResponse()

    chatbot = MonthlyReportChatbot("test-key", "test-model")
    monkeypatch.setattr(chatbot, "_chat_model", lambda: FakeModel())
    current = MonthlySummary("2026-02", 2, 2_000, 384, 5_000)
    previous = MonthlySummary("2026-01", 1, 1_000, 192, 4_800)
    answer = chatbot.reply(
        current,
        previous,
        [{"role": "user", "content": "지난 목표를 기억해줘"}],
        "지난달과 비교해줘",
    )

    serialized = " ".join(str(message.content) for message in captured["messages"])
    assert "walking_distance_km" in serialized
    assert "지난 목표" in serialized
    assert "latitude" not in serialized
    assert answer.startswith("지난달보다")
