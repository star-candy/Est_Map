"""일반·맞춤 경로와 합성 공간 지표를 표시하는 Folium 지도."""

from typing import Any

import folium
from folium.plugins import FastMarkerCluster

from config.settings import Settings
from src.domain import Coordinates, Restaurant, RouteComparison, RouteMode, RoutePath
from src.indicators.real import load_real_points
from src.indicators.sample import load_sample_indicators

MODE_COLORS = {
    RouteMode.SUMMER: "#16a34a",
    RouteMode.AUTUMN: "#d97706",
    RouteMode.WINTER: "#0891b2",
    RouteMode.SAFETY: "#7c3aed",
}
CATEGORY_STYLES = {
    "shade": ("그늘·수관 지표", "#16a34a"),
    "ginkgo": ("은행나무 암나무", "#d97706"),
    "heating": ("도로 열선 설치 구간", "#ef4444"),
    "icing": ("결빙 위험 구간", "#06b6d4"),
    "safety": ("가로등·야간 보행 지표", "#7c3aed"),
}
MODE_CATEGORIES = {
    RouteMode.SUMMER: {"shade"},
    RouteMode.AUTUMN: {"ginkgo"},
    RouteMode.WINTER: {"heating", "icing"},
    RouteMode.SAFETY: {"safety"},
}
REAL_MODE_LAYERS = {
    RouteMode.SUMMER: {"trees", "shades"},
    RouteMode.AUTUMN: {"female_ginkgo"},
    RouteMode.WINTER: {"heating"},
    RouteMode.SAFETY: {"streetlights", "safe_return", "cctv"},
}


def _feature_collection(category: str) -> dict[str, Any]:
    data = load_sample_indicators()
    return {
        "type": "FeatureCollection",
        "features": [
            feature for feature in data["features"] if feature["properties"]["category"] == category
        ],
    }


def _add_indicator_layers(map_view: folium.Map, mode: RouteMode) -> None:
    for category, (label, color) in CATEGORY_STYLES.items():
        group = folium.FeatureGroup(
            name=label, show=category in MODE_CATEGORIES[mode], overlay=True
        )
        folium.GeoJson(
            _feature_collection(category),
            style_function=lambda _feature, layer_color=color: {
                "color": layer_color,
                "weight": 6,
                "opacity": 0.7,
            },
            marker=folium.CircleMarker(radius=7, fill=True, fill_opacity=0.8, color=color),
            tooltip=folium.GeoJsonTooltip(fields=["label"], aliases=["지표:"]),
        ).add_to(group)
        group.add_to(map_view)


def _add_legend(map_view: folium.Map, mode: RouteMode, is_sample: bool) -> None:
    optimized_color = MODE_COLORS[mode]
    data_label = "합성 공간 지표" if is_sample else "서울 공공데이터 공간 지표"
    legend = f"""
    <div style="position:fixed; bottom:30px; left:30px; z-index:9999; background:#ffffff;
      color:#111827 !important; padding:10px 12px; border:1px solid #aaa;
      border-radius:6px; font-size:13px;">
      <b>경로 범례</b><br>
      <span style="color:#64748b">━━</span> 일반 최단 경로<br>
      <span style="color:{optimized_color}">━━</span> {mode.value} 맞춤 경로<br>
      <small>{data_label}</small>
    </div>
    """
    map_view.get_root().html.add_child(folium.Element(legend))


def _real_bounds(comparison: RouteComparison, margin: float = 0.003):
    points = (*comparison.baseline.path, *comparison.optimized.path)
    return (
        round(min(point.latitude for point in points) - margin, 4),
        round(min(point.longitude for point in points) - margin, 4),
        round(max(point.latitude for point in points) + margin, 4),
        round(max(point.longitude for point in points) + margin, 4),
    )


def _add_real_layers(map_view: folium.Map, comparison: RouteComparison) -> None:
    bounds = _real_bounds(comparison)
    layers = (
        ("trees", "trees", "실제 가로수", False),
        ("trees", "female_ginkgo", "은행나무 암나무", True),
        ("shades", "shades", "실제 그늘막", False),
        ("streetlights", "streetlights", "실제 가로등", False),
        ("safe_return", "safe_return", "안심귀갓길 연계 시설", False),
        ("cctv", "cctv", "불법주정차 단속 CCTV", False),
        ("bikes", "bikes", "실제 따릉이 대여소(정적)", False),
    )
    for dataset, style_key, name, female_only in layers:
        points = load_real_points(dataset, bounds)
        if female_only:
            points = tuple(point for point in points if point.is_female_ginkgo)
        group = folium.FeatureGroup(
            name=f"{name} · 경로 주변",
            show=style_key in REAL_MODE_LAYERS[comparison.mode],
            overlay=True,
        )
        FastMarkerCluster(
            [[point.latitude, point.longitude] for point in points],
            name=name,
        ).add_to(group)
        group.add_to(map_view)
    heating_group = folium.FeatureGroup(
        name="도로명으로 확인된 열선 구간",
        show="heating" in REAL_MODE_LAYERS[comparison.mode],
        overlay=True,
    )
    for segment in comparison.heating_segments:
        folium.PolyLine(
            [(point.latitude, point.longitude) for point in segment],
            color="#ef4444",
            weight=4,
            opacity=0.75,
            tooltip="원본 설치구간과 OSM 도로명이 일치한 열선 구간",
        ).add_to(heating_group)
    heating_group.add_to(map_view)


