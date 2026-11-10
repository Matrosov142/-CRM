"""Supplier procurement orders and lines with tenant RLS."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_procurement_orders"
down_revision = "0008_approval_consumption"
branch_labels = None
depends_on = None


def _tenant_policy(table):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
      CREATE POLICY {table}_tenant_access ON {table}
      USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def upgrade():
    # Composite keys allow procurement records to reference only same-tenant actors and approvals.
    op.create_unique_constraint("uq_membership_company_id_id", "memberships", ["company_id", "id"])
    op.create_unique_constraint("uq_approval_request_company_id_id", "approval_requests", ["company_id", "id"])
    op.create_table(
        "procurement_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_number", sa.String(40), nullable=False),
        sa.Column("supplier_name", sa.String(200), nullable=False),
        sa.Column("supplier_inn", sa.String(12), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("authorized_by_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("total_amount > 0", name="ck_procurement_order_amount_positive"),
        sa.CheckConstraint("currency = 'RUB'", name="ck_procurement_order_rub_only"),
        sa.CheckConstraint("status IN ('draft','authorized','cancelled')", name="ck_procurement_order_status"),
        sa.UniqueConstraint("company_id", "order_number", name="uq_procurement_order_number"),
        sa.UniqueConstraint("company_id", "id", name="uq_procurement_order_company_id_id"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_procurement_created_by_same_company"),
        sa.ForeignKeyConstraint(["company_id", "authorized_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_procurement_authorized_by_same_company"),
        sa.ForeignKeyConstraint(["company_id", "approval_request_id"], ["approval_requests.company_id", "approval_requests.id"], ondelete="RESTRICT", name="fk_procurement_approval_same_company"),
    )
    op.create_index("ix_procurement_orders_company_id", "procurement_orders", ["company_id"])
    op.create_table(
        "procurement_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("procurement_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_procurement_line_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_procurement_line_price_nonnegative"),
        sa.UniqueConstraint("procurement_order_id", "line_number", name="uq_procurement_line_number"),
        sa.ForeignKeyConstraint(
            ["company_id", "procurement_order_id"],
            ["procurement_orders.company_id", "procurement_orders.id"],
            ondelete="CASCADE", name="fk_procurement_line_order_same_company",
        ),
    )
    op.create_index("ix_procurement_order_lines_company_id", "procurement_order_lines", ["company_id"])
    op.create_index("ix_procurement_order_lines_procurement_order_id", "procurement_order_lines", ["procurement_order_id"])
    _tenant_policy("procurement_orders")
    _tenant_policy("procurement_order_lines")


def downgrade():
    for table in ("procurement_order_lines", "procurement_orders"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_access ON {table}")
        op.drop_table(table)
    op.drop_constraint("uq_approval_request_company_id_id", "approval_requests", type_="unique")
    op.drop_constraint("uq_membership_company_id_id", "memberships", type_="unique")
