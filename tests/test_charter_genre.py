"""The engine must not have learned what a reactor is.

`docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md` §1 states the failure this
guards: the moment the engine knows what a reactor is, it has a genre, and
every other story pays for it in dead weight. §13 lists "genre-specific
combat, romance, magic, economy, or faction engines in core" as a rejected
shape, inherited from `OFFSCREEN_WORLD_ARCHITECTURE.md` §6.

An intention in a docstring is not a guard. This file reads the source.
"""

from __future__ import annotations

import ast
import copy
import pathlib

from world.charter import normalize_charter, out_of_band, run, seed_roster

from charter_fixtures import ABBEY, SHIP

_PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "world"

#: Every noun either fixture invents. None may appear in the package source.
#: Drawn from the fixtures rather than hand-listed, so a fixture that grows a
#: new noun automatically extends the guard.
def _fixture_nouns():
    nouns = set()
    for spec in (SHIP, ABBEY):
        nouns.update(spec["upkeeps"])
        nouns.update(spec["posts"])
        nouns.update(spec["bodies"])
        for upkeep in spec["upkeeps"].values():
            nouns.add(upkeep["place"])
            nouns.update(upkeep.get("requires") or {})
        for post in spec["posts"].values():
            nouns.add(post["place"])
            nouns.update(post.get("requires") or {})
        for body in spec["bodies"].values():
            nouns.update(body.get("competence") or {})
    return {n for n in nouns if n and len(n) > 3}


def _ready(spec):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    return charter


def _code_names_and_values(path):
    """Every identifier and non-docstring literal in a module.

    CODE, DELIBERATELY NOT PROSE. The first version of this guard scanned raw
    text and failed on three comments -- a docstring saying "life support
    above the galley", one saying "what a chief does with a name", and the
    comment recording that `reactor_thermal` crossed its floor at hour 240 on
    this module's first run. None of those teach the engine anything, and
    `CLAUDE.md` asks for exactly that specificity: *comments and commit
    messages are the exception and should stay specific -- citing the exact
    case is how the next reader knows the rule was earned rather than
    guessed.* Evidence is particular; rules are general. So the guard checks
    what the engine can ACT on: names it binds and values it carries.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef,
                             ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.append(node.id)
        elif isinstance(node, ast.Attribute):
            found.append(node.attr)
        elif isinstance(node, ast.arg):
            found.append(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            found.append(node.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value not in docstrings:
                found.append(node.value)
    return found


def test_no_genre_noun_is_a_name_or_a_value_in_the_package():
    sources = sorted(_PACKAGE.glob("charter*.py"))
    assert sources, "the package moved and this guard stopped guarding"

    nouns = _fixture_nouns()
    offences = []
    for path in sources:
        for name in _code_names_and_values(path):
            lowered = str(name).casefold()
            for noun in nouns:
                if noun.casefold() in lowered:
                    offences.append(f"{path.name}: {name!r} contains {noun!r}")

    assert offences == [], offences


def test_the_same_code_runs_a_starship_and_an_abbey():
    """Not that both work — that neither needed a field the other did not.

    The moment one fixture requires a key the other has no use for, the
    abstraction has sprung a leak, and it leaks here first.
    """
    ship, ship_events = run(_ready(SHIP), hours=720.0, window=4.0)
    abbey, abbey_events = run(_ready(ABBEY), hours=720.0, window=4.0)

    assert set(ship) == set(abbey), "the two institutions have different shapes"
    for state in (ship, abbey):
        for upkeep in state["upkeeps"].values():
            assert not out_of_band(upkeep)
    assert ship_events == [] and abbey_events == []


class TestTheBadWeek:
    """§10's worked example, asserted rather than described.

    The rated engineer breaks an arm. Nothing else changes. What the design
    note claims should follow is a cascade with no authored step in it.
    """

    def test_an_injury_cascades_without_anything_being_authored(self):
        charter = _ready(SHIP)
        # One body, one field. Everything below follows from arithmetic.
        charter["bodies"]["chief"]["available"] = False
        charter["bodies"]["ramos"]["available"] = False

        after, events = run(charter, hours=336.0, window=4.0)
        kinds = [e["kind"] for e in events]

        # The charter believed its roster, staffed the post, and nobody came.
        assert "post_believed_filled" in kinds
        # Then it worked out that they were not there, and said so.
        assert "post_unfilled" in kinds
        # And the thing that post existed to tend went out of band.
        assert any(e["kind"] == "upkeep_out_of_band"
                   and e["upkeep"] == "reactor_thermal" for e in events)
        assert out_of_band(after["upkeeps"]["reactor_thermal"])

    def test_the_institution_abandons_in_priority_order(self):
        """Life support outranks the reactor, so with one able hand short the
        thing that fails is the lower-ranked one. The priority ordering IS the
        characterisation, and this is where it becomes observable."""
        charter = _ready(SHIP)
        for key in ("chief", "ramos", "hale", "cook", "vega"):
            charter["bodies"][key]["available"] = False

        after, _ = run(charter, hours=336.0, window=4.0)

        # okonjo is the only body left and holds `environmental`, so the
        # scrubbers keep running while everything below them goes.
        assert not out_of_band(after["upkeeps"]["life_support_scrub"])
        assert out_of_band(after["upkeeps"]["reactor_thermal"])