def create_route_map(
    settings: Settings,
    comparison: RouteComparison | None = None,
    restaurants: tuple[Restaurant, ...] = (),
) -> folium.Map:
    map_view = folium.Map(
        location=[settings.default_latitude, settings.default_longitude],
        zoom_start=settings.default_zoom,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    if comparison is None:
        folium.Marker(
            [settings.default_latitude, settings.default_longitude],
            tooltip="서울 중심",
            popup="경로를 검색해 주세요.",
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(map_view)
        return map_view

    baseline_points = [(point.latitude, point.longitude) for point in comparison.baseline.path]
    optimized_points = [(point.latitude, point.longitude) for point in comparison.optimized.path]
    folium.PolyLine(
        baseline_points,
        color="#64748b",
        weight=9,
        opacity=0.75,
        tooltip="일반 최단 경로",
    ).add_to(map_view)
    folium.PolyLine(
        optimized_points,
        color=MODE_COLORS[comparison.mode],
        weight=5,
        opacity=0.95,
        tooltip=f"{comparison.mode.value} 맞춤 경로",
    ).add_to(map_view)
    folium.Marker(
        [comparison.origin.latitude, comparison.origin.longitude],
        tooltip="출발지",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(map_view)
    folium.Marker(
        [comparison.destination.latitude, comparison.destination.longitude],
        tooltip="도착지",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(map_view)
    if comparison.indicator_source == "seoul-public-data":
        _add_real_layers(map_view, comparison)
    else:
        _add_indicator_layers(map_view, comparison.mode)
    restaurant_group = folium.FeatureGroup(name="경로 주변 맛집", show=True, overlay=True)
    for restaurant in restaurants:
        popup = f"{restaurant.name}<br>{restaurant.address}<br>출처: {restaurant.provider}"
        folium.Marker(
            [restaurant.coordinates.latitude, restaurant.coordinates.longitude],
            tooltip=restaurant.name,
            popup=popup,
            icon=folium.Icon(color="red", icon="cutlery", prefix="fa"),
        ).add_to(restaurant_group)
    restaurant_group.add_to(map_view)
    _add_legend(map_view, comparison.mode, comparison.indicator_source != "seoul-public-data")
    folium.LayerControl(collapsed=False).add_to(map_view)
    map_view.fit_bounds(baseline_points + optimized_points)
    return map_view


def create_navigation_map(
    settings: Settings,
    route: RoutePath,
    current: Coordinates,
    next_position: Coordinates,
) -> folium.Map:
    """현재 위치, 선택 경로와 다음 행동 지점을 표시하는 클릭 가능한 안내 지도."""
    points = [(point.latitude, point.longitude) for point in route.path]
    map_view = folium.Map(
        location=[current.latitude, current.longitude],
        zoom_start=17,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    folium.PolyLine(
        points, color="#2563eb", weight=7, opacity=0.85, tooltip="선택한 안내 경로"
    ).add_to(map_view)
    folium.Marker(
        [current.latitude, current.longitude],
        tooltip="현재 위치",
        icon=folium.Icon(color="blue", icon="user", prefix="fa"),
    ).add_to(map_view)
    folium.CircleMarker(
        [next_position.latitude, next_position.longitude],
        radius=8,
        color="#f97316",
        fill=True,
        fill_opacity=0.9,
        tooltip="다음 이동 지점",
    ).add_to(map_view)
    folium.Marker(points[-1], tooltip="목적지", icon=folium.Icon(color="red", icon="stop")).add_to(
        map_view
    )
    map_view.get_root().html.add_child(
        folium.Element(
            "<div style='position:fixed;bottom:25px;left:25px;z-index:9999;"
            "background:white;padding:8px;border:1px solid #999;border-radius:6px'>"
            "테스트: 지도를 클릭해 현재 위치 이동</div>"
        )
    )
    return map_view
