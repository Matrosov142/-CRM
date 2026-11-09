"""Processing jobs and operation records; material reservation/write-off is not automatic."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_processing_jobs"
down_revision = "0016_warehouse_shipments"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_number", sa.String(60), nullable=False),
        sa.Column("output_item_name", sa.String(300), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("good_quantity", sa.Numeric(14,3), nullable=False, server_default="0"),
        sa.Column("defective_quantity", sa.Numeric(14,3), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("note", sa.String(2000), nullable=False, server_default=""),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "job_number", name="uq_processing_job_number"),
        sa.UniqueConstraint("company_id", "id", name="uq_processing_job_company_id"),
        sa.ForeignKeyConstraint(["company_id", "order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_processing_job_order_same_company"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_processing_job_creator_same_company"),
        sa.CheckConstraint("planned_quantity > 0 AND good_quantity >= 0 AND defective_quantity >= 0", name="ck_processing_job_quantities"),
        sa.CheckConstraint("status IN ('planned','in_progress','completed','cancelled')", name="ck_processing_job_status"),
    )
    op.create_index("ix_processing_jobs_company_id", "processing_jobs", ["company_id"])
    op.create_table(
        "processing_operations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_name", sa.String(160), nullable=False),
        sa.Column("executor_name", sa.String(160), nullable=False),
        sa.Column("operation_cost", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("processed_quantity", sa.Numeric(14,3)),
        sa.Column("good_quantity", sa.Numeric(14,3)),
        sa.Column("defective_quantity", sa.Numeric(14,3)),
        sa.Column("defect_note", sa.String(1000), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="CASCADE", name="fk_processing_operation_job_same_company"),
        sa.CheckConstraint("operation_cost >= 0", name="ck_processing_operation_cost"),
    )
    op.create_index("ix_processing_operations_job", "processing_operations", ["company_id", "job_id"])
    op.create_table(
        "processing_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stock_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(14,3), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(14,3)),
        sa.Column("unit_cost_snapshot", sa.Numeric(14,2), nullable=False),
        sa.ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="CASCADE", name="fk_processing_material_job_same_company"),
        sa.ForeignKeyConstraint(["company_id", "stock_batch_id"], ["stock_batches.company_id", "stock_batches.id"], ondelete="RESTRICT", name="fk_processing_material_batch_same_company"),
        sa.CheckConstraint("planned_quantity > 0 AND (actual_quantity IS NULL OR actual_quantity >= 0) AND unit_cost_snapshot >= 0", name="ck_processing_material_quantities"),
    )
    op.create_index("ix_processing_materials_job", "processing_materials", ["company_id", "job_id"])

def downgrade():
    op.drop_table("processing_materials")
    op.drop_table("processing_operations")
    op.drop_table("processing_jobs")
