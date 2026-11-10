"""Link delivery estimates to confirmed shipments and capture actual freight cost."""
from alembic import op
import sqlalchemy as sa

revision = "0024_shipment_delivery_costs"
down_revision = "0023_delivery_estimates"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("warehouse_shipments", sa.Column("delivery_estimate_id", sa.UUID(), nullable=True))
    op.add_column("warehouse_shipments", sa.Column("planned_delivery_cost", sa.Numeric(14, 2), nullable=True))
    op.add_column("warehouse_shipments", sa.Column("actual_delivery_cost", sa.Numeric(14, 2), nullable=True))
    op.add_column("warehouse_shipments", sa.Column("actual_delivery_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_shipment_delivery_estimate_same_company", "warehouse_shipments", "delivery_estimates",
        ["company_id", "delivery_estimate_id"], ["company_id", "id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_shipment_planned_delivery_cost_nonnegative", "warehouse_shipments",
        "planned_delivery_cost IS NULL OR planned_delivery_cost >= 0",
    )
    op.create_check_constraint(
        "ck_shipment_actual_delivery_cost_nonnegative", "warehouse_shipments",
        "actual_delivery_cost IS NULL OR actual_delivery_cost >= 0",
    )
    op.create_index("ix_warehouse_shipments_company_delivery_estimate",
                    "warehouse_shipments", ["company_id", "delivery_estimate_id"])


def downgrade():
    op.drop_index("ix_warehouse_shipments_company_delivery_estimate", table_name="warehouse_shipments")
    op.drop_constraint("ck_shipment_actual_delivery_cost_nonnegative", "warehouse_shipments", type_="check")
    op.drop_constraint("ck_shipment_planned_delivery_cost_nonnegative", "warehouse_shipments", type_="check")
    op.drop_constraint("fk_shipment_delivery_estimate_same_company", "warehouse_shipments", type_="foreignkey")
    op.drop_column("warehouse_shipments", "actual_delivery_at")
    op.drop_column("warehouse_shipments", "actual_delivery_cost")
    op.drop_column("warehouse_shipments", "planned_delivery_cost")
    op.drop_column("warehouse_shipments", "delivery_estimate_id")
