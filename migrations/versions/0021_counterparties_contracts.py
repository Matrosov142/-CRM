"""Tenant-scoped counterparties and contract registry."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021_counterparties_contracts"
down_revision = "0020_finance_obligations"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("counterparties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("legal_name", sa.String(250), nullable=False),
        sa.Column("short_name", sa.String(200)),
        sa.Column("inn", sa.String(12)), sa.Column("kpp", sa.String(9)), sa.Column("ogrn", sa.String(15)),
        sa.Column("legal_address", sa.String(500)), sa.Column("actual_address", sa.String(500)),
        sa.Column("contact_name", sa.String(160)), sa.Column("email", sa.String(320)), sa.Column("phone", sa.String(40)),
        sa.Column("notes", sa.String(2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_counterparty_company_id_id"),
        sa.UniqueConstraint("company_id", "inn", name="uq_counterparty_company_inn"),
        sa.CheckConstraint("kind IN ('customer','supplier','both')", name="ck_counterparty_kind"),
        sa.CheckConstraint("status IN ('active','blocked')", name="ck_counterparty_status"),
        sa.CheckConstraint("inn IS NULL OR length(inn) IN (10,12)", name="ck_counterparty_inn_length"))
    op.create_index("ix_counterparties_company_name", "counterparties", ["company_id", "legal_name"])
    op.create_table("contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_number", sa.String(80), nullable=False), sa.Column("title", sa.String(250), nullable=False),
        sa.Column("contract_type", sa.String(12), nullable=False), sa.Column("signed_date", sa.DateTime(timezone=True)),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("auto_renewal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("renewal_notice_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("amount", sa.Numeric(14,2)), sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("responsible_name", sa.String(160)), sa.Column("notes", sa.String(2000), nullable=False, server_default=""),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "id", name="uq_contract_company_id_id"),
        sa.UniqueConstraint("company_id", "contract_number", name="uq_contract_company_number"),
        sa.ForeignKeyConstraint(["company_id", "counterparty_id"], ["counterparties.company_id", "counterparties.id"], ondelete="RESTRICT", name="fk_contract_counterparty_same_company"),
        sa.ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_contract_creator_same_company"),
        sa.CheckConstraint("contract_type IN ('customer','supplier','other')", name="ck_contract_type"),
        sa.CheckConstraint("status IN ('draft','active','suspended','terminated','expired')", name="ck_contract_status"),
        sa.CheckConstraint("currency = 'RUB'", name="ck_contract_currency_rub"),
        sa.CheckConstraint("amount IS NULL OR amount > 0", name="ck_contract_amount_positive"),
        sa.CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="ck_contract_dates"),
        sa.CheckConstraint("renewal_notice_days BETWEEN 0 AND 365", name="ck_contract_renewal_notice"))
    op.create_index("ix_contracts_company_ends", "contracts", ["company_id", "ends_at"])
    for table, policy in (("counterparties", "counterparties_tenant_access"), ("contracts", "contracts_tenant_access")):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {policy} ON {table} USING (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) WITH CHECK (company_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)")

def downgrade():
    op.execute("DROP POLICY IF EXISTS contracts_tenant_access ON contracts")
    op.execute("DROP POLICY IF EXISTS counterparties_tenant_access ON counterparties")
    op.drop_table("contracts")
    op.drop_table("counterparties")
