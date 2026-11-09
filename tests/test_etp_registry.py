from app.etp.registry import PLATFORMS, get_platform, list_platforms

def test_priority_and_codes_are_stable():
    assert [p.code for p in PLATFORMS] == ["b2b_center", "rts_tender", "fabrikant", "sber_a", "tek_torg"]
    assert [p.priority for p in PLATFORMS] == [1, 2, 3, 4, 5]

def test_no_unverified_platform_is_claimed_live():
    for item in PLATFORMS:
        assert item.connection_status == "planned"
        assert item.official_api_verified is False
        assert item.automatic_tender_sync is False
        assert item.document_sync is False
        assert item.status_sync is False
        assert item.manual_import is True

def test_lookup_unknown_platform():
    assert get_platform("unknown") is None

def test_registry_serializes_without_secrets():
    items = list_platforms()
    assert len(items) == 5
    assert all("password" not in str(item).lower() for item in items)
