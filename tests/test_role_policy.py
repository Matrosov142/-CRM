from app.permissions import Role

def test_all_business_roles_are_defined():
    assert {r.value for r in Role} == {
        "director", "tender_specialist", "procurement_manager",
        "warehouse", "logistics", "accounting"
    }

def test_role_values_are_unique():
    values = [r.value for r in Role]
    assert len(values) == len(set(values))
