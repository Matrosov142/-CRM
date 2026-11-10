from decimal import Decimal
import pytest

from app.tender_pricing import calculate_tender_position_pricing
from app.schemas import TenderPositionPricingRequest


def calc(**overrides):
    values = dict(quantity=Decimal("10.000"), purchase=Decimal("1000.00"),
        logistics=Decimal("50.00"), processing=Decimal("20.00"),
        packaging=Decimal("10.00"), tax=Decimal("0.00"), other=Decimal("5.00"),
        conservative_margin=Decimal("10"), target_margin=Decimal("20"),
        aggressive_margin=Decimal("30"))
    values.update(overrides)
    return calculate_tender_position_pricing(**values)


def test_pricing_components_and_totals_are_calculated_exactly():
    result = calc()
    assert result["unit_cost"] == "1085.00"
    assert result["total_cost"] == "10850.00"
    assert result["scenarios"]["целевой"]["unit_sale_price"] == "1356.25"
    assert result["scenarios"]["целевой"]["total_profit"] == "2712.50"
    assert result["currency"] == "RUB"


def test_scenarios_have_increasing_prices_for_increasing_margin():
    scenarios = calc()["scenarios"]
    prices = [Decimal(scenarios[k]["unit_sale_price"]) for k in ("осторожный", "целевой", "агрессивный")]
    assert prices[0] < prices[1] < prices[2]


@pytest.mark.parametrize("field,value", [("purchase", "-1"), ("logistics", "NaN"), ("tax", "Infinity")])
def test_negative_or_non_finite_costs_are_rejected(field, value):
    with pytest.raises(ValueError):
        calc(**{field: Decimal(value)})


def test_zero_quantity_is_rejected():
    with pytest.raises(ValueError, match="Количество"):
        calc(quantity=Decimal("0"))


def test_margin_at_100_percent_is_rejected():
    with pytest.raises(ValueError, match="меньше 100"):
        calc(target_margin=Decimal("100"))


def test_api_schema_rejects_invalid_margin():
    with pytest.raises(Exception):
        TenderPositionPricingRequest(purchase="100", aggressive_margin="100")


def test_tender_router_exposes_preview_endpoint():
    from app.routers.tenders import router
    paths = {route.path for route in router.routes}
    assert "/api/v1/tenders/{tender_id}/positions/{position_id}/pricing-preview" in paths
