from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import ApprovalCreateRequest, OperationLimitRequest


def test_approval_amount_uses_exact_decimal_precision():
    payload = ApprovalCreateRequest(
        operation="purchase", amount="125000.35", reason="Закупка по заказу № 17"
    )
    assert payload.amount == Decimal("125000.35")


def test_approval_amount_rejects_more_than_two_decimal_places():
    with pytest.raises(ValidationError):
        ApprovalCreateRequest(
            operation="purchase", amount="125.999", reason="Проверка точности"
        )


def test_limit_amount_uses_decimal():
    payload = OperationLimitRequest(operation="payment", limit_amount="10000.10")
    assert payload.limit_amount == Decimal("10000.10")
