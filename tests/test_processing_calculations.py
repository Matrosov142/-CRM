from decimal import Decimal as D
import pytest
from app.processing import MaterialConsumption, calculate_material_cost, calculate_unit_cost, validate_quality

def test_material_cost():
    assert calculate_material_cost([MaterialConsumption("Сталь", D("2.5"), D("100.00")), MaterialConsumption("Крепёж", D("3"), D("4.50"))]) == D("263.50")

def test_unit_cost():
    assert calculate_unit_cost(D("263.50"), D("36.50"), D("10")) == D("30.00")

def test_zero_output_rejected():
    with pytest.raises(ValueError): calculate_unit_cost(D("1"), D("1"), D("0"))

def test_quality_reconciliation():
    validate_quality(D("9"), D("1"), D("10"))
    with pytest.raises(ValueError): validate_quality(D("9"), D("2"), D("10"))
