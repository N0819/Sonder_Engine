"""The room path pays only for what can change its answer.

Three costs on the beat's critical path, from the audit of 2026-11-01
(`agents_director_prose_movement_rooms`, Efficiency 1-3):

1. `director_prose.reconcile_rooms` asked the room role whether a fixture the
   room author drew is the same thing as an object the encoder made -- a
   whole model call -- whenever the author built anchored rooms and the
   encoder minted ANY named object, wherever it stood. Only an object that
   can stand in an authored room can duplicate one of its fixtures: a lantern
   picked up in the room the player stands in, while the author builds the
   next one, cannot. An object whose room the beat does not say is still
   asked about: it may be stood where the beat is.
2. `director_rooms._merged` deep-copied the town twice before every designer
   merge -- the scene and the drafted rooms -- and `merge_scene_with_diff`
   copies both again: once is the merge's own boundary.
3. `director_rooms.install_prepared_rooms` worked out every actor's reach
   (an `active_cast` read, sight and heading per body) on every interpret
   whose cache held anything, even when no cached design could be built: a
   design for a room the scene does not hold is never in reach.

And the beat's half of a lot (F5): a lot the rooms-in-view job expanded after
the stage's payload was built was designed from the payload's stale LOT brief
-- the whole building's purpose in one room. The beat re-reads the plan for
the rooms it develops once its own lot expansion has run.
"""

from __future__ import annotations

import copy
import inspect

from agents import director_prose, director_rooms


class _Ctx(dict):
    language = "en"

    def __init__(self):
        super().__init__()
        self.warnings = []

    def add_warning(self, text):
        self.warnings.append(text)


AUTHORED = {"rooms": {"loft": {"name": "The Loft", "anchors": {
    "hay_bale": {"desc": "a bale of hay"}}}}}


def _lantern(placed=None, source="Rhona"):
    patch = {"entities": {"lantern_1": {"name": "a lantern", "kind": "object"}}}
    if placed:
        patch["positions"] = {"lantern_1": placed}
    return {"source_entity_id": source, "event": "Rhona picks up a lantern.",
            "transforms": [{"item": "a lantern", "patch": patch}]}


def _asking(monkeypatch):
    asked = []

    def agent(*a, **k):
        asked.append(a)
        return {"duplicates": []}

    monkeypatch.setattr(director_prose, "_agent_json", agent)
    return asked


def test_an_object_stood_outside_every_authored_room_is_not_asked_about(monkeypatch):
    asked = _asking(monkeypatch)
    scene = {"rooms": {"yard": {"name": "The Yard"}}, "positions": {"Rhona": "yard"}}
    answer, record = director_prose.reconcile_rooms(
        _Ctx(), copy.deepcopy(AUTHORED), [_lantern("yard")], "prose", scene)
    assert asked == [] and record == {}
    assert answer == AUTHORED


def test_an_object_in_an_authored_room_is_still_asked_about(monkeypatch):
    asked = _asking(monkeypatch)
    scene = {"rooms": {"yard": {"name": "The Yard"}}, "positions": {"Rhona": "yard"}}
    director_prose.reconcile_rooms(_Ctx(), copy.deepcopy(AUTHORED),
                                   [_lantern("loft")], "prose", scene)
    assert len(asked) == 1


def test_an_object_the_beat_places_nowhere_is_still_asked_about(monkeypatch):
    """Stood where the beat is (`director._mint_fallback_room`), which may be
    the room being authored: no answer is lost to the saving."""
    asked = _asking(monkeypatch)
    director_prose.reconcile_rooms(_Ctx(), copy.deepcopy(AUTHORED),
                                   [_lantern(source="world")], "prose", {})
    assert len(asked) == 1


def test_a_designer_merge_copies_the_town_once(monkeypatch):
    scene = {"rooms": {"yard": {"name": "The Yard", "adjacent": []}},
             "positions": {"Rhona": "yard"}, "entities": {}}
    draft = {"rooms": {"shed": {"name": "The Shed",
                                "adjacent": [{"to": "yard", "barrier": "open"}]}}}
    before = (copy.deepcopy(scene), copy.deepcopy(draft))
    real, copies = copy.deepcopy, []

    def counting(value, memo=None):
        # the town, or a copy of it, copied whole
        if isinstance(value, dict) and value == before[0]:
            copies.append("scene")
        return real(value, memo)

    monkeypatch.setattr(copy, "deepcopy", counting)
    merged = director_rooms._merged(scene, draft)
    monkeypatch.setattr(copy, "deepcopy", real)
    assert copies == ["scene"]
    assert "shed" in merged["rooms"]
    assert (scene, draft) == before, "the caller's town and draft are untouched"


def test_an_install_with_nothing_buildable_reads_no_reach(temp_db, monkeypatch):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES('t','',0)")
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {
        "attic": {"clean": True, "room": {"name": "Attic"}, "brief": "x"},
        "cellar": {"clean": False, "room": {"name": "Cellar"}, "brief": "x"}})

    def reach(*a, **k):
        raise AssertionError("reach was read for a cache with nothing to build")

    monkeypatch.setattr(director_rooms, "actors_ahead", reach)
    monkeypatch.setattr(director_rooms, "rooms_to_build", reach)
    scene = {"rooms": {"yard": {"name": "The Yard"}, "shed": {"name": "Shed"}},
             "positions": {"Rhona": "yard"}}
    out, installed = director_rooms.install_prepared_rooms(
        cid, scene, "Rhona", cast=[], frame_id=None)
    assert out is scene and installed == {}


def test_the_beat_reads_the_plan_again_for_the_rooms_it_develops(monkeypatch):
    """A lot the job expanded since the payload was built is the entry's
    brief now, not the lot's."""
    import world.structure as structure
    monkeypatch.setattr(structure, "planned_room_brief", lambda cid, scene, ids, **k: {
        rid: {"name": "Entry hall", "purpose": "the house's entry"}
        for rid in ids if rid == "lot__mill"})
    develop = {"lot__mill": {"name": "The Mill", "purpose": "a whole mill"},
               "lane": {"name": "Lane", "purpose": "a lane"}}
    fresh = director_prose.develop_as_planned_now(1, develop, {})
    assert fresh == {"lot__mill": {"name": "Entry hall", "purpose": "the house's entry"},
                     "lane": {"name": "Lane", "purpose": "a lane"}}
    source = inspect.getsource(director_prose.run)
    assert source.index("expand_entered_lots(") < source.index("develop_as_planned_now(")
    assert source.index("develop_as_planned_now(") < source.index("prepared_rooms(")
