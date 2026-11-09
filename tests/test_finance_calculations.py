from decimal import Decimal as D
import pytest
from app.finance import CostBreakdown, calculate_profitability, calculate_unit_economics, compare_plan_actual


def test_profit_and_margin():
    result = calculate_profitability(D("10000"), CostBreakdown(D("6000"), D("500"), D("700"), D("200"), D("100")))
    assert result.costs == D("7500.00")
    assert result.profit == D("2500.00")
    assert result.margin_percent == D("25.00")


def test_loss_is_negative_and_margin_negative():
    result = calculate_profitability(D("100"), CostBreakdown(procurement=D("120")))
    assert result.profit == D("-20.00")
    assert result.margin_percent == D("-20.00")


def test_zero_revenue_margin_is_none():
    result = calculate_profitability(D("0"), CostBreakdown(other=D("10")))
    assert result.profit == D("-10.00")
    assert result.margin_percent is None


def test_unit_economics():
    result = calculate_unit_economics(D("1000"), D("10"), CostBreakdown(procurement=D("600")))
    assert result["revenue_per_unit"] == D("100.00")
    assert result["cost_per_unit"] == D("60.00")
    assert result["profit_per_unit"] == D("40.00")


def test_plan_actual_variances():
    result = compare_plan_actual(D("1000"), CostBreakdown(procurement=D("600")),
                                 D("1100"), CostBreakdown(procurement=D("700")))
    assert result["profit_variance"] == D("0.00")
    assert result["cost_variance"] == D("100.00")
    assert result["revenue_variance"] == D("100.00")


@pytest.mark.parametrize("cost", [D("-1"), D("NaN"), D("Infinity")])
def test_invalid_cost_rejected(cost):
    with pytest.raises(ValueError):
        calculate_profitability(D("100"), CostBreakdown(other=cost))


def test_invalid_quantity_rejected():
    with pytest.raises(ValueError):
        calculate_unit_economics(D("100"), D("0"), CostBreakdown())
