import pytest
from pydantic import ValidationError

from app.schemas import SupplierCreateRequest, SupplierRFQCreateRequest


def test_supplier_inn_and_kpp_formats():
    item = SupplierCreateRequest(name="ООО Поставщик", inn="1234567890", kpp="123456789")
    assert item.inn == "1234567890"
    with pytest.raises(ValidationError):
        SupplierCreateRequest(name="ООО Поставщик", inn="12345")


def test_rfq_requires_supplier_and_position():
    base = {
        "rfq_number": "RFQ-001",
        "title": "Запрос цены",
        "message": "Просим предоставить коммерческое предложение",
        "supplier_ids": ["11111111-1111-4111-8111-111111111111"],
        "lines": [{
            "item_name": "Труба стальная",
            "quantity": "12.500",
            "unit": "м",
        }],
    }
    payload = SupplierRFQCreateRequest(**base)
    assert len(payload.lines) == 1
    with pytest.raises(ValidationError):
        SupplierRFQCreateRequest(**{**base, "supplier_ids": []})
    with pytest.raises(ValidationError):
        SupplierRFQCreateRequest(**{**base, "lines": []})


def test_rfq_rejects_nonpositive_quantity():
    with pytest.raises(ValidationError):
        SupplierRFQCreateRequest(
            rfq_number="RFQ-002",
            title="Запрос цены",
            message="Просим предоставить коммерческое предложение",
            supplier_ids=["11111111-1111-4111-8111-111111111111"],
            lines=[{"item_name": "Клапан", "quantity": "0", "unit": "шт"}],
        )
