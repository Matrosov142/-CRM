#!/usr/bin/env python3
"""Offline release audit. Static checks only; never connects to a database/server."""
from __future__ import annotations
import ast, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors: list[str] = []
notes: list[str] = []

# Canonical QA evidence is consumed by CI and release automation on Linux.
qa_report_path = ROOT / 'docs' / 'QA_REPORT_PILOT_0_25.json'
try:
    json.loads(qa_report_path.read_text(encoding='utf-8'))
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    errors.append(f'QA report must be valid UTF-8 JSON: {exc}')

# 1. Python syntax
py_files = sorted(p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ('__pycache__', '.venv')))
for p in py_files:
    try:
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    except SyntaxError as exc:
        errors.append(f'Syntax error {p.relative_to(ROOT)}:{exc.lineno}: {exc.msg}')

# 2. Alembic revision graph: one root, no duplicate IDs, no missing parents, no branches.
versions = ROOT / 'migrations' / 'versions'
revisions: dict[str, str | None] = {}
for p in versions.glob('*.py'):
    if p.name.startswith('__'):
        continue
    tree = ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {'revision', 'down_revision'}:
                    try: values[target.id] = ast.literal_eval(node.value)
                    except Exception: pass
    rev = values.get('revision')
    down = values.get('down_revision')
    if not isinstance(rev, str):
        errors.append(f'Migration has no literal revision: {p.name}')
        continue
    if rev in revisions:
        errors.append(f'Duplicate migration revision: {rev}')
    revisions[rev] = down if isinstance(down, str) else None
roots = [r for r, d in revisions.items() if d is None]
if len(roots) != 1:
    errors.append(f'Expected one migration root, found {len(roots)}')
for rev, parent in revisions.items():
    if parent is not None and parent not in revisions:
        errors.append(f'Missing migration parent: {rev} -> {parent}')
children: dict[str, int] = {r: 0 for r in revisions}
for parent in revisions.values():
    if parent in children: children[parent] += 1
branches = [r for r, count in children.items() if count > 1]
if branches:
    errors.append('Migration graph branches: ' + ', '.join(sorted(branches)))

# 3. App version and API route registration must agree with release.
main_path = ROOT / 'app' / 'main.py'
main = main_path.read_text(encoding='utf-8')
version_match = re.search(r'version\s*=\s*[\'\"]([^\'\"]+)', main)
if not version_match:
    errors.append('FastAPI version declaration missing')
else:
    app_version = version_match.group(1)
    if app_version != '0.25.0-pilot':
        errors.append(f'FastAPI version is {app_version}, expected 0.25.0-pilot')
for router in ('auth', 'companies', 'procurement', 'suppliers', 'warehouse', 'finance', 'finance_obligations', 'counterparties', 'documents', 'tenders'):
    if f'app.include_router({router}.router)' not in main:
        errors.append(f'Expected router not mounted: {router}')

# Supplier RFQ lines may reference a tender position only within the same tenant.
models_source = (ROOT / 'app' / 'models.py').read_text(encoding='utf-8')
for model_name in ('ProcessingJob', 'ProcessingOperation', 'ProcessingMaterial'):
    if f'class {model_name}(Base)' not in models_source:
        errors.append(f'{model_name} ORM model missing from shared metadata.')
supplier_source = (ROOT / 'app' / 'routers' / 'suppliers.py').read_text(encoding='utf-8')
if 'fk_rfq_line_tender_position_same_company' not in models_source:
    errors.append('RFQ line tender-position link must enforce same-company composite FK.')
if 'ck_rfq_line_tender_link_pair' not in models_source:
    errors.append('RFQ line tender link must require tender and position IDs together.')
if 'Позиция тендера не найдена в вашей компании' not in supplier_source:
    errors.append('RFQ creation must validate linked tender position in current tenant.')

# 4. Dashboard indicators must be tenant-scoped database counts, never demo values.
package_json = (ROOT / 'frontend' / 'package.json').read_text(encoding='utf-8')
if '"version": "0.25.0"' not in package_json:
    errors.append('Frontend package version must match release 0.25.0.')
if '"@types/react": "18.3.18"' not in package_json or '"@types/react-dom": "18.3.5"' not in package_json:
    errors.append('Pinned React type dependencies are missing.')
frontend_app = (ROOT / 'frontend' / 'src' / 'App.tsx').read_text(encoding='utf-8')
if "import type { FormEvent } from 'react'" not in frontend_app or "React.FormEvent" in frontend_app:
    errors.append('React form event types must be imported explicitly.')
frontend = (ROOT / 'frontend' / 'src' / 'App.tsx').read_text(encoding='utf-8')
for phrase in ('ПИЛОТ 0.25', '/api/v1/dashboard/summary'):
    if phrase not in frontend:
        errors.append(f'Pilot UI contract missing: {phrase}')
if 'const demo =' in frontend or 'Просроченные задачи' in frontend:
    errors.append('Dashboard must not show hard-coded KPI values or unsupported task metrics.')
if '/api/v1/users/me' not in frontend or "ROLE_LABELS[currentUser?.role || '']" not in frontend:
    errors.append('Browser header must display the authenticated user role, not a fixed director role.')
dashboard_source = (ROOT / 'app' / 'routers' / 'dashboard.py').read_text(encoding='utf-8')
for required in ('model.company_id == company_id', 'Tender.status.in_', 'ApprovalRequest.status == "pending"', 'StockReservation.status == "active"'):
    if required not in dashboard_source:
        errors.append(f'Dashboard summary tenant/status contract missing: {required}')
