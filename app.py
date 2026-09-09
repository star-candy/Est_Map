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
from src.map_view import create_navigation_map, create_route_map
from src.mobility.bike import (
    StaticSeoulBikeStationProvider,
    recommend_bike_trip,
)
from src.navigation import build_guidance, voice_announcement_key
from src.places.restaurants import (
    GoogleRestaurantProvider,
    TmapRestaurantProvider,
    find_route_restaurants,
)
from src.reporting.accounting import calculate_trip_accounting
from src.reporting.briefing import (
    BriefingError,
    MonthlyReportChatbot,
    TemplateBriefingProvider,
)
from src.reporting.monthly import MonthlyReportStore
from src.reporting.taxi import TaxiFareError, TmapTaxiFareProvider
from src.services.routing import RouteServiceError, RoutingService
from src.services.speech import GeminiSpeechProvider, SpeechError
from src.ui.components import (
    render_bike_recommendation,
    render_completion_success,
    render_data_badge,
    render_mode_help,
    render_monthly_report,
    render_responsible_use_notice,
    render_restaurant_coupon_offer,
    render_restaurants,
    render_results,
)

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
PROJECT_ROOT = Path(__file__).resolve().parent


def _render_navigation(comparison) -> None:
    st.subheader("경로 안내")
    if not st.session_state.get("navigation_active", False):
        selected = st.radio(
            "안내할 경로를 선택하세요.",
            ("일반 보행 경로", f"{comparison.mode.value} 맞춤 경로"),
            horizontal=True,
            key="navigation_route_choice",
        )
        if st.button("경로 안내 시작", type="primary", width="stretch"):
            st.session_state.navigation_active = True
            st.session_state.navigation_route_kind = selected
            route = comparison.baseline if selected == "일반 보행 경로" else comparison.optimized
            st.session_state.navigation_position = route.path[0]
            st.session_state.navigation_audio = None
            st.session_state.navigation_announced_keys = set()
            st.session_state.navigation_first_announcement = True
            st.rerun()
        return

    route_kind = st.session_state.navigation_route_kind
    route = comparison.baseline if route_kind == "일반 보행 경로" else comparison.optimized
    stop_column, reset_column = st.columns(2)
    if stop_column.button("안내 종료", width="stretch"):
        st.session_state.navigation_active = False
        st.session_state.navigation_audio = None
        st.rerun()
    if reset_column.button("출발지로 위치 초기화", width="stretch"):
        st.session_state.navigation_position = route.path[0]
        st.session_state.navigation_audio = None
        st.session_state.navigation_announced_keys = set()
        st.session_state.navigation_first_announcement = True
        st.rerun()

    st.caption(
        "브라우저 위치 버튼은 현재 위치를 한 번 갱신합니다. 연속 추적은 브라우저 정책상 "
        "주기적인 사용자 갱신이 필요하며, 테스트할 때는 아래 지도를 클릭하세요."
    )
    try:
        from streamlit_geolocation import streamlit_geolocation

        location = streamlit_geolocation()
        if isinstance(location, dict) and location.get("latitude") is not None:
            st.session_state.navigation_position = Coordinates(
                float(location["latitude"]), float(location["longitude"])
            )
    except Exception:
        st.caption("브라우저 위치 컴포넌트를 사용할 수 없어 지도 클릭 테스트만 제공합니다.")

    current = st.session_state.get("navigation_position", route.path[0])
    guidance = build_guidance(route, current)
    if guidance.arrived:
        st.success(guidance.instruction)
    elif guidance.off_route:
        st.warning(guidance.instruction)
    else:
        st.info(f"🧭 {guidance.instruction}")
    distance_column, remaining_column = st.columns(2)
    distance_column.metric("다음 행동까지", f"{guidance.distance_to_action_m:.0f}m")
    remaining_column.metric("남은 거리", f"{guidance.remaining_distance_m:.0f}m")
    st.progress(min(1.0, max(0.0, guidance.route_progress)), text="경로 진행률")

    navigation_result = st_folium(
        create_navigation_map(SETTINGS, route, current, guidance.next_position),
        height=SETTINGS.map_height,
        use_container_width=True,
        returned_objects=["last_clicked"],
        key="navigation_map",
    )
    clicked = navigation_result.get("last_clicked") if navigation_result else None
    if clicked:
        clicked_position = Coordinates(float(clicked["lat"]), float(clicked["lng"]))
        if clicked_position != current:
            st.session_state.navigation_position = clicked_position
            st.session_state.navigation_audio = None
            st.rerun()

    if SETTINGS.gemini_api_key:
        automatic_voice = st.toggle(
            "위치에 따라 음성 안내 자동 재생",
            value=True,
            help="출발, 회전 지점 60m 전, 경로 이탈 및 도착 시 자동으로 안내합니다.",
        )
        announcement_key = voice_announcement_key(
            guidance,
            initial=st.session_state.get("navigation_first_announcement", True),
        )
        announced = st.session_state.setdefault("navigation_announced_keys", set())
        if automatic_voice and announcement_key is not None and announcement_key not in announced:
            announced.add(announcement_key)
            st.session_state.navigation_first_announcement = False
            try:
                with st.spinner("다음 이동 음성을 준비하고 있습니다..."):
                    st.session_state.navigation_audio = GeminiSpeechProvider(
                        SETTINGS.gemini_api_key
                    ).synthesize(guidance.instruction)
            except SpeechError as exc:
                st.warning(str(exc))
        if st.session_state.get("navigation_audio"):
            st.audio(st.session_state.navigation_audio, format="audio/wav", autoplay=True)
    else:
        st.caption("GEMINI_API_KEY를 설정하면 검증된 텍스트 안내를 음성으로 재생할 수 있습니다.")


