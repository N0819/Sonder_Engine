"""A relative import names the same module an absolute one does.

`tools/project_check.py`'s facade rule read only absolute imports
(`node.level == 0`), so `from .director_floors import x` in
`agents/character.py` reached past the `agents.director` facade and the rule
passed it. Seven live sites on 2026-11-01 -- in the package the common,
composer and perception splits were filling with relative sibling imports.
CLAUDE.md says the gate "enforces ... a caller imports the facade"; for the
relative spelling it did not.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import project_check as pc  # noqa: E402

DIRECTOR = dict(pkg="agents", stem="director",
                siblings={"director_floors", "director_views"})


def _kinds(source, **kw):
    return [(kind, target) for _line, kind, target
            in pc.facade_import_violations(source, **DIRECTOR, **kw)]


def test_a_caller_reaching_a_sibling_relatively_is_outside_in():
    assert _kinds("from .director_floors import x\n",
                  module="agents.character") == [
        ("outside-in", "agents.director_floors")]
    assert _kinds("from . import director_views\n",
                  module="agents.character") == [
        ("outside-in", "agents.director_views")]


def test_a_caller_importing_the_facade_relatively_is_fine():
    assert _kinds("from .director import x\n", module="agents.character") == []
    assert _kinds("from . import director\n", module="agents.character") == []


def test_a_sibling_importing_a_sibling_relatively_is_fine():
    assert _kinds("from .director_floors import x\n", inside=True,
                  module="agents.director_views") == []


def test_a_sibling_importing_its_facade_relatively_is_inside_out():
    assert _kinds("from .director import x\n", inside=True,
                  module="agents.director_views") == [
        ("inside-out", "agents.director")]
    assert _kinds("from . import director\n", inside=True,
                  module="agents.director_views") == [
        ("inside-out", "agents.director")]


def test_dots_resolve_against_the_file_that_holds_them():
    """Two dots climb a package; a package's own `__init__` is one level up
    from nothing, so its single dot means the package itself."""
    assert pc.resolve_relative_import("agents.character", 1,
                                      "director_floors") == (
        "agents.director_floors")
    assert pc.resolve_relative_import("agents.sub.thing", 2,
                                      "director_floors") == (
        "agents.director_floors")
    assert pc.resolve_relative_import("agents.__init__", 1, "director") == (
        "agents.director")
    assert pc.resolve_relative_import("agents.character", 3, "x") is None


def test_a_module_the_facade_imports_is_upstream_of_it():
    """`agents/director.py` imports `director_prose` as a module, at module
    scope and before `director_fanout` is bound, so `director_prose` cannot
    import the facade back at module scope -- that is the cycle the
    inside-out rule names. It reaches the family's names through the
    siblings, and is not a caller the outside-in rule binds."""
    upstream = pc.facade_dependencies(ROOT / "agents", "director")
    assert "director_prose" in upstream
    assert not upstream & pc.facade_siblings(ROOT / "agents", "director")


def test_the_tree_reaches_no_sibling_past_its_facade_in_either_spelling():
    errors: list[str] = []
    pc.check_facade_import_direction(errors)
    assert errors == [], errors
