"""Classes found by playing, 2026-09-04: a fresh scenario (chat 116, "The
Lantern Station") and chat 114, both on copies of the owner's database with
Gemini 3.8 flash, every stage of every beat read against the others. Each
test names the live case that proved the rule was missing and pins the rule,
never the case:

  * a barrier is a property of the doorway, so a change written on one side
    is written on the other (F16);
  * a planned exit is restored only into a room the scene holds, or the
    dangling-exit guard undoes it in the same commit (F13);
  * a frontier names what lies that way, never a bare direction (F3);
  * the structure check judges the structure's still-planned rooms, not
    every developed one (F31);
  * the minds view carries the authored tier beside the ledgers (F8);
  * a setting-fact need is named as one in the commit warning (F4);
  * an anchor is resolved in the body's own room before scene-wide (F27);
  * a leg walked toward a destination is an arrival in the room between (F28).

Classes found by the five play runs of 2026-09-05 (the lighthouse, the road,
the manor, the flat), each pinned the same way -- the rule, never the case:

  * a body that crosses rooms performs one act per room it is in, and an
    observer is entitled to the legs that happened where their channel stood
    (PA1, and F36's sibling at the memory boundary);
  * sight answers HOW MUCH is seen and the act channel delivers only as much
    conduct as the grade admits, in every room including the observer's own
    (PC1, PE9);
  * a line degraded by distance or noise loses its WORDS, never its speaker,
    when the observer can see who spoke (PD3);
  * a line cannot be concealed from the person it is addressed to (PC2);
  * one beat, one field: every relation a beat builds is graded by the same
    sound field (PC3, half of it).
"""
from __future__ import annotations

import json
import re
import time
import types

import pytest

from agents import composer, perception
from agents.director import (
    _guard_approach_is_not_arrival, _reconcile_near_group_positions,
    crossing_legs, strip_addressee_concealment)
from persist.commit import prune_dangling_exits
from story.plot_packages import OPERATION_FIELDS, _shape_plan_rooms
from story.room_tools import MIND_AUTHORED_ITEMS, MIND_LINE_CHARS, run_tool
from world.spatial import merge_scene_with_diff, spatial_rel_between
from world.structure import plant_structure, protect_planned_edges


# ---------------------------------------------------------------------------
# F16: one doorway, one barrier
# ---------------------------------------------------------------------------

def _two_rooms(a="closed_door", b="closed_door"):
    return {"rooms": {
        "platform": {"name": "Platform", "adjacent": [
            {"to": "gallery", "barrier": a, "dir": "e"}]},
        "gallery": {"name": "Gallery", "adjacent": [
            {"to": "platform", "barrier": b, "dir": "w"},
            {"to": "radio", "barrier": "open_door", "dir": "n"}]},
        "radio": {"name": "Radio", "adjacent": [
            {"to": "gallery", "barrier": "open_door", "dir": "s"}]},
    }, "positions": {}, "entities": {}}


def _edge(scene, room, to):
    return next(e for e in scene["rooms"][room]["adjacent"] if e["to"] == to)


def test_a_door_opened_from_one_side_is_open_from_the_other():
    """Chat 116 beat 1: Marisol held the platform door open; the diff wrote
    `platform -> gallery: open_door` and nothing on the gallery, whose edge
    stayed shut, so the two rooms disagreed about one door."""
    merged = merge_scene_with_diff(_two_rooms(), {"rooms": {
        "platform": {"name": "", "desc": "",
                     "adjacent": [{"to": "gallery", "barrier": "open_door"}]}}})
    assert _edge(merged, "platform", "gallery")["barrier"] == "open_door"
    assert _edge(merged, "gallery", "platform")["barrier"] == "open_door"
    # Nothing else about the gallery moved: its other exit and its bearing.
    assert _edge(merged, "gallery", "radio")["barrier"] == "open_door"
    assert _edge(merged, "gallery", "platform")["dir"] == "w"


def test_a_door_closed_from_one_side_is_closed_from_the_other():
    merged = merge_scene_with_diff(_two_rooms("open_door", "open_door"), {"rooms": {
        "gallery": {"adjacent": [{"to": "platform", "barrier": "closed_door"}]}}})
    assert _edge(merged, "platform", "gallery")["barrier"] == "closed_door"


def test_a_diff_that_wrote_both_sides_is_left_as_written():
    merged = merge_scene_with_diff(_two_rooms(), {"rooms": {
        "platform": {"adjacent": [{"to": "gallery", "barrier": "open_door"}]},
        "gallery": {"adjacent": [{"to": "platform", "barrier": "window"}]}}})
    assert _edge(merged, "platform", "gallery")["barrier"] == "open_door"
    assert _edge(merged, "gallery", "platform")["barrier"] == "window"


