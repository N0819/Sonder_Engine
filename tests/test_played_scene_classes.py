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

And from the play runs of 2026-09-05:

  * `near` names another body, and a body placed near another stands beside
    it; the anchor's spread decides where a body stands only when nothing
    closer says otherwise (`PLAY_2026_09_05_road.md` § PD1).
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

from agents.background import (_beat_for_presence, _beat_scene,
                               _filtered_player_declaration)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import descriptor_bindings, pick_voice_demand
from world.spatial import merge_scene_with_diff
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
    shaped = _shape_plan_rooms(_plan(["the fish wharves lane",
                                      "west ridge path"]))
    assert shaped["rooms"]["platform"]["frontier"] == [
        "the fish wharves lane", "west ridge path"]


def test_the_field_text_no_longer_asks_for_a_direction():
    text = OPERATION_FIELDS["plan_rooms"]["rooms"]
    assert "<direction>" not in text
    assert "never a direction" in text
    assert "NAME" in text


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
# The 2026-09-05 play runs: the road to Ambry (PD4/PD5/PD7/PD12, F63) and
# Flat 4B (PE8). Each rule is pinned; each live case is named in the
# docstring and nowhere in the assertion.
# ---------------------------------------------------------------------------

def test_a_planned_edge_that_says_nothing_about_its_barrier_is_walkable():
    """PD5, "The Long Road to Ambry": `plan_rooms` marks `barrier?`
    optional, the Writers' Room omitted it on every edge of its five-room
    road, and normalization sealed the road the plan had just drawn. Four
    edges had to be opened by hand before the story could be walked."""
    from world.spatial import (edge_passable, normalize_barrier,
                               normalize_scene_barriers)

    assert normalize_barrier(None) == "open"
    assert normalize_barrier("") == "open"
    assert edge_passable({"to": "ford"}, "wood_road")

    scene = {"rooms": {
        "wood_road": {"name": "Wood Road", "adjacent": [{"to": "ford"}]},
        "ford": {"name": "Ford", "adjacent": [{"to": "wood_road"}]}}}
    normalize_scene_barriers(scene)
    assert [e["barrier"] for e in scene["rooms"]["wood_road"]["adjacent"]] \
        == ["open"]
    assert [e["barrier"] for e in scene["rooms"]["ford"]["adjacent"]] == ["open"]


def test_an_unreadable_barrier_word_still_seals_and_still_says_so():
    """The complement, and the reason silence and an unread word are not the
    same input: a word the vocabulary cannot read is evidence somebody meant
    a surface, and it is reported rather than quietly obeyed."""
    from world.spatial import normalize_barrier

    seen = set()
    assert normalize_barrier("grommet spandrel", unresolved=seen) == "wall"
    assert "grommet spandrel" in seen
    # Punctuation with no word in it is the unread case, not the silent one.
    seen = set()
    assert normalize_barrier("???", unresolved=seen) == "wall"
    assert "???" in seen


# ---------------------------------------------------------------------------
# PD4 / F63: a frontier names a place
# ---------------------------------------------------------------------------

#: The Writers' Room's own published frontiers, verbatim from the road run's
#: plan. Six of these became live registry rooms whose uid was the sentence,
#: 6 of the story's 15 rooms.
ROAD_FRONTIERS = [
    "the river flowing west upstream",
    "dense birch and hazel woods to the west",
    "the dense ring of trees enclosing the camp",
    "bare grassy slopes falling away to the east and west",
    "the village street of Ambry beyond the gate",
    "pasture enclosures flanking the palisade",
    # The market run's, F63's own case.
    "The open sky and rooftop views above the square",
]


@pytest.mark.parametrize("phrase", ROAD_FRONTIERS)
def test_a_frontier_that_is_a_description_is_refused_not_minted(phrase):
    with pytest.raises(ValueError) as caught:
        _shape_plan_rooms(_plan([phrase]))
    assert "describes what lies that way instead of naming it" \
        in str(caught.value)


def test_a_stored_description_mints_nothing_and_is_reported(temp_db):
    """A plan published before the refusal existed still carries them. The
    fringe leaves the axis alone and `structure_warnings` says why, instead
    of minting `the_village_street_of_ambry_beyond_the_gate`."""
    from world.structure import (prepare_frontier_expansion,
                                 structure_warnings)

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Road", "", time.time()))
    structure = {"key": "ambry", "name": "Ambry"}
    rooms = {"gate": {"name": "Gate", "adjacent": [], "frontier": [
        "the village street of Ambry beyond the gate", "far road"]}}
    plant_structure(cid, structure, rooms)
    scene = {"rooms": {"gate": {"name": "Gate", "adjacent": []}},
             "positions": {"Corin": "gate"}}
    scene, _mutations = prepare_frontier_expansion(cid, scene)

    minted = set(scene["rooms"]) - {"gate"}
    assert minted == {"far_road"}     # the name minted; the sentence did not
    assert not any("beyond" in uid for uid in scene["rooms"])

    warnings = structure_warnings(structure, rooms)
    assert any("describes what lies that way" in w for w in warnings)
    assert not any("far road" in w for w in warnings)


# ---------------------------------------------------------------------------
# PE8: a plan may name a room that already exists
# ---------------------------------------------------------------------------

def test_a_plan_that_names_a_live_room_is_not_a_contradiction(temp_db):
    """Flat 4B: `stairwell_fourth_to_third` and `flat_4a_hallway` each
    declared `adjacent: [{to: landing}]`, both landed, the landing carried
    both reciprocals -- and the Room's own contradiction tool reported three
    errors it had not made."""
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Flat", "", time.time()))
    plant_structure(cid, {"key": "block", "name": "Block"}, {
        "stairwell_fourth_to_third": {
            "name": "Stairwell", "adjacent": [{"to": "landing"}]},
        "flat_4a_hallway": {
            "name": "4A Hallway", "adjacent": [{"to": "landing"}]}})
    temp_db.wset(cid, "scene", {"location": "Block", "rooms": {
        "landing": {"name": "Landing", "desc": "Worn lino.", "adjacent": [
            {"to": "stairwell_fourth_to_third"}, {"to": "flat_4a_hallway"}]},
        "stairwell_fourth_to_third": {
            "name": "Stairwell", "planned": True,
            "adjacent": [{"to": "landing"}]},
        "flat_4a_hallway": {"name": "4A Hallway", "planned": True,
                            "adjacent": [{"to": "landing"}]}},
        "positions": {"P": "landing"}, "entities": {}})
    assert run_tool(cid, "inspect_contradictions")["structure"] == []


