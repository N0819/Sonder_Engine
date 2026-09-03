"""Within-room geometry and occlusion (`world/spatial_fov.py`), rendered as
text through the composer, read by the Director as a sight digest.

The contract under test is the fail-open one: THE LAYER MAY ONLY SUBTRACT
ON EVIDENCE IT HAS. A room with no geometry composes byte-identically to
before; a body with no station is never behind anything; an observer with
no facing sees the whole room. And where it does subtract, it subtracts
everywhere at once -- presence, appearance, observations, the episode --
because the decision is folded into `visual_level_between`, the one function
every sight decision goes through.
"""

from __future__ import annotations

import json
import re
import time

import pytest

from agents import composer
from world.spatial import (
    anchor_cells, body_cell, body_visibility, feature_visibility,
    room_has_geometry, shadowcast, sight_digest, visual_level_between,
)


# ---------------------------------------------------------------------------
# Fixtures: one taproom, drawn by hand
# ---------------------------------------------------------------------------

def taproom(*, geometry=True):
    """A large room. A waist-high bar runs along the north wall one pace off
    it; a head-high folding screen runs along the east wall one pace off
    it; a hearth on the south wall; the door on the west wall."""
    bar = {"desc": "the long bar", "dir": "n"}
    screen = {"desc": "a folding screen", "dir": "e"}
    if geometry:
        bar.update({"footprint": "run", "height": "waist"})
        screen.update({"footprint": "run", "height": "head"})
    return {
        "tap": {"name": "the Taproom", "size": "large",
                "notes": "Sawdust on the boards.",
                "anchors": {"bar": bar, "screen": screen,
                            "hearth": {"desc": "the hearth", "dir": "s"},
                            "door": {"desc": "the front door", "dir": "w"}}},
    }


def scene(positions, stations=None, orientation=None, poses=None, *,
          rooms=None):
    return {"rooms": rooms if rooms is not None else taproom(),
            "positions": dict(positions), "stations": dict(stations or {}),
            "orientation": dict(orientation or {}),
            "poses": dict(poses or {}), "entities": {}}


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def test_placement_is_keyed_on_room_and_anchor_alone():
    """Adding an anchor never moves an earlier one, and two constructions of
    the same room agree cell for cell."""
    sc = scene({"P": "tap"})
    before = {aid: rec["cells"] for aid, rec in anchor_cells(sc, "tap").items()}
    sc["rooms"]["tap"]["anchors"]["keg"] = {"desc": "a keg", "dir": "e",
                                            "height": "waist"}
    after = anchor_cells(sc, "tap")
    for aid, cells in before.items():
        assert after[aid]["cells"] == cells, aid
    assert "keg" in after
    again = {aid: rec["cells"] for aid, rec in anchor_cells(sc, "tap").items()}
    assert again == {aid: rec["cells"] for aid, rec in after.items()}


def test_a_wall_run_stands_one_pace_off_its_wall_and_a_door_is_the_wall():
    cells = anchor_cells(scene({"P": "tap"}), "tap")
    assert all(y == 1 for _x, y in cells["bar"]["cells"])       # north, inset
    assert all(x == 6 for x, _y in cells["screen"]["cells"])    # east, inset
    assert all(x == 0 for x, _y in cells["door"]["cells"])      # west wall
    assert all(y == 7 for _x, y in cells["hearth"]["cells"])    # south wall
    assert len(cells["bar"]["cells"]) >= 2


def test_a_body_cell_is_derived_from_its_station_and_never_stored():
    sc = scene({"P": "tap", "Barkeep": "tap"},
               {"P": {"at": "door"}, "Barkeep": {"at": "bar", "cover": True}})
    assert body_cell(sc, "P") is not None
    keeper = body_cell(sc, "Barkeep")
    assert keeper is not None and keeper[1] == 0     # the lane behind the bar
    assert body_cell(sc, "Nobody") is None
    assert "cells" not in json.dumps(sc)              # nothing written back


def test_a_body_at_an_anchor_never_stands_inside_it():
    sc = scene({"H": "tap"}, {"H": {"at": "screen", "cover": "screen"}})
    assert body_cell(sc, "H") not in anchor_cells(sc, "tap")["screen"]["cells"]


