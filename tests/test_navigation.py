"""현재 위치 기반 텍스트 경로 안내 테스트."""

from src.domain import Coordinates, RoutePath
from src.navigation import build_guidance, voice_announcement_key


def _route(*points: Coordinates) -> RoutePath:
    return RoutePath(tuple(points), 300.0, 4.0, 50.0)


def test_guidance_announces_next_right_turn() -> None:
    route = _route(
        Coordinates(37.5, 127.0),
        Coordinates(37.501, 127.0),
        Coordinates(37.501, 127.001),
    )

    guidance = build_guidance(route, Coordinates(37.5002, 127.0))

    assert "우회전" in guidance.instruction
    assert 80.0 < guidance.distance_to_action_m < 100.0
    assert not guidance.off_route


def test_guidance_reports_off_route_and_nearest_return_point() -> None:
    route = _route(Coordinates(37.5, 127.0), Coordinates(37.501, 127.0))

    guidance = build_guidance(route, Coordinates(37.5005, 127.001))

    assert guidance.off_route
    assert "벗어났습니다" in guidance.instruction
    assert guidance.off_route_distance_m > 35.0
    assert guidance.next_position.longitude == 127.0


def test_guidance_detects_arrival() -> None:
    destination = Coordinates(37.501, 127.0)
    route = _route(Coordinates(37.5, 127.0), destination)

    guidance = build_guidance(route, destination)

    assert guidance.arrived
    assert guidance.instruction == "목적지에 도착했습니다."


def test_guidance_progress_increases_as_location_moves() -> None:
    route = _route(Coordinates(37.5, 127.0), Coordinates(37.502, 127.0))

    first = build_guidance(route, Coordinates(37.5002, 127.0))
    second = build_guidance(route, Coordinates(37.5012, 127.0))

    assert second.route_progress > first.route_progress
    assert second.remaining_distance_m < first.remaining_distance_m


def test_voice_event_fires_at_departure_and_near_turn_only() -> None:
    route = _route(
        Coordinates(37.5, 127.0),
        Coordinates(37.501, 127.0),
        Coordinates(37.501, 127.001),
    )
    far = build_guidance(route, Coordinates(37.5002, 127.0))
    near = build_guidance(route, Coordinates(37.5006, 127.0))

    assert voice_announcement_key(far, initial=True) == "departure"
    assert voice_announcement_key(far) is None
    assert voice_announcement_key(near).startswith("action:")


def test_arrival_and_off_route_are_voice_events() -> None:
    destination = Coordinates(37.501, 127.0)
    route = _route(Coordinates(37.5, 127.0), destination)

    arrival = build_guidance(route, destination)
    off_route = build_guidance(route, Coordinates(37.5005, 127.001))

    assert voice_announcement_key(arrival) == "arrival"
    assert voice_announcement_key(off_route).startswith("off-route:")
