"""피해가!(街) Streamlit 애플리케이션 진입점."""

import base64
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
from src.rewards.points import PointStore, environmental_encouragement
from src.services.routing import RouteServiceError, RoutingService
from src.services.speech import GeminiSpeechProvider, SpeechError
from src.ui.components import (
    render_bike_recommendation,
    render_completion_success,
    render_data_badge,
    render_leaderboard,
    render_mode_help,
    render_monthly_report,
    render_point_award,
    render_point_summary,
    render_responsible_use_notice,
    render_restaurants,
    render_results,
)
from src.ui.html_frontend import inject_html_host_styles, render_html_frontend
from src.ui.mobile_cards import (
    render_brand_header,
    render_navigation_deck,
    render_page_intro,
    render_route_deck,
    render_trip_deck,
)
from src.ui.responsive import inject_responsive_styles, render_main_navigation

SEOUL_TIMEZONE = ZoneInfo("Asia/Seoul")
PROJECT_ROOT = Path(__file__).resolve().parent


def _render_navigation(comparison) -> None:
    render_page_intro("🧭", "실시간 경로 안내", "선택한 경로를 따라 다음 이동을 확인하세요.")
    render_navigation_deck(comparison)
    render_route_deck(comparison)
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


def _reset_search_state() -> None:
    st.session_state.trip_id = uuid4().hex
    st.session_state.trip_recorded = False
    st.session_state.last_accounting = None
    st.session_state.last_taxi_replaced = False
    st.session_state.fare_notice = None
    st.session_state.restaurants = ()
    st.session_state.restaurant_errors = ()
    st.session_state.html_show_coupons = False
    st.session_state.html_coupon_event_id = None
    st.session_state.navigation_active = False
    st.session_state.navigation_audio = None
    st.session_state.last_point_award = None


def _show_restaurant_coupon_toasts(restaurants) -> None:
    for restaurant in restaurants:
        st.toast(
            f"맛집 혜택 후보 · {restaurant.name}\n\n현재는 제휴 전 MVP 안내입니다.",
            icon="🎁",
            duration="infinite",
        )


def _render_map_page() -> None:
    comparison = st.session_state.get("route_comparison")
    with st.expander("🔎 출발지·도착지와 경로 모드", expanded=comparison is None):
        with st.form("route_search"):
            origin_column, destination_column = st.columns(2)
            origin = origin_column.text_input("출발지", value="서울역", placeholder="서울 내 주소")
            destination = destination_column.text_input(
                "도착지", value="광화문", placeholder="서울 내 주소"
            )
            direct_coordinates = st.checkbox("주소 대신 좌표 직접 입력")
            origin_coordinates = destination_coordinates = None
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
                    _reset_search_state()
                    comparison = st.session_state.route_comparison
                except RouteServiceError as exc:
                    st.session_state.route_comparison = None
                    comparison = None
                    st.error(str(exc))
                except Exception:
                    st.session_state.route_comparison = None
                    comparison = None
                    st.error(
                        "예상하지 못한 오류로 경로를 만들지 못했습니다. 잠시 후 다시 "
                        "시도하거나 좌표 직접 입력을 사용해 주세요."
                    )

    restaurants = st.session_state.get("restaurants", ())
    st_folium(
        create_route_map(SETTINGS, comparison, restaurants),
        height=680,
        use_container_width=True,
        returned_objects=[],
        key="route_map",
    )
    render_results(comparison)
    bike_recommendation = None
    if comparison is not None:
        bike_recommendation = recommend_bike_trip(
            comparison.baseline,
            comparison.origin,
            comparison.destination,
            StaticSeoulBikeStationProvider(),
        )
    render_bike_recommendation(bike_recommendation)
    render_data_badge()
    render_responsible_use_notice()


