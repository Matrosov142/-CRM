from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_rfq_draft_conversion_requires_complete_manual_selection():
    source = (ROOT / "app/routers/suppliers.py").read_text()
    assert 'create-procurement-drafts' in source
    assert 'Сначала вручную выберите поставщика по каждой позиции запроса' in source
    assert 'SupplierOffer.review_status == "confirmed"' in source
    assert 'SupplierOffer.is_current.is_(True)' in source
    assert 'offer_line.specification_match != "match"' in source


def test_generated_orders_are_drafts_and_not_sent():
    source = (ROOT / "app/routers/suppliers.py").read_text()
    assert 'status="draft"' in source
    assert 'procurement.draft_created_from_rfq' in source
    assert 'не согласованы и не отправлены поставщикам' in source


def test_order_source_link_is_tenant_scoped_and_idempotent():
    model = (ROOT / "app/models.py").read_text()
    migration = (ROOT / "migrations/versions/0013_procurement_from_rfq.py").read_text()
    assert 'uq_procurement_order_rfq_supplier' in model
    assert 'fk_procurement_source_rfq_same_company' in migration
    assert 'fk_procurement_source_supplier_same_company' in migration
