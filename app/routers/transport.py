"""Delivery cost estimation: manual carrier tariff vs own fleet; no booking or dispatch."""
from decimal import Decimal
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from app.models import Membership, DeliveryEstimate
from app.database import get_db
from app.audit import record_audit
from sqlalchemy.orm import Session
from app.permissions import Role, require_roles
from app.transport_math import carrier_cost, own_fleet_cost

router = APIRouter(prefix="/api/v1/transport", tags=["Расчёт доставки"])

class CarrierOption(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    base_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    price_per_km: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    loading_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    unloading_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    tolls: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    insurance: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    extra: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    quoted_total: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    delivery_days: int | None = Field(default=None, ge=0, le=365)

class OwnFleetOption(BaseModel):
    fuel_consumption_l_100km: Decimal = Field(gt=0, le=200, max_digits=6, decimal_places=2)
    fuel_price_per_l: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    driver_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    depreciation_per_km: Decimal = Field(default=Decimal("0"), ge=0, max_digits=8, decimal_places=2)
    maintenance_per_km: Decimal = Field(default=Decimal("0"), ge=0, max_digits=8, decimal_places=2)
    tolls: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    loading_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    unloading_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    extra: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    round_trip: bool = True

class DeliveryEstimateRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=300)
    destination: str = Field(min_length=2, max_length=300)
    distance_km_one_way: Decimal = Field(gt=0, le=100000, max_digits=10, decimal_places=2)
    cargo_description: str = Field(min_length=2, max_length=500)
    cargo_weight_kg: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    cargo_volume_m3: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    carrier_options: list[CarrierOption] = Field(default_factory=list, max_length=20)
    own_fleet: OwnFleetOption | None = None

    @model_validator(mode="after")
    def require_option(self):
        if not self.carrier_options and self.own_fleet is None:
            raise ValueError("Укажите тариф хотя бы одной транспортной компании или параметры собственного транспорта")
        return self

@router.post("/estimate")
def estimate_delivery(payload: DeliveryEstimateRequest,
                      actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.LOGISTICS, Role.PROCUREMENT_MANAGER)),
                      db: Session = Depends(get_db)):
    results = []
    for option in payload.carrier_options:
        # Use the actual carrier quote when supplied; otherwise calculate from the entered tariff.
        total = option.quoted_total if option.quoted_total is not None else carrier_cost(
            base_fee=option.base_fee, distance_km=payload.distance_km_one_way,
            price_per_km=option.price_per_km, loading_fee=option.loading_fee,
            unloading_fee=option.unloading_fee, tolls=option.tolls,
            insurance=option.insurance, extra=option.extra)
        results.append({"method": "carrier", "name": option.company_name, "total": str(total),
                        "delivery_days": option.delivery_days, "source": "quote" if option.quoted_total is not None else "manual_tariff_estimate"})
    if payload.own_fleet:
        o = payload.own_fleet
        costs = own_fleet_cost(distance_km=payload.distance_km_one_way,
            fuel_consumption_l_100km=o.fuel_consumption_l_100km, fuel_price_per_l=o.fuel_price_per_l,
            driver_cost=o.driver_cost, depreciation_per_km=o.depreciation_per_km,
            maintenance_per_km=o.maintenance_per_km, tolls=o.tolls,
            loading_fee=o.loading_fee, unloading_fee=o.unloading_fee, extra=o.extra,
            round_trip=o.round_trip)
        results.append({"method": "own_fleet", "name": "Собственный транспорт", "total": str(costs["total"]),
                        "breakdown": {k: str(v) for k, v in costs.items()}, "source": "calculation"})
    results.sort(key=lambda x: Decimal(x["total"]))
    estimate = DeliveryEstimate(
        company_id=actor.company_id, created_by_membership_id=actor.id,
        origin=payload.origin.strip(), destination=payload.destination.strip(),
        distance_km_one_way=payload.distance_km_one_way,
        cargo_description=payload.cargo_description.strip(),
        cargo_weight_kg=payload.cargo_weight_kg, cargo_volume_m3=payload.cargo_volume_m3,
        options=results,
    )
    db.add(estimate)
    db.flush()
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="transport.delivery_estimate_created", entity_type="delivery_estimate",
        entity_id=str(estimate.id), details={"origin": estimate.origin, "destination": estimate.destination,
        "option_count": len(results), "lowest_total": results[0]["total"] if results else None})
    db.commit()
    return {"id": str(estimate.id), "company_id": str(actor.company_id), "currency": "RUB", "origin": payload.origin,
            "destination": payload.destination, "distance_km_one_way": str(payload.distance_km_one_way),
            "cargo_description": payload.cargo_description, "cargo_weight_kg": str(payload.cargo_weight_kg) if payload.cargo_weight_kg else None,
            "cargo_volume_m3": str(payload.cargo_volume_m3) if payload.cargo_volume_m3 else None,
            "options": results, "lowest_estimate": results[0] if results else None,
            "selected_option_index": None,
            "notice": "Расчёт сохранён в истории. Он ориентировочный: расстояние и тарифы введены пользователем. Подтвердите фактическую стоимость и сроки у перевозчика. Автоматического заказа перевозки нет."}


@router.get("/estimates")
def list_delivery_estimates(
    limit: int = Query(default=100, ge=1, le=300),
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.LOGISTICS, Role.PROCUREMENT_MANAGER, Role.ACCOUNTING)),
    db: Session = Depends(get_db),
):
    rows = (db.query(DeliveryEstimate).filter(DeliveryEstimate.company_id == actor.company_id)
        .order_by(DeliveryEstimate.created_at.desc()).limit(limit).all())
    return [{
        "id": str(x.id), "origin": x.origin, "destination": x.destination,
        "distance_km_one_way": str(x.distance_km_one_way), "cargo_description": x.cargo_description,
        "options": x.options, "selected_option_index": x.selected_option_index,
        "selected_option": x.options[x.selected_option_index] if x.selected_option_index is not None else None,
        "created_at": x.created_at.isoformat(),
    } for x in rows]


@router.post("/estimates/{estimate_id}/select")
def select_delivery_option(
    estimate_id: UUID, option_index: int = Query(ge=0),
    actor: Membership = Depends(require_roles(Role.DIRECTOR, Role.LOGISTICS)),
    db: Session = Depends(get_db),
):
    estimate = (db.query(DeliveryEstimate).filter(
        DeliveryEstimate.company_id == actor.company_id,
        DeliveryEstimate.id == estimate_id).with_for_update().first())
    if estimate is None:
        raise HTTPException(status_code=404, detail="Расчёт доставки не найден")
    if option_index >= len(estimate.options):
        raise HTTPException(status_code=422, detail="Вариант доставки не найден")
    estimate.selected_option_index = option_index
    estimate.selected_at = datetime.now(timezone.utc)
    chosen = estimate.options[option_index]
    record_audit(db, company_id=actor.company_id, actor_user_id=actor.user_id,
        action="transport.delivery_option_selected", entity_type="delivery_estimate",
        entity_id=str(estimate.id), details={"option_index": option_index, "method": chosen["method"],
        "name": chosen["name"], "total": chosen["total"]})
    db.commit()
    return {"id": str(estimate.id), "selected_option_index": option_index,
            "selected_option": chosen, "message": "Вариант доставки сохранён. Заказ перевозчику не отправлен."}