def test_a_plan_that_names_nothing_at_all_is_still_a_contradiction(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Flat", "", time.time()))
    plant_structure(cid, {"key": "block", "name": "Block"}, {
        "flat_4a_hallway": {"name": "4A Hallway",
                            "adjacent": [{"to": "roof_garden"}]}})
    temp_db.wset(cid, "scene", {"location": "Block", "rooms": {
        "flat_4a_hallway": {"name": "4A Hallway", "planned": True,
                            "adjacent": [{"to": "roof_garden"}]}},
        "positions": {"P": "flat_4a_hallway"}, "entities": {}})
    found = run_tool(cid, "inspect_contradictions")["structure"]
    assert any("targets unknown room roof_garden" in w for w in found)


# ---------------------------------------------------------------------------
# The two dead Writers' Room calls: a reply that is all reasoning and no
# content is a failed attempt, not an answer
# ---------------------------------------------------------------------------

def _reply(message):
    return {"choices": [{"message": message}]}


@pytest.mark.parametrize("message", [
    # F1's own shape: a reasoning STRING.
    {"content": None, "reasoning": "thinking about it" * 40},
    # The road run's: `reasoning_details`, a list of blocks, and no
    # `reasoning` string anywhere. Both Writers' Room calls died here.
    {"content": None, "reasoning_details": [
        {"type": "reasoning.text", "text": "step one" * 40}]},
    # The same class one API generation over.
    {"content": "", "reasoning_content": "step one" * 40},
])
def test_a_reply_that_is_only_reasoning_is_typed_as_one_failure(message):
    from llm.providers import ReasoningBudgetExhausted, _message_content

    with pytest.raises(ReasoningBudgetExhausted):
        _message_content(_reply(message), "prov", "model")


def test_a_message_with_no_trace_either_stays_the_untyped_no_content_error():
    """Only a reply that says nothing about why the answer is missing falls
    to the untyped error; everything else is F1's class and takes F1's path."""
    from llm.providers import (LLMError, ReasoningBudgetExhausted,
                               _message_content)

    with pytest.raises(LLMError) as caught:
        _message_content(_reply({"role": "assistant"}), "prov", "model")
    assert not isinstance(caught.value, ReasoningBudgetExhausted)
    assert "carried no content" in str(caught.value)


def test_reasoning_only_replies_retry_then_fall_to_the_next_candidate(monkeypatch):
    """F1: four attempts, the last three with reasoning disabled, the same
    empty answer each time -- a retry loop that varies one setting cannot
    recover from a failure that setting does not cause. The role's backup
    candidate is what the loop never reached."""
    from llm import providers

    tried = []

    def _candidates(role):
        return [{"model": "first"}, {"model": "second"}]

    def _once(role, system, user, temperature, json_mode, max_tokens, sampler,
              *, resolved, json_schema=None, reasoning_effort_override=None):
        tried.append((resolved["model"], reasoning_effort_override))
        if resolved["model"] == "first":
            raise providers.ReasoningBudgetExhausted("no answer")
        return "the answer"

    monkeypatch.setattr(providers, "resolve_role_candidates", _candidates)
    monkeypatch.setattr(providers, "_chat_complete_once", _once)
    monkeypatch.setattr(providers, "apply_common_prompt_policy", lambda s: s)

    out = providers.chat_complete("planner", "sys", "usr")
    assert out == "the answer"
    # The one lever first, on the model that failed; then the model changes.
    assert [m for m, _ in tried] == ["first", "first", "second"]
    assert tried[1][1] == "off"
    assert tried[2][1] is None

# F60 / PB3 / PA6 / PC6: a room's anchors are ADDED to, never written whole
# ---------------------------------------------------------------------------

def _common_room():
    """The caravanserai's L-shaped main hall as it stood through beat 6: four
    anchors, a cast member stationed at one of them, the innkeeper's post
    naming another."""
    return {
        "rooms": {
            "common_room": {
                "name": "Common Room", "size": "large",
                "desc": "The inn's main hall.",
                "anchors": {
                    "bookroom_door": {"desc": "the bookroom door", "dir": "n"},
                    "counter": {"desc": "the long counter", "dir": "s",
                                "footprint": "run", "height": "waist"},
                    "hearth": {"desc": "the hearth", "dir": "w",
                               "height": "waist"},
                    "trestle_benches": {"desc": "long pine tables and benches",
                                        "dir": "e", "footprint": "run",
                                        "height": "waist",
                                        "opacity": "opaque"},
                },
                "adjacent": [{"to": "bookroom", "barrier": "closed_door",
                              "dir": "n"}]},
            "bookroom": {"name": "Bookroom", "adjacent": [
                {"to": "common_room", "barrier": "closed_door", "dir": "s"}]},
        },
        "positions": {"Halvard": "common_room"},
        "stations": {"Halvard": {"at": "hearth"}},
        "entities": {},
    }


#: The diff the spatial hand actually wrote on caravanserai turn 7 -- one
#: anchor, to record that the door was now open.
_ONE_ANCHOR = {"rooms": {"common_room": {"anchors": {
    "bookroom_door": {"desc": "the bookroom door, a hand's width open"}}}}}


def test_a_diff_naming_one_anchor_leaves_the_rooms_others_standing():
    """Caravanserai turn 7 (PB3), lighthouse turns 4/7/16 (PA6), manor turns
    1 and 9 (PC6): a diff writing one anchor replaced the whole map, so the
    hall went from four anchors to one and stayed there."""
    merged = merge_scene_with_diff(_common_room(), _ONE_ANCHOR)
    anchors = merged["rooms"]["common_room"]["anchors"]
    assert set(anchors) == {"bookroom_door", "counter", "hearth",
                            "trestle_benches"}
    # The named one updates...
    assert anchors["bookroom_door"]["desc"] == \
        "the bookroom door, a hand's width open"
    assert anchors["bookroom_door"]["dir"] == "n"     # ...silence still lands
    # ...and the untouched ones keep the geometry the fields gate on.
    assert anchors["trestle_benches"]["height"] == "waist"
    assert anchors["trestle_benches"]["opacity"] == "opaque"


def test_an_explicit_removal_removes_exactly_one_anchor():
    """A fixture still leaves a room -- through `remove_anchors`, the sibling
    of `remove_adjacent` one level in -- and takes nothing else with it."""
    merged = merge_scene_with_diff(_common_room(), {"rooms": {"common_room": {
        "remove_anchors": ["hearth"]}}})
    assert set(merged["rooms"]["common_room"]["anchors"]) == {
        "bookroom_door", "counter", "trestle_benches"}
    # The channel is consumed by the merge and never reaches the stored blob.
    assert "remove_anchors" not in merged["rooms"]["common_room"]
    # An explicit act outranks a re-echo: naming an anchor and removing it in
    # one beat removes it, under either spelling of the id.
    merged = merge_scene_with_diff(_common_room(), {"rooms": {"common_room": {
        "anchors": {"hearth": {"desc": "the cold hearth"}},
        "remove_anchors": ["Hearth"]}}})
    assert "hearth" not in merged["rooms"]["common_room"]["anchors"]


def test_a_cast_station_at_an_untouched_anchor_survives_the_beat():
    """Brother Halvard had been at the hearth since the opening; after turn 7
    his station read `{"at": None}` because the anchor it named was gone.
    Manor turn 1 measured the same loss one step on -- an unmeasured body,
    `body_cell` None and the grid reporting `source: "none"`, in the room the
    whole beat was happening in."""
    merged = merge_scene_with_diff(_common_room(), _ONE_ANCHOR)
    assert merged["stations"]["Halvard"]["at"] == "hearth"


def test_a_charter_post_anchor_still_places_its_holder():
    """The innkeeper's post names `counter`. With the map written whole she
    stopped standing at her own counter for the rest of the story and was
    dealt a cell instead."""
    from world.charter import normalize_charter
    from world.charter_place import (charter_placements, placement_uid,
                                     rooms_in_frame)
    charter = normalize_charter({
        "key": "inn",
        "posts": {"desk": {"place": "common_room", "anchor": "counter"}},
        "watch": {"desk": "innkeeper"},
        "bodies": {"innkeeper": {"name": "Yusra", "place": "common_room"}}})
    merged = merge_scene_with_diff(_common_room(), _ONE_ANCHOR)
    placed = charter_placements(
        {"items": {"inn": {"state": charter}}}, merged,
        frame_rooms=rooms_in_frame(merged, ("common_room",)))
    yusra = placed[placement_uid("inn", "innkeeper")]
    assert yusra["station"] == {"at": "counter"}
    assert yusra["source"] == "post"


def test_the_backdrop_key_is_unchanged_when_the_room_did_not_change():
    """The picture of the inn's main hall lost its counter, hearth and
    benches: `room_brief`'s walls are built from the anchors, and
    `visual_signature` keys on the brief."""
    from dressing.backdrops import visual_signature
    scene = _common_room()
    before = visual_signature(scene, "common_room")
    # A beat that touches no anchor at all.
    moved = merge_scene_with_diff(scene, {"positions": {"Halvard": "bookroom"}})
    assert visual_signature(moved, "common_room") == before
    # And a beat that re-echoes one anchor verbatim, which is the ordinary way
    # a hand mentions a fixture it is not changing.
    echoed = merge_scene_with_diff(_common_room(), {"rooms": {"common_room": {
        "anchors": {"counter": {"desc": "the long counter", "dir": "s"}}}}})
    assert visual_signature(echoed, "common_room") == before


def test_a_diff_carrying_no_anchors_leaves_every_room_byte_identical():
    """The freeze: the additive rule is a behaviour change to beats that name
    an anchor and to no others."""
    scene = _common_room()
    before = json.dumps(scene["rooms"], sort_keys=True, ensure_ascii=False)
    merged = merge_scene_with_diff(scene, {
        "positions": {"Halvard": "bookroom"},
        "rooms": {"common_room": {"desc": "The inn's main hall, quieter now."}},
        "remove_adjacent": [],
    })
    rooms = json.loads(json.dumps(merged["rooms"], sort_keys=True,
                                  ensure_ascii=False))
    expected = json.loads(before)
    expected["common_room"]["desc"] = "The inn's main hall, quieter now."
    assert rooms == expected


# ---------------------------------------------------------------------------
# F49 / PB7: a pose detail belongs to the room the pose was struck in
# ---------------------------------------------------------------------------

def _two_room_stack():
    return {
        "rooms": {
            "courtyard": {"name": "Courtyard", "anchors": {
                "well": {"desc": "the stone well", "dir": "n"}},
                "adjacent": [{"to": "upper_gallery", "barrier": "open",
                              "vertical": "up"}]},
            "upper_gallery": {"name": "Upper Gallery", "adjacent": [
                {"to": "courtyard", "barrier": "open", "vertical": "down"}]},
        },
        "positions": {"Tamsin": "courtyard"},
        "entities": {},
    }


def test_a_movers_own_pose_detail_naming_the_room_entered_is_retired():
    """Caravanserai turn 13 (PB7), on the PLAYER's own body. Turn 12 she
    tipped her head back toward the gallery from the courtyard; turn 13 she
    climbed to the gallery and her own outcome view opened "You are standing
    -- head tipped back toward the upper gallery above. You are in Upper
    Gallery." A detail predating the move that names the room the body now
    stands in was written from OUTSIDE it."""
    scene = _two_room_stack()
    scene["poses"] = {"Tamsin": {
        "posture": "standing",
        "detail": "head tipped back toward the upper gallery above"}}
    merged = merge_scene_with_diff(
        scene, {"positions": {"Tamsin": "upper_gallery"}})
    assert merged["poses"]["Tamsin"]["detail"] == ""
    assert merged["poses"]["Tamsin"]["posture"] == "standing"  # subtracts only


def test_a_movers_own_pose_detail_naming_the_room_left_is_retired():
    """House turn 6 (F49): Wren walked from the corridor into the parlour and
    kept `detail: "standing near the coat-stand, looking down toward the
    turn"`, so the parlour view placed her at the corridor's coat-stand."""
    scene = {
        "rooms": {
            "corridor": {"name": "Corridor", "anchors": {
                "coat_stand": {"desc": "a tall coat-stand at the turn"}},
                "adjacent": [{"to": "parlour", "barrier": "open_door"}]},
            "parlour": {"name": "Parlour", "adjacent": [
                {"to": "corridor", "barrier": "open_door"}]},
        },
        "positions": {"Wren": "corridor"}, "entities": {},
        "poses": {"Wren": {"posture": "standing", "detail":
                           "standing near the coat-stand, looking down "
                           "toward the turn"}},
    }
    merged = merge_scene_with_diff(scene, {"positions": {"Wren": "parlour"}})
    assert merged["poses"]["Wren"]["detail"] == ""


def test_a_movers_detail_is_spent_on_the_move_even_when_it_named_no_place():
    """WIDENED 2026-09-05 (rush, PR1). The rule used to subtract only where
    the prose reached for somewhere, tested against the engine's own rooms
    and anchors. A world whose establish minted no anchors has no vocabulary
    to match against, so the test matched nothing and a body was delivered
    "prone against the tar paper beside the hatch" from the far roof -- and
    no vocabulary can catch a place the engine has no record of.

    "arms folded, hood up" would have travelled honestly and goes anyway.
    That is the price of never describing a body by a place it has left."""
    scene = _two_room_stack()
    scene["poses"] = {"Tamsin": {"posture": "standing",
                                 "detail": "arms folded, hood up"}}
    merged = merge_scene_with_diff(
        scene, {"positions": {"Tamsin": "upper_gallery"}})
    assert merged["poses"]["Tamsin"]["detail"] == ""
    assert merged["poses"]["Tamsin"]["posture"] == "standing"


def test_a_pose_detail_this_beat_wrote_for_the_room_entered_stands():
    """The hand that moved the body and wrote the prose in one breath was
    writing about the destination; the merge does not get to know better."""
    scene = _two_room_stack()
    scene["poses"] = {"Tamsin": {"posture": "standing", "detail": "old prose"}}
    merged = merge_scene_with_diff(scene, {
        "positions": {"Tamsin": "upper_gallery"},
        "poses": {"Tamsin": {"posture": "standing", "detail":
                             "one hand on the upper gallery balustrade"}}})
    assert merged["poses"]["Tamsin"]["detail"] == \
        "one hand on the upper gallery balustrade"


# ---------------------------------------------------------------------------
# PC7: a move that did not happen leaves nothing behind
# ---------------------------------------------------------------------------

def test_a_refused_walk_leaves_room_station_and_pose_as_they_were():
    """Manor turn 13. The declared walk to the long gallery was refused
    (`barrier=separated`, the door she had just locked) and Ada stayed in the
    study -- while the committed pose read "standing on the flagged floor of
    the long gallery after passing beneath the stone archway" and her
    companion's pose put her at the study door from the outside. The narrator
    wrote the scene from the poses, so the reader ended the beat with two
    people in the gallery and the engine with two locked in the study."""
    scene = {
        "rooms": {
            "study": {"name": "Study", "anchors": {
                "desk": {"desc": "the writing desk", "dir": "n"}},
                "adjacent": [{"to": "hall", "barrier": "closed_door"}]},
            "hall": {"name": "Hall", "adjacent": [
                {"to": "study", "barrier": "closed_door"}]},
            "long_gallery": {"name": "Long Gallery", "anchors": {
                "archway": {"desc": "the stone archway", "dir": "w"}}},
        },
        "positions": {"Ada": "study", "Penrose": "study"},
        "stations": {"Ada": {"at": "desk", "near": [], "cell": [2, 2]},
                     "Penrose": {"at": "desk", "near": []}},
        # Spelled with all six pose fields so the comparison below is against
        # the normalized shape and measures the refusal, not `_clean_pose`.
        "poses": {"Ada": {"posture": "standing", "support": "",
                          "relative_to": "", "relation": "", "constraint": "",
                          "detail": "at the desk"}},
        "entities": {},
    }
    keys = ("positions", "stations", "poses")
    before = json.dumps({k: scene[k] for k in keys}, sort_keys=True)
    merged = merge_scene_with_diff(scene, {
        # What the backstop leaves behind: the position it popped, recorded.
        "movement_refused": [{"subject": "Ada", "to_room": "long_gallery"},
                             {"subject": "Penrose", "to_room": "long_gallery"}],
        # ...and everything the beat wrote FOR the walk it did not make.
        "positions": {"Ada": "long_gallery", "Penrose": "long_gallery"},
        "stations": {"Ada": {"at": "archway", "cell": [7, 1]}},
        "poses": {"Ada": {"posture": "standing", "detail":
                          "standing on the flagged floor of the long gallery "
                          "after passing beneath the stone archway"},
                  "Penrose": {"posture": "standing", "detail":
                              "at the locked study door with an ear pressed "
                              "against the cold oak panel"}},
    })
    assert json.dumps({k: merged[k] for k in keys}, sort_keys=True) == before


def test_a_refusal_holds_back_only_the_bodies_it_names():
    """One body refused does not freeze the beat for anybody else."""
    scene = {
        "rooms": {"study": {"name": "Study", "adjacent": [
            {"to": "hall", "barrier": "open"}]},
            "hall": {"name": "Hall", "adjacent": [
                {"to": "study", "barrier": "open"}]}},
        "positions": {"Ada": "study", "Penrose": "study"}, "entities": {},
    }
    merged = merge_scene_with_diff(scene, {
        "movement_refused": [{"subject": "Ada", "to_room": "hall"}],
        "positions": {"Ada": "hall", "Penrose": "hall"}})
    assert merged["positions"] == {"Ada": "study", "Penrose": "hall"}


def test_the_backstop_records_every_body_it_holds_back():
    """The producer half of PC7: the consumer above can only subtract what
    the backstop names, and until 2026-09-05 the backstop named nobody.

    Manor run, turn 8: the declared walk into the gallery was refused at a
    wall, the position was popped, and the pose written for the arrival
    survived -- so the ledger held a body posed in a room she had never
    entered. `_refuse_movement` writes one record per body at the moment
    its position is popped: the declarer, and each companion the same beat
    sent to the same destination.
    """
    from agents.director import _refuse_movement

    sd = {"positions": {}}
    _refuse_movement(sd, "Ada", "long_gallery")
    _refuse_movement(sd, "Penrose", "long_gallery")
    assert sd["movement_refused"] == [
        {"subject": "Ada", "to_room": "long_gallery"},
        {"subject": "Penrose", "to_room": "long_gallery"}]

    # The mover is reachable from both the declarer branch and the stranded
    # sweep; a body refused twice was still refused once.
    _refuse_movement(sd, "Ada", "long_gallery")
    assert len(sd["movement_refused"]) == 2

    # A refusal to a DIFFERENT destination is a different refusal.
    _refuse_movement(sd, "Ada", "terrace")
    assert sd["movement_refused"][-1] == {"subject": "Ada",
                                          "to_room": "terrace"}

    # A nameless subject is no record: the merge matches on identity, and a
    # blank would refuse nothing while looking like it refused something.
    _refuse_movement(sd, "  ", "terrace")
    assert len(sd["movement_refused"]) == 3


def test_a_blocked_walk_leaves_no_trace_of_the_arrival(monkeypatch):
    """End to end over the two halves: what the backstop pops, the merge
    subtracts, so a refused walk leaves room, station and pose untouched."""
    from agents.director import _refuse_movement
    from world.spatial import merge_scene_with_diff

    scene = {
        "rooms": {
            "hall": {"name": "Hall",
                     "adjacent": [{"to": "long_gallery", "barrier": "wall"}]},
            "long_gallery": {"name": "Long Gallery", "anchors": {}},
        },
        "positions": {"Ada": "hall"},
        "stations": {"Ada": {"at": "", "near": [], "cell": [1, 1]}},
        "poses": {"Ada": {"posture": "standing", "support": "",
                          "relative_to": "", "relation": "",
                          "constraint": "", "detail": "just inside the hall"}},
        "entities": {},
    }
    keys = ("positions", "stations", "poses")
    before = json.dumps({k: scene[k] for k in keys}, sort_keys=True)

    # What the resolve wrote for a walk through a wall, and what the
    # backstop does about it.
    sd = {"positions": {"Ada": "long_gallery"},
          "stations": {"Ada": {"at": "archway", "cell": [7, 1]}},
          "poses": {"Ada": {"posture": "seated",
                            "detail": "on the gallery window seat"}}}
    sd["positions"].pop("Ada")
    _refuse_movement(sd, "Ada", "long_gallery")

    merged = merge_scene_with_diff(scene, sd)
    assert json.dumps({k: merged[k] for k in keys}, sort_keys=True) == before

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
# PX4: a concealment names a body, and a name the scene cannot resolve is a
# failure to be reported, never a permission
# ---------------------------------------------------------------------------

def _resolve(sequence):
    from agents.director import resolve_concealment_refs
    return resolve_concealment_refs(sequence, _CAST_BY_ID, _CAST_BY_NAME)


def test_a_conceal_from_spelling_the_reader_cannot_match_is_canonicalised():
    """`composer.concealed_from_observer` is the firewall reader and it holds
    no scene: it matches the observer's own name, id and `character:<id>`
    form and nothing else. The Director writes whichever spelling it reached
    for, and the two need not be the same word."""
    sequence = _whisper(["felix"])
    sequence[0]["targets"] = []
    assert _resolve(sequence) == []
    assert sequence[0]["conceal_from"] == ["character:4", "Felix Brand"]


def test_a_conceal_from_naming_nobody_keeps_the_line_concealed_and_warns():
    """It failed OPEN, in the direction that discloses, silently. Measured
    (the Cold Season Ball, 2026-09-05, PX4): the player's own declaration
    carried `conceal_from: ["character:sault", "character:ivo"]`, neither
    entry matched anything, the reader's default is `return False`, and Ivo
    received the line in full in his composed view. No warning in the beat.

    `character:<x>` is a form the ENGINE mints and the model is copying, so
    one that resolves to nobody is a reference that failed, and the safe
    reading of "I meant to hide this from somebody I cannot name" is to keep
    it hidden -- from every body the beat knows about that this line is not
    addressed to, which still delivers it to the person it was said to.
    Over-concealing costs a beat; under-concealing costs the plot."""
    sequence = _whisper(["character:ivo", "character:sault"])
    notes = _resolve(sequence)
    assert any("engine form" in note for note in notes), notes
    kept = sequence[0]["conceal_from"]
    # Felix is not the addressee, so the line is withheld from him...
    assert "character:4" in kept or "Felix Brand" in kept
    # ...and the man it was addressed to still hears it.
    assert "character:7" not in kept and "Lord Edmund" not in kept


def test_a_bare_name_the_scene_does_not_hold_is_left_alone_and_reported():
    """The one case this cannot tell from a typo, and the reason the engine
    form is treated differently. "Don't tell the Doctor" names a third party
    who is not in the room; concealing that line from everybody present would
    delete a declaration rather than keep a secret."""
    sequence = _whisper(["the_doctor"])
    sequence[0]["targets"] = []
    notes = _resolve(sequence)
    assert sequence[0]["conceal_from"] == ["the_doctor"]
    assert any("no body in this scene answers to" in note for note in notes)


def test_a_star_exclusion_is_left_exactly_as_it_is():
    sequence = _whisper(["*"])
    sequence[0]["targets"] = []
    assert _resolve(sequence) == []
    assert sequence[0]["conceal_from"] == ["*"]


def test_resolving_an_already_resolved_exclusion_changes_nothing():
    sequence = _whisper(["felix"])
    sequence[0]["targets"] = []
    _resolve(sequence)
    first = list(sequence[0]["conceal_from"])
    assert _resolve(sequence) == []
    assert sequence[0]["conceal_from"] == first


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

# F29/F54: a quoted line is welded once, by the code that owns quoting
# ---------------------------------------------------------------------------

def _weld(prose, lines, language):
    from language_runtime import language_scope
    from agents.narration import _substitute_dialogue_tokens
    with language_scope(language):
        return _substitute_dialogue_tokens(prose, lines, language=language)


@pytest.mark.parametrize("language,expected", [
    ("en", 'He turns. "Mind the rail." She does not answer.'),
    ("ja", "He turns. 「Mind the rail.」 She does not answer."),
])
def test_a_line_the_model_wrapped_in_quotes_reaches_the_page_in_one_pair(
        language, expected):
    """Five play runs, the majority of beats in each (F29, F54; PA10 turn 12,
    PB9, PD11 turn 18, PE7 -- 31 false guard warnings in the flat run alone):
    the model reads DIALOGUE FIDELITY, writes the token inside quote marks,
    and the engine welded a second pair around it. The marks are the engine's,
    in the form the page's own language uses, and there is one pair of them."""
    prose, missing = _weld(
        'He turns. "{{L1}}" She does not answer.', ["Mind the rail."],
        language)
    assert prose == expected
    assert missing == []


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_marks_the_model_chose_do_not_survive_into_the_page(language):
    """Any pair, not the one pair this repo happened to measure: a Japanese
    story's narrator wrapping 「...」 and an English one wrapping curly
    quotes are the same fault, and the weld is the same answer."""
    for wrapped in ("“{{L1}}”", "「{{L1}}」", '""{{L1}}""'):
        prose, _missing = _weld(wrapped, ["Mind the rail."], language)
        marks = ("「", "」") if language == "ja" else ('"', '"')
        assert prose == marks[0] + "Mind the rail." + marks[1]


@pytest.mark.parametrize("language", ["en", "ja"])
def test_a_line_that_already_carries_marks_is_not_wrapped_twice(language):
    """The other half of the same class: the body handed over is the words,
    and marks that rode in on it are the view's, not a second pair."""
    prose, _missing = _weld("{{L1}}", ['"Mind the rail."'], language)
    assert prose.count('"') + prose.count("「") + prose.count("」") == 2


def test_a_correctly_rendered_muffled_fragment_is_not_invented_dialogue():
    """PA10, lighthouse turn 12. A half-heard line reaches the view UNQUOTED
    (`A muffled voice: ...deafen... glass... midnight...`), so a narrator that
    correctly puts the fragment in the reader's ear as a quote was told it had
    invented dialogue -- and that warning is enforceable, so the false positive
    bought a rewrite. Invented means the view never DELIVERED it, not that the
    view did not QUOTE it."""
    from agents.common import _check_narrator_fidelity
    view = ("A muffled voice: ...deafen... glass... midnight...\n"
            'Ivo Marrick says in a level voice: "The lamp is lit."')
    out = {"prose": ('Ivo Marrick answers, "The lamp is lit." Below, through '
                     'the glass, "...deafen... glass... midnight..."')}
    warnings = _check_narrator_fidelity(out, view)
    assert not [w for w in warnings if w.startswith("Narrator invented")]


def test_a_line_the_view_never_carried_is_still_invented():
    """The guard subtracts; it does not stop asking. A quoted span whose words
    appear nowhere in the view has no authorised speaker."""
    from agents.common import _check_narrator_fidelity
    view = 'Ivo Marrick says in a level voice: "The lamp is lit."'
    out = {"prose": '"The lamp is lit." Then, "And the fog bell?"'}
    warnings = _check_narrator_fidelity(out, view)
    assert [w for w in warnings if w.startswith("Narrator invented")]


# ---------------------------------------------------------------------------
# F59: a view is composed in one language
# ---------------------------------------------------------------------------

def test_the_japanese_pose_sentence_is_wholly_japanese():
    """PA14 (`youはbracedleaning。`), PD11, PE6. Two faults in one
    sentence: `you` is the composer's own second-person TOKEN and had a
    Japanese word waiting in the pack, and the clauses were concatenated the
    way Japanese joins clauses -- which fuses two Latin words into one that
    was never written."""
    from agents.composer import Percept, render_view
    pose = Percept(
        kind="pose", channel="sight", source_label="you", fidelity="full",
        data={"posture": "膝をついて",
              "support": "石床",
              "relative_to": "祭壇", "relation": "下",
              "constraint": "縛られて"},
        salience=0.8, order_key=0, dedupe_key="pose:self")
    assert render_view([pose], language="ja").text == (
        "あなたは祭壇の下に"
        "石床の上に縛られて"
        "膝をついている。")


def test_a_pose_written_in_another_language_keeps_its_own_words_unfused():
    """The residual PD11/PE5, registered as an owner decision: free prose is
    in the language of the beat that wrote it, and a view in another language
    reproduces it rather than inventing a translation. What it may not do is
    weld two of those words together -- the FRAME is Japanese, the authored
    words keep the spacing their own script requires."""
    from agents.composer import Percept, render_view
    pose = Percept(
        kind="pose", channel="sight", source_label="you", fidelity="full",
        data={"posture": "half-crouch", "support": "the ground",
              "relative_to": "the crest", "relation": "below"},
        salience=0.8, order_key=0, dedupe_key="pose:self")
    text = render_view([pose], language="ja").text
    assert text == ("あなたはthe crestのbelowに"
                    "the groundの上にhalf-crouch。")
    assert "belowthe" not in text


def test_the_non_awake_residue_is_composed_in_the_views_own_language():
    """The same class one kind over, and the whole view rather than a clause:
    `_compose_residue_view` reads the pack through the ambient story language,
    which nothing sets outside a turn -- so an unconscious mind's Japanese
    view came back entirely in English. The pack had the Japanese text."""
    from agents.composer import Percept, render_view
    residue = Percept(
        kind="residue", channel="interoception", source_label="you",
        fidelity="full", data={"level": "unconscious", "pain": True},
        salience=1.0, order_key=0, dedupe_key="residue")
    text = render_view([residue], language="ja").text
    assert text and not re.search(r"[A-Za-z]", text)

# The commit-side classes found by playing, 2026-09-05 (PA2, PA9, PA13, PB5,
# PB11, PE10, PE11). Every patch below names the module that DEFINES what it
# intercepts, never `persist.commit`, which is a facade.
# ---------------------------------------------------------------------------

def _play_chat(temp_db, scene, name="Play"):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     (name, "", time.time()))
    temp_db.wset(cid, "scene", scene)
    return cid


