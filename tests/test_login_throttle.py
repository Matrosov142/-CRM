from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.config import settings
from app.login_throttle import (
    MAX_FAILURES_PER_EMAIL,
    MAX_FAILURES_PER_IP,
    WINDOW_MINUTES,
    _client_ip,
    _digest,
    enforce_login_throttle,
    record_login_failure,
)
from app.models import LoginFailure


class FakeQuery:
    def __init__(self, counts):
        self.counts = counts
        self.filters = []
    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self
    def count(self):
        return self.counts.pop(0)


class FakeDB:
    def __init__(self, counts=(0, 0)):
        self.query_counts = list(counts)
        self.added = []
        self.commits = 0
    def query(self, model):
        assert model is LoginFailure
        return FakeQuery(self.query_counts)
    def add(self, item):
        self.added.append(item)
    def commit(self):
        self.commits += 1


def req(ip="203.0.113.10", headers=None):
    return SimpleNamespace(client=SimpleNamespace(host=ip), headers=headers or {})


def test_identifier_digest_is_keyed_and_stable():
    assert _digest("email:admin@example.com") == _digest("email:admin@example.com")
    assert _digest("email:admin@example.com") != _digest("ip:admin@example.com")
    assert len(_digest("test")) == 64


def test_client_ip_ignores_untrusted_forwarded_header():
    request = req(headers={"x-forwarded-for": "198.51.100.99"})
    assert _client_ip(request) == "203.0.113.10"


def test_throttle_allows_below_threshold_and_returns_only_digests():
    db = FakeDB((MAX_FAILURES_PER_EMAIL - 1, MAX_FAILURES_PER_IP - 1))
    email_hash, ip_hash = enforce_login_throttle(db, req(), " Admin@Example.com ")
    assert len(email_hash) == len(ip_hash) == 64
    assert "admin@example.com" not in email_hash


@pytest.mark.parametrize("counts", [
    (MAX_FAILURES_PER_EMAIL, 0),
    (0, MAX_FAILURES_PER_IP),
])
def test_throttle_blocks_at_limit_with_retry_after(counts):
    with pytest.raises(HTTPException) as exc:
        enforce_login_throttle(FakeDB(counts), req(), "admin@example.com")
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == str(WINDOW_MINUTES * 60)


def test_failure_record_contains_no_plaintext_identifiers():
    db = FakeDB()
    email_hash, ip_hash = _digest("email:secret@example.com"), _digest("ip:203.0.113.10")
    record_login_failure(db, email_hash, ip_hash)
    assert db.commits == 1
    assert db.added[0].email_hash == email_hash
    assert db.added[0].ip_hash == ip_hash
    assert not hasattr(db.added[0], "email")
    assert not hasattr(db.added[0], "ip_address")
