from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas import ProcurementOrderCreate


def test_supplier_inn_accepts_10_or_12_digits():
    base = {
        "order_number": "PO-001",
        "supplier_name": "Поставщик",
        "lines": [{"item_name": "Труба", "quantity": "2.000", "unit": "шт", "unit_price": "150.00"}],
    }
    assert ProcurementOrderCreate(**{**base, "supplier_inn": "1234567890"}).supplier_inn == "1234567890"
    assert ProcurementOrderCreate(**{**base, "supplier_inn": "123456789012"}).supplier_inn == "123456789012"


def test_supplier_inn_rejects_invalid_length_or_letters():
    base = {
        "order_number": "PO-001",
        "supplier_name": "Поставщик",
        "lines": [{"item_name": "Труба", "quantity": "2.000", "unit": "шт", "unit_price": "150.00"}],
    }
    with pytest.raises(ValidationError):
        ProcurementOrderCreate(**{**base, "supplier_inn": "12345"})
    with pytest.raises(ValidationError):
        ProcurementOrderCreate(**{**base, "supplier_inn": "123456789A"})


def test_order_requires_at_least_one_line():
    with pytest.raises(ValidationError):
        ProcurementOrderCreate(order_number="PO-002", supplier_name="Поставщик", lines=[])
