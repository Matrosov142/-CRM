"""Link supplier RFQ lines to tender positions within the same tenant."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0031_rfq_tender_position_link"
down_revision = "0030_tender_pricing_versions"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL requires a unique key matching the full composite FK target.
    op.create_unique_constraint(
        "uq_tender_position_company_tender_id", "tender_positions",
        ["company_id", "tender_id", "id"],
    )
    op.add_column("supplier_rfq_lines", sa.Column("tender_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("supplier_rfq_lines", sa.Column("tender_position_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_check_constraint(
        "ck_rfq_line_tender_link_pair", "supplier_rfq_lines",
        "(tender_id IS NULL AND tender_position_id IS NULL) OR (tender_id IS NOT NULL AND tender_position_id IS NOT NULL)",
    )
    op.create_foreign_key(
        "fk_rfq_line_tender_position_same_company", "supplier_rfq_lines", "tender_positions",
        ["company_id", "tender_id", "tender_position_id"],
        ["company_id", "tender_id", "id"], ondelete="RESTRICT",
    )
    op.create_index("ix_rfq_line_tender_position", "supplier_rfq_lines", ["company_id", "tender_id", "tender_position_id"])


def downgrade():
    op.drop_index("ix_rfq_line_tender_position", table_name="supplier_rfq_lines")
    op.drop_constraint("fk_rfq_line_tender_position_same_company", "supplier_rfq_lines", type_="foreignkey")
    op.drop_constraint("ck_rfq_line_tender_link_pair", "supplier_rfq_lines", type_="check")
    op.drop_column("supplier_rfq_lines", "tender_position_id")
    op.drop_column("supplier_rfq_lines", "tender_id")
    op.drop_constraint("uq_tender_position_company_tender_id", "tender_positions", type_="unique")
