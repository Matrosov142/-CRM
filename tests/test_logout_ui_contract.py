from pathlib import Path


def test_logout_ui_checks_server_response_before_clearing_state():
    source = (Path(__file__).resolve().parents[1] / "frontend/src/App.tsx").read_text(encoding="utf-8")
    start = source.index("  async function logout()")
    end = source.index("  if (token) {", start)
    block = source[start:end]
    assert block.count("if (!response.ok)") == 2
    assert "finally { setToken" not in block
    assert "Все сеансы завершены" in block
    assert "Вы вышли из системы." in block
