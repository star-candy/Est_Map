"""교체 가능한 대여소 adapter와 따릉이 복합 이동 추천."""

import csv
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from config.settings import SETTINGS
from src.domain import BikeRecommendation, BikeStation, Coordinates, RoutePath
from src.routing.graph import haversine_m

SAMPLE_STATIONS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "sample" / "bike_stations.csv"
)
WALKING_SPEED_M_PER_MIN = 75.0
CYCLING_SPEED_M_PER_MIN = 250.0
BIKE_ROAD_FACTOR = 1.15
UNLOCK_AND_RETURN_MIN = 3.0


class BikeStationProvider(Protocol):
    """향후 서울시 실시간 따릉이 API adapter가 구현할 인터페이스."""

    def list_stations(self) -> tuple[BikeStation, ...]:
        """현재 조회 가능한 대여소와 가용량을 반환한다."""


class SampleBikeStationProvider:
    def list_stations(self) -> tuple[BikeStation, ...]:
        return _load_sample_stations()


@lru_cache(maxsize=1)
def _load_sample_stations() -> tuple[BikeStation, ...]:
    stations: list[BikeStation] = []
    with SAMPLE_STATIONS_PATH.open(encoding="utf-8", newline="") as source:
        for record in csv.DictReader(source):
            if record["is_sample"].lower() != "true":
                raise ValueError("합성 대여소에는 is_sample=true가 필요합니다.")
            stations.append(
                BikeStation(
                    station_id=record["station_id"],
                    name=record["name"],
                    coordinates=Coordinates(
                        latitude=float(record["latitude"]),
                        longitude=float(record["longitude"]),
                    ),
                    available_bikes=int(record["available_bikes"]),
                    available_docks=int(record["available_docks"]),
                    is_sample=True,
                )
            )
    return tuple(stations)


def find_nearest_station(
    stations: tuple[BikeStation, ...],
    point: Coordinates,
    *,
    require_bike: bool = False,
    require_dock: bool = False,
    radius_m: float = SETTINGS.bike_station_search_radius_m,
    excluded_station_id: str | None = None,
) -> BikeStation | None:
    candidates = []
    for station in stations:
        if station.station_id == excluded_station_id:
            continue
        if require_bike and station.available_bikes <= 0:
            continue
        if require_dock and station.available_docks <= 0:
            continue
        distance = haversine_m(point, station.coordinates)
        if distance <= radius_m:
            candidates.append((distance, station.station_id, station))
    return min(candidates, default=(0.0, "", None))[2]


def recommend_bike_trip(
    walking_route: RoutePath,
    origin: Coordinates,
    destination: Coordinates,
    provider: BikeStationProvider,
) -> BikeRecommendation:
    eligible = (
        walking_route.distance_m >= SETTINGS.bike_distance_threshold_m
        or walking_route.duration_min >= SETTINGS.bike_time_threshold_min
    )
    if not eligible:
        return BikeRecommendation(
            eligible=False,
            recommended=False,
            reason="도보 거리가 1.2km 미만이고 예상 시간도 15분 미만입니다.",
        )

    stations = provider.list_stations()
    pickup = find_nearest_station(stations, origin, require_bike=True)
    if pickup is None:
        return BikeRecommendation(
            eligible=True,
            recommended=False,
            reason="출발지 700m 이내에 대여 가능한 샘플 따릉이 대여소가 없습니다.",
        )
    dropoff = find_nearest_station(
        stations,
        destination,
        require_dock=True,
        excluded_station_id=pickup.station_id,
    )
    if dropoff is None:
        return BikeRecommendation(
            eligible=True,
            recommended=False,
            reason="도착지 700m 이내에 반납 가능한 샘플 따릉이 대여소가 없습니다.",
        )

    first_walk = haversine_m(origin, pickup.coordinates)
    last_walk = haversine_m(dropoff.coordinates, destination)
    cycling = haversine_m(pickup.coordinates, dropoff.coordinates) * BIKE_ROAD_FACTOR
    walking = first_walk + last_walk
    total = walking + cycling
    duration = (
        walking / WALKING_SPEED_M_PER_MIN
        + cycling / CYCLING_SPEED_M_PER_MIN
        + UNLOCK_AND_RETURN_MIN
    )
    return BikeRecommendation(
        eligible=True,
        recommended=True,
        reason="긴 도보 이동을 줄일 수 있는 샘플 따릉이 복합 이동 후보입니다.",
        pickup_station=pickup,
        dropoff_station=dropoff,
        walking_distance_m=walking,
        cycling_distance_m=cycling,
        total_distance_m=total,
        estimated_duration_min=duration,
        is_sample=pickup.is_sample or dropoff.is_sample,
    )
