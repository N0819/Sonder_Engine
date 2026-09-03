"""The planner's seed reaches the Director when a body enters a planned stub
or has one in view, and reaches nothing else.

Before this the seed (room_registry payload.planned: purpose, access,
adjacency) reached a model in exactly one place -- `structure.planned_context`
in the mapping stage, only when `interp.location_query` named one planned
room -- and no card asked anyone to furnish a stub. So a persona walking a
planned town saw rooms that kept their planned names and exits and stayed
bare. The trigger is now deterministic (`structure.rooms_to_develop`), the
brief is `payload.planned_rooms` on the Director's establish and resolve
stages and on the spatial hand, the plan's exits are protected at commit
(`protect_planned_edges`), and a described stub drops its flag
(`settle_developed_stubs`).

A plan is author knowledge. It goes to the Director and its hand, never to a
mind or the narrator; they learn the room by perceiving what the Director
wrote. The perception test below pins that.
"""

from __future__ import annotations

import json
import time

import pytest

from world.structure import (
    is_planned_stub, planned_context, planned_room_brief,
    plant_structure, protect_planned_edges, rooms_to_develop,
    settle_developed_stubs, skeleton_rooms,
)


PURPOSE = "zorbal-haggling over river salt"   # distinctive, greppable


def _structure():
    return {"key": "aldermere", "max_planned": 20,
            "grammar": [{"kind": "lane", "names": ["Wet Lane"],
                         "purposes": ["passage"]}]}


def _rooms():
    return {
        "square": {"name": "Market Square", "purpose": PURPOSE,
                   "access": "public",
                   "adjacent": [{"to": "inn", "barrier": "open_door", "dir": "e"},
                                {"to": "cellar", "barrier": "wall"}],
                   "frontier": []},
        "inn": {"name": "The Wayfarers' Inn", "purpose": "lodging and drink",
                "access": "public",
                "adjacent": [{"to": "square", "barrier": "open_door", "dir": "w"},
                             {"to": "kitchen", "barrier": "closed_door",
                              "dir": "n"}],
                "frontier": []},
        "kitchen": {"name": "Inn Kitchen", "purpose": "cooking",
                    "access": "staff",
                    "adjacent": [{"to": "inn", "barrier": "closed_door",
                                  "dir": "s"}],
                    "frontier": []},
        "cellar": {"name": "Salt Cellar", "purpose": "storage",
                   "access": "keyed",
                   "adjacent": [{"to": "square", "barrier": "wall"}],
                   "frontier": []},
    }


def _chat(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Planned", "", time.time()))
    plant_structure(cid, _structure(), _rooms())
    scene = skeleton_rooms(cid, "aldermere")
    scene["positions"] = {"Player": "square"}
    return cid, scene


class _Ctx:
    def __init__(self, cid, cast=()):
        self.chat = {"id": cid}
        self.cast = list(cast)


# ---------------------------------------------------------------------------
# The trigger
# ---------------------------------------------------------------------------

def test_the_trigger_is_the_focus_room_the_target_and_non_wall_neighbours(temp_db):
    _cid, scene = _chat(temp_db)
    assert rooms_to_develop(scene, "square") == ["square", "inn"]
    assert rooms_to_develop(scene, "square", ("inn",)) == ["square", "inn"]
    assert rooms_to_develop(scene, "inn") == ["inn", "square", "kitchen"]
    # A wall is not a way through; a room two doors away is not in view.
    assert "cellar" not in rooms_to_develop(scene, "square")
    assert "kitchen" not in rooms_to_develop(scene, "square")


def test_entry_hands_the_seed_and_a_developed_room_is_no_longer_a_stub(temp_db):
    cid, scene = _chat(temp_db)
    brief = planned_room_brief(cid, scene, rooms_to_develop(scene, "square"))
    assert set(brief) == {"square", "inn"}
    assert brief["square"]["purpose"] == PURPOSE
    assert brief["square"]["access"] == "public"
    exits = {e["to"]: e for e in brief["square"]["exits"]}
    assert exits["inn"]["barrier"] == "open_door" and exits["inn"]["dir"] == "e"
    assert exits["inn"]["name"] == "The Wayfarers' Inn"
    assert brief["square"]["structure"]["key"] == "aldermere"
    assert brief["square"]["structure"]["grammar"][0]["names"] == ["Wet Lane"]
    # The Director writes the square: it leaves the brief.
    scene["rooms"]["square"]["desc"] = "Striped awnings over salt barrows."
    assert not is_planned_stub(scene, "square")
    assert set(planned_room_brief(
        cid, scene, rooms_to_develop(scene, "square"))) == {"inn"}


def test_in_view_hands_the_neighbour_alone_when_the_focus_is_developed(temp_db):
    cid, scene = _chat(temp_db)
    scene["rooms"]["square"]["desc"] = "Striped awnings."
    brief = planned_room_brief(cid, scene, rooms_to_develop(scene, "square"))
    assert set(brief) == {"inn"}


def test_the_director_view_is_absent_when_nothing_is_in_reach(temp_db):
    from agents.director import _planned_rooms_view
    cid, scene = _chat(temp_db)
    for rid in scene["rooms"]:
        scene["rooms"][rid]["desc"] = "Done."
    assert _planned_rooms_view(scene, _Ctx(cid), "square") is None
    bare = {"rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Player": "hall"}}
    assert _planned_rooms_view(bare, _Ctx(cid), "hall") is None


