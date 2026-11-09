"""Immutable supplier offer revisions with one current version per supplier/RFQ."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_supplier_offer_revisions"
down_revision = "0011_supplier_offers"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("uq_supplier_offer_one_per_supplier_rfq", "supplier_offers", type_="unique")
    op.add_column("supplier_offers", sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("supplier_offers", sa.Column("supersedes_offer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("supplier_offers", sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_unique_constraint("uq_supplier_offer_version", "supplier_offers", ["company_id", "rfq_id", "supplier_id", "version_no"])
    op.create_foreign_key(
        "fk_supplier_offer_supersedes_same_company", "supplier_offers", "supplier_offers",
        ["company_id", "supersedes_offer_id"], ["company_id", "id"], ondelete="RESTRICT",
    )
    op.create_check_constraint("ck_supplier_offer_version_positive", "supplier_offers", "version_no > 0")
    op.create_index("ix_supplier_offer_current", "supplier_offers", ["company_id", "rfq_id", "supplier_id", "is_current"])


def downgrade():
    op.drop_index("ix_supplier_offer_current", table_name="supplier_offers")
    op.drop_constraint("ck_supplier_offer_version_positive", "supplier_offers", type_="check")
    op.drop_constraint("fk_supplier_offer_supersedes_same_company", "supplier_offers", type_="foreignkey")
    op.drop_constraint("uq_supplier_offer_version", "supplier_offers", type_="unique")
    op.drop_column("supplier_offers", "is_current")
    op.drop_column("supplier_offers", "supersedes_offer_id")
    op.drop_column("supplier_offers", "version_no")
    op.create_unique_constraint("uq_supplier_offer_one_per_supplier_rfq", "supplier_offers", ["company_id", "rfq_id", "supplier_id"])
