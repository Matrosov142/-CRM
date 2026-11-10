"""Allow company directors to manage memberships within their tenant."""
from alembic import op

revision = "0006_director_membership"
down_revision = "0005_employee_invitations"
branch_labels = None
depends_on = None


def upgrade():
    # The table owner is the migration role, never the application runtime role.
    # NO FORCE lets the SECURITY DEFINER helper read the complete membership set.
    op.execute("ALTER TABLE memberships NO FORCE ROW LEVEL SECURITY")
    op.execute("""
      CREATE OR REPLACE FUNCTION app_is_company_director(target_company_id uuid)
      RETURNS boolean
      LANGUAGE sql
      STABLE
      SECURITY DEFINER
      SET search_path = pg_catalog, public
      SET row_security = off
      AS $$
        SELECT EXISTS (
          SELECT 1
          FROM public.memberships m
          WHERE m.company_id = target_company_id
            AND m.user_id = NULLIF(current_setting('app.user_id', true), '')::uuid
            AND m.status = 'active'
            AND m.role = 'director'
        )
      $$
    """)
    op.execute("""
      CREATE POLICY memberships_director_manage ON memberships
      FOR ALL
      USING (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND app_is_company_director(company_id)
      )
      WITH CHECK (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND app_is_company_director(company_id)
      )
    """)


def downgrade():
    op.execute("DROP POLICY IF EXISTS memberships_director_manage ON memberships")
    op.execute("DROP FUNCTION IF EXISTS app_is_company_director(uuid)")
    op.execute("ALTER TABLE memberships FORCE ROW LEVEL SECURITY")
