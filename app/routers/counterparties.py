"""Company-scoped counterparties and contract register. No external dispatch."""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.audit import record_audit
from app.database import get_db
from app.models import Counterparty, Contract, Membership
from app.permissions import Role, require_roles
from app.schemas import (CounterpartyCreateRequest, CounterpartyUpdateRequest,
                         ContractCreateRequest, ContractStatusUpdateRequest)

router = APIRouter(prefix="/api/v1/counterparties", tags=["Контрагенты"])
contracts_router = APIRouter(prefix="/api/v1/contracts", tags=["Договоры"])
EDIT_ROLES = (Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)
READ_ROLES = (Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.TENDER_SPECIALIST, Role.ACCOUNTING, Role.WAREHOUSE, Role.LOGISTICS)

def _cp(c):
    return {"id": str(c.id), "kind": c.kind, "legal_name": c.legal_name,
            "short_name": c.short_name, "inn": c.inn, "kpp": c.kpp, "ogrn": c.ogrn,
            "legal_address": c.legal_address, "actual_address": c.actual_address,
            "contact_name": c.contact_name, "email": c.email, "phone": c.phone,
            "notes": c.notes, "status": c.status, "created_at": c.created_at.isoformat()}

def _contract(c, cp_name=None):
    return {"id": str(c.id), "counterparty_id": str(c.counterparty_id),
            "counterparty_name": cp_name, "contract_number": c.contract_number,
            "title": c.title, "contract_type": c.contract_type,
            "signed_date": c.signed_date.isoformat() if c.signed_date else None,
            "starts_at": c.starts_at.isoformat(), "ends_at": c.ends_at.isoformat() if c.ends_at else None,
            "auto_renewal": c.auto_renewal, "renewal_notice_days": c.renewal_notice_days,
            "amount": str(c.amount) if c.amount is not None else None, "currency": c.currency,
            "status": c.status, "responsible_name": c.responsible_name,
            "notes": c.notes, "created_at": c.created_at.isoformat()}

@router.post("", status_code=201)
def create_counterparty(payload: CounterpartyCreateRequest,
    actor: Membership = Depends(require_roles(*EDIT_ROLES)), db: Session = Depends(get_db)):
    if payload.inn and db.query(Counterparty).filter(Counterparty.company_id == actor.company_id,
        Counterparty.inn == payload.inn).first():
        raise HTTPException(status_code=409, detail="Контрагент с таким ИНН уже существует")
    data = payload.model_dump()
    data["legal_name"] = data["legal_name"].strip()
    c = Counterparty(company_id=actor.company_id, **data)
    db.add(c); db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="counterparty.created", entity_type="counterparty", entity_id=str(c.id),
        details={"kind": c.kind, "inn": c.inn})
    db.commit(); return _cp(c)

@router.get("")
def list_counterparties(search: str | None = Query(default=None, max_length=200),
    kind: str | None = Query(default=None, pattern="^(customer|supplier|both)$"),
    status: str | None = Query(default=None, pattern="^(active|blocked)$"),
    actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    q = db.query(Counterparty).filter(Counterparty.company_id == actor.company_id)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter((Counterparty.legal_name.ilike(term)) | (Counterparty.short_name.ilike(term)) | (Counterparty.inn.ilike(term)))
    if kind: q = q.filter(Counterparty.kind == kind)
    if status: q = q.filter(Counterparty.status == status)
    return [_cp(x) for x in q.order_by(Counterparty.legal_name).limit(500).all()]

@router.get("/{counterparty_id}")
def get_counterparty(counterparty_id: UUID, actor: Membership = Depends(require_roles(*READ_ROLES)),
    db: Session = Depends(get_db)):
    c = db.query(Counterparty).filter(Counterparty.id == counterparty_id,
        Counterparty.company_id == actor.company_id).first()
    if c is None: raise HTTPException(status_code=404, detail="Контрагент не найден")
    contracts = db.query(Contract).filter(Contract.company_id == actor.company_id,
        Contract.counterparty_id == c.id).order_by(Contract.starts_at.desc()).all()
    return {**_cp(c), "contracts": [_contract(x, c.legal_name) for x in contracts]}

@router.patch("/{counterparty_id}")
def update_counterparty(counterparty_id: UUID, payload: CounterpartyUpdateRequest,
    actor: Membership = Depends(require_roles(*EDIT_ROLES)), db: Session = Depends(get_db)):
    c = db.query(Counterparty).filter(Counterparty.id == counterparty_id,
        Counterparty.company_id == actor.company_id).with_for_update().first()
    if c is None: raise HTTPException(status_code=404, detail="Контрагент не найден")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, key, value.strip() if isinstance(value, str) else value)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="counterparty.updated", entity_type="counterparty", entity_id=str(c.id),
        details={"status": c.status})
    db.commit(); return _cp(c)

