from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_are_synchronized():
    main = (ROOT / "app/main.py").read_text()
    audit = (ROOT / "tools/release_audit.py").read_text()
    runner = (ROOT / "tools/qa_release.py").read_text()
    assert 'version="0.25.0-pilot"' in main
    assert "expected 0.25.0-pilot" in audit
    assert '"release": "0.25.0-pilot"' in runner


def test_qa_runner_runs_unit_tests_without_postgres_driver_and_gates_rls_tests():
    runner = (ROOT / "tools/qa_release.py").read_text()
    assert 'test_operation_controls.py' not in runner
    assert 'test_postgres_rls_integration.py' in runner
    assert 'HAS_PSYCOPG' in runner and 'HAS_PG_URLS' in runner
    assert 'test_env["DATABASE_URL"] = "sqlite:///' in runner


def test_postgres_ci_uses_separate_non_bypass_runtime_role():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "NOBYPASSRLS" in workflow
    assert "alembic upgrade head" in workflow
    assert "python -m pytest -q" in workflow


def test_release_audit_runs_browser_session_gates_before_final_result():
    audit = (ROOT / "tools/release_audit.py").read_text()
    session_gate = audit.index("Browser session inventory and individual revocation.")
    final_result = audit.index("print('RESULT: PASS")
    assert session_gate < final_result
    assert "loadBrowserSessions" in audit
    assert "revokeBrowserSession" in audit
    assert "ПИЛОТ 0.25" in audit
