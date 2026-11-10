from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas import WarehouseReceiptCreateRequest


def sample(**overrides):
    data = {
        "receipt_number": "ПР-001",
        "procurement_order_id": uuid4(),
        "location": "Стеллаж А-1",
        "lines": [{"procurement_order_line_id": uuid4(), "received_quantity": "10.000",
                   "accepted_quantity": "8.000", "defective_quantity": "2.000",
                   "defect_note": "Повреждена упаковка"}],
    }
    data.update(overrides)
    return data


def test_receipt_schema_accepts_partial_good_and_defective_quantities():
    payload = WarehouseReceiptCreateRequest(**sample())
    line = payload.lines[0]
    assert line.received_quantity == Decimal("10.000")
    assert line.accepted_quantity == Decimal("8.000")
    assert line.defective_quantity == Decimal("2.000")


def test_receipt_schema_rejects_negative_accepted_quantity():
    data = sample()
    data["lines"][0]["accepted_quantity"] = "-1"
    with pytest.raises(ValidationError):
        WarehouseReceiptCreateRequest(**data)


def test_receipt_schema_requires_nonempty_lines():
    with pytest.raises(ValidationError):
        WarehouseReceiptCreateRequest(**sample(lines=[]))
