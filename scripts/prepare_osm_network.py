"""OSM PBF에서 서울 보행망을 추출해 조회 가능한 SQLite로 저장한다."""

from __future__ import annotations

import argparse
import gzip
import math
import re
import shutil
import sqlite3
from pathlib import Path

import pyogrio

SEOUL_BBOX = (126.734, 37.413, 127.269, 37.715)
EXCLUDED_HIGHWAYS = {
    "construction",
    "motorway",
    "motorway_link",
    "proposed",
    "raceway",
    "trunk",
    "trunk_link",
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    first, second = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first) * math.cos(second) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(value))


def _walkable(highway: object, tags: object) -> bool:
    kind = str(highway or "").strip()
    text = str(tags or "")
    if not kind or kind in EXCLUDED_HIGHWAYS:
        return False
    return not re.search(r'"(?:access|foot)"=>"(?:no|private)"', text)


def build_database(pbf_path: Path, output_path: Path) -> tuple[int, int]:
    lines = pyogrio.read_dataframe(
        pbf_path,
        layer="lines",
        bbox=SEOUL_BBOX,
        columns=["osm_id", "name", "highway", "other_tags"],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    connection = sqlite3.connect(output_path)
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE nodes (node_id INTEGER PRIMARY KEY, latitude REAL, longitude REAL);
        CREATE TABLE edges (
            edge_id INTEGER PRIMARY KEY, u INTEGER, v INTEGER, length_m REAL,
            name TEXT, highway TEXT, osm_id TEXT
        );
        CREATE INDEX edges_u ON edges(u);
        CREATE INDEX edges_v ON edges(v);
        CREATE VIRTUAL TABLE edge_bounds USING rtree(edge_id, min_lon, max_lon, min_lat, max_lat);
        """
    )
    connection.executemany(
        "INSERT INTO metadata(key,value) VALUES (?,?)",
        (
            ("source", pbf_path.name),
            ("source_date", "2026-09-07"),
            ("license", "OpenStreetMap ODbL"),
            ("bbox", ",".join(map(str, SEOUL_BBOX))),
        ),
    )
    node_ids: dict[tuple[float, float], int] = {}
    node_rows: list[tuple[int, float, float]] = []
    edge_rows: list[tuple[int, int, int, float, str, str, str]] = []
    bound_rows: list[tuple[int, float, float, float, float]] = []
    edge_id = 0

    def node_id(lon: float, lat: float) -> int:
        key = (round(float(lon), 7), round(float(lat), 7))
        if key not in node_ids:
            identifier = len(node_ids) + 1
            node_ids[key] = identifier
            node_rows.append((identifier, key[1], key[0]))
        return node_ids[key]

    for row in lines.itertuples(index=False):
        if not _walkable(row.highway, row.other_tags):
            continue
        geometry = row.geometry
        parts = geometry.geoms if geometry.geom_type == "MultiLineString" else (geometry,)
        for part in parts:
            coordinates = list(part.coords)
            for first, second in zip(coordinates, coordinates[1:], strict=False):
                lon1, lat1 = first[:2]
                lon2, lat2 = second[:2]
                length = _haversine(lat1, lon1, lat2, lon2)
                if length <= 0 or length > 2_000:
                    continue
                edge_id += 1
                u, v = node_id(lon1, lat1), node_id(lon2, lat2)
                edge_rows.append(
                    (
                        edge_id,
                        u,
                        v,
                        length,
                        str(row.name or ""),
                        str(row.highway or ""),
                        str(row.osm_id or ""),
                    )
                )
                bound_rows.append(
                    (edge_id, min(lon1, lon2), max(lon1, lon2), min(lat1, lat2), max(lat1, lat2))
                )
                if len(edge_rows) >= 50_000:
                    connection.executemany("INSERT INTO nodes VALUES (?,?,?)", node_rows)
                    connection.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?,?)", edge_rows)
                    connection.executemany("INSERT INTO edge_bounds VALUES (?,?,?,?,?)", bound_rows)
                    connection.commit()
                    node_rows.clear()
                    edge_rows.clear()
                    bound_rows.clear()
    connection.executemany("INSERT INTO nodes VALUES (?,?,?)", node_rows)
    connection.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?,?)", edge_rows)
    connection.executemany("INSERT INTO edge_bounds VALUES (?,?,?,?,?)", bound_rows)
    connection.commit()
    connection.close()
    return len(node_ids), edge_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pbf", type=Path, default=Path.home() / "Downloads" / "south-korea-260907.osm.pbf"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/seoul_walk.sqlite3.gz")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_path = args.output.with_suffix("") if args.output.suffix == ".gz" else args.output
    nodes, edges = build_database(args.pbf, database_path)
    if args.output.suffix == ".gz":
        with database_path.open("rb") as source, gzip.open(
            args.output, "wb", compresslevel=9
        ) as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
        database_path.unlink()
    print(f"offline walking network: {nodes:,} nodes, {edges:,} edges")


if __name__ == "__main__":
    main()
