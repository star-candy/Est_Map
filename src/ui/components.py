"""재사용 가능한 Streamlit UI 구성 요소."""

import pandas as pd
import streamlit as st

from src.domain import BikeRecommendation, RouteComparison, RouteMode
from src.reporting.accounting import TripAccounting
from src.reporting.monthly import MonthlySummary


def render_data_badge(use_real_data: bool = False) -> None:
    if use_real_data:
        st.info(
            "서울 공공데이터 파일 사용 · 열선은 좌표가 없어 도로명 일치 edge에만 반영하며 "
            "결빙 위험은 포함하지 않습니다."
        )
    else:
        st.warning("🧪 **샘플 데이터 기반 데모** · 공간 지표는 실제 공공데이터가 아닙니다.")


def render_mode_help(mode: RouteMode) -> None:
    st.caption(mode.description)
    if mode in {RouteMode.WINTER, RouteMode.SAFETY}:
        st.caption("이 경로 정보는 참고용이며 공식 안전 경로가 아닙니다.")


def render_results(comparison: RouteComparison | None) -> None:
    st.subheader("경로 비교")
    if comparison is None:
        with st.container(border=True):
            st.markdown("#### 아직 검색 결과가 없습니다")
            st.caption("출발지와 도착지를 선택한 뒤 경로 검색을 눌러 주세요.")
        return

    table = pd.DataFrame(
        {
            "구분": ["일반 최단 경로", f"{comparison.mode.value} 맞춤 경로"],
            "거리": [
                f"{comparison.baseline.distance_m / 1000:.2f} km",
                f"{comparison.optimized.distance_m / 1000:.2f} km",
            ],
            "예상 시간": [
                f"{comparison.baseline.duration_min:.0f}분",
                f"{comparison.optimized.duration_min:.0f}분",
            ],
            "쾌적 점수": [
                f"{comparison.baseline.comfort_score:.1f}점",
                f"{comparison.optimized.comfort_score:.1f}점",
            ],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")
    detour_column, method_column = st.columns(2)
    detour_column.metric("맞춤 경로 우회율", f"{comparison.detour_ratio:.1%}")
    method_column.metric("생성 방식", comparison.method)
    st.info(comparison.explanation)
    st.caption(f"출처: {comparison.source} · 보행 속도 4.5km/h · 최대 우회율 25%")
    if comparison.model_version:
        st.caption(f"로드된 RL 모델: {comparison.model_version}")
    if comparison.fallback_reason:
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


def render_monthly_report(summary: MonthlySummary, briefing: str) -> None:
    st.subheader("월간 이용 리포트")
    distance_column, carbon_column, savings_column = st.columns(3)
    distance_column.metric("총 걸은 거리", f"{summary.distance_m / 1_000:.2f} km")
    carbon_column.metric("탄소 절감량", f"{summary.carbon_saved_g / 1_000:.2f} kgCO₂e")
    savings_column.metric("추정 비용 절감액", f"{summary.taxi_saved_krw:,}원")
    st.caption(f"{summary.month} · 완료 이동 {summary.trip_count}건")
    st.info(briefing)