def test_the_two_asymmetric_cases_are_not_mirrored():
    """A one-way window is asymmetric by design; a wall is a seal, which
    already takes a two-sided declaration (`_shield_minted_edges`)."""
    scene = _two_rooms("open_door", "one_way_window")
    merged = merge_scene_with_diff(scene, {"rooms": {
        "platform": {"adjacent": [{"to": "gallery", "barrier": "window"}]}}})
    assert _edge(merged, "gallery", "platform")["barrier"] == "one_way_window"
    merged = merge_scene_with_diff(_two_rooms(), {"rooms": {
        "platform": {"adjacent": [{"to": "gallery", "barrier": "one_way_window"}]}}})
    assert _edge(merged, "gallery", "platform")["barrier"] == "closed_door"
    merged = merge_scene_with_diff(_two_rooms("open_door", "open_door"), {"rooms": {
        "platform": {"adjacent": [{"to": "gallery", "barrier": "wall"}]}}})
    assert _edge(merged, "gallery", "platform")["barrier"] == "open_door"


def test_an_edge_that_names_a_room_the_scene_lacks_mints_nothing():
    merged = merge_scene_with_diff(_two_rooms(), {"rooms": {
        "platform": {"adjacent": [{"to": "west", "barrier": "open_door"}]}}})
    assert "west" not in merged["rooms"]


def test_an_edge_written_without_a_barrier_changes_nothing_across():
    merged = merge_scene_with_diff(_two_rooms(), {"rooms": {
        "platform": {"adjacent": [{"to": "gallery", "distance": 4}]}}})
    assert _edge(merged, "gallery", "platform")["barrier"] == "closed_door"


# ---------------------------------------------------------------------------
# F13: a planned exit comes back only into a room the scene holds
# ---------------------------------------------------------------------------

def _station(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Terrace", "", time.time()))
    plant_structure(cid, {"key": "house", "name": "House"}, {
        "terrace": {"name": "Terrace", "adjacent": [
            {"to": "lounge", "barrier": "open_door"},
            {"to": "dining", "barrier": "open_door"}]},
        "lounge": {"name": "Lounge", "adjacent": [{"to": "terrace", "barrier": "open_door"}]},
        "dining": {"name": "Dining", "adjacent": [{"to": "terrace", "barrier": "open_door"}]},
    })
    return cid


def test_a_planned_exit_into_an_unminted_room_is_not_restored(temp_db):
    """Chat 114: every beat restored terrace -> lounge/dining/garden and the
    dangling-exit guard dropped them as undefined in the same commit."""
    cid = _station(temp_db)
    scene = {"rooms": {"terrace": {"name": "Terrace", "desc": "Flagstones.",
                                   "adjacent": []}}}
    assert protect_planned_edges(cid, scene) == []
    assert scene["rooms"]["terrace"]["adjacent"] == []
    assert prune_dangling_exits(scene) == []


def test_the_exit_returns_the_beat_the_stub_is_minted(temp_db):
    cid = _station(temp_db)
    scene = {"rooms": {
        "terrace": {"name": "Terrace", "desc": "Flagstones.", "adjacent": []},
        "lounge": {"name": "Lounge", "planned": True, "adjacent": []}}}
    restored = protect_planned_edges(cid, scene)
    # One doorway, restored from whichever end the sweep reached first.
    assert set(restored) & {("terrace", "lounge"), ("lounge", "terrace")}
    assert len(restored) == 1
    joined = ([e for e in scene["rooms"]["terrace"]["adjacent"] if e["to"] == "lounge"]
              or [e for e in scene["rooms"]["lounge"]["adjacent"] if e["to"] == "terrace"])
    assert joined and joined[0]["barrier"] == "open_door"
    assert prune_dangling_exits(scene) == []


# ---------------------------------------------------------------------------
# F3: a frontier is what lies that way
# ---------------------------------------------------------------------------

def _plan(frontier):
    return {"op": "plan_rooms", "structure": {"key": "stn", "name": "Station"},
            "rooms": {"platform": {"name": "Platform", "purpose": "arrivals",
                                   "adjacent": [], "frontier": frontier}}}


@pytest.mark.parametrize("word", ["west", "W", "North-East", "up", " down "])
def test_a_bare_direction_is_refused_as_a_frontier(word):
    """Chat 116: `frontier: ["west"]` minted a room called West at the
    opening commit."""
    with pytest.raises(ValueError) as caught:
        _shape_plan_rooms(_plan([word]))
    assert "is a direction" in str(caught.value)
    assert "adjacent.bearing" in str(caught.value)


def test_a_frontier_that_names_a_place_is_kept():
    shaped = _shape_plan_rooms(_plan(["the service road down to the valley",
                                      "west ridge path"]))
    assert shaped["rooms"]["platform"]["frontier"] == [
        "the service road down to the valley", "west ridge path"]


def test_the_field_text_no_longer_asks_for_a_direction():
    text = OPERATION_FIELDS["plan_rooms"]["rooms"]
    assert "<direction>" not in text
    assert "never a bare direction" in text


# ---------------------------------------------------------------------------
# F31: the structure check judges planned rooms
# ---------------------------------------------------------------------------

def _story_with_structure(temp_db, rooms):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Station", "", time.time()))
    plant_structure(cid, {"key": "stn", "name": "Station"}, {
        "platform": {"name": "Platform", "adjacent": [{"to": "gallery"}]},
        "gallery": {"name": "Gallery", "adjacent": [{"to": "platform"}]}})
    temp_db.wset(cid, "scene", {"location": "Station", "rooms": rooms,
                                "positions": {"P": "platform"}, "entities": {}})
    return cid


def test_developed_planned_rooms_are_not_contradictions(temp_db):
    """Chat 116 after the opening: all five rooms the establish developed
    from the plan were reported as 'planned room contains prose'."""
    cid = _story_with_structure(temp_db, {
        "platform": {"name": "Platform", "desc": "Timber and iron.",
                     "adjacent": [{"to": "gallery", "barrier": "closed_door"}]},
        "gallery": {"name": "Gallery", "desc": "Glass and brass.",
                    "adjacent": [{"to": "platform", "barrier": "closed_door"}]}})
    found = run_tool(cid, "inspect_contradictions")
    assert found["structure"] == []


def test_a_stub_that_carries_prose_without_settling_still_is_one(temp_db):
    cid = _story_with_structure(temp_db, {
        "platform": {"name": "Platform", "desc": "Timber and iron.", "adjacent": []},
        "gallery": {"name": "Gallery", "planned": True, "desc": "Glass and brass.",
                    "adjacent": []}})
    found = run_tool(cid, "inspect_contradictions")
    assert any("gallery: planned room contains prose" in w for w in found["structure"])


# ---------------------------------------------------------------------------
# F8: the minds view carries the card
# ---------------------------------------------------------------------------

def test_the_minds_view_carries_the_authored_tier(temp_db):
    """Chat 116: asked what Marisol believed, the Planner read an empty
    belief ledger and invented one that contradicted her card."""
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Minds", "", time.time()))
    temp_db.wset(cid, "scene", {"location": "Station", "rooms": {
        "gallery": {"name": "Gallery", "adjacent": []}},
        "positions": {"P": "gallery"}, "entities": {}})
    for _ in range(3):
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                   (cid, _, "", time.time()))
    sheet = {"name": "Marisol Oda", "psychology": {
        "drive": {"essence": "that a true record exists", "expression": "checks twice",
                  "taboo": "letting a wrong reading stand"},
        "values": ["accuracy over comfort", "the record over her own reputation"]
                  + ["v%d" % i for i in range(MIND_AUTHORED_ITEMS + 3)],
        "traits": [{"name": "exacting", "strength": 0.8}, {"name": "dry", "strength": 0.6}],
        "self_model": {"summary": "Believes the generator fault is in the fuel line "
                                  "and that Teo will not admit he changed the filter. "
                                  + "y" * (MIND_LINE_CHARS * 3),
                       "protected_beliefs": ["A number is not rounded."]}}}
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                         ("Marisol Oda", json.dumps(sheet), time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (cid, char_id, "active", json.dumps({})))
    (mind,) = run_tool(cid, "inspect_minds")["minds"]
    authored = mind["authored"]
    assert authored["self_model"].startswith("Believes the generator fault is in the fuel line")
    assert authored["values"][:2] == ["accuracy over comfort",
                                      "the record over her own reputation"]
    assert len(authored["values"]) == MIND_AUTHORED_ITEMS
    assert authored["traits"] == ["exacting (0.8)", "dry (0.6)"]
    assert authored["protected_beliefs"] == ["A number is not rounded."]
    assert mind["beliefs"] == []                   # the ledger is still the ledger


