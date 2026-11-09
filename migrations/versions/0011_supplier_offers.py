"""Supplier offers, human review and per-line selection."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0011_supplier_offers"
down_revision = "0010_suppliers_rfqs"
branch_labels = None
depends_on = None

def rls(t):
    op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY {t}_tenant_access ON {t} USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")

def upgrade():
    # Parent keys required for same-tenant composite foreign keys.
    op.create_unique_constraint("uq_rfq_line_company_id_id", "supplier_rfq_lines", ["company_id", "id"])
    op.create_unique_constraint("uq_rfq_recipient_company_id_id", "supplier_rfq_recipients", ["company_id", "id"])
    op.create_table("supplier_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("source_channel", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("supplier_offer_number", sa.String(80)), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("valid_until", sa.DateTime(timezone=True)), sa.Column("delivery_days", sa.Integer()),
        sa.Column("delivery_cost", sa.Numeric(14,2), nullable=False, server_default="0"), sa.Column("vat_treatment", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("vat_amount", sa.Numeric(14,2)), sa.Column("payment_terms", sa.String(1000)), sa.Column("original_text", sa.String(12000)),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="pending"), sa.Column("review_note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_supplier_offer_company_id_id"), sa.UniqueConstraint("company_id", "rfq_id", "supplier_id", name="uq_supplier_offer_one_per_supplier_rfq"),
        sa.ForeignKeyConstraint(["company_id","rfq_id"],["supplier_rfqs.company_id","supplier_rfqs.id"],ondelete="CASCADE",name="fk_supplier_offer_rfq_same_company"),
        sa.ForeignKeyConstraint(["company_id","supplier_id"],["suppliers.company_id","suppliers.id"],ondelete="RESTRICT",name="fk_supplier_offer_supplier_same_company"),
        sa.ForeignKeyConstraint(["company_id","recipient_id"],["supplier_rfq_recipients.company_id","supplier_rfq_recipients.id"],ondelete="RESTRICT",name="fk_supplier_offer_recipient_same_company"),
        sa.CheckConstraint("source_channel IN ('manual','email','telegram','upload')", name="ck_supplier_offer_channel"),
        sa.CheckConstraint("review_status IN ('pending','confirmed','rejected')", name="ck_supplier_offer_review"),
        sa.CheckConstraint("vat_treatment IN ('included','excluded','no_vat','unknown')", name="ck_supplier_offer_vat"),
        sa.CheckConstraint("delivery_cost >= 0 AND (vat_amount IS NULL OR vat_amount >= 0)", name="ck_supplier_offer_amounts"),
    )
    op.create_index("ix_supplier_offers_company_id", "supplier_offers", ["company_id"])
    op.create_table("supplier_offer_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("rfq_line_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offered_item_name", sa.String(300), nullable=False), sa.Column("offered_specification", sa.String(2000)),
        sa.Column("quantity", sa.Numeric(14,3), nullable=False), sa.Column("unit", sa.String(20), nullable=False), sa.Column("unit_price", sa.Numeric(14,2), nullable=False),
        sa.Column("specification_match", sa.String(20), nullable=False, server_default="unknown"), sa.Column("note", sa.String(1000)),
        sa.ForeignKeyConstraint(["company_id","offer_id"],["supplier_offers.company_id","supplier_offers.id"],ondelete="CASCADE",name="fk_supplier_offer_line_offer_same_company"),
        sa.ForeignKeyConstraint(["company_id","rfq_line_id"],["supplier_rfq_lines.company_id","supplier_rfq_lines.id"],ondelete="RESTRICT",name="fk_supplier_offer_line_rfq_line_same_company"),
        sa.UniqueConstraint("offer_id","rfq_line_id",name="uq_supplier_offer_line_once"), sa.CheckConstraint("quantity > 0 AND unit_price >= 0", name="ck_supplier_offer_line_amounts"),
        sa.CheckConstraint("specification_match IN ('match','mismatch','unknown')", name="ck_supplier_offer_line_spec_match"),
    )
    op.create_index("ix_supplier_offer_lines_company_id", "supplier_offer_lines", ["company_id"])
    op.create_table("supplier_rfq_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("rfq_line_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("note", sa.String(1000), nullable=False, server_default=""), sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id","rfq_id"],["supplier_rfqs.company_id","supplier_rfqs.id"],ondelete="CASCADE",name="fk_rfq_selection_rfq_same_company"),
        sa.ForeignKeyConstraint(["company_id","rfq_line_id"],["supplier_rfq_lines.company_id","supplier_rfq_lines.id"],ondelete="CASCADE",name="fk_rfq_selection_line_same_company"),
        sa.ForeignKeyConstraint(["company_id","offer_id"],["supplier_offers.company_id","supplier_offers.id"],ondelete="RESTRICT",name="fk_rfq_selection_offer_same_company"),
        sa.UniqueConstraint("company_id","rfq_line_id",name="uq_rfq_selection_line"),
    )
    op.create_index("ix_supplier_rfq_selections_company_id", "supplier_rfq_selections", ["company_id"])
    for t in ("supplier_offers","supplier_offer_lines","supplier_rfq_selections"): rls(t)

def downgrade():
    for t in ("supplier_rfq_selections","supplier_offer_lines","supplier_offers"):
        op.execute(f"DROP POLICY IF EXISTS {t}_tenant_access ON {t}")
        op.drop_table(t)
    op.drop_constraint("uq_rfq_recipient_company_id_id", "supplier_rfq_recipients", type_="unique")
    op.drop_constraint("uq_rfq_line_company_id_id", "supplier_rfq_lines", type_="unique")
