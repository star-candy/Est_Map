"""Q-learning 학습, 저장, 로딩, 추론 및 fallback 테스트."""

from pathlib import Path

import pytest

from src.domain import RouteMode, RouteRequest
from src.geocoding import SampleGeocoder
from src.indicators.scoring import attach_sample_indicators
from src.routing.baseline import nearest_node, shortest_path
from src.routing.graph import load_sample_walking_graph
from src.routing.rl_agent import (
    QLearningEnvironment,
    TrainingConfig,
    infer_policy,
    load_policy,
    save_policy,
    train_q_learning,
)
from src.services.routing import RoutingService


def make_environment(episodes: int = 600) -> QLearningEnvironment:
    geocoder = SampleGeocoder()
    origin = geocoder.geocode("서울시청")
    destination = geocoder.geocode("광화문")
    graph = attach_sample_indicators(load_sample_walking_graph())
    start = nearest_node(graph, origin)
    target = nearest_node(graph, destination)
    _, baseline_distance = shortest_path(graph, origin, destination)
    config = TrainingConfig(episodes=episodes, random_seed=42)
    return QLearningEnvironment(graph, start, target, RouteMode.SUMMER, baseline_distance, config)


def test_training_is_reproducible_and_reaches_destination() -> None:
    first_table, first_metadata = train_q_learning(make_environment())
    second_table, second_metadata = train_q_learning(make_environment())

    assert first_table == second_table
    assert first_metadata["evaluation_after"] == second_metadata["evaluation_after"]
    assert first_metadata["evaluation_after"]["destination_reach_rate"] == 1.0


def test_policy_save_and_load_round_trip(tmp_path: Path) -> None:
    q_table, metadata = train_q_learning(make_environment(episodes=200))
    model_path = tmp_path / "policy.joblib"

    save_policy(q_table, metadata, model_path)
    loaded_table, loaded_metadata = load_policy(model_path)

    assert loaded_table == q_table
    assert loaded_metadata == metadata
    assert model_path.with_suffix(".metadata.json").exists()


def test_trained_policy_inference() -> None:
    environment = make_environment()
    q_table, metadata = train_q_learning(environment)

    result = infer_policy(
        environment.graph,
        environment.start,
        environment.target,
        environment.mode,
        q_table,
        metadata,
        environment.baseline_distance,
    )

    assert result.reason is None
    assert result.path is not None
    assert result.path[-1] == environment.target


def test_unlearned_policy_inference_fails_safely() -> None:
    environment = make_environment(episodes=10)
    _, metadata = train_q_learning(environment)

    result = infer_policy(
        environment.graph,
        environment.start,
        environment.target,
        environment.mode,
        {},
        metadata,
        environment.baseline_distance,
    )

    assert result.path is None
    assert "미학습" in str(result.reason)


def test_graph_mismatch_inference_fails_safely() -> None:
    environment = make_environment(episodes=50)
    q_table, metadata = train_q_learning(environment)
    metadata["graph_fingerprint"] = "different-graph"

    result = infer_policy(
        environment.graph,
        environment.start,
        environment.target,
        environment.mode,
        q_table,
        metadata,
        environment.baseline_distance,
    )

    assert result.path is None
    assert "그래프" in str(result.reason)


def test_missing_model_falls_back_to_weighted_astar(tmp_path: Path) -> None:
    service = RoutingService(model_path=tmp_path / "missing.joblib")
    result = service.find_routes(RouteRequest("서울시청", "광화문", RouteMode.SUMMER))

    assert result.method == "weighted A* fallback"
    assert "모델" in str(result.fallback_reason)
    assert result.detour_ratio > -1.0


def test_repository_model_is_connected_to_service() -> None:
    result = RoutingService().find_routes(RouteRequest("서울시청", "광화문", RouteMode.SUMMER))

    assert result.method == "RL 정책"
    assert result.model_version == "q-learning-synthetic-v1"
    assert result.fallback_reason is None


def test_load_missing_policy_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_policy(tmp_path / "missing.joblib")


def test_corrupt_model_falls_back_to_weighted_astar(tmp_path: Path) -> None:
    model_path = tmp_path / "corrupt.joblib"
    model_path.write_bytes(b"not-a-joblib-model")

    result = RoutingService(model_path=model_path).find_routes(
        RouteRequest("서울시청", "광화문", RouteMode.SUMMER)
    )

    assert result.method == "weighted A* fallback"
    assert "모델" in str(result.fallback_reason)
