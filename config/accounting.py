"""비용·탄소 회계의 명시적인 MVP 가정값."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AccountingAssumptions:
    taxi_base_fare_krw: int = 4_800
    taxi_base_distance_m: float = 1_600.0
    taxi_increment_distance_m: float = 131.0
    taxi_increment_fare_krw: int = 100
    passenger_car_co2_g_per_km: float = 192.0


ACCOUNTING = AccountingAssumptions()
