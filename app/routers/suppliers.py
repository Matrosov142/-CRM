"""Supplier directory and RFQ preparation; no external messages are sent."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.database import get_db
from app.dependencies import get_current_membership
from app.models import Membership, Supplier, SupplierRFQ, SupplierRFQLine, SupplierRFQRecipient, TenderPosition, Tender
from app.permissions import Role, require_roles
from app.schemas import SupplierCreateRequest, SupplierUpdateRequest, SupplierRFQCreateRequest

router = APIRouter(prefix="/api/v1/suppliers", tags=["Поставщики"])
rfq_router = APIRouter(prefix="/api/v1/rfqs", tags=["Запросы предложений"])


def _supplier_data(s):
    return {
        "id": str(s.id), "name": s.name, "inn": s.inn, "kpp": s.kpp,
        "contact_name": s.contact_name, "email": s.email, "phone": s.phone,
        "address": s.address, "payment_terms": s.payment_terms,
        "delivery_terms": s.delivery_terms, "notes": s.notes,
        "status": s.status, "created_at": s.created_at.isoformat(),
    }


@router.post("", status_code=201)
def create_supplier(
    payload: SupplierCreateRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    if payload.inn:
        duplicate = db.query(Supplier).filter(
            Supplier.company_id == actor.company_id, Supplier.inn == payload.inn
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Поставщик с таким ИНН уже существует")
    data = payload.model_dump()
    data["name"] = payload.name.strip()
    supplier = Supplier(company_id=actor.company_id, **data)
    db.add(supplier)
    db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
                 action="supplier.created", entity_type="supplier", entity_id=str(supplier.id),
                 details={"name": supplier.name, "inn": supplier.inn})
    db.commit()
    return _supplier_data(supplier)


@router.get("")
def list_suppliers(
    search: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, pattern="^(active|blocked)$"),
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    query = db.query(Supplier).filter(Supplier.company_id == actor.company_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter((Supplier.name.ilike(term)) | (Supplier.inn.ilike(term)))
    if status:
        query = query.filter(Supplier.status == status)
    return [_supplier_data(s) for s in query.order_by(Supplier.name).limit(300).all()]


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: UUID,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.company_id == actor.company_id
    ).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    return _supplier_data(supplier)


@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdateRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    supplier = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.company_id == actor.company_id
    ).with_for_update().first()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Поставщик не найден")
    if payload.inn:
        duplicate = db.query(Supplier).filter(
            Supplier.company_id == actor.company_id,
            Supplier.inn == payload.inn,
            Supplier.id != supplier.id,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Поставщик с таким ИНН уже существует")
    for key, value in payload.model_dump().items():
        setattr(supplier, key, value.strip() if isinstance(value, str) else value)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
                 action="supplier.updated", entity_type="supplier", entity_id=str(supplier.id),
                 details={"status": supplier.status})
    db.commit()
    return _supplier_data(supplier)


@rfq_router.post("", status_code=201)
def create_rfq(
    payload: SupplierRFQCreateRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    supplier_ids = list(dict.fromkeys(payload.supplier_ids))
    suppliers = db.query(Supplier).filter(
        Supplier.company_id == actor.company_id,
        Supplier.id.in_(supplier_ids),
        Supplier.status == "active",
    ).all()
    if len(suppliers) != len(supplier_ids):
        raise HTTPException(status_code=422, detail="Один или несколько поставщиков не найдены или заблокированы")
    rfq = SupplierRFQ(
        company_id=actor.company_id, rfq_number=payload.rfq_number.strip(),
        title=payload.title.strip(), message=payload.message.strip(),
        response_deadline=payload.response_deadline, status="prepared",
        created_by_membership_id=actor.id,
    )
    db.add(rfq)
    db.flush()
    lines = []
    for idx, item in enumerate(payload.lines, 1):
        if item.tender_position_id is not None:
            linked = db.query(TenderPosition).filter(
                TenderPosition.company_id == actor.company_id,
                TenderPosition.tender_id == item.tender_id,
                TenderPosition.id == item.tender_position_id,
            ).first()
            if linked is None:
                raise HTTPException(status_code=422, detail="Позиция тендера не найдена в вашей компании")
            if item.item_name.strip() != linked.item_name.strip():
                raise HTTPException(status_code=422, detail="Наименование строки запроса не совпадает с выбранной позицией тендера")
        line = SupplierRFQLine(
            company_id=actor.company_id, rfq_id=rfq.id, line_number=idx,
            item_name=item.item_name.strip(), specification=item.specification,
            quantity=item.quantity, unit=item.unit.strip(),
            tender_id=item.tender_id, tender_position_id=item.tender_position_id,
        )
        db.add(line)
        lines.append(line)
    recipients = []
    for supplier in suppliers:
        recipient = SupplierRFQRecipient(
            company_id=actor.company_id, rfq_id=rfq.id,
            supplier_id=supplier.id, status="prepared",
        )
        db.add(recipient)
        recipients.append(recipient)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
                 action="rfq.prepared", entity_type="supplier_rfq", entity_id=str(rfq.id),
                 details={"rfq_number": rfq.rfq_number, "supplier_count": len(recipients), "line_count": len(lines)})
    db.commit()
    return {
        "id": str(rfq.id), "rfq_number": rfq.rfq_number, "title": rfq.title,
        "status": rfq.status, "response_deadline": rfq.response_deadline.isoformat() if rfq.response_deadline else None,
        "supplier_count": len(recipients), "line_count": len(lines),
        "message": "Запрос подготовлен. Внешняя отправка не выполнялась.",
    }


@rfq_router.get("")
def list_rfqs(
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    rows = db.query(SupplierRFQ).filter(
        SupplierRFQ.company_id == actor.company_id
    ).order_by(SupplierRFQ.created_at.desc()).limit(200).all()
    return [{
        "id": str(r.id), "rfq_number": r.rfq_number, "title": r.title,
        "status": r.status, "created_at": r.created_at.isoformat(),
        "response_deadline": r.response_deadline.isoformat() if r.response_deadline else None,
    } for r in rows]


@rfq_router.get("/{rfq_id}")
def get_rfq(
    rfq_id: UUID,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    rfq = db.query(SupplierRFQ).filter(
        SupplierRFQ.id == rfq_id, SupplierRFQ.company_id == actor.company_id
    ).first()
    if rfq is None:
        raise HTTPException(status_code=404, detail="Запрос предложений не найден")
    lines = db.query(SupplierRFQLine).filter(
        SupplierRFQLine.company_id == actor.company_id, SupplierRFQLine.rfq_id == rfq.id
    ).order_by(SupplierRFQLine.line_number).all()
    recipients = db.query(SupplierRFQRecipient).filter(
        SupplierRFQRecipient.company_id == actor.company_id, SupplierRFQRecipient.rfq_id == rfq.id
    ).all()
    return {
        "id": str(rfq.id), "rfq_number": rfq.rfq_number, "title": rfq.title,
        "message": rfq.message, "status": rfq.status,
        "response_deadline": rfq.response_deadline.isoformat() if rfq.response_deadline else None,
        "lines": [{"line_number": x.line_number, "item_name": x.item_name,
                   "specification": x.specification, "quantity": str(x.quantity), "unit": x.unit,
                   "tender_id": str(x.tender_id) if x.tender_id else None,
                   "tender_position_id": str(x.tender_position_id) if x.tender_position_id else None} for x in lines],
        "suppliers": [{"supplier_id": str(x.supplier_id), "status": x.status} for x in recipients],
        "external_sending": False,
    }

# Supplier replies are recorded for review; nothing is sent externally.
from decimal import Decimal
from app.models import SupplierOffer, SupplierOfferLine, SupplierRFQSelection, ProcurementOrder, ProcurementOrderLine
from app.schemas import SupplierOfferCreateRequest, SupplierOfferReviewRequest, SupplierOfferSelectionRequest


def _offer_payload(offer, lines, supplier_name):
    goods = sum((Decimal(str(x.quantity)) * Decimal(str(x.unit_price)) for x in lines), Decimal("0.00"))
    declared_vat = Decimal(str(offer.vat_amount)) if offer.vat_amount is not None else None
    total = goods + Decimal(str(offer.delivery_cost)) + (declared_vat or Decimal("0.00"))
    return {
        "id": str(offer.id), "supplier_id": str(offer.supplier_id), "supplier_name": supplier_name,
        "version_no": offer.version_no, "supersedes_offer_id": str(offer.supersedes_offer_id) if offer.supersedes_offer_id else None, "is_current": offer.is_current,
        "supplier_offer_number": offer.supplier_offer_number, "source_channel": offer.source_channel,
        "received_at": offer.received_at.isoformat(), "valid_until": offer.valid_until.isoformat() if offer.valid_until else None,
        "delivery_days": offer.delivery_days, "delivery_cost": str(offer.delivery_cost),
        "vat_treatment": offer.vat_treatment, "vat_amount": str(offer.vat_amount) if offer.vat_amount is not None else None,
        "payment_terms": offer.payment_terms, "review_status": offer.review_status, "review_note": offer.review_note,
        "goods_total": str(goods.quantize(Decimal('0.01'))),
        "total_with_declared_delivery_and_vat": str(total.quantize(Decimal('0.01'))),
        "vat_is_fully_known": offer.vat_amount is not None or offer.vat_treatment == "no_vat",
        "lines": [{"id": str(x.id), "rfq_line_id": str(x.rfq_line_id), "offered_item_name": x.offered_item_name,
                   "offered_specification": x.offered_specification, "quantity": str(x.quantity), "unit": x.unit,
                   "unit_price": str(x.unit_price), "line_total": str((Decimal(str(x.quantity))*Decimal(str(x.unit_price))).quantize(Decimal('0.01'))),
                   "specification_match": x.specification_match, "note": x.note} for x in lines],
    }


@rfq_router.post("/{rfq_id}/offers", status_code=201)
def record_supplier_offer(
    rfq_id: UUID, payload: SupplierOfferCreateRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    rfq = db.query(SupplierRFQ).filter(SupplierRFQ.id == rfq_id, SupplierRFQ.company_id == actor.company_id).first()
    if rfq is None:
        raise HTTPException(status_code=404, detail="Запрос предложений не найден")
    recipient = db.query(SupplierRFQRecipient).filter(
        SupplierRFQRecipient.company_id == actor.company_id, SupplierRFQRecipient.rfq_id == rfq.id,
        SupplierRFQRecipient.supplier_id == payload.supplier_id,
    ).with_for_update().first()
    if recipient is None:
        raise HTTPException(status_code=422, detail="Поставщик не входит в список адресатов этого запроса")
    if db.query(SupplierOffer).filter(SupplierOffer.company_id == actor.company_id,
                                     SupplierOffer.rfq_id == rfq.id,
                                     SupplierOffer.supplier_id == payload.supplier_id).first():
        raise HTTPException(status_code=409, detail="Ответ этого поставщика уже зарегистрирован")
    rfq_lines = db.query(SupplierRFQLine).filter(
        SupplierRFQLine.company_id == actor.company_id, SupplierRFQLine.rfq_id == rfq.id
    ).all()
    valid_ids = {x.id for x in rfq_lines}
    supplied_ids = [x.rfq_line_id for x in payload.lines]
    if len(set(supplied_ids)) != len(supplied_ids) or not set(supplied_ids).issubset(valid_ids):
        raise HTTPException(status_code=422, detail="Позиции ответа содержат дубли или не принадлежат запросу")
    offer = SupplierOffer(
        company_id=actor.company_id, rfq_id=rfq.id, supplier_id=payload.supplier_id,
        recipient_id=recipient.id, version_no=1, is_current=True, source_channel=payload.source_channel,
        supplier_offer_number=payload.supplier_offer_number, received_at=payload.received_at or datetime.now(timezone.utc),
        valid_until=payload.valid_until, delivery_days=payload.delivery_days,
        delivery_cost=payload.delivery_cost, vat_treatment=payload.vat_treatment,
        vat_amount=payload.vat_amount, payment_terms=payload.payment_terms,
        original_text=payload.original_text, review_status="pending", created_by_membership_id=actor.id,
    )
    db.add(offer); db.flush()
    for line in payload.lines:
        db.add(SupplierOfferLine(company_id=actor.company_id, offer_id=offer.id, **line.model_dump()))
    recipient.status = "responded"
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
                 action="supplier_offer.recorded", entity_type="supplier_offer", entity_id=str(offer.id),
                 details={"rfq_id": str(rfq.id), "supplier_id": str(payload.supplier_id), "line_count": len(payload.lines), "source_channel": payload.source_channel})
    db.commit()
    return {"id": str(offer.id), "review_status": "pending", "message": "Ответ сохранён и ожидает проверки. В расчётах выбора пока не участвует."}


@rfq_router.post("/{rfq_id}/offers/{offer_id}/revisions", status_code=201)
def revise_supplier_offer(
    rfq_id: UUID, offer_id: UUID, payload: SupplierOfferCreateRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    """Create an immutable next version; previous versions remain in history."""
    previous = db.query(SupplierOffer).filter(
        SupplierOffer.id == offer_id, SupplierOffer.rfq_id == rfq_id,
        SupplierOffer.company_id == actor.company_id, SupplierOffer.is_current.is_(True),
    ).with_for_update().first()
    if previous is None:
        raise HTTPException(status_code=404, detail="Актуальная версия ответа не найдена")
    if payload.supplier_id != previous.supplier_id:
        raise HTTPException(status_code=422, detail="Нельзя менять поставщика при создании новой версии")
    rfq_lines = db.query(SupplierRFQLine).filter(
        SupplierRFQLine.company_id == actor.company_id, SupplierRFQLine.rfq_id == rfq_id
    ).all()
    valid_ids = {x.id for x in rfq_lines}
    supplied_ids = [x.rfq_line_id for x in payload.lines]
    if len(set(supplied_ids)) != len(supplied_ids) or not set(supplied_ids).issubset(valid_ids):
        raise HTTPException(status_code=422, detail="Позиции новой версии содержат дубли или не принадлежат запросу")
    recipient = db.query(SupplierRFQRecipient).filter(
        SupplierRFQRecipient.company_id == actor.company_id, SupplierRFQRecipient.rfq_id == rfq_id,
        SupplierRFQRecipient.supplier_id == previous.supplier_id,
    ).first()
    if recipient is None:
        raise HTTPException(status_code=409, detail="Не найден адресат исходного запроса")
    previous.is_current = False
    stale_selections = db.query(SupplierRFQSelection).filter(
        SupplierRFQSelection.company_id == actor.company_id,
        SupplierRFQSelection.rfq_id == rfq_id,
        SupplierRFQSelection.offer_id == previous.id,
    ).all()
    for stale in stale_selections:
        record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
            action="supplier_offer.selection_invalidated_by_revision", entity_type="supplier_rfq_selection",
            entity_id=str(stale.id), details={"previous_offer_id": str(previous.id)})
        db.delete(stale)
    new_offer = SupplierOffer(
        company_id=actor.company_id, rfq_id=rfq_id, supplier_id=previous.supplier_id,
        recipient_id=recipient.id, version_no=previous.version_no + 1,
        supersedes_offer_id=previous.id, is_current=True, source_channel=payload.source_channel,
        supplier_offer_number=payload.supplier_offer_number, received_at=payload.received_at or datetime.now(timezone.utc),
        valid_until=payload.valid_until, delivery_days=payload.delivery_days, delivery_cost=payload.delivery_cost,
        vat_treatment=payload.vat_treatment, vat_amount=payload.vat_amount, payment_terms=payload.payment_terms,
        original_text=payload.original_text, review_status="pending", created_by_membership_id=actor.id,
    )
    db.add(new_offer); db.flush()
    for line in payload.lines:
        db.add(SupplierOfferLine(company_id=actor.company_id, offer_id=new_offer.id, **line.model_dump()))
    # Previous human selection is retained as history but no longer considered current.
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="supplier_offer.revised", entity_type="supplier_offer", entity_id=str(new_offer.id),
        details={"previous_offer_id": str(previous.id), "version_no": new_offer.version_no, "supplier_id": str(previous.supplier_id)})
    db.commit()
    return {"id": str(new_offer.id), "version_no": new_offer.version_no, "supersedes_offer_id": str(previous.id),
            "review_status": "pending", "message": "Новая версия сохранена. Требуется повторная проверка; предыдущая версия сохранена в истории."}


@rfq_router.get("/{rfq_id}/offers")
def list_supplier_offers(
    rfq_id: UUID,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    rfq = db.query(SupplierRFQ).filter(SupplierRFQ.id == rfq_id, SupplierRFQ.company_id == actor.company_id).first()
    if rfq is None:
        raise HTTPException(status_code=404, detail="Запрос предложений не найден")
    offers = db.query(SupplierOffer).filter(SupplierOffer.company_id == actor.company_id, SupplierOffer.rfq_id == rfq.id).order_by(SupplierOffer.created_at).all()
    result = []
    for offer in offers:
        lines = db.query(SupplierOfferLine).filter(SupplierOfferLine.company_id == actor.company_id, SupplierOfferLine.offer_id == offer.id).all()
        supplier = db.query(Supplier).filter(Supplier.company_id == actor.company_id, Supplier.id == offer.supplier_id).first()
        result.append(_offer_payload(offer, lines, supplier.name if supplier else "Поставщик"))
    return result


@rfq_router.post("/{rfq_id}/offers/{offer_id}/review")
def review_supplier_offer(
    rfq_id: UUID, offer_id: UUID, payload: SupplierOfferReviewRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    offer = db.query(SupplierOffer).filter(SupplierOffer.id == offer_id, SupplierOffer.rfq_id == rfq_id,
        SupplierOffer.company_id == actor.company_id).with_for_update().first()
    if offer is None:
        raise HTTPException(status_code=404, detail="Ответ поставщика не найден")
    offer.review_status = payload.decision
    offer.review_note = payload.note.strip()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action=f"supplier_offer.{payload.decision}", entity_type="supplier_offer", entity_id=str(offer.id),
        details={"note": offer.review_note})
    db.commit()
    return {"id": str(offer.id), "review_status": offer.review_status, "review_note": offer.review_note}


@rfq_router.get("/{rfq_id}/comparison")
def compare_supplier_offers(
    rfq_id: UUID,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    rfq = db.query(SupplierRFQ).filter(SupplierRFQ.id == rfq_id, SupplierRFQ.company_id == actor.company_id).first()
    if rfq is None:
        raise HTTPException(status_code=404, detail="Запрос предложений не найден")
    rfq_lines = db.query(SupplierRFQLine).filter(SupplierRFQLine.company_id == actor.company_id, SupplierRFQLine.rfq_id == rfq.id).order_by(SupplierRFQLine.line_number).all()
    offers = db.query(SupplierOffer).filter(SupplierOffer.company_id == actor.company_id, SupplierOffer.rfq_id == rfq.id,
        SupplierOffer.review_status == "confirmed", SupplierOffer.is_current.is_(True)).all()
    rows=[]
    for rfq_line in rfq_lines:
        alternatives=[]
        for offer in offers:
            line=db.query(SupplierOfferLine).filter(SupplierOfferLine.company_id == actor.company_id,
                SupplierOfferLine.offer_id == offer.id, SupplierOfferLine.rfq_line_id == rfq_line.id).first()
            if line is None: continue
            supplier=db.query(Supplier).filter(Supplier.company_id == actor.company_id, Supplier.id == offer.supplier_id).first()
            goods=(Decimal(str(line.quantity))*Decimal(str(line.unit_price))).quantize(Decimal('0.01'))
            all_goods=sum((Decimal(str(x.quantity))*Decimal(str(x.unit_price)) for x in db.query(SupplierOfferLine).filter(
                SupplierOfferLine.company_id == actor.company_id, SupplierOfferLine.offer_id == offer.id).all()),Decimal('0.00'))
            delivery_share=(Decimal(str(offer.delivery_cost))*goods/all_goods).quantize(Decimal('0.01')) if all_goods else Decimal('0.00')
            vat=Decimal(str(offer.vat_amount)) if offer.vat_amount is not None else None
            vat_share=(vat*goods/all_goods).quantize(Decimal('0.01')) if vat is not None and all_goods else None
            alternatives.append({"offer_id":str(offer.id),"supplier_id":str(offer.supplier_id),"supplier_name":supplier.name if supplier else "Поставщик",
                "quantity":str(line.quantity),"unit":line.unit,"unit_price":str(line.unit_price),"goods_total":str(goods),
                "allocated_delivery":str(delivery_share),"allocated_declared_vat":str(vat_share) if vat_share is not None else None,
                "landed_total":str((goods+delivery_share+(vat_share or Decimal('0.00'))).quantize(Decimal('0.01'))),
                "vat_treatment":offer.vat_treatment,"vat_complete":vat is not None or offer.vat_treatment == "no_vat",
                "delivery_days":offer.delivery_days,"payment_terms":offer.payment_terms,
                "specification_match":line.specification_match,"warning":("Несоответствие характеристик" if line.specification_match=="mismatch" else "Требуется сверка характеристик" if line.specification_match=="unknown" else None)})
        rows.append({"rfq_line_id":str(rfq_line.id),"item_name":rfq_line.item_name,"quantity":str(rfq_line.quantity),"unit":rfq_line.unit,"offers":alternatives})
    return {"rfq_id":str(rfq.id),"currency":"RUB","rows":rows,
        "method":"Доставка и заявленный НДС распределены пропорционально стоимости товаров по ответу. Это расчётное распределение, не налоговое заключение.",
        "selection_policy":"Автоматический выбор отсутствует. Сравнивайте характеристики, сроки и условия; решение фиксирует сотрудник."}


@rfq_router.post("/{rfq_id}/create-procurement-drafts", status_code=201)
def create_procurement_drafts_from_rfq(
    rfq_id: UUID,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    """Convert all manually selected RFQ lines into one draft per supplier; never authorize or send."""
    rfq = db.query(SupplierRFQ).filter(
        SupplierRFQ.id == rfq_id, SupplierRFQ.company_id == actor.company_id
    ).first()
    if rfq is None:
        raise HTTPException(status_code=404, detail="Запрос предложений не найден")
    rfq_lines = db.query(SupplierRFQLine).filter(
        SupplierRFQLine.company_id == actor.company_id, SupplierRFQLine.rfq_id == rfq.id
    ).order_by(SupplierRFQLine.line_number).all()
    selections = db.query(SupplierRFQSelection).filter(
        SupplierRFQSelection.company_id == actor.company_id, SupplierRFQSelection.rfq_id == rfq.id
    ).all()
    by_line = {x.rfq_line_id: x for x in selections}
    missing = [str(x.id) for x in rfq_lines if x.id not in by_line]
    if missing:
        raise HTTPException(status_code=409, detail="Сначала вручную выберите поставщика по каждой позиции запроса")
    grouped = {}
    for rfq_line in rfq_lines:
        selection = by_line[rfq_line.id]
        offer = db.query(SupplierOffer).filter(
            SupplierOffer.id == selection.offer_id, SupplierOffer.company_id == actor.company_id,
            SupplierOffer.rfq_id == rfq.id, SupplierOffer.review_status == "confirmed",
            SupplierOffer.is_current.is_(True),
        ).first()
        if offer is None:
            raise HTTPException(status_code=409, detail="Один из выбранных ответов больше не является актуальным и подтверждённым")
        offer_line = db.query(SupplierOfferLine).filter(
            SupplierOfferLine.company_id == actor.company_id, SupplierOfferLine.offer_id == offer.id,
            SupplierOfferLine.rfq_line_id == rfq_line.id,
        ).first()
        if offer_line is None or offer_line.specification_match != "match":
            raise HTTPException(status_code=409, detail="В выбранном ответе отсутствует подтверждённое соответствие позиции")
        if Decimal(str(offer_line.quantity)) < Decimal(str(rfq_line.quantity)):
            raise HTTPException(status_code=409, detail="Предложенного количества недостаточно для полного объёма позиции")
        grouped.setdefault(offer.supplier_id, []).append((rfq_line, offer_line))
    created = []
    for supplier_id, items in grouped.items():
        existing = db.query(ProcurementOrder).filter(
            ProcurementOrder.company_id == actor.company_id, ProcurementOrder.source_rfq_id == rfq.id,
            ProcurementOrder.source_supplier_id == supplier_id,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Черновики по этому запросу уже создавались; повторное создание заблокировано")
        supplier = db.query(Supplier).filter(
            Supplier.company_id == actor.company_id, Supplier.id == supplier_id
        ).first()
        if supplier is None:
            raise HTTPException(status_code=409, detail="Поставщик из выбранного предложения не найден")
        order = ProcurementOrder(
            company_id=actor.company_id,
            order_number=f"RFQ-{rfq.rfq_number}-{str(supplier_id)[:8]}",
            supplier_name=supplier.name, supplier_inn=supplier.inn,
            source_rfq_id=rfq.id, source_supplier_id=supplier.id,
            currency="RUB", total_amount=Decimal("0.00"), status="draft",
            created_by_membership_id=actor.id,
        )
        db.add(order); db.flush()
        total = Decimal("0.00")
        for number, (rfq_line, offer_line) in enumerate(items, 1):
            qty = Decimal(str(rfq_line.quantity))
            price = Decimal(str(offer_line.unit_price))
            line_total = (qty * price).quantize(Decimal("0.01"))
            total += line_total
            db.add(ProcurementOrderLine(
                company_id=actor.company_id, procurement_order_id=order.id, line_number=number,
                item_name=rfq_line.item_name, quantity=qty, unit=rfq_line.unit,
                unit_price=price, line_total=line_total,
            ))
        order.total_amount = total.quantize(Decimal("0.01"))
        created.append({"id": str(order.id), "order_number": order.order_number,
                        "supplier_name": order.supplier_name, "total_amount": str(order.total_amount),
                        "line_count": len(items), "status": "draft"})
        record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
            action="procurement.draft_created_from_rfq", entity_type="procurement_order",
            entity_id=str(order.id), details={"rfq_id": str(rfq.id), "supplier_id": str(supplier.id),
                                              "total_amount": str(order.total_amount)})
    db.commit()
    return {"rfq_id": str(rfq.id), "orders": created,
            "message": "Созданы черновики закупок. Они не согласованы и не отправлены поставщикам."}


@rfq_router.post("/{rfq_id}/selections")
def select_supplier_offer(
    rfq_id: UUID, payload: SupplierOfferSelectionRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    rfq=db.query(SupplierRFQ).filter(SupplierRFQ.id==rfq_id,SupplierRFQ.company_id==actor.company_id).first()
    if rfq is None: raise HTTPException(status_code=404,detail="Запрос предложений не найден")
    line=db.query(SupplierRFQLine).filter(SupplierRFQLine.id==payload.rfq_line_id,SupplierRFQLine.rfq_id==rfq.id,SupplierRFQLine.company_id==actor.company_id).first()
    offer=db.query(SupplierOffer).filter(SupplierOffer.id==payload.offer_id,SupplierOffer.rfq_id==rfq.id,SupplierOffer.company_id==actor.company_id).first()
    if line is None or offer is None: raise HTTPException(status_code=404,detail="Позиция или ответ не найдены")
    if offer.review_status!="confirmed" or not offer.is_current: raise HTTPException(status_code=409,detail="Можно выбрать только подтверждённую актуальную версию ответа")
    offer_line=db.query(SupplierOfferLine).filter(SupplierOfferLine.company_id==actor.company_id,SupplierOfferLine.offer_id==offer.id,SupplierOfferLine.rfq_line_id==line.id).first()
    if offer_line is None: raise HTTPException(status_code=422,detail="В ответе нет предложения по выбранной позиции")
    if offer_line.specification_match!="match": raise HTTPException(status_code=409,detail="Нельзя выбрать позицию без подтверждённого совпадения характеристик")
    selection=db.query(SupplierRFQSelection).filter(SupplierRFQSelection.company_id==actor.company_id,SupplierRFQSelection.rfq_line_id==line.id).with_for_update().first()
    if selection is None:
        selection=SupplierRFQSelection(company_id=actor.company_id,rfq_id=rfq.id,rfq_line_id=line.id,offer_id=offer.id,selected_by_membership_id=actor.id,note=payload.note.strip())
        db.add(selection)
    else:
        selection.offer_id=offer.id; selection.selected_by_membership_id=actor.id; selection.note=payload.note.strip(); selection.selected_at=datetime.now(timezone.utc)
    supplier=db.query(Supplier).filter(Supplier.company_id==actor.company_id,Supplier.id==offer.supplier_id).first()
    record_audit(db,company_id=actor.company_id,actor_user_id=actor.user_id,action="supplier_offer.selected",entity_type="supplier_rfq_selection",entity_id=str(selection.id),details={"rfq_id":str(rfq.id),"rfq_line_id":str(line.id),"offer_id":str(offer.id),"supplier":supplier.name if supplier else None,"note":payload.note.strip()})
    db.commit()
    return {"rfq_line_id":str(line.id),"offer_id":str(offer.id),"supplier_name":supplier.name if supplier else None,"status":"Выбор зафиксирован вручную"}
