"""The gate's three per-file shape rules share one parse and say the same.

`check_duplicate_python_symbols`, `check_duplicate_dict_keys` and
`check_empty_tests` each parsed and walked every engine and test module --
three whole-tree passes where one does (tooling_gate E4, 2026-11-01).
`make structure` now runs `python_shape_pass`, which must append exactly what
the three checks append, in the same order, or the speed-up changed a verdict.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402

FILES = {
    "story/twice.py": ("def helper():\n    return 1\n\n"
                       "def helper():\n    return 2\n\n"
                       "class Thing:\n    def go(self):\n        pass\n"
                       "    def go(self):\n        pass\n"),
    "world/keys.py": "TABLE = {'a': 1, 'b': 2, 'a': 3}\n",
    "tests/test_nothing.py": "import os\n\ndef helper():\n    pass\n",
    "tests/test_imports_only.py": "def test_x():\n    import os\n",
    "tests/test_blank.py": "   \n",
    "tests/test_fine.py": "def test_x():\n    assert {'k': 1, 'j': 2}\n",
}


def test_one_pass_appends_what_the_three_checks_append(tmp_path, monkeypatch):
    for rel, text in FILES.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    engine = sorted(tmp_path.glob("story/*.py")) + sorted(
        tmp_path.glob("world/*.py"))
    monkeypatch.setattr(pc, "ROOT", tmp_path)
    monkeypatch.setattr(pc, "engine_python_paths", lambda: engine)

    expected = ([], [], [])
    pc.check_duplicate_python_symbols(expected[0])
    pc.check_duplicate_dict_keys(expected[1])
    pc.check_empty_tests(expected[2])
    got = ([], [], [])
    pc.python_shape_pass(*got)

    assert got == expected
    # And the fixture really exercises every rule.
    assert len(expected[0]) == 2 and len(expected[1]) == 1
    assert len(expected[2]) == 3
