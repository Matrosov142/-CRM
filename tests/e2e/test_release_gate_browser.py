from __future__ import annotations

import os
import uuid
from decimal import Decimal

from playwright.sync_api import sync_playwright

BASE = os.getenv("POTOK_E2E_BASE_URL", "http://127.0.0.1:18080")
UNTRUSTED = os.getenv("POTOK_E2E_UNTRUSTED_URL", "http://127.0.0.1:18081")
PASSWORD = "E2E-only-Secret-42!"


def api(page, path, method="GET", payload=None, *, csrf=True, content_type="application/json", headers=None, raw=None):
    return page.evaluate("""async ({path, method, payload, csrf, contentType, headers, raw}) => {
      const h = {...(headers || {})};
      if (payload !== null && payload !== undefined && contentType) h['Content-Type'] = contentType;
      if (csrf) { const m = document.cookie.match(/(?:^|; )potok_csrf=([^;]+)/); if (m) h['X-CSRF-Token'] = decodeURIComponent(m[1]); }
      const r = await fetch(path, {method, credentials:'include', headers:h,
        body: raw !== null ? raw : (payload == null ? undefined : JSON.stringify(payload))});
      const t = await r.text(); let body; try { body = JSON.parse(t); } catch { body = t; }
      return {status:r.status, body};
    }""", {"path":path,"method":method,"payload":payload,"csrf":csrf,"contentType":content_type,"headers":headers,"raw":raw})


def expect(result, status=200):
    assert result["status"] == status, f"HTTP {result['status']} expected {status}: {result['body']}"
    return result["body"]


def register(page, company, email):
    page.goto(BASE, wait_until="networkidle")
    page.get_by_role("button", name="Создать компанию").first.click()
    page.get_by_label("Название компании").fill(company)
    page.get_by_label("Электронная почта").fill(email)
    page.get_by_label("Пароль").fill(PASSWORD)
    page.locator("form button.primary").click()
    try:
        page.get_by_role("heading", name="Панель директора").wait_for(timeout=15000)
    except Exception as exc:
        raise AssertionError(f"Browser registration did not establish a session. UI={page.locator('body').inner_text()} cookies={owner_cookies(page)}") from exc


def owner_cookies(page):
    return [{k:c[k] for k in ("name", "httpOnly", "secure", "sameSite")}
            for c in page.context.cookies()]


