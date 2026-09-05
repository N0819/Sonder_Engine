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
    for lang, phrase in (("en", "AN EMISSION IS A STATE"),
                         ("ja", "\u767a\u3059\u308b\u3053\u3068\u306f\u72b6\u614b")):
        text = (root / lang / "cards" / "system_prompts" / "specialists"
                / "objects" / "chunks" / "entities.txt").read_text("utf-8")
        assert phrase in text, lang
        assert "_action" in text, lang


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
                row["room"]))
        return rows

    # Patched on the module that DEFINES it: a patch on the facade's
    # re-export is silently inert (docs/experiments/AUDIT_COMMIT.md).
    monkeypatch.setattr(mapping, "_answering_bodies", _answering)
    kept = mapping._drop_needs_the_beat_answers(
        ctx, [_need("the woman with the keys at her belt", kind="person",
                    room="hall")])
    assert kept == []


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
