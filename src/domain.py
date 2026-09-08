"""UI와 외부 공급자에 의존하지 않는 도메인 모델."""

from dataclasses import dataclass
from enum import StrEnum


class RouteMode(StrEnum):
    SUMMER = "여름"
    AUTUMN = "가을"
    WINTER = "겨울"
    SAFETY = "안심"

    @property
    def description(self) -> str:
        return {
            RouteMode.SUMMER: "그늘이 많은 길을 우선합니다.",
            RouteMode.AUTUMN: "은행나무 밀집 구간을 덜 지나도록 돕습니다.",
            RouteMode.WINTER: "결빙 위험을 줄이고 도로 열선 구간을 우선합니다.",
            RouteMode.SAFETY: "가로등과 야간 보행 지표가 좋은 길을 우선합니다.",
        }[self]


@dataclass(frozen=True, slots=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class RouteRequest:
    origin: str
    destination: str
    mode: RouteMode
    use_osm: bool = False
    origin_coordinates: Coordinates | None = None
    destination_coordinates: Coordinates | None = None
    use_real_data: bool = False

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.origin.strip() and self.origin_coordinates is None:
            errors.append("출발지를 입력해 주세요.")
        if not self.destination.strip() and self.destination_coordinates is None:
            errors.append("도착지를 입력해 주세요.")
        if (
            self.origin.strip()
            and self.origin.strip() == self.destination.strip()
            and self.origin_coordinates is None
            and self.destination_coordinates is None
        ):
            errors.append("출발지와 도착지는 서로 달라야 합니다.")
        return tuple(errors)


@dataclass(frozen=True, slots=True)
class RoutePath:
    path: tuple[Coordinates, ...]
    distance_m: float
    duration_min: float
    comfort_score: float


@dataclass(frozen=True, slots=True)
class RouteComparison:
    origin: Coordinates
    destination: Coordinates
    baseline: RoutePath
    optimized: RoutePath
    mode: RouteMode
    detour_ratio: float
    source: str
    is_sample: bool
    method: str
    explanation: str
    fallback_reason: str | None = None
    notice: str | None = None
    model_version: str | None = None
    indicator_source: str = "sample"


@dataclass(frozen=True, slots=True)
class BikeStation:
    station_id: str
    name: str
    coordinates: Coordinates
    available_bikes: int
    available_docks: int
    is_sample: bool
    inventory_known: bool = True


@dataclass(frozen=True, slots=True)
class BikeRecommendation:
    eligible: bool
    recommended: bool
    reason: str
    pickup_station: BikeStation | None = None
    dropoff_station: BikeStation | None = None
    walking_distance_m: float = 0.0
    cycling_distance_m: float = 0.0
    total_distance_m: float = 0.0
    estimated_duration_min: float = 0.0
    is_sample: bool = True
    inventory_known: bool = True
