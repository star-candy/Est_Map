"""첨부 서울 공공데이터 전처리 및 경로 결합 테스트."""

from config.settings import SETTINGS
from src.domain import RouteMode, RouteRequest
from src.geocoding import SAMPLE_PLACES
from src.indicators import real
from src.indicators.real import (
    RealPoint,
    _assign_points_to_nearest_edges,
    _build_edge_index,
    attach_real_indicators,
    load_heating_road_names,
    load_real_points,
    real_data_available,
)
from src.map_view import create_route_map
from src.mobility.bike import StaticSeoulBikeStationProvider
from src.routing.graph import haversine_m, load_offline_walking_graph, load_sample_walking_graph
from src.services.routing import RoutingService


def test_processed_real_data_and_female_ginkgo_filter() -> None:
    assert real_data_available()
    central_seoul = (37.43, 126.79, 37.70, 127.19)
    trees = load_real_points("trees", central_seoul)
    female = [point for point in trees if point.is_female_ginkgo]
    assert len(trees) == 287_635
    assert len(female) == 15_316
    assert all(point.label == "은행나무 암나무" for point in female)
    safe_return = load_real_points("safe_return", central_seoul)
    assert len(safe_return) == 347
    assert all(not point.is_female_ginkgo for point in safe_return)
    cctv = load_real_points("cctv", central_seoul)
    assert cctv
    assert all(not point.is_female_ginkgo for point in cctv)


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


def test_nearby_cctv_increases_safety_score(monkeypatch) -> None:
    graph = load_sample_walking_graph().copy()
    start, end, key = next(iter(graph.edges(keys=True)))
    node = graph.nodes[start]
    cctv = (RealPoint(node["y"], node["x"], "단속 CCTV"),)
    monkeypatch.setattr(
        real,
        "load_real_points",
        lambda dataset, bounds: cctv if dataset == "cctv" else (),
    )
    monkeypatch.setattr(real, "load_heating_road_names", lambda: frozenset())
    scored = attach_real_indicators(graph)
    assert scored.edges[start, end, key]["safety_score"] == 0.5


def test_point_is_assigned_to_only_one_nearest_physical_road() -> None:
    import networkx as nx

    graph = nx.MultiDiGraph()
    graph.add_node("a", y=37.5, x=127.0)
    graph.add_node("b", y=37.501, x=127.0)
    graph.add_node("c", y=37.5, x=127.0001)
    graph.add_node("d", y=37.501, x=127.0001)
    graph.add_edge("a", "b", length=111.0, osm_edge_id=1)
    graph.add_edge("b", "a", length=111.0, osm_edge_id=1)
    graph.add_edge("c", "d", length=111.0, osm_edge_id=2)
    graph.add_edge("d", "c", length=111.0, osm_edge_id=2)
    point = RealPoint(37.5005, 127.00002, "CCTV")

    counts = _assign_points_to_nearest_edges(_build_edge_index(graph), (point,), 12.0)

    assert counts == {("osm", "1"): 1}


def test_heating_road_name_changes_winter_edge_score() -> None:
    graph = load_sample_walking_graph().copy()
    start, end, key = next(iter(graph.edges(keys=True)))
    graph.edges[start, end, key]["name"] = "명륜길"
    scored = attach_real_indicators(graph)
    assert scored.edges[start, end, key]["heating_score"] == 1.0


def test_heating_road_name_accepts_partial_match() -> None:
    graph = load_sample_walking_graph().copy()
    start, end, key = next(iter(graph.edges(keys=True)))
    graph.edges[start, end, key]["name"] = "명륜"
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
    assert "안심귀갓길 연계 시설 · 경로 주변" in layer_names
    assert "불법주정차 단속 CCTV · 경로 주변" in layer_names
    assert "도로명으로 확인된 열선 구간" in layer_names
def test_real_layers_are_automatically_selected_for_each_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.services.routing.OSMGeocoder.geocode",
        lambda self, query: SAMPLE_PLACES[query],
    )
    monkeypatch.setattr(
        "src.services.routing.load_osm_walking_graph",
        lambda *args, **kwargs: load_sample_walking_graph(),
    )
    expected = {
        RouteMode.SUMMER: {"실제 가로수 · 경로 주변", "실제 그늘막 · 경로 주변"},
        RouteMode.AUTUMN: {"은행나무 암나무 · 경로 주변"},
        RouteMode.WINTER: {"도로명으로 확인된 열선 구간"},
        RouteMode.SAFETY: {
            "실제 가로등 · 경로 주변",
            "안심귀갓길 연계 시설 · 경로 주변",
            "불법주정차 단속 CCTV · 경로 주변",
        },
    }
    for mode, expected_visible in expected.items():
        comparison = RoutingService().find_routes(
            RouteRequest("서울역", "광화문", mode, use_osm=True, use_real_data=True)
        )
        route_map = create_route_map(SETTINGS, comparison)
        visible = {
            child.layer_name
            for child in route_map._children.values()
            if getattr(child, "show", False)
        }
        assert expected_visible <= visible
def test_static_bike_data_does_not_invent_inventory() -> None:
    stations = StaticSeoulBikeStationProvider().list_stations()
    assert len(stations) == 2_789
    assert all(not station.is_sample for station in stations)
    assert all(not station.inventory_known for station in stations)


def test_offline_osm_route_follows_real_network() -> None:
    origin = SAMPLE_PLACES["서울역"]
    destination = SAMPLE_PLACES["동대문디자인플라자"]
    graph = load_offline_walking_graph(origin, destination)
    from src.routing.baseline import shortest_path

    path, distance = shortest_path(graph, origin, destination)
    assert graph.graph["source"] == "OSM-PBF-offline"
    assert len(path) > 20
    assert distance > haversine_m(origin, destination) * 1.05


def test_actual_osm_graph_trains_runtime_q_learning_before_quality_gate(tmp_path) -> None:
    origin = SAMPLE_PLACES["서울역"]
    destination = SAMPLE_PLACES["광화문"]
    comparison = RoutingService(model_path=tmp_path / "base.joblib").find_routes(
        RouteRequest(
            "서울역",
            "광화문",
            RouteMode.SUMMER,
            use_osm=True,
            origin_coordinates=origin,
            destination_coordinates=destination,
            use_real_data=True,
        )
    )
    assert comparison.method in {"RL 정책", "weighted A* fallback", "일반 경로 fallback"}
    assert comparison.model_version == "q-learning-osm-runtime-v1"
    assert comparison.baseline.distance_m > haversine_m(origin, destination)
    assert comparison.detour_ratio > -1.0
