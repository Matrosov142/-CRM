"""Employee permission overrides, operation limits and approval requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_permissions_limits"
down_revision = "0006_director_membership"
branch_labels = None
depends_on = None


def _director_only_rls(table):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
      CREATE POLICY {table}_director_access ON {table}
      USING (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND app_is_company_director(company_id)
      )
      WITH CHECK (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND app_is_company_director(company_id)
      )
    """)


def _approval_rls():
    table = "approval_requests"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("""
      CREATE POLICY approval_requests_tenant_read ON approval_requests
      FOR SELECT USING (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
      )
    """)
    op.execute("""
      CREATE POLICY approval_requests_self_create ON approval_requests
      FOR INSERT WITH CHECK (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND EXISTS (
          SELECT 1 FROM memberships m
          WHERE m.id = requested_by_membership_id
            AND m.company_id = approval_requests.company_id
            AND m.user_id = app_current_user_id()
            AND m.status = 'active'
        )
      )
    """)
    op.execute("""
      CREATE POLICY approval_requests_director_decide ON approval_requests
      FOR UPDATE USING (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND app_is_company_director(company_id)
      )
      WITH CHECK (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND app_is_company_director(company_id)
      )
    """)


def upgrade():
    op.create_table(
      "employee_permission_overrides",
      sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
      sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
      sa.Column("membership_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False),
      sa.Column("action", sa.String(80), nullable=False),
      sa.Column("allowed", sa.Boolean(), nullable=False),
      sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
      sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.UniqueConstraint("company_id", "membership_id", "action", name="uq_employee_permission_override"),
    )
    op.create_index("ix_employee_permission_overrides_company_id", "employee_permission_overrides", ["company_id"])
    op.create_index("ix_employee_permission_overrides_membership_id", "employee_permission_overrides", ["membership_id"])

    op.create_table(
      "employee_operation_limits",
      sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
      sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
      sa.Column("membership_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False),
      sa.Column("operation", sa.String(40), nullable=False),
      sa.Column("limit_amount", sa.Numeric(14, 2), nullable=False),
      sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
      sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.CheckConstraint("limit_amount >= 0", name="ck_employee_operation_limit_nonnegative"),
      sa.UniqueConstraint("company_id", "membership_id", "operation", name="uq_employee_operation_limit"),
    )
    op.create_index("ix_employee_operation_limits_company_id", "employee_operation_limits", ["company_id"])
    op.create_index("ix_employee_operation_limits_membership_id", "employee_operation_limits", ["membership_id"])

    op.create_table(
      "approval_requests",
      sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
      sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
      sa.Column("requested_by_membership_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False),
      sa.Column("operation", sa.String(40), nullable=False),
      sa.Column("amount", sa.Numeric(14, 2), nullable=False),
      sa.Column("reason", sa.String(1000), nullable=False),
      sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
      sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
      sa.Column("decision_note", sa.String(1000), nullable=True),
      sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
      sa.CheckConstraint("amount > 0", name="ck_approval_request_amount_positive"),
      sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_approval_request_status"),
    )
    op.create_index("ix_approval_requests_company_id", "approval_requests", ["company_id"])
    op.create_index("ix_approval_requests_requested_by_membership_id", "approval_requests", ["requested_by_membership_id"])

    _director_only_rls("employee_permission_overrides")
    _director_only_rls("employee_operation_limits")
    op.execute("""
      CREATE POLICY employee_operation_limits_self_read ON employee_operation_limits
      FOR SELECT USING (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        AND EXISTS (
          SELECT 1 FROM memberships m
          WHERE m.id = employee_operation_limits.membership_id
            AND m.user_id = app_current_user_id()
            AND m.status = 'active'
        )
      )
    """)
    _approval_rls()


def downgrade():
    op.execute("DROP POLICY IF EXISTS approval_requests_tenant_read ON approval_requests")
    op.execute("DROP POLICY IF EXISTS approval_requests_self_create ON approval_requests")
    op.execute("DROP POLICY IF EXISTS approval_requests_director_decide ON approval_requests")
    op.execute("DROP POLICY IF EXISTS employee_operation_limits_self_read ON employee_operation_limits")
    op.execute("DROP POLICY IF EXISTS employee_operation_limits_director_access ON employee_operation_limits")
    op.execute("DROP POLICY IF EXISTS employee_permission_overrides_director_access ON employee_permission_overrides")
    for table in ("approval_requests", "employee_operation_limits", "employee_permission_overrides"):
        op.drop_table(table)
