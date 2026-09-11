"""반응형 주 메뉴와 쿠폰 알림의 기본 계약 테스트."""

from types import SimpleNamespace

import app
from src.ui.responsive import CATEGORY_LABELS, MAIN_CATEGORIES, inject_responsive_styles


def test_mobile_navigation_has_map_first_and_five_distinct_categories() -> None:
    assert MAIN_CATEGORIES[0] == "지도"
    assert MAIN_CATEGORIES == (
        "지도",
        "안내",
        "주변",
        "이동",
        "리포트",
    )
    assert len(set(MAIN_CATEGORIES)) == len(MAIN_CATEGORIES)
    assert all("\n" in CATEGORY_LABELS[category] for category in MAIN_CATEGORIES)


def test_navigation_is_full_width_bottom_bar_and_uses_theme_colors(monkeypatch) -> None:
    rendered = []
    monkeypatch.setattr("src.ui.responsive.st.markdown", lambda body, **_: rendered.append(body))

    inject_responsive_styles()

    css = rendered[0]
    assert "position: fixed" in css
    assert "width: 100vw" in css
    assert "grid-template-columns: repeat(5" in css
    assert "var(--background-color)" in css
    assert "var(--text-color)" in css
    assert '[data-testid="stBottom"]' in css
    assert "inset: auto 0 calc(76px" in css
    assert "z-index: 100000" in css
    assert '[data-testid="stBottomBlockContainer"]' in css
    assert "pointer-events: auto" in css


def test_each_restaurant_gets_its_own_coupon_toast(monkeypatch) -> None:
    messages = []
    monkeypatch.setattr(app.st, "toast", lambda message, **_: messages.append(message))

    app._show_restaurant_coupon_toasts(
        (SimpleNamespace(name="첫 번째 식당"), SimpleNamespace(name="두 번째 식당"))
    )

    assert len(messages) == 2
    assert "첫 번째 식당" in messages[0]
    assert "두 번째 식당" in messages[1]