def test_browser_release_gate_business_and_security():
    suffix = uuid.uuid4().hex[:10]
    email, company_name = f"owner-{suffix}@example.test", f"E2E Company {suffix}"
    tender_number = f"E2E-{suffix}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        owner_context = browser.new_context()
        page = owner_context.new_page()
        register(page, company_name, email)
        cookie = next(c for c in owner_context.cookies() if c["name"] == "potok_session")
        assert cookie["httpOnly"] and cookie["sameSite"] == "Strict"
        asset_url = page.evaluate("() => document.querySelector('script[type=module]')?.src")
        assert asset_url
        asset_headers = page.evaluate("""async (url) => {
          const r=await fetch(url); return Object.fromEntries(['x-content-type-options','referrer-policy','x-frame-options','permissions-policy'].map(k=>[k,r.headers.get(k)]));
        }""", asset_url)
        assert asset_headers == {
            "x-content-type-options":"nosniff",
            "referrer-policy":"strict-origin-when-cross-origin",
            "x-frame-options":"DENY",
            "permissions-policy":"camera=(), microphone=(), geolocation=()",
        }
        expect(api(page, "/api/v1/companies/current"))

        # The live React interface creates a tender and its position.
        page.get_by_role("link", name="Тендеры").click()
        page.get_by_label("Номер тендера").fill(tender_number)
        page.get_by_label("Заказчик").fill("Тестовый заказчик")
        page.get_by_label("Начальная цена, ₽").fill("100000")
        page.get_by_label("Срок подачи заявки").fill("2030-01-01T12:00")
        xss_payload = 'Тестовая поставка <img src=x onerror="window.e2eXss=1">'
        page.get_by_label("Предмет закупки").fill(xss_payload)
        page.get_by_role("button", name="Сохранить тендер").click()
        page.get_by_text(tender_number, exact=False).wait_for(timeout=10000)
        page.get_by_text(xss_payload, exact=True).wait_for(timeout=10000)
        assert page.locator('img[onerror="window.e2eXss=1"]').count() == 0
        assert page.evaluate("window.e2eXss") is None
        page.get_by_role("button", name="Открыть позиции").click()
        page.get_by_label("Наименование", exact=True).fill("Тестовый насос")
        page.get_by_label("Количество", exact=True).fill("10")
        page.get_by_label("Единица измерения").fill("шт.")
        page.get_by_label("Ориентировочная цена за единицу, ₽").fill("100")
        page.get_by_role("button", name="Добавить позицию").click()
        tender = next(t for t in expect(api(page, "/api/v1/tenders")) if t["tender_number"] == tender_number)
        position = expect(api(page, f"/api/v1/tenders/{tender['id']}/positions"))[0]
        assert Decimal(position["estimated_total"]) == Decimal("1000.00")

        # Browser CSRF enforcement, supplier quote, procurement and partial stock flow.
        expect(api(page, "/api/v1/transport/estimate", "POST", {
            "origin":"A", "destination":"B", "distance_km_one_way":"10", "cargo_description":"test",
            "carrier_options":[{"company_name":"Carrier", "quoted_total":"100"}]
        }, csrf=False), 403)
        supplier = expect(api(page, "/api/v1/suppliers", "POST", {"name":f"Supplier {suffix}"}), 201)
        rfq = expect(api(page, "/api/v1/rfqs", "POST", {
            "rfq_number":f"RFQ-{suffix}","title":"E2E насосы","message":"Запрос тестовых условий поставки",
            "supplier_ids":[supplier["id"]],"lines":[{"item_name":"Тестовый насос","specification":"нержавеющая сталь","quantity":"10","unit":"шт.","tender_id":tender["id"],"tender_position_id":position["id"]}]
        }), 201)
        rfq_line = expect(api(page, f"/api/v1/rfqs/{rfq['id']}"))["lines"][0]
        offer = expect(api(page, f"/api/v1/rfqs/{rfq['id']}/offers", "POST", {
            "supplier_id":supplier["id"],"delivery_cost":"100","vat_treatment":"no_vat",
            "lines":[{"rfq_line_id":rfq_line["id"],"offered_item_name":"Тестовый насос","offered_specification":"нержавеющая сталь","quantity":"10","unit":"шт.","unit_price":"100","specification_match":"match"}]
        }), 201)
        expect(api(page, f"/api/v1/rfqs/{rfq['id']}/offers/{offer['id']}/review", "POST", {"decision":"confirmed","note":"Проверено"}))
        expect(api(page, f"/api/v1/rfqs/{rfq['id']}/selections", "POST", {"offer_id":offer["id"],"rfq_line_id":rfq_line["id"],"note":"E2E"}))
        draft = expect(api(page, f"/api/v1/rfqs/{rfq['id']}/create-procurement-drafts", "POST", {}), 201)["orders"][0]
        assert Decimal(draft["total_amount"]) == Decimal("1000.00")
        expect(api(page, f"/api/v1/procurement/orders/{draft['id']}/authorize", "POST", {"approval_request_id":None}))
        order = expect(api(page, f"/api/v1/procurement/orders/{draft['id']}"))
        line = order["lines"][0]
        members = expect(api(page, "/api/v1/employees"))
        director = next(m for m in members if m["role"] == "director")
        expect(api(page, f"/api/v1/procurement/orders/{draft['id']}/authorize", "POST", {"approval_request_id":None}), 409)
        expect(api(page, f"/api/v1/access/employees/{director['id']}/limits", "PUT", {
            "operation":"purchase","limit_amount":"2000.00"
        }))
        expect(api(page, f"/api/v1/procurement/orders/{draft['id']}/authorize", "POST", {"approval_request_id":None}))
        expect(api(page, "/api/v1/warehouse/receipts", "POST", {
            "receipt_number":f"REC-{suffix}-1","procurement_order_id":draft["id"],"location":"A-01",
            "lines":[{"procurement_order_line_id":line["id"],"received_quantity":"6","accepted_quantity":"5","defective_quantity":"1","defect_note":"Брак тестовой единицы"}]
        }), 201)
        expect(api(page, "/api/v1/warehouse/receipts", "POST", {
            "receipt_number":f"REC-{suffix}-2","procurement_order_id":draft["id"],"location":"A-01",
            "lines":[{"procurement_order_line_id":line["id"],"received_quantity":"4","accepted_quantity":"4","defective_quantity":"0"}]
        }), 201)
        batch = next(x for x in expect(api(page, "/api/v1/warehouse/batches")) if x["item_name"] == "Тестовый насос")

        # Delivery estimate, partial reservation/shipment and actual transport cost.
        estimate = expect(api(page, "/api/v1/transport/estimate", "POST", {
            "origin":"Склад тест","destination":"Адрес тест","distance_km_one_way":"50","cargo_description":"Насос",
            "carrier_options":[{"company_name":"Тест Перевозчик","quoted_total":"250"}]
        }))
        expect(api(page, f"/api/v1/transport/estimates/{estimate['id']}/select?option_index=0", "POST", {}))
        reservation = expect(api(page, "/api/v1/warehouse/reservations", "POST", {
            "reference":f"RES-{suffix}","reason":"E2E частичная отгрузка","lines":[{"stock_batch_id":batch["id"],"quantity":"7"}]
        }), 201)
        active_reservations = expect(api(page, "/api/v1/warehouse/reservations?status=active"))
        reservation_row = next(r for r in active_reservations if r["id"] == reservation["id"])
        reservation_line = reservation_row["lines"][0]
        shipment = expect(api(page, "/api/v1/warehouse/shipments", "POST", {
            "shipment_number":f"SHIP-{suffix}","reservation_id":reservation["id"],"carrier":"Тест Перевозчик","destination":"Адрес тест",
            "delivery_estimate_id":estimate["id"],"lines":[{"reservation_line_id":reservation_line["id"],"quantity":"3"}]
        }), 201)
        assert Decimal(shipment["shipped_quantity"]) == 3
        stock = next(x for x in expect(api(page, "/api/v1/warehouse/availability")) if x["batch_id"] == batch["id"])
        assert (Decimal(stock["physical_quantity"]), Decimal(stock["reserved_quantity"]), Decimal(stock["available_quantity"])) == (6, 4, 2)
        actual = expect(api(page, f"/api/v1/warehouse/shipments/{shipment['id']}/actual-delivery-cost", "POST", {"actual_cost":"275","note":"E2E"}))
        assert Decimal(actual["variance"]) == 25

        # Finance confirmation and document upload/download are performed in browser fetch.
        movement = expect(api(page, "/api/v1/finance/movements", "POST", {
            "movement_number":f"PAY-{suffix}","kind":"payment","amount":"1000.00","movement_date":"2030-01-02T00:00:00Z",
            "counterparty_name":supplier["name"],"purpose":"E2E purchase payment","procurement_order_id":draft["id"]
        }), 201)
        expect(api(page, f"/api/v1/finance/movements/{movement['id']}/confirm", "POST", {}))
        assert Decimal(expect(api(page, "/api/v1/finance/summary"))["confirmed_payments"]) == 1000
        upload = expect(api(page, "/api/v1/documents?title=E2E%20invoice&document_kind=invoice", "POST", None,
            content_type="application/pdf", headers={"X-File-Name":"e2e-invoice.pdf"}, raw="%PDF-1.4\\nE2E fake document\\n%%EOF"), 201)
        downloaded = page.evaluate("""async ({d,v}) => { const r=await fetch(`/api/v1/documents/${d}/versions/${v}/download`,{credentials:'include'}); return {status:r.status,type:r.headers.get('content-type'),bytes:Array.from(new Uint8Array(await r.arrayBuffer()))}; }""", {"d":upload["id"],"v":upload["versions"][0]["id"]})
        assert downloaded["status"] == 200 and downloaded["type"] == "application/pdf"
        assert bytes(downloaded["bytes"]).startswith(b"%PDF-1.4")

        # A separate company cannot list or address the first company's tender.
        other = browser.new_context()
        other_page = other.new_page()
        register(other_page, f"Other E2E {suffix}", f"other-{suffix}@example.test")
        assert expect(api(other_page, "/api/v1/tenders")) == []
        expect(api(other_page, f"/api/v1/tenders/{tender['id']}"), 404)

        # An untrusted browser Origin with a valid CSRF token is rejected.
        untrusted = owner_context.new_page()
        untrusted.goto(UNTRUSTED, wait_until="domcontentloaded")
        expect(api(untrusted, "/api/v1/auth/session/logout", "POST", {}), 403)

        # Role separation and individual session revocation are verified through browser contexts.
        manager_email = f"manager-{suffix}@example.test"
        invite = expect(api(page, "/api/v1/employees/invitations", "POST", {
            "email":manager_email,"role":"procurement_manager"
        }), 201)
        manager_context = browser.new_context()
        manager_page = manager_context.new_page()
        manager_page.goto(BASE, wait_until="domcontentloaded")
        accepted = manager_page.evaluate("""async (payload) => {
          const r=await fetch('/api/v1/employees/invitations/accept',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
          return {status:r.status,body:await r.json()};
        }""", {"invitation_token":invite["invitation_token"],"password":PASSWORD})
        assert accepted["status"] == 201, accepted
        manager_page.get_by_label("Электронная почта").fill(manager_email)
        manager_page.get_by_label("Пароль").fill(PASSWORD)
        manager_page.locator("form button.primary").click()
        manager_page.get_by_role("heading", name="Панель директора").wait_for(timeout=15000)
        expect(api(manager_page, "/api/v1/finance/movements", "POST", {
            "movement_number":f"DENY-{suffix}","kind":"payment","amount":"1",
            "movement_date":"2030-01-02T00:00:00Z","counterparty_name":"Denied test"
        }), 403)

        second_owner = browser.new_context()
        second_page = second_owner.new_page()
        second_page.goto(BASE, wait_until="networkidle")
        second_page.get_by_label("Электронная почта").fill(email)
        second_page.get_by_label("Пароль").fill(PASSWORD)
        second_page.locator("form button.primary").click()
        second_page.get_by_role("heading", name="Панель директора").wait_for(timeout=15000)
        sessions = expect(api(page, "/api/v1/auth/session/sessions"))["sessions"]
        target = next(s for s in sessions if not s["current"])
        expect(api(page, f"/api/v1/auth/session/sessions/{target['id']}", "DELETE", {}))
        assert api(second_page, "/api/v1/companies/current")["status"] == 401
        manager_context.close()
        second_owner.close()
        expect(api(page, "/api/v1/auth/session/logout", "POST", {}))
        assert api(page, "/api/v1/companies/current")["status"] == 401
        other.close()
        owner_context.close()
        browser.close()
