"""weighted A* 비용, 비교와 fallback 테스트."""

import networkx as nx
import pytest

from src.domain import RouteMode, RouteRequest
from src.indicators.scoring import attach_sample_indicators
from src.routing.graph import load_sample_walking_graph
from src.routing.weighted import (
    calculate_adjusted_cost,
    path_distance,
    weighted_astar_path,
)
from src.services.routing import RoutingService


@pytest.mark.parametrize("mode", list(RouteMode))
def test_adjusted_cost_is_positive(mode: RouteMode) -> None:
    data = {
        "length": 100.0,
        "shade_score": 1.0,
        "ginkgo_risk": 1.0,
        "heating_score": 1.0,
        "icing_risk": 1.0,
        "light_score": 1.0,
        "safety_score": 1.0,
    }
    assert calculate_adjusted_cost(data, mode) > 0


def test_weighted_astar_returns_valid_route() -> None:
    graph = attach_sample_indicators(load_sample_walking_graph())
    request = RouteRequest("서울역", "광화문", RouteMode.SUMMER)
    comparison = RoutingService().find_routes(request)
    path = weighted_astar_path(graph, comparison.origin, comparison.destination, request.mode)

    assert nx.is_path(graph, path)
    assert path_distance(graph, path) > 0
    assert comparison.optimized.comfort_score >= comparison.baseline.comfort_score


def test_winter_heating_discount_can_outweigh_a_nearby_detour() -> None:
    cold = {
        "length": 100.0, "shade_score": 0.0, "ginkgo_risk": 0.0,
        "heating_score": 0.0, "icing_risk": 0.0, "light_score": 0.0, "safety_score": 0.0,
    }
    heated = {**cold, "length": 120.0, "heating_score": 1.0}
    assert calculate_adjusted_cost(heated, RouteMode.WINTER) < calculate_adjusted_cost(
        cold, RouteMode.WINTER
    )


@pytest.mark.parametrize("mode", list(RouteMode))
def test_every_mode_returns_comparison_within_detour_limit(mode: RouteMode) -> None:
    comparison = RoutingService().find_routes(RouteRequest("서울시청", "광화문", mode))

    assert comparison.baseline.distance_m > 0
    assert comparison.optimized.distance_m > 0
    assert comparison.detour_ratio > -1.0
    assert 0.0 <= comparison.baseline.comfort_score <= 100.0
    assert 0.0 <= comparison.optimized.comfort_score <= 100.0
    assert comparison.explanation
