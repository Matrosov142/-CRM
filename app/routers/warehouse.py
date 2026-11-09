"""Warehouse receiving and accepted-stock batches. No automatic write-off or shipment."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.database import get_db
from app.dependencies import get_current_membership
from app.models import (Membership, ProcurementOrder, ProcurementOrderLine,
                        WarehouseReceipt, WarehouseReceiptLine, StockBatch, StockReservation, StockReservationLine, WarehouseShipment, WarehouseShipmentLine, DeliveryEstimate)
from app.permissions import Role, require_roles
from app.schemas import WarehouseReceiptCreateRequest, StockReservationCreateRequest, StockReservationReleaseRequest, WarehouseShipmentCreateRequest, ShipmentActualDeliveryCostRequest

router = APIRouter(prefix="/api/v1/warehouse", tags=["Склад"])


@router.post("/receipts", status_code=201)
def create_receipt(payload: WarehouseReceiptCreateRequest,
                   actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE)),
                   db: Session = Depends(get_db)):
    order = db.query(ProcurementOrder).filter(
        ProcurementOrder.id == payload.procurement_order_id,
        ProcurementOrder.company_id == actor.company_id,
    ).with_for_update().first()
    if order is None:
        raise HTTPException(status_code=404, detail="Закупка не найдена")
    if order.status != "authorized":
        raise HTTPException(status_code=409, detail="Принимать можно только согласованную закупку")
    line_ids = [x.procurement_order_line_id for x in payload.lines]
    if len(set(line_ids)) != len(line_ids):
        raise HTTPException(status_code=422, detail="Строка закупки указана повторно")
    order_lines = db.query(ProcurementOrderLine).filter(
        ProcurementOrderLine.company_id == actor.company_id,
        ProcurementOrderLine.procurement_order_id == order.id,
        ProcurementOrderLine.id.in_(line_ids),
    ).all()
    by_id = {line.id: line for line in order_lines}
    if len(by_id) != len(line_ids):
        raise HTTPException(status_code=422, detail="Одна или несколько строк не относятся к этой закупке")

    # Lock existing receipt rows for the selected order lines to serialize partial receipts.
    prior = (db.query(WarehouseReceiptLine.procurement_order_line_id,
                      func.coalesce(func.sum(WarehouseReceiptLine.received_quantity), 0))
             .join(WarehouseReceipt, WarehouseReceipt.id == WarehouseReceiptLine.receipt_id)
             .filter(WarehouseReceiptLine.company_id == actor.company_id,
                     WarehouseReceipt.procurement_order_id == order.id,
                     WarehouseReceipt.status == "accepted",
                     WarehouseReceiptLine.procurement_order_line_id.in_(line_ids))
             .group_by(WarehouseReceiptLine.procurement_order_line_id).all())
    already = {row[0]: Decimal(row[1]) for row in prior}

    for item in payload.lines:
        if item.accepted_quantity + item.defective_quantity != item.received_quantity:
            raise HTTPException(status_code=422, detail="Принятое количество и брак должны равняться фактически полученному")
        if item.accepted_quantity < 0 or item.defective_quantity < 0:
            raise HTTPException(status_code=422, detail="Количество не может быть отрицательным")
        remaining = Decimal(by_id[item.procurement_order_line_id].quantity) - already.get(item.procurement_order_line_id, Decimal("0"))
        if item.received_quantity > remaining:
            raise HTTPException(status_code=409, detail=f"Превышено заказанное количество по позиции: {by_id[item.procurement_order_line_id].item_name}. Остаток к приёмке: {remaining}")

    receipt = WarehouseReceipt(
        company_id=actor.company_id, receipt_number=payload.receipt_number.strip(),
        procurement_order_id=order.id, received_at=payload.received_at or datetime.now(timezone.utc),
        supplier_document_number=payload.supplier_document_number, note=payload.note,
        status="accepted", created_by_membership_id=actor.id,
    )
    db.add(receipt)
    db.flush()
    created_batches = []
    for item in payload.lines:
        source = by_id[item.procurement_order_line_id]
        receipt_line = WarehouseReceiptLine(
            company_id=actor.company_id, receipt_id=receipt.id,
            procurement_order_line_id=source.id, received_quantity=item.received_quantity,
            accepted_quantity=item.accepted_quantity, defective_quantity=item.defective_quantity,
            defect_note=item.defect_note,
        )
        db.add(receipt_line)
        db.flush()
        if item.accepted_quantity > 0:
            batch = StockBatch(
                company_id=actor.company_id, receipt_line_id=receipt_line.id,
                batch_number=f"{payload.receipt_number}-{source.line_number}-{uuid4().hex[:6].upper()}",
                item_name=source.item_name, quantity_received=item.accepted_quantity,
                quantity_balance=item.accepted_quantity, unit=source.unit,
                unit_cost=source.unit_price, location=payload.location,
                received_at=receipt.received_at,
            )
            db.add(batch)
            created_batches.append(batch)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
                 action="warehouse.receipt_created", entity_type="warehouse_receipt",
                 entity_id=str(receipt.id), details={
                     "receipt_number": receipt.receipt_number,
                     "order_id": str(order.id),
                     "received": str(sum((x.received_quantity for x in payload.lines), Decimal("0"))),
                     "accepted": str(sum((x.accepted_quantity for x in payload.lines), Decimal("0"))),
                     "defective": str(sum((x.defective_quantity for x in payload.lines), Decimal("0"))),
                     "batch_count": len(created_batches),
                 })
    db.commit()
    return {"id": str(receipt.id), "receipt_number": receipt.receipt_number,
            "status": receipt.status, "batch_count": len(created_batches),
            "accepted_quantity": str(sum((x.accepted_quantity for x in payload.lines), Decimal("0"))),
            "defective_quantity": str(sum((x.defective_quantity for x in payload.lines), Decimal("0"))),
            "message": "Приёмка сохранена. В складской остаток включено только принятое годное количество."}


@router.get("/batches")
def list_batches(search: str | None = Query(default=None, max_length=200),
                 actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
                 db: Session = Depends(get_db)):
    query = db.query(StockBatch).filter(StockBatch.company_id == actor.company_id)
    if search:
        query = query.filter(StockBatch.item_name.ilike(f"%{search}%"))
    batches = query.order_by(StockBatch.received_at.desc()).limit(300).all()
    return [{"id": str(x.id), "batch_number": x.batch_number, "item_name": x.item_name,
             "quantity_received": str(x.quantity_received), "quantity_balance": str(x.quantity_balance),
             "unit": x.unit, "unit_cost": str(x.unit_cost), "location": x.location,
             "received_at": x.received_at.isoformat()} for x in batches]


@router.get("/receipts")
def list_receipts(actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
                  db: Session = Depends(get_db)):
    rows = db.query(WarehouseReceipt).filter(WarehouseReceipt.company_id == actor.company_id).order_by(WarehouseReceipt.created_at.desc()).limit(200).all()
    return [{"id": str(x.id), "receipt_number": x.receipt_number,
             "procurement_order_id": str(x.procurement_order_id), "received_at": x.received_at.isoformat(),
             "supplier_document_number": x.supplier_document_number, "status": x.status} for x in rows]


@router.post("/reservations", status_code=201)
def create_reservation(payload: StockReservationCreateRequest,
                       actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.PROCUREMENT_MANAGER)),
                       db: Session = Depends(get_db)):
    ids = [x.stock_batch_id for x in payload.lines]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Партия указана повторно")
    batches = (db.query(StockBatch).filter(StockBatch.company_id == actor.company_id,
               StockBatch.id.in_(ids)).order_by(StockBatch.id).with_for_update().all())
    if len(batches) != len(ids):
        raise HTTPException(status_code=422, detail="Одна или несколько партий не найдены")
    reserved_rows = (db.query(StockReservationLine.stock_batch_id, func.coalesce(func.sum(StockReservationLine.quantity - StockReservationLine.quantity_shipped), 0))
        .join(StockReservation, StockReservation.id == StockReservationLine.reservation_id)
        .filter(StockReservationLine.company_id == actor.company_id, StockReservation.status == "active",
                StockReservationLine.stock_batch_id.in_(ids))
        .group_by(StockReservationLine.stock_batch_id).all())
    reserved = {row[0]: Decimal(row[1]) for row in reserved_rows}
    by_id = {b.id: b for b in batches}
    for line in payload.lines:
        available = Decimal(by_id[line.stock_batch_id].quantity_balance) - reserved.get(line.stock_batch_id, Decimal("0"))
        if line.quantity > available:
            raise HTTPException(status_code=409, detail=f"Недостаточно доступного остатка партии {by_id[line.stock_batch_id].batch_number}: доступно {available}")
    reservation = StockReservation(company_id=actor.company_id, reference=payload.reference.strip(),
        reason=payload.reason.strip(), status="active", created_by_membership_id=actor.id)
    db.add(reservation); db.flush()
    for line in payload.lines:
        db.add(StockReservationLine(company_id=actor.company_id, reservation_id=reservation.id,
            stock_batch_id=line.stock_batch_id, quantity=line.quantity))
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="warehouse.stock_reserved", entity_type="stock_reservation", entity_id=str(reservation.id),
        details={"reference": reservation.reference, "lines": len(payload.lines),
                 "quantity": str(sum((x.quantity for x in payload.lines), Decimal("0")))})
    db.commit()
    return {"id": str(reservation.id), "status": "active", "reference": reservation.reference,
            "message": "Резерв создан. Физический остаток не изменён; доступный остаток уменьшен."}

@router.post("/reservations/{reservation_id}/release")
def release_reservation(reservation_id: UUID, payload: StockReservationReleaseRequest,
                        actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.PROCUREMENT_MANAGER)),
                        db: Session = Depends(get_db)):
    reservation = (db.query(StockReservation).filter(StockReservation.company_id == actor.company_id,
        StockReservation.id == reservation_id).with_for_update().first())
    if reservation is None:
        raise HTTPException(status_code=404, detail="Резерв не найден")
    if reservation.status != "active":
        raise HTTPException(status_code=409, detail="Резерв уже освобождён")
    reservation.status = "released"
    reservation.released_by_membership_id = actor.id
    reservation.released_at = datetime.now(timezone.utc)
    reservation.release_reason = payload.reason.strip()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="warehouse.stock_reservation_released", entity_type="stock_reservation",
        entity_id=str(reservation.id), details={"reference": reservation.reference, "reason": reservation.release_reason})
    db.commit()
    return {"id": str(reservation.id), "status": "released",
            "message": "Резерв освобождён. Доступный остаток восстановлен."}


@router.get("/reservations")
def list_reservations(
    status: str | None = Query(default=None, pattern="^(active|released)$"),
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.PROCUREMENT_MANAGER, Role.LOGISTICS, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    """Return reservation headers and line identifiers required for partial shipment."""
    query = db.query(StockReservation).filter(StockReservation.company_id == actor.company_id)
    if status:
        query = query.filter(StockReservation.status == status)
    reservations = query.order_by(StockReservation.created_at.desc()).limit(200).all()
    result = []
    for reservation in reservations:
        lines = (db.query(StockReservationLine, StockBatch)
            .join(StockBatch, StockBatch.id == StockReservationLine.stock_batch_id)
            .filter(StockReservationLine.company_id == actor.company_id,
                    StockReservationLine.reservation_id == reservation.id)
            .order_by(StockReservationLine.id).all())
        result.append({
            "id": str(reservation.id), "reference": reservation.reference,
            "reason": reservation.reason, "status": reservation.status,
            "created_at": reservation.created_at.isoformat(),
            "released_at": reservation.released_at.isoformat() if reservation.released_at else None,
            "release_reason": reservation.release_reason,
            "lines": [{
                "id": str(line.id), "stock_batch_id": str(line.stock_batch_id),
                "batch_number": batch.batch_number, "item_name": batch.item_name,
                "quantity": str(line.quantity), "quantity_shipped": str(line.quantity_shipped),
                "quantity_remaining": str(Decimal(line.quantity) - Decimal(line.quantity_shipped)),
                "unit": batch.unit,
            } for line, batch in lines],
        })
    return result


@router.get("/availability")
def stock_availability(actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
                       db: Session = Depends(get_db)):
    batches = db.query(StockBatch).filter(StockBatch.company_id == actor.company_id).order_by(StockBatch.received_at.desc()).limit(500).all()
    ids = [b.id for b in batches]
    rows = []
    if ids:
        rows = (db.query(StockReservationLine.stock_batch_id, func.coalesce(func.sum(StockReservationLine.quantity - StockReservationLine.quantity_shipped), 0))
            .join(StockReservation, StockReservation.id == StockReservationLine.reservation_id)
            .filter(StockReservationLine.company_id == actor.company_id, StockReservation.status == "active",
                    StockReservationLine.stock_batch_id.in_(ids)).group_by(StockReservationLine.stock_batch_id).all())
    reserved = {row[0]: Decimal(row[1]) for row in rows}
    return [{"batch_id": str(b.id), "batch_number": b.batch_number, "item_name": b.item_name,
        "physical_quantity": str(b.quantity_balance), "reserved_quantity": str(reserved.get(b.id, Decimal("0"))),
        "available_quantity": str(Decimal(b.quantity_balance) - reserved.get(b.id, Decimal("0"))),
        "unit": b.unit, "location": b.location} for b in batches]


@router.post("/shipments", status_code=201)
def create_shipment(payload: WarehouseShipmentCreateRequest,
                    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.LOGISTICS)),
                    db: Session = Depends(get_db)):
    if len({x.reservation_line_id for x in payload.lines}) != len(payload.lines):
        raise HTTPException(status_code=422, detail="Строка резерва указана повторно")
    reservation = (db.query(StockReservation).filter(StockReservation.company_id == actor.company_id,
        StockReservation.id == payload.reservation_id).with_for_update().first())
    if reservation is None:
        raise HTTPException(status_code=404, detail="Резерв не найден")
    if reservation.status != "active":
        raise HTTPException(status_code=409, detail="Отгружать можно только из активного резерва")
    line_ids = [x.reservation_line_id for x in payload.lines]
    reserve_lines = (db.query(StockReservationLine).filter(
        StockReservationLine.company_id == actor.company_id,
        StockReservationLine.reservation_id == reservation.id,
        StockReservationLine.id.in_(line_ids)).order_by(StockReservationLine.id).with_for_update().all())
    if len(reserve_lines) != len(line_ids):
        raise HTTPException(status_code=422, detail="Строка не относится к указанному резерву")
    by_id = {x.id: x for x in reserve_lines}
    batch_ids = [x.stock_batch_id for x in reserve_lines]
    batches = (db.query(StockBatch).filter(StockBatch.company_id == actor.company_id,
        StockBatch.id.in_(batch_ids)).order_by(StockBatch.id).with_for_update().all())
    batch_by_id = {x.id: x for x in batches}
    for item in payload.lines:
        reserve_line = by_id[item.reservation_line_id]
        remaining_reserved = Decimal(reserve_line.quantity) - Decimal(reserve_line.quantity_shipped)
        batch = batch_by_id[reserve_line.stock_batch_id]
        if item.quantity > remaining_reserved:
            raise HTTPException(status_code=409, detail=f"Количество превышает неотгруженный резерв: {remaining_reserved}")
        if item.quantity > Decimal(batch.quantity_balance):
            raise HTTPException(status_code=409, detail=f"Недостаточно физического остатка партии {batch.batch_number}")
    estimate = None
    planned_delivery_cost = None
    if payload.delivery_estimate_id:
        estimate = (db.query(DeliveryEstimate).filter(
            DeliveryEstimate.company_id == actor.company_id,
            DeliveryEstimate.id == payload.delivery_estimate_id).with_for_update().first())
        if estimate is None:
            raise HTTPException(status_code=404, detail="Расчёт доставки не найден")
        if estimate.selected_option_index is None or estimate.selected_option_index >= len(estimate.options):
            raise HTTPException(status_code=409, detail="Сначала выберите вариант в расчёте доставки")
        planned_delivery_cost = Decimal(str(estimate.options[estimate.selected_option_index]["total"]))
    shipment = WarehouseShipment(company_id=actor.company_id, shipment_number=payload.shipment_number.strip(),
        reservation_id=reservation.id, shipped_at=payload.shipped_at or datetime.now(timezone.utc),
        carrier=payload.carrier, tracking_number=payload.tracking_number, destination=payload.destination,
        delivery_estimate_id=estimate.id if estimate else None, planned_delivery_cost=planned_delivery_cost,
        note=payload.note, status="confirmed", created_by_membership_id=actor.id)
    db.add(shipment); db.flush()
    total = Decimal("0")
    for item in payload.lines:
        reserve_line = by_id[item.reservation_line_id]
        batch = batch_by_id[reserve_line.stock_batch_id]
        reserve_line.quantity_shipped = Decimal(reserve_line.quantity_shipped) + item.quantity
        batch.quantity_balance = Decimal(batch.quantity_balance) - item.quantity
        total += item.quantity
        db.add(WarehouseShipmentLine(company_id=actor.company_id, shipment_id=shipment.id,
            reservation_line_id=reserve_line.id, quantity=item.quantity,
            batch_number=batch.batch_number, item_name=batch.item_name))
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="warehouse.shipment_confirmed", entity_type="warehouse_shipment", entity_id=str(shipment.id),
        details={"shipment_number": shipment.shipment_number, "reservation_id": str(reservation.id),
                 "line_count": len(payload.lines), "quantity": str(total),
                 "delivery_estimate_id": str(estimate.id) if estimate else None,
                 "planned_delivery_cost": str(planned_delivery_cost) if planned_delivery_cost is not None else None})
    db.commit()
    return {"id": str(shipment.id), "shipment_number": shipment.shipment_number,
        "status": shipment.status, "shipped_quantity": str(total),
        "delivery_estimate_id": str(shipment.delivery_estimate_id) if shipment.delivery_estimate_id else None,
        "planned_delivery_cost": str(shipment.planned_delivery_cost) if shipment.planned_delivery_cost is not None else None,
        "message": "Отгрузка подтверждена. Физический остаток уменьшен на фактически отгруженное количество."}

@router.get("/shipments")
def list_shipments(actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.WAREHOUSE, Role.LOGISTICS, Role.ACCOUNTING)),
                   db: Session = Depends(get_db)):
    rows = db.query(WarehouseShipment).filter(WarehouseShipment.company_id == actor.company_id).order_by(
        WarehouseShipment.shipped_at.desc()).limit(200).all()
    return [{"id": str(x.id), "shipment_number": x.shipment_number, "reservation_id": str(x.reservation_id),
        "shipped_at": x.shipped_at.isoformat(), "carrier": x.carrier, "tracking_number": x.tracking_number,
        "destination": x.destination, "status": x.status,
        "delivery_estimate_id": str(x.delivery_estimate_id) if x.delivery_estimate_id else None,
        "planned_delivery_cost": str(x.planned_delivery_cost) if x.planned_delivery_cost is not None else None,
        "actual_delivery_cost": str(x.actual_delivery_cost) if x.actual_delivery_cost is not None else None,
        "actual_delivery_at": x.actual_delivery_at.isoformat() if x.actual_delivery_at else None} for x in rows]


@router.post("/shipments/{shipment_id}/actual-delivery-cost")
def record_actual_delivery_cost(
    shipment_id: UUID, payload: ShipmentActualDeliveryCostRequest,
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.LOGISTICS, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    shipment = (db.query(WarehouseShipment).filter(
        WarehouseShipment.company_id == actor.company_id,
        WarehouseShipment.id == shipment_id).with_for_update().first())
    if shipment is None:
        raise HTTPException(status_code=404, detail="Отгрузка не найдена")
    if shipment.delivery_estimate_id is None:
        raise HTTPException(status_code=409, detail="К отгрузке не привязан плановый расчёт доставки")
    previous = str(shipment.actual_delivery_cost) if shipment.actual_delivery_cost is not None else None
    shipment.actual_delivery_cost = payload.actual_cost
    shipment.actual_delivery_at = payload.delivered_at or datetime.now(timezone.utc)
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="warehouse.shipment_actual_delivery_cost_recorded", entity_type="warehouse_shipment",
        entity_id=str(shipment.id), details={"previous_actual_cost": previous,
        "actual_cost": str(payload.actual_cost), "planned_cost": str(shipment.planned_delivery_cost),
        "note": payload.note})
    db.commit()
    variance = (payload.actual_cost - shipment.planned_delivery_cost) if shipment.planned_delivery_cost is not None else None
    return {"shipment_id": str(shipment.id), "planned_cost": str(shipment.planned_delivery_cost) if shipment.planned_delivery_cost is not None else None,
        "actual_cost": str(shipment.actual_delivery_cost), "variance": str(variance) if variance is not None else None,
        "delivered_at": shipment.actual_delivery_at.isoformat(), "message": "Фактическая стоимость доставки сохранена."}
