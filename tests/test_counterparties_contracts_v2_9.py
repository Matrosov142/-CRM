from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from pydantic import ValidationError
from app.schemas import CounterpartyCreateRequest, ContractCreateRequest, ContractStatusUpdateRequest


def test_counterparty_schema_accepts_customer_and_inn():
    obj = CounterpartyCreateRequest(kind="customer", legal_name="ООО Ромашка", inn="1234567890")
    assert obj.kind == "customer"
    assert obj.inn == "1234567890"


def test_counterparty_schema_rejects_invalid_inn():
    with pytest.raises(ValidationError):
        CounterpartyCreateRequest(kind="supplier", legal_name="ООО Поставщик", inn="123")


def test_contract_schema_rub_amount_and_notice():
    obj = ContractCreateRequest(
        counterparty_id="00000000-0000-0000-0000-000000000001",
        contract_number="Д-001", title="Поставка оборудования", contract_type="supplier",
        starts_at=datetime.now(timezone.utc), amount=Decimal("125000.50"), renewal_notice_days=45,
    )
    assert obj.amount == Decimal("125000.50")
    assert obj.renewal_notice_days == 45


def test_contract_schema_rejects_bad_contract_type():
    with pytest.raises(ValidationError):
        ContractCreateRequest(
            counterparty_id="00000000-0000-0000-0000-000000000001",
            contract_number="D1", title="Тест", contract_type="unknown",
            starts_at=datetime.now(timezone.utc),
        )


def test_contract_status_is_limited():
    assert ContractStatusUpdateRequest(status="active").status == "active"
    with pytest.raises(ValidationError):
        ContractStatusUpdateRequest(status="signed")


def test_migration_has_tenant_rls_and_same_company_fk():
    from pathlib import Path
    migration = Path("migrations/versions/0021_counterparties_contracts.py").read_text()
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "fk_contract_counterparty_same_company" in migration
    assert "ck_contract_currency_rub" in migration
