"""Contract documents and immutable file versions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0022_contract_documents"
down_revision = "0021_counterparties_contracts"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True)),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("document_kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_document_company_id_id"),
        sa.ForeignKeyConstraint(["company_id", "contract_id"], ["contracts.company_id", "contracts.id"], ondelete="RESTRICT", name="fk_document_contract_same_company"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_document_creator_same_company"),
        sa.CheckConstraint("document_kind IN ('contract','addendum','invoice','waybill','upd','act','specification','other')", name="ck_document_kind"),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_document_status"))
    op.create_table("document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("uploaded_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_document_version_company_id_id"),
        sa.UniqueConstraint("company_id", "document_id", "version_number", name="uq_document_version_number"),
        sa.ForeignKeyConstraint(["company_id", "document_id"], ["documents.company_id", "documents.id"], ondelete="RESTRICT", name="fk_document_version_document_same_company"),
        sa.ForeignKeyConstraint(["company_id", "uploaded_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_document_version_uploader_same_company"),
        sa.CheckConstraint("version_number > 0 AND size_bytes > 0", name="ck_document_version_positive"))
    op.create_index("ix_documents_company_contract", "documents", ["company_id", "contract_id"])
    op.create_index("ix_document_versions_company_document", "document_versions", ["company_id", "document_id", "version_number"])
    for table, policy in (("documents", "documents_tenant_access"), ("document_versions", "document_versions_tenant_access")):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {policy} ON {table} USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")
def downgrade():
    op.execute("DROP POLICY IF EXISTS document_versions_tenant_access ON document_versions")
    op.execute("DROP POLICY IF EXISTS documents_tenant_access ON documents")
    op.drop_table("document_versions")
    op.drop_table("documents")
