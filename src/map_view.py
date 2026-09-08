"""일반·맞춤 경로와 합성 공간 지표를 표시하는 Folium 지도."""

from typing import Any

import folium
from folium.plugins import FastMarkerCluster

from config.settings import Settings
from src.domain import RouteComparison, RouteMode
from src.indicators.real import load_real_points
from src.indicators.sample import load_sample_indicators

MODE_COLORS = {
    RouteMode.SUMMER: "#16a34a",
    RouteMode.AUTUMN: "#d97706",
    RouteMode.WINTER: "#0891b2",
    RouteMode.SAFETY: "#7c3aed",
}
CATEGORY_STYLES = {
    "shade": ("그늘·수관 proxy", "#16a34a"),
    "ginkgo": ("은행나무 위험", "#d97706"),
    "heating": ("도로 열선", "#ef4444"),
    "icing": ("결빙 위험", "#06b6d4"),
    "safety": ("가로등·야간 안전 proxy", "#7c3aed"),
}
MODE_CATEGORIES = {
    RouteMode.SUMMER: {"shade"},
    RouteMode.AUTUMN: {"ginkgo"},
    RouteMode.WINTER: {"heating", "icing"},
    RouteMode.SAFETY: {"safety"},
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
            name=f"합성 {label}", show=category in MODE_CATEGORIES[mode], overlay=True
        )
        folium.GeoJson(
            _feature_collection(category),
            style_function=lambda _feature, layer_color=color: {
                "color": layer_color,
                "weight": 6,
                "opacity": 0.7,
            },
            marker=folium.CircleMarker(radius=7, fill=True, fill_opacity=0.8, color=color),
            tooltip=folium.GeoJsonTooltip(fields=["label"], aliases=["합성 지표:"]),
        ).add_to(group)
        group.add_to(map_view)


def _add_legend(map_view: folium.Map, mode: RouteMode) -> None:
    optimized_color = MODE_COLORS[mode]
    legend = f"""
    <div style="position:fixed; bottom:30px; left:30px; z-index:9999; background:white;
      padding:10px 12px; border:1px solid #aaa; border-radius:6px; font-size:13px;">
      <b>경로 범례</b><br>
      <span style="color:#64748b">━━</span> 일반 최단 경로<br>
      <span style="color:{optimized_color}">━━</span> {mode.value} 맞춤 경로<br>
      <small>공간 지표는 모두 합성 데이터</small>
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
        ("trees", "실제 가로수", False),
        ("trees", "은행나무 암나무", True),
        ("shades", "실제 그늘막", False),
        ("streetlights", "실제 가로등", False),
        ("bikes", "실제 따릉이 대여소(정적)", False),
    )
    for dataset, name, female_only in layers:
        points = load_real_points(dataset, bounds)
        if female_only:
            points = tuple(point for point in points if point.is_female_ginkgo)
        group = folium.FeatureGroup(name=f"{name} · 경로 주변", show=False, overlay=True)
        FastMarkerCluster(
            [[point.latitude, point.longitude] for point in points],
            name=name,
        ).add_to(group)
        group.add_to(map_view)
    notice_group = folium.FeatureGroup(name="도로 열선 자료 안내", show=False, overlay=True)
    folium.Marker(
        [37.5665, 126.9780],
        tooltip="도로 열선 원본은 좌표 미제공",
        popup=(
            "열선 993건은 설치구간 문자열만 제공합니다. 지도에 임의 위치를 만들지 않고 "
            "OSM 도로명이 일치하는 보행 edge에만 heating_score를 적용합니다."
        ),
        icon=folium.Icon(color="orange", icon="info-sign"),
    ).add_to(notice_group)
    notice_group.add_to(map_view)


def create_route_map(
    settings: Settings, comparison: RouteComparison | None = None
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
    _add_legend(map_view, comparison.mode)
    folium.LayerControl(collapsed=False).add_to(map_view)
    map_view.fit_bounds(baseline_points + optimized_points)
    return map_view
