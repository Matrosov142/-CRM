import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_release_manifest_matches_runtime_versions_and_qa_report():
    manifest = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    qa = json.loads((ROOT / "docs/QA_REPORT_PILOT_0_25.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert manifest["version"] == "0.25.0-pilot"
    assert manifest["qa"] == "docs/QA_REPORT_PILOT_0_25.json"
    assert manifest["release_name"].endswith("v0.25")
    assert qa["release"] == manifest["version"]
    assert package["version"] == "0.25.0"
    assert 'version="0.25.0-pilot"' in main
    assert manifest["qa_summary"]["selected_test_files"] == qa["selected_tests"]["files_run"]
    assert manifest["qa_summary"]["python_files_compilechecked"] == qa["python_files"]

def test_release_manifest_never_claims_production_ready():
    manifest = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
    qa = json.loads((ROOT / "docs/QA_REPORT_PILOT_0_25.json").read_text(encoding="utf-8"))
    assert manifest["production_ready"] is False
    assert qa["production_ready"] is False
