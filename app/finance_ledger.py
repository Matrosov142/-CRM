"""Validated cash movement primitives for the POTOK CRM finance ledger.

This module is deliberately not a bank integration or statutory accounting system.
Only confirmed movements affect cash totals; drafts and cancelled entries are excluded.
All amounts are RUB and use Decimal.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum

MONEY = Decimal("0.01")

class MovementKind(StrEnum):
    RECEIPT = "receipt"       # money received from a customer / other source
    PAYMENT = "payment"       # money paid to a supplier / other recipient

class MovementStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


def normalize_amount(value: Decimal | str | int) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Некорректная сумма операции")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Сумма операции должна быть конечной и больше нуля")
    return amount.quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CashMovement:
    movement_id: str
    kind: MovementKind
    amount: Decimal
    status: MovementStatus
    movement_date: date
    counterparty: str
    purpose: str = ""
    order_reference: str | None = None
    document_reference: str | None = None

    def __post_init__(self):
        if not self.movement_id.strip():
            raise ValueError("Не указан идентификатор операции")
        if not self.counterparty.strip():
            raise ValueError("Не указан контрагент")
        object.__setattr__(self, "amount", normalize_amount(self.amount))
        if not isinstance(self.kind, MovementKind):
            object.__setattr__(self, "kind", MovementKind(self.kind))
        if not isinstance(self.status, MovementStatus):
            object.__setattr__(self, "status", MovementStatus(self.status))


def summarize_cash_movements(movements: list[CashMovement]) -> dict[str, Decimal | int]:
    """Summarize confirmed cash movements only; no inferred AR/AP or opening balance."""
    receipts = Decimal("0.00")
    payments = Decimal("0.00")
    confirmed_count = 0
    draft_count = 0
    cancelled_count = 0
    for movement in movements:
        if movement.status == MovementStatus.DRAFT:
            draft_count += 1
            continue
        if movement.status == MovementStatus.CANCELLED:
            cancelled_count += 1
            continue
        confirmed_count += 1
        if movement.kind == MovementKind.RECEIPT:
            receipts += movement.amount
        else:
            payments += movement.amount
    receipts = receipts.quantize(MONEY)
    payments = payments.quantize(MONEY)
    return {
        "confirmed_receipts": receipts,
        "confirmed_payments": payments,
        "net_cash_flow": (receipts - payments).quantize(MONEY),
        "confirmed_count": confirmed_count,
        "draft_count": draft_count,
        "cancelled_count": cancelled_count,
    }


def outstanding_amount(obligation: Decimal | str | int, confirmed_settlements: list[Decimal | str | int]) -> Decimal:
    """Return unpaid remainder for one obligation; rejects overpayment instead of hiding it."""
    total = normalize_amount(obligation)
    settled = Decimal("0.00")
    for value in confirmed_settlements:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("Некорректная сумма погашения")
        if not amount.is_finite() or amount < 0:
            raise ValueError("Сумма погашения должна быть конечной и неотрицательной")
        settled += amount.quantize(MONEY, rounding=ROUND_HALF_UP)
    settled = settled.quantize(MONEY)
    if settled > total:
        raise ValueError("Сумма подтверждённых оплат превышает обязательство")
    return (total - settled).quantize(MONEY)
