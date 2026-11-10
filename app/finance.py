"""Pure RUB order/position profitability calculations; no persistence or tax advice."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")


def _money(value: Decimal, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Некорректная денежная сумма: {label}")
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"Сумма «{label}» должна быть конечной и неотрицательной")
    return amount.quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CostBreakdown:
    procurement: Decimal = Decimal("0")
    logistics: Decimal = Decimal("0")
    processing: Decimal = Decimal("0")
    packaging: Decimal = Decimal("0")
    other: Decimal = Decimal("0")

    def total(self) -> Decimal:
        values = {
            "закупка": self.procurement,
            "логистика": self.logistics,
            "обработка": self.processing,
            "упаковка": self.packaging,
            "прочие расходы": self.other,
        }
        return sum((_money(v, k) for k, v in values.items()), Decimal("0.00")).quantize(MONEY)


@dataclass(frozen=True)
class Profitability:
    revenue: Decimal
    costs: Decimal
    profit: Decimal
    margin_percent: Decimal | None


def calculate_profitability(revenue: Decimal, costs: CostBreakdown) -> Profitability:
    """Margin = profit/revenue*100. None when revenue is zero; all values are RUB."""
    normalized_revenue = _money(revenue, "выручка")
    normalized_costs = costs.total()
    profit = (normalized_revenue - normalized_costs).quantize(MONEY, rounding=ROUND_HALF_UP)
    margin = None if normalized_revenue == 0 else (profit / normalized_revenue * Decimal("100")).quantize(PERCENT, rounding=ROUND_HALF_UP)
    return Profitability(normalized_revenue, normalized_costs, profit, margin)


def calculate_unit_economics(revenue: Decimal, quantity: Decimal, costs: CostBreakdown) -> dict[str, Decimal | None]:
    """Return per-unit revenue/cost/profit; quantity must be positive."""
    try:
        qty = Decimal(str(quantity))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Некорректное количество")
    if not qty.is_finite() or qty <= 0:
        raise ValueError("Количество должно быть больше нуля")
    result = calculate_profitability(revenue, costs)
    return {
        "revenue_per_unit": (result.revenue / qty).quantize(MONEY, rounding=ROUND_HALF_UP),
        "cost_per_unit": (result.costs / qty).quantize(MONEY, rounding=ROUND_HALF_UP),
        "profit_per_unit": (result.profit / qty).quantize(MONEY, rounding=ROUND_HALF_UP),
        "margin_percent": result.margin_percent,
    }


def compare_plan_actual(plan_revenue: Decimal, plan_costs: CostBreakdown,
                        actual_revenue: Decimal, actual_costs: CostBreakdown) -> dict[str, Profitability | Decimal]:
    """Compare planned and actual figures without mixing the two data sets."""
    plan = calculate_profitability(plan_revenue, plan_costs)
    actual = calculate_profitability(actual_revenue, actual_costs)
    return {
        "plan": plan,
        "actual": actual,
        "profit_variance": (actual.profit - plan.profit).quantize(MONEY, rounding=ROUND_HALF_UP),
        "cost_variance": (actual.costs - plan.costs).quantize(MONEY, rounding=ROUND_HALF_UP),
        "revenue_variance": (actual.revenue - plan.revenue).quantize(MONEY, rounding=ROUND_HALF_UP),
    }
