"""Create append-only, single-use approval consumption records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_approval_consumption"
down_revision = "0007_permissions_limits_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_consumptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approval_request_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("approval_requests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consumed_by_membership_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consumed_entity_type", sa.String(80), nullable=True),
        sa.Column("consumed_entity_id", sa.String(100), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("approval_request_id", name="uq_approval_consumption_request"),
    )
    op.create_index("ix_approval_consumptions_company_id", "approval_consumptions", ["company_id"])
    op.execute("ALTER TABLE approval_consumptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE approval_consumptions FORCE ROW LEVEL SECURITY")
    op.execute("""
      CREATE POLICY approval_consumptions_self_insert ON approval_consumptions
      FOR INSERT WITH CHECK (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND EXISTS (
          SELECT 1 FROM memberships m
          WHERE m.id = consumed_by_membership_id
            AND m.company_id = approval_consumptions.company_id
            AND m.user_id = app_current_user_id()
            AND m.status = 'active'
        )
        AND EXISTS (
          SELECT 1 FROM approval_requests a
          WHERE a.id = approval_request_id
            AND a.company_id = approval_consumptions.company_id
            AND a.requested_by_membership_id = consumed_by_membership_id
            AND a.status = 'approved'
        )
      )
    """)
    op.execute("""
      CREATE POLICY approval_consumptions_self_read ON approval_consumptions
      FOR SELECT USING (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND consumed_by_membership_id IN (
          SELECT m.id FROM memberships m
          WHERE m.company_id = approval_consumptions.company_id
            AND m.user_id = app_current_user_id()
            AND m.status = 'active'
        )
      )
    """)
    # No UPDATE/DELETE policy: consumption records are append-only for runtime roles.


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS approval_consumptions_self_read ON approval_consumptions")
    op.execute("DROP POLICY IF EXISTS approval_consumptions_self_insert ON approval_consumptions")
    op.drop_table("approval_consumptions")
