"""공간 지표 정규화, edge 결합 및 모드 점수 계산."""

from collections.abc import Hashable, Mapping, Sequence
from typing import Any

import networkx as nx
from pyproj import Transformer
from shapely.geometry import LineString, shape
from shapely.ops import transform

from src.domain import RouteMode
from src.indicators.sample import load_sample_indicators

INDICATOR_FIELDS = (
    "shade_score",
    "ginkgo_risk",
    "heating_score",
    "icing_risk",
    "light_score",
    "safety_score",
)
DEFAULT_INDICATORS = {
    "shade_score": 0.0,
    "ginkgo_risk": 0.0,
    "heating_score": 0.0,
    "icing_risk": 0.0,
    "light_score": 0.35,
    "safety_score": 0.35,
}
_TO_METERS = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


def normalize_indicator(value: float) -> float:
    """지표를 0~1 범위로 제한한다."""
    return min(1.0, max(0.0, float(value)))


def _edge_geometry(graph: nx.MultiDiGraph, start: Hashable, end: Hashable, data: Mapping[str, Any]):
    geometry = data.get("geometry")
    if geometry is not None:
        return geometry
    return LineString(
        [
            (graph.nodes[start]["x"], graph.nodes[start]["y"]),
            (graph.nodes[end]["x"], graph.nodes[end]["y"]),
        ]
    )


def attach_sample_indicators(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """합성 feature를 edge ID 또는 공간 근접도로 결합한 graph 사본을 반환한다."""
    result = graph.copy()
    features = load_sample_indicators()["features"]
    projected_features = [
        (feature, transform(_TO_METERS.transform, shape(feature["geometry"])))
        for feature in features
    ]
    for start, end, key, edge_data in result.edges(keys=True, data=True):
        values = DEFAULT_INDICATORS.copy()
        edge_id = edge_data.get("sample_edge_id")
        edge_geometry = _edge_geometry(result, start, end, edge_data)
        projected_edge = transform(_TO_METERS.transform, edge_geometry)
        for feature, projected_feature in projected_features:
            properties = feature["properties"]
            id_match = edge_id is not None and edge_id in properties.get("edge_ids", [])
            is_near = projected_edge.distance(projected_feature) <= properties.get("influence_m", 0)
            if id_match or (edge_id is None and is_near):
                for field, value in properties.get("scores", {}).items():
                    if field in INDICATOR_FIELDS:
                        values[field] = max(values[field], normalize_indicator(value))
        for field, value in values.items():
            result.edges[start, end, key][field] = normalize_indicator(value)
    return result


def edge_comfort(data: Mapping[str, Any], mode: RouteMode) -> float:
    if mode is RouteMode.SUMMER:
        return float(data["shade_score"])
    if mode is RouteMode.AUTUMN:
        return 1.0 - float(data["ginkgo_risk"])
    if mode is RouteMode.WINTER:
        return 0.45 * float(data["heating_score"]) + 0.55 * (1.0 - float(data["icing_risk"]))
    return 0.5 * (float(data["light_score"]) + float(data["safety_score"]))


def path_comfort_score(graph: nx.MultiDiGraph, path: Sequence[Hashable], mode: RouteMode) -> float:
    weighted_score = 0.0
    total_length = 0.0
    for start, end in zip(path, path[1:], strict=False):
        edge = min(graph.get_edge_data(start, end).values(), key=lambda item: item["length"])
        length = float(edge["length"])
        weighted_score += length * edge_comfort(edge, mode)
        total_length += length
    return 100.0 * weighted_score / total_length if total_length else 0.0
