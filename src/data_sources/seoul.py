"""서울 열린데이터광장용 실제 데이터 adapter 기반 구현.

이 모듈은 설정되기 전에는 네트워크를 호출하지 않는다. 원본 스키마의 실제
컬럼명을 확인하지 않은 데이터셋은 매핑을 추측하지 않고 명시적으로 중단한다.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from src.data_sources.base import (
    DatasetProvenance,
    DataSourceConfigurationError,
    DataSourceError,
)
from src.domain import BikeStation, Coordinates


@dataclass(frozen=True, slots=True)
class SeoulOpenApiClient:
    api_key: str
    timeout_seconds: int = 20
    base_url: str = "http://openapi.seoul.go.kr:8088"

    def fetch_page(
        self, service: str, start: int = 1, end: int = 1000
    ) -> tuple[Mapping[str, Any], ...]:
        if not self.api_key or not service:
            raise DataSourceConfigurationError(
                "SEOUL_OPEN_API_KEY와 확정된 API 서비스명이 필요합니다."
            )
        url = "/".join(
            (self.base_url, quote(self.api_key), "json", quote(service), str(start), str(end))
        )
        try:
            response = requests.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DataSourceError("서울 열린데이터광장 조회에 실패했습니다.") from exc
        envelope = payload.get(service)
        if not isinstance(envelope, Mapping):
            raise DataSourceError("API 응답에서 요청한 서비스 envelope를 찾지 못했습니다.")
        result = envelope.get("RESULT", {})
        if isinstance(result, Mapping) and result.get("CODE") not in (None, "INFO-000"):
            raise DataSourceError(f"서울 API 오류: {result.get('CODE')}")
        rows = envelope.get("row", [])
        if not isinstance(rows, list):
            raise DataSourceError("서울 API row 형식이 예상과 다릅니다.")
        return tuple(row for row in rows if isinstance(row, Mapping))


@dataclass(frozen=True, slots=True)
class LocalPublicDatasetAdapter:
    """검증된 CSV/GeoJSON 원본을 읽는 공통 adapter.

    XLSX 자료는 원본을 보존한 뒤 검증된 전처리 스크립트로 CSV/GeoJSON으로
    변환해야 한다. 구체 컬럼 매핑은 데이터 버전을 고정한 후 별도 adapter에서 한다.
    """

    path: Path | None
    provenance: DatasetProvenance

    def list_records(self) -> tuple[Mapping[str, Any], ...]:
        if self.path is None:
            raise DataSourceConfigurationError(
                f"{self.provenance.dataset_name} 원본 파일 경로가 설정되지 않았습니다."
            )
        if not self.path.is_file():
            raise DataSourceConfigurationError(f"원본 파일을 찾을 수 없습니다: {self.path}")
        suffix = self.path.suffix.lower()
        if suffix == ".csv":
            with self.path.open(encoding="utf-8-sig", newline="") as source:
                return tuple(dict(row) for row in csv.DictReader(source))
        if suffix in {".json", ".geojson"}:
            with self.path.open(encoding="utf-8") as source:
                payload = json.load(source)
            features = payload.get("features") if isinstance(payload, dict) else None
            if not isinstance(features, list):
                raise DataSourceError("GeoJSON FeatureCollection 형식이 필요합니다.")
            return tuple(feature for feature in features if isinstance(feature, Mapping))
        raise DataSourceConfigurationError(
            "지원 형식은 CSV/GeoJSON입니다. XLSX 전처리는 데이터 버전 고정 후 구현합니다."
        )


@dataclass(frozen=True, slots=True)
class BikeFieldMap:
    """공식 명세에서 확인한 실제 응답 키를 주입한다(추측 기본값 없음)."""

    station_id: str
    name: str
    latitude: str
    longitude: str
    available_bikes: str
    available_docks: str | None = None


@dataclass(frozen=True, slots=True)
class SeoulBikeStationAdapter:
    client: SeoulOpenApiClient
    service_name: str
    fields: BikeFieldMap

    def list_stations(self) -> tuple[BikeStation, ...]:
        rows = self.client.fetch_page(self.service_name)
        stations: list[BikeStation] = []
        try:
            for row in rows:
                stations.append(
                    BikeStation(
                        station_id=str(row[self.fields.station_id]),
                        name=str(row[self.fields.name]),
                        coordinates=Coordinates(
                            latitude=float(row[self.fields.latitude]),
                            longitude=float(row[self.fields.longitude]),
                        ),
                        available_bikes=int(float(row[self.fields.available_bikes])),
                        available_docks=(
                            int(float(row[self.fields.available_docks]))
                            if self.fields.available_docks
                            else 0
                        ),
                        is_sample=False,
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataSourceError("따릉이 응답 스키마가 확정된 필드 매핑과 다릅니다.") from exc
        return tuple(stations)


# TODO: 가로수는 배포 가능한 라이선스를 선택한 뒤 수종 필드와 좌표계를 검증하고
#       edge buffer로 결합한다. 성별 필드가 없으면 은행나무 전체를 회피 대상으로 삼는다.
# TODO: 그늘막 주소를 지오코딩하되 결과/정확도/원본 주소를 함께 보존한다.
# TODO: 도로 열선의 텍스트 설치구간을 수동 검수 가능한 선형 geometry로 map-match한다.
# TODO: 가로등은 좌표 컬럼을 검증하고 운영상태가 없음을 UI 데이터 품질에 표시한다.
