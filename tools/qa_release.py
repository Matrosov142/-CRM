#!/usr/bin/env python3
"""Reproducible release QA gate for ПОТОК CRM v0.25.

Offline checks are separated from PostgreSQL integration checks.
A PASS is not a production or legal certification.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HAS_PSYCOPG = importlib.util.find_spec("psycopg") is not None
HAS_PG_URLS = bool(
    os.environ.get("TEST_ADMIN_DATABASE_URL")
    and os.environ.get("TEST_RUNTIME_DATABASE_URL")
)

EXCLUDED: set[str] = set()
if not HAS_PSYCOPG:
    EXCLUDED.update({"test_postgres_rls_integration.py", "test_postgres_rls_matrix.py"})
elif not HAS_PG_URLS:
    EXCLUDED.update({"test_postgres_rls_integration.py", "test_postgres_rls_matrix.py"})


def run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout


python_files = [
    path for path in ROOT.rglob("*.py")
    if not any(part in {"__pycache__", ".venv", ".pytest_cache"} for part in path.parts)
]
compile_rc, compile_out = run(
    [sys.executable, "-m", "compileall", "-q", "app", "migrations", "tests"]
)
audit_rc, audit_out = run([sys.executable, "tools/release_audit.py"])

test_files = sorted(
    str(path.relative_to(ROOT))
    for path in (ROOT / "tests").glob("test_*.py")
    if path.name not in EXCLUDED
)
test_env = os.environ.copy()
# Pure unit tests should not require a PostgreSQL DBAPI driver at import time.
# SQLite is used only to construct SQLAlchemy metadata; no DB schema is created.
test_env["DATABASE_URL"] = "sqlite:////tmp/potok-crm-release-qa.db"
test_env["JWT_SECRET"] = "release-qa-only-secret-not-for-production-000000"
proc = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", *test_files],
    cwd=ROOT, env=test_env, text=True,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
test_rc, test_out = proc.returncode, proc.stdout

FRONTEND_LOCK = (ROOT / "frontend" / "package-lock.json").is_file()
FRONTEND_BUILD = "not run: package-lock.json absent or npm dependencies unavailable"

report = {
    "release": "0.25.0-pilot",
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "python_files": len(python_files),
    "compileall": {"passed": compile_rc == 0, "output": compile_out[-4000:]},
    "static_audit": {"passed": audit_rc == 0, "output": audit_out[-4000:]},
    "selected_tests": {
        "passed": test_rc == 0,
        "files_run": len(test_files),
        "excluded_due_to_environment": sorted(EXCLUDED),
        "output": test_out[-6000:],
    },
    "postgresql_integration": {
        "configured": HAS_PSYCOPG and HAS_PG_URLS,
        "status": (
            "included in pytest run"
            if HAS_PSYCOPG and HAS_PG_URLS
            else "not run: requires psycopg and disposable TEST_ADMIN_DATABASE_URL / TEST_RUNTIME_DATABASE_URL"
        ),
    },
    "frontend": {
        "package_lock_present": FRONTEND_LOCK,
        "production_build": FRONTEND_BUILD,
    },
    "docker_runtime": "not run: Docker CLI/daemon unavailable in build environment",
    "production_ready": False,
}

report_path = ROOT / "docs" / "QA_REPORT_PILOT_0_25.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

print(json.dumps({
    "release": report["release"],
    "python_files": report["python_files"],
    "compileall": report["compileall"]["passed"],
    "static_audit": report["static_audit"]["passed"],
    "selected_tests_passed": report["selected_tests"]["passed"],
    "selected_test_files": report["selected_tests"]["files_run"],
    "excluded": report["selected_tests"]["excluded_due_to_environment"],
    "postgresql_integration": report["postgresql_integration"]["status"],
    "frontend": {
        "package_lock_present": FRONTEND_LOCK,
        "production_build": FRONTEND_BUILD,
    },
    "docker_runtime": "not run: Docker CLI/daemon unavailable in build environment",
    "frontend_lock_present": FRONTEND_LOCK,
    "production_ready": False,
}, ensure_ascii=False, indent=2))

sys.exit(0 if compile_rc == 0 and audit_rc == 0 and test_rc == 0 else 1)
