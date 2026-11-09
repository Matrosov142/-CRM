from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas import SupplierOfferCreateRequest

def test_offer_payload_accepts_explicit_manual_response():
    payload = SupplierOfferCreateRequest(
        supplier_id=uuid4(), source_channel="manual", delivery_cost="100.00",
        vat_treatment="included", vat_amount="20.00",
        lines=[{"rfq_line_id":uuid4(),"offered_item_name":"Труба","quantity":"2","unit":"шт","unit_price":"50.00","specification_match":"match"}],
    )
    assert payload.delivery_cost == Decimal("100.00")
    assert payload.lines[0].unit_price == Decimal("50.00")

def test_offer_payload_rejects_negative_vat():
    with pytest.raises(ValidationError):
        SupplierOfferCreateRequest(
            supplier_id=uuid4(), vat_amount="-1",
            lines=[{"rfq_line_id":uuid4(),"offered_item_name":"Товар","quantity":"1","unit":"шт","unit_price":"1"}],
        )