def _render_nearby_page(comparison) -> None:
    render_page_intro("🍽️", "도보 동선 맞춤 스팟", "맞춤 경로에 고르게 분포한 음식점을 찾습니다.")
    restaurants = st.session_state.get("restaurants", ())
    restaurant_errors = st.session_state.get("restaurant_errors", ())
    if comparison is None:
        st.info("지도 메뉴에서 경로를 먼저 검색해 주세요.")
        render_restaurants((), ())
        return

    providers = []
    if SETTINGS.tmap_app_key:
        providers.append(
            TmapRestaurantProvider(SETTINGS.tmap_app_key, SETTINGS.external_request_timeout_seconds)
        )
    if SETTINGS.google_map_api_key:
        providers.append(
            GoogleRestaurantProvider(
                SETTINGS.google_map_api_key, SETTINGS.external_request_timeout_seconds
            )
        )
    if st.button("🍽️ 맞춤 경로 주변 맛집 찾기", disabled=not providers, width="stretch"):
        with st.spinner("경로 주변 음식점을 찾고 있습니다..."):
            restaurants, restaurant_errors = find_route_restaurants(
                comparison.optimized,
                tuple(providers),
                SETTINGS.restaurant_search_radius_m,
                SETTINGS.restaurant_max_results,
            )
            st.session_state.restaurants = restaurants
            st.session_state.restaurant_errors = restaurant_errors
            _show_restaurant_coupon_toasts(restaurants)
    if not providers:
        st.caption("TMAP 또는 Google Places API 키가 없어 음식점 검색을 사용할 수 없습니다.")
    render_restaurants(restaurants, restaurant_errors)


def _render_trip_page(store: MonthlyReportStore, point_store: PointStore, comparison) -> None:
    render_page_intro("✅", "이동 기록", "완료한 걷기를 로컬 기록과 포인트에 반영합니다.")
    now = datetime.now(SEOUL_TIMEZONE)
    attendance_claimed = point_store.attendance_claimed(now)
    render_trip_deck(comparison, point_store.total_points())
    if not attendance_claimed and st.button("오늘 출석체크 · 50 P 받기", type="primary"):
        attendance_award = point_store.claim_attendance(now)
        if attendance_award.awarded:
            st.toast("출석체크 완료! 50포인트를 받았어요.", icon="🎁")
        attendance_claimed = True
    render_point_summary(point_store.total_points(), attendance_claimed)

    if comparison is None:
        st.info("지도 메뉴에서 경로를 검색한 뒤 이동을 기록할 수 있습니다.")
    else:
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
            inserted = store.record_trip(
                st.session_state.trip_id,
                route_kind,
                accounting,
                datetime.now(SEOUL_TIMEZONE),
            )
            if inserted:
                award = point_store.award_walking_trip(
                    st.session_state.trip_id,
                    accounting.distance_m,
                    accounting.carbon_saved_g,
                    datetime.now(SEOUL_TIMEZONE),
                )
                st.session_state.trip_recorded = True
                st.session_state.last_accounting = accounting
                st.session_state.last_taxi_replaced = taxi_replaced
                st.session_state.fare_notice = fare_notice
                st.session_state.last_point_award = award
                st.toast(
                    environmental_encouragement(accounting.distance_m, accounting.carbon_saved_g),
                    icon="🐧",
                    duration="infinite",
                )
            else:
                st.session_state.trip_recorded = True
                st.info("이미 기록된 이동입니다. 중복으로 집계하지 않았습니다.")
        if st.session_state.get("trip_recorded") and st.session_state.get("last_accounting"):
            render_completion_success(
                st.session_state.last_accounting, st.session_state.last_taxi_replaced
            )
            if st.session_state.get("fare_notice"):
                st.info(st.session_state.fare_notice)
            if st.session_state.get("last_point_award"):
                render_point_award(st.session_state.last_point_award)
    render_leaderboard(point_store.leaderboard())


