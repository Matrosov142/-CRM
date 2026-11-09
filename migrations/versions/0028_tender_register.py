"""Add company-isolated manual tender register."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0028_tender_register"
down_revision = "0027_auth_session_device_metadata"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("tenders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("tender_number", sa.String(100), nullable=False),
        sa.Column("customer_name", sa.String(250), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("initial_price", sa.Numeric(14,2), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_region", sa.String(160)),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("prospectivity", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("responsible_membership_id", postgresql.UUID(as_uuid=True)),
        sa.Column("notes", sa.String(4000), nullable=False, server_default=""),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_tender_company_id_id"),
        sa.UniqueConstraint("company_id", "platform", "tender_number", name="uq_tender_company_platform_number"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_tender_creator_same_company"),
        sa.ForeignKeyConstraint(["company_id", "responsible_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_tender_owner_same_company"),
        sa.CheckConstraint("initial_price >= 0", name="ck_tender_initial_price_nonnegative"),
        sa.CheckConstraint("status IN ('new','analysis','preparing','submitted','won','lost','cancelled')", name="ck_tender_status"),
        sa.CheckConstraint("prospectivity IN ('high','medium','low')", name="ck_tender_prospectivity"),
    )
    op.create_index("ix_tenders_company_deadline", "tenders", ["company_id", "deadline"])
    op.execute("ALTER TABLE tenders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenders FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenders_tenant_access ON tenders USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")


def downgrade():
    op.execute("DROP POLICY IF EXISTS tenders_tenant_access ON tenders")
    op.drop_table("tenders")
