"""Supplier procurement orders. Placing is a controlled financial commitment."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.controls import require_operation_authorization
from app.database import get_db
from app.dependencies import get_current_membership
from app.models import Membership, ProcurementOrder, ProcurementOrderLine
from app.permissions import Role, require_roles
from app.procurement_math import calculate_order_totals
from app.schemas import ProcurementOrderCreate, ProcurementOrderPlaceRequest

router = APIRouter(prefix="/api/v1/procurement", tags=["Закупки"])


def _order_payload(order, lines):
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "supplier_name": order.supplier_name,
        "supplier_inn": order.supplier_inn,
        "currency": order.currency,
        "total_amount": str(order.total_amount),
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "authorized_at": order.authorized_at.isoformat() if order.authorized_at else None,
        "lines": [{
            "id": str(line.id),
            "line_number": line.line_number,
            "item_name": line.item_name,
            "quantity": str(line.quantity),
            "unit": line.unit,
            "unit_price": str(line.unit_price),
            "line_total": str(line.line_total),
        } for line in lines],
    }


@router.post("/orders", status_code=201)
def create_procurement_order(
    payload: ProcurementOrderCreate,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    # Calculate all money server-side; client totals are never trusted.
    try:
        line_values, total = calculate_order_totals(payload.lines)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    order = ProcurementOrder(
        company_id=actor.company_id,
        order_number=payload.order_number.strip(),
        supplier_name=payload.supplier_name.strip(),
        supplier_inn=payload.supplier_inn,
        currency="RUB",
        total_amount=total,
        status="draft",
        created_by_membership_id=actor.id,
    )
    db.add(order)
    db.flush()
    lines = []
    for number, item, line_total in line_values:
        line = ProcurementOrderLine(
            company_id=actor.company_id,
            procurement_order_id=order.id,
            line_number=number,
            item_name=item.item_name.strip(),
            quantity=item.quantity,
            unit=item.unit.strip(),
            unit_price=item.unit_price,
            line_total=line_total,
        )
        db.add(line)
        lines.append(line)
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="procurement.order_created", entity_type="procurement_order",
        entity_id=str(order.id),
        details={"order_number": order.order_number, "supplier": order.supplier_name, "total_amount": str(total)},
    )
    db.commit()
    return _order_payload(order, lines)


@router.get("/orders")
def list_procurement_orders(
    status: str | None = Query(default=None, pattern="^(draft|authorized|cancelled)$"),
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    query = db.query(ProcurementOrder).filter(ProcurementOrder.company_id == actor.company_id)
    if status:
        query = query.filter(ProcurementOrder.status == status)
    orders = query.order_by(ProcurementOrder.created_at.desc()).limit(200).all()
    return [{
        "id": str(o.id), "order_number": o.order_number, "supplier_name": o.supplier_name,
        "total_amount": str(o.total_amount), "currency": o.currency, "status": o.status,
        "created_at": o.created_at.isoformat(),
    } for o in orders]


@router.get("/orders/{order_id}")
def get_procurement_order(
    order_id: UUID,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    order = db.query(ProcurementOrder).filter(
        ProcurementOrder.id == order_id,
        ProcurementOrder.company_id == actor.company_id,
    ).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ поставщику не найден")
    lines = db.query(ProcurementOrderLine).filter(
        ProcurementOrderLine.procurement_order_id == order.id,
        ProcurementOrderLine.company_id == actor.company_id,
    ).order_by(ProcurementOrderLine.line_number).all()
    return _order_payload(order, lines)


@router.post("/orders/{order_id}/authorize")
def authorize_procurement_order(
    order_id: UUID,
    payload: ProcurementOrderPlaceRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.PROCUREMENT_MANAGER)),
    db: Session = Depends(get_db),
):
    order = db.query(ProcurementOrder).filter(
        ProcurementOrder.id == order_id,
        ProcurementOrder.company_id == actor.company_id,
    ).with_for_update().first()
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ поставщику не найден")
    if order.status != "draft":
        raise HTTPException(status_code=409, detail="Подтвердить можно только черновик заказа")
    # The approval consumption and order state change share this transaction.
    require_operation_authorization(
        db, actor, "purchase", order.total_amount,
        approval_request_id=payload.approval_request_id,
        entity_type="procurement_order", entity_id=str(order.id),
    )
    order.status = "authorized"
    order.authorized_by_membership_id = actor.id
    order.approval_request_id = payload.approval_request_id
    order.authorized_at = datetime.now(timezone.utc)
    record_audit(
        db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="procurement.order_authorized", entity_type="procurement_order",
        entity_id=str(order.id),
        details={"order_number": order.order_number, "total_amount": str(order.total_amount),
                 "approval_request_id": str(payload.approval_request_id) if payload.approval_request_id else None},
    )
    db.commit()
    return {"authorized": True, "id": str(order.id), "status": order.status,
            "message": "Закупка согласована и зафиксирована в CRM. Поставщику не отправляли."}
