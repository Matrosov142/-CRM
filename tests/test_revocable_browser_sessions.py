from datetime import datetime, timezone
from uuid import uuid4

from app.config import settings
from app.routers.auth import _create_browser_session
from app.security import decode_access_token


class FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0
    def add(self, item):
        self.added.append(item)
    def commit(self):
        self.commits += 1


def test_browser_session_issues_unique_jti_and_persists_server_record():
    db = FakeDB()
    user_id, company_id = uuid4(), uuid4()
    token = _create_browser_session(db, user_id, company_id, "director")
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["company_id"] == str(company_id)
    assert claims["type"] == "access"
    assert claims["jti"]
    assert len(claims["jti"]) <= 64
    assert len(db.added) == 1
    record = db.added[0]
    assert record.jti == claims["jti"]
    assert record.user_id == user_id
    assert record.company_id == company_id
    assert record.revoked_at is None
    assert record.expires_at > datetime.now(timezone.utc)
    assert db.commits == 1


def test_browser_sessions_receive_distinct_identifiers():
    db = FakeDB()
    user_id, company_id = uuid4(), uuid4()
    first = decode_access_token(_create_browser_session(db, user_id, company_id, "director"))
    second = decode_access_token(_create_browser_session(db, user_id, company_id, "director"))
    assert first["jti"] != second["jti"]
    assert len(db.added) == 2


def test_browser_session_stores_bounded_user_agent_metadata():
    db = FakeDB()
    token = _create_browser_session(db, uuid4(), uuid4(), "director", "A" * 900)
    assert decode_access_token(token)["jti"] == db.added[0].jti
    assert db.added[0].user_agent == "A" * 500
