"""Add user-agent metadata for browser session management."""
from alembic import op
import sqlalchemy as sa

revision = "0027_auth_session_device_metadata"
down_revision = "0026_login_failure_throttle"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("auth_sessions", sa.Column("user_agent", sa.String(length=500), nullable=True))

def downgrade():
    op.drop_column("auth_sessions", "user_agent")
