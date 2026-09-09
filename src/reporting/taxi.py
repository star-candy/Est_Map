"""TMAP 자동차 경로의 예상 택시요금 adapter."""

from dataclasses import dataclass

import requests

from src.domain import Coordinates


class TaxiFareError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TmapTaxiFareProvider:
    app_key: str
    timeout_seconds: int = 20
    endpoint: str = "https://apis.openapi.sk.com/tmap/routes"

    def estimate(self, origin: Coordinates, destination: Coordinates) -> int:
        payload = {
            "startX": origin.longitude,
            "startY": origin.latitude,
            "endX": destination.longitude,
            "endY": destination.latitude,
            "reqCoordType": "WGS84GEO",
            "resCoordType": "WGS84GEO",
            "searchOption": "0",
            "trafficInfo": "N",
        }
        try:
            response = requests.post(
                self.endpoint,
                params={"version": "1", "format": "json"},
                json=payload,
                headers={"appKey": self.app_key, "Content-Type": "application/json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            features = response.json()["features"]
            properties = next(
                feature["properties"]
                for feature in features
                if "taxiFare" in feature.get("properties", {})
            )
            fare = int(properties["taxiFare"])
            if fare <= 0:
                raise ValueError("택시요금이 0 이하입니다.")
            return fare
        except (requests.RequestException, KeyError, TypeError, ValueError, StopIteration) as exc:
            raise TaxiFareError("TMAP 예상 택시요금을 조회하지 못했습니다.") from exc
