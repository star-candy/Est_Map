"""따릉이 추천 임계값과 대여소 선택 테스트."""

import pytest

from src.domain import BikeStation, Coordinates, RoutePath
from src.mobility.bike import (
    SampleBikeStationProvider,
    find_nearest_station,
    recommend_bike_trip,
)


def walking_route(distance_m: float, duration_min: float) -> RoutePath:
    return RoutePath((), distance_m, duration_min, 0.0)


@pytest.mark.parametrize(
    ("distance_m", "duration_min"),
    [(1_200.0, 10.0), (1_000.0, 15.0), (1_300.0, 18.0)],
)
def test_bike_threshold_uses_distance_or_time(distance_m: float, duration_min: float) -> None:
    result = recommend_bike_trip(
        walking_route(distance_m, duration_min),
        Coordinates(37.5547, 126.9707),
        Coordinates(37.5759, 126.9768),
        SampleBikeStationProvider(),
    )

    assert result.eligible is True
    assert result.recommended is True


def test_bike_not_eligible_below_both_thresholds() -> None:
    result = recommend_bike_trip(
        walking_route(1_100.0, 14.9),
        Coordinates(37.5547, 126.9707),
        Coordinates(37.5759, 126.9768),
        SampleBikeStationProvider(),
    )

    assert result.eligible is False
    assert result.recommended is False


def test_nearest_station_skips_unavailable_bikes() -> None:
    point = Coordinates(37.5665, 126.9780)
    empty = BikeStation("empty", "빈 대여소", point, 0, 5, True)
    available = BikeStation("available", "대여 가능", Coordinates(37.5667, 126.9782), 2, 3, True)

    selected = find_nearest_station((empty, available), point, require_bike=True)

    assert selected == available


def test_nearest_station_skips_unavailable_docks_and_excluded_station() -> None:
    point = Coordinates(37.5665, 126.9780)
    no_dock = BikeStation("no-dock", "반납 불가", point, 4, 0, True)
    excluded = BikeStation("excluded", "제외", Coordinates(37.5666, 126.9781), 4, 4, True)
    available = BikeStation("available", "반납 가능", Coordinates(37.5667, 126.9782), 2, 3, True)

    selected = find_nearest_station(
        (no_dock, excluded, available),
        point,
        require_dock=True,
        excluded_station_id="excluded",
    )

    assert selected == available


def test_no_nearby_station_returns_reason() -> None:
    result = recommend_bike_trip(
        walking_route(2_000.0, 30.0),
        Coordinates(37.69, 127.20),
        Coordinates(37.68, 127.21),
        SampleBikeStationProvider(),
    )

    assert result.eligible is True
    assert result.recommended is False
    assert "대여 가능한" in result.reason


def test_sample_recommendation_has_distance_and_time() -> None:
    result = recommend_bike_trip(
        walking_route(2_500.0, 34.0),
        Coordinates(37.5547, 126.9707),
        Coordinates(37.5759, 126.9768),
        SampleBikeStationProvider(),
    )

    assert result.recommended is True
    assert result.pickup_station is not None
    assert result.dropoff_station is not None
    assert result.pickup_station.station_id != result.dropoff_station.station_id
    assert result.walking_distance_m > 0
    assert result.cycling_distance_m > 0
    assert result.total_distance_m == pytest.approx(
        result.walking_distance_m + result.cycling_distance_m
    )
    assert result.estimated_duration_min > 0
    assert result.is_sample is True
