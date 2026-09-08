"""LLM과 독립적인 이동 비용 및 탄소 계산."""

from dataclasses import dataclass
from math import ceil

from config.accounting import ACCOUNTING, AccountingAssumptions


@dataclass(frozen=True, slots=True)
class TripAccounting:
    distance_m: float
    carbon_saved_g: float
    taxi_saved_krw: int


def estimate_taxi_fare_krw(
    distance_m: float, assumptions: AccountingAssumptions = ACCOUNTING
) -> int:
    if distance_m <= 0:
        return 0
    excess = max(0.0, distance_m - assumptions.taxi_base_distance_m)
    increments = ceil(excess / assumptions.taxi_increment_distance_m)
    return assumptions.taxi_base_fare_krw + increments * assumptions.taxi_increment_fare_krw


def estimate_carbon_saved_g(
    distance_m: float, assumptions: AccountingAssumptions = ACCOUNTING
) -> float:
    return max(0.0, distance_m) / 1_000.0 * assumptions.passenger_car_co2_g_per_km


def calculate_trip_accounting(
    distance_m: float,
    taxi_replaced: bool,
    assumptions: AccountingAssumptions = ACCOUNTING,
) -> TripAccounting:
    return TripAccounting(
        distance_m=max(0.0, distance_m),
        carbon_saved_g=estimate_carbon_saved_g(distance_m, assumptions),
        taxi_saved_krw=estimate_taxi_fare_krw(distance_m, assumptions) if taxi_replaced else 0,
    )