# ---------------------------------------------------------------------------
# Shadowcasting on hand-drawn shapes
# ---------------------------------------------------------------------------

def _cast(walls, origin, side=8):
    def blocked(x, y):
        return not (0 <= x < side and 0 <= y < side) or (x, y) in walls
    return shadowcast(origin, side + 1, blocked)


def test_shadowcast_open_room_sees_every_cell():
    seen = _cast(set(), (3, 3))
    assert seen >= {(x, y) for x in range(8) for y in range(8)}


def test_shadowcast_a_counter_shadows_what_is_behind_it():
    counter = {(x, 3) for x in range(2, 6)}
    seen = _cast(counter, (3, 6))
    assert (3, 3) in seen                 # the counter itself is seen
    assert (3, 1) not in seen             # straight behind it is not
    assert (0, 1) in seen                 # round the end of it is


def test_shadowcast_a_corner_hides_the_room_beyond_it():
    corner = {(4, y) for y in range(0, 5)} | {(x, 4) for x in range(4, 8)}
    seen = _cast(corner, (1, 1))
    assert (6, 6) not in seen
    assert (6, 1) not in seen
    assert (1, 6) in seen


def test_shadowcast_a_screen_has_two_sides():
    screen = {(4, 2), (4, 3), (4, 4)}
    assert (6, 3) not in _cast(screen, (2, 3))
    assert (2, 3) not in _cast(screen, (6, 3))


# ---------------------------------------------------------------------------
# Eye height
# ---------------------------------------------------------------------------

def _behind_bar(posture=None):
    poses = {"Keeper": {"posture": posture}} if posture else {}
    return scene({"P": "tap", "Keeper": "tap"},
                 {"P": {"at": "hearth"}, "Keeper": {"at": "bar", "cover": True}},
                 {"P": {"facing": "n"}}, poses)


def test_a_standing_body_behind_a_waist_high_counter_shows_from_the_waist_up():
    rec = body_visibility(_behind_bar(), "P", "Keeper")
    assert rec["visible"] and rec["basis"] == "line"
    assert rec["hidden_below"] == "waist"
    assert rec["occluded_by"] == "the long bar"


@pytest.mark.parametrize("posture", ["crouching", "prone", "lying"])
def test_a_low_body_behind_a_waist_high_counter_is_hidden(posture):
    rec = body_visibility(_behind_bar(posture), "P", "Keeper")
    assert not rec["visible"] and rec["basis"] == "line"
    assert rec["occluded_by"] == "the long bar"
    assert visual_level_between(_behind_bar(posture), "P", "Keeper") == "none"


def test_a_crouching_observer_cannot_see_over_the_counter_either():
    sc = _behind_bar()
    sc["poses"]["P"] = {"posture": "crouched low"}
    assert not body_visibility(sc, "P", "Keeper")["visible"]


def test_a_head_high_screen_hides_a_standing_body():
    sc = scene({"P": "tap", "H": "tap"},
               {"P": {"at": "door"}, "H": {"at": "screen", "cover": "screen"}},
               {"P": {"facing": "e"}})
    rec = body_visibility(sc, "P", "H")
    assert not rec["visible"] and rec["occluded_by"] == "a folding screen"


def test_a_see_through_screen_hides_nothing():
    sc = scene({"P": "tap", "H": "tap"},
               {"P": {"at": "door"}, "H": {"at": "screen", "cover": "screen"}})
    sc["rooms"]["tap"]["anchors"]["screen"]["opacity"] = "see_through"
    assert body_visibility(sc, "P", "H")["visible"]


# ---------------------------------------------------------------------------
# Doorway casting
# ---------------------------------------------------------------------------

def two_rooms(barrier="open_door", screen=False):
    rooms = {
        "hall": {"name": "the Hall", "size": "medium",
                 "adjacent": [{"to": "yard", "barrier": barrier, "dir": "e"}],
                 "anchors": {"table": {"desc": "a trestle table", "dir": "w",
                                       "height": "waist"}}},
        "yard": {"name": "the Yard", "size": "medium",
                 "adjacent": [{"to": "hall", "barrier": barrier, "dir": "w"}],
                 "anchors": {"well": {"desc": "the well", "dir": "e",
                                      "height": "waist"}}},
    }
    if screen:
        rooms["yard"]["anchors"]["cart"] = {
            "desc": "a cart", "dir": "w", "footprint": "run", "height": "full"}
    return rooms


