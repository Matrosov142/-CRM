"""Pure monetary calculations for supplier purchase orders."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def calculate_order_totals(lines):
    """Return normalized (line_number, item, line_total) and RUB order total."""
    if not lines:
        raise ValueError("Заказ должен содержать хотя бы одну позицию")
    calculated = []
    total = Decimal("0.00")
    for number, item in enumerate(lines, start=1):
        try:
            quantity = Decimal(str(item.quantity))
            unit_price = Decimal(str(item.unit_price))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Некорректное количество или цена")
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError("Количество должно быть больше нуля")
        if not unit_price.is_finite() or unit_price < 0:
            raise ValueError("Цена не может быть отрицательной")
        line_total = (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += line_total
        calculated.append((number, item, line_total))
    total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if total <= 0:
        raise ValueError("Сумма заказа должна быть больше нуля")
    return calculated, total
