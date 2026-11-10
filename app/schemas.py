from pydantic import BaseModel, EmailStr, Field, model_validator
from decimal import Decimal
from datetime import datetime
from uuid import UUID

class RegisterCompanyRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    company_id: UUID | None = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    company_id: UUID
    role: str

class CompanyResponse(BaseModel):
    id: UUID
    name: str
    status: str
    model_config = {"from_attributes": True}


class EmployeeInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(min_length=3, max_length=30)

class EmployeeInviteResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    expires_at: str
    invitation_token: str
    delivery_status: str = "Требуется передать сотруднику вручную"

class AcceptEmployeeInviteRequest(BaseModel):
    invitation_token: str = Field(min_length=40, max_length=128)
    password: str = Field(min_length=12, max_length=128)

class EmployeeResponse(BaseModel):
    id: UUID
    membership_id: UUID
    email: EmailStr
    role: str
    status: str


class EmployeeRoleUpdateRequest(BaseModel):
    role: str = Field(min_length=3, max_length=30)


class PermissionOverrideRequest(BaseModel):
    action: str = Field(min_length=3, max_length=80)
    allowed: bool

class OperationLimitRequest(BaseModel):
    operation: str = Field(min_length=3, max_length=40)
    limit_amount: Decimal = Field(ge=Decimal("0.00"), max_digits=14, decimal_places=2)

class ApprovalCreateRequest(BaseModel):
    operation: str = Field(min_length=3, max_length=40)
    amount: Decimal = Field(gt=Decimal("0.00"), max_digits=14, decimal_places=2)
    reason: str = Field(min_length=5, max_length=1000)

class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str = Field(default="", max_length=1000)


class ProcurementOrderLineCreate(BaseModel):
    item_name: str = Field(min_length=2, max_length=300)
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)


class ProcurementOrderCreate(BaseModel):
    order_number: str = Field(min_length=1, max_length=40)
    supplier_name: str = Field(min_length=2, max_length=200)
    supplier_inn: str | None = Field(default=None, pattern=r"^\d{10}(?:\d{2})?$", max_length=12)
    lines: list[ProcurementOrderLineCreate] = Field(min_length=1, max_length=100)


class ProcurementOrderPlaceRequest(BaseModel):
    approval_request_id: UUID | None = None


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    inn: str | None = Field(default=None, pattern=r"^\d{10}(?:\d{2})?$", max_length=12)
    kpp: str | None = Field(default=None, pattern=r"^\d{9}$", max_length=9)
    contact_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)
    payment_terms: str | None = Field(default=None, max_length=500)
    delivery_terms: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class SupplierUpdateRequest(SupplierCreateRequest):
    status: str = Field(default="active", pattern="^(active|blocked)$")


class SupplierRFQLineCreate(BaseModel):
    item_name: str = Field(min_length=2, max_length=300)
    specification: str | None = Field(default=None, max_length=2000)
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    tender_id: UUID | None = None
    tender_position_id: UUID | None = None

    @model_validator(mode="after")
    def validate_tender_link_pair(self):
        if (self.tender_id is None) != (self.tender_position_id is None):
            raise ValueError("Для связи с тендером необходимо указать и тендер, и его позицию")
        return self


class SupplierRFQCreateRequest(BaseModel):
    rfq_number: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=2, max_length=250)
    message: str = Field(min_length=5, max_length=4000)
    response_deadline: datetime | None = None
    supplier_ids: list[UUID] = Field(min_length=1, max_length=50)
    lines: list[SupplierRFQLineCreate] = Field(min_length=1, max_length=100)


class SupplierOfferLineInput(BaseModel):
    rfq_line_id: UUID
    offered_item_name: str = Field(min_length=1, max_length=300)
    offered_specification: str | None = Field(default=None, max_length=2000)
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    specification_match: str = Field(default="unknown", pattern="^(match|mismatch|unknown)$")
    note: str | None = Field(default=None, max_length=1000)


class SupplierOfferCreateRequest(BaseModel):
    supplier_id: UUID
    source_channel: str = Field(default="manual", pattern="^(manual|email|telegram|upload)$")
    supplier_offer_number: str | None = Field(default=None, max_length=80)
    received_at: datetime | None = None
    valid_until: datetime | None = None
    delivery_days: int | None = Field(default=None, ge=0, le=3650)
    delivery_cost: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), max_digits=14, decimal_places=2)
    vat_treatment: str = Field(default="unknown", pattern="^(included|excluded|no_vat|unknown)$")
    vat_amount: Decimal | None = Field(default=None, ge=Decimal("0.00"), max_digits=14, decimal_places=2)
    payment_terms: str | None = Field(default=None, max_length=1000)
    original_text: str | None = Field(default=None, max_length=12000)
    lines: list[SupplierOfferLineInput] = Field(min_length=1, max_length=100)