def test_an_open_doorway_casts_into_the_next_room():
    sc = scene({"P": "hall", "Q": "yard"},
               {"P": {"at": "door:yard"}, "Q": {"at": "door:hall"}},
               rooms=two_rooms())
    rec = body_visibility(sc, "P", "Q")
    assert rec["visible"] and rec["through"] == "yard"


def test_what_stands_inside_the_doorway_blocks_the_cast():
    sc = scene({"P": "hall", "Q": "yard"},
               {"P": {"at": "door:yard"}, "Q": {"at": "well"}},
               rooms=two_rooms(screen=True))
    rec = body_visibility(sc, "P", "Q")
    assert not rec["visible"] and rec["occluded_by"] == "a cart"


def test_a_shut_door_casts_nothing_and_answers_open():
    sc = scene({"P": "hall", "Q": "yard"},
               {"P": {"at": "door:yard"}, "Q": {"at": "well"}},
               rooms=two_rooms(barrier="closed_door", screen=True))
    # Sight through a shut door is the barrier's business, not this layer's;
    # it must not claim a line it never cast.
    assert body_visibility(sc, "P", "Q")["basis"] == "open"


# ---------------------------------------------------------------------------
# Fail-open: subtract only on evidence
# ---------------------------------------------------------------------------

def test_no_station_on_either_side_is_never_behind_anything():
    sc = scene({"P": "tap", "H": "tap"}, {"H": {"at": "screen", "cover": True}})
    rec = body_visibility(sc, "P", "H")
    assert rec["visible"] and rec["basis"] == "open"
    assert visual_level_between(sc, "P", "H") == "full"


def test_no_facing_sees_the_whole_room():
    sc = scene({"P": "tap"}, {"P": {"at": "door"}})
    rows = feature_visibility(sc, "P")
    assert rows and all(r["visible"] for r in rows if r["anchor"] != "hearth")
    assert all(r["basis"] in ("open", "line") for r in rows)


def test_a_facing_puts_what_is_behind_out_of_view_and_a_sweep_turns_round():
    sc = scene({"P": "tap"}, {"P": {"at": "hearth"}}, {"P": {"facing": "n"}})
    by_id = {r["anchor"]: r for r in feature_visibility(sc, "P")}
    # Facing north from the hearth on the south wall: the bar lies ahead --
    # and nothing behind but the hearth itself, which is within reach and
    # so never subtracted.
    assert by_id["bar"]["visible"] and by_id["bar"]["basis"] == "open"
    assert by_id["hearth"]["visible"]
    sc2 = scene({"P": "tap"}, {"P": {"at": "hearth"}}, {"P": {"facing": "s"}})
    by_id = {r["anchor"]: r for r in feature_visibility(sc2, "P")}
    assert not by_id["bar"]["visible"] and by_id["bar"]["basis"] == "cone"
    swept = {r["anchor"]: r for r in feature_visibility(sc2, "P", sweep=True)}
    assert swept["bar"]["visible"]


def test_a_room_without_geometry_composes_byte_identically():
    """The environment percept of a room nobody authored geometry on carries
    no features and keys exactly as it always did; a presence percept in it
    carries no cover fields and keys exactly as it always did."""
    rooms = taproom(geometry=False)
    assert not room_has_geometry({"rooms": rooms}, "tap")
    env = composer.environment_percept("tap", "the Taproom", "Sawdust.", "lit")
    assert "features" not in env.data
    assert env.dedupe_key == composer.standing_key(
        "env", ("tap",), ("the Taproom", "Sawdust.", "lit"))
    sc = scene({"P": "tap", "Keeper": "tap"},
               {"P": {"at": "hearth"}, "Keeper": {"at": "bar", "cover": True}},
               {"P": {"facing": "n"}}, rooms=rooms)
    display = {"Keeper": "Keeper"}
    [p] = composer.presence_percepts(sc, "P", [{"name": "Keeper"}], display)
    assert "behind" not in p.data and "shows" not in p.data
    assert p.dedupe_key == composer.standing_key(
        "presence", (composer.body_key("Keeper"),),
        (p.data["tier"], p.data["arc"], p.data["sight"], ""))
    assert composer._presence_clause(p) == "Keeper is across the room"


