from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_qa_preflight_cannot_replace_canonical_ci_report():
    runner = (ROOT / "tools/qa_release.py").read_text(encoding="utf-8")
    assert 'os.environ.get("CI", "").lower() == "true"' in runner
    assert 'report_name = "QA_REPORT_PILOT_0_25.json"' in runner
    assert 'report_name = "QA_PREFLIGHT_LOCAL.json"' in runner
    assert 'encoding="utf-8"' in runner


def test_local_qa_preflight_report_is_ignored():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "docs/QA_PREFLIGHT_LOCAL.json" in ignore


def test_static_release_audit_parses_canonical_qa_report_as_utf8_json():
    audit = (ROOT / "tools/release_audit.py").read_text(encoding="utf-8")
    assert "json.loads(qa_report_path.read_text(encoding='utf-8'))" in audit
