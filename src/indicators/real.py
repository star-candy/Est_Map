"""전처리된 서울 공공데이터를 보행 edge 지표로 결합한다."""

from __future__ import annotations

import csv
import gzip
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import networkx as nx
from shapely import STRtree
from shapely.geometry import Point
from shapely.ops import transform

from src.indicators.scoring import _TO_METERS, _edge_geometry, normalize_indicator

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
POINT_FILES = {
    "trees": "trees.csv.gz",
    "shades": "shades.csv.gz",
    "streetlights": "streetlights.csv.gz",
    "bikes": "bike_stations.csv.gz",
    "safe_return": "safe_return.csv.gz",
    "cctv": "cctv.csv.gz",
}


@dataclass(frozen=True, slots=True)
class RealPoint:
    latitude: float
    longitude: float
    label: str
    detail: str = ""
    is_female_ginkgo: bool = False


def real_data_available() -> bool:
    required = (*POINT_FILES.values(), "heating.csv.gz")
    return all((PROCESSED_DIR / name).is_file() for name in required)


@lru_cache(maxsize=32)
def load_real_points(
    dataset: str, bounds: tuple[float, float, float, float]
) -> tuple[RealPoint, ...]:
    """주어진 (south, west, north, east) 범위의 실제 지점만 읽는다."""
    path = PROCESSED_DIR / POINT_FILES[dataset]
    south, west, north, east = bounds
    points: list[RealPoint] = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
            if not (south <= latitude <= north and west <= longitude <= east):
                continue
            if dataset == "trees":
                label = row["species"]
                detail = row["address"]
                female = row["is_female_ginkgo"] == "true"
            elif dataset == "shades":
                label = row["name"] or row["type"]
                detail, female = row["address"], False
            elif dataset == "bikes":
                label = row["name"]
                detail, female = f"정적 거치대 {row['capacity']}개", False
            elif dataset == "safe_return":
                label = row["label"]
                detail, female = "서울시 안심귀갓길 서비스 통합데이터", False
            elif dataset == "cctv":
                label = row["location"] or "불법주정차 단속 CCTV"
                detail, female = row["address"], False
            else:
                label, detail, female = row["id"], "가로등 위치", False
            points.append(RealPoint(latitude, longitude, label, detail, female))
    return tuple(points)


