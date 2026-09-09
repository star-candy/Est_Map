"""샘플 및 OpenStreetMap 보행 그래프 로딩."""

import gzip
import shutil
import sqlite3
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import networkx as nx

from config.settings import SETTINGS
from src.domain import Coordinates
from src.geocoding import SAMPLE_PLACES


def haversine_m(first: Coordinates, second: Coordinates) -> float:
    radius_m = 6_371_000
    lat1, lat2 = radians(first.latitude), radians(second.latitude)
    delta_lat = radians(second.latitude - first.latitude)
    delta_lon = radians(second.longitude - first.longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * radius_m * asin(sqrt(value))


def _add_bidirectional_edge(
    graph: nx.MultiDiGraph, first: str, second: str, edge_id: str | None = None
) -> None:
    first_point = Coordinates(graph.nodes[first]["y"], graph.nodes[first]["x"])
    second_point = Coordinates(graph.nodes[second]["y"], graph.nodes[second]["x"])
    length = haversine_m(first_point, second_point)
    graph.add_edge(first, second, length=length, sample_edge_id=edge_id)
    graph.add_edge(second, first, length=length, sample_edge_id=edge_id)


@lru_cache(maxsize=1)
def load_sample_walking_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(crs="EPSG:4326", source="synthetic")
    node_names = {
        "station": "서울역",
        "city_hall": "서울시청",
        "gwanghwamun": "광화문",
        "palace": "경복궁",
        "jongno": "종로3가역",
        "ddp": "동대문디자인플라자",
    }
    for node, place_name in node_names.items():
        point = SAMPLE_PLACES[place_name]
        graph.add_node(node, y=point.latitude, x=point.longitude)

    graph.add_node("alley1", y=37.5690, x=126.9810)
    graph.add_node("alley2", y=37.5725, x=126.9800)

    for first, second, edge_id in (
        ("station", "city_hall", "station-city"),
        ("city_hall", "gwanghwamun", "city-gwanghwamun"),
        ("city_hall", "alley1", "city-alley1"),
        ("alley1", "alley2", "alley1-alley2"),
        ("alley2", "gwanghwamun", "alley2-gwanghwamun"),
        ("gwanghwamun", "palace", "gwanghwamun-palace"),
        ("gwanghwamun", "jongno", "gwanghwamun-jongno"),
        ("city_hall", "jongno", "city-jongno"),
        ("jongno", "ddp", "jongno-ddp"),
    ):
        _add_bidirectional_edge(graph, first, second, edge_id)
    return graph


def build_fallback_graph(origin: Coordinates, destination: Coordinates) -> nx.MultiDiGraph:
    """외부 그래프 실패 시 두 좌표 사이에 명시적인 합성 우회로를 만든다."""
    graph = nx.MultiDiGraph(crs="EPSG:4326", source="synthetic-fallback")
    delta_lat = destination.latitude - origin.latitude
    delta_lon = destination.longitude - origin.longitude
    points = {
        "origin": origin,
        "middle": Coordinates(
            origin.latitude + delta_lat * 0.5 + delta_lon * 0.06,
            origin.longitude + delta_lon * 0.5 - delta_lat * 0.06,
        ),
        "destination": destination,
    }
    for node, point in points.items():
        graph.add_node(node, y=point.latitude, x=point.longitude)
    _add_bidirectional_edge(graph, "origin", "middle")
    _add_bidirectional_edge(graph, "middle", "destination")
    return graph


@lru_cache(maxsize=16)
def _cached_osm_graph(west: float, south: float, east: float, north: float) -> nx.MultiDiGraph:
    import osmnx as ox

    ox.settings.requests_timeout = SETTINGS.external_request_timeout_seconds
    ox.settings.overpass_rate_limit = False
    return ox.graph_from_bbox(
        (west, south, east, north),
        network_type="walk",
        simplify=True,
        retain_all=False,
    )


def load_osm_walking_graph(
    origin: Coordinates, destination: Coordinates, margin_degrees: float = 0.006
) -> nx.MultiDiGraph:
    north = round(max(origin.latitude, destination.latitude) + margin_degrees, 4)
    south = round(min(origin.latitude, destination.latitude) - margin_degrees, 4)
    east = round(max(origin.longitude, destination.longitude) + margin_degrees, 4)
    west = round(min(origin.longitude, destination.longitude) - margin_degrees, 4)
    return _cached_osm_graph(west, south, east, north)


@lru_cache(maxsize=1)
def _offline_database_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    archive = project_root / SETTINGS.offline_osm_archive_path
    cache_path = project_root / SETTINGS.offline_osm_cache_path
    if not archive.is_file():
        raise FileNotFoundError("오프라인 서울 보행망 압축 파일이 없습니다.")
    if not cache_path.is_file() or cache_path.stat().st_mtime < archive.stat().st_mtime:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        with gzip.open(archive, "rb") as source, temporary.open("wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        temporary.replace(cache_path)
    return cache_path


@lru_cache(maxsize=8)
def _load_offline_bbox(west: float, south: float, east: float, north: float) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph(crs="EPSG:4326", source="OSM-PBF-offline")
    query = """
        SELECT e.edge_id, e.u, e.v, e.length_m, e.name, e.highway, e.osm_id,
               u.latitude, u.longitude, v.latitude, v.longitude
        FROM edge_bounds b
        JOIN edges e ON e.edge_id = b.edge_id
        JOIN nodes u ON u.node_id = e.u
        JOIN nodes v ON v.node_id = e.v
        WHERE b.max_lon >= ? AND b.min_lon <= ?
          AND b.max_lat >= ? AND b.min_lat <= ?
    """
    with sqlite3.connect(f"file:{_offline_database_path()}?mode=ro", uri=True) as connection:
        rows = connection.execute(query, (west, east, south, north))
        for edge_id, u, v, length, name, highway, osm_id, u_lat, u_lon, v_lat, v_lon in rows:
            graph.add_node(u, y=u_lat, x=u_lon)
            graph.add_node(v, y=v_lat, x=v_lon)
            attributes = {
                "length": float(length),
                "name": name or "",
                "highway": highway or "",
                "osm_edge_id": edge_id,
                "osm_way_id": osm_id or "",
            }
            graph.add_edge(u, v, **attributes)
            graph.add_edge(v, u, **attributes)
    return graph


def load_offline_walking_graph(origin: Coordinates, destination: Coordinates) -> nx.MultiDiGraph:
    """압축 배포된 서울 OSM PBF 인덱스에서 연결된 보행 부분 그래프를 읽는다."""
    from src.routing.baseline import nearest_node

    for margin in (0.006, 0.012, 0.025):
        north = round(max(origin.latitude, destination.latitude) + margin, 4)
        south = round(min(origin.latitude, destination.latitude) - margin, 4)
        east = round(max(origin.longitude, destination.longitude) + margin, 4)
        west = round(min(origin.longitude, destination.longitude) - margin, 4)
        graph = _load_offline_bbox(west, south, east, north)
        if not graph:
            continue
        start = nearest_node(graph, origin)
        target = nearest_node(graph, destination)
        if nx.has_path(graph, start, target):
            return graph
    raise nx.NetworkXNoPath("오프라인 보행망에서 연결된 경로를 찾지 못했습니다.")
