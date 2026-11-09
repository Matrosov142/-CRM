"""Partial warehouse receipts, defect quantities and accepted stock batches."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_warehouse_receiving"
down_revision = "0013_procurement_from_rfq"
branch_labels = None
depends_on = None


def tenant_rls(table):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY {table}_tenant_access ON {table}
      USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)""")


def upgrade():
    op.create_unique_constraint("uq_procurement_order_line_company_id_id", "procurement_order_lines", ["company_id", "id"])
    op.create_table(
        "warehouse_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receipt_number", sa.String(50), nullable=False),
        sa.Column("procurement_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("supplier_document_number", sa.String(100), nullable=True),
        sa.Column("note", sa.String(2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="accepted"),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_warehouse_receipt_company_id_id"),
        sa.UniqueConstraint("company_id", "receipt_number", name="uq_warehouse_receipt_number"),
        sa.ForeignKeyConstraint(["company_id", "procurement_order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_receipt_order_same_company"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_receipt_creator_same_company"),
        sa.CheckConstraint("status = 'accepted'", name="ck_warehouse_receipt_status"),
    )
    op.create_index("ix_warehouse_receipts_company_id", "warehouse_receipts", ["company_id"])
    op.create_table(
        "warehouse_receipt_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("procurement_order_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("received_quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("accepted_quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("defective_quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("defect_note", sa.String(1000), nullable=False, server_default=""),
        sa.UniqueConstraint("company_id", "id", name="uq_warehouse_receipt_line_company_id_id"),
        sa.ForeignKeyConstraint(["company_id", "receipt_id"], ["warehouse_receipts.company_id", "warehouse_receipts.id"], ondelete="CASCADE", name="fk_receipt_line_receipt_same_company"),
        sa.ForeignKeyConstraint(["company_id", "procurement_order_line_id"], ["procurement_order_lines.company_id", "procurement_order_lines.id"], ondelete="RESTRICT", name="fk_receipt_line_order_line_same_company"),
        sa.CheckConstraint("received_quantity > 0 AND accepted_quantity >= 0 AND defective_quantity >= 0 AND received_quantity = accepted_quantity + defective_quantity", name="ck_receipt_line_quantities"),
    )
    op.create_index("ix_warehouse_receipt_lines_company_id", "warehouse_receipt_lines", ["company_id"])
    op.create_table(
        "stock_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receipt_line_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("batch_number", sa.String(60), nullable=False),
        sa.Column("item_name", sa.String(300), nullable=False),
        sa.Column("quantity_received", sa.Numeric(14,3), nullable=False),
        sa.Column("quantity_balance", sa.Numeric(14,3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14,2), nullable=False),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_stock_batch_company_id_id"),
        sa.UniqueConstraint("company_id", "batch_number", name="uq_stock_batch_number"),
        sa.ForeignKeyConstraint(["company_id", "receipt_line_id"], ["warehouse_receipt_lines.company_id", "warehouse_receipt_lines.id"], ondelete="RESTRICT", name="fk_stock_batch_receipt_line_same_company"),
        sa.CheckConstraint("quantity_received > 0 AND quantity_balance >= 0 AND quantity_balance <= quantity_received", name="ck_stock_batch_quantities"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_stock_batch_unit_cost"),
    )
    op.create_index("ix_stock_batches_company_id", "stock_batches", ["company_id"])
    op.create_index("ix_stock_batches_item_name", "stock_batches", ["company_id", "item_name"])
    for table in ("warehouse_receipts", "warehouse_receipt_lines", "stock_batches"):
        tenant_rls(table)


def downgrade():
    for table in ("stock_batches", "warehouse_receipt_lines", "warehouse_receipts"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_access ON {table}")
        op.drop_table(table)
    op.drop_constraint("uq_procurement_order_line_company_id_id", "procurement_order_lines", type_="unique")
