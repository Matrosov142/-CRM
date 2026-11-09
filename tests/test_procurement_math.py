from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.procurement_math import calculate_order_totals


def test_order_totals_round_each_line_and_sum():
    lines = [
        SimpleNamespace(quantity=Decimal("2.500"), unit_price=Decimal("100.10")),
        SimpleNamespace(quantity=Decimal("1.000"), unit_price=Decimal("0.99")),
    ]
    calculated, total = calculate_order_totals(lines)
    assert [row[2] for row in calculated] == [Decimal("250.25"), Decimal("0.99")]
    assert total == Decimal("251.24")


def test_order_rejects_zero_quantity():
    with pytest.raises(ValueError, match="Количество"):
        calculate_order_totals([SimpleNamespace(quantity=Decimal("0"), unit_price=Decimal("10"))])


def test_order_rejects_zero_total():
    with pytest.raises(ValueError, match="Сумма"):
        calculate_order_totals([SimpleNamespace(quantity=Decimal("1"), unit_price=Decimal("0"))])