# ---------------------------------------------------------------------------
# F4: a setting fact is named as one
# ---------------------------------------------------------------------------

def test_a_setting_fact_need_is_named_as_a_fact():
    from persist.commit import _describe_need
    assert _describe_need({"kind": "thing", "reason": "setting_fact",
                           "subject": "The cable car runs once a day."}) \
        == "setting fact 'The cable car runs once a day.'"
    assert _describe_need({"kind": "room", "reason": "rendered_unplanned",
                           "subject": "cellar"}) == "room 'cellar'"


# ---------------------------------------------------------------------------
# F27: an anchor lives in a room
# ---------------------------------------------------------------------------

class _Ctx(types.SimpleNamespace):
    def get(self, key, default=None):
        return getattr(self, key, default)


def test_a_door_anchored_on_both_its_sides_is_not_an_ambiguity():
    """Chat 116 beat 2: `station_door` on the platform AND on the gallery
    (one door, two sides); two bodies near each other at the gallery's read
    as 'fresh station anchors do not identify one unambiguous room'."""
    scene = {"rooms": {
        "platform": {"name": "Platform", "anchors": {"station_door": {"desc": "the door"}},
                     "adjacent": [{"to": "gallery", "barrier": "open_door"}]},
        "gallery": {"name": "Gallery", "anchors": {"station_door": {"desc": "the door"}},
                    "adjacent": [{"to": "platform", "barrier": "open_door"}]}},
        "positions": {"Ren": "platform", "Marisol": "gallery", "Teo": "gallery"}}
    diff = {"positions": {}, "stations": {
        "Teo": {"at": "station_door", "near": ["Marisol"]},
        "Marisol": {"at": "station_door", "near": ["Teo"]}}}
    ctx = _Ctx(warnings=[], director_interpret={})
    _reconcile_near_group_positions(ctx, scene, diff, "Ren")
    assert not [w for w in ctx.warnings if "Near-group position conflict" in w]
    assert diff["positions"] == {}


