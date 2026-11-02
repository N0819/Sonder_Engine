"""An agency floor knows a mind by every spelling the world keeps for it.

`director_prose.a_walk_is_its_owners`, `the_account_places_its_own_body` and
`conduct_is_its_owners` matched a mind by the exact spelling of the identity
index -- its name or its key -- so the SAME undeclared move was refused
under the full name and let through under the scene record's id or alias
(audit of 2026-11-01, `agents_director_prose_movement_rooms` F2):

    'Abel Coyle'      -> {"Tamsin Reed": "low_walk"}                       (refused)
    'Coyle'           -> {"Tamsin Reed": "low_walk", "Coyle": "low_walk"}   (passes)
    'char_abel_coyle' -> {... "char_abel_coyle": "low_walk"}               (passes)

and the encoder does spell a body by its record's id (scratch story 166 turn
4598 filed the pilot as `char_hester_gale`; `director_movement.
_canonical_following_ops`), after which the commit's spelling policy lands
the position on the mind. A deterministic floor must not depend on the model
spelling a name the one way the floor reads it.

Read through the engine's own identity: the scene's record of the body (its
id, name and aliases -- `world.spatial.same_subject`), and the cast's sheets
(`common.cast_spelling_policy`: the sheet uid, `character:<id>`, aliases),
never a guess -- a spelling two minds answer to names neither.
"""

from __future__ import annotations

import copy
import inspect

import pytest

from agents import director_prose
from agents.director_prose import (
    a_walk_is_its_owners,
    conduct_is_its_owners,
)

TAMSIN, ABEL = "Tamsin Reed", "Abel Coyle"
INDEX = {"persona:21": TAMSIN, "character:2": ABEL}
SPAN = "turn:9:primary:raw"
INPUTS = [{"entity_id": "persona:21", "authority_mode": "world_author",
           "events": [{"event_id": SPAN, "type": "raw_input"}]}]
SCENE = {
    "rooms": {"landing": {"name": "Landing Stage"}, "low_walk": {"name": "Low Walk"}},
    "positions": {TAMSIN: "landing", ABEL: "landing"},
    "entities": {"char_abel_coyle": {"name": ABEL, "kind": "person",
                                     "aliases": ["Coyle"]}},
}


def _span(spelling):
    return {"source_entity_id": "persona:21", "source_event_id": SPAN,
            "event": "Tamsin walks down to the low walk with Abel.",
            "observable": "walks down to the low walk", "speech": False,
            "movement": None, "item_names": [TAMSIN],
            "transforms": [{"item": TAMSIN, "patch": {"positions": {
                TAMSIN: "low_walk", spelling: "low_walk"}}}]}


def _walk(event, **kw):
    warnings, rows = [], []
    out = a_walk_is_its_owners([copy.deepcopy(event)], INPUTS, INDEX,
                               copy.deepcopy(SCENE), warn=warnings.append,
                               refusals=rows, **kw)
    return out, rows, warnings


@pytest.mark.parametrize("spelling", [ABEL, "abel coyle", "Coyle", "char_abel_coyle"])
def test_his_walk_is_refused_under_every_spelling_his_record_keeps(spelling):
    out, rows, warnings = _walk(_span(spelling))
    assert out[0]["transforms"][0]["patch"]["positions"] == {TAMSIN: "low_walk"}
    assert [row["mind"] for row in rows] == ["character:2"]
    assert warnings and ABEL in warnings[0]


def test_a_sheet_spelling_the_scene_does_not_keep_is_read_through_the_cast():
    """A uid only the cast's sheet holds (no scene record names it): the
    stage hands the floor the one spelling policy the commit folds by."""
    def spell(label):
        return ABEL if str(label).strip().casefold() == "abel_sheet_uid" else label

    scene = dict(copy.deepcopy(SCENE), entities={})
    warnings, rows = [], []
    out = a_walk_is_its_owners([_span("abel_sheet_uid")], INPUTS, INDEX, scene,
                               warn=warnings.append, refusals=rows, spell=spell)
    assert out[0]["transforms"][0]["patch"]["positions"] == {TAMSIN: "low_walk"}
    assert [row["mind"] for row in rows] == ["character:2"]


def test_a_spelling_two_minds_answer_to_names_neither():
    """Never a guess: an alias both minds' records carry is no mind's."""
    index = dict(INDEX, **{"character:3": "Mara Coyle"})
    scene = copy.deepcopy(SCENE)
    scene["entities"]["char_mara_coyle"] = {"name": "Mara Coyle", "kind": "person",
                                            "aliases": ["Coyle"]}
    out = a_walk_is_its_owners([_span("Coyle")], INPUTS, index, scene)
    assert out[0]["transforms"][0]["patch"]["positions"] == {
        TAMSIN: "low_walk", "Coyle": "low_walk"}


def test_a_follow_written_for_his_record_id_is_his_and_not_hers_to_start():
    follow = {"source_entity_id": "persona:21", "source_event_id": SPAN,
              "event": "Abel falls in behind Tamsin.", "movement": None,
              "transforms": [{"item": ABEL, "patch": {"following_ops": [
                  {"op": "start", "follower": "char_abel_coyle", "target": TAMSIN}]}}]}
    out, _rows, warnings = _walk(follow)
    assert out[0]["transforms"] == []
    assert any(ABEL in w for w in warnings)


def test_the_conduct_floor_reads_his_record_id_as_him():
    """At interpret the cast declared nothing: an act filed under his record's
    id is his conduct, refused and offered, as under his name."""
    sits = {"source_entity_id": "char_abel_coyle", "source_event_id": SPAN,
            "event": "Abel sits on the bollard.", "observable": "sits on the bollard",
            "movement": None, "transforms": [{"item": ABEL, "patch": {"poses": {
                ABEL: {"posture": "seated", "support": "bollard"}}}}]}
    kept, refused = conduct_is_its_owners([sits], INPUTS, INDEX, copy.deepcopy(SCENE))
    assert kept == [] and [row["mind"] for row in refused] == ["character:2"]


def test_the_stage_hands_its_floors_the_casts_spelling():
    source = inspect.getsource(director_prose.run)
    assert "spell=" in source[source.index("a_walk_is_its_owners("):]
