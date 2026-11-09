"""Supplier directory and RFQ preparation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_suppliers_rfqs"
down_revision = "0009_procurement_orders"
branch_labels = None
depends_on = None


def tenant_rls(table):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
      CREATE POLICY {table}_tenant_access ON {table}
      USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
      WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def upgrade():
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("inn", sa.String(12), nullable=True),
        sa.Column("kpp", sa.String(9), nullable=True),
        sa.Column("contact_name", sa.String(160), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("payment_terms", sa.String(500), nullable=True),
        sa.Column("delivery_terms", sa.String(500), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "inn", name="uq_supplier_company_inn"),
        sa.UniqueConstraint("company_id", "id", name="uq_supplier_company_id_id"),
        sa.CheckConstraint("status IN ('active','blocked')", name="ck_supplier_status"),
    )
    op.create_index("ix_suppliers_company_id", "suppliers", ["company_id"])

    op.create_table(
        "supplier_rfqs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfq_number", sa.String(40), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("message", sa.String(4000), nullable=False),
        sa.Column("response_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_supplier_rfq_company_id_id"),
        sa.UniqueConstraint("company_id", "rfq_number", name="uq_supplier_rfq_number"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_rfq_creator_same_company"),
        sa.CheckConstraint("status IN ('draft','prepared','closed')", name="ck_supplier_rfq_status"),
    )
    op.create_index("ix_supplier_rfqs_company_id", "supplier_rfqs", ["company_id"])

    op.create_table(
        "supplier_rfq_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_name", sa.String(300), nullable=False),
        sa.Column("specification", sa.String(2000), nullable=True),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.UniqueConstraint("rfq_id", "line_number", name="uq_rfq_line_number"),
        sa.ForeignKeyConstraint(["company_id", "rfq_id"], ["supplier_rfqs.company_id", "supplier_rfqs.id"], ondelete="CASCADE", name="fk_rfq_line_parent_same_company"),
        sa.CheckConstraint("quantity > 0", name="ck_rfq_line_quantity_positive"),
    )
    op.create_index("ix_supplier_rfq_lines_company_id", "supplier_rfq_lines", ["company_id"])

    op.create_table(
        "supplier_rfq_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="prepared"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("company_id", "rfq_id", "supplier_id", name="uq_rfq_supplier"),
        sa.ForeignKeyConstraint(["company_id", "rfq_id"], ["supplier_rfqs.company_id", "supplier_rfqs.id"], ondelete="CASCADE", name="fk_rfq_recipient_rfq_same_company"),
        sa.ForeignKeyConstraint(["company_id", "supplier_id"], ["suppliers.company_id", "suppliers.id"], ondelete="RESTRICT", name="fk_rfq_recipient_supplier_same_company"),
        sa.CheckConstraint("status IN ('prepared','sent','declined','responded')", name="ck_rfq_recipient_status"),
    )
    op.create_index("ix_supplier_rfq_recipients_company_id", "supplier_rfq_recipients", ["company_id"])
    for table in ("suppliers", "supplier_rfqs", "supplier_rfq_lines", "supplier_rfq_recipients"):
        tenant_rls(table)


def downgrade():
    for table in ("supplier_rfq_recipients", "supplier_rfq_lines", "supplier_rfqs", "suppliers"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_access ON {table}")
        op.drop_table(table)
