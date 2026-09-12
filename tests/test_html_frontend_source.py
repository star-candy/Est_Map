"""HTML 앱의 상태 처리와 내부 스크롤 계약을 검사한다."""

from pathlib import Path

FRONTEND = Path("src/ui/html_frontend/index.html")
HOST = Path("src/ui/html_frontend.py")


def test_transient_toasts_are_consumed_once() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert "shownToastKeys=new Set()" in source
    assert "shownToastKeys.has(key)" in source
    assert "coupon_event_id" in source


def test_frontend_relays_map_click_and_scrolls_inside_full_frame() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert "e.data?.type==='pihaga-map-click'" in source
    assert "overflow-y:auto" in source
    assert "height:100vh" in source
    assert "frame.srcdoc=" in source
    assert 'id="active-map-frame"' in source


def test_frontend_waits_for_backend_event_ack_before_rendering() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert "pendingEventId=id" in source
    assert "nextPayload.ack_event_id!==pendingEventId" in source
    assert "pendingEventId=null;payload=nextPayload" in source


def test_ai_answers_use_safe_readable_rich_text() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert "function richText(value)" in source
    assert "esc(value)" in source
    assert "richText(x.content)" in source


def test_streamlit_host_removes_component_whitespace() -> None:
    source = HOST.read_text(encoding="utf-8")

    assert '[data-testid="stMainBlockContainer"]' in source
    assert 'iframe[title*="pihaga_mobile_frontend"]' in source
    assert "margin: 0 !important" in source
    assert '[data-testid="stVerticalBlock"] { gap: 0 !important; }' in source


def test_frontend_has_persistent_accessible_theme_toggle() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert 'localStorage.getItem("pihaga-theme")' in source
    assert 'localStorage.setItem("pihaga-theme",themePreference)' in source
    assert "function toggleTheme()" in source
    assert 'class="theme-toggle"' in source
    assert 'aria-label="${dark?' in source
