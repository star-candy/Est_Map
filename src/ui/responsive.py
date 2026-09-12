"""반응형 지도 중심 화면의 공통 스타일과 주 메뉴."""

import streamlit as st

MAIN_CATEGORIES = ("지도", "안내", "주변", "이동", "리포트")

CATEGORY_LABELS = {
    "지도": "🗺️\n지도",
    "안내": "🧭\n안내",
    "주변": "🍽️\n주변",
    "이동": "✅\n이동",
    "리포트": "📊\n리포트",
}


def inject_responsive_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-bg: var(--background-color);
            --surface: var(--secondary-background-color);
            --text: var(--text-color);
            --accent: var(--primary-color);
            --border: var(--secondary-background-color);
            --pv-primary: #00855d;
            --pv-primary-dark: #006948;
            --pv-secondary: #006398;
            --pv-soft-green: #d9f8e9;
            --pv-shadow: 0 10px 30px rgba(19, 27, 46, 0.10);
        }
        .stApp { background: var(--app-bg); color: var(--text); }
        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: 1440px;
            padding-top: 1rem;
            padding-bottom: 7rem;
        }
        .pv-brand-bar {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            min-height: 60px;
            margin-bottom: 0.75rem;
            padding: 0.55rem 0.75rem;
            border: 1px solid color-mix(in srgb, var(--text) 10%, transparent);
            border-radius: 20px;
            background: color-mix(in srgb, var(--background-color) 92%, transparent);
            box-shadow: 0 4px 18px rgba(19, 27, 46, 0.06);
            backdrop-filter: blur(14px);
        }
        .pv-brand-mark {
            width: 42px;
            height: 42px;
            flex: 0 0 42px;
            padding: 7px;
            border-radius: 14px;
            background: linear-gradient(145deg, #13b882, #00855d);
        }
        .pv-brand-mark svg { width: 100%; height: 100%; overflow: visible; }
        .pv-brand-mark path, .pv-brand-mark circle {
            fill: none;
            stroke: #fff;
            stroke-width: 4;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .pv-brand-mark .pv-leaf { fill: #c9f5df; stroke: none; }
        .pv-brand-copy { display: flex; min-width: 0; flex-direction: column; }
        .pv-brand-copy strong { color: var(--pv-primary-dark); font-size: 1.16rem; }
        .pv-brand-copy strong span { margin-left: 0.12rem; font-size: 0.78em; }
        .pv-brand-copy small { color: color-mix(in srgb, var(--text) 64%, transparent); }
        .pv-page-pill, .pv-intro-badge {
            margin-left: auto;
            padding: 0.35rem 0.72rem;
            border-radius: 999px;
            color: var(--pv-primary-dark);
            background: var(--pv-soft-green);
            font-size: 0.78rem;
            font-weight: 700;
        }
        .pv-page-intro {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin: 0.35rem 0 0.9rem;
            padding: 0.9rem 1rem;
            border-radius: 18px;
            background: var(--secondary-background-color);
        }
        .pv-intro-icon { font-size: 1.55rem; }
        .pv-page-intro h2 { margin: 0 !important; font-size: 1.05rem !important; }
        .pv-page-intro p {
            margin: 0.12rem 0 0;
            color: color-mix(in srgb, var(--text) 68%, transparent);
            font-size: 0.82rem;
        }
        .pv-route-deck, .pv-empty-deck, .pv-navigation-deck,
        .pv-trip-deck, .pv-report-deck {
            margin: 0.65rem 0;
            border: 1px solid color-mix(in srgb, var(--text) 9%, transparent);
            border-radius: 22px;
            background: var(--background-color);
            box-shadow: var(--pv-shadow);
        }
        .pv-empty-deck {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            padding: 1.05rem;
        }
        .pv-empty-deck > span { color: var(--pv-primary); font-size: 1.8rem; }
        .pv-empty-deck p { margin: 0.18rem 0 0; opacity: 0.68; font-size: 0.82rem; }
        .pv-route-deck { padding: 0.7rem 0.9rem 0.85rem; }
        .pv-drag-handle {
            width: 38px;
            height: 4px;
            margin: 0 auto 0.7rem;
            border-radius: 999px;
            background: color-mix(in srgb, var(--text) 18%, transparent);
        }
        .pv-route-heading {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
        }
        .pv-route-heading h2 { margin: 0.32rem 0 0.65rem !important; font-size: 1rem !important; }
        .pv-route-badge, .pv-card-label {
            color: var(--pv-primary-dark);
            font-size: 0.72rem;
            font-weight: 800;
        }
        .pv-route-badge {
            display: inline-flex;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            background: var(--pv-soft-green);
        }
        .pv-score { min-width: 76px; padding: 0.35rem 0.55rem; text-align: right; }
        .pv-score small { display: block; opacity: 0.64; }
        .pv-score strong { color: var(--pv-primary-dark); font-size: 1.45rem; }
        .pv-score span { color: var(--pv-primary-dark); font-size: 0.75rem; }
        .pv-route-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.55rem; }
        .pv-route-card {
            min-width: 0;
            padding: 0.75rem;
            border-radius: 16px;
            background: var(--secondary-background-color);
        }
        .pv-route-card.pv-recommended {
            color: #fff;
            background: linear-gradient(145deg, var(--pv-primary), var(--pv-primary-dark));
        }
        .pv-route-card.pv-recommended .pv-card-label,
        .pv-route-card.pv-recommended small { color: #d9f8e9; }
        .pv-route-card > strong { display: block; margin-top: 0.25rem; font-size: 1.45rem; }
        .pv-route-card p { margin: 0.12rem 0; font-size: 0.78rem; }
        .pv-route-card small { opacity: 0.75; font-size: 0.7rem; }
        .pv-engine-row {
            display: flex;
            justify-content: space-between;
            margin-top: 0.55rem;
            padding-top: 0.55rem;
            border-top: 1px solid color-mix(in srgb, var(--text) 9%, transparent);
            font-size: 0.75rem;
        }
        .pv-engine-row span { opacity: 0.62; }
        .pv-navigation-deck { padding: 1rem; }
        .pv-navigation-deck > div { display: flex; align-items: center; gap: 0.4rem; }
        .pv-navigation-deck p { margin: 0.45rem 0 0.2rem; font-size: 1rem; }
        .pv-navigation-deck small { opacity: 0.65; }
        .pv-live-dot {
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--pv-primary);
            box-shadow: 0 0 0 5px color-mix(in srgb, var(--pv-primary) 20%, transparent);
        }
        .pv-trip-deck {
            display: grid;
            grid-template-columns: 1.4fr 1fr;
            gap: 0.7rem;
            padding: 0.8rem;
        }
        .pv-trip-distance, .pv-wallet {
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 108px;
            padding: 0.8rem;
            border-radius: 16px;
            background: var(--secondary-background-color);
        }
        .pv-trip-distance small, .pv-wallet span { opacity: 0.65; font-size: 0.75rem; }
        .pv-trip-distance strong { color: var(--pv-primary-dark); font-size: 1.65rem; }
        .pv-trip-distance span { font-size: 0.76rem; }
        .pv-wallet { color: #fff; background: linear-gradient(145deg, #006398, #004b73); }
        .pv-wallet strong { margin-top: 0.3rem; font-size: 1.2rem; }
        .pv-report-deck { padding: 0.9rem; }
        .pv-report-title { display: flex; justify-content: space-between; margin-bottom: 0.65rem; }
        .pv-report-title span { font-weight: 750; }
        .pv-report-title strong { color: var(--pv-primary-dark); }
        .pv-report-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.55rem; }
        .pv-report-grid article {
            min-height: 98px;
            padding: 0.7rem;
            border-radius: 16px;
            background: var(--secondary-background-color);
        }
        .pv-report-grid article:first-child {
            color: #fff;
            background: linear-gradient(145deg, var(--pv-primary), var(--pv-primary-dark));
        }
        .pv-report-grid small { display: block; opacity: 0.72; }
        .pv-report-grid strong { font-size: 1.45rem; }
        .pv-report-grid span { margin-left: 0.15rem; font-size: 0.7rem; }
        .pv-report-grid p { margin: 0.18rem 0 0; font-size: 0.7rem; opacity: 0.72; }
        div[data-testid="stExpander"] {
            border: 1px solid color-mix(in srgb, var(--text) 10%, transparent);
            border-radius: 18px;
            background: var(--background-color);
            box-shadow: 0 5px 18px rgba(19, 27, 46, 0.06);
        }
        div[data-testid="stForm"] { border: 0; padding: 0.35rem 0.1rem; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: color-mix(in srgb, var(--text) 10%, transparent) !important;
            border-radius: 18px !important;
        }
        .st-key-main_category {
            position: fixed;
            inset: auto auto 0 0;
            z-index: 99999;
            width: 100vw;
            margin: 0;
            padding: 0.55rem max(0.75rem, env(safe-area-inset-right))
                calc(0.55rem + env(safe-area-inset-bottom))
                max(0.75rem, env(safe-area-inset-left));
            border: 0;
            border-top: 1px solid var(--border);
            border-radius: 0;
            background: var(--background-color);
            box-shadow: 0 -4px 18px rgba(25, 45, 65, 0.16);
            backdrop-filter: blur(12px);
        }
        .st-key-main_category [role="radiogroup"] {
            display: grid !important;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.25rem;
            width: 100%;
        }
        .st-key-main_category label {
            display: flex !important;
            justify-content: center;
            color: var(--text) !important;
            min-width: 0 !important;
            min-height: 54px;
            margin: 0 !important;
            padding: 0.4rem 0.25rem !important;
            border-radius: 12px;
            text-align: center;
        }
        .st-key-main_category label p {
            margin: 0 !important;
            white-space: pre-line !important;
            font-size: 0.9rem;
            line-height: 1.35;
            text-align: center;
        }
        .st-key-main_category label > div:first-child { display: none; }
        .st-key-main_category label:has(input:checked) {
            color: var(--pv-primary-dark) !important;
            background: var(--pv-soft-green);
        }
        div[data-testid="stToast"] {
            width: min(420px, calc(100vw - 2rem));
            padding: 0.25rem;
        }
        div[data-testid="stToast"] [data-testid="stMarkdownContainer"] p {
            color: var(--text) !important;
            font-size: 1.05rem;
            line-height: 1.5;
        }
        [data-testid="stAlertContainer"],
        [data-testid="stNotificationContent"] {
            color: var(--text);
        }
        /* Streamlit의 sticky chat_input 전체 stacking context를 footer 위로 올린다. */
        [data-testid="stBottom"] {
            position: fixed !important;
            inset: auto 0 calc(76px + env(safe-area-inset-bottom)) 0 !important;
            z-index: 100000 !important;
            pointer-events: none;
        }
        [data-testid="stBottomBlockContainer"] {
            bottom: auto !important;
            padding-bottom: 0.45rem !important;
            background: var(--background-color);
            pointer-events: auto;
        }
        @media (max-width: 768px) {
            header[data-testid="stHeader"] { height: 0; }
            [data-testid="stAppViewContainer"] > .main .block-container {
                width: 100%;
                max-width: 100%;
                padding: 0.35rem 0.45rem 6.5rem;
            }
            h1 { font-size: 1.25rem !important; margin: 0.1rem 0 !important; }
            h2, h3 { font-size: 1.05rem !important; }
            .st-key-main_category {
                padding: 0.45rem max(0.25rem, env(safe-area-inset-right))
                    calc(0.45rem + env(safe-area-inset-bottom))
                    max(0.25rem, env(safe-area-inset-left));
            }
            .st-key-main_category [role="radiogroup"] {
                gap: 0;
            }
            .st-key-main_category label {
                display: flex !important;
                justify-content: center;
                min-width: 0 !important;
                min-height: 52px;
                margin: 0 !important;
                padding: 0.25rem 0.05rem !important;
                font-size: 0.78rem !important;
                text-align: center;
            }
            .st-key-main_category label p {
                font-size: 0.76rem;
                line-height: 1.25;
            }
            .pv-brand-bar { margin-bottom: 0.45rem; border-radius: 16px; }
            .pv-page-pill { display: none; }
            .pv-page-intro { padding: 0.75rem; }
            .pv-intro-badge { display: none; }
            .pv-route-deck, .pv-empty-deck, .pv-navigation-deck,
            .pv-trip-deck, .pv-report-deck { border-radius: 18px; }
            iframe[title="streamlit_folium.st_folium"] {
                min-height: 64vh !important;
                border-radius: 14px;
            }
            div[data-testid="stHorizontalBlock"] { gap: 0.45rem; }
            button, [data-testid="stBaseButton-secondary"],
            [data-testid="stBaseButton-primary"] { min-height: 44px; }
            div[data-testid="stMetric"] {
                padding: 0.45rem;
                border-radius: 12px;
                background: var(--surface);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_main_navigation() -> str:
    return st.radio(
        "메뉴",
        MAIN_CATEGORIES,
        format_func=CATEGORY_LABELS.get,
        horizontal=True,
        label_visibility="collapsed",
        key="main_category",
    )