def _play_ctx(temp_db, cid, diff, *, turn_idx=1, name="Play"):
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    ctx = PipelineContext(
        chat=ChatData(id=cid, name=name, persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_idx, chat_id=cid, idx=turn_idx, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": diff}
    return ctx


# ---------------------------------------------------------------------------
# PA9: the beat's notices are composed, not raced
# ---------------------------------------------------------------------------

def test_a_notice_filed_before_the_sweep_survives_the_sweeps_rewrite(temp_db):
    """The lighthouse run, 2026-09-05: a `steadiness: failing` great lamp went
    out at the commits of turns 5 and 11, `_record_failed_sources` filed the
    notice both times in `prepare_scene_commit` -- before the write lock --
    and `commit_transit_sweep`, the first domain inside it, wrote the key
    whole from its own list. Both notices were gone before the beat ended,
    the Director's payload carried `engine_notices: []` on turns 6 and 12,
    and the whole `steadiness` mechanism was inert for a twenty-turn run."""
    from persist import commit
    from world.spatial import fails_on

    scene = {"rooms": {"watch": {"name": "Watch Room", "light": "dark",
                                 "exposure": "enclosed"}},
             "positions": {"lamp": "watch"},
             "entities": {"lamp": {"name": "the great lamp",
                                   "light_source": "bright",
                                   "steadiness": "failing"}}}
    out = next(b for b in range(200) if fails_on(b, "lamp"))
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {"time": "a moment later"}, turn_idx=out)

    prepared = commit.prepare_scene_commit(ctx)
    assert any("has gone out" in n
               for n in temp_db.wget(cid, "engine_notices", []))
    commit.commit_transit_sweep(ctx, 0, prepared=prepared)

    notices = temp_db.wget(cid, "engine_notices", [])
    assert any("has gone out" in n for n in notices), notices
    # And a notice filed AFTER the rewrite lands beside it: the destruction
    # domain runs later in the same transaction.
    commit.add_engine_notice(None, cid, "the pier has been razed.")
    notices = temp_db.wget(cid, "engine_notices", [])
    assert any("has gone out" in n for n in notices)
    assert "the pier has been razed." in notices


def test_the_beats_notice_list_is_composed_once_without_repeats():
    from persist.commit import compose_engine_notices

    ctx = types.SimpleNamespace(engine_feedback=["staged", "shared"])
    assert compose_engine_notices(ctx, ["swept", "shared"]) == [
        "swept", "shared", "staged"]
    assert compose_engine_notices(None, ["swept", "swept"]) == ["swept"]


def test_the_previous_beats_notices_do_not_accumulate(temp_db):
    """The key is beat-scoped: the sweep's rewrite retires the last beat's
    list, which is exactly why nothing else may write it whole."""
    from persist import commit
    cid = _play_chat(temp_db, {"rooms": {"r": {"name": "R"}},
                               "positions": {}, "entities": {}})
    temp_db.wset(cid, "engine_notices", ["last beat's news"])
    ctx = _play_ctx(temp_db, cid, {"time": "a moment later"}, turn_idx=2)
    prepared = commit.prepare_scene_commit(ctx)
    commit.commit_transit_sweep(ctx, 0, prepared=prepared)
    assert temp_db.wget(cid, "engine_notices", []) == []


# ---------------------------------------------------------------------------
# PA2: an event is not a state
# ---------------------------------------------------------------------------

def _bell_scene(running=False):
    return {"rooms": {"watch": {"name": "Watch Room"}},
            "positions": {"bell": "watch", "Wren": "watch"},
            "entities": {"bell": {"name": "the fog bell",
                                  "sound_source": "loud",
                                  "state": {"running": running}}}}


def test_a_noise_written_as_this_beats_act_does_not_run_into_the_next():
    """The lighthouse run turn 11: the bell was pulled ONCE and the objects
    hand wrote `state.running: true` beside its authored `sound_source:
    loud`. Nothing cleared it, and for nine beats every view in the watch
    room read "the noise drowns everything" -- the closing line of turn 20,
    spoken at a half-deaf man's good ear at arm's reach, reached nobody.
    The engine already spells the difference: a `*_action` key lives for the
    beat that asserted it, a switch does not."""
    from world.spatial import merge_scene_with_diff
    from world.spatial import _running

    once = merge_scene_with_diff(_bell_scene(), {"entities": {
        "bell": {"state": {"sound_action": "rung once, the stroke dying"}}}})
    assert once["entities"]["bell"]["state"]["sound_action"]
    # The next beat says nothing about the bell: the act is over, and the
    # thing is not emitting on it.
    after = merge_scene_with_diff(once, {"time": "a moment later"})
    assert "sound_action" not in (after["entities"]["bell"].get("state") or {})
    assert _running(after["entities"]["bell"]) is False

    # A switch that was thrown is a fact about the world and keeps standing.
    running = merge_scene_with_diff(_bell_scene(), {"entities": {
        "bell": {"state": {"running": True}}}})
    still = merge_scene_with_diff(running, {"time": "a moment later"})
    assert _running(still["entities"]["bell"]) is True


def test_the_beat_that_starts_an_emission_is_told_it_started_one(temp_db):
    from persist import commit
    cid = _play_chat(temp_db, _bell_scene())
    ctx = _play_ctx(temp_db, cid,
                    {"entities": {"bell": {"state": {"running": True}}}})
    commit.prepare_scene_commit(ctx)
    notices = temp_db.wget(cid, "engine_notices", [])
    assert any("RUNNING" in n and "bell" in n for n in notices), notices
    assert any("event of that beat" in n for n in notices)


def test_a_beat_that_says_nothing_about_a_running_source_is_told_nothing(temp_db):
    """A standing generator is not news every beat; a warning that fires
    always carries no information."""
    from persist import commit
    cid = _play_chat(temp_db, _bell_scene(running=True))
    ctx = _play_ctx(temp_db, cid, {"time": "a moment later"})
    commit.prepare_scene_commit(ctx)
    assert temp_db.wget(cid, "engine_notices", []) == []


def test_the_objects_hand_is_told_an_event_is_not_a_state():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "language_packs"
    # The clause named the distinction from 2026-09-04 and had nowhere to
    # send the event: it pointed a one-off at the resolved prose or at a
    # `_action` state key, neither of which anybody can hear. Since
    # 2026-09-05 there is a channel, so the clause points at THAT
    # (`docs/UNBUILT.md` \u00a7 1.117) -- the distinction is unchanged and the
    # destination is real.
    for lang, phrase in (("en", "AN EMISSION IS A STATE"),
                         ("ja", "\u767a\u3059\u308b\u3053\u3068\u306f\u72b6\u614b")):
        text = (root / lang / "cards" / "system_prompts" / "specialists"
                / "objects" / "chunks" / "entities.txt").read_text("utf-8")
        assert phrase in text, lang
        assert "sensory_events" in text, lang
        assert "state.running" in text, lang


# ---------------------------------------------------------------------------
# PA13 / PE11: a mint with no room, and a mint of a thing already there
# ---------------------------------------------------------------------------

def _flat_scene():
    return {"rooms": {"hall": {"name": "Hallway"},
                      "kitchen": {"name": "Kitchen"}},
            "positions": {"Wren": "kitchen"},
            "entities": {"buzzer": {"name": "Door Buzzer", "kind": "object",
                                    "sound_source": "loud"}},
            "contained": {}}


def test_a_mint_with_no_room_is_put_where_the_beat_is(temp_db):
    """Lighthouse turns 14 and 18 (`watch_room_storm_pane`, `box_of_matches`)
    and Flat 4B turns 5 and 14 (`kitchen_sink_tap`, minted unplaced twice
    because nothing ever placed the first): the resolve warned correctly and
    nothing acted on the warning."""
    from persist import commit
    scene = _flat_scene()
    scene["positions"]["buzzer"] = "hall"
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {
        "positions": {"Wren": "kitchen"},
        "entities": {
            "kitchen_sink_tap": {"name": "kitchen sink tap", "kind": "fixture",
                                 "sound_source": "audible"}}})
    sc = commit.prepare_scene_commit(ctx)["scene"]
    assert sc["positions"]["kitchen_sink_tap"] == "kitchen"
    assert any("minted with no room" in n
               for n in temp_db.wget(cid, "engine_notices", []))


