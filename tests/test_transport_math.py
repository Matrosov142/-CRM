from decimal import Decimal as D
import pytest
from app.transport_math import carrier_cost, own_fleet_cost

def test_carrier_tariff_adds_all_cost_components():
    assert carrier_cost(base_fee=D("500"), distance_km=D("100"), price_per_km=D("20"),
        loading_fee=D("100"), unloading_fee=D("150"), tolls=D("50"), insurance=D("30")) == D("2830.00")

def test_own_fleet_round_trip_accounts_fuel_and_wear():
    result = own_fleet_cost(distance_km=D("100"), fuel_consumption_l_100km=D("20"),
        fuel_price_per_l=D("60"), driver_cost=D("1000"), depreciation_per_km=D("5"),
        maintenance_per_km=D("2"), round_trip=True)
    assert result["fuel_liters"] == D("40.000")
    assert result["fuel_cost"] == D("2400.00")
    assert result["depreciation_cost"] == D("1000.00")
    assert result["maintenance_cost"] == D("400.00")
    assert result["total"] == D("4800.00")

def test_negative_costs_rejected():
    with pytest.raises(ValueError):
        carrier_cost(base_fee=D("-1"), distance_km=D("10"), price_per_km=D("1"))