def _render_report_page(store: MonthlyReportStore) -> None:
    render_page_intro("📊", "월간 이동 리포트", "걷기와 환경 기여를 월별로 확인하세요.")
    current_month = datetime.now(SEOUL_TIMEZONE).strftime("%Y-%m")
    months = store.available_months()
    report_months = (current_month,) + tuple(month for month in months if month != current_month)
    selected_month = st.selectbox("리포트 월", report_months)
    summary = store.monthly_summary(selected_month)
    previous_summary = store.previous_month_summary(selected_month)
    render_monthly_report(
        summary, TemplateBriefingProvider().generate(summary), previous_summary
    )
    if not SETTINGS.gemini_api_key:
        st.caption(
            "GEMINI_API_KEY가 없어 계산값 기반 기본 템플릿을 사용합니다. "
            "키를 설정하면 월간 통계와 대화하는 이동 코치가 활성화됩니다."
        )
        return

    st.subheader("월간 이동 코치")
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
                ({"role": "user", "content": question}, {"role": "assistant", "content": answer})
            )
            with st.chat_message("assistant"):
                st.markdown(answer)
        except BriefingError as exc:
            st.warning(f"{exc} 기본 월간 리포트는 계속 사용할 수 있습니다.")


def _route_payload(comparison):
    if comparison is None:
        return None
    return {
        "mode": comparison.mode.value,
        "method": comparison.method,
        "explanation": comparison.explanation,
        "fallback_reason": comparison.fallback_reason,
        "model_version": comparison.model_version,
        "baseline": {
            "distance": f"{comparison.baseline.distance_m / 1000:.2f}",
            "duration": f"{comparison.baseline.duration_min:.0f}",
            "comfort": f"{comparison.baseline.comfort_score:.1f}",
        },
        "optimized": {
            "distance": f"{comparison.optimized.distance_m / 1000:.2f}",
            "duration": f"{comparison.optimized.duration_min:.0f}",
            "comfort": f"{comparison.optimized.comfort_score:.1f}",
        },
    }


def _navigation_payload(comparison):
    if comparison is None or not st.session_state.get("navigation_active", False):
        return {"active": False}
    route = (
        comparison.baseline
        if st.session_state.get("navigation_route_kind") == "baseline"
        else comparison.optimized
    )
    current = st.session_state.get("navigation_position", route.path[0])
    guidance = build_guidance(route, current)
    return {
        "active": True,
        "instruction": guidance.instruction,
        "action_distance": f"{guidance.distance_to_action_m:.0f}",
        "remaining": f"{guidance.remaining_distance_m:.0f}",
        "progress": guidance.route_progress,
        "arrived": guidance.arrived,
        "off_route": guidance.off_route,
    }


