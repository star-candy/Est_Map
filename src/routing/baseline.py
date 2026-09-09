"""NetworkX 기반 거리 최단 경로 계산."""

from collections.abc import Hashable

import networkx as nx

from src.domain import Coordinates


class RoutingError(RuntimeError):
    """보행 경로를 계산할 수 없을 때 발생한다."""


def nearest_node(graph: nx.MultiDiGraph, point: Coordinates) -> Hashable:
    if not graph.nodes:
        raise RoutingError("보행 그래프가 비어 있습니다.")
    return min(
        graph.nodes,
        key=lambda node: (
            (graph.nodes[node]["y"] - point.latitude) ** 2
            + (graph.nodes[node]["x"] - point.longitude) ** 2
        ),
    )


def shortest_path(
    graph: nx.MultiDiGraph, origin: Coordinates, destination: Coordinates
) -> tuple[list[Hashable], float]:
    start = nearest_node(graph, origin)
    end = nearest_node(graph, destination)
    # 실제 OSM 그래프에서는 단순 거리보다 전용 보행시설을 우선한다. 합성/테스트
    # edge처럼 highway 태그가 없으면 기존 거리 비용을 그대로 사용한다.
    from src.routing.weighted import calculate_baseline_cost

    try:
        path = nx.shortest_path(
            graph,
            start,
            end,
            weight=lambda _u, _v, edges: min(
                calculate_baseline_cost(dict(data)) for data in edges.values()
            ),
            method="dijkstra",
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise RoutingError("두 장소를 잇는 보행 경로를 찾지 못했습니다.") from exc
    distance = float(nx.path_weight(graph, path, weight="length"))
    return path, distance


def path_coordinates(graph: nx.MultiDiGraph, path: list[Hashable]) -> tuple[Coordinates, ...]:
    return tuple(
        Coordinates(latitude=float(graph.nodes[node]["y"]), longitude=float(graph.nodes[node]["x"]))
        for node in path
    )
