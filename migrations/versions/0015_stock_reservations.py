"""Tenant-scoped stock reservations; physical balances remain unchanged."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0015_stock_reservations"
down_revision = "0014_warehouse_receiving"
branch_labels = None
depends_on = None

def tenant_rls(table):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY {table}_tenant_access ON {table}
      USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)""")

def upgrade():
    op.create_table("stock_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reference", sa.String(160), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_by_membership_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(1000), nullable=True),
        sa.UniqueConstraint("company_id", "id", name="uq_stock_reservation_company_id_id"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_stock_reservation_creator_same_company"),
        sa.CheckConstraint("status IN ('active', 'released')", name="ck_stock_reservation_status"))
    op.create_index("ix_stock_reservations_company_id", "stock_reservations", ["company_id"])
    op.create_table("stock_reservation_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False),
        sa.UniqueConstraint("company_id", "id", name="uq_stock_reservation_line_company_id_id"),
        sa.ForeignKeyConstraint(["company_id", "reservation_id"], ["stock_reservations.company_id", "stock_reservations.id"], ondelete="CASCADE", name="fk_stock_reservation_line_header_same_company"),
        sa.ForeignKeyConstraint(["company_id", "stock_batch_id"], ["stock_batches.company_id", "stock_batches.id"], ondelete="RESTRICT", name="fk_stock_reservation_line_batch_same_company"),
        sa.CheckConstraint("quantity > 0", name="ck_stock_reservation_line_quantity_positive"))
    op.create_index("ix_stock_reservation_lines_company_id", "stock_reservation_lines", ["company_id"])
    op.create_index("ix_stock_reservation_lines_batch", "stock_reservation_lines", ["company_id", "stock_batch_id"])
    for t in ("stock_reservations", "stock_reservation_lines"): tenant_rls(t)

def downgrade():
    for t in ("stock_reservation_lines", "stock_reservations"):
        op.execute(f"DROP POLICY IF EXISTS {t}_tenant_access ON {t}")
        op.drop_table(t)
