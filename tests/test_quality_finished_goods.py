from decimal import Decimal
import pytest
from app.quality import validate_inspection, validate_finished_goods_release


def test_passed_inspection_allows_good_output():
    validate_inspection(Decimal("10"), Decimal("9"), Decimal("1"), "passed")
    validate_finished_goods_release(Decimal("9"), Decimal("9"), "passed")


def test_inspection_quantities_must_reconcile():
    with pytest.raises(ValueError):
        validate_inspection(Decimal("10"), Decimal("8"), Decimal("1"), "passed")


def test_failed_inspection_cannot_release_batch():
    with pytest.raises(ValueError):
        validate_finished_goods_release(Decimal("5"), Decimal("5"), "failed")


def test_release_cannot_exceed_accepted_quantity():
    with pytest.raises(ValueError):
        validate_finished_goods_release(Decimal("4"), Decimal("4.001"), "passed")


def test_passed_result_requires_good_quantity():
    with pytest.raises(ValueError):
        validate_inspection(Decimal("2"), Decimal("0"), Decimal("2"), "passed")
