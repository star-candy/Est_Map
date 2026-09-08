"""서울 쾌적 경로 Streamlit 애플리케이션 진입점."""

from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit_folium import st_folium

from config.settings import SETTINGS
from src.domain import Coordinates, RouteMode, RouteRequest
from src.geocoding import SAMPLE_PLACES
from src.map_view import create_route_map
from src.mobility.bike import (
    SampleBikeStationProvider,
    StaticSeoulBikeStationProvider,
    recommend_bike_trip,
)
from src.reporting.accounting import calculate_trip_accounting
from src.reporting.briefing import (
    BriefingError,
    MonthlyReportChatbot,
    TemplateBriefingProvider,
)
from src.reporting.monthly import MonthlyReportStore
from src.services.routing import RouteServiceError, RoutingService
from src.ui.components import (
    render_bike_recommendation,
    render_completion_success,
    render_data_badge,
    render_mode_help,
    render_monthly_report,
    render_results,
)

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
PROJECT_ROOT = Path(__file__).resolve().parent


def _coordinate_inputs(prefix: str, default: Coordinates) -> Coordinates:
    latitude_column, longitude_column = st.columns(2)
    latitude = latitude_column.number_input(
        f"{prefix} 위도", value=default.latitude, format="%.6f"
    )
    longitude = longitude_column.number_input(
        f"{prefix} 경도", value=default.longitude, format="%.6f"
    )
    return Coordinates(latitude=latitude, longitude=longitude)