def test_a_degradation_is_a_failing_test():
    """A room with geometry, a facing and stations, and NOTHING between two
    standing bodies: the layer has evidence and still subtracts nothing."""
    sc = scene({"P": "tap", "Q": "tap"},
               {"P": {"at": "door"}, "Q": {"at": "hearth"}},
               {"P": {"facing": "s"}})
    rec = body_visibility(sc, "P", "Q")
    assert rec["visible"] and rec["basis"] == "line"
    assert rec["occluded_by"] is None and rec["hidden_below"] is None
    assert visual_level_between(sc, "P", "Q") == "full"


# ---------------------------------------------------------------------------
# The firewall: a hidden body is absent from every representation at once
# ---------------------------------------------------------------------------

def _hidden_pair():
    return scene({"P": "tap", "H": "tap"},
                 {"P": {"at": "door"}, "H": {"at": "screen", "cover": "screen"}},
                 {"P": {"facing": "e"}, "H": {"facing": "w"}})


def test_an_occluded_body_is_absent_from_view_observations_and_episode():
    sc = _hidden_pair()
    others = [{"name": "H", "appearance": "a tall man in a red coat"}]
    display = composer.observer_display_map(sc, "P", others, {"P": ["H"]})
    percepts = [composer.environment_percept("tap", "the Taproom", "", "lit")]
    percepts += composer.presence_percepts(sc, "P", others, display)
    percepts += composer.pose_percepts(sc, "P", others, display)
    assert not [p for p in percepts if p.kind in ("presence", "pose")]
    rendered = composer.render_view(percepts, mode="character")
    assert "H" not in rendered.text.split() and "red coat" not in rendered.text
    atoms = composer.observations_from_render("player", rendered)
    assert not [a for a in atoms if "red coat" in a["observed"]["text"]]
    content, _gist, _entities = composer.render_episode(percepts)
    assert "red coat" not in content
    # And symmetrically: the screen has two sides.
    assert visual_level_between(sc, "H", "P") == "none"


def test_the_stage_itself_withholds_the_hidden_body(temp_db):
    """`perception_act` end to end: the player's view of a character crouched
    behind the screen is composed about nobody, and the character's view of
    the player is too."""
    from agents.perception import perception_act
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import default_character_data

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Geometry", "", time.time()))
    sheet = default_character_data("Reya")
    sheet["embodiment"]["visible"]["summary"] = "a wiry courier in a red coat"
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(sheet), "{}", time.time(), "char_reya"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    sc = scene({"The Stranger": "tap", "Reya": "tap"},
               {"The Stranger": {"at": "door"},
                "Reya": {"at": "screen", "cover": "screen"}},
               {"The Stranger": {"facing": "e"}, "Reya": {"facing": "w"}})
    sc.update({"location": "Taproom", "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "scene", sc)
    temp_db.wset(chat_id, "known", {"Reya": ["The Stranger"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "I wait.", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Geometry", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="I wait.", created=time.time()),
        cast=cast, input="I wait.")
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": "waits by the door",
                      "observable": "waits by the door",
                      "visibility": "overt"}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": [char_id], "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}}}
    out = perception_act(ctx, "n0")
    player_view = out["views"].get("player") or ""
    assert "red coat" not in player_view and "Reya" not in player_view
    assert not out["company"].get("player")
    # The screen has two sides: Reya's view is composed about nobody either
    # (her presence ledger is empty), though what she can HEAR of the beat
    # still reaches her -- sound is not this layer's to gate.
    assert not out["company"].get(str(char_id))
    assert "COMPOSER TRIPWIRE" not in " ".join(ctx.warnings)


# ---------------------------------------------------------------------------
# Rendering: a person's words, never the grid's
# ---------------------------------------------------------------------------

_GRID_WORDS = re.compile(
    r"\b(cell|cells|fraction|degree|degrees|sector|grid|ahead_left|"
    r"ahead_right|behind_left|behind_right|\d+(\.\d+)?)\b", re.I)


