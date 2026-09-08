"""모드 지표를 반영한 weighted A* 경로 탐색."""

from collections.abc import Hashable
from typing import Any

import networkx as nx

from src.domain import Coordinates, RouteMode
from src.routing.baseline import RoutingError, nearest_node
from src.routing.graph import haversine_m

MIN_COST_FACTOR = 0.20
DEFAULT_MAX_DETOUR_RATIO = 0.25


def mode_cost_factor(data: dict[str, Any], mode: RouteMode) -> float:
    if mode is RouteMode.SUMMER:
        factor = 1.0 - 0.35 * float(data["shade_score"])
    elif mode is RouteMode.AUTUMN:
        factor = 1.0 + 0.45 * float(data["ginkgo_risk"])
    elif mode is RouteMode.WINTER:
        factor = 1.0 + 0.55 * float(data["icing_risk"]) - 0.30 * float(data["heating_score"])
    else:
        factor = (
            1.0
            + 0.30 * (1.0 - float(data["light_score"]))
            + 0.35 * (1.0 - float(data["safety_score"]))
        )
    return max(MIN_COST_FACTOR, factor)


def calculate_adjusted_cost(data: dict[str, Any], mode: RouteMode) -> float:
    return max(0.001, float(data["length"]) * mode_cost_factor(data, mode))


def _heuristic(graph: nx.MultiDiGraph, first: Hashable, second: Hashable) -> float:
    first_point = Coordinates(graph.nodes[first]["y"], graph.nodes[first]["x"])
    second_point = Coordinates(graph.nodes[second]["y"], graph.nodes[second]["x"])
    return haversine_m(first_point, second_point) * MIN_COST_FACTOR


def weighted_astar_path(
    graph: nx.MultiDiGraph, origin: Coordinates, destination: Coordinates, mode: RouteMode
) -> list[Hashable]:
    for _, _, _, data in graph.edges(keys=True, data=True):
        data["adjusted_cost"] = calculate_adjusted_cost(data, mode)
    start = nearest_node(graph, origin)
    end = nearest_node(graph, destination)
    try:
        return nx.astar_path(
            graph,
            start,
            end,
            heuristic=lambda first, second: _heuristic(graph, first, second),
            weight="adjusted_cost",
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise RoutingError("선택한 모드의 맞춤 경로를 찾지 못했습니다.") from exc


def path_distance(graph: nx.MultiDiGraph, path: list[Hashable]) -> float:
    return float(nx.path_weight(graph, path, weight="length"))


def enforce_detour_limit(
    baseline_path: list[Hashable],
    baseline_distance: float,
    candidate_path: list[Hashable],
    candidate_distance: float,
    max_detour_ratio: float = DEFAULT_MAX_DETOUR_RATIO,
) -> tuple[list[Hashable], float, str | None]:
    if baseline_distance <= 0:
        reason = "일반 경로 거리가 0이어서 일반 경로를 사용했습니다."
        return baseline_path, baseline_distance, reason
    detour_ratio = candidate_distance / baseline_distance - 1.0
    if detour_ratio > max_detour_ratio:
        reason = (
            f"맞춤 경로가 최대 우회율 {max_detour_ratio:.0%}를 초과해 "
            "일반 경로를 사용했습니다."
        )
        return baseline_path, baseline_distance, reason
    return candidate_path, candidate_distance, None
