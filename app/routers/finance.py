"""Persistent tenant-scoped finance cash ledger. Not statutory accounting."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.audit import record_audit
from app.database import get_db
from app.models import FinanceMovement, Membership, ProcurementOrder
from app.permissions import Role, require_roles
from app.schemas import FinanceMovementCreateRequest, FinanceMovementCancelRequest

router = APIRouter(prefix="/api/v1/finance", tags=["Финансы"])
READ_ROLES = (Role.DIRECTOR, Role.ACCOUNTING)
WRITE_ROLES = (Role.DIRECTOR, Role.ACCOUNTING)

def _payload(m):
    return {"id": str(m.id), "movement_number": m.movement_number, "kind": m.kind, "status": m.status,
            "amount": str(m.amount), "currency": m.currency, "movement_date": m.movement_date.isoformat(),
            "counterparty_name": m.counterparty_name, "counterparty_inn": m.counterparty_inn,
            "purpose": m.purpose, "document_reference": m.document_reference,
            "procurement_order_id": str(m.procurement_order_id) if m.procurement_order_id else None,
            "created_at": m.created_at.isoformat(), "confirmed_at": m.confirmed_at.isoformat() if m.confirmed_at else None}

@router.post("/movements", status_code=201)
def create_movement(payload: FinanceMovementCreateRequest, actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    if payload.procurement_order_id:
        order = db.query(ProcurementOrder).filter(ProcurementOrder.id == payload.procurement_order_id, ProcurementOrder.company_id == actor.company_id).first()
        if order is None:
            raise HTTPException(status_code=404, detail="Закупочный заказ не найден")
    duplicate = db.query(FinanceMovement).filter(FinanceMovement.company_id == actor.company_id, FinanceMovement.movement_number == payload.movement_number.strip()).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Операция с таким номером уже существует")
    movement = FinanceMovement(company_id=actor.company_id, movement_number=payload.movement_number.strip(), kind=payload.kind,
        status="draft", amount=payload.amount, currency="RUB", movement_date=payload.movement_date,
        counterparty_name=payload.counterparty_name.strip(), counterparty_inn=payload.counterparty_inn,
        purpose=payload.purpose, document_reference=payload.document_reference, procurement_order_id=payload.procurement_order_id,
        created_by_membership_id=actor.id)
    db.add(movement); db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id, action="finance.movement_created",
        entity_type="finance_movement", entity_id=str(movement.id), details={"number": movement.movement_number, "kind": movement.kind, "amount": str(movement.amount)})
    db.commit(); return _payload(movement)

@router.get("/movements")
def list_movements(status: str | None = Query(default=None, pattern="^(draft|confirmed|cancelled)$"),
                   kind: str | None = Query(default=None, pattern="^(receipt|payment)$"),
                   actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    q = db.query(FinanceMovement).filter(FinanceMovement.company_id == actor.company_id)
    if status: q = q.filter(FinanceMovement.status == status)
    if kind: q = q.filter(FinanceMovement.kind == kind)
    return [_payload(m) for m in q.order_by(FinanceMovement.movement_date.desc(), FinanceMovement.created_at.desc()).limit(500).all()]

@router.post("/movements/{movement_id}/confirm")
def confirm_movement(movement_id: UUID, actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    m = db.query(FinanceMovement).filter(FinanceMovement.id == movement_id, FinanceMovement.company_id == actor.company_id).with_for_update().first()
    if m is None: raise HTTPException(status_code=404, detail="Финансовая операция не найдена")
    if m.status != "draft": raise HTTPException(status_code=409, detail="Подтвердить можно только черновик")
    m.status="confirmed"; m.confirmed_by_membership_id=actor.id; m.confirmed_at=datetime.now(timezone.utc)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id, action="finance.movement_confirmed", entity_type="finance_movement", entity_id=str(m.id), details={"amount": str(m.amount), "kind": m.kind})
    db.commit(); return {"confirmed": True, "movement": _payload(m)}

@router.post("/movements/{movement_id}/cancel")
def cancel_movement(movement_id: UUID, payload: FinanceMovementCancelRequest, actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    m = db.query(FinanceMovement).filter(FinanceMovement.id == movement_id, FinanceMovement.company_id == actor.company_id).with_for_update().first()
    if m is None: raise HTTPException(status_code=404, detail="Финансовая операция не найдена")
    if m.status != "draft": raise HTTPException(status_code=409, detail="Отменить можно только черновик; подтверждённые операции корректируются отдельной сторнирующей записью")
    m.status="cancelled"; m.cancelled_at=datetime.now(timezone.utc)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id, action="finance.movement_cancelled", entity_type="finance_movement", entity_id=str(m.id), details={"reason": payload.reason})
    db.commit(); return {"cancelled": True, "movement": _payload(m)}

@router.get("/summary")
def finance_summary(actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    rows = db.query(FinanceMovement.kind, func.count(FinanceMovement.id), func.coalesce(func.sum(FinanceMovement.amount), 0)).filter(
        FinanceMovement.company_id == actor.company_id, FinanceMovement.status == "confirmed").group_by(FinanceMovement.kind).all()
    totals = {"receipt": Decimal("0.00"), "payment": Decimal("0.00"), "receipt_count": 0, "payment_count": 0}
    for kind, count, amount in rows:
        totals[kind] = Decimal(amount).quantize(Decimal("0.01")); totals[kind + "_count"] = count
    return {"currency": "RUB", "confirmed_receipts": str(totals["receipt"]), "confirmed_payments": str(totals["payment"]),
            "net_cash_flow": str((totals["receipt"] - totals["payment"]).quantize(Decimal("0.01"))),
            "receipt_count": totals["receipt_count"], "payment_count": totals["payment_count"],
            "note": "Учитываются только подтверждённые движения; это не бухгалтерская отчётность и не расчёт дебиторской/кредиторской задолженности."}
