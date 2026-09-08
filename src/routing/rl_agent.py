"""제한된 부분 그래프에서 동작하는 재현 가능한 tabular Q-learning."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Hashable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import networkx as nx

from src.domain import Coordinates, RouteMode
from src.indicators.scoring import edge_comfort, path_comfort_score
from src.routing.graph import haversine_m
from src.routing.weighted import path_distance

State = tuple[str, int, int]
QTable = dict[State, dict[str, float]]
MODEL_SCHEMA_VERSION = 1
DEFAULT_RANDOM_SEED = 42


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    episodes: int = 4_000
    learning_rate: float = 0.18
    discount_factor: float = 0.95
    epsilon_start: float = 1.0
    epsilon_end: float = 0.03
    max_steps: int = 40
    random_seed: int = DEFAULT_RANDOM_SEED
    max_detour_ratio: float = 0.25


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    average_reward: float
    destination_reach_rate: float
    average_detour_ratio: float
    average_mode_score: float


@dataclass(frozen=True, slots=True)
class InferenceResult:
    path: list[Hashable] | None
    reason: str | None


def graph_fingerprint(graph: nx.MultiDiGraph) -> str:
    nodes = sorted(
        (str(node), round(float(data["y"]), 7), round(float(data["x"]), 7))
        for node, data in graph.nodes(data=True)
    )
    edges = sorted(
        (
            str(start),
            str(end),
            str(key),
            round(float(data["length"]), 3),
            *(round(float(data[field]), 4) for field in (
                "shade_score",
                "ginkgo_risk",
                "heating_score",
                "icing_risk",
                "light_score",
                "safety_score",
            )),
        )
        for start, end, key, data in graph.edges(keys=True, data=True)
    )
    payload = json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


class QLearningEnvironment:
    def __init__(
        self,
        graph: nx.MultiDiGraph,
        start: Hashable,
        target: Hashable,
        mode: RouteMode,
        baseline_distance: float,
        config: TrainingConfig,
    ) -> None:
        self.graph = graph
        self.start = start
        self.target = target
        self.mode = mode
        self.baseline_distance = baseline_distance
        self.config = config
        self.current = start
        self.distance_travelled = 0.0
        self.visited: set[Hashable] = {start}
        self.path: list[Hashable] = [start]

    def reset(self) -> State:
        self.current = self.start
        self.distance_travelled = 0.0
        self.visited = {self.start}
        self.path = [self.start]
        return self.state()

    def _edge(self, start: Hashable, end: Hashable) -> Mapping[str, Any]:
        return min(self.graph.get_edge_data(start, end).values(), key=lambda data: data["length"])

    def actions(self) -> list[str]:
        return sorted(str(node) for node in self.graph.successors(self.current))

    def _distance_bin(self) -> int:
        current = Coordinates(
            self.graph.nodes[self.current]["y"], self.graph.nodes[self.current]["x"]
        )
        target = Coordinates(self.graph.nodes[self.target]["y"], self.graph.nodes[self.target]["x"])
        ratio = haversine_m(current, target) / max(self.baseline_distance, 1.0)
        if ratio <= 0.25:
            return 0
        if ratio <= 0.60:
            return 1
        if ratio <= 1.0:
            return 2
        return 3

    def _indicator_bin(self) -> int:
        actions = list(self.graph.successors(self.current))
        if not actions:
            return 0
        score = max(edge_comfort(self._edge(self.current, action), self.mode) for action in actions)
        return min(2, int(score * 3))

    def state(self) -> State:
        return str(self.current), self._distance_bin(), self._indicator_bin()

    def step(self, action: str) -> tuple[State, float, bool, bool]:
        lookup = {str(node): node for node in self.graph.successors(self.current)}
        if action not in lookup:
            return self.state(), -30.0, True, False
        next_node = lookup[action]
        edge = self._edge(self.current, next_node)
        length = float(edge["length"])
        reward = -(length / 100.0) + 2.0 * edge_comfort(edge, self.mode)
        if next_node in self.visited:
            reward -= 4.0
        self.distance_travelled += length
        self.current = next_node
        self.path.append(next_node)
        self.visited.add(next_node)
        reached_target = next_node == self.target
        excessive = self.distance_travelled > self.baseline_distance * (
            1.0 + self.config.max_detour_ratio
        )
        reached = reached_target and not excessive
        if reached:
            reward += 100.0
        elif excessive:
            reward -= 30.0
        return self.state(), reward, reached_target or excessive, reached


def _select_action(
    q_table: QTable, state: State, actions: list[str], epsilon: float, rng: random.Random
) -> str:
    if rng.random() < epsilon or state not in q_table:
        return rng.choice(actions)
    values = q_table[state]
    best_value = max(values.get(action, 0.0) for action in actions)
    best_actions = [action for action in actions if values.get(action, 0.0) == best_value]
    return rng.choice(best_actions)


def run_episode(
    environment: QLearningEnvironment,
    q_table: QTable | None,
    rng: random.Random,
    epsilon: float,
    learn: bool,
) -> tuple[float, bool, list[Hashable]]:
    state = environment.reset()
    total_reward = 0.0
    reached = False
    for _ in range(environment.config.max_steps):
        actions = environment.actions()
        if not actions:
            total_reward -= 20.0
            break
        table = q_table if q_table is not None else {}
        action = _select_action(table, state, actions, epsilon, rng)
        next_state, reward, done, reached = environment.step(action)
        total_reward += reward
        if learn and q_table is not None:
            q_table.setdefault(state, {})
            old_value = q_table[state].get(action, 0.0)
            next_values = q_table.get(next_state, {})
            future = max(next_values.values(), default=0.0) if not done else 0.0
            target = reward + environment.config.discount_factor * future
            q_table[state][action] = old_value + environment.config.learning_rate * (
                target - old_value
            )
        state = next_state
        if done:
            break
    else:
        total_reward -= 20.0
    return total_reward, reached, environment.path.copy()


def evaluate_policy(
    environment: QLearningEnvironment,
    q_table: QTable | None,
    episodes: int,
    random_seed: int,
) -> EvaluationMetrics:
    rng = random.Random(random_seed)
    rewards: list[float] = []
    detours: list[float] = []
    scores: list[float] = []
    reached_count = 0
    for _ in range(episodes):
        epsilon = 1.0 if q_table is None else 0.0
        reward, reached, path = run_episode(environment, q_table, rng, epsilon, learn=False)
        rewards.append(reward)
        if reached:
            reached_count += 1
            distance = path_distance(environment.graph, path)
            detours.append(distance / environment.baseline_distance - 1.0)
            scores.append(path_comfort_score(environment.graph, path, environment.mode))
    return EvaluationMetrics(
        average_reward=sum(rewards) / len(rewards),
        destination_reach_rate=reached_count / episodes,
        average_detour_ratio=sum(detours) / len(detours) if detours else 0.0,
        average_mode_score=sum(scores) / len(scores) if scores else 0.0,
    )


def train_q_learning(environment: QLearningEnvironment) -> tuple[QTable, dict[str, Any]]:
    config = environment.config
    before = evaluate_policy(environment, None, 200, config.random_seed + 1)
    q_table: QTable = {}
    rng = random.Random(config.random_seed)
    for episode in range(config.episodes):
        progress = episode / max(config.episodes - 1, 1)
        epsilon = config.epsilon_start + progress * (config.epsilon_end - config.epsilon_start)
        run_episode(environment, q_table, rng, epsilon, learn=True)
    after = evaluate_policy(environment, q_table, 200, config.random_seed + 2)
    metadata = {
        "schema_version": MODEL_SCHEMA_VERSION,
        "model_version": "q-learning-synthetic-v1",
        "trained_at": datetime.now(UTC).isoformat(),
        "random_seed": config.random_seed,
        "mode": environment.mode.value,
        "start_node": str(environment.start),
        "target_node": str(environment.target),
        "graph_fingerprint": graph_fingerprint(environment.graph),
        "training_config": asdict(config),
        "evaluation_before": asdict(before),
        "evaluation_after": asdict(after),
        "state_count": len(q_table),
    }
    return q_table, metadata


def save_policy(q_table: QTable, metadata: dict[str, Any], model_path: Path) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"q_table": q_table, "metadata": metadata}, model_path)
    metadata_path = model_path.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def load_policy(model_path: Path) -> tuple[QTable, dict[str, Any]]:
    if not model_path.exists():
        raise FileNotFoundError("학습된 RL 모델 파일이 없습니다.")
    payload = joblib.load(model_path)
    if payload.get("metadata", {}).get("schema_version") != MODEL_SCHEMA_VERSION:
        raise ValueError("RL 모델 schema 버전이 현재 코드와 다릅니다.")
    return payload["q_table"], payload["metadata"]


def infer_policy(
    graph: nx.MultiDiGraph,
    start: Hashable,
    target: Hashable,
    mode: RouteMode,
    q_table: QTable,
    metadata: Mapping[str, Any],
    baseline_distance: float,
) -> InferenceResult:
    if metadata.get("graph_fingerprint") != graph_fingerprint(graph):
        return InferenceResult(None, "현재 그래프가 학습 모델의 그래프와 다릅니다.")
    if metadata.get("mode") != mode.value:
        return InferenceResult(None, "선택 모드에 맞는 학습 정책이 없습니다.")
    if metadata.get("start_node") != str(start) or metadata.get("target_node") != str(target):
        return InferenceResult(None, "이 출발지·도착지 구간은 학습되지 않았습니다.")

    config = TrainingConfig(**metadata["training_config"])
    environment = QLearningEnvironment(graph, start, target, mode, baseline_distance, config)
    state = environment.reset()
    visited = {start}
    for _ in range(config.max_steps):
        actions = environment.actions()
        learned = q_table.get(state)
        if not actions or not learned or not any(action in learned for action in actions):
            return InferenceResult(None, "미학습 상태를 만나 정책 추론을 중단했습니다.")
        action = min(actions, key=lambda item: (-learned.get(item, float("-inf")), item))
        next_state, _, done, reached = environment.step(action)
        if environment.current in visited and not reached:
            return InferenceResult(None, "RL 정책에서 반복 루프가 감지됐습니다.")
        visited.add(environment.current)
        state = next_state
        if done:
            if reached:
                distance = path_distance(graph, environment.path)
                if distance > baseline_distance * (1.0 + config.max_detour_ratio):
                    return InferenceResult(None, "RL 경로가 최대 우회율을 초과했습니다.")
                return InferenceResult(environment.path.copy(), None)
            return InferenceResult(None, "RL 경로가 과도하게 우회해 목적지에 도달하지 못했습니다.")
    return InferenceResult(None, "RL 정책이 최대 이동 횟수 안에 목적지에 도달하지 못했습니다.")
