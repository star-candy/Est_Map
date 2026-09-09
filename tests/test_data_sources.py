from pathlib import Path

import pytest

from src.data_sources.base import DatasetProvenance, DataSourceConfigurationError
from src.data_sources.seoul import (
    SEOUL_DISTRICT_CCTV_SERVICES,
    LocalPublicDatasetAdapter,
    SeoulIllegalParkingCctvAdapter,
    SeoulOpenApiClient,
)


def test_real_file_adapter_is_optional() -> None:
    adapter = LocalPublicDatasetAdapter(
        path=None,
        provenance=DatasetProvenance(
            provider="서울특별시",
            dataset_name="테스트",
            official_url="https://data.seoul.go.kr/",
            source_crs=None,
            license_name="공공누리 제1유형",
        ),
    )
    with pytest.raises(DataSourceConfigurationError):
        adapter.list_records()


def test_csv_adapter_preserves_unmapped_columns(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("확인된컬럼,값\n주소,1\n", encoding="utf-8-sig")
    adapter = LocalPublicDatasetAdapter(
        source,
        DatasetProvenance("기관", "자료", "https://example.test", None, "확인 필요"),
    )
    assert adapter.list_records() == ({"확인된컬럼": "주소", "값": "1"},)


def test_seoul_client_requires_key_and_service() -> None:
    with pytest.raises(DataSourceConfigurationError):
        SeoulOpenApiClient(api_key="").fetch_page("")


def test_cctv_adapter_combines_districts_and_filters_non_parking_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        SeoulOpenApiClient,
        "fetch_all",
        lambda self, service: (
            {
                "FIX_CCTV_ADDR": "서울시 테스트로 1",
                "LAT": "37.55",
                "LOT": "126.98",
                "CGG_CD": "테스트구",
                "CRDN_BRNCH_NM": "테스트 지점",
                "GRNDS_SE": "불법주정차단속용",
            },
            {"LAT": "37.55", "LOT": "126.98", "GRNDS_SE": "버스전용차로단속용"},
        ),
    )
    records = SeoulIllegalParkingCctvAdapter(SeoulOpenApiClient("key")).list_records()
    assert len(SEOUL_DISTRICT_CCTV_SERVICES) == 25
    assert len(records) == 25
    assert all(record["category"] == "불법주정차단속용" for record in records)
    assert all(record["is_sample"] == "false" for record in records)
