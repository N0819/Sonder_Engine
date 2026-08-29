"""A body the simulation places in a room is composed into that room's views.

`tests/test_background_presence_channels.py` opens "a background presence is a
body in a room, and reaches an observer through the same channels every other
body does" -- and pins the channels an ACT or a LINE travels down. Standing
still was the case nobody wrote: a presence that does not speak this beat
reached no view at all, because `agents/perception.py` builds every observer's
co-present body list out of the cast and the players and nothing else.

That gap has a second half, and together they emptied a room.
`world/charter_crowd.members_of` SUBTRACTS from the derived crowd "every body
presented individually this beat" -- bound bodies and bodies with a live
presence record -- on DESIGN_BACKGROUND_PRESENTATION B2's rule that "a charter
body is ground (in the crowd) exactly when nothing this beat presents it
individually". The subtraction was built; the presentation it subtracts FOR
was not. So a body that earned a presence record left the crowd and entered
nothing, and B2's other clause -- "below the floor of the smallest band,
members present as individual ambient figures" -- had no implementation at
all.

Measured live 2026-08-28, chat 98 (bench.db) turns 10-13: five simulated
crew whose charter `place` was the player's lounge. Before they had records
the room read "a handful lieutenant commanders and ensigns"; the moment
records existed for all five, `crowds_for_room` returned `[]` and every
composed view of that room -- the player's included -- held nobody at all,
while `background_presence_records(cid, places={"ten_forward"})` still
returned all five. The populace did not become wrong at the narrator, or at
the Director, or in the ledger: it became wrong in the view, which is the
only representation any mind reads.

The firewall reading, which is why the fix ADDS rather than relaxes: these
bodies now arrive as `others` for every perceiver and pass through exactly
the subtractions a cast body does -- `visual_level_between` drops the ones
in other rooms, `observer_display_map` hands back a descriptor rather than
a name to anyone who has not met them. Nothing is granted that a channel did
not already carry; what changes is that a person standing in front of you is
in your view.
"""

from __future__ import annotations

import json
import time

from agents.common import chatter_inputs, crowds_for_room
from agents.perception import perception_outcome
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from world.charter_runtime import background_presence_records, save_registry

CELL = "cell"
OBS = "observation"


def _scene():
    return {
        "location": "Site", "time": "night",
        "rooms": {
            CELL: {"name": "Interview Cell", "adjacent": [], "light": "lit"},
            OBS: {"name": "Observation Room", "adjacent": [], "light": "lit"},
        },
        "positions": {"The Stranger": CELL, "Reya": CELL},
        "entities": {},
        "attire": {}, "overlays": {},
    }


def _ctx(temp_db, *, scene=None, presences=None, turn_idx=1):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Standing presence", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(default_character_data("Reya")), "{}",
         time.time(), "char_reya"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", scene if scene is not None else _scene())
    if presences is not None:
        temp_db.wset(chat_id, "background_presences", presences)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Standing presence", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="", created=time.time()),
        cast=cast, input="")
    ctx.director_interpret = {
        "sequence": [], "speech": None, "speech_volume": "normal",
        "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [],
                            "state_diff": {}}
    ctx["background_react"] = {
        "fired": False, "name": None, "reactions": [], "selected": [],
        "mode": "background_react",
    }
    return ctx


def _company(out, pid="player"):
    """Whom this observer's view was composed about, minus the registered
    cast -- who were never the question."""
    return [row.get("name")
            for row in (out.get("company") or {}).get(pid, [])
            if row.get("name") != "Reya"]


# --- a tracked presence, standing still -----------------------------------

def test_a_silent_presence_in_the_room_is_in_the_players_view(temp_db):
    """The measured hole. `background_react` fired nothing, so nothing put
    this body anywhere -- and it was standing next to the player."""
    sc = _scene()
    sc["positions"]["bg0001"] = CELL
    sc["entities"]["bg0001"] = {"name": "Site Guard", "kind": "person"}
    ctx = _ctx(temp_db, scene=sc, presences={
        "Site Guard": {"first_turn": 0, "last_turn": 1, "nature": "person",
                       "dialogue_turns": [], "mention_turns": [],
                       "addressed_turns": [],
                       "sketch": {"station_room": CELL}},
    })
    out = perception_outcome(ctx, "n0")
    assert "Site Guard" in _company(out)
    # The body reached the player; its NAME did not.
    assert "Site Guard" not in (out["views"]["player"] or "")


def test_a_presence_in_another_room_is_not_in_the_players_view(temp_db):
    """The addition passes through the same subtraction every cast body
    does: sight is graded, and an unseen body simply never becomes a
    percept."""
    sc = _scene()
    sc["positions"]["bg0001"] = OBS
    sc["entities"]["bg0001"] = {"name": "Site Guard", "kind": "person"}
    ctx = _ctx(temp_db, scene=sc, presences={
        "Site Guard": {"first_turn": 0, "last_turn": 1, "nature": "person",
                       "dialogue_turns": [], "mention_turns": [],
                       "addressed_turns": [], "sketch": {"station_room": OBS}},
    })
    out = perception_outcome(ctx, "n0")
    assert "Site Guard" not in _company(out)
    assert "Site Guard" not in (out["views"]["player"] or "")


