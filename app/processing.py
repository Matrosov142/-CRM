"""Pure processing calculations. Persistence and stock write-off are intentionally separate."""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass

QTY = Decimal("0.001")
MONEY = Decimal("0.01")

@dataclass(frozen=True)
class MaterialConsumption:
    item_name: str
    quantity: Decimal
    unit_cost: Decimal


def calculate_material_cost(materials: list[MaterialConsumption]) -> Decimal:
    total = Decimal("0")
    for material in materials:
        if material.quantity < 0 or material.unit_cost < 0:
            raise ValueError("Количество и цена материала не могут быть отрицательными")
        total += material.quantity * material.unit_cost
    return total.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_unit_cost(material_cost: Decimal, operation_cost: Decimal, output_quantity: Decimal) -> Decimal:
    if material_cost < 0 or operation_cost < 0:
        raise ValueError("Себестоимость не может быть отрицательной")
    if output_quantity <= 0:
        raise ValueError("Количество готовой продукции должно быть больше нуля")
    return ((material_cost + operation_cost) / output_quantity).quantize(MONEY, rounding=ROUND_HALF_UP)


def validate_quality(good_quantity: Decimal, defective_quantity: Decimal, processed_quantity: Decimal) -> None:
    if min(good_quantity, defective_quantity, processed_quantity) < 0:
        raise ValueError("Количество не может быть отрицательным")
    if good_quantity + defective_quantity != processed_quantity:
        raise ValueError("Годное количество и брак должны равняться обработанному количеству")
