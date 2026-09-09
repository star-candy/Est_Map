"""weighted A* 비용, 비교와 fallback 테스트."""

import networkx as nx
import pytest

from src.domain import RouteMode, RouteRequest
from src.indicators.scoring import attach_sample_indicators
from src.routing.graph import load_sample_walking_graph
from src.routing.weighted import (
    calculate_adjusted_cost,
    calculate_baseline_cost,
    path_distance,
    weighted_astar_path,
)
from src.services.routing import RoutingService, candidate_improves_mode


def test_unknown_or_major_road_has_higher_pedestrian_cost() -> None:
    footway = {"length": 100.0, "highway": "footway"}
    primary = {"length": 100.0, "highway": "primary"}
    unknown = {"length": 100.0, "highway": "nan"}

    assert calculate_baseline_cost(footway) < calculate_baseline_cost(primary)
    assert calculate_baseline_cost(footway) < calculate_baseline_cost(unknown)


def test_mode_improvement_can_justify_detour_over_25_percent() -> None:
    assert candidate_improves_mode(20.0, 1_000.0, 21.0, 1_600.0)


def test_no_mode_improvement_falls_back_to_shorter_route() -> None:
    assert not candidate_improves_mode(20.0, 1_000.0, 20.0, 1_001.0)


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


def test_sparse_custom_indicator_has_strong_route_priority() -> None:
    plain = {
        "length": 100.0,
        "shade_score": 0.0,
        "ginkgo_risk": 0.0,
        "heating_score": 0.0,
        "icing_risk": 0.0,
        "light_score": 0.0,
        "safety_score": 0.0,
    }
    shaded = {**plain, "shade_score": 1.0}
    heated = {**plain, "heating_score": 1.0}
    safe = {**plain, "safety_score": 1.0}

    assert calculate_adjusted_cost(shaded, RouteMode.SUMMER) < 0.1 * calculate_adjusted_cost(
        plain, RouteMode.SUMMER
    )
    assert calculate_adjusted_cost(heated, RouteMode.WINTER) < 0.1 * calculate_adjusted_cost(
        plain, RouteMode.WINTER
    )
    assert calculate_adjusted_cost(safe, RouteMode.SAFETY) < 0.1 * calculate_adjusted_cost(
        plain, RouteMode.SAFETY
    )


@pytest.mark.parametrize("mode", list(RouteMode))
def test_every_mode_returns_comparison_within_detour_limit(mode: RouteMode) -> None:
    comparison = RoutingService().find_routes(RouteRequest("서울시청", "광화문", mode))

    assert comparison.baseline.distance_m > 0
    assert comparison.optimized.distance_m > 0
    assert comparison.detour_ratio >= 0.0
    assert 0.0 <= comparison.baseline.comfort_score <= 100.0
    assert 0.0 <= comparison.optimized.comfort_score <= 100.0
    assert comparison.explanation


def test_winter_explanation_uses_plain_korean_instead_of_proxy() -> None:
    comparison = RoutingService().find_routes(
        RouteRequest("서울시청", "광화문", RouteMode.WINTER)
    )
    assert "도로 열선 설치 구간" in comparison.explanation
    assert "proxy" not in comparison.explanation
