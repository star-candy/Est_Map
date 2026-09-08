"""일반·맞춤 경로와 합성 공간 지표를 표시하는 Folium 지도."""

from typing import Any

import folium

from config.settings import Settings
from src.domain import RouteComparison, RouteMode
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
    _add_indicator_layers(map_view, comparison.mode)
    _add_legend(map_view, comparison.mode)
    folium.LayerControl(collapsed=False).add_to(map_view)
    map_view.fit_bounds(baseline_points + optimized_points)
    return map_view