def _coordinate_inputs(prefix: str, default: Coordinates) -> Coordinates:
    latitude_column, longitude_column = st.columns(2)
    latitude = latitude_column.number_input(f"{prefix} 위도", value=default.latitude, format="%.6f")
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
    render_responsible_use_notice()
    render_data_badge()

    with st.form("route_search"):
        direct_coordinates = False
        origin_coordinates = destination_coordinates = None
        origin_column, destination_column = st.columns(2)
        origin = origin_column.text_input("출발지", value="서울역", placeholder="서울 내 주소")
        destination = destination_column.text_input(
            "도착지", value="광화문", placeholder="서울 내 주소"
        )
        direct_coordinates = st.checkbox("주소 대신 좌표 직접 입력")
        if direct_coordinates:
            origin_coordinates = _coordinate_inputs("출발지", SAMPLE_PLACES["서울역"])
            destination_coordinates = _coordinate_inputs("도착지", SAMPLE_PLACES["광화문"])

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
        use_osm=True,
        origin_coordinates=origin_coordinates if direct_coordinates else None,
        destination_coordinates=destination_coordinates if direct_coordinates else None,
        use_real_data=True,
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
                    st.session_state.fare_notice = None
                    st.session_state.gemini_briefing = None
                    st.session_state.restaurants = ()
                    st.session_state.restaurant_errors = ()
                    st.session_state.restaurant_coupon_open = False
                    st.session_state.navigation_active = False
                    st.session_state.navigation_audio = None
                except RouteServiceError as exc:
                    st.session_state.route_comparison = None
                    st.error(str(exc))
                except Exception:
                    st.session_state.route_comparison = None
                    st.error(
                        "예상하지 못한 오류로 경로를 만들지 못했습니다. 잠시 후 다시 "
                        "시도하거나 좌표 직접 입력을 사용해 주세요."
                    )

    comparison = st.session_state.route_comparison
    restaurants = st.session_state.get("restaurants", ())
    restaurant_errors = st.session_state.get("restaurant_errors", ())
    if comparison is not None:
        providers = []
        if SETTINGS.tmap_app_key:
            providers.append(
                TmapRestaurantProvider(
                    SETTINGS.tmap_app_key, SETTINGS.external_request_timeout_seconds
                )
            )
        if SETTINGS.google_map_api_key:
            providers.append(
                GoogleRestaurantProvider(
                    SETTINGS.google_map_api_key, SETTINGS.external_request_timeout_seconds
                )
            )
        if st.button("🍽️ 맞춤 경로 주변 맛집 찾기", disabled=not providers):
            with st.spinner("경로 주변 음식점을 찾고 있습니다..."):
                restaurants, restaurant_errors = find_route_restaurants(
                    comparison.optimized,
                    tuple(providers),
                    SETTINGS.restaurant_search_radius_m,
                    SETTINGS.restaurant_max_results,
                )
                st.session_state.restaurants = restaurants
                st.session_state.restaurant_errors = restaurant_errors
                if restaurants:
                    st.session_state.restaurant_coupon_open = True
        if st.session_state.get("restaurant_coupon_open", False) and restaurants:
            render_restaurant_coupon_offer(restaurants)
        if not providers:
            st.caption("TMAP 또는 Google Places API 키가 없어 음식점 검색을 사용할 수 없습니다.")
    st.subheader("지도")
    st_folium(
        create_route_map(SETTINGS, comparison, restaurants),
        height=SETTINGS.map_height,
        use_container_width=True,
        returned_objects=[],
    )
    render_results(comparison)
    if comparison is not None:
        _render_navigation(comparison)
    render_restaurants(restaurants, restaurant_errors)
    bike_recommendation = None
    if comparison is not None:
        bike_recommendation = recommend_bike_trip(
            comparison.baseline,
            comparison.origin,
            comparison.destination,
            StaticSeoulBikeStationProvider(),
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
        taxi_replaced = st.checkbox(
            "택시를 타는 대신 이 경로를 걸었습니다. (선택하면 절감액을 계산합니다.)"
        )
        already_recorded = st.session_state.get("trip_recorded", False)
        if st.button("이동 완료", type="primary", disabled=already_recorded, width="stretch"):
            selected_route = (
                comparison.baseline if route_kind == "일반 최단 경로" else comparison.optimized
            )
            taxi_fare = None
            fare_notice = None
            if taxi_replaced and SETTINGS.tmap_app_key:
                try:
                    taxi_fare = TmapTaxiFareProvider(
                        SETTINGS.tmap_app_key, SETTINGS.external_request_timeout_seconds
                    ).estimate(comparison.origin, comparison.destination)
                except TaxiFareError as exc:
                    fare_notice = f"{exc} 서울 택시요금 가정식으로 계산했습니다."
            accounting = calculate_trip_accounting(
                selected_route.distance_m, taxi_replaced, taxi_fare_krw=taxi_fare
            )
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
                st.session_state.fare_notice = fare_notice
            else:
                st.session_state.trip_recorded = True
                st.info("이미 기록된 이동입니다. 중복으로 집계하지 않았습니다.")
        if st.session_state.get("trip_recorded") and st.session_state.get("last_accounting"):
            render_completion_success(
                st.session_state.last_accounting,
                st.session_state.last_taxi_replaced,
            )
            if st.session_state.get("fare_notice"):
                st.info(st.session_state.fare_notice)

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
                st.warning(
                    f"{exc} 잠시 후 다시 질문해 주세요. 기본 템플릿 리포트는 계속 "
                    "사용할 수 있습니다."
                )
    else:
        st.caption(
            "GEMINI_API_KEY가 없어 계산값 기반 기본 템플릿을 사용합니다. "
            "키를 설정하면 월간 통계와 대화하는 이동 코치가 활성화됩니다."
        )


if __name__ == "__main__":
    main()
