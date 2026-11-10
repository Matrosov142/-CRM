from decimal import Decimal as D
import pytest
from app.offer_math import line_total, allocate_proportionally, landed_total

def test_line_total_decimal_precision():
    assert line_total(D("2.5"), D("10.10")) == D("25.25")

def test_delivery_and_vat_allocation():
    assert allocate_proportionally(D("100"), D("25"), D("100")) == D("25.00")
    assert allocate_proportionally(D("20"), D("0"), D("0")) == D("0.00")

def test_landed_total_uses_only_declared_vat():
    assert landed_total(D("100"), D("10"), D("20")) == D("130.00")
    assert landed_total(D("100"), D("10"), None) == D("110.00")

def test_negative_amounts_rejected():
    with pytest.raises(ValueError): line_total(D("-1"), D("2"))
    with pytest.raises(ValueError): allocate_proportionally(D("-1"), D("2"), D("3"))

def test_unknown_vat_is_not_silently_added():
    result = landed_total(D("80"), D("5"), None)
    assert result == D("85.00")
