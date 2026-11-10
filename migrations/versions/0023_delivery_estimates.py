"""Persist delivery estimates and manual selection."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023_delivery_estimates"
down_revision = "0022_contract_documents"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "delivery_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin", sa.String(300), nullable=False),
        sa.Column("destination", sa.String(300), nullable=False),
        sa.Column("distance_km_one_way", sa.Numeric(10, 2), nullable=False),
        sa.Column("cargo_description", sa.String(500), nullable=False),
        sa.Column("cargo_weight_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column("cargo_volume_m3", sa.Numeric(10, 3), nullable=True),
        sa.Column("options", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("selected_option_index", sa.Integer(), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_delivery_estimate_company_id_id"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_delivery_estimate_creator_same_company"),
        sa.CheckConstraint("distance_km_one_way > 0", name="ck_delivery_estimate_distance_positive"),
        sa.CheckConstraint("selected_option_index IS NULL OR selected_option_index >= 0", name="ck_delivery_estimate_selected_index"),
    )
    op.create_index("ix_delivery_estimates_company_created", "delivery_estimates", ["company_id", "created_at"])
    op.execute("ALTER TABLE delivery_estimates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE delivery_estimates FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY delivery_estimates_tenant_access ON delivery_estimates
        USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)""")

def downgrade():
    op.execute("DROP POLICY IF EXISTS delivery_estimates_tenant_access ON delivery_estimates")
    op.drop_table("delivery_estimates")
