"""외부 네트워크를 사용하지 않는 일반 경로 테스트."""

import networkx as nx
import pytest

from src.domain import Coordinates, RouteMode, RouteRequest
from src.geocoding import is_in_seoul
from src.routing.baseline import shortest_path
from src.services.routing import RoutingService


def test_shortest_path_uses_edge_length() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("a", y=37.5, x=127.0)
    graph.add_node("b", y=37.51, x=127.01)
    graph.add_node("c", y=37.52, x=127.02)
    graph.add_edge("a", "b", length=100.0)
    graph.add_edge("b", "c", length=150.0)
    graph.add_edge("a", "c", length=400.0)

    path, distance = shortest_path(graph, Coordinates(37.5, 127.0), Coordinates(37.52, 127.02))

    assert path == ["a", "b", "c"]
    assert distance == pytest.approx(250.0)


def test_shortest_path_prefers_dedicated_walkway_over_primary_road() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node("a", y=37.5, x=127.0)
    graph.add_node("road", y=37.501, x=127.001)
    graph.add_node("walk", y=37.501, x=126.999)
    graph.add_node("d", y=37.502, x=127.0)
    graph.add_edge("a", "road", length=100.0, highway="primary")
    graph.add_edge("road", "d", length=100.0, highway="primary")
    graph.add_edge("a", "walk", length=140.0, highway="footway")
    graph.add_edge("walk", "d", length=140.0, highway="footway")

    path, distance = shortest_path(graph, Coordinates(37.5, 127.0), Coordinates(37.502, 127.0))

    assert path == ["a", "walk", "d"]
    assert distance == pytest.approx(280.0)


def test_sample_service_always_returns_route() -> None:
    comparison = RoutingService().find_routes(RouteRequest("서울역", "광화문", RouteMode.SUMMER))

    assert comparison.baseline.distance_m > 0
    assert comparison.baseline.duration_min == pytest.approx(comparison.baseline.distance_m / 75.0)
    assert len(comparison.optimized.path) >= 2
    assert comparison.is_sample is True


def test_seoul_bounds() -> None:
    assert is_in_seoul(Coordinates(37.5665, 126.9780))
    assert not is_in_seoul(Coordinates(35.1796, 129.0756))
