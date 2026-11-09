"""Enable tenant isolation for core tenant tables.

The application DB role MUST NOT own these tables and MUST NOT have BYPASSRLS.
The migration role should own schema objects; runtime role is separate.
"""
from alembic import op

revision = "0003_tenant_rls"
down_revision = "0002_membership_role"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION app_current_user_id()
        RETURNS uuid
        LANGUAGE sql STABLE
        AS $$
          SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
        $$;
    """)
    op.execute("ALTER TABLE memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY memberships_self_access ON memberships
        USING (user_id = app_current_user_id())
        WITH CHECK (user_id = app_current_user_id())
    """)
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE companies FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY companies_member_access ON companies
        USING (EXISTS (
            SELECT 1 FROM memberships m
            WHERE m.company_id = companies.id
              AND m.user_id = app_current_user_id()
              AND m.status = 'active'
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM memberships m
            WHERE m.company_id = companies.id
              AND m.user_id = app_current_user_id()
              AND m.status = 'active'
        ))
    """)

def downgrade():
    op.execute("DROP POLICY IF EXISTS companies_member_access ON companies")
    op.execute("ALTER TABLE companies DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS memberships_self_access ON memberships")
    op.execute("ALTER TABLE memberships DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS app_current_user_id()")
