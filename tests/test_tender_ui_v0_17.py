from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tender_register_is_connected_to_real_api_and_company_list():
    ui = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "setSection('tenders');loadTenders()" in ui
    assert "fetch(`${API}/api/v1/tenders`" in ui
    assert "fetch(`${API}/api/v1/tenders`, {method:'POST'" in ui
    assert "credentials:'include'" in ui
    assert "...csrfHeaders()" in ui
    assert "Тендеры компании" in ui
    assert "/api/v1/dashboard/summary" in ui
    assert "Демонстрационные данные" not in ui
    assert "/api/v1/users/me" in ui
    assert "ROLE_LABELS[currentUser?.role || '']" in ui


def test_tender_router_handles_unique_constraint_race_and_blank_values():
    router = (ROOT / "app/routers/tenders.py").read_text(encoding="utf-8")
    assert "from sqlalchemy.exc import IntegrityError" in router
    assert router.count("except IntegrityError:") == 3
    assert "if not platform or not number or not customer or not subject:" in router
    assert "db.rollback()" in router


def test_release_versions_are_synchronized():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    pkg = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
    audit = (ROOT / "tools/release_audit.py").read_text(encoding="utf-8")
    assert 'version="0.25.0-pilot"' in main
    assert '"version": "0.25.0"' in pkg
    assert "0.25.0-pilot" in audit
