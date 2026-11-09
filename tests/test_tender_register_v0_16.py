from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas import TenderCreateRequest, TenderUpdateRequest

ROOT = Path(__file__).resolve().parents[1]


def payload(**overrides):
    data = dict(platform="B2B-Center", tender_number="123456", customer_name="ООО Заказчик",
        subject="Поставка промышленного оборудования", initial_price=Decimal("125000.00"),
        deadline=datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc))
    data.update(overrides)
    return data


def test_tender_schema_accepts_rub_and_three_prospectivity_levels():
    for level in ("high", "medium", "low"):
        item = TenderCreateRequest(**payload(prospectivity=level))
        assert item.prospectivity == level
        assert item.initial_price == Decimal("125000.00")


def test_tender_schema_rejects_negative_price_and_unknown_status():
    with pytest.raises(ValidationError):
        TenderCreateRequest(**payload(initial_price=Decimal("-1")))
    with pytest.raises(ValidationError):
        TenderCreateRequest(**payload(status="maybe"))


def test_tender_update_allows_partial_changes():
    item = TenderUpdateRequest(status="analysis", notes="Проверить документацию")
    assert item.model_dump(exclude_unset=True) == {"status": "analysis", "notes": "Проверить документацию"}


def test_tender_migration_enforces_tenant_rls_and_same_company_memberships():
    migration = (ROOT / "migrations/versions/0028_tender_register.py").read_text()
    assert 'down_revision = "0027_auth_session_device_metadata"' in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration and "FORCE ROW LEVEL SECURITY" in migration
    assert "app.tenant_id" in migration
    assert 'memberships.company_id", "memberships.id' in migration
    assert "uq_tender_company_platform_number" in migration


def test_tender_api_scopes_every_lookup_to_current_company_and_audits_changes():
    router = (ROOT / "app/routers/tenders.py").read_text()
    assert "Tender.company_id == actor.company_id" in router
    assert "tender.created" in router and "tender.updated" in router
    assert "responsible_membership_id" in router
    assert "require_roles(*WRITE_ROLES)" in router


def test_tender_router_is_registered_and_version_bumped():
    main = (ROOT / "app/main.py").read_text()
    assert "app.include_router(tenders.router)" in main
    assert 'version="0.25.0-pilot"' in main
