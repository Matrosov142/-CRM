from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_first_admin_bootstrap_is_one_time_and_uses_one_shot_admin_service():
    script = (ROOT / "ops/create_first_admin.py").read_text()
    runbook = (ROOT / "docs/PILOT_RUNBOOK_RU.md").read_text()
    assert "if db.scalar(select(func.count()).select_from(User))" in script
    assert "getpass(" in script
    assert "len(password) < 14" in script
    assert 'role="director"' in script
    assert 'os.environ.get("DB_ADMIN_PASSWORD")' in script
    assert "potok_admin" in script
    assert 'os.environ.get("MIGRATION_DATABASE_URL")' not in script
    assert "run --rm --no-deps" in runbook
    assert "--entrypoint python" in runbook
    assert "db-bootstrap -m ops.create_first_admin" in runbook


def test_api_runtime_container_does_not_receive_database_owner_secrets():
    compose = (ROOT / "compose.pilot.yml").read_text()
    entry = (ROOT / "ops/container-entrypoint.sh").read_text()
    api_environment = compose.split("  api:", 1)[1].split("  web:", 1)[0]
    assert "DB_ADMIN_PASSWORD" not in api_environment
    assert "DB_OWNER_PASSWORD" not in api_environment
    assert "MIGRATION_DATABASE_URL" not in api_environment
    assert "exec uvicorn" in entry
