from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_has_dependency_audits_and_preserves_backend_evidence():
    workflow = (ROOT / ".github/workflows/release-gate.yml").read_text()
    assert "pip-audit -r requirements.txt" in workflow
    assert "npm audit --audit-level=high" in workflow
    assert "tee docs/CI_QA_LOG.txt" in workflow
    assert "set -o pipefail" in workflow
    assert "actions/upload-artifact@v4" in workflow


def test_ci_performs_a_real_backup_restore_drill():
    workflow = (ROOT / ".github/workflows/release-gate.yml").read_text()
    assert "ops/backup-pilot.sh" in workflow
    assert "sha256sum -c SHA256SUMS" in workflow
    assert "pg_restore --exit-on-error" in workflow
    assert "potok_restore_test" in workflow
    assert "rc1-backup-ok" in workflow
    assert "0032_processing_quality_rls" in workflow
    assert 'test -s "$BACKUP_PATH/database.dump"' in workflow
    assert "SELECT version_num FROM alembic_version" in workflow


def test_docker_build_contexts_exclude_secrets_and_local_artifacts():
    root_ignore = (ROOT / ".dockerignore").read_text()
    web_ignore = (ROOT / "frontend/.dockerignore").read_text()
    assert ".env.*" in root_ignore and ".env.*" in web_ignore
    assert "backups" in root_ignore
    assert "node_modules" in web_ignore
    assert "dist" in web_ignore


def test_gitignore_has_real_patterns_not_escaped_literal_newlines():
    gitignore = (ROOT / ".gitignore").read_text()
    assert "\\\\n" not in gitignore
    assert ".env.pilot" in gitignore or ".env.*" in gitignore
    assert "backups/" in gitignore


def test_backup_script_archives_document_root_and_runtime_has_tar():
    backup = (ROOT / "ops/backup-pilot.sh").read_text()
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "tar -czf - -C /var/lib/potok-crm documents" in backup
    assert "postgresql-client tar" in dockerfile


def test_database_owner_is_not_the_bootstrap_superuser():
    compose = (ROOT / "compose.pilot.yml").read_text()
    bootstrap = (ROOT / "ops/db-bootstrap.sh").read_text()
    migrate = (ROOT / "ops/db-migrate.sh").read_text()
    generator = (ROOT / "ops/pilot-up.sh").read_text()
    assert "POSTGRES_USER: potok_admin" in compose
    assert "DB_ADMIN_PASSWORD" in compose
    assert "db-bootstrap:" in compose and "db-migrate:" in compose
    assert "CREATE ROLE potok_owner" in bootstrap
    assert "NOSUPERUSER" in bootstrap and "NOBYPASSRLS" in bootstrap
    assert "MIGRATION_DATABASE_URL" in migrate
    api_environment = compose.split("  api:", 1)[1].split("  web:", 1)[0]
    assert "DB_ADMIN_PASSWORD" not in api_environment
    assert "DB_OWNER_PASSWORD" not in api_environment
    migration_environment = compose.split("  db-migrate:", 1)[1].split("  api:", 1)[0]
    assert "DB_ADMIN_PASSWORD" not in migration_environment
    assert "RUNTIME_DB_PASSWORD" not in migration_environment
    assert "DB_ADMIN_PASSWORD" in generator
    assert "rm -f db-bootstrap db-migrate" in generator


def test_compose_ci_verifies_owner_and_runtime_roles():
    workflow = (ROOT / ".github/workflows/release-gate.yml").read_text()
    assert "Verify PostgreSQL role separation" in workflow
    assert "false|false|false|false" in workflow
    assert "OWNER_TABLES" in workflow
    assert "API_ENV_NAMES" in workflow
    assert "DB_OWNER_PASSWORD|MIGRATION_DATABASE_URL" in workflow


def test_bootstrap_admin_secret_is_only_passed_to_one_shot_command():
    compose = (ROOT / "compose.pilot.yml").read_text()
    runbook = (ROOT / "docs/PILOT_RUNBOOK_RU.md").read_text()
    bootstrap_service = compose.split("  db-bootstrap:", 1)[1].split("  db-migrate:", 1)[0]
    api_environment = compose.split("  api:", 1)[1].split("  web:", 1)[0]
    assert "DB_ADMIN_PASSWORD" in bootstrap_service
    assert "DB_ADMIN_PASSWORD" not in api_environment
    assert "run --rm --no-deps" in runbook
    assert "--entrypoint python" in runbook
    assert "db-bootstrap -m ops.create_first_admin" in runbook


def test_pilot_secret_file_writer_uses_real_newlines_and_restrictive_permissions():
    script = (ROOT / "ops/pilot-up.sh").read_text()
    assert r"printf 'DB_ADMIN_PASSWORD=%s\\n'" not in script
    assert r"printf 'DB_ADMIN_PASSWORD=%s\n'" in script
    assert 'chmod 600 "$ENV_FILE"' in script


def test_completed_secret_bearing_jobs_are_removed_after_startup():
    compose = (ROOT / "compose.pilot.yml").read_text()
    launcher = (ROOT / "ops/pilot-up.sh").read_text()
    workflow = (ROOT / ".github/workflows/release-gate.yml").read_text()
    assert "db-bootstrap:" in compose and "db-migrate:" in compose
    assert "rm -f db-bootstrap db-migrate" in launcher
    assert "rm -f db-bootstrap db-migrate" in workflow
