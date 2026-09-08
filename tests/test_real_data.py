"""첨부 서울 공공데이터 전처리 및 경로 결합 테스트."""

from config.settings import SETTINGS
from src.domain import RouteMode, RouteRequest
from src.geocoding import SAMPLE_PLACES
from src.indicators.real import (
    attach_real_indicators,
    load_heating_road_names,
    load_real_points,
    real_data_available,
)
from src.map_view import create_route_map
from src.mobility.bike import StaticSeoulBikeStationProvider
from src.routing.graph import load_sample_walking_graph
from src.services.routing import RoutingService


def test_processed_real_data_and_female_ginkgo_filter() -> None:
    assert real_data_available()
    central_seoul = (37.43, 126.79, 37.70, 127.19)
    trees = load_real_points("trees", central_seoul)
    female = [point for point in trees if point.is_female_ginkgo]
    assert len(trees) == 287_635
    assert len(female) == 15_316
    assert all(point.label == "은행나무 암나무" for point in female)


def test_real_indicators_are_normalized_on_every_edge() -> None:
    graph = attach_real_indicators(load_sample_walking_graph())
    assert graph.graph["indicator_source"] == "seoul-public-data"
    for _, _, data in graph.edges(data=True):
        for field in (
            "shade_score",
            "ginkgo_risk",
            "heating_score",
            "icing_risk",
            "light_score",
            "safety_score",
        ):
            assert 0.0 <= data[field] <= 1.0
    assert load_heating_road_names()


def test_heating_road_name_changes_winter_edge_score() -> None:
    graph = load_sample_walking_graph().copy()
    start, end, key = next(iter(graph.edges(keys=True)))
    graph.edges[start, end, key]["name"] = "명륜길"
    scored = attach_real_indicators(graph)
    assert scored.edges[start, end, key]["heating_score"] == 1.0


def test_real_mode_routes_and_map_layers_when_osm_is_offline(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.routing.OSMGeocoder.geocode",
        lambda self, query: SAMPLE_PLACES[query],
    )
    monkeypatch.setattr(
        "src.services.routing.load_osm_walking_graph",
        lambda *args, **kwargs: load_sample_walking_graph(),
    )
    comparison = RoutingService().find_routes(
        RouteRequest(
            "서울역",
            "광화문",
            RouteMode.AUTUMN,
            use_osm=True,
            use_real_data=True,
        )
    )
    assert comparison.indicator_source == "seoul-public-data"
    assert "서울 공공데이터" in comparison.source
    route_map = create_route_map(SETTINGS, comparison)
    layer_names = {getattr(child, "layer_name", "") for child in route_map._children.values()}
    assert "실제 가로수 · 경로 주변" in layer_names
    assert "은행나무 암나무 · 경로 주변" in layer_names
    assert "실제 그늘막 · 경로 주변" in layer_names
    assert "실제 가로등 · 경로 주변" in layer_names
    assert "도로 열선 자료 안내" in layer_names


def test_static_bike_data_does_not_invent_inventory() -> None:
    stations = StaticSeoulBikeStationProvider().list_stations()
    assert len(stations) == 2_789
    assert all(not station.is_sample for station in stations)
    assert all(not station.inventory_known for station in stations)
