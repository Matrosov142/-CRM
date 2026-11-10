from fastapi import HTTPException
from fastapi.responses import Response
from starlette.requests import Request

from app.config import settings
from app.dependencies import get_current_membership
from app.routers.auth import _set_browser_session, _clear_browser_session, _validate_browser_origin, SESSION_COOKIE, CSRF_COOKIE


def make_request(method='POST', cookies=None, headers=None):
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {'type':'http','http_version':'1.1','method':method,'path':'/api/v1/test',
             'raw_path':b'/api/v1/test','query_string':b'','headers':raw_headers,
             'client':('testclient',123),'server':('testserver',80),'scheme':'http'}
    request = Request(scope)
    request._cookies = cookies or {}
    return request


def test_browser_session_cookie_is_httponly_and_csrf_is_readable(monkeypatch):
    monkeypatch.setattr(settings, 'environment', 'production')
    response = Response()
    _set_browser_session(response, 'signed-access-token')
    cookies = response.headers.getlist('set-cookie')
    session = next(c for c in cookies if c.startswith(f'{SESSION_COOKIE}=') )
    csrf = next(c for c in cookies if c.startswith(f'{CSRF_COOKIE}=') )
    assert 'httponly' in session.lower()
    assert 'secure' in session.lower()
    assert 'samesite=strict' in session.lower()
    assert 'httponly' not in csrf.lower()
    assert 'secure' in csrf.lower()
    assert 'samesite=strict' in csrf.lower()


def test_cookie_authenticated_mutation_requires_csrf():
    request = make_request(cookies={SESSION_COOKIE:'token', CSRF_COOKIE:'expected'})
    try:
        get_current_membership(request=request, credentials=None, db=None)
    except HTTPException as exc:
        assert exc.status_code == 403
        assert 'CSRF' in exc.detail
    else:
        raise AssertionError('Missing CSRF header must be rejected')


def test_cookie_authenticated_mutation_rejects_bad_origin():
    request = make_request(cookies={SESSION_COOKIE:'token', CSRF_COOKIE:'same'},
                           headers={'X-CSRF-Token':'same','Origin':'https://evil.example'})
    try:
        get_current_membership(request=request, credentials=None, db=None)
    except HTTPException as exc:
        assert exc.status_code == 403
        assert 'источник' in exc.detail
    else:
        raise AssertionError('Untrusted origin must be rejected')


def test_safe_cookie_read_does_not_require_csrf_header():
    request = make_request(method='GET', cookies={SESSION_COOKIE:'token'})
    # CSRF check is intentionally limited to state-changing methods. The request
    # proceeds to JWT/DB validation, which is outside this focused unit test.
    from app.dependencies import decode_access_token
    try:
        get_current_membership(request=request, credentials=None, db=None)
    except Exception as exc:
        assert not isinstance(exc, HTTPException) or exc.status_code == 401


def test_cookie_authenticated_mutation_requires_origin_even_when_csrf_matches():
    request = make_request(cookies={SESSION_COOKIE:'token', CSRF_COOKIE:'same'},
                           headers={'X-CSRF-Token':'same'})
    try:
        get_current_membership(request=request, credentials=None, db=None)
    except HTTPException as exc:
        assert exc.status_code == 403
        assert 'источник' in exc.detail
    else:
        raise AssertionError('Missing Origin must be rejected')


def test_browser_login_origin_must_be_allowlisted(monkeypatch):
    monkeypatch.setattr(settings, 'cors_origins', 'https://crm.example')
    allowed = make_request(headers={'Origin':'https://crm.example'})
    _validate_browser_origin(allowed)
    denied = make_request(headers={'Origin':'https://attacker.example'})
    try:
        _validate_browser_origin(denied)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError('Untrusted login origin must be rejected')


def test_browser_login_origin_is_required():
    try:
        _validate_browser_origin(make_request())
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError('Missing login Origin must be rejected')
