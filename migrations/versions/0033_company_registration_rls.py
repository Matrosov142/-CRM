"""Permit only the explicit, transaction-scoped company bootstrap insert."""
from alembic import op

revision = "0033_company_registration_rls"
down_revision = "0032_processing_quality_rls"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE POLICY companies_bootstrap_registration_insert ON companies
        FOR INSERT
        WITH CHECK (
            current_setting('app.bootstrap_registration', true) = 'on'
            AND id = NULLIF(current_setting('app.bootstrap_company_id', true), '')::uuid
        )
    """)


def downgrade():
    op.execute("DROP POLICY IF EXISTS companies_bootstrap_registration_insert ON companies")
