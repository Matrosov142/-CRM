from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.controls import _money, require_operation_authorization


def test_money_normalizes_decimal_and_rejects_negative():
    assert _money("125.5") == Decimal("125.50")
    with pytest.raises(HTTPException) as error:
        _money("-0.01")
    assert error.value.status_code == 422


def test_money_rejects_nan():
    with pytest.raises(HTTPException):
        _money("NaN")


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDB:
    def __init__(self, *values):
        self.values = list(values)
        self.flushed = False
        self.audit = []

    def execute(self, statement):
        return Result(self.values.pop(0))

    def flush(self):
        self.flushed = True


def actor():
    return SimpleNamespace(id=uuid4(), company_id=uuid4(), user_id=uuid4(), status="active")


def test_operation_under_limit_needs_no_approval():
    employee = actor()
    db = FakeDB(SimpleNamespace(limit_amount=Decimal("5000.00")))
    assert require_operation_authorization(db, employee, "purchase", "4999.99") is None
    assert db.values == []


def test_missing_limit_fails_closed():
    employee = actor()
    db = FakeDB(None)
    with pytest.raises(HTTPException) as error:
        require_operation_authorization(db, employee, "payment", 100)
    assert error.value.status_code == 409


def test_over_limit_without_approval_is_blocked():
    employee = actor()
    db = FakeDB(SimpleNamespace(limit_amount=Decimal("100.00")))
    with pytest.raises(HTTPException) as error:
        require_operation_authorization(db, employee, "purchase", 100.01)
    assert error.value.status_code == 403


def test_unsupported_operation_is_rejected():
    employee = actor()
    db = FakeDB()
    with pytest.raises(HTTPException) as error:
        require_operation_authorization(db, employee, "unknown", 1)
    assert error.value.status_code == 422
