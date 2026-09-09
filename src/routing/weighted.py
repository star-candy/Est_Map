"""모드 지표를 반영한 weighted A* 경로 탐색."""

from collections.abc import Hashable
from typing import Any

import networkx as nx

from src.domain import Coordinates, RouteMode
from src.routing.baseline import RoutingError, nearest_node
from src.routing.graph import haversine_m

MIN_COST_FACTOR = 0.20

# OSM의 ``network_type=walk``에는 보행 가능한 일반 도로도 포함된다. 전용
# 보행시설을 우선하되, 태그가 부족한 도로를 완전히 제거해 그래프를 끊지는 않는다.
PEDESTRIAN_PRIORITY_FACTORS = {
    "footway": 1.00,
    "pedestrian": 1.00,
    "path": 1.00,
    "steps": 1.05,
    "corridor": 1.00,
    "crossing": 1.00,
    "elevator": 1.00,
    "platform": 1.00,
    "living_street": 1.04,
    "residential": 1.08,
    "service": 1.12,
    "unclassified": 1.18,
    "track": 1.25,
    "cycleway": 1.30,
    "tertiary": 1.35,
    "tertiary_link": 1.45,
    "secondary": 1.55,
    "secondary_link": 1.70,
    "primary": 1.80,
    "primary_link": 2.00,
    "busway": 2.00,
}


def pedestrian_priority_factor(data: dict[str, Any]) -> float:
    """보행시설 태그가 명확한 edge를 우선하는 보수적 비용 계수."""
    highway = data.get("highway")
    kinds = highway if isinstance(highway, list) else [highway]
    factors = [PEDESTRIAN_PRIORITY_FACTORS.get(str(kind or "").strip(), 1.75) for kind in kinds]
    return min(factors, default=1.75)


def calculate_baseline_cost(data: dict[str, Any]) -> float:
    return max(0.001, float(data["length"]) * pedestrian_priority_factor(data))


def mode_cost_factor(data: dict[str, Any], mode: RouteMode) -> float:
    if mode is RouteMode.SUMMER:
        factor = 5.0 - 4.80 * float(data["shade_score"])
    elif mode is RouteMode.AUTUMN:
        factor = 1.0 + 8.00 * float(data["ginkgo_risk"])
    elif mode is RouteMode.WINTER:
        factor = (
            5.0
            + 5.00 * float(data["icing_risk"])
            - 4.80 * float(data["heating_score"])
        )
    else:
        factor = 0.20 + 4.80 * (1.0 - float(data["safety_score"]))
    return max(MIN_COST_FACTOR, factor)


def calculate_adjusted_cost(data: dict[str, Any], mode: RouteMode) -> float:
    return max(
        0.001,
        float(data["length"]) * pedestrian_priority_factor(data) * mode_cost_factor(data, mode),
    )


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