# ---------------------------------------------------------------------------
# F28: a leg walked is an arrival in the room between
# ---------------------------------------------------------------------------

def _corridor():
    return {"rooms": {
        "radio": {"name": "Radio", "adjacent": [{"to": "gallery", "barrier": "open_door"}]},
        "gallery": {"name": "Gallery", "adjacent": [
            {"to": "radio", "barrier": "open_door"},
            {"to": "shed", "barrier": "closed_door"},
            {"to": "platform", "barrier": "closed_door"}]},
        "shed": {"name": "Shed", "adjacent": [{"to": "gallery", "barrier": "closed_door"}]},
        "platform": {"name": "Platform", "adjacent": [{"to": "gallery", "barrier": "closed_door"}]},
    }, "positions": {"Ren": "radio"}}


def _heading(to="shed"):
    return {"movement": {"to_room": to, "mover": "self", "arrives": False}}


def test_the_room_between_is_reached_on_the_way():
    """Chat 116 beat 3: 'I pick up the tool roll and head for the shed' from
    the radio room; the beat walked Ren into the gallery and the guard put
    them back in the radio room, which the next beat narrated from."""
    ctx, diff = types.SimpleNamespace(warnings=[]), {"positions": {"Ren": "gallery"}}
    _guard_approach_is_not_arrival(ctx, _heading(), diff, _corridor(), "Ren")
    assert diff["positions"] == {"Ren": "gallery"}
    assert "Approach leg" in ctx.warnings[0]


def test_the_destination_itself_is_still_not_reached():
    ctx, diff = types.SimpleNamespace(warnings=[]), {"positions": {"Ren": "shed"}}
    scene = _corridor()
    scene["positions"]["Ren"] = "gallery"
    _guard_approach_is_not_arrival(ctx, _heading(), diff, scene, "Ren")
    assert diff["positions"] == {}
    assert "Approach is not arrival" in ctx.warnings[0]


def test_a_room_that_is_not_a_step_from_here_is_not_a_leg():
    ctx, diff = types.SimpleNamespace(warnings=[]), {"positions": {"Ren": "platform"}}
    _guard_approach_is_not_arrival(ctx, _heading(), diff, _corridor(), "Ren")
    assert diff["positions"] == {}
    assert "Approach is not arrival" in ctx.warnings[0]


# ===========================================================================
# 2026-09-05: the geometry run (docs/experiments/DEBUG_RUN_2026_09_05.md),
# chats 114/115 and two fresh scenarios on an export-built scratch db.
# ===========================================================================

# ---------------------------------------------------------------------------
# F36: the identity floor covers the episode, not only the view
# ---------------------------------------------------------------------------

def _outcome_ctx():
    return types.SimpleNamespace(warnings=[])


def test_a_strangers_name_in_the_episode_is_repaired_and_reported():
    """Chat 115 (copy), turn 2: Sarah Moon's VIEW read "standing facing the
    young woman" after the tripwire and her EPISODE read "standing facing
    Hinami" -- the body specialist's pose `detail` carried a name she had
    never been given, and the episode was stored as rendered."""
    from agents.perception import _scrub_episode_identities
    ctx = _outcome_ctx()
    roster = [{"name": "Sarah Moon", "appearance": "a lab coat", "aliases": []},
              {"name": "Hinami", "appearance": "a young fox-eared woman", "aliases": []}]
    known = {"Sarah Moon": []}
    content, gist = _scrub_episode_identities(
        ctx, "perception_outcome", "Sarah Moon",
        "I was standing facing Hinami with hands clasped. "
        "\"Science lady, is this lift going down or up?\"",
        "I was standing facing Hinami.", known, roster)
    assert "Hinami" not in content and "Hinami" not in gist
    assert "the young fox-eared woman" in content
    assert "Science lady" in content            # quoted spans are untouched
    assert len(ctx.warnings) == 1
    assert "episode of Sarah Moon" in ctx.warnings[0]
    assert "Hinami" in ctx.warnings[0]


def test_a_recognised_name_in_the_episode_stands():
    from agents.perception import _scrub_episode_identities
    ctx = _outcome_ctx()
    roster = [{"name": "Sarah Moon", "appearance": "", "aliases": []},
              {"name": "Hinami", "appearance": "", "aliases": []}]
    content, gist = _scrub_episode_identities(
        ctx, "perception_outcome", "Sarah Moon",
        "I was standing facing Hinami.", "facing Hinami",
        {"Sarah Moon": ["Hinami"]}, roster)
    assert content == "I was standing facing Hinami." and gist == "facing Hinami"
    assert ctx.warnings == []


# ---------------------------------------------------------------------------
# a plan that attaches to a live room from the planned side
# ---------------------------------------------------------------------------

