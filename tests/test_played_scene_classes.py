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
"""
from __future__ import annotations

import json
import time
import types

import pytest

from agents.director import (
    _guard_approach_is_not_arrival, _reconcile_near_group_positions)
from persist.commit import prune_dangling_exits
from story.plot_packages import OPERATION_FIELDS, _shape_plan_rooms
from story.room_tools import MIND_AUTHORED_ITEMS, MIND_LINE_CHARS, run_tool
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
    rooms = {GALLERY: {"name": "Upper Gallery", "size": "large",
                       "anchors": {"rail": {}, "stair": {}}}}
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
