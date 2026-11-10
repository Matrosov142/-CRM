from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

def test_every_release_gate_precedes_final_exit():
    source = (ROOT / "tools/release_audit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    exits = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "sys" and n.func.attr == "exit"]
    assert len(exits) == 1
    exit_line = exits[0]
    lines = source.splitlines()
    for marker in (
        "Browser session inventory and individual revocation.",
        "class TenderPosition(Base)",
        "class TenderPositionPricingVersion(Base)",
        "pricing-calculations",
    ):
        marker_lines = [i + 1 for i, line in enumerate(lines) if marker in line]
        assert marker_lines and min(marker_lines) < exit_line

def test_audit_does_not_report_success_before_pricing_version_gates():
    source = (ROOT / "tools/release_audit.py").read_text(encoding="utf-8")
    assert source.index("class TenderPositionPricingVersion(Base)") < source.index("print('RESULT: PASS")
