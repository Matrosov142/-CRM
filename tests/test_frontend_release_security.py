from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_access_token_is_not_persisted_in_browser_storage():
    app = (ROOT / "frontend/src/App.tsx").read_text()
    assert "localStorage" not in app
    assert "sessionStorage" not in app
    assert "useState('')" in app

def test_delivery_estimate_id_is_saved_and_shipment_actual_cost_is_editable():
    app = (ROOT / "frontend/src/App.tsx").read_text()
    assert "setDeliveryEstimateId(data.id)" in app
    assert "/api/v1/warehouse/shipments" in app
    assert "actual-delivery-cost" in app
    assert "Сохранить факт" in app

def test_frontend_has_no_literal_backslash_newline_type_declaration():
    app = (ROOT / "frontend/src/App.tsx").read_text()
    assert r"\\ntype DeliveryHistory" not in app
    assert "\ntype DeliveryHistory" in app