def test_a_plan_attached_to_a_live_room_from_its_own_side_is_minted(temp_db):
    """Chat 114 (copy), turns 4-6: the Room planned a lighthouse `adjacent:
    [{to: beach}]`; the live beach is in no plan and names nothing back, so
    the fringe never minted the keeper's room, and the Director minted
    `beach_far_end` beside the plan and filed a need the plan answered."""
    from world.structure import materialize_planned_fringe
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Shore", "", time.time()))
    plant_structure(cid, {"key": "lighthouse", "name": "Lighthouse"}, {
        "keeper_room": {"name": "Keeper's Room", "adjacent": [
            {"to": "beach", "barrier": "open_door", "bearing": "s"},
            {"to": "lamp_room", "barrier": "open"}]},
        "lamp_room": {"name": "Lamp Room", "adjacent": [{"to": "keeper_room", "barrier": "open"}]},
    })
    scene = {"rooms": {"beach": {"name": "Beach", "adjacent": [
        {"to": "terrace", "barrier": "open"}]},
        "terrace": {"name": "Terrace", "adjacent": [{"to": "beach", "barrier": "open"}]}},
        "positions": {"Hinami": "beach"}, "entities": {}}
    scene, added = materialize_planned_fringe(cid, scene)
    assert added == 1
    assert "keeper_room" in scene["rooms"]
    assert scene["rooms"]["keeper_room"]["planned"] is True
    exits = {e["to"]: e for e in scene["rooms"]["beach"]["adjacent"]}
    assert "keeper_room" in exits and exits["keeper_room"]["barrier"] == "open_door"
    assert exits["terrace"]["barrier"] == "open"           # the live exit stands
    assert "lamp_room" not in scene["rooms"]              # two hops: not the fringe


def test_a_live_exit_the_room_declared_is_not_overwritten_by_the_plan(temp_db):
    from world.structure import materialize_planned_fringe
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Shore", "", time.time()))
    plant_structure(cid, {"key": "lighthouse", "name": "Lighthouse"}, {
        "keeper_room": {"name": "Keeper's Room", "adjacent": [
            {"to": "beach", "barrier": "closed_door"}]}})
    scene = {"rooms": {"beach": {"name": "Beach", "adjacent": [
        {"to": "keeper_room", "barrier": "open_door", "dir": "n"}]},
        "keeper_room": {"name": "Keeper's Room", "adjacent": [{"to": "beach", "barrier": "open_door"}]}},
        "positions": {"Hinami": "beach"}, "entities": {}}
    scene, added = materialize_planned_fringe(cid, scene)
    assert added == 0
    assert scene["rooms"]["beach"]["adjacent"] == [
        {"to": "keeper_room", "barrier": "open_door", "dir": "n"}]


# ---------------------------------------------------------------------------
# an entity named with its determiner takes no second one
# ---------------------------------------------------------------------------

def test_an_entity_named_with_its_article_is_not_given_another():
    """Chat 114 (copy), turn 2: "You are standing facing the The TARDIS"."""
    from agents.composer import _pose_referent
    scene = {"rooms": {"beach": {"name": "Beach"}},
             "entities": {"tardis": {"name": "The TARDIS", "kind": "object"},
                          "console": {"name": "hexagonal console", "kind": "object"}},
             "positions": {"Hinami": "beach", "tardis": "beach", "console": "beach"}}
    assert _pose_referent(scene, "Hinami", {}, [], "tardis") == "The TARDIS"
    assert _pose_referent(scene, "Hinami", {}, [], "console") == "the hexagonal console"


# ---------------------------------------------------------------------------
# PA1: a body that crosses rooms performs one act per room it is in
# ---------------------------------------------------------------------------
#
# "The Lamp at Sorrow Point" turn 16. Wren left the watch room and walked
# down three rooms; Ivo stayed behind and received, on the SIGHT channel,
# "descends the spiral stair, passing through the store below and stepping
# into the kitchen. ... drops it onto the floor beside the stove." He cited
# it as present evidence and it became rows 69 and 77 of his `memories`. The
# stair is dark and the last hop is through a door.
#
# The rule: a body that crosses rooms performs one act per room it is in, and
# an observer is entitled to the legs that happened where their channel
# stood. One boundary is not the class -- both its rooms are rooms the body
# was in with those observers in them, and they are the two ends of one
# doorway -- so only a walk PAST one boundary is judged here.

def _stack(stair_light="dark"):
    """Watch room over a dark stair over a kitchen, the last hop a door."""
    return {
        "rooms": {
            "watch_room": {"name": "the watch room", "adjacent": [
                {"to": "stair", "barrier": "open"}]},
            "stair": {"name": "the spiral stair", "light": stair_light,
                      "adjacent": [
                          {"to": "watch_room", "barrier": "open"},
                          {"to": "kitchen", "barrier": "open_door"}]},
            "kitchen": {"name": "the kitchen", "adjacent": [
                {"to": "stair", "barrier": "open_door"}]},
        },
        "positions": {"Wren": "kitchen", "Ivo": "watch_room",
                      "Marrick": "kitchen"},
        "entities": {}, "poses": {},
    }


_DESCENT = {
    "event_id": "turn:1:player:0:action",
    "observable": ("grips the cold rail and descends the spiral stair, "
                   "passing through the store below and stepping into the "
                   "kitchen"),
    "visibility": "overt",
}


