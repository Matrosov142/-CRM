from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reservation_read_endpoint_exposes_line_ids_for_shipment():
    source = (ROOT / "app/routers/warehouse.py").read_text()
    assert '@router.get("/reservations")' in source
    assert 'StockReservationLine.reservation_id == reservation.id' in source
    assert '"quantity_remaining": str(Decimal(line.quantity) - Decimal(line.quantity_shipped))' in source
    assert '"id": str(line.id)' in source
    assert 'StockReservationLine.company_id == actor.company_id' in source
