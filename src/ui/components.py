"""재사용 가능한 Streamlit UI 구성 요소."""

import pandas as pd
import streamlit as st

from src.domain import BikeRecommendation, Restaurant, RouteComparison, RouteMode
from src.reporting.accounting import TripAccounting
from src.reporting.monthly import MonthlySummary
from src.rewards.points import LeaderboardEntry, PointAward
from src.ui.mobile_cards import render_report_deck, render_route_deck


def monthly_savings_delta(summary: MonthlySummary, previous_summary: MonthlySummary | None) -> int:
    previous = previous_summary.taxi_saved_krw if previous_summary else 0
    return summary.taxi_saved_krw - previous


def render_data_badge() -> None:
    st.info(
        "서울 공공데이터 파일 사용 · 일반·맞춤 경로는 OSM 보행망을 사용합니다. "
        "열선은 도로명이 확인된 구간만 표시합니다."
    )


def render_point_summary(total_points: int, attendance_claimed: bool) -> None:
    with st.container(border=True):
        points_column, attendance_column = st.columns(2)
        points_column.metric("내 포인트", f"{total_points:,} P")
        if attendance_claimed:
            attendance_column.success("오늘 출석 완료 · +50 P")
        else:
            attendance_column.caption("오늘 출석체크로 50 P를 받을 수 있어요.")


def render_point_award(award: PointAward) -> None:
    st.success(
        f"걷기 포인트 +{award.points:,} P · 현재 {award.total_points:,} P "
        f"(거리 {award.distance_points} P + 탄소 {award.carbon_points} P)"
    )


