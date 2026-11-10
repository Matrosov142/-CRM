from pathlib import Path

from app.models import TenderPositionPricingVersion
from app.routers.tenders import router

ROOT = Path(__file__).resolve().parents[1]


def test_pricing_version_model_has_tenant_and_immutable_snapshot_fields():
    table = TenderPositionPricingVersion.__table__
    assert {"company_id", "tender_id", "position_id", "version", "inputs", "result",
            "created_by_membership_id", "created_at"}.issubset(table.columns.keys())
    constraints = {c.name for c in table.constraints}
    assert "uq_tender_pricing_position_version" in constraints
    assert "fk_tender_pricing_same_company_position" in constraints
    assert "fk_tender_pricing_creator_same_company" in constraints


def test_pricing_version_api_exposes_save_and_history_routes():
    paths = {route.path for route in router.routes}
    route = "/api/v1/tenders/{tender_id}/positions/{position_id}/pricing-calculations"
    assert route in paths
    assert any(r.path == route and "POST" in r.methods for r in router.routes)
    assert any(r.path == route and "GET" in r.methods for r in router.routes)


def test_pricing_version_migration_enforces_rls_and_unique_versions():
    migration = (ROOT / "migrations/versions/0030_tender_pricing_versions.py").read_text()
    assert 'down_revision = "0029_tender_positions"' in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "trg_tender_pricing_versions_immutable" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "uq_tender_pricing_position_version" in migration


def test_frontend_saves_and_displays_pricing_versions():
    frontend = (ROOT / "frontend/src/App.tsx").read_text()
    assert "savePositionPricing" in frontend
    assert "pricing-calculations" in frontend
    assert "История расчётов" in frontend
    assert "Сохранить версию расчёта" in frontend


def test_position_with_pricing_history_cannot_be_deleted_silently():
    router_source = (ROOT / "app/routers/tenders.py").read_text()
    assert "has_pricing_history" in router_source
    assert "Нельзя удалить позицию: по ней сохранена история расчётов" in router_source