def _build_html_payload(store: MonthlyReportStore, point_store: PointStore) -> dict:
    comparison = st.session_state.get("route_comparison")
    restaurants = st.session_state.get("restaurants", ())
    current_month = datetime.now(SEOUL_TIMEZONE).strftime("%Y-%m")
    report_months = (current_month,) + tuple(
        month for month in store.available_months() if month != current_month
    )
    selected_month = st.session_state.get("html_report_month", current_month)
    if selected_month not in report_months:
        selected_month = current_month
    summary = store.monthly_summary(selected_month)
    previous = store.previous_month_summary(selected_month)
    bike = None
    if comparison is not None:
        recommendation = recommend_bike_trip(
            comparison.baseline,
            comparison.origin,
            comparison.destination,
            StaticSeoulBikeStationProvider(),
        )
        bike = {
            "eligible": recommendation.eligible,
            "recommended": recommendation.recommended,
            "reason": recommendation.reason,
            "pickup": recommendation.pickup_station.name
            if recommendation.pickup_station
            else None,
            "dropoff": recommendation.dropoff_station.name
            if recommendation.dropoff_station
            else None,
            "duration": f"{recommendation.estimated_duration_min:.0f}",
        }
    histories = st.session_state.setdefault("monthly_chat_histories", {})
    history = histories.setdefault(selected_month, [])
    map_html = create_route_map(SETTINGS, comparison, restaurants).get_root().render()
    navigation_map_html = map_html
    if comparison is not None and st.session_state.get("navigation_active", False):
        route = (
            comparison.baseline
            if st.session_state.get("navigation_route_kind") == "baseline"
            else comparison.optimized
        )
        current = st.session_state.get("navigation_position", route.path[0])
        guidance = build_guidance(route, current)
        navigation_map_html = create_navigation_map(
            SETTINGS, route, current, guidance.next_position
        ).get_root().render()
    audio = st.session_state.get("navigation_audio")
    return {
        "ack_event_id": st.session_state.get("last_html_event_id"),
        "inputs": st.session_state.get(
            "html_route_inputs", {"origin": "서울역", "destination": "광화문", "mode": "여름"}
        ),
        "active_page": st.session_state.get("html_active_page", "map"),
        "route": _route_payload(comparison),
        "map_html": map_html,
        "navigation_map_html": navigation_map_html,
        "navigation": _navigation_payload(comparison),
        "bike": bike,
        "restaurants": [
            {
                "name": item.name,
                "address": item.address,
                "provider": item.provider,
                "rating": item.rating,
                "reviews": item.user_rating_count,
                "url": item.map_url,
            }
            for item in restaurants
        ],
        "trip": {
            "points": point_store.total_points(),
            "recorded": st.session_state.get("trip_recorded", False),
            "attendance_claimed": point_store.attendance_claimed(
                datetime.now(SEOUL_TIMEZONE)
            ),
        },
        "leaderboard": [
            {"rank": item.rank, "name": item.name, "points": item.points}
            for item in point_store.leaderboard()
        ],
        "report": {
            "month": selected_month,
            "months": report_months,
            "trips": summary.trip_count,
            "distance": f"{summary.distance_m / 1000:.2f}",
            "distance_delta": f"{(summary.distance_m - previous.distance_m) / 1000:+.2f}",
            "carbon": f"{summary.carbon_saved_g / 1000:.2f}",
            "savings": f"{summary.taxi_saved_krw:,}",
            "briefing": TemplateBriefingProvider().generate(summary),
            "history": history,
        },
        "audio": base64.b64encode(audio).decode("ascii") if audio else None,
        "notice": st.session_state.get("html_notice"),
        "show_coupons": st.session_state.get("html_show_coupons", False),
        "coupon_event_id": st.session_state.get("html_coupon_event_id"),
    }


def _set_html_notice(text: str, kind: str = "info") -> None:
    st.session_state.html_notice = {"id": uuid4().hex, "text": text, "type": kind}


def _html_restaurant_providers():
    providers = []
    if SETTINGS.tmap_app_key:
        providers.append(
            TmapRestaurantProvider(SETTINGS.tmap_app_key, SETTINGS.external_request_timeout_seconds)
        )
    if SETTINGS.google_map_api_key:
        providers.append(
            GoogleRestaurantProvider(
                SETTINGS.google_map_api_key, SETTINGS.external_request_timeout_seconds
            )
        )
    return tuple(providers)


def _synthesize_navigation_instruction(comparison) -> None:
    if not SETTINGS.gemini_api_key:
        return
    route = (
        comparison.baseline
        if st.session_state.get("navigation_route_kind") == "baseline"
        else comparison.optimized
    )
    current = st.session_state.get("navigation_position", route.path[0])
    guidance = build_guidance(route, current)
    try:
        st.session_state.navigation_audio = GeminiSpeechProvider(
            SETTINGS.gemini_api_key
        ).synthesize(guidance.instruction)
    except SpeechError as exc:
        st.session_state.navigation_audio = None
        _set_html_notice(str(exc), "error")


