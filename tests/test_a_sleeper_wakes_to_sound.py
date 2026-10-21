"""A SLEEPER WAKES TO SOUND (DESIGN_SOUND_FIELD.md § 13, wave B1, 2026-10-20).

Real world: a sleeper is woken by a sound that is loud or sudden for the
room -- behavioural awakening climbs across about 50-70 dB(A) at the ear --
or by a meaningful one far quieter, their own name above all. A steady
murmur does not wake them. Before this, nothing in the engine woke a sleeper
by sound: the Director's waking floors run only on a beat with no encoded
events, the encoder was asked to judge "a noise reaches them" with no model
of what reaches an ear, and the residue's "a sound, huge and wordless" fired
for a shout anywhere in the beat, another building included.

The class, a test (or more) each:

  1. a sound at the sleeper's ear at `WAKING_DB` that stands out of the
     room wakes them, and nothing quieter does; a steady murmur never does;
  2. their own name in a line whose words would reach them awake wakes
     them; a name breathed beyond reach does not;
  3. what wakes is a sound of THIS beat reaching THEM: a shout in a room
     with no air to theirs wakes nobody and is no longer in their residue;
     a running thing that was already running is slept through, one that
     starts is not;
  4. only sleep is woken by sound -- not a sedated or unconscious body, not
     a sleep the beat itself began;
  5. the woken mind is told what woke them and nothing else (the
     firewall), and the commit ends the sleep: the next beat they are awake.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data
from story.scene import awareness_map
from world.spatial import (WAKING_DB, WAKING_EMERGENCE_DB, started_sources,
                           wakes_sleeper)


# --- unit -----------------------------------------------------------------

def test_the_waking_threshold_is_a_level_and_an_emergence():
    """60 dB(A) at the ear, and ten decibels out of the room's steady noise:
    a raised voice across a quiet room wakes a sleeper, a conversation
    across it does not, and on an engine deck what would wake a bedroom is
    slept through."""
    assert WAKING_DB == 60.0 and WAKING_EMERGENCE_DB == 10.0
    assert wakes_sleeper(64.0, 27.0)            # a raised voice across the room
    assert not wakes_sleeper(54.0, 27.0)        # a normal one across it
    assert wakes_sleeper(60.0, 27.0)            # a normal one at the bedside
    assert not wakes_sleeper(72.0, 68.0)        # a din the sleeper went under in
    assert not wakes_sleeper(None, 27.0)


def test_a_sound_that_starts_is_not_the_room_s_own():
    before = {"entities": {"gen": {"sound_source": "loud", "state": {"running": False}},
                           "fan": {"sound_source": "faint"}}}
    after = {"entities": {"gen": {"sound_source": "loud", "state": {"running": True}},
                          "fan": {"sound_source": "faint"}}}
    assert started_sources(before, after) == {"gen"}
    assert started_sources(after, after) == set()


# --- integration harness ----------------------------------------------------

def _make_ctx(temp_db, *, level="asleep", hinami_cell=(1, 1),
              moon_cell=(6, 4), moon_room="room1", generator=None,
              far_room=False, sleeper="Hinami"):
    sheet = default_persona_data("Hinami")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(sheet), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Night", "", time.time(), persona_id))
    moon_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Dr. Moon", json.dumps(default_character_data("Dr. Moon")), "{}",
         time.time(), "char_dr_moon_%d" % time.time_ns()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, moon_id, "active", "{}"))
    rooms = {"room1": {"name": "the bedroom", "exposure": "enclosed",
                       "extent": {"w": 8, "d": 6}, "anchors": {},
                       "adjacent": []}}
    if far_room:
        # A room with no air to the bedroom: another building, nothing joins
        # them on the room graph.
        rooms["far"] = {"name": "the warehouse", "exposure": "enclosed",
                        "extent": {"w": 8, "d": 6}, "anchors": {},
                        "adjacent": []}
    entities = {}
    if generator:
        entities["gen"] = {"name": "a generator", "kind": "object",
                           "sound_source": "loud",
                           "state": {"running": generator == "running"}}
    scene = {"location": "the house", "time": "night", "rooms": rooms,
             "positions": {"Hinami": "room1", "Dr. Moon": moon_room,
                           **({"gen": "room1"} if generator else {})},
             "stations": {"Hinami": {"cell": list(hinami_cell)},
                          "Dr. Moon": {"cell": list(moon_cell)},
                          **({"gen": {"cell": [2, 1]}} if generator else {})},
             "entities": entities, "attire": {}, "overlays": {},
             "poses": {}, "orientation": {}, "contained": {}}
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "known", {"Dr. Moon": ["Hinami"], "Hinami": ["Dr. Moon"]})
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)",
        ("cond_sleep_hinami", chat_id, sleeper, "awareness", 0.0, None, None,
         json.dumps({"condition_id": "cond_sleep_hinami", "subject_id": sleeper,
                     "kind": "awareness",
                     "state": {"level": level, "cause": "a long night"}}), 1))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Night", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "room1"
    ctx.director_interpret = {"sequence": [], "flow": {"reactors": [moon_id]}}
    return ctx, chat_id


def _line(quote, volume="normal", target="Hinami"):
    return {"speaker": "Dr. Moon", "exact_quote": quote, "volume": volume,
            "intended_target": target}


def _outcome(ctx, lines=(), *, diff=None, events=()):
    import agents.perception as perception
    ctx.director_resolve = {"resolved_event": "Dr. Moon is in the room.",
                            "dialogue_log": list(lines),
                            "state_diff": diff or {}}
    if events:
        ctx.director_resolve["state_diff"]["sensory_events"] = list(events)
    return perception.perception_outcome(ctx, nonce=0)


# --- 1. a sound loud for the room wakes; a murmur does not ------------------

def test_a_shout_across_the_room_wakes_her_and_a_conversation_does_not(temp_db):
    """A shout five paces off is some 76 dB(A) at her ear: it wakes her. A
    normal voice from the same place is about 54 -- under the waking level --
    and she sleeps on, with nothing of it in the residue."""
    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Everyone out, the roof is coming in!",
                               "shout", target=None)])
    view = out["views"]["player"]
    # The waking leads; since round 2 the rest of the beat follows it
    # (tests/test_a_woken_sleeper_perceives_the_rest_of_the_beat.py).
    assert view.startswith("A shout tears through your sleep. You are awake.")
    assert "roof" not in view               # not a word of what woke her
    assert out.get("woken") == {"Hinami": {"by": "shout"}}

    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Let her sleep. We leave at dawn.",
                               target=None)])
    assert out["views"]["player"] == "You are under, below waking."
    assert not out.get("woken")


def test_a_voice_at_the_bedside_wakes_the_sleeper(temp_db):
    """A normal voice a pace off is 60 dB(A) at the ear: the waking level."""
    ctx, _chat = _make_ctx(temp_db, moon_cell=(2, 1))
    out = _outcome(ctx, [_line("The coffee's ready.", target=None)])
    assert out.get("woken") == {"Hinami": {"by": "voice"}}
    assert out["views"]["player"].startswith(
        "A voice reaches down into your sleep and draws you up. You are awake.")
    assert "coffee" not in out["views"]["player"]


# --- 2. their own name ------------------------------------------------------

def test_their_own_name_across_the_room_wakes_them(temp_db):
    """The own-name effect: a normal voice across the room, too quiet to
    wake by level, wakes a sleeper when it says their name -- and a name
    WHISPERED five paces off does not, because the whisper's words do not
    reach her ear."""
    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Hinami, the car is here.")])
    assert out.get("woken") == {"Hinami": {"by": "name"}}
    view = out["views"]["player"]
    assert view.startswith("Someone says your name, and it pulls you up out "
                           "of sleep. You are awake.")
    # The firewall: what woke them, and not one word of the line. Who is in
    # the room reaches them since round 2 -- they are awake now and he is
    # standing there -- but not as the line's speaker.
    assert "car" not in view
    assert "says" not in view.split("You are awake.", 1)[1]

    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Hinami is asleep, let her be.", "whisper",
                               target=None)])
    assert not out.get("woken")
    assert out["views"]["player"] == "You are under, below waking."


# --- 3. this beat, reaching them --------------------------------------------

def test_a_shout_with_no_air_to_the_sleeper_reaches_nothing(temp_db):
    """A shout in a building nothing joins to the bedroom wakes nobody --
    and is no longer in the residue: it was "a sound, huge and wordless,
    reaches down" for a loud line anywhere in the beat."""
    ctx, _chat = _make_ctx(temp_db, moon_room="far", far_room=True)
    out = _outcome(ctx, [_line("WHERE IS EVERYONE?", "shout", target=None)])
    assert not out.get("woken")
    assert out["views"]["player"] == "You are under, below waking."


