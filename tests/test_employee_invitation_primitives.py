from app.invitation_security import token_hash, ALLOWED_ROLES, INVITE_TTL_HOURS


def test_invitation_token_is_hashed_deterministically():
    token = "test-token-value-with-sufficient-entropy"
    digest = token_hash(token)
    assert len(digest) == 64
    assert digest != token
    assert token_hash(token) == digest


def test_only_known_employee_roles_are_invitable():
    assert ALLOWED_ROLES == {
        "tender_specialist", "procurement_manager", "warehouse",
        "logistics", "accounting",
    }
    assert "director" not in ALLOWED_ROLES


def test_invitation_lifetime_is_72_hours():
    assert INVITE_TTL_HOURS == 72
