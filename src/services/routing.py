"""지오코딩, 공간 지표, 일반 및 맞춤 경로 계산을 조율하는 서비스."""

from collections.abc import Hashable
from pathlib import Path

import networkx as nx

from config.settings import SETTINGS
from src.domain import Coordinates, RouteComparison, RoutePath, RouteRequest
from src.geocoding import GeocodingError, OSMGeocoder, SampleGeocoder, validate_seoul
from src.indicators.real import attach_real_indicators
from src.indicators.scoring import attach_sample_indicators, path_comfort_score
from src.routing.baseline import nearest_node, path_coordinates, shortest_path
from src.routing.graph import (
    build_fallback_graph,
    load_offline_walking_graph,
    load_osm_walking_graph,
    load_sample_walking_graph,
)
from src.routing.rl_agent import infer_policy, load_policy, train_or_load_runtime_policy
from src.routing.weighted import (
    DEFAULT_MAX_DETOUR_RATIO,
    enforce_detour_limit,
    path_distance,
    weighted_astar_path,
)

WALKING_SPEED_M_PER_MIN = 75.0


class RouteServiceError(RuntimeError):
    """UI에 안전하게 표시할 수 있는 경로 서비스 오류."""


def _explanation(request: RouteRequest, baseline_score: float, optimized_score: float) -> str:
    focus = {
        "여름": "그늘·수관 proxy가 높은 구간",
        "가을": "합성 은행나무 위험이 낮은 구간",
        "겨울": "열선 proxy가 높고 결빙 위험이 낮은 구간",
        "안심": "가로등·야간 안전 proxy가 높은 구간",
    }[request.mode.value]
    change = optimized_score - baseline_score
    if change > 0.05:
        return f"{focus}을 우선해 쾌적 점수가 일반 경로보다 {change:.1f}점 높습니다."
    return f"{focus}을 반영했지만 우회 제한 안에서 일반 경로와 유사한 결과가 선택됐습니다."


def _make_path(
    graph: nx.MultiDiGraph, path: list[Hashable], distance: float, request: RouteRequest
) -> RoutePath:
    return RoutePath(
        path=path_coordinates(graph, path),
        distance_m=distance,
        duration_min=distance / WALKING_SPEED_M_PER_MIN,
        comfort_score=path_comfort_score(graph, path, request.mode),
    )


