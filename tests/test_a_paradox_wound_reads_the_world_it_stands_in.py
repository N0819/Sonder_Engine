"""A paradox wound shows on the room it opens in without hiding the room,
ends when the fixed point it guards is withdrawn, and reads an anchor's
existence from the scene before the projection.

world_misc_causal (audit 2026-11-01):
* F4 -- the hazard wound note was APPENDED to `notes`, and the view reads
  `notes` before `desc` (`common_rooms.room_prose`): a desc-only room
  (268 of 1,093 live rooms) was described to every mind as the wound
  sentence alone, and a room whose notes ran past `ROOM_PROSE_CHARS` (600)
  lost the wound to the cut.
* F5 (CORRUPTION) -- deleting a fixed point mid-wound left the wound
  escalating to its ceiling: `_advance_paradox` resolved only when the anchor
  was satisfied, and a deleted anchor is never satisfied. In `toll` mode each
  stage decays memory confidence irreversibly, for a constraint the host
  withdrew.
* The existence check asked only the `world_entities` projection, though
  the commit runs with the scene -- the engine's source of truth -- at hand:
  an entity a scene writer added outside the commit (the World Browser, a
  presence handover) existed to every reader but this one.
"""

from __future__ import annotations

import time

from core.db import q, qi, wget, wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from world import paradox

LONG = " ".join(["The kitchen is long and low, and its black range ticks."] * 14)


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Test", "", time.time()))


def _ctx(chat_id, idx=[0]):
    idx[0] += 1
    turn_id = qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                 "VALUES(?,?,?,?,?)", (chat_id, idx[0], "t", time.time(), None))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx[0], player_input="t",
                      created=time.time(), frame_id=None),
        cast=[], input="t")


def _entity_row(chat_id, eid):
    qi("INSERT INTO world_entities(entity_id,chat_id,kind,payload) VALUES(?,?,?,?)",
       (eid, chat_id, "person", "{}"))


def _open_wound(temp_db, room):
    chat_id = _chat(temp_db)
    wset(chat_id, "scene", {"rooms": {"kitchen": room},
                            "positions": {"pete": "kitchen"}, "entities": {}})
    wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
    paradox.set_policy(chat_id, mode="hazard")
    paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                            required_exists=False, label="x")
    _entity_row(chat_id, "pete")
    ctx = _ctx(chat_id)
    paradox.check_and_apply_paradox(ctx, 0)
    wset(chat_id, "simulation_clock",
         {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.6})
    paradox.check_and_apply_paradox(ctx, 0)
    return chat_id, ctx


def _view(chat_id):
    from agents.common import room_prose
    return room_prose(wget(chat_id, "scene")["rooms"]["kitchen"])


def test_a_room_described_only_by_desc_keeps_its_description(temp_db):
    chat_id, _ = _open_wound(temp_db, {
        "name": "Kitchen", "desc": "A low kitchen with a black range.",
        "adjacent": []})
    view = _view(chat_id)
    assert "A low kitchen with a black range." in view
    assert "feels wrong now" in view


def test_a_long_description_still_shows_the_wound(temp_db):
    chat_id, _ = _open_wound(temp_db, {"name": "Kitchen", "notes": LONG,
                                       "adjacent": []})
    assert "feels wrong now" in _view(chat_id)


def test_resolution_gives_the_room_back_exactly(temp_db):
    room = {"name": "Kitchen", "desc": "A low kitchen with a black range.",
            "adjacent": []}
    chat_id, ctx = _open_wound(temp_db, dict(room))
    qi("DELETE FROM world_entities WHERE chat_id=? AND entity_id=?",
       (chat_id, "pete"))
    sc = wget(chat_id, "scene")
    sc["positions"].pop("pete", None)
    wset(chat_id, "scene", sc)
    paradox.check_and_apply_paradox(ctx, 0)
    after = wget(chat_id, "scene")["rooms"]["kitchen"]
    assert {k: after.get(k) for k in room} == room
    assert not after.get("notes")


def test_a_withdrawn_fixed_point_ends_its_wound(temp_db):
    chat_id = _chat(temp_db)
    wset(chat_id, "scene", {"rooms": {"hall": {"name": "Hall", "adjacent": [
        {"to": "yard"}]}, "yard": {"name": "Yard", "adjacent": [{"to": "hall"}]}},
        "positions": {"pete": "hall"}, "entities": {}})
    wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
    paradox.set_policy(chat_id, mode="hazard")
    anchor = paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                     required_exists=False, label="x")
    _entity_row(chat_id, "pete")
    ctx = _ctx(chat_id)
    paradox.check_and_apply_paradox(ctx, 0)
    wset(chat_id, "simulation_clock",
         {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.6})
    paradox.check_and_apply_paradox(ctx, 0)
    assert wget(chat_id, "scene")["rooms"]["hall"].get("paradox_consumed")

    paradox.remove_fixed_point(chat_id, anchor)
    wset(chat_id, "simulation_clock",
         {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.9})
    result = paradox.check_and_apply_paradox(ctx, 0)
    assert result.get("resolved") is True
    assert paradox.get_paradox(chat_id, None) is None
    rooms = wget(chat_id, "scene")["rooms"]
    assert not rooms["hall"].get("paradox_consumed")
    assert not rooms["yard"].get("paradox_consumed")
    assert paradox.check_and_apply_paradox(ctx, 0) == {"active": False}


def test_an_entity_the_scene_holds_exists_before_its_projection_catches_up(
        temp_db):
    chat_id = _chat(temp_db)
    wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                            "positions": {"Pete": "road"},
                            "entities": {"pete": {"name": "Pete",
                                                  "kind": "person"}}})
    paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                            required_exists=True, label="Pete must live")
    # No world_entities row: a scene writer outside the commit put him there.
    assert q("SELECT 1 FROM world_entities WHERE chat_id=?", (chat_id,)) == []
    assert paradox.check_and_apply_paradox(_ctx(chat_id), 0) == {"active": False}


def test_a_required_absence_is_broken_by_the_scene_alone(temp_db):
    chat_id = _chat(temp_db)
    wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                            "positions": {"Pete": "road"},
                            "entities": {"pete": {"name": "Pete",
                                                  "kind": "person"}}})
    paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                            required_exists=False, label="Pete must die")
    result = paradox.check_and_apply_paradox(_ctx(chat_id), 0)
    assert result.get("label") == "Pete must die"