@lru_cache(maxsize=1)
def load_heating_road_names() -> frozenset[str]:
    names: set[str] = set()
    with gzip.open(PROCESSED_DIR / "heating.csv.gz", "rt", encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            name = re.sub(r"\s+", "", row["road_name"])
            if name:
                names.add(name)
    return frozenset(names)


def _graph_bounds(
    graph: nx.MultiDiGraph, margin: float = 0.001
) -> tuple[float, float, float, float]:
    latitudes = [float(data["y"]) for _, data in graph.nodes(data=True)]
    longitudes = [float(data["x"]) for _, data in graph.nodes(data=True)]
    return (
        round(min(latitudes) - margin, 4),
        round(min(longitudes) - margin, 4),
        round(max(latitudes) + margin, 4),
        round(max(longitudes) + margin, 4),
    )


def _physical_edge_id(start: object, end: object, data: dict) -> tuple[str, ...]:
    """양방향으로 복제된 edge가 같은 지표를 공유하도록 물리 구간 ID를 만든다."""
    osm_id = data.get("osm_edge_id")
    if osm_id is not None:
        return ("osm", str(osm_id))
    sample_id = data.get("sample_edge_id")
    if sample_id is not None:
        return ("sample", str(sample_id))
    return ("nodes", *sorted((repr(start), repr(end))))


def _road_group_id(edge_id: tuple[str, ...], data: dict) -> tuple[str, ...]:
    """한 시설의 영향이 이어질 동일 OSM way 또는 샘플 도로 그룹을 식별한다."""
    osm_way = data.get("osm_way_id", data.get("osmid"))
    if isinstance(osm_way, list):
        osm_way = osm_way[0] if osm_way else None
    if osm_way not in (None, ""):
        return ("osm-way", str(osm_way))
    sample_id = data.get("sample_edge_id")
    if sample_id is not None:
        return ("sample", str(sample_id))
    return edge_id


def _build_edge_index(
    graph: nx.MultiDiGraph,
) -> tuple[list, list[tuple[str, ...]], list[tuple[str, ...]], STRtree | None]:
    """데이터셋들이 함께 재사용할 물리 도로 공간 인덱스를 만든다."""
    geometries = []
    edge_ids: list[tuple[str, ...]] = []
    road_groups: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for start, end, data in graph.edges(data=True):
        edge_id = _physical_edge_id(start, end, data)
        if edge_id in seen:
            continue
        seen.add(edge_id)
        geometries.append(transform(_TO_METERS.transform, _edge_geometry(graph, start, end, data)))
        edge_ids.append(edge_id)
        road_groups.append(_road_group_id(edge_id, data))
    return geometries, edge_ids, road_groups, STRtree(geometries) if geometries else None


def _assign_points_to_nearest_edges(
    edge_index: tuple[
        list, list[tuple[str, ...]], list[tuple[str, ...]], STRtree | None
    ],
    points: tuple[RealPoint, ...],
    max_distance_m: float,
    max_road_groups: int = 1,
) -> dict[tuple[str, ...], int]:
    """가장 가까운 도로를 고른 뒤 같은 OSM way의 인접 구간에만 영향을 확장한다."""
    geometries, edge_ids, road_groups, tree = edge_index
    if tree is None or not points:
        return {}

    counts: dict[tuple[str, ...], int] = {}
    for point in points:
        projected = transform(_TO_METERS.transform, Point(point.longitude, point.latitude))
        candidates = tree.query(projected, predicate="dwithin", distance=max_distance_m)
        if len(candidates) == 0:
            continue
        ranked = sorted(candidates, key=lambda index: geometries[int(index)].distance(projected))
        selected_groups: list[tuple[str, ...]] = []
        for index in ranked:
            group = road_groups[int(index)]
            if group not in selected_groups:
                selected_groups.append(group)
            if len(selected_groups) >= max_road_groups:
                break
        for index in candidates:
            position = int(index)
            if road_groups[position] not in selected_groups:
                continue
            edge_id = edge_ids[position]
            counts[edge_id] = counts.get(edge_id, 0) + 1
    return counts


def _edge_has_heating(edge_name: object, heating_names: frozenset[str]) -> bool:
    names = edge_name if isinstance(edge_name, list) else [edge_name]
    for value in names:
        normalized = re.sub(r"\s+", "", str(value or ""))
        if normalized and any(
            name in normalized or normalized in name for name in heating_names
        ):
            return True
    return False


def attach_real_indicators(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """실제 좌표 지점과 열선 도로명을 edge에 결합한 graph 사본을 반환한다."""
    if not real_data_available():
        raise FileNotFoundError("전처리된 실제 서울 데이터가 없습니다.")
    result = graph.copy()
    bounds = _graph_bounds(result)
    trees = load_real_points("trees", bounds)
    female_ginkgo = tuple(point for point in trees if point.is_female_ginkgo)
    shade_points = load_real_points("shades", bounds)
    lights = load_real_points("streetlights", bounds)
    safe_return = load_real_points("safe_return", bounds)
    cctv = load_real_points("cctv", bounds)
    # 넓은 buffer로 인접 평행도로까지 중복 점수를 주지 않고 가장 가까운 도로에만
    # 시설을 귀속한다. 거리는 원본 좌표 오차와 일반적인 도로 폭만 허용하는 수준이다.
    edge_index = _build_edge_index(result)
    # 가로수 좌표는 차도 중심선과 평행 보행로 사이에 놓이는 경우가 많아 가까운
    # 두 도로 그룹까지 반영한다. 시설물은 가장 가까운 한 그룹만 사용한다.
    tree_counts = _assign_points_to_nearest_edges(edge_index, trees, 15.0, max_road_groups=2)
    ginkgo_counts = _assign_points_to_nearest_edges(
        edge_index, female_ginkgo, 18.0, max_road_groups=2
    )
    shade_counts = _assign_points_to_nearest_edges(edge_index, shade_points, 35.0)
    light_counts = _assign_points_to_nearest_edges(edge_index, lights, 25.0, max_road_groups=2)
    safe_return_counts = _assign_points_to_nearest_edges(edge_index, safe_return, 40.0)
    cctv_counts = _assign_points_to_nearest_edges(edge_index, cctv, 40.0)
    heating_names = load_heating_road_names()

    for start, end, key, data in result.edges(keys=True, data=True):
        edge_id = _physical_edge_id(start, end, data)
        canopy = tree_counts.get(edge_id, 0)
        shades = shade_counts.get(edge_id, 0)
        ginkgo = ginkgo_counts.get(edge_id, 0)
        light_count = light_counts.get(edge_id, 0)
        safe_return_count = safe_return_counts.get(edge_id, 0)
        cctv_count = cctv_counts.get(edge_id, 0)
        light_score = normalize_indicator(light_count / 3.0)
        safe_return_score = normalize_indicator(safe_return_count)
        cctv_score = normalize_indicator(cctv_count)
        values = {
            "shade_score": normalize_indicator(max(canopy / 4.0, shades)),
            "ginkgo_risk": normalize_indicator(ginkgo / 2.0),
            "heating_score": float(_edge_has_heating(data.get("name"), heating_names)),
            # 고도/노면/기상 시계열이 없는 상태에서 결빙을 임의 추정하지 않는다.
            "icing_risk": 0.0,
            "light_score": light_score,
            # 공식 안전 보장을 뜻하지 않으며 세 관측 자료의 공간 근접도다.
            "safety_score": normalize_indicator(
                0.35 * safe_return_score + 0.15 * light_score + 0.50 * cctv_score
            ),
        }
        for field, value in values.items():
            result.edges[start, end, key][field] = value
    result.graph["indicator_source"] = "seoul-public-data"
    return result
