from datetime import date
from decimal import Decimal
import pytest
from app.finance_ledger import (
    CashMovement, MovementKind, MovementStatus,
    summarize_cash_movements, outstanding_amount,
)


def movement(mid, kind, amount, status=MovementStatus.CONFIRMED):
    return CashMovement(mid, kind, Decimal(amount), status, date(2026, 11, 8), "ООО Контрагент")


def test_only_confirmed_movements_affect_cash_flow():
    result = summarize_cash_movements([
        movement("1", MovementKind.RECEIPT, "1000.00"),
        movement("2", MovementKind.PAYMENT, "250.50"),
        movement("3", MovementKind.RECEIPT, "900", MovementStatus.DRAFT),
        movement("4", MovementKind.PAYMENT, "100", MovementStatus.CANCELLED),
    ])
    assert result == {
        "confirmed_receipts": Decimal("1000.00"),
        "confirmed_payments": Decimal("250.50"),
        "net_cash_flow": Decimal("749.50"),
        "confirmed_count": 2, "draft_count": 1, "cancelled_count": 1,
    }


def test_outstanding_balance_after_partial_payments():
    assert outstanding_amount("1000", ["200.10", "300.20"]) == Decimal("499.70")


def test_overpayment_is_rejected():
    with pytest.raises(ValueError, match="превышает обязательство"):
        outstanding_amount("100", ["60", "50"])


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity"])
def test_invalid_movement_amount_rejected(amount):
    with pytest.raises(ValueError):
        movement("x", MovementKind.RECEIPT, amount)


def test_blank_counterparty_rejected():
    with pytest.raises(ValueError, match="контрагент"):
        CashMovement("x", MovementKind.RECEIPT, Decimal("1"), MovementStatus.CONFIRMED,
                     date(2026, 11, 8), " ")
