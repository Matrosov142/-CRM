from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_receipt_creates_stock_only_from_accepted_quantity():
    source = (ROOT / "app/routers/warehouse.py").read_text()
    assert "if item.accepted_quantity > 0" in source
    assert "quantity_received=item.accepted_quantity" in source
    assert "quantity_balance=item.accepted_quantity" in source
    assert "item.accepted_quantity + item.defective_quantity != item.received_quantity" in source


def test_receipt_is_limited_to_authorized_order_and_company():
    source = (ROOT / "app/routers/warehouse.py").read_text()
    assert "ProcurementOrder.company_id == actor.company_id" in source
    assert 'order.status != "authorized"' in source
    assert "Role.WAREHOUSE" in source


def test_warehouse_tables_have_tenant_rls_and_same_company_constraints():
    migration = (ROOT / "migrations/versions/0014_warehouse_receiving.py").read_text()
    for table in ("warehouse_receipts", "warehouse_receipt_lines", "stock_batches"):
        assert f'"{table}"' in migration
    assert "CREATE POLICY {table}_tenant_access" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration and "FORCE ROW LEVEL SECURITY" in migration
    assert "fk_receipt_order_same_company" in migration
    assert "fk_receipt_line_order_line_same_company" in migration
    assert "fk_stock_batch_receipt_line_same_company" in migration