def test_a_walk_past_one_boundary_names_every_room_the_body_was_in():
    sc = _stack()
    assert crossing_legs(sc, "watch_room", "kitchen") == (
        "watch_room", "stair", "kitchen")
    # Nothing crossed, and one boundary crossed: one room and two rooms.
    assert crossing_legs(sc, "kitchen", "kitchen") == ("kitchen",)
    assert crossing_legs(sc, "watch_room", "stair") == ("watch_room", "stair")


def test_a_door_shut_behind_the_walk_is_still_one_boundary():
    """The outcome scene shows no passable route -- she opened it, crossed
    and shut it -- and that walk is still one step through one doorway."""
    sc = _stack()
    for edge in (sc["rooms"]["stair"]["adjacent"]
                 + sc["rooms"]["kitchen"]["adjacent"]):
        if edge["to"] in ("kitchen", "stair"):
            edge["barrier"] = "closed_door"
    assert crossing_legs(sc, "stair", "kitchen") == ("stair", "kitchen")


def test_a_move_with_no_walkable_route_names_the_rooms_between_as_unknown():
    """Carried, a lift, a door shut behind them: the rooms between are real
    and unnameable, and nobody has a channel to a room the engine cannot
    name."""
    sc = _stack()
    sc["rooms"]["stair"]["adjacent"] = []
    sc["rooms"]["watch_room"]["adjacent"] = []
    sc["rooms"]["kitchen"]["adjacent"] = []
    legs = crossing_legs(sc, "watch_room", "kitchen")
    assert legs == ("watch_room", "", "kitchen")
    assert not perception._channel_to_every_leg(
        sc, None, "Ivo", "watch_room", legs)


def test_the_observer_left_behind_is_entitled_to_the_room_they_stood_in():
    sc = _stack()
    legs = crossing_legs(sc, "watch_room", "kitchen")
    assert perception._multi_room_legs(
        sc, [("Wren", "watch_room", "kitchen")]) == {"Wren": legs}
    # The room she left is his; the store below and the kitchen are not.
    assert not perception._channel_to_every_leg(
        sc, None, "Ivo", "watch_room", legs)
    # And the observer in the room she arrived in is in exactly the same
    # position from the other end: the rooms behind her are not his either.
    assert not perception._channel_to_every_leg(
        sc, None, "Marrick", "kitchen", legs)


def test_a_channel_that_stood_in_every_room_keeps_the_whole_surface():
    """The rule subtracts and only subtracts: an observer who could see the
    whole walk is owed all of it."""
    sc = _stack(stair_light="lit")
    sc["rooms"]["watch_room"]["adjacent"].append(
        {"to": "kitchen", "barrier": "open"})
    sc["rooms"]["kitchen"]["adjacent"].append(
        {"to": "watch_room", "barrier": "open"})
    legs = crossing_legs(sc, "watch_room", "kitchen")
    assert perception._channel_to_every_leg(
        sc, None, "Ivo", "watch_room", legs)


def test_one_boundary_is_left_exactly_as_it_was():
    """The byte-identity freeze: where nothing crossed more than one
    doorway, no act delivery consults this rule at all."""
    sc = _stack()
    assert perception._multi_room_legs(sc, []) == {}
    assert perception._multi_room_legs(
        sc, [("Wren", "watch_room", "stair")]) == {}
    assert perception._multi_room_legs(
        sc, [("Wren", "kitchen", "kitchen")]) == {}
    assert perception._legs_of_actor(sc, {}, "Wren") == ()


def test_the_room_the_walk_crossed_cannot_reach_the_episode():
    """F36's sibling: F36 was an unearned NAME reaching the episode; this is
    an unearned ROOM. The episode is minted from the delivered percepts
    (`composer.render_episode`), so what delivery refuses memory never sees
    -- which is the whole argument for gating delivery rather than the
    memory writer."""
    sc = _stack()
    legs = crossing_legs(sc, "watch_room", "kitchen")
    percepts = [
        composer.environment_percept("watch_room", "the watch room"),
        composer.crossing_percept("Wren", "Wren Calloway", "left"),
    ]
    if perception._channel_to_every_leg(
            sc, None, "Ivo", "watch_room", legs):       # pragma: no cover
        percepts.append(composer.act_percept(
            sc, _DESCENT, "Ivo", "Wren", {"same_room": False},
            display="Wren Calloway", can_see=True))
    content, gist, _entities = composer.render_episode(percepts)
    assert "watch room" in content
    for unearned in ("stair", "store", "kitchen", "stove"):
        assert unearned not in content.lower(), content
        assert unearned not in gist.lower(), gist


def test_the_same_surface_delivered_whole_is_unchanged_by_the_grade():
    """The other half of the freeze: `act_percept`'s default is the sight
    grade it always had."""
    sc = _stack()
    rel = {"same_room": True, "barrier": "open"}
    plain = composer.act_percept(sc, _DESCENT, "Ivo", "Wren", rel,
                                 display="Wren Calloway", can_see=True)
    graded = composer.act_percept(sc, _DESCENT, "Ivo", "Wren", rel,
                                  display="Wren Calloway", can_see=True,
                                  sight="full")
    assert plain == graded
    assert composer._render_event(plain) == composer._render_event(graded)


