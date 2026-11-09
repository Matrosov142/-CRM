"""Quality inspections and traceable finished-goods batches."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_quality_finished_goods"
down_revision = "0017_processing_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_inspections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_number", sa.String(60), nullable=False),
        sa.Column("inspected_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("good_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("defective_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("result", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("defect_description", sa.String(2000), nullable=False, server_default=""),
        sa.Column("inspected_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_quality_inspection_company_id"),
        sa.ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="RESTRICT", name="fk_quality_inspection_job_same_company"),
        sa.ForeignKeyConstraint(["company_id", "inspected_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_quality_inspection_inspector_same_company"),
        sa.CheckConstraint("inspected_quantity > 0 AND good_quantity >= 0 AND defective_quantity >= 0 AND good_quantity + defective_quantity = inspected_quantity", name="ck_quality_inspection_quantities"),
        sa.CheckConstraint("result IN ('pending','passed','failed','rework')", name="ck_quality_inspection_result"),
        sa.UniqueConstraint("company_id", "inspection_number", name="uq_quality_inspection_number"),
    )
    op.create_index("ix_quality_inspections_company_id", "quality_inspections", ["company_id"])
    op.create_table(
        "finished_goods_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inspection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_number", sa.String(60), nullable=False),
        sa.Column("item_name", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("quantity_available", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("location", sa.String(120)),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "batch_number", name="uq_finished_goods_batch_number"),
        sa.ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="RESTRICT", name="fk_finished_goods_job_same_company"),
        sa.ForeignKeyConstraint(["company_id", "inspection_id"], ["quality_inspections.company_id", "quality_inspections.id"], ondelete="RESTRICT", name="fk_finished_goods_inspection_same_company"),
        sa.CheckConstraint("quantity > 0 AND quantity_available >= 0 AND quantity_available <= quantity", name="ck_finished_goods_batch_quantities"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_finished_goods_batch_unit_cost"),
        sa.CheckConstraint("status IN ('available','reserved','shipped','blocked')", name="ck_finished_goods_batch_status"),
    )
    op.create_index("ix_finished_goods_batches_company_id", "finished_goods_batches", ["company_id"])


def downgrade():
    op.drop_table("finished_goods_batches")
    op.drop_table("quality_inspections")
