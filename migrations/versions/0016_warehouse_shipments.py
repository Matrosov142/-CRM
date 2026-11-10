"""Confirmed partial shipments consume physical stock and reserved quantity."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0016_warehouse_shipments"
down_revision = "0015_stock_reservations"
branch_labels = None
depends_on = None

def tenant_rls(table):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {table}_tenant_access ON {table} USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")

def upgrade():
    op.add_column("stock_reservation_lines", sa.Column("quantity_shipped", sa.Numeric(14,3), nullable=False, server_default="0"))
    op.create_check_constraint("ck_reservation_line_shipped_range", "stock_reservation_lines", "quantity_shipped >= 0 AND quantity_shipped <= quantity")
    op.create_table("warehouse_shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shipment_number", sa.String(60), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("carrier", sa.String(160)), sa.Column("tracking_number", sa.String(120)),
        sa.Column("destination", sa.String(500)), sa.Column("note", sa.String(2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmed"),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_warehouse_shipment_company_id_id"),
        sa.ForeignKeyConstraint(["company_id", "reservation_id"], ["stock_reservations.company_id", "stock_reservations.id"], ondelete="RESTRICT", name="fk_shipment_reservation_same_company"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_shipment_creator_same_company"),
        sa.CheckConstraint("status IN ('confirmed')", name="ck_warehouse_shipment_status"))
    op.create_index("ix_warehouse_shipments_company_id", "warehouse_shipments", ["company_id"])
    op.create_table("warehouse_shipment_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reservation_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("batch_number", sa.String(60), nullable=False), sa.Column("item_name", sa.String(300), nullable=False),
        sa.ForeignKeyConstraint(["company_id", "shipment_id"], ["warehouse_shipments.company_id", "warehouse_shipments.id"], ondelete="CASCADE", name="fk_shipment_line_header_same_company"),
        sa.ForeignKeyConstraint(["company_id", "reservation_line_id"], ["stock_reservation_lines.company_id", "stock_reservation_lines.id"], ondelete="RESTRICT", name="fk_shipment_line_reservation_line_same_company"),
        sa.CheckConstraint("quantity > 0", name="ck_shipment_line_quantity_positive"))
    op.create_index("ix_warehouse_shipment_lines_company_id", "warehouse_shipment_lines", ["company_id"])
    tenant_rls("warehouse_shipments"); tenant_rls("warehouse_shipment_lines")

def downgrade():
    for t in ("warehouse_shipment_lines", "warehouse_shipments"):
        op.execute(f"DROP POLICY IF EXISTS {t}_tenant_access ON {t}")
        op.drop_table(t)
    op.drop_constraint("ck_reservation_line_shipped_range", "stock_reservation_lines", type_="check")
    op.drop_column("stock_reservation_lines", "quantity_shipped")