class SupplierOfferReviewRequest(BaseModel):
    decision: str = Field(pattern="^(confirmed|rejected)$")
    note: str = Field(default="", max_length=1000)

class SupplierOfferSelectionRequest(BaseModel):
    offer_id: UUID
    rfq_line_id: UUID
    note: str = Field(default="", max_length=1000)

class WarehouseReceiptLineInput(BaseModel):
    procurement_order_line_id: UUID
    received_quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    accepted_quantity: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=3)
    defective_quantity: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=3)
    defect_note: str = Field(default="", max_length=1000)

class WarehouseReceiptCreateRequest(BaseModel):
    receipt_number: str = Field(min_length=1, max_length=50)
    procurement_order_id: UUID
    received_at: datetime | None = None
    supplier_document_number: str | None = Field(default=None, max_length=100)
    note: str = Field(default="", max_length=2000)
    location: str | None = Field(default=None, max_length=120)
    lines: list[WarehouseReceiptLineInput] = Field(min_length=1, max_length=100)


class StockReservationLineInput(BaseModel):
    stock_batch_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)

class StockReservationCreateRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=1000)
    lines: list[StockReservationLineInput] = Field(min_length=1, max_length=100)

class StockReservationReleaseRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class WarehouseShipmentLineInput(BaseModel):
    reservation_line_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)

class WarehouseShipmentCreateRequest(BaseModel):
    shipment_number: str = Field(min_length=1, max_length=60)
    reservation_id: UUID
    shipped_at: datetime | None = None
    carrier: str | None = Field(default=None, max_length=160)
    tracking_number: str | None = Field(default=None, max_length=120)
    destination: str | None = Field(default=None, max_length=500)
    delivery_estimate_id: UUID | None = None
    note: str = Field(default="", max_length=2000)
    lines: list[WarehouseShipmentLineInput] = Field(min_length=1, max_length=100)

class ShipmentActualDeliveryCostRequest(BaseModel):
    actual_cost: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    delivered_at: datetime | None = None
    note: str = Field(default="", max_length=1000)

class ProcessingMaterialInput(BaseModel):
    stock_batch_id: UUID
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)

class ProcessingJobCreateRequest(BaseModel):
    job_number: str = Field(min_length=1, max_length=60)
    order_id: UUID
    output_item_name: str = Field(min_length=2, max_length=300)
    planned_quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    materials: list[ProcessingMaterialInput] = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=2000)

class ProcessingOperationInput(BaseModel):
    operation_name: str = Field(min_length=2, max_length=160)
    executor_name: str = Field(min_length=2, max_length=160)
    operation_cost: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    started_at: datetime | None = None
    completed_at: datetime | None = None

class ProcessingResultInput(BaseModel):
    processed_quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    good_quantity: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=3)
    defective_quantity: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=3)
    defect_note: str = Field(default="", max_length=1000)


class QualityInspectionCreate(BaseModel):
    job_id: UUID
    inspection_number: str = Field(min_length=1, max_length=60)
    inspected_quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    good_quantity: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=3)
    defective_quantity: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=3)
    result: str = Field(pattern="^(pending|passed|failed|rework)$")
    defect_description: str = Field(default="", max_length=2000)


class FinishedGoodsBatchCreate(BaseModel):
    job_id: UUID
    inspection_id: UUID
    batch_number: str = Field(min_length=1, max_length=60)
    item_name: str = Field(min_length=2, max_length=300)
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)
    unit_cost: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    location: str | None = Field(default=None, max_length=120)


class FinanceMovementCreateRequest(BaseModel):
    movement_number: str = Field(min_length=1, max_length=60)
    kind: str = Field(pattern="^(receipt|payment)$")
    amount: Decimal = Field(gt=Decimal("0.00"), max_digits=14, decimal_places=2)
    movement_date: datetime
    counterparty_name: str = Field(min_length=2, max_length=200)
    counterparty_inn: str | None = Field(default=None, pattern=r"^\d{10}(?:\d{2})?$", max_length=12)
    purpose: str = Field(default="", max_length=1000)
    document_reference: str | None = Field(default=None, max_length=120)
    procurement_order_id: UUID | None = None

class FinanceMovementCancelRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class FinanceObligationCreateRequest(BaseModel):
    obligation_number: str = Field(min_length=1, max_length=60)
    side: str = Field(pattern="^(receivable|payable)$")
    amount: Decimal = Field(gt=Decimal("0.00"), max_digits=14, decimal_places=2)
    counterparty_name: str = Field(min_length=2, max_length=200)
    counterparty_inn: str | None = Field(default=None, pattern=r"^\d{10}(?:\d{2})?$", max_length=12)
    description: str = Field(default="", max_length=1000)
    due_date: datetime
    procurement_order_id: UUID | None = None

