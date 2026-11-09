"""Add append-only audit events and tenant RLS."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_rbac_audit"
down_revision = "0003_tenant_rls"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False, server_default="success"),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("outcome IN ('success', 'denied', 'failure')", name="ck_audit_outcome"),
    )
    op.create_index("ix_audit_events_company_id", "audit_events", ["company_id"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY audit_events_tenant_access ON audit_events
        USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)
    # Reject UPDATE/DELETE at database level for audit immutability.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events are append-only';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_events_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation()
    """)

def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_mutation()")
    op.drop_table("audit_events")
