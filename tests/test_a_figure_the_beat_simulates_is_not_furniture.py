"""A name this beat is already simulating is a body, whatever the world holds.

`mint_unreferenced_things` refuses to stand furniture up wearing a person's
name -- its own docstring says so -- but it tested that by reading
`kind == "person"` off the SCENE. A hand reports `no_referent` precisely
BECAUSE the world holds no record, so for a villager the beat has only just
named, the person-refusal was structurally unable to fire. The name was minted
`{"name": ..., "kind": "fixture"}`, and `_bind_minted_entities_to_present_figures`
then declined to bind it to the charter body of the same name, because an
inert kind is a thing and "things are never bound".

Measured (chat 151, 2026-09-21): `gushiga_toriki` was minted on turn 8 as
`{"name": "Gushiga Toriki", "kind": "fixture"}` -- the bare two-key shape this
function writes -- while a charter figure named Gushiga Toriki spoke and acted
on turns 9 and 10 from the beach outside. One villager, two records, and the
furniture copy is on three inert deny-lists: it cannot be given a voice, cannot
be tracked as a presence, cannot be promoted, and is severed from the charter
body that simulates him off screen.

The beat is shown its figures before it mints anything -- the payload half and
the binding floor read the same roster -- so the refusal reads that roster too.
"""

from __future__ import annotations

from agents.director import mint_unreferenced_things

SCENE = {"rooms": {"beach": {"name": "Moonlit Beach"}},
         "positions": {"Hinami": "beach"},
         "entities": {"Hinami": {"name": "Hinami", "kind": "person"}}}

FIGURES = [{"name": "Gushiga Toriki", "room": "beach", "role": "baker",
            "charter": "c1", "body": "b1"}]


def _out(*missing):
    return {"orchestration": {"specialists": {"contact": {"results": [
        {"status": "no_referent", "settled": {},
         "missing_referents": list(missing)}]}}}}


def test_the_live_case_no_longer_mints_furniture():
    """The measured chat-151 mint, refused."""
    diff = {}
    assert mint_unreferenced_things(
        _out("Gushiga Toriki"), SCENE, diff, "beach",
        figures=FIGURES) == []
    assert not diff.get("entities")


def test_without_the_roster_the_guard_cannot_see_him():
    """Why the refusal had to move. The scene alone holds no record of this
    body -- that is the condition a `no_referent` verdict reports -- so the
    old evidence was structurally incapable of answering, and the name came
    out as a fixture. This is the defect, pinned so it cannot return quietly."""
    diff = {}
    assert mint_unreferenced_things(
        _out("Gushiga Toriki"), SCENE, diff, "beach") == ["gushiga_toriki"]
    assert diff["entities"]["gushiga_toriki"]["kind"] == "fixture"


def test_an_alias_of_a_figure_is_the_figure():
    diff = {}
    figures = [dict(FIGURES[0], aliases=["the baker"])]
    assert mint_unreferenced_things(
        _out("the baker"), SCENE, diff, "beach", figures=figures) == []


def test_a_figure_standing_elsewhere_is_still_a_body():
    """A mint naming a body is a render of that body wherever it stands --
    the binding floor's own rule for a reserved plan. A villager who stepped
    out of the room does not become furniture for the beat they are gone."""
    diff = {}
    elsewhere = [dict(FIGURES[0], room="village_lane")]
    assert mint_unreferenced_things(
        _out("Gushiga Toriki"), SCENE, diff, "beach",
        figures=elsewhere) == []


def test_a_real_thing_still_mints_with_a_roster_present():
    """The refusal must not swallow the function's actual job."""
    diff = {}
    assert mint_unreferenced_things(
        _out("flour sack"), SCENE, diff, "beach",
        figures=FIGURES) == ["flour_sack"]
    assert diff["entities"]["flour_sack"]["name"] == "flour sack"
    assert diff["positions"]["flour_sack"] == "beach"


def test_a_malformed_roster_row_is_ignored_not_fatal():
    diff = {}
    assert mint_unreferenced_things(
        _out("flour sack"), SCENE, diff, "beach",
        figures=[None, "Gushiga Toriki", {}]) == ["flour_sack"]
