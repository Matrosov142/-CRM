from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_postgres_ci_workflow_runs_migrations_and_rls_tests():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "postgres:16" in workflow
    assert "alembic upgrade head" in workflow
    assert "python -m pytest -q" in workflow
    assert "NOBYPASSRLS" in workflow
    assert "REVOKE UPDATE, DELETE ON audit_events" in workflow


def test_local_postgres_qa_is_loopback_bound_and_disposable():
    compose = (ROOT / "compose.postgres-test.yml").read_text()
    runner = (ROOT / "tools/run_postgres_qa.sh").read_text()
    assert "127.0.0.1:55432:5432" in compose
    assert "down -v" in runner
    assert "alembic upgrade head" in runner