def test_rendered_text_carries_no_grid_vocabulary():
    sc = scene({"P": "tap", "Keeper": "tap", "Q": "tap"},
               {"P": {"at": "hearth"}, "Keeper": {"at": "bar", "cover": True},
                "Q": {"at": "door"}},
               {"P": {"facing": "n"}})
    others = [{"name": "Keeper", "appearance": "a stout man"},
              {"name": "Q", "appearance": "a girl"}]
    display = {"Keeper": "Keeper", "Q": "Q"}
    rows = feature_visibility(sc, "P")
    features = [{"desc": r["desc"], "tier": r["tier"], "side": r["side"],
                 "peripheral": r["peripheral"]}
                for r in rows if r["visible"] and not r["implicit"]]
    percepts = [composer.environment_percept(
        "tap", "the Taproom", "Sawdust on the boards.", "lit",
        features=features)]
    percepts += composer.presence_percepts(sc, "P", others, display)
    text = composer.render_view(percepts, mode="character").text
    assert "You can see" in text
    assert "behind the long bar, from the waist up" in text
    assert not _GRID_WORDS.search(text), text


def test_a_partly_seen_body_reads_as_behind_something():
    sc = _behind_bar()
    [p] = composer.presence_percepts(sc, "P", [{"name": "Keeper"}],
                                     {"Keeper": "Keeper"})
    assert p.data["behind"] == "the long bar" and p.data["shows"] == "waist"
    assert composer._presence_clause(p).endswith(
        "behind the long bar, from the waist up")


def test_turning_changes_the_room_for_the_ledger():
    """The visible set is content: the same room seen from a new facing keys
    as CHANGED, not as the same fact said again."""
    def env(facing):
        sc = scene({"P": "tap"}, {"P": {"at": "door"}}, {"P": {"facing": facing}})
        rows = feature_visibility(sc, "P")
        return composer.environment_percept(
            "tap", "the Taproom", "", "lit",
            features=[{"desc": r["desc"], "tier": r["tier"], "side": r["side"],
                       "peripheral": r["peripheral"]}
                      for r in rows if r["visible"] and not r["implicit"]])
    east, south = env("e"), env("s")
    assert east.dedupe_key != south.dedupe_key
    assert composer._subject_prefix(east.dedupe_key) == \
        composer._subject_prefix(south.dedupe_key)


# ---------------------------------------------------------------------------
# The Director's digest
# ---------------------------------------------------------------------------

def test_sight_digest_names_who_sees_whom_and_what_stands_between():
    sc = scene({"P": "tap", "Keeper": "tap", "H": "tap", "Nobody": "tap"},
               {"P": {"at": "door"}, "Keeper": {"at": "bar", "cover": True},
                "H": {"at": "screen", "cover": "screen"}},
               {"P": {"facing": "e"}})
    digest = sight_digest(sc, ["P", "Keeper", "H", "Nobody"])
    assert "Keeper" in digest["sees"]["P"]
    assert "H" not in digest["sees"]["P"]
    assert {"observer": "P", "subject": "H", "behind": "a folding screen"} \
        in digest["hidden"]
    assert any(c["observer"] == "P" and c["subject"] == "Keeper"
               and c["behind"] == "the long bar" and c["shows"] == "waist up"
               for c in digest["cover"])
    # An unmeasured body is open to everyone, never hidden from anyone.
    assert "Nobody" in digest["sees"]["P"]
    assert not [h for h in digest["hidden"] if "Nobody" in h.values()]


def test_the_director_payload_carries_the_digest_and_the_spatial_hand_reads_it():
    from agents.director import _specialist_payload
    from agents.director import _sightlines_view

    class _Ctx:
        cast = [{"sheet": json.dumps({"identity": {"name": "H"}})}]
        chat = {"id": 1}
    sc = _hidden_pair()
    digest = _sightlines_view(sc, _Ctx(), "P")
    assert digest and digest["hidden"]
    view = {"source": "player_declaration", "player": "P", "cast": [],
            "declared_actions": {}, "dice": [], "declaration": {},
            "manifest": [], "ledger_notes": {}}
    payload = _specialist_payload("spatial", _Ctx(), sc, view,
                                  {"sightlines": digest})
    assert payload["sightlines"] == digest
    body = _specialist_payload("body", _Ctx(), sc, view, {"sightlines": digest})
    assert "sightlines" not in body
