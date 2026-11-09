"""Tenant-isolated receivables/payables and allocations to confirmed cash movements."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.audit import record_audit
from app.database import get_db
from app.models import FinanceObligation, FinanceAllocation, FinanceMovement, Membership, ProcurementOrder
from app.permissions import Role, require_roles
from app.schemas import FinanceObligationCreateRequest, FinanceAllocationCreateRequest

router = APIRouter(prefix="/api/v1/finance", tags=["Финансовые обязательства"])
ROLES = (Role.DIRECTOR, Role.ACCOUNTING)
CENT = Decimal("0.01")

def _allocated(db, company_id, obligation_id):
    value = db.query(func.coalesce(func.sum(FinanceAllocation.amount), 0)).filter(
        FinanceAllocation.company_id == company_id,
        FinanceAllocation.obligation_id == obligation_id).scalar()
    return Decimal(value).quantize(CENT)

def _movement_allocated(db, company_id, movement_id):
    value = db.query(func.coalesce(func.sum(FinanceAllocation.amount), 0)).filter(
        FinanceAllocation.company_id == company_id,
        FinanceAllocation.movement_id == movement_id).scalar()
    return Decimal(value).quantize(CENT)

def _payload(db, o):
    allocated = _allocated(db, o.company_id, o.id)
    remaining = (Decimal(o.amount) - allocated).quantize(CENT)
    now = datetime.now(timezone.utc)
    status = "оплачено" if remaining == 0 else ("частично оплачено" if allocated else ("просрочено" if o.due_date < now else "ожидает оплаты"))
    return {"id": str(o.id), "obligation_number": o.obligation_number, "side": o.side,
            "amount": str(o.amount), "allocated": str(allocated), "remaining": str(remaining),
            "currency": o.currency, "counterparty_name": o.counterparty_name,
            "counterparty_inn": o.counterparty_inn, "description": o.description,
            "due_date": o.due_date.isoformat(), "status": status,
            "procurement_order_id": str(o.procurement_order_id) if o.procurement_order_id else None,
            "created_at": o.created_at.isoformat()}

@router.post("/obligations", status_code=201)
def create_obligation(payload: FinanceObligationCreateRequest,
                      actor: Membership = Depends(require_roles(*ROLES)), db: Session = Depends(get_db)):
    if payload.procurement_order_id:
        order = db.query(ProcurementOrder).filter(ProcurementOrder.id == payload.procurement_order_id,
            ProcurementOrder.company_id == actor.company_id).first()
        if order is None:
            raise HTTPException(status_code=404, detail="Закупочный заказ не найден")
    duplicate = db.query(FinanceObligation).filter(FinanceObligation.company_id == actor.company_id,
        FinanceObligation.obligation_number == payload.obligation_number.strip()).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Обязательство с таким номером уже существует")
    o = FinanceObligation(company_id=actor.company_id, obligation_number=payload.obligation_number.strip(),
        side=payload.side, amount=payload.amount, currency="RUB", counterparty_name=payload.counterparty_name.strip(),
        counterparty_inn=payload.counterparty_inn, description=payload.description,
        due_date=payload.due_date, procurement_order_id=payload.procurement_order_id,
        created_by_membership_id=actor.id)
    db.add(o); db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="finance.obligation_created", entity_type="finance_obligation", entity_id=str(o.id),
        details={"number": o.obligation_number, "side": o.side, "amount": str(o.amount)})
    db.commit(); return _payload(db, o)

@router.get("/obligations")
def list_obligations(side: str | None = None,
                     actor: Membership = Depends(require_roles(*ROLES)), db: Session = Depends(get_db)):
    if side not in (None, "receivable", "payable"):
        raise HTTPException(status_code=422, detail="Допустимые стороны: receivable, payable")
    q = db.query(FinanceObligation).filter(FinanceObligation.company_id == actor.company_id)
    if side: q = q.filter(FinanceObligation.side == side)
    return [_payload(db, o) for o in q.order_by(FinanceObligation.due_date.asc()).limit(500).all()]

@router.post("/obligations/{obligation_id}/allocations", status_code=201)
def allocate_payment(obligation_id: UUID, payload: FinanceAllocationCreateRequest,
                    actor: Membership = Depends(require_roles(*ROLES)), db: Session = Depends(get_db)):
    # Row locks serialize concurrent allocation attempts for the same obligation and movement.
    o = db.query(FinanceObligation).filter(FinanceObligation.id == obligation_id,
        FinanceObligation.company_id == actor.company_id).with_for_update().first()
    if o is None:
        raise HTTPException(status_code=404, detail="Обязательство не найдено")
    m = db.query(FinanceMovement).filter(FinanceMovement.id == payload.movement_id,
        FinanceMovement.company_id == actor.company_id).with_for_update().first()
    if m is None:
        raise HTTPException(status_code=404, detail="Денежная операция не найдена")
    expected_kind = "receipt" if o.side == "receivable" else "payment"
    if m.status != "confirmed":
        raise HTTPException(status_code=409, detail="Распределять можно только подтверждённую денежную операцию")
    if m.kind != expected_kind:
        raise HTTPException(status_code=409, detail="Тип денежной операции не соответствует обязательству")
    obligation_remaining = (Decimal(o.amount) - _allocated(db, actor.company_id, o.id)).quantize(CENT)
    movement_remaining = (Decimal(m.amount) - _movement_allocated(db, actor.company_id, m.id)).quantize(CENT)
    if payload.amount > obligation_remaining:
        raise HTTPException(status_code=409, detail="Сумма превышает остаток обязательства")
    if payload.amount > movement_remaining:
        raise HTTPException(status_code=409, detail="Сумма превышает нераспределённый остаток денежной операции")
    a = FinanceAllocation(company_id=actor.company_id, obligation_id=o.id, movement_id=m.id,
        amount=payload.amount, created_by_membership_id=actor.id)
    db.add(a); db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="finance.obligation_payment_allocated", entity_type="finance_obligation", entity_id=str(o.id),
        details={"movement_id": str(m.id), "amount": str(payload.amount)})
    db.commit()
    return {"allocation_id": str(a.id), "obligation": _payload(db, o)}

@router.get("/obligations/summary")
def obligations_summary(actor: Membership = Depends(require_roles(*ROLES)), db: Session = Depends(get_db)):
    obligations = db.query(FinanceObligation).filter(FinanceObligation.company_id == actor.company_id).all()
    totals = {"receivable_total": Decimal("0.00"), "receivable_remaining": Decimal("0.00"),
              "payable_total": Decimal("0.00"), "payable_remaining": Decimal("0.00"),
              "overdue_receivable": Decimal("0.00"), "overdue_payable": Decimal("0.00")}
    now = datetime.now(timezone.utc)
    for o in obligations:
        rem = (Decimal(o.amount) - _allocated(db, actor.company_id, o.id)).quantize(CENT)
        prefix = "receivable" if o.side == "receivable" else "payable"
        totals[prefix + "_total"] += Decimal(o.amount)
        totals[prefix + "_remaining"] += rem
        if rem > 0 and o.due_date < now:
            totals["overdue_" + prefix] += rem
    return {"currency": "RUB", **{k: str(v.quantize(CENT)) for k, v in totals.items()},
            "note": "Сводка по заведённым обязательствам и распределённым подтверждённым платежам; не является бухгалтерской отчётностью."}
