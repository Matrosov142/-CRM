from app.rbac import Action, has_permission

def test_director_has_all_defined_permissions():
    assert all(has_permission("director", action) for action in Action)

def test_warehouse_cannot_approve_payments_or_write_off():
    assert has_permission("warehouse", Action.WAREHOUSE_RECEIVE)
    assert not has_permission("warehouse", Action.PAYMENTS_APPROVE)
    assert not has_permission("warehouse", Action.WAREHOUSE_WRITE_OFF)

def test_accounting_has_finance_but_not_warehouse_mutation():
    assert has_permission("accounting", Action.FINANCE_VIEW)
    assert has_permission("accounting", Action.PAYMENTS_APPROVE)
    assert not has_permission("accounting", Action.WAREHOUSE_RECEIVE)

def test_unknown_role_and_unknown_action_are_denied():
    assert not has_permission("superuser", Action.STAFF_MANAGE)
    assert not has_permission("director", "arbitrary.admin")

def test_tender_specialist_cannot_approve_tender():
    assert has_permission("tender_specialist", Action.TENDERS_EDIT)
    assert not has_permission("tender_specialist", Action.TENDERS_APPROVE)
