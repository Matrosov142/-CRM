"""Manual tender register. External ETP integrations are intentionally not implied."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.audit import record_audit
from app.database import get_db
from app.models import Tender, TenderPosition, TenderPositionPricingVersion, Membership
from app.permissions import Role, require_roles
from app.schemas import TenderCreateRequest, TenderUpdateRequest, TenderPositionCreateRequest, TenderPositionUpdateRequest, TenderPositionPricingRequest

router = APIRouter(prefix="/api/v1/tenders", tags=["Тендеры"])
READ_ROLES = (Role.DIRECTOR, Role.TENDER_SPECIALIST, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)
WRITE_ROLES = (Role.DIRECTOR, Role.TENDER_SPECIALIST)


def _view(t: Tender) -> dict:
    return {"id": str(t.id), "platform": t.platform, "tender_number": t.tender_number,
        "customer_name": t.customer_name, "subject": t.subject,
        "initial_price": str(t.initial_price), "currency": "RUB",
        "deadline": t.deadline.isoformat(), "delivery_region": t.delivery_region,
        "status": t.status, "prospectivity": t.prospectivity,
        "responsible_membership_id": str(t.responsible_membership_id) if t.responsible_membership_id else None,
        "notes": t.notes, "created_at": t.created_at.isoformat(), "updated_at": t.updated_at.isoformat()}


@router.post("", status_code=201)
def create_tender(payload: TenderCreateRequest,
    actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    platform, number = payload.platform.strip(), payload.tender_number.strip()
    customer, subject = payload.customer_name.strip(), payload.subject.strip()
    if not platform or not number or not customer or not subject:
        raise HTTPException(status_code=422, detail="Площадка, номер, заказчик и предмет закупки не могут быть пустыми")
    if db.query(Tender).filter(Tender.company_id == actor.company_id,
        Tender.platform == platform, Tender.tender_number == number).first():
        raise HTTPException(status_code=409, detail="Тендер с таким номером на этой площадке уже существует")
    if payload.responsible_membership_id:
        from app.models import Membership as Member
        owner = db.query(Member).filter(Member.id == payload.responsible_membership_id,
            Member.company_id == actor.company_id, Member.status == "active").first()
        if owner is None:
            raise HTTPException(status_code=422, detail="Ответственный сотрудник не найден в вашей компании")
    values = payload.model_dump()
    values["platform"], values["tender_number"] = platform, number
    values["customer_name"], values["subject"] = customer, subject
    tender = Tender(company_id=actor.company_id, created_by_membership_id=actor.id, **values)
    db.add(tender); db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="tender.created", entity_type="tender", entity_id=str(tender.id),
        details={"platform": platform, "tender_number": number})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Тендер с таким номером на этой площадке уже существует")
    db.refresh(tender)
    return _view(tender)


@router.get("")
def list_tenders(search: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, pattern="^(new|analysis|preparing|submitted|won|lost|cancelled)$"),
    prospectivity: str | None = Query(default=None, pattern="^(high|medium|low)$"),
    actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    q = db.query(Tender).filter(Tender.company_id == actor.company_id)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter((Tender.tender_number.ilike(term)) | (Tender.customer_name.ilike(term)) | (Tender.subject.ilike(term)))
    if status: q = q.filter(Tender.status == status)
    if prospectivity: q = q.filter(Tender.prospectivity == prospectivity)
    return [_view(t) for t in q.order_by(Tender.deadline.asc()).limit(500).all()]


@router.get("/{tender_id}")
def get_tender(tender_id: UUID, actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    t = db.query(Tender).filter(Tender.id == tender_id, Tender.company_id == actor.company_id).first()
    if t is None: raise HTTPException(status_code=404, detail="Тендер не найден")
    return _view(t)


@router.patch("/{tender_id}")
def update_tender(tender_id: UUID, payload: TenderUpdateRequest,
    actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    t = db.query(Tender).filter(Tender.id == tender_id, Tender.company_id == actor.company_id).with_for_update().first()
    if t is None: raise HTTPException(status_code=404, detail="Тендер не найден")
    changes = payload.model_dump(exclude_unset=True)
    if "responsible_membership_id" in changes and changes["responsible_membership_id"] is not None:
        from app.models import Membership as Member
        owner = db.query(Member).filter(Member.id == changes["responsible_membership_id"],
            Member.company_id == actor.company_id, Member.status == "active").first()
        if owner is None: raise HTTPException(status_code=422, detail="Ответственный сотрудник не найден в вашей компании")
    for key, value in changes.items():
        setattr(t, key, value.strip() if isinstance(value, str) else value)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="tender.updated", entity_type="tender", entity_id=str(t.id), details={"fields": sorted(changes)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Не удалось сохранить изменения из-за конфликта данных")
    db.refresh(t)
    return _view(t)



def _position_view(p: TenderPosition) -> dict:
    total = (p.quantity * p.estimated_unit_price) if p.estimated_unit_price is not None else None
    return {"id": str(p.id), "tender_id": str(p.tender_id), "line_number": p.line_number,
        "item_name": p.item_name, "specification": p.specification,
        "quantity": str(p.quantity), "unit": p.unit,
        "estimated_unit_price": str(p.estimated_unit_price) if p.estimated_unit_price is not None else None,
        "estimated_total": str(total) if total is not None else None,
        "notes": p.notes, "created_at": p.created_at.isoformat()}


def _company_tender(db: Session, tender_id: UUID, company_id):
    tender = db.query(Tender).filter(Tender.id == tender_id, Tender.company_id == company_id).first()
    if tender is None:
        raise HTTPException(status_code=404, detail="Тендер не найден")
    return tender


@router.get("/{tender_id}/positions")
def list_tender_positions(tender_id: UUID, actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    _company_tender(db, tender_id, actor.company_id)
    rows = db.query(TenderPosition).filter(TenderPosition.company_id == actor.company_id,
        TenderPosition.tender_id == tender_id).order_by(TenderPosition.line_number.asc()).all()
    return [_position_view(row) for row in rows]


@router.post("/{tender_id}/positions", status_code=201)
def create_tender_position(tender_id: UUID, payload: TenderPositionCreateRequest,
    actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id, Tender.company_id == actor.company_id).with_for_update().first()
    if tender is None:
        raise HTTPException(status_code=404, detail="Тендер не найден")
    item_name = payload.item_name.strip()
    if not item_name:
        raise HTTPException(status_code=422, detail="Наименование позиции обязательно")
    next_line = (db.query(TenderPosition.line_number).filter(
        TenderPosition.company_id == actor.company_id, TenderPosition.tender_id == tender_id)
        .order_by(TenderPosition.line_number.desc()).limit(1).scalar() or 0) + 1
    values = payload.model_dump()
    values["item_name"] = item_name
    values["unit"] = payload.unit.strip()
    if not values["unit"]:
        raise HTTPException(status_code=422, detail="Единица измерения обязательна")
    row = TenderPosition(company_id=actor.company_id, tender_id=tender_id, line_number=next_line, **values)
    db.add(row)
    db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="tender.position.created", entity_type="tender_position", entity_id=str(row.id),
        details={"tender_id": str(tender_id), "line_number": next_line})
    db.commit(); db.refresh(row)
    return _position_view(row)


@router.patch("/{tender_id}/positions/{position_id}")
def update_tender_position(tender_id: UUID, position_id: UUID, payload: TenderPositionUpdateRequest,
    actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    _company_tender(db, tender_id, actor.company_id)
    row = db.query(TenderPosition).filter(TenderPosition.id == position_id,
        TenderPosition.tender_id == tender_id, TenderPosition.company_id == actor.company_id).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Позиция тендера не найдена")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
            if key in ("item_name", "unit") and not value:
                raise HTTPException(status_code=422, detail="Наименование и единица измерения не могут быть пустыми")
        setattr(row, key, value)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="tender.position.updated", entity_type="tender_position", entity_id=str(row.id),
        details={"fields": sorted(changes), "tender_id": str(tender_id)})
    db.commit(); db.refresh(row)
    return _position_view(row)


@router.delete("/{tender_id}/positions/{position_id}", status_code=204)
def delete_tender_position(tender_id: UUID, position_id: UUID,
    actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    _company_tender(db, tender_id, actor.company_id)
    row = db.query(TenderPosition).filter(TenderPosition.id == position_id,
        TenderPosition.tender_id == tender_id, TenderPosition.company_id == actor.company_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Позиция тендера не найдена")
    has_pricing_history = db.query(TenderPositionPricingVersion.id).filter(
        TenderPositionPricingVersion.company_id == actor.company_id,
        TenderPositionPricingVersion.position_id == position_id).first()
    if has_pricing_history:
        raise HTTPException(status_code=409, detail="Нельзя удалить позицию: по ней сохранена история расчётов")
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="tender.position.deleted", entity_type="tender_position", entity_id=str(row.id),
        details={"tender_id": str(tender_id), "line_number": row.line_number})
    db.delete(row); db.commit()
    return None


@router.post("/{tender_id}/positions/{position_id}/pricing-preview")
def preview_tender_position_pricing(tender_id: UUID, position_id: UUID,
    payload: TenderPositionPricingRequest,
    actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    """Calculate a non-persistent price preview for a position in the current tenant."""
    from app.tender_pricing import calculate_tender_position_pricing
    _company_tender(db, tender_id, actor.company_id)
    row = db.query(TenderPosition).filter(TenderPosition.id == position_id,
        TenderPosition.tender_id == tender_id, TenderPosition.company_id == actor.company_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Позиция тендера не найдена")
    try:
        result = calculate_tender_position_pricing(
            quantity=row.quantity, purchase=payload.purchase, logistics=payload.logistics,
            processing=payload.processing, packaging=payload.packaging, tax=payload.tax,
            other=payload.other, conservative_margin=payload.conservative_margin,
            target_margin=payload.target_margin, aggressive_margin=payload.aggressive_margin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result["tender_id"] = str(tender_id)
    result["position_id"] = str(position_id)
    result["position_name"] = row.item_name
    result["line_number"] = row.line_number
    result["persisted"] = False
    return result


@router.post("/{tender_id}/positions/{position_id}/pricing-calculations", status_code=201)
def save_tender_position_pricing(tender_id: UUID, position_id: UUID,
    payload: TenderPositionPricingRequest,
    actor: Membership = Depends(require_roles(*WRITE_ROLES)), db: Session = Depends(get_db)):
    """Persist an immutable version of the manually supplied pricing assumptions."""
    from app.tender_pricing import calculate_tender_position_pricing
    _company_tender(db, tender_id, actor.company_id)
    row = db.query(TenderPosition).filter(TenderPosition.id == position_id,
        TenderPosition.tender_id == tender_id, TenderPosition.company_id == actor.company_id).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Позиция тендера не найдена")
    try:
        result = calculate_tender_position_pricing(
            quantity=row.quantity, purchase=payload.purchase, logistics=payload.logistics,
            processing=payload.processing, packaging=payload.packaging, tax=payload.tax,
            other=payload.other, conservative_margin=payload.conservative_margin,
            target_margin=payload.target_margin, aggressive_margin=payload.aggressive_margin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    last_version = db.query(TenderPositionPricingVersion.version).filter(
        TenderPositionPricingVersion.company_id == actor.company_id,
        TenderPositionPricingVersion.position_id == position_id).order_by(
        TenderPositionPricingVersion.version.desc()).limit(1).scalar() or 0
    inputs = {key: str(value) for key, value in payload.model_dump().items()}
    version = TenderPositionPricingVersion(company_id=actor.company_id, tender_id=tender_id,
        position_id=position_id, version=last_version + 1, inputs=inputs, result=result,
        created_by_membership_id=actor.id)
    db.add(version); db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="tender.position.pricing_saved", entity_type="tender_position_pricing",
        entity_id=str(version.id), details={"tender_id": str(tender_id),
        "position_id": str(position_id), "version": version.version})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Конфликт версии расчёта. Повторите сохранение")
    db.refresh(version)
    return {"id": str(version.id), "version": version.version, "inputs": version.inputs,
        "result": version.result, "created_by_membership_id": str(version.created_by_membership_id),
        "created_at": version.created_at.isoformat()}


@router.get("/{tender_id}/positions/{position_id}/pricing-calculations")
def list_tender_position_pricing(tender_id: UUID, position_id: UUID,
    actor: Membership = Depends(require_roles(*READ_ROLES)), db: Session = Depends(get_db)):
    _company_tender(db, tender_id, actor.company_id)
    position = db.query(TenderPosition.id).filter(TenderPosition.id == position_id,
        TenderPosition.tender_id == tender_id, TenderPosition.company_id == actor.company_id).first()
    if position is None:
        raise HTTPException(status_code=404, detail="Позиция тендера не найдена")
    rows = db.query(TenderPositionPricingVersion).filter(
        TenderPositionPricingVersion.company_id == actor.company_id,
        TenderPositionPricingVersion.tender_id == tender_id,
        TenderPositionPricingVersion.position_id == position_id).order_by(
        TenderPositionPricingVersion.version.desc()).limit(100).all()
    return [{"id": str(v.id), "version": v.version, "inputs": v.inputs, "result": v.result,
        "created_by_membership_id": str(v.created_by_membership_id), "created_at": v.created_at.isoformat()}
        for v in rows]
