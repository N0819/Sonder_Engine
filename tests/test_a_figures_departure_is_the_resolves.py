"""A FIGURE'S DECLARED DEPARTURE IS THE RESOLVE'S TO WRITE, NEVER THE COMMIT'S.

Chat 167 turn 4626 (Cwm Du). A hewer standing the overman's watch -- a
charter body the scene stood beside the player on the main level -- was a
background figure asked BEFORE the resolve, and declared `goes_to:
"pit_bottom"`. The Director never saw that field: `_take_declaration` dropped
it, so the resolve kept him on the main level, a pace behind her. The commit
then enacted it anyway -- `apply_presence_departures`, after the scene and
its lease had committed -- and he stood in the pit bottom at the start of
4627, so his next line crossed rooms and reached her as fragments. The
investigation counted nine such moves across three stories.

A declaration made before the resolve is enacted by the resolve or not at
all: the handovers applier already said so (`is_figure`, scratch story 165
turn 4581). Now the departure applier asks the same predicate, and the
destination goes to the resolve, typed, as that body's own walk.
"""

from __future__ import annotations

from types import SimpleNamespace

from agents.director import _causal_event_inputs, _take_declaration
from persist.commit import apply_presence_departures, apply_presence_handovers


def _scene():
    door = "open_door"
    return {"rooms": {"main_level": {"name": "Main Level", "adjacent": [
                          {"to": "pit_bottom", "barrier": door}]},
                      "pit_bottom": {"name": "Pit Bottom", "adjacent": [
                          {"to": "main_level", "barrier": door}]}},
            "entities": {"Gwenafryn Abogwyn": {"name": "Gwenafryn Abogwyn",
                                               "kind": "person",
                                               "charter_ref": {"charter": "colliery",
                                                               "body": "hewer:0005"}}},
            "positions": {"Gwenafryn Abogwyn": "main_level", "Nell Hartley": "main_level"}}


FIGURE = {"name": "Gwenafryn Abogwyn", "room": "main_level", "goes_to": "pit_bottom",
          "action": "walks along the Main Level toward the Pit Bottom",
          "is_figure": True, "char_id": None,
          "sequence": [{"type": "action", "event_id": "f1",
                        "attempt": "walks along the Main Level toward the Pit Bottom",
                        "observable": "walks off toward the Pit Bottom",
                        "visibility": "overt", "conceal_from": [], "targets": [],
                        "commitment": "asserted"}]}


def test_the_commit_never_enacts_a_departure_declared_before_the_resolve():
    scene = _scene()
    presences = {"Gwenafryn Abogwyn": {"name": "Gwenafryn Abogwyn", "recent": []}}
    moved = apply_presence_departures(scene, [dict(FIGURE)], presences)
    assert moved == []
    assert scene["positions"]["Gwenafryn Abogwyn"] == "main_level"
    assert presences["Gwenafryn Abogwyn"]["recent"] == []


def test_a_voice_that_speaks_after_the_resolve_still_goes():
    """The Josiah Crane case: a background reaction after the resolve, which
    nothing else writes, still arrives."""
    scene = _scene()
    presences = {"Gwenafryn Abogwyn": {"name": "Gwenafryn Abogwyn", "recent": []}}
    after = {k: v for k, v in FIGURE.items() if k != "is_figure"}
    moved = apply_presence_departures(scene, [after], presences)
    assert moved == [("Gwenafryn Abogwyn", "main_level", "pit_bottom")]


def test_both_appliers_ask_one_predicate():
    from persist import commit_background
    assert commit_background._declared_before_the_resolve(FIGURE)
    assert not commit_background._declared_before_the_resolve({"name": "x"})
    scene = _scene()
    handed = apply_presence_handovers(
        scene, [dict(FIGURE, hands_over={"what": "a lamp", "to": "Nell Hartley"})], {})
    assert handed == []


def test_the_destination_goes_to_the_resolve_as_the_bodys_own_walk():
    decls, speech, actions = [], {}, {}
    _take_declaration(decls, speech, actions, dict(FIGURE))
    assert decls[0]["goes_to"] == "pit_bottom"
    ctx = SimpleNamespace(chat={"id": 1, "persona_id": 22}, extra_players=[])
    groups = _causal_event_inputs(ctx, {"sequence": []}, decls, [], [])
    figure = next(g for g in groups if g["entity_id"] == "Gwenafryn Abogwyn")
    assert figure["goes_to"] == "pit_bottom"
    assert figure["authority_mode"] == "autonomous"
    # a declaration with no destination carries none
    decls2 = []
    _take_declaration(decls2, {}, {}, {k: v for k, v in FIGURE.items() if k != "goes_to"})
    groups2 = _causal_event_inputs(ctx, {"sequence": []}, decls2, [], [])
    assert "goes_to" not in next(g for g in groups2 if g["entity_id"] == "Gwenafryn Abogwyn")


def test_the_resolve_card_names_the_field_in_both_packs():
    from pathlib import Path
    for language in ("en", "ja"):
        card = Path(f"language_packs/{language}/cards/system_prompts/prose_contract/"
                    "director_resolve.txt").read_text(encoding="utf-8")
        assert "goes_to" in card, language
