"""Add privacy-preserving persistent login failure throttling."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0026_login_failure_throttle"
down_revision = "0025_auth_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_login_failures_email_hash", "login_failures", ["email_hash"])
    op.create_index("ix_login_failures_ip_hash", "login_failures", ["ip_hash"])
    op.create_index("ix_login_failures_attempted_at", "login_failures", ["attempted_at"])
    # Global/pre-tenant table. Stores keyed digests only, never raw email or IP.


def downgrade():
    op.drop_index("ix_login_failures_attempted_at", table_name="login_failures")
    op.drop_index("ix_login_failures_ip_hash", table_name="login_failures")
    op.drop_index("ix_login_failures_email_hash", table_name="login_failures")
    op.drop_table("login_failures")
