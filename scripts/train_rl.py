"""합성 부분 그래프의 tabular Q-learning 정책을 학습하고 저장한다."""

import argparse
from pathlib import Path

from src.domain import RouteMode
from src.geocoding import SampleGeocoder
from src.indicators.scoring import attach_sample_indicators
from src.routing.baseline import nearest_node, shortest_path
from src.routing.graph import load_sample_walking_graph
from src.routing.rl_agent import QLearningEnvironment, TrainingConfig, save_policy, train_q_learning


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=4_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--origin", default="서울시청")
    parser.add_argument("--destination", default="광화문")
    parser.add_argument("--mode", choices=[mode.value for mode in RouteMode], default="여름")
    parser.add_argument("--output", type=Path, default=Path("models/q_policy_summer.joblib"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mode = RouteMode(args.mode)
    geocoder = SampleGeocoder()
    origin = geocoder.geocode(args.origin)
    destination = geocoder.geocode(args.destination)
    graph = attach_sample_indicators(load_sample_walking_graph())
    start = nearest_node(graph, origin)
    target = nearest_node(graph, destination)
    _, baseline_distance = shortest_path(graph, origin, destination)
    config = TrainingConfig(episodes=args.episodes, random_seed=args.seed)
    environment = QLearningEnvironment(graph, start, target, mode, baseline_distance, config)
    q_table, metadata = train_q_learning(environment)
    save_policy(q_table, metadata, args.output)

    before = metadata["evaluation_before"]
    after = metadata["evaluation_after"]
    print(f"모델 저장: {args.output}")
    print(f"상태 수: {metadata['state_count']}, seed: {metadata['random_seed']}")
    print(
        "학습 전/후 평균 보상: "
        f"{before['average_reward']:.2f} → {after['average_reward']:.2f}"
    )
    print(
        "학습 전/후 목적지 도달률: "
        f"{before['destination_reach_rate']:.1%} → {after['destination_reach_rate']:.1%}"
    )
    print(
        "학습 후 평균 우회율/모드 점수: "
        f"{after['average_detour_ratio']:.1%} / {after['average_mode_score']:.1f}점"
    )


if __name__ == "__main__":
    main()

