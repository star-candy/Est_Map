"""저장소에 포함된 합성 공간 지표 데이터 로더."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SAMPLE_INDICATORS_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "sample" / "indicators.geojson"
)


@lru_cache(maxsize=1)
def load_sample_indicators() -> dict[str, Any]:
    with SAMPLE_INDICATORS_PATH.open(encoding="utf-8") as source:
        data: dict[str, Any] = json.load(source)
    if data.get("type") != "FeatureCollection":
        raise ValueError("지표 파일이 GeoJSON FeatureCollection이 아닙니다.")
    has_unmarked_feature = any(
        feature.get("properties", {}).get("is_sample") is not True for feature in data["features"]
    )
    if has_unmarked_feature:
        raise ValueError("모든 합성 지표 레코드에는 is_sample=true가 필요합니다.")
    return data