class RoutingService:
    def __init__(self, model_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.model_path = model_path or project_root / SETTINGS.rl_model_path

    def _resolve_point(
        self, label: str, query: str, direct: Coordinates | None, use_osm: bool
    ) -> tuple[Coordinates, str | None]:
        if direct is not None:
            point, notice = direct, None
        elif use_osm:
            try:
                point, notice = OSMGeocoder().geocode(query), None
            except GeocodingError as external_error:
                try:
                    point = SampleGeocoder().geocode(query)
                    notice = f"{external_error} '{query}'의 샘플 좌표를 사용했습니다."
                except GeocodingError as sample_error:
                    raise RouteServiceError(
                        f"{label} 주소를 찾지 못했습니다. "
                        "예제 장소를 선택하거나 좌표를 입력해 주세요."
                    ) from sample_error
        else:
            try:
                point, notice = SampleGeocoder().geocode(query), None
            except GeocodingError as exc:
                raise RouteServiceError(str(exc)) from exc
        try:
            validate_seoul(point, label)
        except GeocodingError as exc:
            raise RouteServiceError(str(exc)) from exc
        return point, notice

    def find_routes(self, request: RouteRequest) -> RouteComparison:
        origin, origin_notice = self._resolve_point(
            "출발지", request.origin, request.origin_coordinates, request.use_osm
        )
        destination, destination_notice = self._resolve_point(
            "도착지", request.destination, request.destination_coordinates, request.use_osm
        )
        if origin == destination:
            raise RouteServiceError("출발지와 도착지는 서로 달라야 합니다.")

        notices = [notice for notice in (origin_notice, destination_notice) if notice]
        is_sample = not request.use_osm
        source = "합성 보행 그래프와 합성 공간 지표"
        if request.use_osm:
            try:
                graph = load_offline_walking_graph(origin, destination)
                source = "오프라인 OpenStreetMap PBF 보행 그래프와 합성 공간 지표"
            except Exception as offline_error:
                try:
                    graph = load_osm_walking_graph(origin, destination)
                    source = "온라인 OpenStreetMap 보행 그래프와 합성 공간 지표"
                    notices.append(
                        "오프라인 보행망을 사용할 수 없어 온라인 연결을 사용했습니다: "
                        f"{offline_error}"
                    )
                except Exception:
                    graph = build_fallback_graph(origin, destination)
                    is_sample = True
                    source = "합성 fallback 보행 그래프와 합성 공간 지표"
                    notices.append(
                        "오프라인·온라인 보행망 연결에 실패하여 "
                        "합성 샘플 경로를 표시합니다."
                    )
        else:
            graph = load_sample_walking_graph()

        if request.use_real_data:
            try:
                graph = attach_real_indicators(graph)
                source = source.replace("합성 공간 지표", "서울 공공데이터 공간 지표")
            except (FileNotFoundError, ValueError) as exc:
                graph = attach_sample_indicators(graph)
                notices.append(f"실제 데이터 처리에 실패하여 합성 지표를 사용합니다: {exc}")
        else:
            graph = attach_sample_indicators(graph)
        try:
            baseline_nodes, baseline_distance = shortest_path(graph, origin, destination)
        except Exception as exc:
            raise RouteServiceError("일반 보행 경로를 계산하지 못했습니다.") from exc

        rl_reason: str | None = None
        model_version: str | None = None
        method = "RL 정책"
        try:
            start = nearest_node(graph, origin)
            target = nearest_node(graph, destination)
            if request.use_real_data and not is_sample:
                inference, metadata = train_or_load_runtime_policy(
                    graph,
                    baseline_nodes,
                    start,
                    target,
                    request.mode,
                    baseline_distance,
                    self.model_path.parent / "runtime",
                )
            else:
                q_table, metadata = load_policy(self.model_path)
                inference = infer_policy(
                    graph,
                    start,
                    target,
                    request.mode,
                    q_table,
                    metadata,
                    baseline_distance,
                )
            model_version = str(metadata["model_version"])
            candidate_nodes = inference.path
            rl_reason = inference.reason
        except Exception as exc:
            candidate_nodes = None
            rl_reason = f"RL 모델을 사용할 수 없습니다: {exc}"

        if candidate_nodes is None:
            method = "weighted A* fallback"
            try:
                candidate_nodes = weighted_astar_path(graph, origin, destination, request.mode)
            except Exception as exc:
                raise RouteServiceError("맞춤 보행 경로를 계산하지 못했습니다.") from exc
        candidate_distance = path_distance(graph, candidate_nodes)

        optimized_nodes, optimized_distance, detour_reason = enforce_detour_limit(
            baseline_nodes,
            baseline_distance,
            candidate_nodes,
            candidate_distance,
            DEFAULT_MAX_DETOUR_RATIO,
        )
        baseline = _make_path(graph, baseline_nodes, baseline_distance, request)
        optimized = _make_path(graph, optimized_nodes, optimized_distance, request)
        detour_ratio = optimized_distance / baseline_distance - 1.0 if baseline_distance else 0.0
        fallback_reasons = [reason for reason in (rl_reason, detour_reason) if reason]
        if detour_reason:
            method = "일반 경로 fallback"
        return RouteComparison(
            origin=origin,
            destination=destination,
            baseline=baseline,
            optimized=optimized,
            mode=request.mode,
            detour_ratio=detour_ratio,
            source=source,
            is_sample=is_sample,
            method=method,
            explanation=_explanation(request, baseline.comfort_score, optimized.comfort_score),
            fallback_reason=" ".join(fallback_reasons) or None,
            notice=" ".join(notices) or None,
            model_version=model_version,
            indicator_source=str(graph.graph.get("indicator_source", "sample")),
        )


BaselineRouteService = RoutingService
