"""Deterministic supplier-offer totals; VAT is never inferred."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)

def line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    if quantity <= 0 or unit_price < 0:
        raise ValueError("Количество должно быть положительным, цена — неотрицательной")
    return money(quantity * unit_price)

def allocate_proportionally(amount: Decimal, line_value: Decimal, goods_total: Decimal) -> Decimal:
    if amount < 0 or line_value < 0 or goods_total < 0:
        raise ValueError("Суммы не могут быть отрицательными")
    if goods_total == 0:
        return Decimal("0.00")
    return money(amount * line_value / goods_total)

def landed_total(goods: Decimal, delivery: Decimal, declared_vat: Decimal | None) -> Decimal:
    if goods < 0 or delivery < 0 or (declared_vat is not None and declared_vat < 0):
        raise ValueError("Суммы не могут быть отрицательными")
    # If VAT is unknown, return subtotal without pretending it is VAT-inclusive.
    return money(goods + delivery + (declared_vat or Decimal("0.00")))
