"""HTML 프런트엔드 이벤트가 기존 Python 서비스로 전달되는지 확인한다."""

from datetime import datetime

import app
from src.domain import Coordinates, RouteComparison, RouteMode, RoutePath


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class StoreStub:
    def __init__(self) -> None:
        self.recorded = False

    def record_trip(self, *_args) -> bool:
        self.recorded = True
        return True


class PointStoreStub:
    def __init__(self) -> None:
        self.awarded = False

    def award_walking_trip(self, *_args) -> None:
        self.awarded = True


def comparison() -> RouteComparison:
    origin = Coordinates(37.5, 127.0)
    destination = Coordinates(37.51, 127.01)
    baseline = RoutePath((origin, destination), 1_000, 13, 45)
    optimized = RoutePath((origin, destination), 1_150, 15, 82)
    return RouteComparison(
        origin,
        destination,
        baseline,
        optimized,
        RouteMode.SUMMER,
        0.15,
        "OSM",
        False,
        "RL 정책",
        "실제 연결",
    )


def test_search_event_calls_existing_routing_service(monkeypatch) -> None:
    state = SessionState()
    result = comparison()

    class ServiceStub:
        def find_routes(self, request):
            assert request.origin == "서울역"
            assert request.mode is RouteMode.SUMMER
            return result

    monkeypatch.setattr(app.st, "session_state", state)
    monkeypatch.setattr(app, "RoutingService", ServiceStub)

    handled = app._handle_html_event(
        {
            "id": "search-1",
            "action": "search_route",
            "origin": "서울역",
            "destination": "광화문",
            "mode": "여름",
        },
        StoreStub(),
        PointStoreStub(),
    )

    assert handled is True
    assert state.route_comparison is result
    assert state.html_notice["type"] == "success"


def test_completion_event_records_route_and_points(monkeypatch) -> None:
    state = SessionState(route_comparison=comparison(), trip_recorded=False)
    store = StoreStub()
    points = PointStoreStub()
    monkeypatch.setattr(app.st, "session_state", state)
    monkeypatch.setattr(app, "datetime", datetime)

    handled = app._handle_html_event(
        {
            "id": "trip-1",
            "action": "complete_trip",
            "route_kind": "optimized",
            "taxi_replaced": False,
        },
        store,
        points,
    )

    assert handled is True
    assert store.recorded is True
    assert points.awarded is True
    assert state.trip_recorded is True
    assert "걸어서 이동해" in state.html_notice["text"]
    assert "환경 기여가 이번 달 기록" not in state.html_notice["text"]


def test_map_click_updates_navigation_position(monkeypatch) -> None:
    state = SessionState(route_comparison=comparison(), navigation_active=True)
    monkeypatch.setattr(app.st, "session_state", state)
    monkeypatch.setattr(app, "_synthesize_navigation_instruction", lambda _comparison: None)

    handled = app._handle_html_event(
        {
            "id": "map-click-1",
            "action": "update_location",
            "page": "navigation",
            "latitude": 37.502,
            "longitude": 127.003,
        },
        StoreStub(),
        PointStoreStub(),
    )

    assert handled is True
    assert state.navigation_position == Coordinates(37.502, 127.003)
    assert state.html_active_page == "navigation"
