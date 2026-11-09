"""Persistent tenant-isolated finance cash movements."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0019_finance_movements"
down_revision = "0018_quality_finished_goods"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("finance_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("movement_number", sa.String(60), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("amount", sa.Numeric(14,2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("movement_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("counterparty_name", sa.String(200), nullable=False),
        sa.Column("counterparty_inn", sa.String(12)),
        sa.Column("purpose", sa.String(1000), nullable=False, server_default=""),
        sa.Column("document_reference", sa.String(120)),
        sa.Column("procurement_order_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confirmed_by_membership_id", postgresql.UUID(as_uuid=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "id", name="uq_finance_movement_company_id"),
        sa.UniqueConstraint("company_id", "movement_number", name="uq_finance_movement_number"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_movement_creator_same_company"),
        sa.ForeignKeyConstraint(["company_id", "confirmed_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_movement_confirmer_same_company"),
        sa.ForeignKeyConstraint(["company_id", "procurement_order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_finance_movement_order_same_company"),
        sa.CheckConstraint("kind IN ('receipt','payment')", name="ck_finance_movement_kind"),
        sa.CheckConstraint("status IN ('draft','confirmed','cancelled')", name="ck_finance_movement_status"),
        sa.CheckConstraint("amount > 0", name="ck_finance_movement_amount_positive"),
        sa.CheckConstraint("currency = 'RUB'", name="ck_finance_movement_rub_only"))
    op.create_index("ix_finance_movements_company_id", "finance_movements", ["company_id"])
    op.create_index("ix_finance_movements_company_date", "finance_movements", ["company_id", "movement_date"])
    op.execute("ALTER TABLE finance_movements ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE finance_movements FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY finance_movements_tenant_access ON finance_movements USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")

def downgrade():
    op.execute("DROP POLICY IF EXISTS finance_movements_tenant_access ON finance_movements")
    op.drop_table("finance_movements")