@contracts_router.post("", status_code=201)
def create_contract(payload: ContractCreateRequest,
    actor: Membership = Depends(require_roles(*EDIT_ROLES)), db: Session = Depends(get_db)):
    cp = db.query(Counterparty).filter(Counterparty.id == payload.counterparty_id,
        Counterparty.company_id == actor.company_id, Counterparty.status == "active").first()
    if cp is None: raise HTTPException(status_code=404, detail="Активный контрагент не найден")
    if payload.ends_at and payload.ends_at < payload.starts_at:
        raise HTTPException(status_code=422, detail="Дата окончания не может быть раньше даты начала")
    if db.query(Contract).filter(Contract.company_id == actor.company_id,
        Contract.contract_number == payload.contract_number.strip()).first():
        raise HTTPException(status_code=409, detail="Договор с таким номером уже существует")
    if payload.contract_type == "customer" and cp.kind not in ("customer", "both"):
        raise HTTPException(status_code=422, detail="Тип контрагента не подходит для договора с заказчиком")
    if payload.contract_type == "supplier" and cp.kind not in ("supplier", "both"):
        raise HTTPException(status_code=422, detail="Тип контрагента не подходит для договора с поставщиком")
    contract_data = payload.model_dump()
    contract_data["contract_number"] = payload.contract_number.strip()
    contract_data["title"] = payload.title.strip()
    c = Contract(company_id=actor.company_id, **contract_data,
        currency="RUB", status="draft", created_by_membership_id=actor.id)
    db.add(c); db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="contract.created", entity_type="contract", entity_id=str(c.id),
        details={"number": c.contract_number, "counterparty_id": str(cp.id)})
    db.commit(); return _contract(c, cp.legal_name)

@contracts_router.get("")
def list_contracts(status: str | None = Query(default=None, pattern="^(draft|active|suspended|terminated|expired)$"),
    counterparty_id: UUID | None = None, expiring_days: int | None = Query(default=None, ge=0, le=365),
    actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    q = db.query(Contract, Counterparty.legal_name).join(Counterparty,
        (Counterparty.id == Contract.counterparty_id) & (Counterparty.company_id == Contract.company_id)).filter(
        Contract.company_id == actor.company_id)
    if status: q = q.filter(Contract.status == status)
    if counterparty_id: q = q.filter(Contract.counterparty_id == counterparty_id)
    if expiring_days is not None:
        now = datetime.now(timezone.utc)
        until = now.replace(hour=23, minute=59, second=59, microsecond=0)
        from datetime import timedelta
        until = until + timedelta(days=expiring_days)
        q = q.filter(Contract.status == "active", Contract.ends_at.is_not(None),
            Contract.ends_at >= now, Contract.ends_at <= until)
    return [_contract(c, name) for c, name in q.order_by(Contract.ends_at.asc().nullslast()).limit(500).all()]

@contracts_router.patch("/{contract_id}/status")
def update_contract_status(contract_id: UUID, payload: ContractStatusUpdateRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.ACCOUNTING)), db: Session = Depends(get_db)):
    c = db.query(Contract).filter(Contract.id == contract_id,
        Contract.company_id == actor.company_id).with_for_update().first()
    if c is None: raise HTTPException(status_code=404, detail="Договор не найден")
    old = c.status; c.status = payload.status
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="contract.status_changed", entity_type="contract", entity_id=str(c.id),
        details={"from": old, "to": c.status})
    db.commit()
    cp = db.query(Counterparty).filter(Counterparty.id == c.counterparty_id,
        Counterparty.company_id == actor.company_id).first()
    return _contract(c, cp.legal_name if cp else None)