def test_a_machine_that_was_running_is_slept_through(temp_db):
    """A generator already running when she went under is the room's own
    noise; one that starts beside her this beat is sudden, and wakes her."""
    ctx, _chat = _make_ctx(temp_db, generator="running")
    out = _outcome(ctx)
    assert not out.get("woken")

    ctx, _chat = _make_ctx(temp_db, generator="off")
    out = _outcome(ctx, diff={"entities": {"gen": {"state": {"running": True}}}})
    assert out.get("woken") == {"Hinami": {"by": "noise"}}


# --- 4. only sleep, and only a sleep the beat found ---------------------------

def test_only_a_sleep_the_beat_found_is_woken(temp_db):
    """The same shout that wakes a sleeper does not wake a SEDATED body, and
    does not end a sleep the beat itself began (the diff opens it): the
    shout came before it."""
    ctx, _chat = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Wake up!", "shout")])
    assert out.get("woken") == {"Hinami": {"by": "shout"}}

    ctx, _chat = _make_ctx(temp_db, level="sedated")
    out = _outcome(ctx, [_line("Wake up!", "shout")])
    assert not out.get("woken")
    assert "awake" not in out["views"]["player"].lower()

    ctx, chat_id = _make_ctx(temp_db)
    temp_db.q("UPDATE world_conditions SET active=0 WHERE chat_id=?", (chat_id,))
    diff = {"conditions": {"c_new": [{
        "condition_id": "c_new", "subject_id": "Hinami", "kind": "awareness",
        "state": {"level": "asleep", "cause": "exhausted"}}]}}
    out = _outcome(ctx, [_line("Good night!", "shout", target=None)], diff=diff)
    assert not out.get("woken")


