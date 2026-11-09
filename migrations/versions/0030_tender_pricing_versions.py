"""Persist immutable tender position pricing calculation versions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0030_tender_pricing_versions"
down_revision = "0029_tender_positions"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("tender_position_pricing_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_tender_pricing_company_id_id"),
        sa.UniqueConstraint("company_id", "position_id", "version", name="uq_tender_pricing_position_version"),
        sa.ForeignKeyConstraint(["company_id", "tender_id", "position_id"],
            ["tender_positions.company_id", "tender_positions.tender_id", "tender_positions.id"],
            ondelete="CASCADE", name="fk_tender_pricing_same_company_position"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"],
            ["memberships.company_id", "memberships.id"], ondelete="RESTRICT",
            name="fk_tender_pricing_creator_same_company"),
        sa.CheckConstraint("version > 0", name="ck_tender_pricing_version_positive"),
    )
    op.create_index("ix_tender_pricing_company_id", "tender_position_pricing_versions", ["company_id"])
    op.create_index("ix_tender_pricing_tender_id", "tender_position_pricing_versions", ["tender_id"])
    op.create_index("ix_tender_pricing_position_id", "tender_position_pricing_versions", ["position_id"])
    op.execute("ALTER TABLE tender_position_pricing_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tender_position_pricing_versions FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tender_pricing_tenant_access ON tender_position_pricing_versions USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_tender_pricing_version_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'tender pricing versions are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_tender_pricing_versions_immutable
        BEFORE UPDATE OR DELETE ON tender_position_pricing_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_tender_pricing_version_mutation()
    """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_tender_pricing_versions_immutable ON tender_position_pricing_versions")
    op.execute("DROP FUNCTION IF EXISTS prevent_tender_pricing_version_mutation()")
    op.execute("DROP POLICY IF EXISTS tender_pricing_tenant_access ON tender_position_pricing_versions")
    op.drop_table("tender_position_pricing_versions")
