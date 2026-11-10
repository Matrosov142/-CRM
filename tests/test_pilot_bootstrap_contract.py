from pathlib import Path
from ops.create_first_admin import normalize_email

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


def test_one_shot_bootstrap_has_database_and_jwt_settings_for_first_admin_command():
    compose = (ROOT / "compose.pilot.yml").read_text()
    bootstrap_service = compose.split("  db-bootstrap:", 1)[1].split("  db-migrate:", 1)[0]
    api_environment = compose.split("  api:", 1)[1].split("  web:", 1)[0]
    assert "DATABASE_URL: postgresql+psycopg://potok_admin:${DB_ADMIN_PASSWORD}@db:5432/potok_crm" in bootstrap_service
    assert "JWT_SECRET: ${JWT_SECRET:?Create .env.pilot first}" in bootstrap_service
    assert "DATABASE_URL: postgresql+psycopg://potok_admin" not in api_environment


def test_local_pilot_allows_only_its_same_origin_for_browser_sessions():
    compose = (ROOT / "compose.pilot.yml").read_text()
    api_environment = compose.split("  api:", 1)[1].split("  web:", 1)[0]
    assert "CORS_ORIGINS: ${CORS_ORIGINS:-http://127.0.0.1:18080}" in api_environment


def test_bootstrap_email_validation_matches_application_email_schema():
    assert normalize_email("Local-Pilot@example.com") == "local-pilot@example.com"
    assert normalize_email("local-pilot@example.test") is None
