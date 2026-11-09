"""Pure validation rules for quality release and finished-goods batches."""
from decimal import Decimal


def validate_inspection(inspected: Decimal, good: Decimal, defective: Decimal, result: str) -> None:
    if min(inspected, good, defective) < 0 or inspected <= 0:
        raise ValueError("Количество проверки должно быть положительным, остальные количества — неотрицательными")
    if good + defective != inspected:
        raise ValueError("Годное количество и брак должны равняться проверенному количеству")
    if result not in {"pending", "passed", "failed", "rework"}:
        raise ValueError("Недопустимый результат контроля качества")
    if result == "passed" and good <= 0:
        raise ValueError("Нельзя выпустить партию без годной продукции")
    if result in {"failed", "rework"} and good > 0:
        raise ValueError("При результате «не пройдено» или «доработка» выпуск партии запрещён")


def validate_finished_goods_release(good_quantity: Decimal, released_quantity: Decimal, inspection_result: str) -> None:
    if inspection_result != "passed":
        raise ValueError("Готовую продукцию можно оприходовать только после успешного контроля качества")
    if good_quantity <= 0 or released_quantity <= 0:
        raise ValueError("Количество выпуска должно быть больше нуля")
    if released_quantity > good_quantity:
        raise ValueError("Нельзя выпустить больше годного количества по результатам контроля")