def _handle_html_event(event: dict, store: MonthlyReportStore, point_store: PointStore) -> bool:
    event_id = str(event.get("id", ""))
    if not event_id or event_id == st.session_state.get("last_html_event_id"):
        return False
    st.session_state.last_html_event_id = event_id
    event_page = str(event.get("page", ""))
    if event_page in {"map", "navigation", "nearby", "trip", "report"}:
        st.session_state.html_active_page = event_page
    st.session_state.html_notice = None
    st.session_state.html_show_coupons = False
    action = event.get("action")
    comparison = st.session_state.get("route_comparison")

    if action == "search_route":
        inputs = {
            "origin": str(event.get("origin", "")).strip(),
            "destination": str(event.get("destination", "")).strip(),
            "mode": str(event.get("mode", "여름")),
        }
        st.session_state.html_route_inputs = inputs
        try:
            direct_coordinates = bool(event.get("direct_coordinates", False))
            origin_coordinates = destination_coordinates = None
            if direct_coordinates:
                origin_coordinates = Coordinates(
                    float(event["origin_latitude"]), float(event["origin_longitude"])
                )
                destination_coordinates = Coordinates(
                    float(event["destination_latitude"]),
                    float(event["destination_longitude"]),
                )
            request = RouteRequest(
                origin=inputs["origin"],
                destination=inputs["destination"],
                mode=RouteMode(inputs["mode"]),
                use_osm=True,
                origin_coordinates=origin_coordinates,
                destination_coordinates=destination_coordinates,
                use_real_data=True,
            )
            errors = request.validate()
            if errors:
                raise RouteServiceError(" ".join(errors))
            st.session_state.route_comparison = RoutingService().find_routes(request)
            _reset_search_state()
            _set_html_notice("일반 경로와 맞춤 경로를 찾았습니다.", "success")
        except (RouteServiceError, ValueError) as exc:
            st.session_state.route_comparison = None
            _set_html_notice(str(exc), "error")
        except Exception:
            st.session_state.route_comparison = None
            _set_html_notice(
                "경로를 만들지 못했습니다. 주소를 확인하고 다시 시도해 주세요.", "error"
            )
    elif action == "search_restaurants":
        if comparison is None:
            _set_html_notice("지도에서 경로를 먼저 검색해 주세요.", "error")
        else:
            providers = _html_restaurant_providers()
            if not providers:
                _set_html_notice("TMAP 또는 Google Places API 키가 필요합니다.", "error")
            else:
                restaurants, errors = find_route_restaurants(
                    comparison.optimized,
                    providers,
                    SETTINGS.restaurant_search_radius_m,
                    SETTINGS.restaurant_max_results,
                )
                st.session_state.restaurants = restaurants
                st.session_state.restaurant_errors = errors
                st.session_state.html_show_coupons = bool(restaurants)
                st.session_state.html_coupon_event_id = uuid4().hex if restaurants else None
                if errors and not restaurants:
                    _set_html_notice(" ".join(errors), "error")
    elif action == "start_navigation" and comparison is not None:
        st.session_state.navigation_active = True
        st.session_state.navigation_route_kind = event.get("route_kind", "optimized")
        route = (
            comparison.baseline
            if st.session_state.navigation_route_kind == "baseline"
            else comparison.optimized
        )
        st.session_state.navigation_position = route.path[0]
        _synthesize_navigation_instruction(comparison)
    elif action == "stop_navigation":
        st.session_state.navigation_active = False
        st.session_state.navigation_audio = None
    elif action == "update_location" and comparison is not None:
        st.session_state.navigation_position = Coordinates(
            float(event["latitude"]), float(event["longitude"])
        )
        _synthesize_navigation_instruction(comparison)
    elif action == "location_error":
        _set_html_notice("현재 위치를 가져오지 못했습니다. 브라우저 위치 권한을 확인해 주세요.")
    elif action == "claim_attendance":
        award = point_store.claim_attendance(datetime.now(SEOUL_TIMEZONE))
        if award.awarded:
            _set_html_notice("출석체크 완료! 50포인트를 받았습니다.", "success")
        else:
            _set_html_notice("오늘 출석 포인트는 이미 받았습니다.")
    elif action == "complete_trip":
        if comparison is None:
            _set_html_notice("기록할 경로가 없습니다.", "error")
        elif st.session_state.get("trip_recorded", False):
            _set_html_notice("이미 기록된 이동입니다.")
        else:
            route_kind = str(event.get("route_kind", "optimized"))
            route = comparison.baseline if route_kind == "baseline" else comparison.optimized
            taxi_replaced = bool(event.get("taxi_replaced", False))
            taxi_fare = None
            if taxi_replaced and SETTINGS.tmap_app_key:
                try:
                    taxi_fare = TmapTaxiFareProvider(
                        SETTINGS.tmap_app_key, SETTINGS.external_request_timeout_seconds
                    ).estimate(comparison.origin, comparison.destination)
                except TaxiFareError:
                    taxi_fare = None
            accounting = calculate_trip_accounting(
                route.distance_m, taxi_replaced, taxi_fare_krw=taxi_fare
            )
            completed_at = datetime.now(SEOUL_TIMEZONE)
            trip_id = st.session_state.setdefault("trip_id", uuid4().hex)
            inserted = store.record_trip(trip_id, route_kind, accounting, completed_at)
            if inserted:
                point_store.award_walking_trip(
                    trip_id, accounting.distance_m, accounting.carbon_saved_g, completed_at
                )
                st.session_state.trip_recorded = True
                _set_html_notice(
                    environmental_encouragement(
                        accounting.distance_m, accounting.carbon_saved_g
                    ),
                    "success",
                )
            else:
                st.session_state.trip_recorded = True
                _set_html_notice("이미 기록된 이동입니다.")
    elif action == "chat":
        question = str(event.get("question", "")).strip()
        current_month = st.session_state.get(
            "html_report_month", datetime.now(SEOUL_TIMEZONE).strftime("%Y-%m")
        )
        histories = st.session_state.setdefault("monthly_chat_histories", {})
        history = histories.setdefault(current_month, [])
        if not SETTINGS.gemini_api_key:
            _set_html_notice("GEMINI_API_KEY가 없어 AI 이동 코치를 사용할 수 없습니다.", "error")
        elif question:
            try:
                answer = MonthlyReportChatbot(
                    SETTINGS.gemini_api_key,
                    SETTINGS.gemini_model,
                    SETTINGS.external_request_timeout_seconds,
                ).reply(
                    store.monthly_summary(current_month),
                    store.previous_month_summary(current_month),
                    history,
                    question,
                )
                history.extend(
                    (
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    )
                )
            except BriefingError as exc:
                _set_html_notice(str(exc), "error")
    elif action == "select_report_month":
        st.session_state.html_report_month = str(event.get("month", ""))
    return True


