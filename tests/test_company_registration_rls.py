from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_browser_registration_sets_a_transaction_local_company_id_before_insert():
    source = (ROOT / "app/routers/auth.py").read_text()
    assert "set_config('app.bootstrap_registration', 'on', true)" in source
    assert "set_config('app.bootstrap_company_id', :company_id, true)" in source
    assert source.index("set_config('app.bootstrap_company_id'") < source.index("company = Company(id=company_id")
    assert "set_tenant_context(db, user.id, company.id)" in source


def test_registration_policy_is_insert_only_and_bound_to_selected_uuid():
    migration = (ROOT / "migrations/versions/0033_company_registration_rls.py").read_text()
    assert "FOR INSERT" in migration
    assert "current_setting('app.bootstrap_registration', true) = 'on'" in migration
    assert "id = NULLIF(current_setting('app.bootstrap_company_id', true), '')::uuid" in migration
    assert "FOR UPDATE" not in migration and "FOR SELECT" not in migration
