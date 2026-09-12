"""첨부 모바일 시안을 실제 도메인 값에 연결하는 표시용 카드."""

from html import escape

import streamlit as st

from src.domain import RouteComparison
from src.reporting.monthly import MonthlySummary


def render_brand_header(category: str) -> None:
    safe_category = escape(category)
    st.markdown(
        f"""
        <div class="pv-brand-bar">
          <div class="pv-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 48 48" role="img">
              <path d="M11 35C17 28 18 20 27 17C33 15 36 12 39 7" />
              <circle cx="39" cy="7" r="5" />
              <path class="pv-leaf" d="M9 38c1-8 5-12 12-13c-1 8-5 12-12 13Z" />
            </svg>
          </div>
          <div class="pv-brand-copy">
            <strong>피해가!<span>(街)</span></strong>
            <small>서울 맞춤 보행 경로</small>
          </div>
          <span class="pv-page-pill">{safe_category}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_intro(icon: str, title: str, description: str, badge: str | None = None) -> None:
    badge_html = f'<span class="pv-intro-badge">{escape(badge)}</span>' if badge else ""
    st.markdown(
        f"""
        <section class="pv-page-intro">
          <span class="pv-intro-icon" aria-hidden="true">{escape(icon)}</span>
          <div><h2>{escape(title)}</h2><p>{escape(description)}</p></div>
          {badge_html}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_route_deck(comparison: RouteComparison | None) -> None:
    if comparison is None:
        st.markdown(
            """
            <section class="pv-empty-deck">
              <span>⌖</span><div><strong>경로를 검색해 보세요</strong>
              <p>일반 최단 경로와 계절·안심 맞춤 경로를 한눈에 비교합니다.</p></div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        return

    baseline = comparison.baseline
    optimized = comparison.optimized
    improvement = optimized.comfort_score - baseline.comfort_score
    method = escape(comparison.method)
    mode = escape(comparison.mode.value)
    st.markdown(
        f"""
        <section class="pv-route-deck">
          <div class="pv-drag-handle"></div>
          <div class="pv-route-heading">
            <div><span class="pv-route-badge">{mode} 맞춤 추천</span>
            <h2>맞춤 경로와 일반 경로 비교</h2></div>
            <div class="pv-score"><small>쾌적 점수</small>
            <strong>{optimized.comfort_score:.0f}</strong><span>점</span></div>
          </div>
          <div class="pv-route-grid">
            <article class="pv-route-card pv-recommended">
              <span class="pv-card-label">추천 · {mode}</span>
              <strong>{optimized.duration_min:.0f}분</strong>
              <p>{optimized.distance_m / 1000:.2f}km · 쾌적 {optimized.comfort_score:.1f}점</p>
              <small>일반 경로 대비 {improvement:+.1f}점</small>
            </article>
            <article class="pv-route-card">
              <span class="pv-card-label">일반 최단</span>
              <strong>{baseline.duration_min:.0f}분</strong>
              <p>{baseline.distance_m / 1000:.2f}km · 쾌적 {baseline.comfort_score:.1f}점</p>
              <small>거리 기준 보행 경로</small>
            </article>
          </div>
          <div class="pv-engine-row"><span>경로 생성 엔진</span><strong>{method}</strong></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_navigation_deck(comparison: RouteComparison) -> None:
    st.markdown(
        f"""
        <section class="pv-navigation-deck">
          <div><span class="pv-live-dot"></span><strong>안내 준비 완료</strong></div>
          <p>{escape(comparison.mode.value)} 맞춤 경로 ·
          {comparison.optimized.distance_m / 1000:.2f}km ·
          약 {comparison.optimized.duration_min:.0f}분</p>
          <small>현재 위치 권한이 없으면 지도를 눌러 위치를 시험할 수 있습니다.</small>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_trip_deck(comparison: RouteComparison | None, total_points: int) -> None:
    if comparison is None:
        distance = "경로 검색 전"
        detail = "지도에서 경로를 검색하면 예상 이동 정보가 표시됩니다."
    else:
        distance = f"{comparison.optimized.distance_m / 1000:.2f}km"
        detail = f"{comparison.mode.value} 맞춤 경로 · 약 {comparison.optimized.duration_min:.0f}분"
    st.markdown(
        f"""
        <section class="pv-trip-deck">
          <div class="pv-trip-distance"><small>이번 이동</small><strong>{distance}</strong>
          <span>{escape(detail)}</span></div>
          <div class="pv-wallet"><span>나의 로컬 포인트</span>
          <strong>{total_points:,} P</strong></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_report_deck(summary: MonthlySummary, previous: MonthlySummary) -> None:
    distance_delta = (summary.distance_m - previous.distance_m) / 1000
    st.markdown(
        f"""
        <section class="pv-report-deck">
          <div class="pv-report-title"><span>이번 달 에코 임팩트</span>
          <strong>{summary.month}</strong></div>
          <div class="pv-report-grid">
            <article><small>걸은 거리</small>
            <strong>{summary.distance_m / 1000:.2f}</strong><span>km</span>
            <p>전월 대비 {distance_delta:+.2f}km</p></article>
            <article><small>완료 이동</small>
            <strong>{summary.trip_count}</strong><span>건</span></article>
            <article><small>탄소 절감</small>
            <strong>{summary.carbon_saved_g / 1000:.2f}</strong><span>kgCO₂e</span></article>
            <article><small>비용 절감</small>
            <strong>{summary.taxi_saved_krw:,}</strong><span>원</span></article>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
