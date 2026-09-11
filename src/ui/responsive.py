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
        }
        .stApp { background: var(--app-bg); color: var(--text); }
        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: 1440px;
            padding-top: 1rem;
            padding-bottom: 7rem;
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
            color: #ffffff !important;
            background: var(--accent);
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