class FinanceAllocationCreateRequest(BaseModel):
    movement_id: UUID
    amount: Decimal = Field(gt=Decimal("0.00"), max_digits=14, decimal_places=2)

class CounterpartyCreateRequest(BaseModel):
    kind: str = Field(pattern="^(customer|supplier|both)$")
    legal_name: str = Field(min_length=2, max_length=250)
    short_name: str | None = Field(default=None, max_length=200)
    inn: str | None = Field(default=None, pattern=r"^\d{10}(?:\d{2})?$", max_length=12)
    kpp: str | None = Field(default=None, pattern=r"^\d{9}$", max_length=9)
    ogrn: str | None = Field(default=None, pattern=r"^\d{13}(?:\d{2})?$", max_length=15)
    legal_address: str | None = Field(default=None, max_length=500)
    actual_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    notes: str = Field(default="", max_length=2000)

class CounterpartyUpdateRequest(BaseModel):
    short_name: str | None = Field(default=None, max_length=200)
    legal_address: str | None = Field(default=None, max_length=500)
    actual_address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(active|blocked)$")

class ContractCreateRequest(BaseModel):
    counterparty_id: UUID
    contract_number: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=250)
    contract_type: str = Field(pattern="^(customer|supplier|other)$")
    signed_date: datetime | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    auto_renewal: bool = False
    renewal_notice_days: int = Field(default=30, ge=0, le=365)
    amount: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=14, decimal_places=2)
    responsible_name: str | None = Field(default=None, max_length=160)
    notes: str = Field(default="", max_length=2000)

class ContractStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(draft|active|suspended|terminated|expired)$")


class TenderCreateRequest(BaseModel):
    platform: str = Field(min_length=2, max_length=40)
    tender_number: str = Field(min_length=1, max_length=100)
    customer_name: str = Field(min_length=2, max_length=250)
    subject: str = Field(min_length=3, max_length=500)
    initial_price: Decimal = Field(ge=Decimal("0"), max_digits=14, decimal_places=2)
    deadline: datetime
    delivery_region: str | None = Field(default=None, max_length=160)
    status: str = Field(default="new", pattern="^(new|analysis|preparing|submitted|won|lost|cancelled)$")
    prospectivity: str = Field(default="medium", pattern="^(high|medium|low)$")
    responsible_membership_id: UUID | None = None
    notes: str = Field(default="", max_length=4000)

class TenderUpdateRequest(BaseModel):
    customer_name: str | None = Field(default=None, min_length=2, max_length=250)
    subject: str | None = Field(default=None, min_length=3, max_length=500)
    initial_price: Decimal | None = Field(default=None, ge=Decimal("0"), max_digits=14, decimal_places=2)
    deadline: datetime | None = None
    delivery_region: str | None = Field(default=None, max_length=160)
    status: str | None = Field(default=None, pattern="^(new|analysis|preparing|submitted|won|lost|cancelled)$")
    prospectivity: str | None = Field(default=None, pattern="^(high|medium|low)$")
    responsible_membership_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)


class TenderPositionCreateRequest(BaseModel):
    item_name: str = Field(min_length=2, max_length=300)
    specification: str = Field(default="", max_length=2000)
    quantity: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=3)
    unit: str = Field(default="шт.", min_length=1, max_length=30)
    estimated_unit_price: Decimal | None = Field(default=None, ge=Decimal("0"), max_digits=14, decimal_places=2)
    notes: str = Field(default="", max_length=1000)

class TenderPositionPricingRequest(BaseModel):
    purchase: Decimal = Field(gt=Decimal("0"), max_digits=14, decimal_places=2)
    logistics: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    processing: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    packaging: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    tax: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    other: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), max_digits=14, decimal_places=2)
    conservative_margin: Decimal = Field(default=Decimal("10"), ge=Decimal("0"), lt=Decimal("100"), max_digits=5, decimal_places=2)
    target_margin: Decimal = Field(default=Decimal("20"), ge=Decimal("0"), lt=Decimal("100"), max_digits=5, decimal_places=2)
    aggressive_margin: Decimal = Field(default=Decimal("30"), ge=Decimal("0"), lt=Decimal("100"), max_digits=5, decimal_places=2)


class TenderPositionUpdateRequest(BaseModel):
    item_name: str | None = Field(default=None, min_length=2, max_length=300)
    specification: str | None = Field(default=None, max_length=2000)
    quantity: Decimal | None = Field(default=None, gt=Decimal("0"), max_digits=14, decimal_places=3)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    estimated_unit_price: Decimal | None = Field(default=None, ge=Decimal("0"), max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=1000)
