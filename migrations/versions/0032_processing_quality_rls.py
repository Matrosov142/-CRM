"""Force tenant RLS on production and finished-goods tables."""
from alembic import op

revision = "0032_processing_quality_rls"
down_revision = "0031_rfq_tender_position_link"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "processing_jobs",
    "processing_operations",
    "processing_materials",
    "quality_inspections",
    "finished_goods_batches",
)


def upgrade():
    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f"CREATE POLICY {table}_tenant_access ON \"{table}\" "
            "USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade():
    for table in reversed(TENANT_TABLES):
        op.execute(f'DROP POLICY IF EXISTS {table}_tenant_access ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