def test_a_mint_the_beat_cannot_place_is_not_given_an_invented_room(temp_db):
    """Where the beat cannot say where the player is, nothing is placed:
    inventing a room for a thing is worse than leaving it nowhere."""
    from persist import commit
    scene = _flat_scene()
    scene["positions"] = {}
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {"entities": {
        "kitchen_sink_tap": {"name": "kitchen sink tap", "kind": "fixture"}}})
    sc = commit.prepare_scene_commit(ctx)["scene"]
    assert "kitchen_sink_tap" not in sc["positions"]


def test_a_mint_naming_a_thing_the_scene_holds_makes_no_second_one(temp_db):
    """Flat 4B turn 2: `door_buzzer` stood in the hallway with `sound_source:
    loud` and had just sounded, and the beat minted a second buzzer beside
    it. `dedup_minted_rooms` has had this floor for rooms since it existed."""
    from persist import commit
    scene = _flat_scene()
    scene["positions"]["buzzer"] = "hall"
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {"entities": {
        "intercom": {"name": "Door Buzzer", "kind": "object",
                     "state": {"running": True}}}})
    sc = commit.prepare_scene_commit(ctx)["scene"]
    assert "intercom" not in sc["entities"]
    assert sc["entities"]["buzzer"]["state"]["running"] is True
    assert sc["positions"]["buzzer"] == "hall"
    assert any("scene already holds" in n
               for n in temp_db.wget(cid, "engine_notices", []))


def test_a_genuinely_new_thing_beside_an_old_one_is_still_minted(temp_db):
    """A second lamp beside a lamp is a real second lamp; only a mint calling
    itself by the standing thing's OWN name is the standing thing."""
    from persist import commit
    scene = _flat_scene()
    scene["positions"]["buzzer"] = "hall"
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {"entities": {
        "kettle": {"name": "the kettle", "kind": "object"}}})
    sc = commit.prepare_scene_commit(ctx)["scene"]
    assert "kettle" in sc["entities"]


# ---------------------------------------------------------------------------
# PB11 / PE10: a need is what nobody has planned
# ---------------------------------------------------------------------------

def _need(subject, kind="thing", room="", reason="generation_request"):
    return {"kind": kind, "reason": reason, "subject": subject,
            "surface": {"room": room} if room else {}}


def test_a_need_for_a_thing_standing_in_the_named_room_is_not_filed(temp_db):
    """Flat 4B turn 2: the commit filed "the beat reached for thing 'intercom
    buzzer' no plan holds" while `door_buzzer` stood in that hallway,
    sounding."""
    from persist.commit import _drop_needs_the_beat_answers
    scene = _flat_scene()
    scene["positions"]["buzzer"] = "hall"
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {})
    kept = _drop_needs_the_beat_answers(
        ctx, [_need("intercom buzzer", room="hall")])
    assert kept == []
    assert any("already holding it" in m for m in ctx.engine_feedback)


def test_a_need_for_a_thing_in_a_room_that_does_not_hold_it_is_filed(temp_db):
    from persist.commit import _drop_needs_the_beat_answers
    scene = _flat_scene()
    scene["positions"]["buzzer"] = "hall"
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {})
    kept = _drop_needs_the_beat_answers(
        ctx, [_need("intercom buzzer", room="kitchen")])
    assert [n["subject"] for n in kept] == ["intercom buzzer"]


def test_a_need_whose_subject_is_a_sentence_is_refused(temp_db):
    """Flat 4B turn 6 filed "the beat reached for thing 'I say to nobody in
    particular, I go back down the hall' no plan holds" -- a whole clause
    offered to the Writers' Room as an object to author."""
    from persist.commit import _drop_needs_the_beat_answers
    cid = _play_chat(temp_db, _flat_scene())
    ctx = _play_ctx(temp_db, cid, {})
    kept = _drop_needs_the_beat_answers(ctx, [
        _need("I say to nobody in particular, I go back down the hall")])
    assert kept == []
    assert any("reads as a sentence" in m for m in ctx.engine_feedback)


def test_a_room_need_and_a_setting_fact_are_never_dropped_here(temp_db):
    """A place and a fact are not bodies: this filter answers only for what
    the beat was already holding in its hands."""
    from persist.commit import _drop_needs_the_beat_answers
    cid = _play_chat(temp_db, _flat_scene())
    ctx = _play_ctx(temp_db, cid, {})
    needs = [_need("Hallway", kind="room"),
             _need("The cable car runs once a day, and stops at dusk.",
                   reason="setting_fact")]
    assert _drop_needs_the_beat_answers(ctx, needs) == needs


def test_a_need_naming_a_body_the_beat_carried_is_answered_by_it(
        temp_db, monkeypatch):
    """The caravanserai run turn 3: "the beat reached for thing 'the woman
    with the keys at her belt' no plan holds", while the same beat's payload
    carried "Innkeeper Yusra Qadan ... wearing a dark house-coat, a ring of
    keys at the belt", standing at the counter the player addressed."""
    import persist.commit_mapping as mapping
    cid = _play_chat(temp_db, _flat_scene())
    ctx = _play_ctx(temp_db, cid, {})
    figures = [{"name": "Yusra Qadan", "room": "hall", "role": "innkeeper",
                "appearance": "wearing a dark house-coat, a ring of keys "
                              "at the belt"}]
    original = mapping._answering_bodies

    def _answering(cid_, ctx_, scene, rooms):
        rows = list(original(cid_, ctx_, scene, rooms))
        for row in figures:
            rows.append((set(mapping._need_words(
                " ".join(str(row[f]) for f in ("name", "role", "appearance")))),
                row["room"], "the beat"))
        return rows

    # Patched on the module that DEFINES it: a patch on the facade's
    # re-export is silently inert (docs/experiments/AUDIT_COMMIT.md).
    monkeypatch.setattr(mapping, "_answering_bodies", _answering)
    kept = mapping._drop_needs_the_beat_answers(
        ctx, [_need("the woman with the keys at her belt", kind="person",
                    room="hall")])
    assert kept == []


def test_a_name_the_worlds_plans_already_hold_files_no_need(temp_db):
    """PQ13, quiet run 2026-09-05. The Writers' Room published a
    `plan_entity` for Jem Clough; four beats later the commit filed *"the beat
    reached for thing 'Jem Clough' no plan holds"* -- for a person whose plan
    the world was holding, in the ledger this reads from. A need is what
    NOBODY has planned, and a published plan is a plan; asking the Room to
    author a second Jem Clough is what not looking costs."""
    from persist.commit import _drop_needs_the_beat_answers
    from world.planned_entities import add_planned_entity

    cid = _play_chat(temp_db, _flat_scene())
    ctx = _play_ctx(temp_db, cid, {})
    add_planned_entity(cid, {"kind": "person", "name": "Jem Clough",
                             "role": "caller",
                             "brief": {"where": "hall"}})
    assert _drop_needs_the_beat_answers(
        ctx, [_need("Jem Clough", kind="person", room="hall")]) == []


def test_one_word_in_common_is_not_an_answer(temp_db):
    """The threshold is the whole of the care: this reads free prose, so it
    fails toward filing. One shared word is a coincidence between any two
    nouns in English."""
    from persist.commit import _drop_needs_the_beat_answers
    scene = _flat_scene()
    scene["positions"]["buzzer"] = "hall"
    cid = _play_chat(temp_db, scene)
    ctx = _play_ctx(temp_db, cid, {})
    kept = _drop_needs_the_beat_answers(ctx, [_need("a brass hallway key")])
    assert [n["subject"] for n in kept] == ["a brass hallway key"]


# ---------------------------------------------------------------------------
# PB5: enrolment is membership, and membership is for people
# ---------------------------------------------------------------------------

def _mule_scene():
    return {"rooms": {"courtyard": {"name": "Courtyard"}},
            "positions": {"tamsin_mule": "courtyard"},
            "entities": {"tamsin_mule": {
                "name": "Tamsin's Pack Mule", "kind": "animal",
                "description": "A sturdy, dust-caked grey pack mule."}}}


def test_a_beast_the_scene_placed_is_not_enrolled_as_a_person():
    """The caravanserai opening enrolled `tamsin_mule` (kind `animal`) as a
    guest of the house and dealt it a tall wiry ruddy young body with a
    black braid and a torn ear. `animal` is on `_ANIMATE_ENTITY_KINDS` --
    the list that answers "must this occupy a room" -- so the speech verdict
    read "person"."""
    from persist.commit import (presence_has_an_identity,
                                presence_is_enrollable)
    scene = _mule_scene()
    record = {"name": "Tamsin's Pack Mule", "entity_id": "tamsin_mule"}
    # Its NAME is still nobody's to withhold, and it may still be voiced:
    # this narrows enrolment only.
    assert presence_has_an_identity(scene, "Tamsin's Pack Mule", record) is True
    assert presence_is_enrollable(scene, "Tamsin's Pack Mule", record) is False


def test_a_presence_the_scene_never_placed_as_a_thing_is_enrolled():
    """A person the Director rendered with no plan behind them has no entity
    record at all: the provenance is already person-shaped."""
    from persist.commit import presence_is_enrollable
    assert presence_is_enrollable(
        {"rooms": {"quay": {"name": "Quay"}}, "positions": {}, "entities": {}},
        "Dock Hand", {"name": "Dock Hand"}) is True


def test_the_frozen_nature_settles_it_in_both_directions():
    from persist.commit import presence_is_enrollable
    scene = _mule_scene()
    assert presence_is_enrollable(scene, "Tamsin's Pack Mule", {
        "name": "Tamsin's Pack Mule", "entity_id": "tamsin_mule",
        "nature": "person"}) is True
    assert presence_is_enrollable(
        {"rooms": {}, "positions": {}, "entities": {}},
        "Dock Hand", {"name": "Dock Hand", "nature": "thing"}) is False


def test_a_beast_that_has_spoken_is_a_person_by_conduct():
    """Conduct is this engine's standard of proof everywhere else, and the
    two Daleks in the corpus are the only `undecided` presences that ever
    took a turn at speech."""
    from persist.commit import presence_is_enrollable
    scene = _mule_scene()
    assert presence_is_enrollable(scene, "Tamsin's Pack Mule", {
        "name": "Tamsin's Pack Mule", "entity_id": "tamsin_mule",
        "dialogue_turns": [3]}) is True

# PB1/PB6: being addressed changes who is PICKED, never what was HEARD --
# and a description is resolved against the room the beat puts the speaker in
# ---------------------------------------------------------------------------

GALLERY = "upper_gallery"
YARD = "courtyard"

# The caravanserai's shape, turn 13: two rooms one shut door apart. Measured
# on that scene, `Sef Ul -> Tamsin` grades `none` at whisper and `fragment`
# at ordinary speech, so neither volume clears the FULL bar an address needs.
_HOUSE_ROOMS = {
    YARD: {"name": "Courtyard", "adjacent": [
        {"to": GALLERY, "barrier": "closed_door", "dir": "u"}]},
    GALLERY: {"name": "Upper Gallery", "adjacent": [
        {"to": YARD, "barrier": "closed_door", "dir": "d"}]},
}

# `charter_surface.appearance_text`'s own shape -- adjectives, the role
# noun, "with" the hair and marks, "wearing" what is worn -- so the words the
# ENGINE joins with are the ones every body in a cohort shares, and fall out
# of the match by construction rather than by being listed.
APRON = ("young broad-shouldered ruddy person, with a black braid, "
         "wearing a long apron")
APRON_2 = ("middle-aged rangy sallow person, with a shaved scalp, "
           "wearing a long apron")
NO_APRON = ("boyish rangy square sun-darkened quick-stepping person, with "
            "hair bound in a cloth, a missing front tooth")


def _presence(where, appearance, role):
    return {"first_turn": 1, "last_turn": 4, "where": where,
            "sketch": {"station_room": where, "appearance": appearance,
                       "role_hint": role}}


def _house(temp_db, presences, *, opens_in=YARD, ends_in=GALLERY,
           refs=(), volume="whisper", line="Which of these doors is free?",
           rooms=None, stations=None):
    """A chat standing the player in `opens_in` with a diff that moves her to
    `ends_in` -- the pre-commit read every background reader gets, since the
    stage runs before `persist/commit.py` writes anything."""
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Caravanserai", "", time.time()))
    positions = {"The Stranger": opens_in}
    for name, rec in presences.items():
        positions[name] = rec["where"]
    scene = {"location": "house", "time": "dusk",
             "rooms": json.loads(json.dumps(rooms or _HOUSE_ROOMS)),
             "positions": positions, "entities": {}, "attire": {},
             "overlays": {}}
    if stations:
        scene["stations"] = dict(stations)
    temp_db.wset(cid, "scene", scene)
    temp_db.wset(cid, "background_presences",
                 {name: {k: v for k, v in rec.items() if k != "where"}
                  for name, rec in presences.items()})
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 13, line, time.time()))
    dr = {"resolved_event": "She reaches the rail.",
          "dialogue_log": [{"speaker": "The Stranger", "exact_quote": line,
                            "volume": volume, "visibility": "overt"}],
          "state_diff": {"positions": {"The Stranger": ends_in}}}
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Caravanserai", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=13, player_input=line,
                      created=time.time()),
        cast=[], input=line, director_resolve=dr)
    ctx["director_interpret"] = {
        "flow": {"addressed_to_refs": list(refs)},
        "sequence": [{"type": "speech", "text": line, "volume": volume,
                      "visibility": "overt"}],
        "movement": {"mover": "self", "to_room": ends_in}}
    return ctx, dr