def test_a_device_with_a_record_is_not_a_body_in_the_room(temp_db):
    """`presence_has_an_identity`'s line, borrowed rather than restated: a
    ceiling-mounted suppression fixture with an accrued record is not
    somebody standing there, and rendering one as "the unfamiliar person"
    is the measured chat-82 failure this gate exists to refuse."""
    sc = _scene()
    sc["positions"]["anchor"] = CELL
    sc["entities"]["anchor"] = {"name": "Scranton Reality Anchors",
                                "kind": "device"}
    ctx = _ctx(temp_db, scene=sc, presences={
        "Scranton Reality Anchors": {
            "first_turn": 0, "last_turn": 1, "nature": "thing",
            "dialogue_turns": [], "mention_turns": [], "addressed_turns": [],
            "sketch": {"station_room": CELL}},
    })
    out = perception_outcome(ctx, "n0")
    assert "Scranton Reality Anchors" not in _company(out)


# --- charter bodies, the two sides of the crowd floor ----------------------

def _charter(place_counts):
    """One institution whose bodies stand where the caller says."""
    bodies = {}
    n = 0
    for place, count in place_counts.items():
        for _ in range(count):
            n += 1
            key = "hand:%04d" % n
            bodies[key] = {"key": key, "name": "Hand %d" % n,
                           "place": place, "home_post": "deckhand"}
    return {"key": "guild", "kind": "guild", "bodies": bodies,
            "posts": {"deckhand": {"place": CELL, "serves": []}},
            "watch": {}, "bindings": {}, "figures": {}}


def _with_charter(temp_db, chat_id, place_counts):
    save_registry(chat_id, {"items": {"guild": _charter(place_counts)}})
    return background_presence_records(chat_id, places={CELL})


def test_below_the_crowd_floor_the_bodies_are_individual_figures(temp_db):
    """B2's unimplemented clause: "below the floor of the smallest band,
    members present as individual ambient figures". Two people in a room are
    two people, and `crowd_for` correctly refuses to call them a crowd --
    which until now meant nobody saw them."""
    ctx = _ctx(temp_db)
    derived = _with_charter(temp_db, ctx.chat.id, {CELL: 2})
    assert len(derived) == 2
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    assert crowds_for_room(ctx.chat.id, sc, CELL,
                           chatter_inputs(ctx.chat.id, sc, turn_idx=1)) == []
    seen = _company(perception_outcome(ctx, "n0"))
    assert sorted(seen) == sorted(derived)


def test_at_the_crowd_floor_the_crowd_is_the_presentation(temp_db):
    """The complement, and the reason the addition cannot be unconditional:
    a body the derived crowd carries must NOT also arrive as an individual
    figure, or one institution stands in the room twice."""
    ctx = _ctx(temp_db)
    derived = _with_charter(temp_db, ctx.chat.id, {CELL: 5})
    assert len(derived) == 5
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    assert crowds_for_room(ctx.chat.id, sc, CELL,
                           chatter_inputs(ctx.chat.id, sc, turn_idx=1))
    assert _company(perception_outcome(ctx, "n0")) == []


def test_a_lapsed_record_goes_back_to_the_crowd_and_not_to_both(temp_db):
    """`charter_crowd.presented`'s idle lapse returns a body to the crowd's
    ground without deleting its record. The record is still in the ledger,
    so the addition has to read the same lapse the subtraction does -- or
    one institution stands in the room twice, once as a band and once as
    the people in it."""
    ctx = _ctx(temp_db, turn_idx=40)
    derived = _with_charter(temp_db, ctx.chat.id, {CELL: 5})
    temp_db.wset(ctx.chat.id, "background_presences", {
        "p_%d" % i: {"uid": "p_%d" % i, "name": name, "nature": "person",
                     # Engaged long ago: past PRESENTED_IDLE_BEATS.
                     "first_turn": 1, "last_turn": 1, "dialogue_turns": [1],
                     "mention_turns": [], "addressed_turns": [],
                     "charter_refs": rec["charter_refs"],
                     "sketch": rec["sketch"]}
        for i, (name, rec) in enumerate(sorted(derived.items()))
    })
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    assert crowds_for_room(ctx.chat.id, sc, CELL,
                           chatter_inputs(ctx.chat.id, sc, turn_idx=40))
    assert _company(perception_outcome(ctx, "n0")) == []


def test_a_figure_is_described_by_what_the_crowd_would_have_called_it(temp_db):
    """The band said "deckhands"; the one deckhand standing out of it must
    not read as an unfamiliar person. One noun (`charter_crowd.member_noun`)
    answers both, because a room whose crowd reads one way and whose
    individuals read another is a description of two rooms."""
    ctx = _ctx(temp_db)
    _with_charter(temp_db, ctx.chat.id, {CELL: 1})
    view = perception_outcome(ctx, "n0")["views"]["player"] or ""
    assert "deckhand" in view.casefold()


def test_the_ledger_that_empties_the_crowd_fills_the_view(temp_db):
    """Chat 98's exact state. Every body at the place carries a live
    presence record, so `members_of` subtracts all of them and the room
    holds no crowd -- and before this, no bodies either. The subtraction and
    the presentation are now the same predicate, so the populace is
    conserved across it."""
    ctx = _ctx(temp_db)
    derived = _with_charter(temp_db, ctx.chat.id, {CELL: 5})
    temp_db.wset(ctx.chat.id, "background_presences", {
        "p_%d" % i: {"uid": "p_%d" % i, "name": name, "nature": "person",
                     "first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                     "mention_turns": [], "addressed_turns": [],
                     "charter_refs": rec["charter_refs"],
                     "sketch": rec["sketch"]}
        for i, (name, rec) in enumerate(sorted(derived.items()))
    })
    sc = temp_db.wget(ctx.chat.id, "scene", {})
    assert crowds_for_room(ctx.chat.id, sc, CELL,
                           chatter_inputs(ctx.chat.id, sc, turn_idx=1)) == []
    assert sorted(_company(perception_outcome(ctx, "n0"))) == sorted(derived)
