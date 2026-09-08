"""주소를 좌표로 변환하는 교체 가능한 geocoding adapter."""

from functools import lru_cache
from typing import Protocol

from config.settings import SETTINGS
from src.domain import Coordinates

SEOUL_BOUNDS = (37.413, 37.715, 126.734, 127.269)
SAMPLE_PLACES: dict[str, Coordinates] = {
    "서울역": Coordinates(37.5547, 126.9707),
    "서울시청": Coordinates(37.5663, 126.9779),
    "광화문": Coordinates(37.5759, 126.9768),
    "경복궁": Coordinates(37.5796, 126.9770),
    "종로3가역": Coordinates(37.5704, 126.9920),
    "동대문디자인플라자": Coordinates(37.5665, 127.0090),
}


class GeocodingError(RuntimeError):
    """사용자 입력을 좌표로 변환할 수 없을 때 발생한다."""


class Geocoder(Protocol):
    def geocode(self, query: str) -> Coordinates:
        """주소 또는 장소명을 위도와 경도로 변환한다."""


def is_in_seoul(point: Coordinates) -> bool:
    south, north, west, east = SEOUL_BOUNDS
    return south <= point.latitude <= north and west <= point.longitude <= east


def validate_seoul(point: Coordinates, label: str) -> None:
    if not is_in_seoul(point):
        raise GeocodingError(f"{label}가 서울시 범위를 벗어났습니다.")


class SampleGeocoder:
    def geocode(self, query: str) -> Coordinates:
        normalized = query.strip().replace(" ", "")
        for name, point in SAMPLE_PLACES.items():
            if normalized == name.replace(" ", ""):
                return point
        examples = ", ".join(SAMPLE_PLACES)
        raise GeocodingError(f"샘플 장소를 찾지 못했습니다. 사용 가능한 장소: {examples}")


@lru_cache(maxsize=128)
def _cached_osm_geocode(query: str) -> Coordinates:
    import osmnx as ox

    ox.settings.requests_timeout = SETTINGS.external_request_timeout_seconds
    try:
        latitude, longitude = ox.geocode(f"{query}, 서울, 대한민국")
    except Exception as exc:
        raise GeocodingError("주소 검색 서비스에 연결하지 못했습니다.") from exc
    return Coordinates(float(latitude), float(longitude))


class OSMGeocoder:
    def geocode(self, query: str) -> Coordinates:
        if not query.strip():
            raise GeocodingError("검색할 주소가 비어 있습니다.")
        return _cached_osm_geocode(query.strip())
