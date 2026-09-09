"""경로 주변 음식점 검색 테스트."""

from src.domain import Coordinates, Restaurant, RoutePath
from src.places.restaurants import find_route_restaurants, route_sample_points


def _path() -> RoutePath:
    return RoutePath(
        tuple(Coordinates(37.5 + index * 0.001, 127.0) for index in range(10)),
        1_000,
        13,
        50,
    )


def test_route_sampling_is_bounded_and_includes_endpoints() -> None:
    sampled = route_sample_points(_path())
    assert len(sampled) == 3
    assert sampled[0] == _path().path[0]
    assert sampled[-1] == _path().path[-1]


def test_route_sampling_uses_travel_distance_not_vertex_index() -> None:
    path = RoutePath(
        (
            Coordinates(37.5, 127.0),
            Coordinates(37.50001, 127.0),
            Coordinates(37.50002, 127.0),
            Coordinates(37.51, 127.0),
        ),
        1_100,
        15,
        50,
    )
    middle = route_sample_points(path)[1]
    assert 37.504 < middle.latitude < 37.506


def test_restaurant_search_deduplicates_providers_and_limits_results() -> None:
    restaurant = Restaurant(
        "place-1",
        "테스트 식당",
        Coordinates(37.5, 127.0),
        "서울",
        "Google Places",
        rating=4.5,
        user_rating_count=100,
    )

    class Provider:
        def nearby(self, point, radius_m, limit):
            return (restaurant,)

    results, errors = find_route_restaurants(_path(), (Provider(),), 250, 8)
    assert results == (restaurant,)
    assert len(errors) == 1
    assert "일부 구간" in errors[0]


def test_restaurant_search_balances_origin_middle_and_destination() -> None:
    calls = []

    class Provider:
        def nearby(self, point, radius_m, limit):
            calls.append(point)
            section = len(calls)
            return tuple(
                Restaurant(
                    f"section-{section}-{index}",
                    f"구간 {section} 식당 {index}",
                    point,
                    "서울",
                    "테스트",
                    rating=4.3,
                    user_rating_count=50,
                )
                for index in range(limit)
            )

    results, errors = find_route_restaurants(_path(), (Provider(),), 250, 6)

    assert len(calls) == 3
    assert len(results) == 6
    assert {restaurant.provider_id.split("-")[1] for restaurant in results} == {"1", "2", "3"}
    assert errors == ()


def test_restaurant_search_prefers_well_rated_reviewed_places() -> None:
    point = _path().path[0]
    ordinary = Restaurant(
        "ordinary", "일반 식당", point, "서울", "Google Places", 3.9, 500
    )
    unproven = Restaurant(
        "unproven", "리뷰 적은 식당", point, "서울", "Google Places", 4.9, 3
    )
    favorite = Restaurant(
        "favorite", "검증된 맛집", point, "서울", "Google Places", 4.4, 120
    )

    class Provider:
        def nearby(self, point, radius_m, limit):
            return ordinary, unproven, favorite

    results, errors = find_route_restaurants(_path(), (Provider(),), 2_000, 8)
    assert results == (favorite,)
    assert errors == ()