# --- the onset residue: the player's raised voice, where it reaches ----------

def _onset(ctx, quote, volume="shout"):
    import agents.perception as perception
    ctx.director_interpret = {
        "sequence": [{"type": "speech", "text": quote, "volume": volume,
                      "tone": "", "visibility": "overt", "conceal_from": []}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": ctx.director_interpret["flow"]}
    return perception.perception_act(ctx, "n0")


def test_the_player_s_shout_reaches_a_sleeper_only_where_it_reaches(temp_db):
    """At the onset a sleeping reactor's residue said "a sound, huge and
    wordless, reaches down" for any loud line of the player's, wherever he
    lay. In the room with her shout it does; in a building with no air to
    hers it does not."""
    ctx, _chat = _make_ctx(temp_db, sleeper="Dr. Moon")
    out = _onset(ctx, "Fire! Everybody up!")
    moon_view = next(v for k, v in out["views"].items() if k != "player")
    assert "a sound, huge and wordless" in moon_view.lower()

    ctx, _chat = _make_ctx(temp_db, sleeper="Dr. Moon", moon_room="far",
                           far_room=True)
    out = _onset(ctx, "Fire! Everybody up!")
    moon_view = next(v for k, v in out["views"].items() if k != "player")
    assert "huge and wordless" not in moon_view.lower()
    assert "under, below waking" in moon_view.lower()


# --- 5. the commit ends the sleep -------------------------------------------

def test_the_commit_ends_the_sleep_a_sound_broke_and_nothing_else(temp_db):
    from persist.commit import commit_world_entities
    ctx, chat_id = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Everyone out!", "shout", target=None)])
    assert out.get("woken")
    ctx.perception_outcome = out
    commit_world_entities(ctx, "n1")
    row = temp_db.q("SELECT active, payload FROM world_conditions "
                    "WHERE condition_id='cond_sleep_hinami'", one=True)
    assert row["active"] == 0
    assert "woken by a sound" in json.loads(row["payload"])["ended_reason"]
    assert "hinami" not in awareness_map(chat_id)

    # A beat that woke nobody ends nothing.
    ctx, chat_id = _make_ctx(temp_db)
    out = _outcome(ctx, [_line("Let her sleep.", target=None)])
    ctx.perception_outcome = out
    commit_world_entities(ctx, "n1")
    assert awareness_map(chat_id)["hinami"]["level"] == "asleep"
