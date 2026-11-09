from pathlib import Path
import pytest
from pydantic import ValidationError
from app.models import SupplierRFQLine, TenderPosition
from app.schemas import SupplierRFQLineCreate
from app.routers.suppliers import rfq_router

ROOT = Path(__file__).resolve().parents[1]


def test_rfq_line_accepts_optional_tender_position_pair():
    payload = SupplierRFQLineCreate(item_name="Задвижка", quantity="2", unit="шт.")
    assert payload.tender_id is None and payload.tender_position_id is None
    linked = SupplierRFQLineCreate(
        item_name="Задвижка", quantity="2", unit="шт.",
        tender_id="11111111-1111-4111-8111-111111111111",
        tender_position_id="22222222-2222-4222-8222-222222222222",
    )
    assert linked.tender_id is not None and linked.tender_position_id is not None


def test_rfq_line_rejects_partial_tender_link():
    with pytest.raises(ValidationError):
        SupplierRFQLineCreate(item_name="Задвижка", quantity="2", unit="шт.",
                              tender_position_id="22222222-2222-4222-8222-222222222222")


def test_rfq_line_model_has_same_company_composite_link_and_pair_check():
    table = SupplierRFQLine.__table__
    assert {"tender_id", "tender_position_id"}.issubset(table.columns.keys())
    constraints = {c.name for c in table.constraints}
    assert "fk_rfq_line_tender_position_same_company" in constraints
    assert "ck_rfq_line_tender_link_pair" in constraints
    tender_constraints = {c.name for c in TenderPosition.__table__.constraints}
    assert "uq_tender_position_company_tender_id" in tender_constraints


def test_rfq_detail_returns_tender_position_references():
    source = (ROOT / "app/routers/suppliers.py").read_text()
    assert '"tender_position_id": str(x.tender_position_id) if x.tender_position_id else None' in source
    assert "Позиция тендера не найдена в вашей компании" in source
    assert "Наименование строки запроса не совпадает" in source


def test_migration_adds_composite_fk_and_pair_constraint_with_rls_inherited():
    migration = (ROOT / "migrations/versions/0031_rfq_tender_position_link.py").read_text()
    assert 'down_revision = "0030_tender_pricing_versions"' in migration
    assert '"company_id", "tender_id", "tender_position_id"' in migration
    assert '"company_id", "tender_id", "id"' in migration
    assert "ck_rfq_line_tender_link_pair" in migration
    # Existing supplier_rfq_lines RLS remains enabled; this migration must not weaken it.
    assert "DISABLE ROW LEVEL SECURITY" not in migration


def test_composite_position_target_exists_before_pricing_foreign_key():
    positions = (ROOT / "migrations/versions/0029_tender_positions.py").read_text()
    pricing = (ROOT / "migrations/versions/0030_tender_pricing_versions.py").read_text()
    link = (ROOT / "migrations/versions/0031_rfq_tender_position_link.py").read_text()
    assert 'UniqueConstraint("company_id", "tender_id", "id", name="uq_tender_position_company_tender_id")' in positions
    assert "ALTER TABLE public.tender_positions" in pricing
    assert "uq_tender_position_company_tender_id" in pricing
    assert pricing.index("uq_tender_position_company_tender_id") < pricing.index("op.create_table")
    assert "op.create_unique_constraint" not in link
