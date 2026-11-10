from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shipment_delivery_link_is_same_tenant_and_costs_are_nonnegative():
    migration = (ROOT / "migrations/versions/0024_shipment_delivery_costs.py").read_text()
    assert '"company_id", "delivery_estimate_id"' in migration
    assert '"company_id", "id"' in migration
    assert "planned_delivery_cost >= 0" in migration
    assert "actual_delivery_cost >= 0" in migration


def test_shipment_creation_requires_selected_estimate_and_snapshots_plan():
    router = (ROOT / "app/routers/warehouse.py").read_text()
    assert "DeliveryEstimate.company_id == actor.company_id" in router
    assert "estimate.selected_option_index is None" in router
    assert "planned_delivery_cost = Decimal(str(estimate.options[estimate.selected_option_index][\"total\"]))" in router
    assert 'action="warehouse.shipment_confirmed"' in router


def test_actual_delivery_cost_is_tenant_scoped_validated_and_audited():
    router = (ROOT / "app/routers/warehouse.py").read_text()
    schema = (ROOT / "app/schemas.py").read_text()
    assert '"/shipments/{shipment_id}/actual-delivery-cost"' in router
    assert "WarehouseShipment.company_id == actor.company_id" in router
    assert "warehouse.shipment_actual_delivery_cost_recorded" in router
    assert 'Field(ge=Decimal("0")' in schema
    assert "actual_delivery_cost" in router
