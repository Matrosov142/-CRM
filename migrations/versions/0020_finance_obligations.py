"""Receivables/payables and confirmed cash movement allocations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020_finance_obligations"
down_revision = "0019_finance_movements"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("finance_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obligation_number", sa.String(60), nullable=False),
        sa.Column("side", sa.String(12), nullable=False),
        sa.Column("amount", sa.Numeric(14,2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("counterparty_name", sa.String(200), nullable=False),
        sa.Column("counterparty_inn", sa.String(12)),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("procurement_order_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_finance_obligation_company_id"),
        sa.UniqueConstraint("company_id", "obligation_number", name="uq_finance_obligation_number"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_obligation_creator_same_company"),
        sa.ForeignKeyConstraint(["company_id", "procurement_order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_finance_obligation_order_same_company"),
        sa.CheckConstraint("side IN ('receivable','payable')", name="ck_finance_obligation_side"),
        sa.CheckConstraint("amount > 0", name="ck_finance_obligation_amount_positive"),
        sa.CheckConstraint("currency = 'RUB'", name="ck_finance_obligation_rub_only"))
    op.create_index("ix_finance_obligations_company_due", "finance_obligations", ["company_id", "due_date"])
    op.create_table("finance_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obligation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(14,2), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_finance_allocation_company_id"),
        sa.ForeignKeyConstraint(["company_id", "obligation_id"], ["finance_obligations.company_id", "finance_obligations.id"], ondelete="RESTRICT", name="fk_finance_allocation_obligation_same_company"),
        sa.ForeignKeyConstraint(["company_id", "movement_id"], ["finance_movements.company_id", "finance_movements.id"], ondelete="RESTRICT", name="fk_finance_allocation_movement_same_company"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_allocation_creator_same_company"),
        sa.CheckConstraint("amount > 0", name="ck_finance_allocation_amount_positive"))
    op.create_index("ix_finance_allocations_company_obligation", "finance_allocations", ["company_id", "obligation_id"])
    op.create_index("ix_finance_allocations_company_movement", "finance_allocations", ["company_id", "movement_id"])
    for table, policy in (("finance_obligations", "finance_obligations_tenant_access"), ("finance_allocations", "finance_allocations_tenant_access")):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {policy} ON {table} USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")

def downgrade():
    op.execute("DROP POLICY IF EXISTS finance_allocations_tenant_access ON finance_allocations")
    op.execute("DROP POLICY IF EXISTS finance_obligations_tenant_access ON finance_obligations")
    op.drop_table("finance_allocations")
    op.drop_table("finance_obligations")
