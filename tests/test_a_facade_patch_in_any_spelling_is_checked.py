"""A patch on a facade is read in every spelling a test writes one.

`check_facade_patch_targets` read `monkeypatch.setattr(module, "name", ...)`
alone. The string form -- `monkeypatch.setattr("mind.memory.name", ...)` --
had seven live sites, all on the `mind.memory` facade, and `mock.patch` /
`patch.object` were invisible too. And it counted a sibling as holding a name
only when it IMPORTED it, never when it DEFINED it and called it there: the
splitter that landed `agents.common` (2026-11-01) found both shapes in its own
repoint table, where the gate alone would have let ten patches go inert.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402


def _sites(source):
    return sorted((module, attr) for _line, module, attr
                  in pc.facade_patch_sites(ast.parse(source)))


def test_every_spelling_of_a_patch_names_its_target():
    source = (
        "from unittest import mock\n"
        "from unittest.mock import patch\n"
        "def test_x(monkeypatch):\n"
        "    monkeypatch.setattr(commit, 'a', None)\n"
        "    monkeypatch.setattr(agents.director, 'b', None)\n"
        "    monkeypatch.setattr('mind.memory.c', None)\n"
        "    with mock.patch('persist.commit.d'):\n"
        "        pass\n"
        "    with patch.object(commit, 'e'):\n"
        "        pass\n"
        "@patch('world.spatial.f')\n"
        "def test_y(fake):\n"
        "    pass\n"
    )
    assert _sites(source) == [
        ("commit", "a"), ("commit", "e"), ("director", "b"),
        ("mind.memory", "c"), ("persist.commit", "d"), ("world.spatial", "f")]


def test_an_attribute_held_in_a_variable_is_not_guessed():
    """Undecidable without running the test, and so not read at all."""
    source = ("def test_x(monkeypatch, name):\n"
              "    monkeypatch.setattr(commit, name, None)\n")
    assert _sites(source) == []


def test_a_name_a_module_defines_at_top_level_is_one_it_holds():
    tree = ast.parse("def helper():\n    pass\n"
                     "class Thing:\n    pass\n"
                     "LIMIT = 3\n"
                     "def caller():\n    helper()\n"
                     "    def inner():\n        pass\n")
    assert pc._module_definitions(tree) == {"helper", "Thing", "LIMIT",
                                            "caller"}


def test_no_test_patches_a_facade_name_a_sibling_holds_in_any_spelling():
    errors: list[str] = []
    pc.check_facade_patch_targets(errors)
    assert errors == [], errors
