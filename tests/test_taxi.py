"""TMAP 예상 택시요금 adapter 테스트."""

from src.domain import Coordinates
from src.reporting.taxi import TmapTaxiFareProvider


def test_tmap_taxi_fare_adapter(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"features": [{"properties": {"taxiFare": 8_200}}]}

    monkeypatch.setattr("src.reporting.taxi.requests.post", lambda *args, **kwargs: Response())
    fare = TmapTaxiFareProvider("test-key").estimate(
        Coordinates(37.5, 127.0), Coordinates(37.51, 127.01)
    )
    assert fare == 8_200
