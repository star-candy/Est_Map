"""피해가 HTML 프런트엔드와 Streamlit Python 사이의 양방향 컴포넌트."""

from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

_FRONTEND_DIRECTORY = Path(__file__).resolve().parent / "html_frontend"
_component = components.declare_component("pihaga_mobile_frontend", path=_FRONTEND_DIRECTORY)


def render_html_frontend(payload: dict[str, Any]) -> dict[str, Any] | None:
    """전체 HTML 앱을 그리고 사용자의 가장 최근 동작을 Python에 반환한다."""
    return _component(payload=payload, default=None, key="pihaga-html-app")


def inject_html_host_styles() -> None:
    """커스텀 앱이 Streamlit 기본 여백 없이 화면 전체를 사용하게 한다."""
    st.markdown(
        """
        <style>
        html, body, .stApp, .stMain, .stAppViewContainer,
        [data-testid="stAppViewContainer"], [data-testid="stMain"],
        [data-testid="stAppViewContainer"] > .main {
            width: 100% !important;
            height: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        header[data-testid="stHeader"], footer, [data-testid="stDecoration"] {
            display: none !important;
        }
        [data-testid="stVerticalBlock"] { gap: 0 !important; }
        [data-testid="stElementContainer"]:has(style) {
            margin: 0 !important;
            padding: 0 !important;
        }
        [data-testid="stAppViewContainer"] > .main .block-container,
        [data-testid="stMainBlockContainer"], .stMainBlockContainer {
            width: 100% !important;
            max-width: none !important;
            min-width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        [data-testid="stCustomComponentV1"], .stCustomComponentV1,
        [data-testid="stElementContainer"]:has([data-testid="stCustomComponentV1"]),
        [data-testid="stElementContainer"]:has(iframe[title*="pihaga_mobile_frontend"]),
        .element-container:has(iframe[title*="pihaga_mobile_frontend"]) {
            width: 100% !important;
            max-width: none !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        [data-testid="stCustomComponentV1"] iframe,
        .stCustomComponentV1 iframe,
        iframe[title*="pihaga_mobile_frontend"] {
            display: block;
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            border: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
