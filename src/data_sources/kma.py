"""기상청 공공데이터포털 API adapter 준비 코드."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.data_sources.base import DatasetProvenance, DataSourceConfigurationError
from src.domain import Coordinates


@dataclass(frozen=True, slots=True)
class KmaWeatherAdapter:
    """명세가 고정되기 전 계산/필드 매핑을 추측하지 않는 adapter 경계."""

    service_key: str | None
    provenance: DatasetProvenance

    def get_weather(self, point: Coordinates, at: datetime | None = None) -> Mapping[str, Any]:
        del point, at
        if not self.service_key:
            raise DataSourceConfigurationError("KMA_DATA_API_KEY가 필요합니다.")
        raise DataSourceConfigurationError(
            "TODO: 활용 신청한 단기예보/생활기상지수 명세 버전을 고정하고 "
            "격자 변환 및 응답 필드 매핑을 구현해야 합니다."
        )
