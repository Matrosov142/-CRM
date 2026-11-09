import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, ForeignKey, UniqueConstraint, Numeric, JSON, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_membership_company_user"), UniqueConstraint("company_id", "id", name="uq_membership_company_id_id"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="director")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    company: Mapped[Company] = relationship()
    user: Mapped[User] = relationship()


class AuthSession(Base):
    """Server-side registry for revocable browser sessions."""
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class LoginFailure(Base):
    """Failed login attempt fingerprints; no raw email address or IP is stored."""
    __tablename__ = "login_failures"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    details: Mapped[dict] = mapped_column(__import__("sqlalchemy").JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EmployeeInvitation(Base):
    __tablename__ = "employee_invitations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EmployeePermissionOverride(Base):
    __tablename__ = "employee_permission_overrides"
    __table_args__ = (UniqueConstraint("company_id", "membership_id", "action", name="uq_employee_permission_override"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EmployeeOperationLimit(Base):
    __tablename__ = "employee_operation_limits"
    __table_args__ = (UniqueConstraint("company_id", "membership_id", "operation", name="uq_employee_operation_limit"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    limit_amount: Mapped[float] = mapped_column(__import__("sqlalchemy").Numeric(14, 2), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (UniqueConstraint("company_id", "id", name="uq_approval_request_company_id_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[float] = mapped_column(__import__("sqlalchemy").Numeric(14, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApprovalConsumption(Base):
    __tablename__ = "approval_consumptions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    approval_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("approval_requests.id", ondelete="RESTRICT"), nullable=False, unique=True)
    consumed_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False)
    consumed_entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    consumed_entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ProcurementOrder(Base):
    __tablename__ = "procurement_orders"
    __table_args__ = (
        UniqueConstraint("company_id", "order_number", name="uq_procurement_order_number"),
        UniqueConstraint("company_id", "id", name="uq_procurement_order_company_id_id"),
        UniqueConstraint("company_id", "source_rfq_id", "source_supplier_id", name="uq_procurement_order_rfq_supplier"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_procurement_created_by_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "authorized_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_procurement_authorized_by_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "approval_request_id"], ["approval_requests.company_id", "approval_requests.id"], ondelete="RESTRICT", name="fk_procurement_approval_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    order_number: Mapped[str] = mapped_column(String(40), nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    source_rfq_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    total_amount: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    authorized_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approval_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcurementOrderLine(Base):
    __tablename__ = "procurement_order_lines"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_procurement_order_line_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(
            ["company_id", "procurement_order_id"],
            ["procurement_orders.company_id", "procurement_orders.id"],
            ondelete="CASCADE",
            name="fk_procurement_line_order_same_company",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    procurement_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(__import__("sqlalchemy").Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14, 2), nullable=False)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("company_id", "inn", name="uq_supplier_company_inn"),
        UniqueConstraint("company_id", "id", name="uq_supplier_company_id_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_terms: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SupplierRFQ(Base):
    __tablename__ = "supplier_rfqs"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_supplier_rfq_company_id_id"),
        UniqueConstraint("company_id", "rfq_number", name="uq_supplier_rfq_number"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_rfq_creator_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    rfq_number: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    message: Mapped[str] = mapped_column(String(4000), nullable=False)
    response_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SupplierRFQLine(Base):
    __tablename__ = "supplier_rfq_lines"
    __table_args__ = (
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "rfq_id"], ["supplier_rfqs.company_id", "supplier_rfqs.id"], ondelete="CASCADE", name="fk_rfq_line_parent_same_company"),
        UniqueConstraint("rfq_id", "line_number", name="uq_rfq_line_number"),
        UniqueConstraint("company_id", "id", name="uq_rfq_line_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(
            ["company_id", "tender_id", "tender_position_id"],
            ["tender_positions.company_id", "tender_positions.tender_id", "tender_positions.id"],
            ondelete="RESTRICT", name="fk_rfq_line_tender_position_same_company"),
        __import__("sqlalchemy").CheckConstraint(
            "(tender_id IS NULL AND tender_position_id IS NULL) OR (tender_id IS NOT NULL AND tender_position_id IS NOT NULL)",
            name="ck_rfq_line_tender_link_pair"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    line_number: Mapped[int] = mapped_column(__import__("sqlalchemy").Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    specification: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    tender_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tender_position_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class SupplierRFQRecipient(Base):
    __tablename__ = "supplier_rfq_recipients"
    __table_args__ = (
        UniqueConstraint("company_id", "rfq_id", "supplier_id", name="uq_rfq_supplier"),
        UniqueConstraint("company_id", "id", name="uq_rfq_recipient_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "rfq_id"], ["supplier_rfqs.company_id", "supplier_rfqs.id"], ondelete="CASCADE", name="fk_rfq_recipient_rfq_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "supplier_id"], ["suppliers.company_id", "suppliers.id"], ondelete="RESTRICT", name="fk_rfq_recipient_supplier_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="prepared")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_supplier_offer_company_id_id"),
        UniqueConstraint("company_id", "rfq_id", "supplier_id", "version_no", name="uq_supplier_offer_version"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "rfq_id"], ["supplier_rfqs.company_id", "supplier_rfqs.id"], ondelete="CASCADE", name="fk_supplier_offer_rfq_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "supplier_id"], ["suppliers.company_id", "suppliers.id"], ondelete="RESTRICT", name="fk_supplier_offer_supplier_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "recipient_id"], ["supplier_rfq_recipients.company_id", "supplier_rfq_recipients.id"], ondelete="RESTRICT", name="fk_supplier_offer_recipient_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "supersedes_offer_id"], ["supplier_offers.company_id", "supplier_offers.id"], ondelete="RESTRICT", name="fk_supplier_offer_supersedes_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version_no: Mapped[int] = mapped_column(__import__("sqlalchemy").Integer, nullable=False, default=1)
    supersedes_offer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(__import__("sqlalchemy").Boolean, nullable=False, default=True)
    source_channel: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    supplier_offer_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(__import__("sqlalchemy").Integer, nullable=True)
    delivery_cost: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,2), nullable=False, default=Decimal("0.00"))
    vat_treatment: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    vat_amount: Mapped[Decimal | None] = mapped_column(__import__("sqlalchemy").Numeric(14,2), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_text: Mapped[str | None] = mapped_column(String(12000), nullable=True)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    review_note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SupplierOfferLine(Base):
    __tablename__ = "supplier_offer_lines"
    __table_args__ = (
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "offer_id"], ["supplier_offers.company_id", "supplier_offers.id"], ondelete="CASCADE", name="fk_supplier_offer_line_offer_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "rfq_line_id"], ["supplier_rfq_lines.company_id", "supplier_rfq_lines.id"], ondelete="RESTRICT", name="fk_supplier_offer_line_rfq_line_same_company"),
        UniqueConstraint("offer_id", "rfq_line_id", name="uq_supplier_offer_line_once"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rfq_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    offered_item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    offered_specification: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,2), nullable=False)
    specification_match: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class SupplierRFQSelection(Base):
    __tablename__ = "supplier_rfq_selections"
    __table_args__ = (
        UniqueConstraint("company_id", "rfq_line_id", name="uq_rfq_selection_line"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "rfq_id"], ["supplier_rfqs.company_id", "supplier_rfqs.id"], ondelete="CASCADE", name="fk_rfq_selection_rfq_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "rfq_line_id"], ["supplier_rfq_lines.company_id", "supplier_rfq_lines.id"], ondelete="CASCADE", name="fk_rfq_selection_line_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "offer_id"], ["supplier_offers.company_id", "supplier_offers.id"], ondelete="RESTRICT", name="fk_rfq_selection_offer_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    rfq_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rfq_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    offer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    selected_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

class WarehouseReceipt(Base):
    __tablename__ = "warehouse_receipts"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_warehouse_receipt_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "procurement_order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_receipt_order_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_receipt_creator_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_number: Mapped[str] = mapped_column(String(50), nullable=False)
    procurement_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    supplier_document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="accepted")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class WarehouseReceiptLine(Base):
    __tablename__ = "warehouse_receipt_lines"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_warehouse_receipt_line_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "receipt_id"], ["warehouse_receipts.company_id", "warehouse_receipts.id"], ondelete="CASCADE", name="fk_receipt_line_receipt_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "procurement_order_line_id"], ["procurement_order_lines.company_id", "procurement_order_lines.id"], ondelete="RESTRICT", name="fk_receipt_line_order_line_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    procurement_order_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    received_quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    accepted_quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    defective_quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    defect_note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")


class StockBatch(Base):
    __tablename__ = "stock_batches"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_stock_batch_company_id_id"),
        UniqueConstraint("company_id", "batch_number", name="uq_stock_batch_number"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "receipt_line_id"], ["warehouse_receipt_lines.company_id", "warehouse_receipt_lines.id"], ondelete="RESTRICT", name="fk_stock_batch_receipt_line_same_company"),
        __import__("sqlalchemy").CheckConstraint("quantity_received > 0 AND quantity_balance >= 0 AND quantity_balance <= quantity_received", name="ck_stock_batch_quantities"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    receipt_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    batch_number: Mapped[str] = mapped_column(String(60), nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    quantity_balance: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,2), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class StockReservation(Base):
    __tablename__ = "stock_reservations"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_stock_reservation_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_stock_reservation_creator_same_company"),
        __import__("sqlalchemy").CheckConstraint("status IN ('active', 'released')", name="ck_stock_reservation_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    released_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

class StockReservationLine(Base):
    __tablename__ = "stock_reservation_lines"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_stock_reservation_line_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "reservation_id"], ["stock_reservations.company_id", "stock_reservations.id"], ondelete="CASCADE", name="fk_stock_reservation_line_header_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "stock_batch_id"], ["stock_batches.company_id", "stock_batches.id"], ondelete="RESTRICT", name="fk_stock_reservation_line_batch_same_company"),
        __import__("sqlalchemy").CheckConstraint("quantity > 0", name="ck_stock_reservation_line_quantity_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    stock_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    quantity_shipped: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False, default=Decimal("0"))


class WarehouseShipment(Base):
    __tablename__ = "warehouse_shipments"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_warehouse_shipment_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "reservation_id"], ["stock_reservations.company_id", "stock_reservations.id"], ondelete="RESTRICT", name="fk_shipment_reservation_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_shipment_creator_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "delivery_estimate_id"], ["delivery_estimates.company_id", "delivery_estimates.id"], ondelete="RESTRICT", name="fk_shipment_delivery_estimate_same_company"),
        __import__("sqlalchemy").CheckConstraint("planned_delivery_cost IS NULL OR planned_delivery_cost >= 0", name="ck_shipment_planned_delivery_cost_nonnegative"),
        __import__("sqlalchemy").CheckConstraint("actual_delivery_cost IS NULL OR actual_delivery_cost >= 0", name="ck_shipment_actual_delivery_cost_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_number: Mapped[str] = mapped_column(String(60), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    shipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    carrier: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_estimate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    planned_delivery_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    actual_delivery_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    actual_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

class WarehouseShipmentLine(Base):
    __tablename__ = "warehouse_shipment_lines"
    __table_args__ = (
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "shipment_id"], ["warehouse_shipments.company_id", "warehouse_shipments.id"], ondelete="CASCADE", name="fk_shipment_line_header_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "reservation_line_id"], ["stock_reservation_lines.company_id", "stock_reservation_lines.id"], ondelete="RESTRICT", name="fk_shipment_line_reservation_line_same_company"),
        __import__("sqlalchemy").CheckConstraint("quantity > 0", name="ck_shipment_line_quantity_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reservation_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(60), nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)


class ProcessingJob(Base):
    """Tenant-scoped processing job mapped to migration 0017."""
    __tablename__ = "processing_jobs"
    __table_args__ = (
        UniqueConstraint("company_id", "job_number", name="uq_processing_job_number"),
        UniqueConstraint("company_id", "id", name="uq_processing_job_company_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_processing_job_order_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_processing_job_creator_same_company"),
        __import__("sqlalchemy").CheckConstraint("planned_quantity > 0 AND good_quantity >= 0 AND defective_quantity >= 0", name="ck_processing_job_quantities"),
        __import__("sqlalchemy").CheckConstraint("status IN ('planned','in_progress','completed','cancelled')", name="ck_processing_job_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_number: Mapped[str] = mapped_column(String(60), nullable=False)
    output_item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    defective_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    note: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProcessingOperation(Base):
    __tablename__ = "processing_operations"
    __table_args__ = (
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="CASCADE", name="fk_processing_operation_job_same_company"),
        __import__("sqlalchemy").CheckConstraint("operation_cost >= 0", name="ck_processing_operation_cost"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    operation_name: Mapped[str] = mapped_column(String(160), nullable=False)
    executor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    operation_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    good_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    defective_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    defect_note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")


class ProcessingMaterial(Base):
    __tablename__ = "processing_materials"
    __table_args__ = (
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="CASCADE", name="fk_processing_material_job_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "stock_batch_id"], ["stock_batches.company_id", "stock_batches.id"], ondelete="RESTRICT", name="fk_processing_material_batch_same_company"),
        __import__("sqlalchemy").CheckConstraint("planned_quantity > 0 AND (actual_quantity IS NULL OR actual_quantity >= 0) AND unit_cost_snapshot >= 0", name="ck_processing_material_quantities"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    stock_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    planned_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    actual_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit_cost_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class QualityInspection(Base):
    __tablename__ = "quality_inspections"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_quality_inspection_company_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="RESTRICT", name="fk_quality_inspection_job_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "inspected_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_quality_inspection_inspector_same_company"),
        __import__("sqlalchemy").CheckConstraint("inspected_quantity > 0 AND good_quantity >= 0 AND defective_quantity >= 0 AND good_quantity + defective_quantity = inspected_quantity", name="ck_quality_inspection_quantities"),
        __import__("sqlalchemy").CheckConstraint("result IN ('pending','passed','failed','rework')", name="ck_quality_inspection_result"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    inspection_number: Mapped[str] = mapped_column(String(60), nullable=False)
    inspected_quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    defective_quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    defect_description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    inspected_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class FinishedGoodsBatch(Base):
    __tablename__ = "finished_goods_batches"
    __table_args__ = (
        UniqueConstraint("company_id", "batch_number", name="uq_finished_goods_batch_number"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "job_id"], ["processing_jobs.company_id", "processing_jobs.id"], ondelete="RESTRICT", name="fk_finished_goods_job_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "inspection_id"], ["quality_inspections.company_id", "quality_inspections.id"], ondelete="RESTRICT", name="fk_finished_goods_inspection_same_company"),
        __import__("sqlalchemy").CheckConstraint("quantity > 0 AND quantity_available >= 0 AND quantity_available <= quantity", name="ck_finished_goods_batch_quantities"),
        __import__("sqlalchemy").CheckConstraint("status IN ('available','reserved','shipped','blocked')", name="ck_finished_goods_batch_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    inspection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(60), nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    quantity_available: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class FinanceMovement(Base):
    """Tenant-scoped cash movement; only confirmed entries affect cash reports."""
    __tablename__ = "finance_movements"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_finance_movement_company_id"),
        UniqueConstraint("company_id", "movement_number", name="uq_finance_movement_number"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_movement_creator_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "confirmed_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_movement_confirmer_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "procurement_order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_finance_movement_order_same_company"),
        __import__("sqlalchemy").CheckConstraint("kind IN ('receipt','payment')", name="ck_finance_movement_kind"),
        __import__("sqlalchemy").CheckConstraint("status IN ('draft','confirmed','cancelled')", name="ck_finance_movement_status"),
        __import__("sqlalchemy").CheckConstraint("amount > 0", name="ck_finance_movement_amount_positive"),
        __import__("sqlalchemy").CheckConstraint("currency = 'RUB'", name="ck_finance_movement_rub_only"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_number: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")
    amount: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    movement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    counterparty_name: Mapped[str] = mapped_column(String(200), nullable=False)
    counterparty_inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    purpose: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    document_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    procurement_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    confirmed_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FinanceObligation(Base):
    """Tenant-scoped receivable/payable obligation; settlement is allocation-based."""
    __tablename__ = "finance_obligations"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_finance_obligation_company_id"),
        UniqueConstraint("company_id", "obligation_number", name="uq_finance_obligation_number"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_obligation_creator_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "procurement_order_id"], ["procurement_orders.company_id", "procurement_orders.id"], ondelete="RESTRICT", name="fk_finance_obligation_order_same_company"),
        __import__("sqlalchemy").CheckConstraint("side IN ('receivable','payable')", name="ck_finance_obligation_side"),
        __import__("sqlalchemy").CheckConstraint("amount > 0", name="ck_finance_obligation_amount_positive"),
        __import__("sqlalchemy").CheckConstraint("currency = 'RUB'", name="ck_finance_obligation_rub_only"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    obligation_number: Mapped[str] = mapped_column(String(60), nullable=False)
    side: Mapped[str] = mapped_column(String(12), nullable=False)
    amount: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    counterparty_name: Mapped[str] = mapped_column(String(200), nullable=False)
    counterparty_inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    procurement_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

class FinanceAllocation(Base):
    """Allocation of a confirmed cash movement to one obligation."""
    __tablename__ = "finance_allocations"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_finance_allocation_company_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "obligation_id"], ["finance_obligations.company_id", "finance_obligations.id"], ondelete="RESTRICT", name="fk_finance_allocation_obligation_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "movement_id"], ["finance_movements.company_id", "finance_movements.id"], ondelete="RESTRICT", name="fk_finance_allocation_movement_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_finance_allocation_creator_same_company"),
        __import__("sqlalchemy").CheckConstraint("amount > 0", name="ck_finance_allocation_amount_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    obligation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    movement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(__import__("sqlalchemy").Numeric(14,2), nullable=False)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

class Counterparty(Base):
    __tablename__ = "counterparties"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_counterparty_company_id_id"),
        UniqueConstraint("company_id", "inn", name="uq_counterparty_company_inn"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(250), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(15), nullable=True)
    legal_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actual_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_contract_company_id_id"),
        UniqueConstraint("company_id", "contract_number", name="uq_contract_company_number"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "counterparty_id"], ["counterparties.company_id", "counterparties.id"], ondelete="RESTRICT", name="fk_contract_counterparty_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_contract_creator_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    contract_number: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(12), nullable=False)
    signed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    renewal_notice_days: Mapped[int] = mapped_column(__import__("sqlalchemy").Integer, nullable=False, default=30)
    amount: Mapped[Decimal | None] = mapped_column(__import__("sqlalchemy").Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    responsible_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_document_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "contract_id"], ["contracts.company_id", "contracts.id"], ondelete="RESTRICT", name="fk_document_contract_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "created_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_document_creator_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    document_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_document_version_company_id_id"),
        UniqueConstraint("company_id", "document_id", "version_number", name="uq_document_version_number"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "document_id"], ["documents.company_id", "documents.id"], ondelete="RESTRICT", name="fk_document_version_document_same_company"),
        __import__("sqlalchemy").ForeignKeyConstraint(["company_id", "uploaded_by_membership_id"], ["memberships.company_id", "memberships.id"], ondelete="RESTRICT", name="fk_document_version_uploader_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(__import__("sqlalchemy").Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(__import__("sqlalchemy").BigInteger, nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    uploaded_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Tender(Base):
    """Company-scoped tender register; imported source data is reviewed by a human."""
    __tablename__ = "tenders"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_tender_company_id_id"),
        UniqueConstraint("company_id", "platform", "tender_number", name="uq_tender_company_platform_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    tender_number: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(250), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    initial_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_region: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="new")
    prospectivity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    responsible_membership_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str] = mapped_column(String(4000), nullable=False, default="")
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class TenderPosition(Base):
    """A requested item within a tender; scoped to the same tenant as its tender."""
    __tablename__ = "tender_positions"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_tender_position_company_id_id"),
        UniqueConstraint("company_id", "tender_id", "id", name="uq_tender_position_company_tender_id"),
        UniqueConstraint("company_id", "tender_id", "line_number", name="uq_tender_position_line"),
        __import__("sqlalchemy").ForeignKeyConstraint(
            ["company_id", "tender_id"], ["tenders.company_id", "tenders.id"],
            ondelete="CASCADE", name="fk_tender_position_same_company"),
        __import__("sqlalchemy").CheckConstraint("quantity > 0", name="ck_tender_position_quantity_positive"),
        __import__("sqlalchemy").CheckConstraint("estimated_unit_price IS NULL OR estimated_unit_price >= 0", name="ck_tender_position_price_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    specification: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False, default="шт.")
    estimated_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TenderPositionPricingVersion(Base):
    """Immutable, tenant-scoped snapshot of a manual tender position pricing calculation."""
    __tablename__ = "tender_position_pricing_versions"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_tender_pricing_company_id_id"),
        UniqueConstraint("company_id", "position_id", "version", name="uq_tender_pricing_position_version"),
        __import__("sqlalchemy").ForeignKeyConstraint(
            ["company_id", "tender_id", "position_id"],
            ["tender_positions.company_id", "tender_positions.tender_id", "tender_positions.id"],
            ondelete="CASCADE", name="fk_tender_pricing_same_company_position"),
        __import__("sqlalchemy").ForeignKeyConstraint(
            ["company_id", "created_by_membership_id"],
            ["memberships.company_id", "memberships.id"],
            ondelete="RESTRICT", name="fk_tender_pricing_creator_same_company"),
        __import__("sqlalchemy").CheckConstraint("version > 0", name="ck_tender_pricing_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    tender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    position_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DeliveryEstimate(Base):
    __tablename__ = "delivery_estimates"
    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_delivery_estimate_company_id_id"),
        __import__("sqlalchemy").ForeignKeyConstraint(
            ["company_id", "created_by_membership_id"],
            ["memberships.company_id", "memberships.id"],
            ondelete="RESTRICT", name="fk_delivery_estimate_creator_same_company"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    origin: Mapped[str] = mapped_column(String(300), nullable=False)
    destination: Mapped[str] = mapped_column(String(300), nullable=False)
    distance_km_one_way: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cargo_description: Mapped[str] = mapped_column(String(500), nullable=False)
    cargo_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    cargo_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    options: Mapped[list] = mapped_column(JSON, nullable=False)
    selected_option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
