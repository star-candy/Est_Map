"""서울 쾌적 경로 앱의 중앙 설정."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    app_title: str = "서울 쾌적 경로"
    app_icon: str = "🗺️"
    default_latitude: float = 37.5665
    default_longitude: float = 126.9780
    default_zoom: int = 12
    sample_mode: bool = True
    map_height: int = 480
    external_request_timeout_seconds: int = 20
    rl_model_path: str = "models/q_policy_summer.joblib"
    bike_distance_threshold_m: float = 1_200.0
    bike_time_threshold_min: float = 15.0
    bike_station_search_radius_m: float = 700.0
    local_report_db_path: str = (
        os.getenv("LOCAL_REPORT_DB_PATH") or "data/local/monthly_report.sqlite3"
    )
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash"
    seoul_open_api_key: str | None = os.getenv("SEOUL_OPEN_API_KEY") or None
    seoul_tree_data_path: str | None = os.getenv("SEOUL_TREE_DATA_PATH") or None
    seoul_shade_data_path: str | None = os.getenv("SEOUL_SHADE_DATA_PATH") or None
    seoul_heating_data_path: str | None = os.getenv("SEOUL_HEATING_DATA_PATH") or None
    seoul_streetlight_data_path: str | None = (
        os.getenv("SEOUL_STREETLIGHT_DATA_PATH") or None
    )
    seoul_bike_api_service: str | None = (
        os.getenv("SEOUL_BIKE_API_SERVICE") or None
    )
    kma_data_api_key: str | None = os.getenv("KMA_DATA_API_KEY") or None
    vworld_api_key: str | None = os.getenv("VWORLD_API_KEY") or None
    kakao_rest_api_key: str | None = os.getenv("KAKAO_REST_API_KEY") or None
    tmap_app_key: str | None = os.getenv("TMAP_APP_KEY") or None
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None


SETTINGS = Settings()