def test_a_presence_that_cannot_hear_the_line_is_not_picked_to_answer_it(temp_db):
    """Caravanserai turn 13 (PLAY_2026_09_05, PB1). Tamsin climbed to the
    upper gallery and said quietly "which of these doors is free?", addressing
    a shape at the balustrade. The gate stamped the pick `channel: exempt` on
    the strength of the address and voiced a boy standing in the courtyard one
    floor below -- `hear_level` none at every volume, both directions -- who
    answered the question's content. An address is a claim about who the
    SPEAKER meant; it is not a channel."""
    ctx, dr = _house(temp_db,
                     {"Sef Ul": _presence(YARD, NO_APRON, "yard boy")},
                     refs=["the shape leaning on the balustrade"])
    assert pick_voice_demand(ctx, dr, cap=1)["picks"] == []


def test_no_percept_of_a_line_it_could_not_hear_reaches_that_presence(temp_db):
    """The other half of the same guarantee: nothing about the beat is
    delivered to a body out of earshot, so even a picked one would have
    nothing to answer from."""
    ctx, dr = _house(temp_db,
                     {"Sef Ul": _presence(YARD, NO_APRON, "yard boy")},
                     refs=["the shape leaning on the balustrade"])
    sc = _beat_scene(ctx, dr)
    assert _filtered_player_declaration(ctx, sc, "Sef Ul", YARD) == ""
    assert _beat_for_presence(dr, sc, YARD, "Sef Ul", beat_room=GALLERY) == ""


def test_the_same_presence_in_the_room_the_beat_ends_in_does_answer(temp_db):
    """The complement, and the reason the fix narrows eligibility rather than
    the address: standing where the line was spoken, the same body hears it
    and is picked. Silence is legitimate; silence everywhere is not."""
    ctx, dr = _house(temp_db,
                     {"Sef Ul": _presence(GALLERY, NO_APRON, "house boy")},
                     refs=["the shape leaning on the balustrade"])
    out = pick_voice_demand(ctx, dr, cap=1)
    assert out["picks"] == ["Sef Ul"]
    assert out["meta"]["Sef Ul"]["player_addressed"] is True
    assert "channel:hearing" in out["meta"]["Sef Ul"]["why"]


def test_a_description_binds_inside_the_room_the_beat_puts_the_speaker_in(temp_db):
    """PB6, and PB1's first cause. Turn 11: "the girl with the apron" bound to
    a trader with no apron and no post while apron-wearing serving hands stood
    in the room. Two rules meet here -- the cohort is the room the beat's own
    diff leaves the speaker in, never the one the stored scene still holds
    her in, and the seeded pick runs over the bodies the description could be
    true of."""
    presences = {
        "Neris Qadan": _presence(GALLERY, APRON, "serving hand"),
        "Ysolde Marr": _presence(GALLERY, APRON_2, "serving hand"),
        "Nuri Haddan": _presence(GALLERY, NO_APRON, "trader"),
        "Hamo Fesk": _presence(YARD, APRON, "serving hand"),
    }
    ctx, dr = _house(temp_db, presences, refs=["the girl with the apron"],
                     volume="normal")
    bound = descriptor_bindings(ctx, dr)["the girl with the apron"]
    assert bound in ("Neris Qadan", "Ysolde Marr")
    # Stable: the gate reads the binding before commit and the debt writer
    # reads it at commit, and the two must be the same body.
    assert descriptor_bindings(ctx, dr)["the girl with the apron"] == bound
    assert pick_voice_demand(ctx, dr, cap=1)["picks"] == [bound]


def test_a_description_nothing_in_the_room_answers_still_binds_in_that_room(temp_db):
    """The narrowing is a preference, not a filter: the binding is a MINT, so
    a description no co-present body answers still resolves -- to somebody in
    the room the beat leaves the speaker in."""
    presences = {"Nuri Haddan": _presence(GALLERY, NO_APRON, "trader"),
                 "Hamo Fesk": _presence(YARD, APRON, "serving hand")}
    ctx, dr = _house(temp_db, presences, refs=["the girl with the apron"],
                     volume="normal")
    assert descriptor_bindings(ctx, dr)[
        "the girl with the apron"] == "Nuri Haddan"


def test_a_whisper_the_sound_model_calls_inaudible_gets_no_reply(temp_db):
    """Same room, and still not reached: a measured `across` in a large room
    grades a whisper to none. The volume is the beat's own, so the gate asks
    the question the line actually poses rather than assuming ordinary
    speech."""
    # THE ANCHORS CARRY BEARINGS, as 96.4% of the owner's 854 live anchors
    # do. Without them the grid seeds both into the room's INTERIOR, where
    # two anchors sit closer together than two on opposite walls and the
    # whisper carries -- a real weakness, measured and registered as
    # `docs/UNBUILT.md` § 1.138, and a separate question from this one. This
    # test asks whether the sound model refuses a whisper across a large
    # room, so it is given the shape the world actually produces.
    rooms = {GALLERY: {"name": "Upper Gallery", "size": "large",
                       "anchors": {"rail": {"dir": "n"},
                                   "stair": {"dir": "s"}}}}
    ctx, dr = _house(
        temp_db, {"Sef Ul": _presence(GALLERY, NO_APRON, "house boy")},
        opens_in=GALLERY, ends_in=GALLERY, rooms=rooms,
        refs=["the shape leaning on the balustrade"],
        stations={"The Stranger": {"at": "rail"}, "Sef Ul": {"at": "stair"}})
    assert pick_voice_demand(ctx, dr, cap=1)["picks"] == []
    # And the same pair at ordinary speech is reached, so the refusal is the
    # sound model's answer about this line and not a rule about the room.
    ctx2, dr2 = _house(
        temp_db, {"Sef Ul": _presence(GALLERY, NO_APRON, "house boy")},
        opens_in=GALLERY, ends_in=GALLERY, rooms=rooms, volume="normal",
        refs=["the shape leaning on the balustrade"],
        stations={"The Stranger": {"at": "rail"}, "Sef Ul": {"at": "stair"}})
    assert pick_voice_demand(ctx2, dr2, cap=1)["picks"] == ["Sef Ul"]

# PD1 (2026-09-05): `near` names a body, and a body near another stands
# beside it -- the anchor's spread places a body only when nothing closer
# says otherwise
# ---------------------------------------------------------------------------

def _scrub_edge(stations, room=None):
    """A 15x20 hilltop with a run anchor along its whole north wall, the
    shape the two bodies were dealt six paces apart on."""
    return {
        "rooms": {"hilltop": {
            "name": "the hilltop", "extent": {"w": 15, "d": 20},
            "light": "lit",
            "adjacent": [],
            "anchors": {
                "scrub_edge": {"desc": "the scrub edge", "dir": "n",
                               "footprint": "run", "height": "waist"},
                "cairn": {"desc": "the cairn", "dir": "s", "height": "waist"},
            }}},
        "positions": {name: room or "hilltop" for name in stations},
        "stations": {k: dict(v) for k, v in stations.items()},
        "poses": {}, "orientation": {}, "entities": {}, "contained": {},
    }


def _apart(scene, a, b):
    from world.spatial import body_cell
    ca, cb = body_cell(scene, a), body_cell(scene, b)
    assert ca is not None and cb is not None
    return max(abs(ca[0] - cb[0]), abs(ca[1] - cb[1])), ca, cb


def test_two_bodies_each_near_the_other_stand_together_at_one_anchor():
    """Turn 18/19/20 of the road run: both stations read `{"at":
    "scrub_edge", "near": [the other]}` and the derived cells were (4, 3)
    and (10, 3) -- six paces apart on a run anchor spanning a fifteen-pace
    wall, while the composed view of the same beat said "within arm's
    reach". The player's line reached neither of them
    (`PLAY_2026_09_05_road.md` § PD1)."""
    sc = _scrub_edge({
        "Sable": {"at": "scrub_edge", "near": ["Corin Ashe"]},
        "Corin Ashe": {"at": "scrub_edge", "near": ["Sable"]},
    })
    gap, ca, cb = _apart(sc, "Sable", "Corin Ashe")
    assert gap <= 1, (ca, cb)
    # Symmetric: the pair's two cells do not depend on which is asked for,
    # and both still stand AT the anchor they named.
    from world.spatial import anchor_cells, body_cell
    again = _apart(sc, "Corin Ashe", "Sable")
    assert (again[2], again[1]) == (ca, cb)
    run = {tuple(c) for c in anchor_cells(sc, "hilltop")["scrub_edge"]["cells"]}
    for cell in (ca, cb):
        assert min(max(abs(cell[0] - x), abs(cell[1] - y))
                   for x, y in run) <= 1


def test_a_body_near_another_stands_beside_it_and_an_authored_cell_wins():
    """`near` outranks the anchor's spread; an authored `cell` is geometry
    and outranks both."""
    one_sided = _scrub_edge({
        "Sable": {"at": "cairn"},
        "Corin Ashe": {"at": "scrub_edge", "near": ["Sable"]},
    })
    assert _apart(one_sided, "Sable", "Corin Ashe")[0] <= 1
    pinned = _scrub_edge({
        "Sable": {"at": "scrub_edge", "near": ["Corin Ashe"],
                  "cell": [12, 9]},
        "Corin Ashe": {"at": "scrub_edge", "near": ["Sable"]},
    })
    from world.spatial import body_cell
    assert body_cell(pinned, "Sable") == (12, 9)


def test_a_pair_standing_together_can_hear_each_other():
    """What the six paces cost: a normal voice between two bodies the scene
    says are together."""
    from world.spatial import hear_level, spatial_rel_between
    sc = _scrub_edge({
        "Sable": {"at": "scrub_edge", "near": ["Corin Ashe"]},
        "Corin Ashe": {"at": "scrub_edge", "near": ["Sable"]},
    })
    rel = spatial_rel_between(sc, "Corin Ashe", "Sable")
    assert hear_level(rel, "normal") == "full"


# ---------------------------------------------------------------------------
# PE2 / PC7 (second half): a shut door on the way is a contest, not a wall
# ---------------------------------------------------------------------------
#
# Flat 4B, 2026-09-05. FOUR of six declared inter-room moves never committed:
# "I go back down the hall and into my bedroom" is kitchen --open-- hallway
# --closed_door-- bedroom, and the backstop answered "no passable route ...
# (barrier=separated); position unchanged" while the identical one-hop
# crossing would have been allowed as CONTESTED. The host moved a body by
# hand three times for the story to continue.
#
# Two rules, and they answer two questions. HOW FAR she got is the floor
# plan's: the walk commits its passable prefix and stops at the first shut
# door. WHAT HAPPENS AT THAT DOOR is causality's, and belongs to the resolve
# exactly as it does at one hop. A wall is neither -- no route reaches it,
# doors counted -- and a walk into one is still refused whole.


def _flat_4b_scene(hall_to_bedroom="closed_door"):
    """kitchen_living --open-- hallway --X-- noors_bedroom, plus a balcony
    the flat can only reach through a wall."""
    return {
        "location": "Flat 4B",
        "rooms": {
            "kitchen_living": {"name": "Kitchen", "adjacent": [
                {"to": "hallway", "barrier": "open", "distance": "near"}]},
            "hallway": {"name": "Hallway", "adjacent": [
                {"to": "kitchen_living", "barrier": "open",
                 "distance": "near"},
                {"to": "noors_bedroom", "barrier": hall_to_bedroom,
                 "distance": "near"}]},
            "noors_bedroom": {"name": "Bedroom",
                              "anchors": {"bed": {"desc": "the bed"}},
                              "adjacent": [
                                  {"to": "hallway", "barrier": hall_to_bedroom,
                                   "distance": "near"}]},
            "balcony": {"name": "Balcony", "adjacent": [
                {"to": "kitchen_living", "barrier": "wall"}]},
        },
        "positions": {"The Stranger": "kitchen_living",
                      "Mara": "kitchen_living"},
        "stations": {}, "poses": {}, "entities": {}, "attire": {},
        "overlays": {},
    }


def _movement_ctx(temp_db, scene, to_room, arrives=True):
    from story.character_schema import default_character_data

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Flat", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}",
         time.time(), "char_mara"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", scene)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "move", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Flat", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="move", created=time.time()),
        cast=cast, input="move")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "movement": {"to_room": to_room, "mover": "self", "arrives": arrives},
        "flow": {"reactors": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    return ctx


def test_a_walk_stopped_by_one_shut_door_lands_at_the_door(temp_db,
                                                           monkeypatch):
    """Turn 6 of the flat. The declared walk crosses one open doorway and
    meets one shut one: she is in the hallway, and the bedroom is contested
    -- not "position unchanged"."""
    import agents.director as director
    from tests.helpers import fanout_resolve_agent

    ctx = _movement_ctx(temp_db, _flat_4b_scene(), "noors_bedroom")
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        # The beat wrote the arrival's prose without asserting the position.
        {"state_diff": {
            "poses": {"The Stranger": {
                "posture": "standing",
                "detail": "just inside the bedroom, the door shut behind"}},
            "stations": {"The Stranger": {"at": "bed"}}}}))

    sd = director.director_resolve(ctx, nonce=0)["state_diff"]

    assert sd["positions"]["The Stranger"] == "hallway"
    assert not [w for w in ctx.warnings if "Blocked movement" in w]
    assert any("Partial movement" in w and "'hallway'" in w
               and "'noors_bedroom'" in w for w in ctx.warnings)
    # The prose written for the room she did not reach goes with the leg she
    # did not walk; the position is true and stays.
    assert "The Stranger" not in sd["poses"]
    assert "The Stranger" not in sd["stations"]
    # She DID move, so nothing is recorded as refused.
    assert not sd.get("movement_refused")


def test_the_resolve_still_owns_whether_the_door_opened(temp_db, monkeypatch):
    """The other half of the contest, and the half PE2 measured: when the
    beat itself says she went through, the walk stands -- the same trust the
    one-hop branch has always extended."""
    import agents.director as director
    from tests.helpers import fanout_resolve_agent

    ctx = _movement_ctx(temp_db, _flat_4b_scene(), "noors_bedroom")
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"The Stranger": "noors_bedroom"}}}))

    sd = director.director_resolve(ctx, nonce=0)["state_diff"]

    assert sd["positions"]["The Stranger"] == "noors_bedroom"
    assert any("Contested crossing honoured" in w and "noors_bedroom" in w
               for w in ctx.warnings)


