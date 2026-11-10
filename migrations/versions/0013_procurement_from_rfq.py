"""Link supplier procurement drafts to their originating RFQ and supplier."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_procurement_from_rfq"
down_revision = "0012_supplier_offer_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("procurement_orders", sa.Column("source_rfq_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("procurement_orders", sa.Column("source_supplier_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_unique_constraint("uq_procurement_order_rfq_supplier", "procurement_orders",
                                ["company_id", "source_rfq_id", "source_supplier_id"])
    op.create_foreign_key("fk_procurement_source_rfq_same_company", "procurement_orders", "supplier_rfqs",
                          ["company_id", "source_rfq_id"], ["company_id", "id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_procurement_source_supplier_same_company", "procurement_orders", "suppliers",
                          ["company_id", "source_supplier_id"], ["company_id", "id"], ondelete="RESTRICT")


def downgrade():
    op.drop_constraint("fk_procurement_source_supplier_same_company", "procurement_orders", type_="foreignkey")
    op.drop_constraint("fk_procurement_source_rfq_same_company", "procurement_orders", type_="foreignkey")
    op.drop_constraint("uq_procurement_order_rfq_supplier", "procurement_orders", type_="unique")
    op.drop_column("procurement_orders", "source_supplier_id")
    op.drop_column("procurement_orders", "source_rfq_id")
