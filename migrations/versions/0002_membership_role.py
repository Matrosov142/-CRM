"""Add role to company memberships."""
from alembic import op
import sqlalchemy as sa

revision = "0002_membership_role"
down_revision = "0001_initial_core"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("memberships", sa.Column("role", sa.String(length=30), nullable=False, server_default="director"))

def downgrade():
    op.drop_column("memberships", "role")