# ---------------------------------------------------------------------------
# PC1 + PE9: sight is graded, and the act channel spends the grade
# ---------------------------------------------------------------------------
#
# PC1, "The Long Gallery" turns 11-12: Ada and Mrs Penrose behind a locked
# `closed_door`, and a crossing record floors sight at `shapes` for a beat.
# `_in_plain_view` reduced that to a boolean and Lord Edmund read "opens a
# black notebook on her knee" through the door, in the same beat the dialogue
# gate honoured the same wall. PE9 is the same question never asked inside
# one room: `same_room` short-circuits, so an occluder never subtracted.

def _across_a_shut_door():
    sc = {
        "rooms": {
            "great_hall": {"name": "the great hall", "adjacent": [
                {"to": "study", "barrier": "closed_door"}]},
            "study": {"name": "the study", "adjacent": [
                {"to": "great_hall", "barrier": "closed_door"}]},
        },
        "positions": {"Edmund": "great_hall", "Ada": "study"},
        "entities": {}, "poses": {},
        "crossings": {"Ada": {"from": "great_hall", "to": "study",
                              "beats": 1}},
    }
    return sc


def _parlour(screen=True):
    """One room, two chairs nine paces apart, a tall screen between them."""
    anchors = {"west_chair": {"desc": "a chair", "cell": [0, 1]},
               "east_chair": {"desc": "a chair", "cell": [8, 1]}}
    anchors["between"] = ({"desc": "a tall screen", "cell": [4, 1],
                           "height": "full", "opacity": "opaque"} if screen
                          else {"desc": "a low stool", "cell": [4, 1],
                                "height": "knee"})
    return {
        "rooms": {"parlour": {"name": "the parlour", "adjacent": [],
                              "extent": {"w": 9, "d": 3},
                              "anchors": anchors}},
        "positions": {"Ada": "parlour", "Edmund": "parlour"},
        "stations": {"Ada": {"at": "west_chair"},
                     "Edmund": {"at": "east_chair"}},
        "entities": {}, "poses": {},
    }


_NOTEBOOK = {"event_id": "turn:11:0:action", "visibility": "overt",
             "observable": "opens a black notebook on her knee"}


def test_a_crossing_through_a_shut_door_grades_shapes_not_full():
    sc = _across_a_shut_door()
    rel = spatial_rel_between(sc, "Edmund", "Ada",
                              observer_room="great_hall", target_room="study")
    assert rel.get("crossing") is True
    assert perception._sight_detail(sc, "Edmund", "Ada", rel) == "shapes"


def test_a_shapes_grade_admits_motion_and_no_conduct():
    sc = _across_a_shut_door()
    percept = composer.act_percept(
        sc, _NOTEBOOK, "Edmund", "Ada", {"same_room": False},
        display="Ada Quill", can_see=True, sight="shapes")
    assert percept is not None and percept.fidelity == "shapes"
    assert "notebook" not in str(percept.data)
    line = composer._render_event(percept)
    assert "Ada Quill" in line and "notebook" not in line
    episode = composer._episode_sentence(percept)
    assert "notebook" not in episode
    # And `none` refuses outright.
    assert composer.act_percept(
        sc, _NOTEBOOK, "Edmund", "Ada", {"same_room": False},
        display="Ada Quill", can_see=True, sight="none") is None


def test_an_occluder_in_the_same_room_subtracts_from_the_act():
    sc = _parlour()
    rel = spatial_rel_between(sc, "Edmund", "Ada")
    assert rel.get("same_room") is True
    assert perception._sight_detail(sc, "Edmund", "Ada", rel) == "none"


def test_an_open_line_in_the_same_room_is_unchanged():
    """The freeze the owner asked for: with nothing between two bodies in a
    room, the grade is what it always was."""
    sc = _parlour(screen=False)
    rel = spatial_rel_between(sc, "Edmund", "Ada")
    assert perception._sight_detail(sc, "Edmund", "Ada", rel) == "full"
    # And a scene with no geometry at all cannot be subtracted from.
    plain = _stack()
    assert perception._sight_detail(
        plain, "Ivo", "Marrick", {"same_room": True}) == "full"


# ---------------------------------------------------------------------------
# PD3: a fragment loses its words, never its speaker
# ---------------------------------------------------------------------------
#
# "The Ambry Road" turn 20: Sable's view rendered her own employer, three
# paces in front of her in daylight and described in full by the same view,
# as "A muffled voice: ...milestone... ferryman... business...". Her memory
# row said the same, and the narrator sited the voice at a gatehouse nobody
# was standing in.

_LINE = {"speaker": "Corin", "text": "the milestone, the ferryman, business",
         "volume": "normal"}
_MUFFLING = {"same_room": False, "barrier": "closed_door", "distance": "near"}


def test_a_fragment_from_a_visible_speaker_keeps_its_speaker():
    percept = composer.speech_percept(
        _LINE, _MUFFLING, "Sable", display="Corin", can_see=True)
    assert percept.fidelity == "fragment"
    assert percept.data.get("attributed") is True
    assert "Corin" in composer._render_event(percept)
    assert "Corin" in composer._episode_sentence(percept)
    # The WORDS are still degraded: sight answers who, hearing answers what.
    assert "ferryman" in composer._render_event(percept)
    assert "the milestone, the ferryman, business" not in \
        composer._render_event(percept)


