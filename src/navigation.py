"""경로 polyline과 현재 위치를 이용한 로컬 텍스트 보행 안내."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians

from src.domain import Coordinates, RoutePath
from src.routing.graph import haversine_m

OFF_ROUTE_THRESHOLD_M = 35.0
ARRIVAL_THRESHOLD_M = 20.0
TURN_THRESHOLD_DEGREES = 30.0
VOICE_TURN_TRIGGER_M = 60.0


@dataclass(frozen=True, slots=True)
class NavigationGuidance:
    instruction: str
    distance_to_action_m: float
    remaining_distance_m: float
    off_route_distance_m: float
    route_progress: float
    next_position: Coordinates
    arrived: bool = False
    off_route: bool = False


def voice_announcement_key(
    guidance: NavigationGuidance, *, initial: bool = False
) -> str | None:
    """현재 위치에서 새로 재생해야 할 접근성 음성 이벤트를 식별한다."""
    if guidance.arrived:
        return "arrival"
    if guidance.off_route:
        progress_bucket = int(guidance.route_progress * 20)
        return f"off-route:{progress_bucket}"
    if initial:
        return "departure"
    if guidance.distance_to_action_m <= VOICE_TURN_TRIGGER_M:
        point = guidance.next_position
        return f"action:{point.latitude:.6f}:{point.longitude:.6f}"
    return None


def _xy(point: Coordinates, reference: Coordinates) -> tuple[float, float]:
    latitude_scale = 111_320.0
    longitude_scale = latitude_scale * cos(radians(reference.latitude))
    return (
        (point.longitude - reference.longitude) * longitude_scale,
        (point.latitude - reference.latitude) * latitude_scale,
    )


def _turn_angle(first: Coordinates, vertex: Coordinates, third: Coordinates) -> float:
    before = _xy(first, vertex)
    after = _xy(third, vertex)
    incoming = (-before[0], -before[1])
    cross = incoming[0] * after[1] - incoming[1] * after[0]
    dot = incoming[0] * after[0] + incoming[1] * after[1]
    return degrees(atan2(cross, dot))


def _turn_label(angle: float) -> str:
    if abs(angle) >= 150:
        return "유턴"
    return "좌회전" if angle > 0 else "우회전"


def build_guidance(route: RoutePath, current: Coordinates) -> NavigationGuidance:
    """현재 위치를 경로에 투영하고 다음 유의미한 회전 또는 목적지를 안내한다."""
    points = route.path
    if len(points) < 2:
        raise ValueError("안내할 경로 좌표가 부족합니다.")

    segment_lengths = [haversine_m(a, b) for a, b in zip(points, points[1:], strict=False)]
    cumulative = [0.0]
    for length in segment_lengths:
        cumulative.append(cumulative[-1] + length)

    best_distance = float("inf")
    best_progress = 0.0
    best_segment = 0
    best_position = points[0]
    for index, (start, end) in enumerate(zip(points, points[1:], strict=False)):
        sx, sy = _xy(start, current)
        ex, ey = _xy(end, current)
        dx, dy = ex - sx, ey - sy
        denominator = dx * dx + dy * dy
        fraction = min(1.0, max(0.0, -(sx * dx + sy * dy) / denominator)) if denominator else 0.0
        px, py = sx + fraction * dx, sy + fraction * dy
        distance = hypot(px, py)
        if distance < best_distance:
            best_distance = distance
            best_segment = index
            best_progress = cumulative[index] + fraction * segment_lengths[index]
            best_position = Coordinates(
                start.latitude + fraction * (end.latitude - start.latitude),
                start.longitude + fraction * (end.longitude - start.longitude),
            )

    remaining = max(0.0, cumulative[-1] - best_progress)
    if haversine_m(current, points[-1]) <= ARRIVAL_THRESHOLD_M or remaining <= ARRIVAL_THRESHOLD_M:
        return NavigationGuidance(
            "목적지에 도착했습니다.", 0.0, remaining, best_distance, 1.0, points[-1], arrived=True
        )
    if best_distance > OFF_ROUTE_THRESHOLD_M:
        return NavigationGuidance(
            f"경로에서 {best_distance:.0f}m 벗어났습니다. 지도에 표시된 경로로 복귀하세요.",
            best_distance,
            remaining,
            best_distance,
            best_progress / max(cumulative[-1], 1.0),
            best_position,
            off_route=True,
        )

    for vertex_index in range(best_segment + 1, len(points) - 1):
        if cumulative[vertex_index] <= best_progress + 5.0:
            continue
        angle = _turn_angle(
            points[vertex_index - 1], points[vertex_index], points[vertex_index + 1]
        )
        if abs(angle) >= TURN_THRESHOLD_DEGREES:
            distance = cumulative[vertex_index] - best_progress
            return NavigationGuidance(
                f"약 {distance:.0f}m 직진 후 {_turn_label(angle)}하세요.",
                distance,
                remaining,
                best_distance,
                best_progress / max(cumulative[-1], 1.0),
                points[vertex_index],
            )

    return NavigationGuidance(
        f"경로를 따라 목적지까지 약 {remaining:.0f}m 이동하세요.",
        remaining,
        remaining,
        best_distance,
        best_progress / max(cumulative[-1], 1.0),
        points[-1],
    )