def render_leaderboard(entries: tuple[LeaderboardEntry, ...]) -> None:
    st.subheader("포인트 비교 · MVP")
    rows = [
        {
            "순위": entry.rank,
            "사용자": f"{entry.name} (나)" if entry.is_current_user else entry.name,
            "포인트": f"{entry.points:,} P",
            "데이터": "현재 로컬 값" if entry.is_current_user else "데모 값",
        }
        for entry in entries
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("다른 사용자의 이름과 포인트는 MVP 화면용 고정 샘플이며 실제 사용자가 아닙니다.")


def render_responsible_use_notice() -> None:
    with st.expander("개인정보·외부 API·AI 결과 안내", expanded=False):
        st.markdown(
            """
- 경로 검색에는 위치 확인에 필요한 **출발지와 도착지**만 입력하세요. 주민등록번호,
  전화번호, 이름 등 개인식별정보는 입력하지 마세요.
- 입력 주소는 좌표 변환을 위해 Nominatim으로 전송됩니다. 좌표 직접 입력을 선택할 수
  있습니다. 경로 전체와 정밀 좌표는 월간 기록에 저장하지 않습니다.
- 맛집 버튼을 누르면 맞춤 경로의 출발·중간·도착 주변 좌표가 TMAP과 Google에
  전송됩니다. 택시 대체를 확인하면 출발·도착 좌표가 TMAP 요금 조회에 사용됩니다.
- Gemini 이동 코치에는 월간 집계와 대화 내용만 전달되며 주소와 경로는 보내지 않습니다.
- 경로 안내의 현재 위치는 브라우저 권한을 받은 경우에만 조회하며 로컬 세션에서만
  사용하고 월간 기록에 저장하지 않습니다. 자동 음성 안내를 켜면 출발·회전 접근·경로
  이탈·도착 시 현재 안내 문장만 Gemini TTS로 전송됩니다.
- 맞춤 경로와 RL 정책은 공공데이터 기반 참고 결과입니다. 데이터 누락과 지역별 시설
  밀도 차이로 잘못되거나 편향된 결과가 나올 수 있으며 안전을 보장하지 않습니다.
"""
        )


def render_mode_help(mode: RouteMode) -> None:
    st.caption(mode.description)
    st.caption(
        "AI·공간지표 추천은 참고용입니다. 누락되거나 오래된 데이터로 잘못된 결과가 "
        "나올 수 있으며 공식 안전 경로가 아닙니다."
    )


def render_results(comparison: RouteComparison | None) -> None:
    render_route_deck(comparison)
    if comparison is None:
        return
    detour_column, method_column = st.columns(2)
    detour_column.metric("맞춤 경로 우회율", f"{comparison.detour_ratio:.1%}")
    method_column.metric("생성 방식", comparison.method)
    st.info(comparison.explanation)
    st.caption(f"출처: {comparison.source} · 보행 속도 4.5km/h · 맞춤 경로 우회율 제한 없음")
    if comparison.model_version:
        st.caption(f"로드된 RL 모델: {comparison.model_version}")
    if comparison.fallback_reason:
        if comparison.method == "weighted A* fallback":
            st.info(
                "맞춤 경로는 weighted A*로 정상 생성되었습니다. "
                f"RL 후보 제외 사유: {comparison.fallback_reason}"
            )
        else:
            st.warning(comparison.fallback_reason)
    if comparison.notice:
        st.warning(comparison.notice)


def render_bike_recommendation(recommendation: BikeRecommendation | None) -> None:
    st.subheader("따릉이 복합 이동")
    if recommendation is None:
        st.caption("경로를 검색하면 따릉이 복합 이동 가능성을 확인합니다.")
        return
    if not recommendation.recommended:
        if recommendation.eligible:
            st.warning(f"따릉이 추천 제외 · {recommendation.reason}")
        else:
            st.caption(f"따릉이 추천 기준 미충족 · {recommendation.reason}")
        return

    st.success("🚲 따릉이 복합 이동을 고려해 보세요.")
    st.write(recommendation.reason)
    pickup = recommendation.pickup_station
    dropoff = recommendation.dropoff_station
    if pickup is None or dropoff is None:
        return
    if recommendation.inventory_known:
        st.markdown(f"**대여:** {pickup.name} · 자전거 {pickup.available_bikes}대")
        st.markdown(f"**반납:** {dropoff.name} · 빈 거치대 {dropoff.available_docks}개")
    else:
        st.markdown(f"**대여 후보:** {pickup.name}")
        st.markdown(f"**반납 후보:** {dropoff.name}")
        st.warning("정적 대여소 위치 자료이며 현재 자전거·빈 거치대 수는 제공하지 않습니다.")
    distance_column, time_column = st.columns(2)
    distance_column.metric(
        "개략 복합 거리",
        f"{recommendation.total_distance_m / 1000:.2f} km",
        help=(
            f"도보 {recommendation.walking_distance_m / 1000:.2f}km + "
            f"자전거 {recommendation.cycling_distance_m / 1000:.2f}km"
        ),
    )
    time_column.metric("개략 예상 시간", f"{recommendation.estimated_duration_min:.0f}분")
    if recommendation.is_sample:
        st.caption("대여소 위치와 가용 자전거·거치대 수는 실시간 정보가 아닌 합성 샘플 값입니다.")


def render_restaurants(restaurants: tuple[Restaurant, ...], errors: tuple[str, ...] = ()) -> None:
    st.subheader("경로 주변 맛집")
    if not restaurants:
        st.caption("경로 검색 후 ‘주변 음식점 찾기’를 누르면 맞춤 경로 주변을 조회합니다.")
    for restaurant in restaurants:
        rating = f" · 평점 {restaurant.rating:.1f}" if restaurant.rating is not None else ""
        reviews = (
            f" · 리뷰 {restaurant.user_rating_count:,}개"
            if restaurant.user_rating_count is not None
            else ""
        )
        with st.container(border=True):
            st.markdown(f"**{restaurant.name}**{rating}{reviews}")
            st.caption(f"{restaurant.address} · {restaurant.provider}")
            if restaurant.map_url:
                st.link_button("지도에서 보기", restaurant.map_url)
    if errors:
        st.warning(" ".join(errors))


def render_completion_success(accounting: TripAccounting, taxi_replaced: bool) -> None:
    st.success(
        f"✅ 이동 완료 · {accounting.distance_m / 1_000:.2f}km가 이번 달 기록에 반영됐습니다."
    )
    st.write(
        "승용차 이동을 같은 거리만큼 대체했다고 가정한 탄소 절감량: "
        f"**{accounting.carbon_saved_g:.0f}gCO₂e**"
    )
    if taxi_replaced:
        st.write(f"택시 대신 걸어서 아낀 추정 비용: **{accounting.taxi_saved_krw:,}원**")
        if accounting.taxi_fare_source:
            st.caption(f"계산 출처: {accounting.taxi_fare_source}")


def render_monthly_report(
    summary: MonthlySummary, briefing: str, previous_summary: MonthlySummary | None = None
) -> None:
    previous = previous_summary or MonthlySummary("", 0, 0.0, 0.0, 0)
    render_report_deck(summary, previous)
    savings_delta = monthly_savings_delta(summary, previous_summary)
    st.caption(f"{summary.month} · 완료 이동 {summary.trip_count}건")
    st.caption(f"추정 비용 절감액은 전월보다 {savings_delta:+,}원입니다.")
    st.info(briefing)
