import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_release_version_matches_api():
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert package["version"] == "0.25.0"
    assert 'version="0.25.0-pilot"' in main


def test_react_type_dependencies_are_explicit_and_pinned():
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    dev = package.get("devDependencies", {})
    assert dev.get("@types/react") == "18.3.18"
    assert dev.get("@types/react-dom") == "18.3.5"


def test_frontend_uses_imported_form_event_type():
    app = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "import type { FormEvent } from 'react'" in app
    assert "React.FormEvent" not in app