def test_a_walk_through_a_wall_is_still_refused_whole(temp_db, monkeypatch):
    """The guard's reason for existing. No route reaches the balcony, doors
    counted, so none of the contest rule applies: the position is stripped
    and the refusal is recorded for the merge to subtract."""
    import agents.director as director
    from tests.helpers import fanout_resolve_agent

    ctx = _movement_ctx(temp_db, _flat_4b_scene(), "balcony")
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"The Stranger": "balcony"}}}))

    sd = director.director_resolve(ctx, nonce=0)["state_diff"]

    assert "The Stranger" not in sd["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)
    assert {"subject": "The Stranger", "to_room": "balcony"} \
        in sd["movement_refused"]


def test_a_companion_stops_where_the_mover_stops(temp_db, monkeypatch):
    """The stranded rule from the other side (chat 74). A body the same beat
    sent to the same destination out of the mover's own room walked the same
    edges, so it reaches what the mover reached -- never the room past the
    door the mover could not open, and never one the mover cannot reach."""
    import agents.director as director
    from tests.helpers import fanout_resolve_agent

    ctx = _movement_ctx(temp_db, _flat_4b_scene(), "noors_bedroom")
    monkeypatch.setattr(director, "_agent_json", fanout_resolve_agent(
        {"state_diff": {"positions": {"Mara": "noors_bedroom"}}}))

    sd = director.director_resolve(ctx, nonce=0)["state_diff"]

    assert sd["positions"]["The Stranger"] == "hallway"
    assert sd["positions"]["Mara"] == "hallway"
    assert any("Held the group together" in w for w in ctx.warnings)


def test_a_fully_passable_multi_hop_walk_is_unchanged(temp_db, monkeypatch):
    """The counter-case that keeps the rule honest: with the door open the
    walk commits its destination and says nothing about doors."""
    import agents.director as director

    ctx = _movement_ctx(temp_db, _flat_4b_scene(hall_to_bedroom="open_door"),
                        "noors_bedroom")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    sd = director.director_resolve(ctx, nonce=0)["state_diff"]

    assert sd["positions"]["The Stranger"] == "noors_bedroom"
    assert not [w for w in ctx.warnings if "movement" in w.casefold()]


def test_the_walk_leg_names_the_door_that_stopped_it():
    """The primitive under both branches, and the answer to the objection
    the old comment recorded: the contest IS attributable on a multi-hop
    path, because the walk is followed edge by edge."""
    from agents.director import declared_walk_leg

    scene = _flat_4b_scene()
    assert declared_walk_leg(scene, "kitchen_living", "noors_bedroom") == \
        ("hallway", "noors_bedroom", False)
    # A wall: no route at all, doors counted.
    assert declared_walk_leg(scene, "kitchen_living", "balcony") == \
        ("kitchen_living", None, True)
    # Open throughout: no contest to attribute.
    assert declared_walk_leg(_flat_4b_scene(hall_to_bedroom="open_door"),
                             "kitchen_living", "noors_bedroom") == \
        ("noors_bedroom", None, False)
    # The first edge shut is the one-hop case, and the prefix is the room she
    # already stands in -- the caller's old contested branch, unaltered.
    assert declared_walk_leg(scene, "hallway", "noors_bedroom") == \
        ("hallway", "noors_bedroom", False)


# ---------------------------------------------------------------------------
# PC8 / F65: a title with a name in it is one name
# ---------------------------------------------------------------------------
#
# Manor run, 2026-09-05: "facing Lord you", "before Lord you", "toward Mrs. I
# with practiced, gentle courtesy", "turns away from you you". Twice the
# composer's own tripwire fired and called it an engine defect, which it was.
# The rewrite replaced the name FRAGMENT it happened to hold and left
# whatever stood in front of it -- and, applied shortest-form-first, matched
# inside a name it had already half-rewritten.


def test_a_title_before_a_name_is_rewritten_with_the_name():
    from agents.common import _self_second_person, self_name_forms

    forms = self_name_forms("Edmund Harrowgate", ["Edmund Harrowgate"])
    out = _self_second_person(
        "Penrose stands facing Lord Edmund Harrowgate, then turns before "
        "Lord Edmund Harrowgate.", forms)
    assert out == "Penrose stands facing you, then turns before you."
    assert "Lord you" not in out and "Harrowgate" not in out


def test_the_widest_form_of_one_name_wins_over_its_own_word_tokens():
    """"toward Dov Aharon" became "toward you Aharon" became "toward you
    you": the short form fired inside the long one."""
    from agents.common import _self_second_person, self_name_forms

    forms = self_name_forms("Dov Aharon", ["Dov"])
    out = _self_second_person(
        "Tam Reyes leans forward across the counter toward Dov Aharon.", forms)
    assert out == "Tam Reyes leans forward across the counter toward you."


def test_the_rewrite_leaves_a_third_partys_title_and_name_alone():
    """The observer is somebody else: nothing of Lord Edmund's name is this
    perceiver's, so the sentence is delivered as written."""
    from agents.common import _self_second_person, self_name_forms

    line = "Ada Quill stands facing Lord Edmund Harrowgate."
    assert _self_second_person(
        line, self_name_forms("Mrs Penrose", ["Mrs Penrose"])) == line


def test_the_episodes_first_person_pass_inherits_the_same_boundary():
    """"toward Mrs. I" was the same defect one renderer further on: the
    episode takes "you" to "I", so a title stranded beside a pronoun comes
    back wearing the other person."""
    from agents.common import _self_second_person, self_name_forms
    from agents.composer import _first_person

    forms = self_name_forms("Penrose", ["Penrose"])
    out = _first_person(_self_second_person(
        "He moves toward Mrs. Penrose with practiced, gentle courtesy.",
        forms))
    assert out == "He moves toward me with practiced, gentle courtesy."

# PB4: a body is presented once per view -- as ground in a crowd or as a
# figure, and the two presentations are one subtraction computed once
# (`PLAY_2026_09_05_caravanserai.md` § PB4)
# ---------------------------------------------------------------------------

def _qesh_chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Qesh", "", time.time()))


def _qesh_registry(db, cid, count, room="courtyard"):
    """One institution with ``count`` unposted bodies standing in ``room``."""
    from world.charter_runtime import save_registry
    save_registry(cid, {"qesh_house": {
        "key": "qesh_house", "priority": [], "clock_hours": 0.0,
        "upkeeps": {"water": {"place": room}},
        "posts": {"water_carrier": {"place": room, "serves": ["water"],
                                    "requires": {}}},
        "bodies": {
            "wc%d" % n: {"key": "wc%d" % n, "name": "Ilka Toum %d" % n,
                         "place": room, "berth": room, "available": True,
                         "home_post": "water_carrier", "competence": {}}
            for n in range(count)},
        "watch": {},
    }})


def _qesh_scene(room="courtyard"):
    return {"rooms": {room: {"name": "Courtyard", "adjacent": []}},
            "positions": {}, "entities": {}}


def _presented_names(cid, sc, room):
    """(the crowd rows, the figure names) one view is composed from, read
    through ONE stage's shared inputs, exactly as perception reads them."""
    from agents.common import (charter_crowds_for_room, chatter_inputs,
                               presence_figures_for_room)
    inputs = chatter_inputs(cid, sc, turn_idx=4)
    crowds = charter_crowds_for_room(cid, sc, room, inputs)
    figures = presence_figures_for_room(cid, sc, room, inputs, turn_idx=4)
    return crowds, [str(row["name"]) for row in figures]


def test_a_view_with_a_band_line_does_not_also_name_the_bodies_it_covers(
        temp_db):
    """Caravanserai turn 3: the composed view carried the band line "a
    handful serving hands and wardens" AND eleven individual figure labels
    of the same institution's people. The crowd is the carried set and the
    figures are its complement, so a name cannot be in both."""
    cid = _qesh_chat(temp_db)
    _qesh_registry(temp_db, cid, 7)
    crowds, figures = _presented_names(cid, _qesh_scene(), "courtyard")
    assert len(crowds) == 1, "seven bodies at one place are a crowd"
    assert figures == [], (
        "the band covers these bodies and the view named them too: %r"
        % figures)


def test_a_record_that_lost_its_charter_link_is_still_ground(temp_db):
    """The two readers agreed by REF, and a record whose `charter_refs` were
    never written has none -- so the same person arrived as figure and as
    ground for want of a link nobody stored. The display name is the other
    identity a view has, and it answers the same question."""
    cid = _qesh_chat(temp_db)
    _qesh_registry(temp_db, cid, 7)
    temp_db.wset(cid, "background_presences", {"p1": {
        "name": "Ilka Toum 3", "uid": "p1", "nature": "person",
        "dialogue_turns": [4], "mention_turns": [], "addressed_turns": [],
        "charter_refs": [],
        "sketch": {"station_room": "courtyard", "role_hint": "water carrier"},
    }})
    crowds, figures = _presented_names(cid, _qesh_scene(), "courtyard")
    assert crowds and "Ilka Toum 3" not in figures


def test_every_body_in_the_room_reaches_the_view_as_one_or_the_other(temp_db):
    """Caravanserai turn 12, the other direction: seven bodies in the
    courtyard reached the player as a band and as nobody. Below the crowd
    floor every body is a figure; at or above it every body is ground; the
    union is the institution's people standing there either way."""
    from world.charter_crowd import CHARTER_CROWD_FLOOR
    for count in (CHARTER_CROWD_FLOOR - 1, CHARTER_CROWD_FLOOR + 2):
        cid = _qesh_chat(temp_db)
        _qesh_registry(temp_db, cid, count)
        crowds, figures = _presented_names(cid, _qesh_scene(), "courtyard")
        carried = count if crowds else 0
        assert carried + len(figures) == count, (
            "%d bodies stand there and %d reached the view"
            % (count, carried + len(figures)))
        assert bool(crowds) != bool(figures)


def test_a_scene_with_no_charter_composes_exactly_as_it_did(temp_db):
    """The freeze: a story with no institution pays nothing, reads the same,
    and the scene it was handed is not written to."""
    cid = _qesh_chat(temp_db)
    sc = _qesh_scene()
    before = json.dumps(sc, sort_keys=True)
    crowds, figures = _presented_names(cid, sc, "courtyard")
    assert crowds == [] and figures == []
    assert json.dumps(sc, sort_keys=True) == before


# ---------------------------------------------------------------------------
# PE3: a line is heard from where the speaker stood when they said it
# (`PLAY_2026_09_05_flat.md` § PE3)
# ---------------------------------------------------------------------------

def _pe3_flat_scene():
    return {"rooms": {
        "living_room": {"name": "Living room", "adjacent": [
            {"to": "balcony", "barrier": "closed_door", "dir": "e"}]},
        "balcony": {"name": "Balcony", "adjacent": [
            {"to": "living_room", "barrier": "closed_door", "dir": "w"}]},
    }, "positions": {"Sami Haddad": "living_room"}, "entities": {}}


def test_a_line_after_a_declared_arrival_is_graded_at_the_destination():
    """Flat turn 20: a woman came in from the balcony, put a hand flat on a
    man's shoulder, and the line she said with her hand on him reached both
    cast views as a muffled voice through a shut glass door."""
    sc = _pe3_flat_scene()
    interp = {"movement": {"to_room": "living_room", "mover": "self",
                           "arrives": True}}
    arrival = perception._declared_arrival_room(sc, interp, "balcony")
    assert arrival == "living_room"
    event = {"type": "speech", "text": "You can have the sofa.",
             "targets": ["Sami Haddad"]}
    assert perception._speech_room_for(
        sc, event, arrival, "balcony") == "living_room"


def test_a_line_before_a_declared_departure_is_graded_where_it_was_said():
    """The opposite case, kept right: the beat ends on the balcony and the
    line was said to somebody in the room left behind."""
    sc = _pe3_flat_scene()
    interp = {"movement": {"to_room": "balcony", "mover": "self",
                           "arrives": True}}
    arrival = perception._declared_arrival_room(sc, interp, "living_room")
    assert arrival == "balcony"
    event = {"type": "speech", "text": "Goodnight.",
             "targets": ["Sami Haddad"]}
    assert perception._speech_room_for(
        sc, event, arrival, "living_room") == "living_room"


def test_a_beat_that_declares_no_arrival_grades_every_line_where_it_stood():
    """The floor: a move of a vehicle rather than a body, a declaration that
    only sets off, a destination the scene does not hold, and a move to the
    room the beat already found them in all leave the grading where it was."""
    sc = _pe3_flat_scene()
    for movement in (None,
                     {"to_room": "living_room", "mover": "the_van"},
                     {"to_room": "living_room", "arrives": False},
                     {"to_room": "a_room_nobody_built"},
                     {"to_room": "balcony"}):
        assert perception._declared_arrival_room(
            sc, {"movement": movement}, "balcony") == ""
    event = {"type": "speech", "text": "Hello.", "targets": ["Sami Haddad"]}
    assert perception._speech_room_for(sc, event, "", "balcony") == "balcony"


def test_an_unaddressed_line_keeps_the_room_the_beat_found_the_speaker_in():
    """Widening a channel is the direction a mistake here would leak in, so
    only a line the beat aims at somebody standing in the destination is
    graded there. The residual is registered (`docs/UNBUILT.md` § 1.122)."""
    sc = _pe3_flat_scene()
    interp = {"movement": {"to_room": "living_room", "mover": "self"}}
    arrival = perception._declared_arrival_room(sc, interp, "balcony")
    for event in ({"type": "speech", "text": "Finally."},
                  {"type": "speech", "text": "Hi.", "targets": ["nobody"]}):
        assert perception._speech_room_for(
            sc, event, arrival, "balcony") == "balcony"


# ---------------------------------------------------------------------------
# PD8: an answer that was produced and heard belongs in the view and in the
# log that records who spoke; and a body is enrolled by an institution that
# exists, never by founding one to hold it
# (`PLAY_2026_09_05_road.md` § PD8, second half)
# ---------------------------------------------------------------------------

def _road_ctx(temp_db, *, presence_room):
    """A camp clearing, a cast witness standing in it, and a background
    presence who answers a direct question from ``presence_room``."""
    from story.character_schema import (default_character_data,
                                        default_persona_data)

    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Sable", json.dumps(default_persona_data("Sable")), "{}"))
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Road", "", time.time(), persona_id))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Corin Ashe", json.dumps(default_character_data("Corin Ashe")),
         "{}", time.time(), "char_c"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (cid, char_id, "active", "{}"))
    temp_db.wset(cid, "scene", {
        "location": "the clearing", "time": "evening",
        "rooms": {"clearing": {"name": "Clearing", "desc": "A clearing.",
                               "adjacent": []},
                  "coppice": {"name": "Coppice", "desc": "Cut wood.",
                              "adjacent": []}},
        "positions": {"Sable": "clearing", "Corin Ashe": "clearing",
                      "Hob Tarry": presence_room},
        "entities": {}, "attire": {}, "overlays": {},
    })
    temp_db.wset(cid, "known", {"Corin Ashe": ["Sable", "Hob Tarry"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Road", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "clearing"
    ctx.director_interpret = {
        "action": None, "sequence": [], "speech": None,
        "speech_volume": "normal", "flow": {"reactors": [char_id]}}
    ctx.director_resolve = {
        "resolved_event": "The clamp smokes.", "state_diff": {},
        "dialogue_log": [], "dialogue_order": []}
    ctx["background_react"] = {
        "fired": True, "name": "Hob Tarry",
        "reactions": [{
            "name": "Hob Tarry", "room": presence_room, "action": "",
            "dialogue_log_entry": {
                "speaker": "Hob Tarry", "volume": "normal",
                "exact_quote": "Two days yet, if the wind holds steady."}}]}
    return ctx, char_id


def test_a_produced_background_answer_reaches_the_view_and_the_log(temp_db):
    """Road turn 15: the burner answered a direct question and the line
    reached no view and no dialogue log."""
    from persist.commit import _background_fired_reactions
    ctx, char_id = _road_ctx(temp_db, presence_room="clearing")
    out = perception.perception_outcome(ctx, nonce="n")
    view = out["views"][str(char_id)] or ""
    assert "Two days yet" in view, view
    assert not [w for w in ctx.warnings if "reached no view" in w]
    logged = [r["dialogue_log_entry"]["exact_quote"]
              for r in _background_fired_reactions(ctx.get("background_react"))]
    assert logged == ["Two days yet, if the wind holds steady."]


def test_an_answer_no_channel_carried_is_said_out_loud(temp_db):
    """"The NPC answered and nobody heard" is indistinguishable, in every
    record afterwards, from "the NPC said nothing" unless the beat says
    which it was. The run gave no warning at all."""
    ctx, _char_id = _road_ctx(temp_db, presence_room="coppice")
    perception.perception_outcome(ctx, nonce="n")
    assert [w for w in ctx.warnings
            if "Hob Tarry" in w and "reached no view" in w], ctx.warnings


def test_a_body_is_not_enrolled_by_founding_an_institution_for_it(temp_db):
    """Road turn 15, the other half: a charcoal burner at a woodland camp
    was written into a freshly founded `households` charter, which then
    refused his own greeting as `outside_licence`."""
    from world.charter_enrol import enrol_person
    from world.charter_runtime import registry_for
    cid = _qesh_chat(temp_db)
    rec = enrol_person(cid, {"kind": "person", "surface": {
        "name": "Hob Tarry", "room": "charcoal_camp_clearing"}})
    assert rec["ref"] is None and not rec["charter"]
    assert registry_for(cid)["items"] == {}


# ---------------------------------------------------------------------------
# PB14: a published plan's edge survives the beats after it is published
# (`PLAY_2026_09_05_caravanserai.md` § PB14, the F13 family)
# ---------------------------------------------------------------------------

def _road_plan(cid):
    """Three planned rooms in a line: the gate, the road, the shrine."""
    plant_structure(cid, {"key": "qesh_road", "name": "Qesh road"}, {
        "qesh_gate": {"name": "Gate", "adjacent": [
            {"to": "desert_road_east", "barrier": "open"}]},
        "desert_road_east": {"name": "Desert road", "adjacent": [
            {"to": "qesh_gate", "barrier": "open"},
            {"to": "milestone_shrine", "barrier": "open"}]},
        "milestone_shrine": {"name": "Milestone shrine", "adjacent": [
            {"to": "desert_road_east", "barrier": "open"}]},
    })


def test_a_published_plans_edge_survives_the_beats_after_it_is_published(
        temp_db):
    """Caravanserai turns 6-14: every commit warned "dropped exit(s) from
    `desert_road_east` to undefined room(s) `milestone_shrine`", because the
    fringe supplied the plan's whole adjacency and the dangling-exit guard
    took away the way on to a room nobody had walked toward yet."""
    from world.structure import materialize_planned_fringe
    cid = _qesh_chat(temp_db)
    _road_plan(cid)
    scene = {"rooms": {"qesh_gate": {"name": "Gate", "adjacent": []}},
             "positions": {"Tamsin Vell": "qesh_gate"}, "entities": {}}
    for _beat in range(3):
        scene, _added = materialize_planned_fringe(cid, scene)
        assert "desert_road_east" in scene["rooms"]
        assert prune_dangling_exits(scene) == [], (
            "the plan's own edge was dropped and warned about again")


def test_the_planned_edge_comes_back_the_beat_its_target_is_minted(temp_db):
    """Nothing is lost: the plan keeps the edge, and it returns as soon as
    the scene holds the room on the other side of it."""
    from world.structure import materialize_planned_fringe
    cid = _qesh_chat(temp_db)
    _road_plan(cid)
    scene = {"rooms": {"qesh_gate": {"name": "Gate", "adjacent": []}},
             "positions": {"Tamsin Vell": "qesh_gate"}, "entities": {}}
    scene, _ = materialize_planned_fringe(cid, scene)
    scene["positions"]["Tamsin Vell"] = "desert_road_east"
    scene, _ = materialize_planned_fringe(cid, scene)
    assert "milestone_shrine" in scene["rooms"]
    assert prune_dangling_exits(scene) == []
    assert {e["to"] for e in scene["rooms"]["desert_road_east"]["adjacent"]} \
        == {"qesh_gate", "milestone_shrine"}
    assert protect_planned_edges(cid, scene) == []


def test_a_scene_with_no_plan_is_returned_exactly_as_it_was(temp_db):
    """The freeze."""
    from world.structure import materialize_planned_fringe
    cid = _qesh_chat(temp_db)
    scene = {"rooms": {"gate": {"name": "Gate", "adjacent": []}},
             "positions": {"Tamsin Vell": "gate"}, "entities": {}}
    before = json.dumps(scene, sort_keys=True)
    scene, added = materialize_planned_fringe(cid, scene)
    assert added == 0 and json.dumps(scene, sort_keys=True) == before


# ---------------------------------------------------------------------------
# PA15: a diagnostic that cannot be traced to its cause is a diagnostic
# nobody can act on (`PLAY_2026_09_05_lighthouse.md` § PA15)
# ---------------------------------------------------------------------------

def test_a_tripwires_excerpt_carries_enough_text_to_find_the_sentence():
    """Lighthouse turn 9: the self-narration tripwire fired on live data,
    repaired the view correctly, and printed `'Marrick...'` -- a fragment
    the sentence splitter had cut down to nothing findable, in a view of a
    thousand characters."""
    view = ("You are standing in the lantern room. The light turns above "
            "you, unevenly. Marrick. He does not look up from the brass "
            "housing, and the rain goes on against the glass.")
    excerpt = perception._excerpt_in(view, "Marrick.")
    assert "Marrick." in excerpt
    assert len(excerpt) >= 40 + len("Marrick.")
    assert excerpt.strip(".") in view


def test_an_excerpt_the_text_no_longer_holds_is_still_reported():
    """A repair may rewrite what it reports, and a bounded excerpt of the
    fragment beats no excerpt at all."""
    assert perception._excerpt_in("a repaired view", "gone") == "gone"
    assert perception._excerpt_in("anything", "") == ""

# Four hands that could see something true and had no channel to say it
# (the play runs of 2026-09-05). Each is the class, not the case:
#
#   * taking cover is a fact about which side of a fixture a body stands on,
#     and the geometry has had a place for it since the prototype -- what was
#     missing was the field reaching the geometry at all (manor § PC9);
#   * a thing is hidden by something being between it and the room, and that
#     something has a name; a sentence saying it is hidden is read by nothing
#     (manor § PC5);
#   * a room's own fixture is a contact endpoint like any other -- a body
#     leans on it, sets its back against it (caravanserai § PB10);
#   * one object, one name, whichever hand is speaking: a doorway answers to
#     `door:<room>` for the hand that places bodies and for the hand that
#     records touch alike (flat § PE12).
# ---------------------------------------------------------------------------


def _gallery(stations, extra_anchors=None):
    """A lit 11x11 gallery with an opaque, head-high folding screen pinned
    across the middle and a waist-high hearth to the south of it -- the shape
    the manor's turn 15 was played on."""
    anchors = {
        "folding_screen": {"desc": "the folding screen", "dir": "n",
                           "cell": [5, 5], "footprint": "run",
                           "height": "head", "opacity": "opaque"},
        "hearth": {"desc": "the hearth", "dir": "s", "cell": [5, 9],
                   "height": "waist"},
    }
    anchors.update(extra_anchors or {})
    return {
        "rooms": {"gallery": {"name": "the long gallery", "light": "lit",
                              "extent": {"w": 11, "d": 11}, "adjacent": [],
                              "anchors": anchors}},
        "positions": {name: "gallery" for name in stations},
        "stations": {k: dict(v) for k, v in stations.items()},
        "poses": {}, "orientation": {}, "entities": {}, "contained": {},
    }


def test_a_body_that_takes_cover_is_out_of_the_line_that_crosses_the_fixture():
    """PC9. The station said WHERE (the screen) and nothing said WHICH SIDE,
    so a body that stepped behind an opaque, head-high screen was judged by
    sight, light and sound as standing in the open on the room's side of it.
    """
    from world.spatial import body_visibility

    stations = {"Ada Quill": {"at": "folding_screen"},
                "Edmund": {"at": "hearth"},
                "Penrose": {"at": "alcove"}}
    alcove = {"alcove": {"desc": "the alcove", "dir": "n", "cell": [5, 1],
                         "height": "waist"}}

    open_ = _gallery(stations, alcove)
    assert body_visibility(open_, "Edmund", "Ada Quill")["fraction"] == 1.0

    covered = dict(stations)
    covered["Ada Quill"] = {"at": "folding_screen", "cover": "folding_screen"}
    behind = _gallery(covered, alcove)

    # The line that CROSSES the screen loses her, and names what took her.
    across = body_visibility(behind, "Edmund", "Ada Quill")
    assert across["visible"] is False and across["fraction"] == 0.0
    assert across["occluded_by"] == "the folding screen"

    # The line that does NOT cross it is untouched: cover is a fact about one
    # fixture, not a cloak.
    same_side = body_visibility(behind, "Penrose", "Ada Quill")
    assert same_side["visible"] is True and same_side["fraction"] == 1.0


def test_the_station_table_carries_the_cover_the_hand_was_told_to_write():
    """The other half of PC9, and the whole of why the clause had no effect:
    the spatial chunk has said `cover:true` or an anchor id since 2026-09-02
    and `_coerce_station_table` kept only `at` and `near`, so the field never
    survived the round trip into the merge.

    A bare `true` is canonicalized against the `at` of the same entry, and
    station hygiene keeps it honest across beats: stations merge PARTIALLY,
    so left alone a cover would ride into the next station this body is given
    and put it behind a fixture nobody ducked behind.
    """
    from llm.schemas import DirectorSpatialSpecialist, StateDiff
    from world.spatial import merge_scene_with_diff

    hand = DirectorSpatialSpecialist(
        stations={"Ada Quill": {"at": "folding_screen", "cover": True}})
    assert hand.stations["Ada Quill"]["cover"] == "folding_screen"

    named = StateDiff(stations={"Ada Quill": {"at": "folding_screen",
                                              "cover": "folding_screen"}})
    assert named.stations["Ada Quill"]["cover"] == "folding_screen"

    # ...and a station that says nothing about cover carries no `cover` key,
    # which is exactly the record every scene has today.
    plain = StateDiff(stations={"Ada Quill": {"at": "hearth"}})
    assert "cover" not in plain.stations["Ada Quill"]

    # Cover is about the fixture the body is AT, so stepping to another one
    # leaves nothing to be behind and the merge cleans it -- the sibling of
    # the stale `at` and the stale `near` that hygiene already clears.
    behind = _gallery({"Ada Quill": {"at": "folding_screen",
                                     "cover": "folding_screen"}})
    assert behind["stations"]["Ada Quill"]["cover"] == "folding_screen"
    moved = merge_scene_with_diff(
        behind, {"stations": {"Ada Quill": {"at": "hearth"}}})
    assert "cover" not in moved["stations"]["Ada Quill"]


def _tower_and_gallery():
    """A ledger authored inside a window seat, one open doorway from the
    gallery the player is standing in -- the manor's turns 14 and 18."""
    return {
        "rooms": {
            "tower": {"name": "the tower room", "light": "lit",
                      "extent": {"w": 8, "d": 8},
                      "adjacent": [{"to": "gallery", "barrier": "open",
                                    "dir": "s"}],
                      "anchors": {"window_seat": {"desc": "the window seat",
                                                  "dir": "n"}}},
            "gallery": {"name": "the long gallery", "light": "lit",
                        "extent": {"w": 8, "d": 8},
                        "adjacent": [{"to": "tower", "barrier": "open",
                                      "dir": "n"}],
                        "anchors": {}},
        },
        "positions": {"Ada Quill": "gallery", "estate_ledger": "tower"},
        "stations": {}, "poses": {}, "orientation": {}, "contained": {},
        "entities": {
            "window_seat": {"name": "the window seat", "kind": "container",
                            "container": True, "state": {"open": False}},
            "estate_ledger": {
                "name": "the estate ledger", "kind": "object",
                "portable": True,
                "scent": "old paper, binding paste, dry leather"},
        },
    }


def test_a_thing_shut_inside_a_scene_object_is_revealed_by_opening_it():
    """PC5. The ledger was authored `state: {concealment: "hidden inside the
    locked tower window seat"}` -- a key no reader in the engine consults --
    so its own scent reached the player a room away through a shut chest, and
    the beat that opened the seat could only flip that string to "exposed",
    which the reconciliation reported as prose the diff does not encode.

    The record that carries the fact is the one the engine already keeps, and
    every field subtracts from it for free. Revealing is RELEASING it, which
    is what makes finding a hidden thing an act with a result.
    """
    import copy

    from world.spatial import (hiding_holders_of, merge_scene_with_diff,
                               scent_level, spatial_rel_between)

    hidden = merge_scene_with_diff(copy.deepcopy(_tower_and_gallery()), {
        "containment": {"estate_ledger": {"in": "window_seat",
                                          "mode": "container"}}})
    assert hiding_holders_of(hidden, "estate_ledger") == ["window_seat"]
    # A carried thing has no position of its own: it is wherever its holder
    # is, which is the room the seat stands in.
    assert hidden["positions"]["estate_ledger"] == "tower"
    shut = spatial_rel_between(hidden, "Ada Quill", "estate_ledger")
    assert shut["concealed"] is True
    assert scent_level(shut) != "full"

    found = merge_scene_with_diff(copy.deepcopy(hidden), {
        "containment": {"estate_ledger": None},
        "entities": {"window_seat": {"state": {"open": True}}}})
    assert hiding_holders_of(found, "estate_ledger") == []
    assert found["positions"]["estate_ledger"] == "tower"
    open_seat = spatial_rel_between(found, "Ada Quill", "estate_ledger")
    assert not open_seat.get("concealed")
    assert scent_level(open_seat) == "full"


def _caravanserai(positions=None):
    """A caravanserai common room whose counter is an ANCHOR and not an
    entity, with a shut door onto the yard."""
    return {
        "rooms": {
            "common_room": {
                "name": "the common room", "light": "lit",
                "extent": {"w": 10, "d": 10},
                "adjacent": [{"to": "yard", "barrier": "closed_door",
                              "dir": "e"}],
                "anchors": {"counter": {"desc": "the long counter",
                                        "dir": "w"}}},
            "yard": {"name": "the yard", "light": "lit",
                     "extent": {"w": 8, "d": 8},
                     "adjacent": [{"to": "common_room",
                                   "barrier": "closed_door", "dir": "w"}],
                     "anchors": {}},
        },
        "positions": positions or {"Rasa Oren": "common_room"},
        "stations": {}, "poses": {}, "orientation": {}, "contained": {},
        "entities": {},
    }


def _touch(target, actor="Rasa Oren", part="elbows", manner="lean"):
    return {"op": "add", "actor": actor, "actor_part": part,
            "target": target, "target_part": "", "manner": manner,
            "relation": "surface", "motion": "settled"}


def test_a_contact_naming_a_rooms_own_fixture_lands():
    """PB10. Three beats in a row the contact hand refused an ordinary act --
    "counter is not an indexed entity; cannot record contact for elbows on
    counter" -- with `counter` an anchor of the room the player stood in.
    Even had it written the op, the merge would have dropped it: contact
    hygiene asks `positions` where each endpoint is, and a fixture has no
    position of its own.
    """
    import copy

    from world.spatial import (contact_thing_label, contacts_of,
                               effective_station, merge_scene_with_diff)

    leaning = merge_scene_with_diff(copy.deepcopy(_caravanserai()),
                                    {"contact_ops": [_touch("counter")]})
    [contact] = contacts_of(leaning, "Rasa Oren")
    assert contact["target"] == "counter" and contact["actor_part"] == "elbows"

    # A body against the furniture is a body AT it: the station the hand
    # never writes falls out of the ledger it does.
    assert effective_station(leaning, "Rasa Oren")["at"] == "counter"

    # And the room vouches for the fixture as a THING, so the identity floor
    # that feeds the narrator does not mint a person out of it.
    assert contact_thing_label(leaning, "counter") == "the long counter"

    # Fail-open: a target no index names is as unrecordable as it was.
    nothing = merge_scene_with_diff(copy.deepcopy(_caravanserai()),
                                    {"contact_ops": [_touch("chandelier")]})
    assert contacts_of(nothing, "Rasa Oren") == []


def test_the_same_doorway_answers_to_both_hands_under_one_id():
    """PE12. The interpret's contact hand refused ("door is not in
    entity_names") while the resolve's wrote a contact whose target was a
    ROOM ID and whose part was a prose label -- two vocabularies for one
    object, so what one hand wrote the other could not read. The engine has
    owned the name all along: `effective_anchors` contributes `door:<room>`
    for every edge, which is the id the hand that places bodies already uses
    for `at`.
    """
    import copy

    from agents import director
    from world.spatial import (contacts_of, effective_anchors,
                               effective_station, merge_scene_with_diff)

    scene = _caravanserai()
    assert "door:yard" in effective_anchors(scene, "common_room")

    # The hand that places bodies names it...
    stationed = merge_scene_with_diff(
        copy.deepcopy(scene), {"stations": {"Rasa Oren": {"at": "door:yard"}}})
    assert effective_station(stationed, "Rasa Oren")["at"] == "door:yard"

    # ...and the hand that records touch names the same object the same way.
    against = merge_scene_with_diff(
        copy.deepcopy(scene),
        {"contact_ops": [_touch("door:yard", part="back", manner="rest")]})
    [contact] = contacts_of(against, "Rasa Oren")
    assert contact["target"] == "door:yard"

    # Both because the contact hand is now SHOWN the id, beside the room's
    # authored fixtures: it can no longer reach for a room id or a phrase.
    payload = director._specialist_payload(
        "contact", None, scene,
        {"source": "resolved_beat", "player": "Rasa Oren", "cast": [],
         "declared_actions": [], "dice": {}, "prose": "She leans back.",
         "dialogue": [], "manifest": []},
        {})
    assert sorted(payload["anchors"]["common_room"]) == ["counter", "door:yard"]
    assert payload["anchors"]["common_room"]["door:yard"]


def test_a_beat_that_uses_none_of_these_writes_none_of_them():
    """The freeze. Two bodies touching in a room with a fixture nobody
    touched: no cover on any station, no containment record, and every
    contact endpoint still a subject the scene positions -- the three new
    paths are silent on a beat that does not reach for them.
    """
    import copy

    from world.spatial import contacts_of, merge_scene_with_diff

    scene = _caravanserai({"Rasa Oren": "common_room", "Yusra": "common_room"})
    before = copy.deepcopy(scene)
    after = merge_scene_with_diff(scene, {
        "stations": {"Rasa Oren": {"at": "counter", "near": ["Yusra"]}},
        "contact_ops": [_touch("Yusra", part="hand", manner="rest")],
    })
    assert all("cover" not in st for st in after["stations"].values())
    assert after.get("contained") == before.get("contained") == {}
    for contact in contacts_of(after, "Rasa Oren"):
        assert contact["actor"] in after["positions"]
        assert contact["target"] in after["positions"]

# DECIBELS, AND HOW FAR A VERY LOUD SOUND GOES
# (`docs/design/DESIGN_SOUND_DECIBELS.md`, 2026-09-05)
#
# Three classes, each stated as a rule and none as a case:
#
#   * a wall attenuates and does not abolish -- a sound loud enough crosses
#     one and a voice never does, at any volume;
#   * a sound that HAPPENS is heard where it happened and is over when the
#     beat is (`docs/UNBUILT.md` § 1.117);
#   * a distant sound delivers a direction and a character and never a
#     sentence, and there is no configuration in which it delivers one.
# ---------------------------------------------------------------------------

def _two_room_house(barrier, *, size="medium"):
    """Two rooms joined by one edge, no anchor geometry anywhere -- so what
    answers is the far field and nothing else."""
    return {
        "rooms": {
            "hall": {"name": "the hall", "size": size, "exposure": "enclosed",
                     "adjacent": [{"to": "cellar", "barrier": barrier,
                                   "dir": "s"}], "anchors": {}},
            "cellar": {"name": "the cellar", "size": size,
                       "exposure": "enclosed", "adjacent": [], "anchors": {}},
        },
        "positions": {}, "stations": {}, "orientation": {}, "poses": {},
        "entities": {}, "contained": {},
    }


def test_a_wall_attenuates_and_does_not_abolish():
    """THE CLASS: a barrier is a loss, not a switch. `APERTURE_PASS["wall"]`
    was 0 because the table was borrowed from sight, where a wall really is
    a switch -- so no explosion, ever, was heard through one by anybody, and
    no constant could have changed that because the room beyond a wall was
    not placed at all.

    Stated as the two sentences it has to satisfy at once, which is what
    makes a wall a wall: a sound loud enough crosses it, and a voice never
    does however hard it is thrown."""
    from world.spatial import (distant_sounds, SOUND_LEVELS, SPEECH_DB,
                               far_field_sources)
    sc = _two_room_house("wall")
    crash = [{"kind": "sound", "source_room": "hall",
              "level": "catastrophic", "detail": "a shattering roar"}]
    sc["positions"] = {"Ada": "cellar"}
    assert distant_sounds(sc, "Ada", events=crash), (
        "a catastrophic event did not cross one wall")
    # Every quieter rung dies against it, and the LADDER is what decides --
    # not the room, not the story, not a special case. RESOLVED 2026-09-05:
    # at the wall's old 45 dB only the top rung crossed, and the note's own
    # sentence ("a catastrophic event is a fragment two rooms away") was
    # true through doorways and false through walls. 45 turned out to be the
    # real-world number standing in a table whose other seven entries are on
    # a scale compressed by 0.358, so a wall is 16 here and BOTH top rungs
    # cross one, which is what the note always said.
    # WHICH RUNGS CROSS MOVED 2026-09-06, when the impact ladder was untied
    # from the voice ladder on the owner's ruling: an IMPACT is not measured
    # against conversation, so `loud` is 72 dB rather than 56 and `deafening`
    # 80 rather than 61.8. A hammer on steel through one wall of a concrete
    # building is heard, and now it is. What the rung decides is unchanged
    # and is still the whole point: the LADDER decides, not the room, not the
    # story, not a special case.
    for level in SOUND_LEVELS:
        quieter = [{**crash[0], "level": level}]
        crossed = bool(distant_sounds(sc, "Ada", events=quieter))
        assert crossed == (
            level in ("loud", "deafening", "thunderous", "catastrophic")), level
    # And the quiet end still dies against a wall, which is the other half of
    # "attenuates and does not abolish".
    for level in ("faint", "audible"):
        assert not distant_sounds(
            sc, "Ada", events=[{**crash[0], "level": level}]), level
    # And no voice, at any volume: the far field has no door for speech.
    sc["positions"]["Bel"] = "hall"
    for volume in SPEECH_DB:
        assert far_field_sources(sc) == [], volume
    # An open door in the same wall's place carries everything the wall
    # stopped, which is what says the wall was the reason.
    through = _two_room_house("open_door")
    through["positions"] = {"Ada": "cellar"}
    for level in ("thunderous", "catastrophic"):
        assert distant_sounds(through, "Ada",
                              events=[{**crash[0], "level": level}]), level


def test_a_sound_that_happens_is_over_when_the_beat_is(temp_db):
    """§ 1.117'S GAP, AND THE SHAPE OF ITS CLOSE. `sound_source` +
    `state.running` is a STANDING emission and outlives every beat that says
    nothing about it -- which is how a fog bell pulled once on turn 11
    rewrote nine beats of one story with a noise floor of 20.5 against a
    whisper's 0.34. There was no other channel, so a one-off sound was
    either that or nothing.

    The rule this pins is not "expire noises after N beats", which would be
    guessing what kind of thing a noise is. It is that THE BEAT NUMBER IS
    THE LIFETIME: the record carries the beat that wrote it, and every
    reader asks for a beat.
    """
    import time as _time
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist import commit
    from world.spatial import beat_sensory_events, SENSORY_EVENTS_KEY

    def commit_beat(sc, beat, diff):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("House", "", _time.time()))
        temp_db.wset(chat_id, "scene", sc)
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="House", persona_id=None,
                          lorebook_id=None, scenario="", created=_time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=beat, player_input="",
                          created=_time.time()),
            cast=[], input="")
        ctx.director_resolve = {"state_diff": dict(diff)}
        return commit.prepare_scene_commit(ctx)["scene"], ctx

    sc = _two_room_house("open_door")
    event = {"kind": "sound", "room": "hall", "level": "thunderous",
             "source": "the roof", "detail": "a long splintering crack"}
    merged, ctx = commit_beat(sc, 11, {"sensory_events": [event]})
    stored = merged[SENSORY_EVENTS_KEY]
    assert stored["beat"] == 11
    assert beat_sensory_events(merged, 11) == [event]
    # ... and it is not this beat's noise on any other beat, ever.
    assert beat_sensory_events(merged, 12) == []
    # A beat that says nothing about it does not inherit it: a beat with no
    # noise in it is a beat with no noise in it, which is the whole
    # difference from `state.running` and the reason the bell was a defect.
    quiet, _ctx = commit_beat(merged, 12, {})
    assert SENSORY_EVENTS_KEY not in quiet
    # A noise nowhere is not an event this engine holds, and the hand that
    # wrote it is told so rather than having it silently dropped.
    _lost, ctx = commit_beat(sc, 13,
                             {"sensory_events": [{"level": "loud"}]})
    assert any("A sound happens somewhere" in w for w in ctx.warnings)


