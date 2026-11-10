"""Employee invitations with tenant and token-scoped RLS."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_employee_invitations"
down_revision = "0004_rbac_audit"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "employee_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_employee_invitations_company_id", "employee_invitations", ["company_id"])
    op.create_index("ix_employee_invitations_email", "employee_invitations", ["email"])
    op.create_index("ix_employee_invitations_token_hash", "employee_invitations", ["token_hash"], unique=True)
    op.execute("ALTER TABLE employee_invitations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE employee_invitations FORCE ROW LEVEL SECURITY")
    op.execute("""
      CREATE POLICY employee_invitations_scoped_access ON employee_invitations
      USING (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        OR token_hash = NULLIF(current_setting('app.invitation_token_hash', true), '')
      )
      WITH CHECK (
        company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
      )
    """)

def downgrade():
    op.drop_table("employee_invitations")
