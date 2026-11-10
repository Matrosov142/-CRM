from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_session_management_is_user_scoped_and_never_returns_token():
    source = (ROOT / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    assert '@router.get("/session/sessions")' in source
    assert '@router.delete("/session/sessions/{session_id}")' in source
    assert 'AuthSession.user_id == user_id' in source
    assert 'AuthSession.id == session_id' in source
    assert '"user_agent": (row.user_agent or "")[:180]' in source
    assert '"token":' not in source


def test_revoke_endpoint_requires_origin_and_csrf():
    source = (ROOT / "app" / "routers" / "auth.py").read_text(encoding="utf-8")
    marker = 'def revoke_browser_session('
    body = source[source.index(marker):]
    assert '_validate_browser_origin(request)' in body
    assert 'X-CSRF-Token' in body
    assert 'compare_digest' in body
    assert 'target.user_id == user_id' in body or 'AuthSession.user_id == user_id' in body
