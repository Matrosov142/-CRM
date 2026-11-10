from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_workflow_covers_postgres_frontend_docker_and_restore_gates():
    workflow = (ROOT / ".github/workflows/release-gate.yml").read_text()
    for required in (
        "postgres:16",
        "alembic upgrade head",
        "TEST_ADMIN_DATABASE_URL",
        "TEST_RUNTIME_DATABASE_URL",
        "npm ci",
        "npm run build",
        "docker compose --env-file .env.pilot -f compose.pilot.yml up -d --build",
        "curl -fsS http://127.0.0.1:18080/api/v1/health/ready",
        "curl -fsS http://127.0.0.1:18080/healthz",
        "ops/backup-pilot.sh",
        "pg_restore --exit-on-error",
        "docker compose --env-file .env.pilot -f compose.pilot.yml down -v",
    ):
        assert required in workflow
    assert workflow.count("alembic upgrade head") >= 2


def test_frontend_image_uses_lockfile_and_valid_nginx_build_context():
    dockerfile = (ROOT / "frontend/Dockerfile").read_text()
    assert "COPY package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert (ROOT / "frontend/ops/nginx.conf").is_file()


def test_pilot_compose_build_contexts_match_dockerfiles():
    compose = (ROOT / "compose.pilot.yml").read_text()
    assert sum(line.strip() == "context: ." for line in compose.splitlines()) == 3
    assert compose.count("context: ./frontend") == 1
    assert compose.count("dockerfile: Dockerfile") == 4
    assert "db-bootstrap:" in compose and "db-migrate:" in compose
    assert "service_completed_successfully" in compose
    assert (ROOT / "Dockerfile").is_file()
    assert (ROOT / "frontend/Dockerfile").is_file()


def test_release_plan_keeps_production_gate_closed_until_evidence_exists():
    plan = (ROOT / "docs/RELEASE_RC1_PLAN_RU.md").read_text()
    manifest = (ROOT / "RELEASE_MANIFEST.json").read_text()
    assert "NO-GO" in plan
    assert '"production_ready": false' in manifest
    assert "backup/restore" in plan.lower()


def test_postgres_rls_matrix_is_part_of_release_qa():
    runner = (ROOT / "tools/qa_release.py").read_text()
    matrix = (ROOT / "tests/test_postgres_rls_matrix.py").read_text()
    assert "test_postgres_rls_matrix.py" in runner
    assert "relforcerowsecurity" in matrix
    assert "app.tenant_id" in matrix
