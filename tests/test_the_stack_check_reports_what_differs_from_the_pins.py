"""The gate says which stack its verdict is about.

`make check` ran whatever `python` resolved to. On the owner's machine that
was Pydantic 1.10.14, NumPy 1.26.4 and pytest 9.1.1 with no xdist, while
`.venv` -- what both launchers build, what every player runs -- held the
pinned 2.11.7 / 2.2.6 / 8.4.1 (2026-11-01); CLAUDE.md records two defects
that lived in exactly that gap with the suite green through both. `make stack`
(`project_check.py --stack`) prints the interpreter and the pinned versions it
carries, and refuses a stack that differs from `constraints.txt` unless told
`ALLOW_UNPINNED=1`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402


def test_the_pins_are_read_from_the_constraints_file():
    pins = pc.constraint_pins(
        "# a comment\n"
        "fastapi==0.115.14\n"
        "pytest-xdist==3.8.0  # trailing note\n"
        "requests>=2.32\n"
        "\n")
    assert pins == {"fastapi": "0.115.14", "pytest-xdist": "3.8.0"}
    real = pc.constraint_pins(pc.CONSTRAINTS.read_text(encoding="utf-8"))
    assert {"pydantic", "numpy", "pytest", "pytest-xdist"} <= set(real)


def test_a_pin_installed_at_another_version_is_a_difference():
    pins = {"pydantic": "2.11.7", "numpy": "2.2.6", "playwright": "1.61.0"}
    installed = {"pydantic": "1.10.14", "numpy": "2.2.6", "playwright": None}
    assert pc.stack_differences(pins, installed) == [
        "pydantic 1.10.14 (constraints.txt pins 2.11.7)"]


def test_drift_refuses_unless_the_caller_says_it_knows(monkeypatch, capsys):
    monkeypatch.setattr(pc, "installed_versions",
                        lambda names: {name: "0.0.1" for name in names})
    assert pc.report_stack(environ={}) == 1
    assert "not the pinned stack" in capsys.readouterr().out
    assert pc.report_stack(environ={pc.ALLOW_UNPINNED_ENV: "1"}) == 0


def test_the_pinned_stack_passes(monkeypatch):
    pins = pc.constraint_pins(pc.CONSTRAINTS.read_text(encoding="utf-8"))
    monkeypatch.setattr(pc, "installed_versions", lambda names: dict(pins))
    assert pc.report_stack(environ={}) == 0


def test_an_import_under_an_if_in_a_function_is_a_deferred_edge(tmp_path):
    """`_import_kind_edges` walked an `if` only outside functions, so every
    import under an `if` in a function body went uncounted -- deferred edges
    short in `tools/package_edges.json`, cycles unaffected (tooling_gate F12).
    """
    source = tmp_path / "mod.py"
    source.write_text(
        "def f(ready):\n"
        "    if ready:\n"
        "        import world.spatial\n"
        "    else:\n"
        "        from persist import commit\n",
        encoding="utf-8")
    assert sorted(pc._import_kind_edges(source, "story")) == [
        ("story", "persist", "deferred"), ("story", "world", "deferred")]
