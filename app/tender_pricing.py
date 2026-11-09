"""Transparent per-position tender pricing; all inputs are explicit per-unit RUB amounts."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _amount(value, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Некорректное значение: {label}")
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label}: сумма должна быть конечной и неотрицательной")
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_tender_position_pricing(*, quantity, purchase, logistics, processing,
                                      packaging, tax, other, conservative_margin,
                                      target_margin, aggressive_margin) -> dict:
    """Calculate cost and three selling-price scenarios from per-unit inputs.

    Margin is a share of selling price, not a markup on cost. Tax is an explicit
    per-unit amount; VAT/tax is never inferred from a supplier offer.
    """
    qty = _amount(quantity, "Количество")
    if qty <= 0:
        raise ValueError("Количество должно быть больше нуля")
    components = {
        "Закупочная цена": _amount(purchase, "Закупочная цена"),
        "Логистика": _amount(logistics, "Логистика"),
        "Обработка": _amount(processing, "Обработка"),
        "Упаковка": _amount(packaging, "Упаковка"),
        "Налоги и сборы": _amount(tax, "Налоги и сборы"),
        "Прочие расходы": _amount(other, "Прочие расходы"),
    }
    unit_cost = sum(components.values(), ZERO)
    if unit_cost <= 0:
        raise ValueError("Себестоимость должна быть больше нуля")
    scenarios = {}
    for key, raw_margin in (("осторожный", conservative_margin),
                            ("целевой", target_margin),
                            ("агрессивный", aggressive_margin)):
        margin = _amount(raw_margin, f"Маржа ({key})")
        if margin >= 100:
            raise ValueError("Маржа должна быть меньше 100%")
        rate = margin / Decimal("100")
        unit_price = _money(unit_cost / (Decimal("1") - rate))
        unit_profit = _money(unit_price - unit_cost)
        scenarios[key] = {
            "margin_percent": str(margin.quantize(Decimal("0.01"))),
            "unit_sale_price": str(unit_price),
            "total_sale_price": str(_money(unit_price * qty)),
            "unit_profit": str(unit_profit),
            "total_profit": str(_money(unit_profit * qty)),
            "actual_margin_percent": str((_money(unit_profit / unit_price * 100)).quantize(Decimal("0.01"))),
        }
    return {
        "currency": "RUB",
        "quantity": str(qty),
        "cost_components_per_unit": {k: str(_money(v)) for k, v in components.items()},
        "unit_cost": str(_money(unit_cost)),
        "total_cost": str(_money(unit_cost * qty)),
        "scenarios": scenarios,
        "disclaimer": "Расчёт предварительный и основан на введённых вручную допущениях. Налоги и НДС не определяются автоматически.",
    }
