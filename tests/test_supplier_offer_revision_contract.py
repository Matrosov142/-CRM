from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_supplier_offer_model_has_version_chain_and_current_flag():
    source = (ROOT / "app/models.py").read_text()
    assert '"version_no"' in source or '"version_no"' in source
    assert "supersedes_offer_id" in source
    assert "is_current" in source
    assert "uq_supplier_offer_version" in source


def test_revision_endpoint_keeps_history_and_requires_re_review():
    source = (ROOT / "app/routers/suppliers.py").read_text()
    assert '/offers/{offer_id}/revisions' in source
    assert 'previous.is_current = False' in source
    assert 'review_status="pending"' in source
    assert 'supersedes_offer_id=previous.id' in source
    assert 'SupplierOffer.is_current.is_(True)' in source


def test_revision_migration_is_tenant_scoped_and_reversible():
    source = (ROOT / "migrations/versions/0012_supplier_offer_revisions.py").read_text()
    assert 'fk_supplier_offer_supersedes_same_company' in source
    assert 'uq_supplier_offer_version' in source
    assert 'def downgrade()' in source
