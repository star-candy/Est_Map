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


def _tree(points: tuple[RealPoint, ...]) -> STRtree | None:
    geometries = [transform(_TO_METERS.transform, Point(p.longitude, p.latitude)) for p in points]
    return STRtree(geometries) if geometries else None


def _near_count(tree: STRtree | None, geometry, distance: float) -> int:
    if tree is None:
        return 0
    return len(tree.query(geometry, predicate="dwithin", distance=distance))


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
    tree_index = _tree(trees)
    ginkgo_index = _tree(female_ginkgo)
    shade_index = _tree(shade_points)
    light_index = _tree(lights)
    safe_return_index = _tree(safe_return)
    heating_names = load_heating_road_names()

    for start, end, key, data in result.edges(keys=True, data=True):
        edge = transform(_TO_METERS.transform, _edge_geometry(result, start, end, data))
        canopy = _near_count(tree_index, edge, 15.0)
        shades = _near_count(shade_index, edge, 35.0)
        ginkgo = _near_count(ginkgo_index, edge, 18.0)
        light_count = _near_count(light_index, edge, 25.0)
        safe_return_count = _near_count(safe_return_index, edge, 40.0)
        light_score = normalize_indicator(light_count / 3.0)
        safe_return_score = normalize_indicator(safe_return_count)
        values = {
            "shade_score": normalize_indicator(max(canopy / 4.0, shades)),
            "ginkgo_risk": normalize_indicator(ginkgo / 2.0),
            "heating_score": float(_edge_has_heating(data.get("name"), heating_names)),
            # 고도/노면/기상 시계열이 없는 상태에서 결빙을 임의 추정하지 않는다.
            "icing_risk": 0.0,
            "light_score": light_score,
            # 공식 안전 보장을 뜻하지 않으며 두 관측 자료의 공간 근접도다.
            "safety_score": normalize_indicator(0.55 * safe_return_score + 0.45 * light_score),
        }
        for field, value in values.items():
            result.edges[start, end, key][field] = value
    result.graph["indicator_source"] = "seoul-public-data"
    return result
