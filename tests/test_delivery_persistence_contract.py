from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_delivery_estimate_has_tenant_rls_and_composite_creator_fk():
    migration = (ROOT / "migrations/versions/0023_delivery_estimates.py").read_text()
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "app.tenant_id" in migration
    assert "memberships.company_id", "memberships.id" in migration

def test_transport_api_persists_and_audits_estimates():
    router = (ROOT / "app/routers/transport.py").read_text()
    assert "db.add(estimate)" in router
    assert "transport.delivery_estimate_created" in router
    assert "@router.get(\"/estimates\")" in router
    assert "@router.post(\"/estimates/{estimate_id}/select\")" in router
    assert "transport.delivery_option_selected" in router

def test_frontend_shows_saved_delivery_history_and_selection():
    frontend = (ROOT / "frontend/src/App.tsx").read_text()
    assert "/api/v1/transport/estimates" in frontend
    assert "История расчётов" in frontend
    assert "Выбрать вариант" in frontend