def _main_native() -> None:
    st.set_page_config(
        page_title=SETTINGS.app_title,
        page_icon=SETTINGS.app_icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_responsive_styles()
    category = render_main_navigation()
    render_brand_header(category)

    st.session_state.setdefault("route_comparison", None)
    comparison = st.session_state.route_comparison
    store = MonthlyReportStore(PROJECT_ROOT / SETTINGS.local_report_db_path)
    point_store = PointStore(PROJECT_ROOT / SETTINGS.local_report_db_path)

    if category == "지도":
        _render_map_page()
    elif category == "안내":
        if comparison is None:
            st.info("지도 메뉴에서 경로를 먼저 검색해 주세요.")
        else:
            _render_navigation(comparison)
    elif category == "주변":
        _render_nearby_page(comparison)
    elif category == "이동":
        _render_trip_page(store, point_store, comparison)
    else:
        _render_report_page(store)


def main() -> None:
    st.set_page_config(
        page_title=SETTINGS.app_title,
        page_icon=SETTINGS.app_icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_html_host_styles()
    store = MonthlyReportStore(PROJECT_ROOT / SETTINGS.local_report_db_path)
    point_store = PointStore(PROJECT_ROOT / SETTINGS.local_report_db_path)
    payload = _build_html_payload(store, point_store)
    event = render_html_frontend(payload)
    if event and _handle_html_event(event, store, point_store):
        st.rerun()


if __name__ == "__main__":
    main()
