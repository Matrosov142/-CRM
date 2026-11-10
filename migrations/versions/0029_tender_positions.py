"""Add tenant-safe tender positions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0029_tender_positions"
down_revision = "0028_tender_register"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("tender_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(300), nullable=False),
        sa.Column("specification", sa.String(2000), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False, server_default="шт."),
        sa.Column("estimated_unit_price", sa.Numeric(14,2)),
        sa.Column("notes", sa.String(1000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_tender_position_company_id_id"),
        sa.UniqueConstraint("company_id", "tender_id", "id", name="uq_tender_position_company_tender_id"),
        sa.UniqueConstraint("company_id", "tender_id", "line_number", name="uq_tender_position_line"),
        sa.ForeignKeyConstraint(["company_id", "tender_id"], ["tenders.company_id", "tenders.id"], ondelete="CASCADE", name="fk_tender_position_same_company"),
        sa.CheckConstraint("quantity > 0", name="ck_tender_position_quantity_positive"),
        sa.CheckConstraint("estimated_unit_price IS NULL OR estimated_unit_price >= 0", name="ck_tender_position_price_nonnegative"),
    )
    op.create_index("ix_tender_positions_company_tender", "tender_positions", ["company_id", "tender_id"])
    op.execute("ALTER TABLE tender_positions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tender_positions FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tender_positions_tenant_access ON tender_positions USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")


def downgrade():
    op.execute("DROP POLICY IF EXISTS tender_positions_tenant_access ON tender_positions")
    op.drop_table("tender_positions")
