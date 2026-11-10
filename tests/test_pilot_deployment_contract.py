from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_api_runtime_uses_only_runtime_role_and_migrations_are_separate():
    compose = (ROOT / "compose.pilot.yml").read_text()
    migrate = (ROOT / "ops/db-migrate.sh").read_text()
    bootstrap = (ROOT / "ops/db-bootstrap.sh").read_text()
    api_environment = compose.split("  api:", 1)[1].split("  web:", 1)[0]
    assert "DATABASE_URL: postgresql+psycopg://potok_runtime:" in api_environment
    assert "DB_ADMIN_PASSWORD" not in api_environment
    assert "DB_OWNER_PASSWORD" not in api_environment
    assert "MIGRATION_DATABASE_URL" not in api_environment
    assert "MIGRATION_DATABASE_URL" in migrate
    assert "NOSUPERUSER" in bootstrap and "NOBYPASSRLS" in bootstrap
    assert "REVOKE UPDATE, DELETE ON audit_events" in migrate


def test_pilot_web_port_is_loopback_only_and_db_is_not_published():
    compose = (ROOT / "compose.pilot.yml").read_text()
    assert '127.0.0.1:18080:8080' in compose
    assert '5432:' not in compose
    assert '8000:' not in compose
    web = compose.split("  web:", 1)[1].split("volumes:", 1)[0]
    assert "networks: [backend, ingress]" in web
    assert "  backend:\n    internal: true\n  ingress: {}" in compose


def test_pilot_disables_open_registration_and_api_docs():
    compose = (ROOT / "compose.pilot.yml").read_text()
    main = (ROOT / "app/main.py").read_text()
    assert 'ALLOW_BOOTSTRAP_REGISTRATION: "false"' in compose
    assert 'docs_url="/docs" if settings.environment == "development" else None' in main
