"""Transparent delivery cost estimates for carrier and own-fleet scenarios.
All monetary values are RUB; estimates are not carrier tariffs or route quotes.
"""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

def carrier_cost(*, base_fee: Decimal, distance_km: Decimal, price_per_km: Decimal,
                 loading_fee: Decimal = Decimal("0"), unloading_fee: Decimal = Decimal("0"),
                 tolls: Decimal = Decimal("0"), insurance: Decimal = Decimal("0"),
                 extra: Decimal = Decimal("0")) -> Decimal:
    values = (base_fee, distance_km, price_per_km, loading_fee, unloading_fee, tolls, insurance, extra)
    if any(v < 0 for v in values):
        raise ValueError("Значения тарифа и расстояния не могут быть отрицательными")
    return money(base_fee + distance_km * price_per_km + loading_fee + unloading_fee + tolls + insurance + extra)

def own_fleet_cost(*, distance_km: Decimal, fuel_consumption_l_100km: Decimal,
                   fuel_price_per_l: Decimal, driver_cost: Decimal = Decimal("0"),
                   depreciation_per_km: Decimal = Decimal("0"), maintenance_per_km: Decimal = Decimal("0"),
                   tolls: Decimal = Decimal("0"), loading_fee: Decimal = Decimal("0"),
                   unloading_fee: Decimal = Decimal("0"), extra: Decimal = Decimal("0"),
                   round_trip: bool = False) -> dict:
    values = (distance_km, fuel_consumption_l_100km, fuel_price_per_l, driver_cost,
              depreciation_per_km, maintenance_per_km, tolls, loading_fee, unloading_fee, extra)
    if any(v < 0 for v in values):
        raise ValueError("Расходы и параметры не могут быть отрицательными")
    trip_distance = distance_km * (Decimal("2") if round_trip else Decimal("1"))
    fuel_liters = trip_distance * fuel_consumption_l_100km / Decimal("100")
    fuel = money(fuel_liters * fuel_price_per_l)
    depreciation = money(trip_distance * depreciation_per_km)
    maintenance = money(trip_distance * maintenance_per_km)
    total = money(fuel + depreciation + maintenance + driver_cost + tolls + loading_fee + unloading_fee + extra)
    return {"distance_km": trip_distance, "fuel_liters": fuel_liters.quantize(Decimal("0.001")),
            "fuel_cost": fuel, "depreciation_cost": depreciation, "maintenance_cost": maintenance,
            "driver_cost": money(driver_cost), "tolls": money(tolls),
            "loading_fee": money(loading_fee), "unloading_fee": money(unloading_fee),
            "extra": money(extra), "total": total}
