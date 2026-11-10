from pathlib import Path
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas import TenderPositionCreateRequest, TenderPositionUpdateRequest

ROOT = Path(__file__).resolve().parents[1]

def test_position_schema_accepts_fractional_quantity_and_price():
    item = TenderPositionCreateRequest(item_name="Труба стальная", specification="DN100, PN16", quantity=Decimal("12.500"), unit="м", estimated_unit_price=Decimal("1200.00"))
    assert item.quantity == Decimal("12.500")
    assert item.estimated_unit_price == Decimal("1200.00")

def test_position_schema_rejects_nonpositive_quantity_and_negative_price():
    with pytest.raises(ValidationError):
        TenderPositionCreateRequest(item_name="Труба", quantity=Decimal("0"))
    with pytest.raises(ValidationError):
        TenderPositionCreateRequest(item_name="Труба", quantity=Decimal("1"), estimated_unit_price=Decimal("-1"))

def test_position_update_is_partial():
    update = TenderPositionUpdateRequest(quantity=Decimal("3"))
    assert update.model_dump(exclude_unset=True) == {"quantity": Decimal("3")}

def test_tender_position_migration_has_same_company_fk_and_rls():
    migration = (ROOT / "migrations/versions/0029_tender_positions.py").read_text()
    assert 'down_revision = "0028_tender_register"' in migration
    assert '["company_id", "tender_id"]' in migration
    assert '"tenders.company_id", "tenders.id"' in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration and "FORCE ROW LEVEL SECURITY" in migration
    assert "app.tenant_id" in migration

def test_tender_position_routes_scope_every_operation_to_company():
    router = (ROOT / "app/routers/tenders.py").read_text()
    assert '@router.get("/{tender_id}/positions")' in router
    assert '@router.post("/{tender_id}/positions", status_code=201)' in router
    assert '@router.patch("/{tender_id}/positions/{position_id}")' in router
    assert '@router.delete("/{tender_id}/positions/{position_id}", status_code=204)' in router
    assert 'TenderPosition.company_id == actor.company_id' in router
    assert 'tender.position.created' in router and 'tender.position.deleted' in router
