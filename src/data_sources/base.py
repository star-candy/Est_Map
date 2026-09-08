"""공공데이터 adapter가 따라야 하는 공급자 중립 인터페이스."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from src.domain import Coordinates


class DataSourceError(RuntimeError):
    """외부 데이터 조회나 변환이 실패했음을 나타낸다."""


class DataSourceConfigurationError(DataSourceError):
    """키, 파일 또는 확정된 스키마가 아직 설정되지 않았음을 나타낸다."""


@dataclass(frozen=True, slots=True)
class DatasetProvenance:
    provider: str
    dataset_name: str
    official_url: str
    source_crs: str | None
    license_name: str
    is_sample: bool = False


class SpatialRecordProvider(Protocol):
    """좌표 또는 주소를 가진 원본 공간 레코드를 반환한다."""

    provenance: DatasetProvenance

    def list_records(self) -> tuple[Mapping[str, Any], ...]: ...


class WeatherProvider(Protocol):
    """이미 계산하지 않은 공식 기상 관측/예보 레코드를 반환한다."""

    provenance: DatasetProvenance

    def get_weather(
        self, point: Coordinates, at: datetime | None = None
    ) -> Mapping[str, Any]: ...
