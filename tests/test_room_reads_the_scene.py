"""What `inspect_rooms` reports, and what `inspect_contradictions` can catch.

Companion to `tests/test_room_sees_things.py`, which holds the plan-tier half.
This is the read side, against a real chat row.

Two defects, both measured on the live chat 114 register:

  * `occupants` came from `positions`, which keys BODIES. A thing is placed
    either by a position row or by being an ANCHOR of the room it stands in,
    and the live TARDIS is the second shape with no position at all -- so the
    only read the Room has of a room reported an empty shore with a police box
    standing on it.
  * `planned_exit_to_nowhere` compared `planned_context`'s output against a
    set of room IDS. That function renders each edge as the neighbour's
    DISPLAY NAME, so a coherent plan produced 83 dangling rows, 65 of them
    pure rendering artefact. A report wrong 65 times in 83 is not one anybody
    can act on, and it buried the row that was real.
"""
import json
import time

import pytest

from story.room_tools import _t_inspect_contradictions, _t_inspect_rooms


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Shore", "A dark beach.", time.time()))


def _scene(db, cid, scene):
    db.wset(cid, "scene", scene)


_SHORE = {
    "rooms": {
        "beach": {"name": "Moonlit Shore", "desc": "Dark sand.",
                  "adjacent": [{"to": "terrace", "barrier": "open"}],
                  "anchors": {"tardis": {"desc": "A blue police box."}}},
        "terrace": {"name": "Coastal Terrace", "desc": "Stone.",
                    "adjacent": [{"to": "beach", "barrier": "open"}]},
    },
    "entities": {
        "tardis": {"name": "The TARDIS", "kind": "vehicle",
                   "description": "A blue police box.",
                   "plan_ref": {"uid": "plan:thing:the_tardis:1e1ac4"}},
        "hinami": {"name": "Hinami", "kind": "person",
                   "description": "A kitsune."},
    },
    "positions": {"Hinami": "beach"},
    "stations": {},
}


class TestARoomReportsWhatStandsInIt:
    def test_a_thing_placed_as_an_anchor_is_reported(self, temp_db):
        cid = _chat(temp_db)
        _scene(temp_db, cid, _SHORE)
        rooms = {r["id"]: r for r in _t_inspect_rooms(cid, None)["rooms"]}
        assert [t["name"] for t in rooms["beach"]["things"]] == ["The TARDIS"]
        assert rooms["terrace"]["things"] == []

    def test_a_thing_carries_the_plan_it_was_bound_to(self, temp_db):
        """"Is this the thing I planned, or another one?" is the question this
        read exists to answer."""
        cid = _chat(temp_db)
        _scene(temp_db, cid, _SHORE)
        rooms = {r["id"]: r for r in _t_inspect_rooms(cid, None)["rooms"]}
        assert rooms["beach"]["things"][0]["plan_ref"] \
            == "plan:thing:the_tardis:1e1ac4"

    def test_a_body_is_an_occupant_and_not_also_a_thing(self, temp_db):
        """A cast member routinely has both a position row and a scene entity
        under the same display name; listed in both it reads as two beings."""
        cid = _chat(temp_db)
        _scene(temp_db, cid, _SHORE)
        rooms = {r["id"]: r for r in _t_inspect_rooms(cid, None)["rooms"]}
        assert rooms["beach"]["occupants"] == ["Hinami"]
        assert "Hinami" not in [t["name"] for t in rooms["beach"]["things"]]

    def test_a_thing_placed_by_a_position_row_is_reported_too(self, temp_db):
        cid = _chat(temp_db)
        scene = json.loads(json.dumps(_SHORE))
        scene["rooms"]["beach"].pop("anchors")
        scene["positions"]["tardis"] = "beach"
        _scene(temp_db, cid, scene)
        rooms = {r["id"]: r for r in _t_inspect_rooms(cid, None)["rooms"]}
        assert [t["name"] for t in rooms["beach"]["things"]] == ["The TARDIS"]

    def test_a_story_with_no_things_reports_empty_lists(self, temp_db):
        cid = _chat(temp_db)
        scene = json.loads(json.dumps(_SHORE))
        scene["entities"].pop("tardis")
        scene["rooms"]["beach"].pop("anchors")
        _scene(temp_db, cid, scene)
        rooms = {r["id"]: r for r in _t_inspect_rooms(cid, None)["rooms"]}
        assert all(r["things"] == [] for r in rooms.values())


class TestAPlanTheSceneHasAlreadyPlacedElsewhere:
    def test_the_divergence_is_reported(self, temp_db):
        cid = _chat(temp_db)
        _scene(temp_db, cid, _SHORE)
        temp_db.wset(cid, "planned_entities", {
            "plan:thing:the_tardis:1e1ac4": {
                "uid": "plan:thing:the_tardis:1e1ac4", "kind": "thing",
                "name": "The TARDIS", "aliases": [], "role": "",
                "brief": {"purpose": "", "truths": "", "where": "terrace"}}})
        rows = [r for r in _t_inspect_contradictions(cid, None)["dangling"]
                if r["kind"] == "plan_rendered_elsewhere"]
        assert len(rows) == 1
        assert rows[0]["plan_says"] == "terrace"
        assert rows[0]["actually_in"] == "beach"

    def test_a_plan_standing_where_it_says_is_not_a_contradiction(
            self, temp_db):
        cid = _chat(temp_db)
        _scene(temp_db, cid, _SHORE)
        temp_db.wset(cid, "planned_entities", {
            "plan:thing:the_tardis:1e1ac4": {
                "uid": "plan:thing:the_tardis:1e1ac4", "kind": "thing",
                "name": "The TARDIS", "aliases": [], "role": "",
                "brief": {"purpose": "", "truths": "", "where": "beach"}}})
        assert not [r for r in _t_inspect_contradictions(cid, None)["dangling"]
                    if r["kind"] == "plan_rendered_elsewhere"]

    def test_an_unrendered_plan_is_not_a_contradiction(self, temp_db):
        """Nothing has bound it yet, so the plan is a promise rather than a
        disagreement -- which is what `plan_in_no_room` is for."""
        cid = _chat(temp_db)
        scene = json.loads(json.dumps(_SHORE))
        scene["entities"]["tardis"].pop("plan_ref")
        _scene(temp_db, cid, scene)
        temp_db.wset(cid, "planned_entities", {
            "plan:thing:the_tardis:1e1ac4": {
                "uid": "plan:thing:the_tardis:1e1ac4", "kind": "thing",
                "name": "The TARDIS", "aliases": [], "role": "",
                "brief": {"purpose": "", "truths": "", "where": "terrace"}}})
        assert not [r for r in _t_inspect_contradictions(cid, None)["dangling"]
                    if r["kind"] == "plan_rendered_elsewhere"]
