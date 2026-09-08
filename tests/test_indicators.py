"""합성 지표 결합과 정규화 테스트."""

from src.indicators.sample import load_sample_indicators
from src.indicators.scoring import INDICATOR_FIELDS, attach_sample_indicators, normalize_indicator
from src.routing.graph import load_sample_walking_graph


def test_normalize_indicator_clamps_range() -> None:
    assert normalize_indicator(-0.2) == 0.0
    assert normalize_indicator(0.4) == 0.4
    assert normalize_indicator(1.4) == 1.0


def test_all_sample_records_are_marked() -> None:
    data = load_sample_indicators()
    assert data["features"]
    assert all(feature["properties"]["is_sample"] is True for feature in data["features"])


def test_every_edge_receives_normalized_indicators() -> None:
    graph = attach_sample_indicators(load_sample_walking_graph())
    for _, _, data in graph.edges(data=True):
        for field in INDICATOR_FIELDS:
            assert field in data
            assert 0.0 <= data[field] <= 1.0