def main() -> None:
    st.set_page_config(
        page_title=SETTINGS.app_title,
        page_icon=SETTINGS.app_icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.title(f"{SETTINGS.app_icon} {SETTINGS.app_title}")
    st.caption("서울의 일반 최단 보행 경로와 계절·안심 맞춤 경로를 비교하는 MVP입니다.")
    data_source = st.radio(
        "경로 데이터",
        ("샘플 데모", "실제 로컬 데이터 + OpenStreetMap"),
        horizontal=True,
        help="실제 모드는 첨부 공공데이터와 OSM 보행망을 사용하며 인터넷 연결이 필요합니다.",
    )
    use_real_data = data_source == "실제 로컬 데이터 + OpenStreetMap"
    render_data_badge(use_real_data)

    with st.form("route_search"):
        use_osm = use_real_data
        direct_coordinates = False
        origin_coordinates = destination_coordinates = None

        if use_osm:
            origin_column, destination_column = st.columns(2)
            origin = origin_column.text_input("출발지", value="서울역", placeholder="서울 내 주소")
            destination = destination_column.text_input(
                "도착지", value="광화문", placeholder="서울 내 주소"
            )
            direct_coordinates = st.checkbox("주소 대신 좌표 직접 입력")
            if direct_coordinates:
                origin_coordinates = _coordinate_inputs("출발지", SAMPLE_PLACES["서울역"])
                destination_coordinates = _coordinate_inputs("도착지", SAMPLE_PLACES["광화문"])
        else:
            names = tuple(SAMPLE_PLACES)
            origin_column, destination_column = st.columns(2)
            origin = origin_column.selectbox("출발지", names, index=0)
            destination = destination_column.selectbox("도착지", names, index=2)

        mode = st.radio(
            "경로 모드",
            options=list(RouteMode),
            format_func=lambda item: item.value,
            horizontal=True,
        )
        submitted = st.form_submit_button("경로 검색", type="primary", width="stretch")

    render_mode_help(mode)
    if "route_comparison" not in st.session_state:
        st.session_state.route_comparison = None

    request = RouteRequest(
        origin=origin,
        destination=destination,
        mode=mode,
        use_osm=use_osm,
        origin_coordinates=origin_coordinates if direct_coordinates else None,
        destination_coordinates=destination_coordinates if direct_coordinates else None,
        use_real_data=use_real_data,
    )
    if submitted:
        errors = request.validate()
        if errors:
            st.session_state.route_comparison = None
            for error in errors:
                st.error(error)
        else:
            with st.spinner("보행 경로를 찾고 있습니다..."):
                try:
                    st.session_state.route_comparison = RoutingService().find_routes(request)
                    st.session_state.trip_id = uuid4().hex
                    st.session_state.trip_recorded = False
                    st.session_state.last_accounting = None
                    st.session_state.last_taxi_replaced = False
                    st.session_state.gemini_briefing = None
                except RouteServiceError as exc:
                    st.session_state.route_comparison = None
                    st.error(str(exc))

    comparison = st.session_state.route_comparison
    st.subheader("지도")
    st_folium(
        create_route_map(SETTINGS, comparison),
        height=SETTINGS.map_height,
        use_container_width=True,
        returned_objects=[],
    )
    render_results(comparison)
    bike_recommendation = None
    if comparison is not None:
        bike_recommendation = recommend_bike_trip(
            comparison.baseline,
            comparison.origin,
            comparison.destination,
            StaticSeoulBikeStationProvider() if use_real_data else SampleBikeStationProvider(),
        )
    render_bike_recommendation(bike_recommendation)

    store = MonthlyReportStore(PROJECT_ROOT / SETTINGS.local_report_db_path)
    if comparison is not None:
        st.subheader("이동 완료")
        route_kind = st.radio(
            "실제로 이동한 경로를 확인해 주세요.",
            ("일반 최단 경로", f"{comparison.mode.value} 맞춤 경로"),
            horizontal=True,
        )
        taxi_replaced = st.checkbox("택시를 타는 대신 이 경로를 걸었습니다.")
        already_recorded = st.session_state.get("trip_recorded", False)
        if st.button("이동 완료", type="primary", disabled=already_recorded, width="stretch"):
            selected_route = (
                comparison.baseline if route_kind == "일반 최단 경로" else comparison.optimized
            )
            accounting = calculate_trip_accounting(selected_route.distance_m, taxi_replaced)
            completed_at = datetime.now(SEOUL_TIMEZONE)
            inserted = store.record_trip(
                st.session_state.trip_id,
                route_kind,
                accounting,
                completed_at,
            )
            if inserted:
                st.session_state.trip_recorded = True
                st.session_state.last_accounting = accounting
                st.session_state.last_taxi_replaced = taxi_replaced
            else:
                st.session_state.trip_recorded = True
                st.info("이미 기록된 이동입니다. 중복으로 집계하지 않았습니다.")
        if st.session_state.get("trip_recorded") and st.session_state.get("last_accounting"):
            render_completion_success(
                st.session_state.last_accounting,
                st.session_state.last_taxi_replaced,
            )

    current_month = datetime.now(SEOUL_TIMEZONE).strftime("%Y-%m")
    months = store.available_months()
    report_months = (current_month,) + tuple(month for month in months if month != current_month)
    selected_month = st.selectbox("리포트 월", report_months)
    summary = store.monthly_summary(selected_month)
    previous_summary = store.previous_month_summary(selected_month)
    template_briefing = TemplateBriefingProvider().generate(summary)
    render_monthly_report(summary, template_briefing, previous_summary)

    if SETTINGS.gemini_api_key:
        st.subheader("월간 이동 코치")
        st.caption("월간 통계를 바탕으로 비교, 패턴과 다음 이동 목표를 대화로 확인하세요.")
        histories = st.session_state.setdefault("monthly_chat_histories", {})
        history = histories.setdefault(selected_month, [])
        for turn in history:
            with st.chat_message(turn["role"]):
                st.markdown(turn["content"])
        question = st.chat_input("예: 지난달과 비교해서 무엇이 달라졌나요?")
        if question:
            with st.chat_message("user"):
                st.markdown(question)
            try:
                provider = MonthlyReportChatbot(
                    SETTINGS.gemini_api_key,
                    SETTINGS.gemini_model,
                    SETTINGS.external_request_timeout_seconds,
                )
                with st.spinner("월간 이동 코치가 답변을 준비하고 있습니다..."):
                    answer = provider.reply(summary, previous_summary, history, question)
                history.extend(
                    (
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    )
                )
                with st.chat_message("assistant"):
                    st.markdown(answer)
            except BriefingError as exc:
                st.warning(f"{exc} 기본 템플릿 리포트는 계속 사용할 수 있습니다.")
    else:
        st.caption(
            "GEMINI_API_KEY가 없어 계산값 기반 기본 템플릿을 사용합니다. "
            "키를 설정하면 월간 통계와 대화하는 이동 코치가 활성화됩니다."
        )


if __name__ == "__main__":
    main()
