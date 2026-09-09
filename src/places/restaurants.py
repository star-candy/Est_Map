"""TMAP/Google을 통한 경로 주변 음식점 검색."""

from dataclasses import dataclass
from math import ceil
from typing import Protocol

import requests

from src.domain import Coordinates, Restaurant, RoutePath
from src.routing.graph import haversine_m


class RestaurantSearchError(RuntimeError):
    pass


class RestaurantProvider(Protocol):
    def nearby(
        self, point: Coordinates, radius_m: float, limit: int
    ) -> tuple[Restaurant, ...]: ...


def route_sample_points(path: RoutePath, maximum: int = 3) -> tuple[Coordinates, ...]:
    points = path.path
    if len(points) <= maximum or maximum <= 1:
        return points
    segment_lengths = [
        haversine_m(points[index - 1], points[index]) for index in range(1, len(points))
    ]
    total = sum(segment_lengths)
    if total <= 0:
        return (points[0],)

    sampled: list[Coordinates] = []
    segment_index = 0
    distance_before_segment = 0.0
    for sample_index in range(maximum):
        target = total * sample_index / (maximum - 1)
        while (
            segment_index < len(segment_lengths) - 1
            and distance_before_segment + segment_lengths[segment_index] < target
        ):
            distance_before_segment += segment_lengths[segment_index]
            segment_index += 1
        length = segment_lengths[segment_index]
        ratio = min(1.0, max(0.0, (target - distance_before_segment) / max(length, 1e-9)))
        start, end = points[segment_index], points[segment_index + 1]
        sampled.append(
            Coordinates(
                start.latitude + (end.latitude - start.latitude) * ratio,
                start.longitude + (end.longitude - start.longitude) * ratio,
            )
        )
    return tuple(sampled)


@dataclass(frozen=True, slots=True)
class GoogleRestaurantProvider:
    api_key: str
    timeout_seconds: int = 20
    endpoint: str = "https://places.googleapis.com/v1/places:searchNearby"

    def nearby(self, point: Coordinates, radius_m: float, limit: int) -> tuple[Restaurant, ...]:
        body = {
            "includedTypes": ["restaurant"],
            "maxResultCount": min(limit, 20),
            "rankPreference": "POPULARITY",
            "languageCode": "ko",
            "locationRestriction": {"circle": {"center": {
                "latitude": point.latitude, "longitude": point.longitude
            }, "radius": radius_m}},
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,places.location,"
                "places.rating,places.userRatingCount,places.googleMapsUri"
            ),
        }
        try:
            response = requests.post(
                self.endpoint,
                json=body,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            places = response.json().get("places", [])
            return tuple(
                Restaurant(
                    provider_id=str(place["id"]),
                    name=str(place["displayName"]["text"]),
                    coordinates=Coordinates(
                        float(place["location"]["latitude"]),
                        float(place["location"]["longitude"]),
                    ),
                    address=str(place.get("formattedAddress", "")),
                    provider="Google Places",
                    rating=float(place["rating"]) if "rating" in place else None,
                    user_rating_count=(
                        int(place["userRatingCount"]) if "userRatingCount" in place else None
                    ),
                    map_url=place.get("googleMapsUri"),
                )
                for place in places
            )
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise RestaurantSearchError(
                "Google 맛집 검색에 실패했습니다. 잠시 후 다시 시도하거나 API 설정을 확인하세요."
            ) from exc


@dataclass(frozen=True, slots=True)
class TmapRestaurantProvider:
    app_key: str
    timeout_seconds: int = 20
    endpoint: str = "https://apis.openapi.sk.com/tmap/pois"

    def nearby(self, point: Coordinates, radius_m: float, limit: int) -> tuple[Restaurant, ...]:
        params = {
            "version": "1", "searchKeyword": "음식점", "count": min(limit, 20),
            "centerLon": point.longitude, "centerLat": point.latitude,
            "radius": max(1, round(radius_m / 1000, 2)),
            "reqCoordType": "WGS84GEO", "resCoordType": "WGS84GEO", "searchtypCd": "R",
        }
        try:
            response = requests.get(
                self.endpoint, params=params, headers={"appKey": self.app_key},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            pois = response.json()["searchPoiInfo"]["pois"]["poi"]
            return tuple(
                Restaurant(
                    provider_id=str(poi["id"]), name=str(poi["name"]),
                    coordinates=Coordinates(
                        float(poi.get("frontLat") or poi["noorLat"]),
                        float(poi.get("frontLon") or poi["noorLon"]),
                    ),
                    address=" ".join(str(poi.get(key, "")) for key in (
                        "upperAddrName", "middleAddrName", "lowerAddrName", "detailAddrName"
                    )).strip(),
                    provider="TMAP POI",
                )
                for poi in pois
            )
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise RestaurantSearchError(
                "TMAP 맛집 검색에 실패했습니다. 잠시 후 다시 시도하거나 API 설정을 확인하세요."
            ) from exc


def find_route_restaurants(
    path: RoutePath,
    providers: tuple[RestaurantProvider, ...],
    radius_m: float,
    limit: int,
) -> tuple[tuple[Restaurant, ...], tuple[str, ...]]:
    sample_points = route_sample_points(path)
    if not sample_points or limit <= 0:
        return (), ()
    per_point_limit = max(2, ceil(limit / len(sample_points)))
    buckets: list[list[Restaurant]] = [[] for _ in sample_points]
    errors: list[str] = []
    for index, point in enumerate(sample_points):
        local_seen: set[tuple[str, str]] = set()
        for provider in providers:
            try:
                for restaurant in provider.nearby(point, radius_m, per_point_limit):
                    if haversine_m(point, restaurant.coordinates) > radius_m:
                        continue
                    key = (restaurant.provider, restaurant.provider_id)
                    if key not in local_seen:
                        buckets[index].append(restaurant)
                        local_seen.add(key)
            except RestaurantSearchError as exc:
                if str(exc) not in errors:
                    errors.append(str(exc))

    qualified_section_count = 0
    for index, bucket in enumerate(buckets):
        qualified = [
            restaurant
            for restaurant in bucket
            if restaurant.rating is not None
            and restaurant.rating >= 4.0
            and (restaurant.user_rating_count or 0) >= 20
        ]
        if qualified:
            qualified_section_count += 1
            buckets[index] = sorted(
                qualified,
                key=lambda restaurant: (
                    -(restaurant.rating or 0.0),
                    -(restaurant.user_rating_count or 0),
                ),
            )
    if qualified_section_count == 0:
        errors.append(
            "평점 4.0·리뷰 20개 이상인 후보가 없어 가까운 일반 음식점을 표시합니다."
        )
    elif qualified_section_count < len(buckets):
        errors.append(
            "일부 구간은 평점·리뷰 기준을 충족한 후보가 없어 가까운 음식점을 함께 표시합니다."
        )

    # 출발지 결과가 먼저 한도를 채우지 않도록 각 구간에서 한 곳씩 순환 선택한다.
    selected: list[Restaurant] = []
    selected_keys: set[tuple[str, str]] = set()
    depth = 0
    while len(selected) < limit and any(depth < len(bucket) for bucket in buckets):
        for bucket in buckets:
            if depth >= len(bucket):
                continue
            restaurant = bucket[depth]
            key = (restaurant.provider, restaurant.provider_id)
            if key not in selected_keys:
                selected.append(restaurant)
                selected_keys.add(key)
            if len(selected) >= limit:
                break
        depth += 1
    return tuple(selected), tuple(errors)
