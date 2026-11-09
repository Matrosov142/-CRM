from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def test_shipment_routes_and_guardrails():
    source = (ROOT / "app/routers/warehouse.py").read_text()
    assert '@router.post("/shipments"' in source
    assert '@router.get("/shipments"' in source
    assert 'item.quantity > remaining_reserved' in source
    assert 'batch.quantity_balance = Decimal(batch.quantity_balance) - item.quantity' in source
    assert 'warehouse.shipment_confirmed' in source
def test_migration_has_tenant_rls_and_partial_shipment_counter():
    source = (ROOT / "migrations/versions/0016_warehouse_shipments.py").read_text()
    assert 'quantity_shipped' in source
    assert 'ENABLE ROW LEVEL SECURITY' in source
    assert 'FORCE ROW LEVEL SECURITY' in source
    assert 'down_revision = "0015_stock_reservations"' in source
