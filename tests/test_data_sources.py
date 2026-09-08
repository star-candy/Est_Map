from pathlib import Path

import pytest

from src.data_sources.base import DatasetProvenance, DataSourceConfigurationError
from src.data_sources.seoul import LocalPublicDatasetAdapter, SeoulOpenApiClient


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