def test_a_distant_sound_gives_a_direction_and_never_a_place_or_a_line():
    """THE FIREWALL FLOOR OF THE FAR FIELD, and it is a floor and not a
    clause: a mind may receive a distant sound it had a channel to and
    nothing more. A bearing is a DIRECTION, and the difference from a
    location is the whole of what the far field may say -- the record names
    the observer's own room's edge, which the payload already carried, and
    carries no room id, no room name, no speaker and no words."""
    from world.spatial import distant_sounds, sound_bearing_via
    sc = _two_room_house("open_door")
    sc["rooms"]["cellar"]["adjacent"] = [
        {"to": "vault", "barrier": "open_door", "dir": "s"}]
    sc["rooms"]["vault"] = {"name": "the sealed vault", "size": "small",
                            "exposure": "enclosed", "adjacent": [],
                            "anchors": {}}
    sc["positions"] = {"Ada": "hall"}
    events = [{"kind": "sound", "source_room": "vault",
               "level": "catastrophic", "source": "the vault door",
               "detail": "a deep grinding boom"}]
    heard = distant_sounds(sc, "Ada", events=events)
    assert heard and heard[0]["character"] == "a deep grinding boom"
    bearing = heard[0]["bearing"]
    assert bearing and bearing["phrase"]
    # Not one room the listener has never been in is named anywhere: not in
    # the record, not in the bearing, not in the room the sound came THROUGH
    # -- which the flood knows and which never leaves the function.
    blob = json.dumps(heard, sort_keys=True)
    for unseen in ("vault", "the sealed vault", "cellar", "the cellar",
                   "the vault door"):
        assert unseen not in blob, (unseen, blob)
    # What it DOES carry is the edge of the observer's own room, which they
    # can see, and the character of the sound, which they can hear.
    assert bearing["scope"] == "beyond" and bearing["barrier"] == "open_door"
    assert sound_bearing_via(sc, "Ada", "hall", room="hall") is None
