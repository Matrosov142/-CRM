"""Mandatory transaction-level authorization for operations with financial limits.

Call this helper inside the same database transaction as the protected business
operation. It deliberately does not commit: the caller must commit the operation
and approval consumption atomically, or roll both back.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.access_control import VALID_OPERATIONS
from app.models import ApprovalConsumption, ApprovalRequest, EmployeeOperationLimit, Membership


def _money(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Некорректная сумма операции")
    if not amount.is_finite() or amount < 0:
        raise HTTPException(status_code=422, detail="Сумма должна быть неотрицательной")
    return amount


def require_operation_authorization(
    db: Session,
    membership: Membership,
    operation: str,
    amount,
    *,
    approval_request_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> ApprovalRequest | None:
    """Enforce employee limit and consume one matching director approval.

    Returns the consumed approval row when approval was required, otherwise None.
    The caller MUST execute the protected write and commit in this same transaction.
    """
    if operation not in VALID_OPERATIONS:
        raise HTTPException(status_code=422, detail="Неизвестный тип операции")
    if membership.status != "active":
        raise HTTPException(status_code=403, detail="Доступ сотрудника приостановлен")

    value = _money(amount)
    limit_row = db.execute(
        select(EmployeeOperationLimit)
        .where(
            EmployeeOperationLimit.company_id == membership.company_id,
            EmployeeOperationLimit.membership_id == membership.id,
            EmployeeOperationLimit.operation == operation,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if limit_row is None:
        raise HTTPException(status_code=409, detail="Лимит операции не установлен директором")

    if value <= Decimal(str(limit_row.limit_amount)):
        if approval_request_id is not None:
            raise HTTPException(status_code=409, detail="Согласование не требуется: сумма в пределах лимита")
        return None

    if approval_request_id is None:
        raise HTTPException(status_code=403, detail="Сумма превышает лимит. Требуется согласование директора")

    approval = db.execute(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_request_id,
            ApprovalRequest.company_id == membership.company_id,
            ApprovalRequest.requested_by_membership_id == membership.id,
            ApprovalRequest.operation == operation,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="Согласование не найдено для этой операции и сотрудника")
    if approval.status != "approved":
        raise HTTPException(status_code=409, detail="Согласование не одобрено")
    if Decimal(str(approval.amount)).quantize(Decimal("0.01")) != value:
        raise HTTPException(status_code=409, detail="Сумма операции не совпадает с согласованной")
    already_used = db.execute(
        select(ApprovalConsumption.id).where(
            ApprovalConsumption.company_id == membership.company_id,
            ApprovalConsumption.approval_request_id == approval.id,
        )
    ).scalar_one_or_none()
    if already_used is not None:
        raise HTTPException(status_code=409, detail="Это согласование уже использовано")

    db.add(ApprovalConsumption(
        company_id=membership.company_id,
        approval_request_id=approval.id,
        consumed_by_membership_id=membership.id,
        consumed_entity_type=entity_type,
        consumed_entity_id=entity_id,
        consumed_at=datetime.now(timezone.utc),
    ))
    record_audit(
        db,
        company_id=membership.company_id,
        actor_user_id=membership.user_id,
        action="approval.consumed",
        entity_type="approval_request",
        entity_id=str(approval.id),
        details={
            "operation": operation,
            "amount": str(value),
            "business_entity_type": entity_type,
            "business_entity_id": entity_id,
        },
    )
    db.flush()
    return approval