def test_the_spatial_hand_is_handed_the_brief_and_the_body_hand_is_not(temp_db):
    from agents.director import _specialist_payload
    from agents.director import _planned_rooms_view
    cid, scene = _chat(temp_db)
    brief = _planned_rooms_view(scene, _Ctx(cid), "square", "inn")
    assert brief and set(brief) == {"square", "inn"}
    view = {"source": "resolved_beat", "player": "Player", "cast": [],
            "declared_actions": {}, "dice": [], "prose": "", "dialogue": [],
            "manifest": [], "ledger_notes": {}}
    extras = {"planned_rooms": brief}
    ctx = _Ctx(cid)
    spatial = _specialist_payload("spatial", ctx, scene, view, extras)
    assert spatial["planned_rooms"] == brief
    assert "planned_rooms" not in _specialist_payload(
        "body", ctx, scene, view, extras)
    assert "planned_rooms" not in _specialist_payload(
        "social", ctx, scene, view, extras)


# ---------------------------------------------------------------------------
# Commit: the plan's exits stay, and a described stub settles
# ---------------------------------------------------------------------------

def test_a_developed_room_keeps_every_planned_exit(temp_db):
    cid, scene = _chat(temp_db)
    # The development rewrote the square with a new exit and forgot the inn.
    scene["rooms"]["square"]["desc"] = "Striped awnings."
    scene["rooms"]["square"]["adjacent"] = [
        {"to": "wet_lane", "barrier": "open", "dir": "s"}]
    scene["rooms"]["wet_lane"] = {"name": "Wet Lane", "adjacent": []}
    # And the inn's own edge to the square was severed too.
    scene["rooms"]["inn"]["adjacent"] = [
        e for e in scene["rooms"]["inn"]["adjacent"] if e["to"] != "square"]
    restored = protect_planned_edges(cid, scene)
    # One doorway, declared from either end (the graph is undirected), so
    # ONE restoration joins them again -- whichever room the sweep reached
    # first -- and the other side then reads as present.
    assert set(restored) & {("square", "inn"), ("inn", "square")}
    assert len(restored) == 1
    square_edges = {e["to"]: e for e in scene["rooms"]["square"]["adjacent"]}
    inn_edges = {e["to"]: e for e in scene["rooms"]["inn"]["adjacent"]}
    joined = square_edges.get("inn") or inn_edges.get("square")
    assert joined and joined["barrier"] == "open_door"
    assert "wet_lane" in square_edges              # the added exit stays
    # A planned edge to a room the scene has NOT reached is not forced in.
    assert not [r for r in restored if r[1] == "cellar"]


def test_an_edge_present_from_the_far_side_is_not_duplicated(temp_db):
    cid, scene = _chat(temp_db)
    scene["rooms"]["square"]["adjacent"] = []       # only the inn declares it
    assert protect_planned_edges(cid, scene) == []


def test_a_described_stub_settles_and_a_bare_one_does_not():
    scene = {"rooms": {
        "square": {"name": "Market Square", "planned": True,
                   "purpose": PURPOSE, "access": "public",
                   "desc": "Striped awnings.", "adjacent": []},
        "inn": {"name": "Inn", "planned": True, "purpose": "lodging",
                "adjacent": []},
    }}
    assert settle_developed_stubs(scene) == ["square"]
    square = scene["rooms"]["square"]
    assert "planned" not in square and "purpose" not in square
    assert square["desc"] == "Striped awnings."
    assert scene["rooms"]["inn"]["planned"] is True
    assert scene["rooms"]["inn"]["purpose"] == "lodging"


def test_the_commit_path_runs_both_seams(temp_db, monkeypatch):
    """`commit_scene_state` calls protection then settlement before the fringe
    materializes -- pinned by source, since driving a whole commit here would
    pin the rest of the pipeline with it."""
    import inspect
    import persist.commit_scene_state as css
    src = inspect.getsource(css)
    body = src[src.index("protect_planned_edges(cid, sc)"):]
    assert body.index("settle_developed_stubs(sc)") \
        < body.index("prepare_frontier_expansion(cid, sc)")


# ---------------------------------------------------------------------------
# The mapping path is unchanged
# ---------------------------------------------------------------------------

def test_planned_context_still_answers_a_named_query(temp_db):
    cid, _scene = _chat(temp_db)
    context = planned_context(cid, "Market Square")
    assert context["room_uid"] == "square" and context["purpose"] == PURPOSE
    assert planned_context(cid, "nowhere in particular") is None


# ---------------------------------------------------------------------------
# The firewall: the seed reaches no mind
# ---------------------------------------------------------------------------

def test_the_seed_reaches_no_view_and_no_observation(temp_db):
    from agents.perception import perception_act
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_character_data

    cid, scene = _chat(temp_db)
    sheet = default_character_data("Reya")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(sheet), "{}", time.time(), "char_reya"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (cid, char_id, "active", "{}"))
    scene.update({"location": "Aldermere", "attire": {}, "overlays": {},
                  "entities": {},
                  "positions": {"The Stranger": "square", "Reya": "square"}})
    temp_db.wset(cid, "scene", scene)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "I look around.", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Planned", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1,
                      player_input="I look around.", created=time.time()),
        cast=cast, input="I look around.")
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": "looks around",
                      "observable": "looks around", "visibility": "overt"}],
        "speech": None, "speech_volume": "normal", "action": None,
        "location_query": "the square",
        "flow": {"reactors": [char_id], "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}}}
    out = perception_act(ctx, "n0")
    blob = json.dumps(out)
    assert "zorbal" not in blob
    # The onset pass composes the CHARACTERS' views (the player's own comes
    # at outcome); Reya stands in the stub and receives its name and no seed.
    assert "Market Square" in (out["views"].get(str(char_id)) or "")
