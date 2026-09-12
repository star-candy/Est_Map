"""모바일 카드가 고정 예시가 아닌 실제 도메인 값을 표시하는지 확인한다."""

from src.domain import Coordinates, RouteComparison, RouteMode, RoutePath
from src.reporting.monthly import MonthlySummary
from src.ui.mobile_cards import render_brand_header, render_report_deck, render_route_deck


def _capture_markdown(monkeypatch) -> list[str]:
    rendered: list[str] = []
    monkeypatch.setattr(
        "src.ui.mobile_cards.st.markdown", lambda body, **_: rendered.append(body)
    )
    return rendered


def test_route_deck_uses_route_result_values(monkeypatch) -> None:
    rendered = _capture_markdown(monkeypatch)
    baseline = RoutePath((Coordinates(37.5, 127.0),), 1_000, 13, 42)
    optimized = RoutePath((Coordinates(37.5, 127.0),), 1_200, 16, 81)
    comparison = RouteComparison(
        Coordinates(37.5, 127.0),
        Coordinates(37.51, 127.01),
        baseline,
        optimized,
        RouteMode.SUMMER,
        0.2,
        "test",
        False,
        "RL 정책",
        "실제 값",
    )

    render_route_deck(comparison)

    assert "1.20km" in rendered[0]
    assert "81.0점" in rendered[0]
    assert "RL 정책" in rendered[0]


def test_report_and_brand_cards_use_current_values_and_escape_text(monkeypatch) -> None:
    rendered = _capture_markdown(monkeypatch)
    render_brand_header("<리포트>")
    render_report_deck(
        MonthlySummary("2026-09", 3, 4_500, 740, 8_000),
        MonthlySummary("2026-08", 2, 3_000, 500, 4_800),
    )

    assert "&lt;리포트&gt;" in rendered[0]
    assert "4.50" in rendered[1]
    assert "8,000" in rendered[1]
    assert "전월 대비 +1.50km" in rendered[1]
