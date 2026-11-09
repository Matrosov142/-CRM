"""Fine-grained employee permissions, limits and director approvals."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.database import get_db
from app.models import (
    ApprovalRequest, EmployeeOperationLimit, EmployeePermissionOverride,
    Membership,
)
from app.permissions import require_director
from app.dependencies import get_current_membership
from app.schemas import (
    PermissionOverrideRequest, OperationLimitRequest,
    ApprovalCreateRequest, ApprovalDecisionRequest,
)
from app.rbac import Action, ROLE_PERMISSIONS, effective_permission
from app.access_control import VALID_OPERATIONS

router = APIRouter(prefix="/api/v1/access", tags=["Права и согласования"])


@router.get("/roles")
def role_matrix(actor: Membership = Depends(require_director())):
    return {
        role: sorted(action.value for action in actions)
        for role, actions in ROLE_PERMISSIONS.items()
    }


@router.get("/employees/{membership_id}/permissions")
def employee_permissions(
    membership_id: UUID,
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    target = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.company_id == actor.company_id,
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    overrides = {
        item.action: item.allowed
        for item in db.query(EmployeePermissionOverride).filter(
            EmployeePermissionOverride.company_id == actor.company_id,
            EmployeePermissionOverride.membership_id == target.id,
        ).all()
    }
    return {
        "membership_id": str(target.id),
        "role": target.role,
        "permissions": {
            action.value: effective_permission(target.role, action, overrides.get(action.value))
            for action in Action
        },
        "overrides": overrides,
    }


@router.put("/employees/{membership_id}/permissions")
def set_employee_permission(
    membership_id: UUID,
    payload: PermissionOverrideRequest,
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    try:
        action = Action(payload.action)
    except ValueError:
        raise HTTPException(status_code=422, detail="Неизвестное действие")
    target = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.company_id == actor.company_id,
        Membership.status == "active",
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Активный сотрудник не найден")
    if target.role == "director":
        raise HTTPException(status_code=409, detail="Нельзя ограничивать права директора этим механизмом")
    item = db.query(EmployeePermissionOverride).filter(
        EmployeePermissionOverride.company_id == actor.company_id,
        EmployeePermissionOverride.membership_id == target.id,
        EmployeePermissionOverride.action == action.value,
    ).with_for_update().first()
    if item is None:
        item = EmployeePermissionOverride(
            company_id=actor.company_id, membership_id=target.id,
            action=action.value, allowed=payload.allowed,
            updated_by_user_id=actor.user_id,
        )
        db.add(item)
    else:
        item.allowed = payload.allowed
        item.updated_by_user_id = actor.user_id
        item.updated_at = datetime.now(timezone.utc)
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="employee.permission_changed", entity_type="membership",
        entity_id=str(target.id),
        details={"action": action.value, "allowed": payload.allowed},
    )
    db.commit()
    return {"updated": True, "action": action.value, "allowed": payload.allowed}


@router.put("/employees/{membership_id}/limits")
def set_employee_limit(
    membership_id: UUID,
    payload: OperationLimitRequest,
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    if payload.operation not in VALID_OPERATIONS:
        raise HTTPException(status_code=422, detail="Неизвестный тип лимита")
    target = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.company_id == actor.company_id,
        Membership.status == "active",
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Активный сотрудник не найден")
    item = db.query(EmployeeOperationLimit).filter(
        EmployeeOperationLimit.company_id == actor.company_id,
        EmployeeOperationLimit.membership_id == target.id,
        EmployeeOperationLimit.operation == payload.operation,
    ).with_for_update().first()
    if item is None:
        item = EmployeeOperationLimit(
            company_id=actor.company_id, membership_id=target.id,
            operation=payload.operation, limit_amount=Decimal(str(payload.limit_amount)),
            updated_by_user_id=actor.user_id,
        )
        db.add(item)
    else:
        item.limit_amount = Decimal(str(payload.limit_amount))
        item.updated_by_user_id = actor.user_id
        item.updated_at = datetime.now(timezone.utc)
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="employee.operation_limit_changed", entity_type="membership",
        entity_id=str(target.id),
        details={"operation": payload.operation, "limit_amount": payload.limit_amount},
    )
    db.commit()
    return {"updated": True, "operation": payload.operation, "limit_amount": payload.limit_amount}




@router.get("/employees/{membership_id}/limits")
def employee_limits(
    membership_id: UUID,
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    target = db.query(Membership).filter(
        Membership.id == membership_id,
        Membership.company_id == actor.company_id,
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    rows = db.query(EmployeeOperationLimit).filter(
        EmployeeOperationLimit.company_id == actor.company_id,
        EmployeeOperationLimit.membership_id == target.id,
    ).all()
    return [{
        "operation": row.operation,
        "limit_amount": float(row.limit_amount),
        "updated_at": row.updated_at.isoformat(),
    } for row in rows]

@router.post("/approval-requests", status_code=201)
def create_approval_request(
    payload: ApprovalCreateRequest,
    actor: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    if payload.operation not in VALID_OPERATIONS:
        raise HTTPException(status_code=422, detail="Неизвестный тип операции")
    limit = db.query(EmployeeOperationLimit).filter(
        EmployeeOperationLimit.company_id == actor.company_id,
        EmployeeOperationLimit.membership_id == actor.id,
        EmployeeOperationLimit.operation == payload.operation,
    ).with_for_update().first()
    if limit is None:
        raise HTTPException(status_code=409, detail="Для этой операции директор ещё не установил лимит")
    if Decimal(str(payload.amount)) <= limit.limit_amount:
        raise HTTPException(status_code=409, detail="Сумма не превышает лимит; отдельное согласование не требуется")
    duplicate = db.query(ApprovalRequest).filter(
        ApprovalRequest.company_id == actor.company_id,
        ApprovalRequest.requested_by_membership_id == actor.id,
        ApprovalRequest.operation == payload.operation,
        ApprovalRequest.amount == payload.amount,
        ApprovalRequest.status == "pending",
    ).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Такой запрос уже ожидает решения директора")
    request = ApprovalRequest(
        company_id=actor.company_id, requested_by_membership_id=actor.id,
        operation=payload.operation, amount=Decimal(str(payload.amount)),
        reason=payload.reason.strip(), status="pending",
    )
    db.add(request)
    db.flush()
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="approval.requested", entity_type="approval_request",
        entity_id=str(request.id),
        details={"operation": payload.operation, "amount": payload.amount},
    )
    db.commit()
    return {"id": str(request.id), "status": "pending", "message": "Запрос направлен директору"}


@router.get("/my-approval-requests")
def list_my_approval_requests(
    actor: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    rows = db.query(ApprovalRequest).filter(
        ApprovalRequest.company_id == actor.company_id,
        ApprovalRequest.requested_by_membership_id == actor.id,
    ).order_by(ApprovalRequest.created_at.desc()).all()
    return [{
        "id": str(row.id), "operation": row.operation,
        "amount": str(row.amount), "reason": row.reason,
        "status": row.status, "decision_note": row.decision_note,
        "created_at": row.created_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    } for row in rows]


@router.get("/approval-requests")
def list_approval_requests(
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    rows = db.query(ApprovalRequest).filter(
        ApprovalRequest.company_id == actor.company_id
    ).order_by(ApprovalRequest.created_at.desc()).all()
    return [{
        "id": str(row.id), "requested_by_membership_id": str(row.requested_by_membership_id),
        "operation": row.operation, "amount": float(row.amount), "reason": row.reason,
        "status": row.status, "decision_note": row.decision_note,
        "created_at": row.created_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    } for row in rows]


@router.post("/approval-requests/{request_id}/decision")
def decide_approval_request(
    request_id: UUID,
    payload: ApprovalDecisionRequest,
    actor: Membership = Depends(require_director()),
    db: Session = Depends(get_db),
):
    request = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == request_id,
        ApprovalRequest.company_id == actor.company_id,
    ).with_for_update().first()
    if request is None:
        raise HTTPException(status_code=404, detail="Запрос согласования не найден")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="Запрос уже рассмотрен")
    request.status = payload.decision
    request.decided_by_user_id = actor.user_id
    request.decision_note = payload.note.strip() or None
    request.decided_at = datetime.now(timezone.utc)
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="approval.decided", entity_type="approval_request",
        entity_id=str(request.id),
        details={"decision": payload.decision, "note": request.decision_note},
    )
    db.commit()
    return {"decided": True, "status": request.status}