def test_a_fragment_from_a_speaker_the_observer_cannot_see_stays_anonymous():
    percept = composer.speech_percept(
        _LINE, _MUFFLING, "Sable", display="a voice", can_see=False)
    assert percept.data.get("attributed") is False
    assert "Corin" not in composer._render_event(percept)
    assert "Corin" not in composer._episode_sentence(percept)


# ---------------------------------------------------------------------------
# PC2: a line cannot be concealed from the person it is addressed to
# ---------------------------------------------------------------------------
#
# "The Long Gallery" turn 17: the player whispered to Edmund at arm's reach.
# The schema floor repaired the one id the FLOW carried and left the other
# exclusion standing -- the addressee -- and the line then appears in no view
# at all, the player's own included.

_CAST_BY_ID = {4: ["felix brand", "felix"], 7: ["lord edmund", "edmund"]}
_CAST_BY_NAME = {"Felix Brand": ["felix brand", "felix"],
                 "Lord Edmund": ["lord edmund", "edmund"]}


def _whisper(conceal_from):
    return [{"type": "speech", "visibility": "concealed",
             "text": "You carried it out yourself.",
             "targets": ["Lord Edmund"], "conceal_from": list(conceal_from)}]


def test_a_line_is_not_concealed_from_the_person_it_is_addressed_to():
    sequence = _whisper(["Lord Edmund", 4])
    notes = strip_addressee_concealment(sequence, _CAST_BY_ID, _CAST_BY_NAME)
    assert sequence[0]["conceal_from"] == [4]
    assert sequence[0]["visibility"] == "concealed"
    assert any("own addressee" in note for note in notes)


def test_a_line_concealed_from_its_addressee_alone_stops_being_concealed():
    """Emptying the list is not excluding nobody -- both readers treat an
    empty `conceal_from` as hidden from everyone but the actor -- so the
    concealment goes and audibility is left to volume and distance."""
    sequence = _whisper(["edmund"])
    notes = strip_addressee_concealment(sequence, _CAST_BY_ID, _CAST_BY_NAME)
    assert sequence[0]["conceal_from"] == []
    assert sequence[0]["visibility"] == "overt"
    assert any("audibility left to volume" in note for note in notes)


def test_a_line_concealed_from_everybody_is_reported_as_a_dropped_beat():
    """A line concealed from every body the beat knows about is a
    declaration the engine dropped, not a secret it kept, and it says so."""
    sequence = _whisper(["Felix Brand", "Lord Edmund"])
    sequence[0]["targets"] = []
    sequence[0]["intended_target"] = "the man at the door"
    notes = strip_addressee_concealment(sequence, _CAST_BY_ID, _CAST_BY_NAME)
    assert sequence[0]["conceal_from"] == ["Felix Brand", "Lord Edmund"]
    assert any("reaches nobody" in note for note in notes)


def test_stripping_one_addressee_leaves_the_rest_of_the_exclusion_alone():
    """The repair is the addressee and nothing else: Felix stays excluded and
    the line still reaches the man it was said to."""
    sequence = _whisper(["Felix Brand", "Lord Edmund"])
    notes = strip_addressee_concealment(sequence, _CAST_BY_ID, _CAST_BY_NAME)
    assert sequence[0]["conceal_from"] == ["Felix Brand"]
    assert sequence[0]["visibility"] == "concealed"
    assert not any("reaches nobody" in note for note in notes)


def test_an_action_may_still_be_concealed_from_the_person_it_targets():
    """Picking the pocket of somebody you are talking to is exactly that
    shape, so actions are left alone."""
    sequence = [{"type": "action", "visibility": "concealed",
                 "observable": "lifts the key from his coat",
                 "targets": ["Lord Edmund"], "conceal_from": ["Lord Edmund"]}]
    assert strip_addressee_concealment(
        sequence, _CAST_BY_ID, _CAST_BY_NAME) == []
    assert sequence[0]["conceal_from"] == ["Lord Edmund"]


# ---------------------------------------------------------------------------
# PC3: one beat, one field
# ---------------------------------------------------------------------------
#
# "The Long Gallery" turn 16: Ada shouted by name across one open archway and
# the man she was summoning heard nothing in the act pass and the whole line
# in the outcome pass, while a listener behind a shut door got a fragment in
# both. Two floors answered one line, and which one answered depended on
# whether the composite grid happened to place the speaker's room. Every
# relation perception builds for a beat now carries the same field; the
# field's own floor for a raised voice one passable edge away is
# `world/spatial_sound_field.py`'s half and is not built here.

def test_every_relation_perception_builds_for_a_beat_carries_the_field():
    import inspect
    for func in (perception._source_channels, perception._composer_outcome):
        source = inspect.getsource(func)
        for call in re.findall(r"spatial_rel_between\((?:[^()]|\([^()]*\))*\)",
                               source):
            assert "sound=" in call, call
