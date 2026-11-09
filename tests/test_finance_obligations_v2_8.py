from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas import FinanceObligationCreateRequest, FinanceAllocationCreateRequest

def test_obligation_accepts_receivable_rub_amount():
    payload = FinanceObligationCreateRequest(
        obligation_number="AR-001", side="receivable", amount=Decimal("1200.50"),
        counterparty_name="ООО Ромашка", due_date=datetime(2026, 12, 1, tzinfo=timezone.utc))
    assert payload.amount == Decimal("1200.50")
    assert payload.side == "receivable"

def test_obligation_rejects_unknown_side():
    with pytest.raises(ValidationError):
        FinanceObligationCreateRequest(obligation_number="X", side="other", amount=Decimal("1.00"),
            counterparty_name="ООО Ромашка", due_date=datetime.now(timezone.utc))

def test_obligation_rejects_zero_amount():
    with pytest.raises(ValidationError):
        FinanceObligationCreateRequest(obligation_number="X", side="payable", amount=Decimal("0.00"),
            counterparty_name="ООО Ромашка", due_date=datetime.now(timezone.utc))

def test_allocation_requires_positive_amount_and_movement():
    payload = FinanceAllocationCreateRequest(movement_id=uuid4(), amount=Decimal("0.01"))
    assert payload.amount == Decimal("0.01")
    with pytest.raises(ValidationError):
        FinanceAllocationCreateRequest(movement_id=uuid4(), amount=Decimal("0.00"))
