"""The spatial facade binds every public name ONCE, so a reader of
`world.spatial` gets the object its name says.

Audit world_spatial_structure_light F13 / world_spatial_truth F25 (2026-11-01,
CONFIRMED): `world/spatial.py` imported `SCENT_LEVELS` twice -- the senses
ladder `('none', 'muffled', 'full')` from `spatial_senses`, then the scent
field's strength ladder from `spatial_scent_field` -- and the second shadowed
the first. `tests/test_senses_gate.py` iterated it as the `sense_adjusted`
ladder, and since `sense_adjusted` returns an unknown word unchanged, the scent
third of its byte-identity check asserted nothing. An AST scan of the facade
found this its only collision; this pins the class.
"""

import ast
from pathlib import Path

import world.spatial as spatial


def _facade_tree():
    return ast.parse(Path(spatial.__file__).read_text())


def _bound_names():
    names = []
    for node in _facade_tree().body:
        if isinstance(node, ast.ImportFrom):
            names.extend(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names.extend(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _bound_from():
    """`{name: module}` for every name the facade's import block lifts out of
    a module. Read off the facade's own source, so the test names no sibling
    it would only call through (`project_check.check_facade_import_direction`):
    with `test_no_name_is_bound_twice`, a name bound from a sibling here IS
    that sibling's object."""
    return {alias.asname or alias.name: node.module
            for node in _facade_tree().body if isinstance(node, ast.ImportFrom)
            for alias in node.names}


def test_no_name_is_bound_twice():
    names = _bound_names()
    twice = sorted({n for n in names if names.count(n) > 1})
    assert twice == []


def test_the_two_scent_ladders_have_two_names():
    bound = _bound_from()
    assert bound["SCENT_LEVELS"] == "world.spatial_scent_field"
    assert bound["SCENT_GRADE_LEVELS"] == "world.spatial_senses"
    assert spatial.SCENT_GRADE_LEVELS == ("none", "muffled", "full")
    assert spatial.SCENT_LEVELS != spatial.SCENT_GRADE_LEVELS


def test_the_body_ledgers_are_the_facades_to_hand_out():
    """`_BODY_LEDGERS` -- the scene ledgers only a body has a row in -- is the
    identity module's one statement of them, and a reader outside `world/`
    (dressing/backdrops.py keeps a pinned copy until it can) imports it
    through the facade (lane L10's request, 2026-11-01)."""
    assert _bound_from()["_BODY_LEDGERS"] == "world.spatial_identity"
    assert spatial._BODY_LEDGERS == ("attire", "scales", "vitals", "overlays")
