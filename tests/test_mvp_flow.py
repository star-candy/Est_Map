"""API 키 없는 전체 사용자 흐름 회귀 테스트."""

from datetime import datetime

import networkx as nx
import pytest

from config.settings import SETTINGS
from src.domain import Coordinates, RouteMode, RouteRequest
from src.geocoding import GeocodingError
from src.map_view import create_route_map
from src.mobility.bike import SampleBikeStationProvider, recommend_bike_trip
from src.reporting.accounting import calculate_trip_accounting
from src.reporting.monthly import MonthlyReportStore
from src.services.routing import RouteServiceError, RoutingService


@pytest.mark.parametrize("mode", list(RouteMode))
def test_keyless_sample_flow_for_every_mode(mode: RouteMode) -> None:
    comparison = RoutingService().find_routes(RouteRequest("서울역", "동대문디자인플라자", mode))

    assert comparison.is_sample is True
    assert comparison.baseline.path
    assert comparison.optimized.path
    assert comparison.method in {
        "RL 정책",
        "weighted A* fallback",
    }
    assert comparison.detour_ratio > -1.0

    route_map = create_route_map(SETTINGS, comparison)
    html = route_map.get_root().render()
    assert "일반 최단 경로" in html
    assert f"{mode.value} 맞춤 경로" in html
    assert "합성 공간 지표" in html
    assert "color:#111827 !important" in html
    expected_layer = {
        RouteMode.SUMMER: "그늘·수관 지표",
        RouteMode.AUTUMN: "은행나무 암나무",
        RouteMode.WINTER: "도로 열선 설치 구간",
        RouteMode.SAFETY: "가로등·야간 보행 지표",
    }[mode]
    layer_names = {getattr(child, "layer_name", None) for child in route_map._children.values()}
    assert expected_layer in layer_names


def test_long_route_bike_and_completion_monthly_flow(tmp_path) -> None:
    comparison = RoutingService().find_routes(
        RouteRequest("서울역", "동대문디자인플라자", RouteMode.SUMMER)
    )
    bike = recommend_bike_trip(
        comparison.baseline,
        comparison.origin,
        comparison.destination,
        SampleBikeStationProvider(),
    )
    assert comparison.baseline.distance_m >= 1_200
    assert bike.recommended is True
    assert bike.is_sample is True

    store = MonthlyReportStore(tmp_path / "report.sqlite3")
    accounting = calculate_trip_accounting(comparison.optimized.distance_m, True)
    completed_at = datetime.fromisoformat("2026-09-08T12:00:00+09:00")
    assert store.record_trip("same-search", "여름 맞춤 경로", accounting, completed_at)
    assert not store.record_trip("same-search", "여름 맞춤 경로", accounting, completed_at)
    summary = store.monthly_summary("2026-09")
    assert summary.trip_count == 1
    assert summary.distance_m == pytest.approx(comparison.optimized.distance_m)
    assert summary.carbon_saved_g > 0
    assert summary.taxi_saved_krw > 0


def test_invalid_address_and_outside_seoul_are_friendly(monkeypatch) -> None:
    def fail_geocoding(self, query):
        raise GeocodingError("주소 검색 서비스에 연결하지 못했습니다.")

    monkeypatch.setattr("src.services.routing.OSMGeocoder.geocode", fail_geocoding)
    with pytest.raises(RouteServiceError, match="주소를 찾지 못했습니다"):
        RoutingService().find_routes(
            RouteRequest("존재하지 않는 주소", "광화문", RouteMode.SUMMER, use_osm=True)
        )

    with pytest.raises(RouteServiceError, match="서울시 범위를 벗어났습니다"):
        RoutingService().find_routes(
            RouteRequest(
                "직접 좌표",
                "광화문",
                RouteMode.SUMMER,
                use_osm=True,
                origin_coordinates=Coordinates(35.1796, 129.0756),
                destination_coordinates=Coordinates(37.5759, 126.9768),
            )
        )


def test_network_failure_does_not_invent_sample_route(monkeypatch) -> None:
    def fail_graph(*args, **kwargs):
        raise ConnectionError("offline")

    monkeypatch.setattr(
        "src.services.routing.OSMGeocoder.geocode",
        lambda self, query: Coordinates(37.5665, 126.9780)
        if query == "서울시청"
        else Coordinates(37.5759, 126.9768),
    )
    monkeypatch.setattr("src.services.routing.load_offline_walking_graph", fail_graph)
    monkeypatch.setattr("src.services.routing.load_osm_walking_graph", fail_graph)
    with pytest.raises(RouteServiceError, match="OSM 보행망"):
        RoutingService().find_routes(
            RouteRequest("서울시청", "광화문", RouteMode.SUMMER, use_osm=True)
        )


def test_no_path_is_reported_as_friendly_error(monkeypatch) -> None:
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    graph.add_node("station", y=37.5547, x=126.9707)
    graph.add_node("gwanghwamun", y=37.5759, x=126.9768)
    monkeypatch.setattr("src.services.routing.load_sample_walking_graph", lambda: graph)

    with pytest.raises(RouteServiceError, match="일반 보행 경로를 계산하지 못했습니다"):
        RoutingService().find_routes(RouteRequest("서울역", "광화문", RouteMode.SUMMER))