if 'localStorage' in frontend or 'sessionStorage' in frontend:
    errors.append('Bearer token must not be persisted in browser storage.')
if "/api/v1/auth/session/login" not in frontend or "credentials: 'include'" not in frontend:
    errors.append('Browser login must use the HttpOnly cookie session endpoint.')
if 'potok_session' not in (ROOT / 'app' / 'routers' / 'auth.py').read_text(encoding='utf-8'):
    errors.append('HttpOnly browser session cookie is not configured.')
auth_source = (ROOT / 'app' / 'routers' / 'auth.py').read_text(encoding='utf-8')
dep_source = (ROOT / 'app' / 'dependencies.py').read_text(encoding='utf-8')
if 'httponly=True' not in auth_source or 'samesite="strict"' not in auth_source:
    errors.append('Session cookie must be HttpOnly and SameSite=Strict.')
if 'X-CSRF-Token' not in dep_source or 'compare_digest' not in dep_source:
    errors.append('Cookie-authenticated mutations must enforce CSRF token comparison.')
if 'not origin or origin not in settings.allowed_origins' not in dep_source:
    errors.append('Cookie-authenticated mutations must require an allowlisted Origin.')
if '_validate_browser_origin(request)' not in auth_source:
    errors.append('Browser login/register/logout must validate the Origin allowlist.')
if '_create_browser_session' not in auth_source or 'AuthSession' not in dep_source:
    errors.append('Browser sessions must be registered and validated server-side.')
if 'enforce_login_throttle' not in auth_source or 'record_login_failure' not in auth_source:
    errors.append('Login endpoints must enforce persistent login throttling.')
if 'email_hash' not in (ROOT / 'app' / 'models.py').read_text(encoding='utf-8') or 'ip_hash' not in (ROOT / 'app' / 'models.py').read_text(encoding='utf-8'):
    errors.append('Login failure storage must use keyed identifier digests.')
if '/session/logout-all' not in auth_source or 'logoutAll' not in frontend:
    errors.append('Logout-all session revocation must be available in the browser UI.')
if "useState('cookie-session')" not in frontend:
    errors.append('Browser UI must attempt cookie-session restoration after page reload.')
if 'setDeliveryEstimateId(data.id)' not in frontend:
    errors.append('Delivery estimate response ID is not retained for later selection.')
if 'actual-delivery-cost' not in frontend or 'loadShipments' not in frontend:
    errors.append('Shipment actual delivery cost screen is missing.')

# Logout UI must only clear local authenticated state after server-confirmed revocation.
logout_block = frontend[frontend.find('  async function logout()'):frontend.find('  if (token) {')]
if 'if (!response.ok)' not in logout_block or "setToken('')" not in logout_block:
    errors.append('Logout UI must validate server response before clearing local session state.')
if 'finally { setToken' in logout_block:
    errors.append('Logout UI must not clear local session state in finally after a failed revocation.')

# Browser session inventory and individual revocation.
# Keep every release gate BEFORE the final result/exit; checks after sys.exit are unreachable.
if '/session/sessions' not in auth_source or 'revoke_browser_session' not in auth_source:
    errors.append('Browser session inventory and individual revocation must be available.')
if 'loadBrowserSessions' not in frontend or 'revokeBrowserSession' not in frontend:
    errors.append('Browser session management must be exposed in the UI.')
if 'ПИЛОТ 0.25' not in frontend:
    errors.append('Pilot UI banner must match release 0.25.')
positions = (ROOT / 'app' / 'routers' / 'tenders.py').read_text(encoding='utf-8')
for route in ('/{tender_id}/positions', '/{tender_id}/positions/{position_id}'):
    if route not in positions:
        errors.append(f'Tender position route missing: {route}')
if 'class TenderPosition(Base)' not in (ROOT / 'app' / 'models.py').read_text(encoding='utf-8'):
    errors.append('TenderPosition model missing.')
pricing = (ROOT / 'app' / 'tender_pricing.py').read_text(encoding='utf-8')
if 'calculate_tender_position_pricing' not in pricing:
    errors.append('Tender position pricing calculator is missing.')
if '/{tender_id}/positions/{position_id}/pricing-preview' not in positions:
    errors.append('Tender position pricing preview API route is missing.')
if 'calculatePositionPricing' not in frontend or 'pricing-preview' not in frontend:
    errors.append('Tender position pricing calculator UI is missing.')

# Persisted pricing-version gates must execute before the final result/exit.
pricing_model = (ROOT / 'app' / 'models.py').read_text(encoding='utf-8')
if 'class TenderPositionPricingVersion(Base)' not in pricing_model:
    errors.append('Immutable tender pricing version model is missing.')
if '/{tender_id}/positions/{position_id}/pricing-calculations' not in positions:
    errors.append('Persisted tender pricing calculation API routes are missing.')
if 'savePositionPricing' not in frontend or 'pricing-calculations' not in frontend:
    errors.append('Persisted tender pricing calculation UI is missing.')

print(f'Python files syntax-checked: {len(py_files)}')
print(f'Alembic revisions: {len(revisions)}; roots: {len(roots)}; branches: {len(branches)}')
print(f'FastAPI version: {version_match.group(1) if version_match else "MISSING"}')
for note in notes: print('[ACTION REQUIRED]', note)
for error in errors: print('[FAIL]', error)
if errors:
    print('RESULT: FAIL')
    sys.exit(1)
print('RESULT: PASS — static release audit only; no runtime, database, RLS or security penetration tests performed.')
