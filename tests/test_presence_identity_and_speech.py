"""One presence per body, and only a person may hold a background speaking turn.

Both properties were violated together in chat 80 ("Sarah Moon" interview):
`background_presences` held SIX entries for THREE things -- each entity
tracked once by display name ("Scranton Reality Anchors", "Guard 1",
"Guard 2") and once by its scene entity id ("cfc004eb2c174286",
"ab1299cb69244904", "eef58c8d667f414f") -- and the id-keyed twin of a
ceiling-mounted suppression device (kind "device") accrued its own dialogue
history and its own separately-minted human blurb ("sallow skin, buzzed
hair"), then interrogated the restrained player twice:

  turn 3: "You're not restrained. You're contained."
  turn 7: "Stand up straight when you talk."

Both lines rendered as "the unfamiliar person" because a raw uid is not a
name the player knows. The identity layer worked; the presence ledger and
the speaking gate did not.
"""

from __future__ import annotations

import json
import time

from story.character_schema import default_character_data
from persist.commit import (
    _fold_duplicate_presences,
    _presence_speech_verdict,
    pick_background_reactors,
    track_background_presences,
)
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _ctx(db, chat_id, turn_idx, director_resolve, player_input=""):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, player_input, time.time()),
    )
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input, director_resolve=director_resolve,
    )


# The chat 80 shape: the same body reachable under an opaque entity id and a
# human display name, positions keyed by the id.
_DEVICE_SCENE = {
    "location": "Site-19", "time": "night",
    "rooms": {"interview_cell": {"name": "Interview Cell", "adjacent": []}},
    "positions": {"cfc004eb2c174286": "interview_cell",
                  "Hinami": "interview_cell"},
    "entities": {
        "cfc004eb2c174286": {
            "name": "Scranton Reality Anchors", "kind": "device",
            "portable": False,
            "description": "Reality-anchoring devices mounted in the "
                           "interview cell ceiling corners.",
        },
    },
    "attire": {}, "overlays": {},
}


def _guard_scene():
    return {
        "location": "Site-19", "time": "night",
        "rooms": {"obs_room": {"name": "Observation Room", "adjacent": []}},
        "positions": {"ab1299cb69244904": "obs_room", "Hinami": "obs_room"},
        "entities": {
            "ab1299cb69244904": {
                "name": "Guard 1", "kind": "person", "portable": False,
                "description": "A Site Security Guard in tactical armor.",
            },
        },
        "attire": {}, "overlays": {},
    }


# ---------------------------------------------------------------------------
# Defect 1: an entity with both a name and an id yields ONE presence
# ---------------------------------------------------------------------------

def test_entity_harvested_by_def_and_position_yields_one_presence(temp_db):
    """The two structured harvests (state_diff.entities keyed by id with a
    display name inside; state_diff.positions keyed by id) must file under
    ONE key. Before the fold, chat 80 turn 0 tracked every body twice: a
    name-keyed record holding the role_hint and an id-keyed record holding
    the station_room, and the halves then diverged for the whole story."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _guard_scene())

    ctx = _ctx(temp_db, chat_id, 1, {
        "resolved_event": "The guard shifts his weight.",
        "dialogue_log": [],
        "state_diff": {
            "entities": {"ab1299cb69244904": {
                "name": "Guard 1", "kind": "person",
                "description": "A Site Security Guard in tactical armor.",
            }},
            "positions": {"ab1299cb69244904": "obs_room"},
        },
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert "Guard 1" in presences
    assert "ab1299cb69244904" not in presences
    # Both harvests contributed to the ONE record: the def's description and
    # the id-keyed position both landed in the same sketch.
    sketch = presences["Guard 1"]["sketch"]
    assert sketch.get("role_hint")
    assert sketch.get("station_room") == "obs_room"


def test_split_ledger_heals_into_one_presence_at_next_commit(temp_db):
    """A story already carrying both halves must not read as two people.
    Chat 80's actual split: the name-keyed anchors record held mention_turns
    [2, 6, 7] and the honest device blurb; the id-keyed twin held
    dialogue_turns [3, 7], a station, and an invented human face. One track
    pass on any later beat folds them, keyed by the display name, with the
    name-keyed record's frozen blurb kept."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _DEVICE_SCENE)
    temp_db.wset(chat_id, "background_presences", {
        "Scranton Reality Anchors": {
            "first_turn": 0, "last_turn": 7,
            "dialogue_turns": [], "mention_turns": [2, 6, 7],
            "sketch": {"role_hint": "Reality-anchoring devices."},
            "blurb": {"manner": "No speech; emits a continuous low hum."},
        },
        "cfc004eb2c174286": {
            "first_turn": 0, "last_turn": 7,
            "dialogue_turns": [3, 7], "mention_turns": [],
            "sketch": {"station_room": "interview_cell"},
            "blurb": {"manner": "Flat, clipped speech."},
        },
    })

    ctx = _ctx(temp_db, chat_id, 8, {
        "resolved_event": "The hum continues.", "dialogue_log": [],
        "state_diff": {},
    })
    track_background_presences(ctx, nonce=0)

    presences = temp_db.wget(chat_id, "background_presences", {})
    assert "cfc004eb2c174286" not in presences
    rec = presences["Scranton Reality Anchors"]
    assert rec["dialogue_turns"] == [3, 7]
    assert rec["mention_turns"] == [2, 6, 7]
    assert rec["sketch"]["station_room"] == "interview_cell"
    assert rec["sketch"]["role_hint"] == "Reality-anchoring devices."
    # Blurbs are frozen: the display-name record's own blurb survives the
    # fold; the twin's invented temperament does not replace it.
    assert rec["blurb"]["manner"] == "No speech; emits a continuous low hum."


def test_gate_reads_split_ledger_as_one_person(temp_db):
    """pick_background_reactors runs BEFORE commit can heal the ledger, so it
    must read through the fold: a split person must cost one pick under one
    spelling (the display name), never two picks for one body."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _guard_scene())
    temp_db.wset(chat_id, "background_presences", {
        "Guard 1": {"first_turn": 0, "last_turn": 5,
                    "dialogue_turns": [2], "mention_turns": [],
                    "sketch": {"role_hint": "A Site Security Guard."}},
        "ab1299cb69244904": {"first_turn": 0, "last_turn": 5,
                             "dialogue_turns": [3], "mention_turns": [],
                             "sketch": {"station_room": "obs_room"}},
    })

    ctx = _ctx(temp_db, chat_id, 6, {})
    picks = pick_background_reactors(
        ctx, {"resolved_event": "Guard 1 shifts.", "dialogue_log": []}, cap=3)
    assert picks == ["Guard 1"]


# ---------------------------------------------------------------------------
# Defect 2: only a person may hold a background speaking turn
# ---------------------------------------------------------------------------

def test_device_is_never_picked_on_ambient_salience(temp_db):
    """The chat 80 defect exactly: a kind "device" entity at its "post" in
    the player's room, with mentions and even accrued (backstop-authored)
    dialogue history, must not be handed a speaking turn. The ledger says
    nothing about what a name denotes; the scene does, and it says this is
    not a person."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _DEVICE_SCENE)
    temp_db.wset(chat_id, "background_presences", {
        "Scranton Reality Anchors": {
            "first_turn": 0, "last_turn": 7,
            "dialogue_turns": [3, 7], "mention_turns": [2, 6],
            "sketch": {"station_room": "interview_cell"},
        },
    })

    ctx = _ctx(temp_db, chat_id, 8, {})
    picks = pick_background_reactors(
        ctx,
        {"resolved_event": "The Scranton Reality Anchors hum overhead.",
         "dialogue_log": []},
        cap=3)
    assert picks == []


def test_director_routing_hands_a_kind_undecided_entity_a_voice(temp_db):
    """The one channel that may give a kind-undecided entity a voice is the
    Director's own explicit judgment: routed_to_background means the Director
    wrote it a line and handed it over, which is a personhood finding this
    stage must honour (the kind string alone cannot separate a suppression
    device from a "dalek war machine" -- both are live kinds)."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _DEVICE_SCENE)
    temp_db.wset(chat_id, "background_presences", {})

    ctx = _ctx(temp_db, chat_id, 8, {})
    picks = pick_background_reactors(
        ctx,
        {"resolved_event": "The anchors crackle.", "dialogue_log": [],
         "routed_to_background": ["Scranton Reality Anchors"]},
        cap=1)
    assert picks == ["Scranton Reality Anchors"]


def test_bodiless_voice_is_never_picked(temp_db):
    """A ubiquitous entity (ship computer, PA) is the Director's own mouth --
    the resolve prompt is explicit that bodiless voices never get a character
    step -- so even direct address must not buy it a background turn."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", {
        "location": "ship", "time": "day",
        "rooms": {"bridge": {"name": "Bridge", "adjacent": []}},
        "positions": {"Hinami": "bridge"},
        "entities": {"ship_computer": {"name": "Computer", "kind": "computer",
                                       "portable": False}},
        "attire": {}, "overlays": {},
    })
    temp_db.wset(chat_id, "background_presences", {
        "Computer": {"first_turn": 0, "last_turn": 4,
                     "dialogue_turns": [1, 2], "mention_turns": [3]},
    })

    ctx = _ctx(temp_db, chat_id, 5, {}, player_input="Computer, report.")
    picks = pick_background_reactors(
        ctx, {"resolved_event": "The bridge is quiet.", "dialogue_log": [],
              "routed_to_background": ["Computer"]},
        cap=3)
    assert picks == []


def test_inert_kind_presence_is_never_picked(temp_db):
    """The chat 75 class stays closed at the gate too: a shed utility sash
    that slipped into the ledger before tracking excluded it got a
    housekeeper persona and three turns of dialogue. Whatever the record
    says, a thing speaks for nobody."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", {
        "location": "hotel", "time": "night",
        "rooms": {"suite": {"name": "Suite", "adjacent": []}},
        "positions": {"utility_sash": "suite", "Hinami": "suite"},
        "entities": {"utility_sash": {"name": "Utility Sash",
                                      "kind": "clothing", "portable": True}},
        "attire": {}, "overlays": {},
    })
    temp_db.wset(chat_id, "background_presences", {
        "Utility Sash": {"first_turn": 0, "last_turn": 4,
                         "dialogue_turns": [2, 3],
                         "sketch": {"station_room": "suite"}},
    })

    ctx = _ctx(temp_db, chat_id, 5, {})
    picks = pick_background_reactors(
        ctx, {"resolved_event": "The sash lies on the bed.",
              "dialogue_log": []},
        cap=3)
    assert picks == []


def test_ordinary_unregistered_person_still_gets_a_turn(temp_db):
    """Background life must keep working: the gate returning [] on most
    turns is correct, and a person-kind presence with history (or none but a
    scene record saying person) still qualifies exactly as before. This is
    the barkeep/night-clerk class the stage exists for."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _guard_scene())
    temp_db.wset(chat_id, "background_presences", {
        "Guard 1": {"first_turn": 0, "last_turn": 5,
                    "dialogue_turns": [2], "mention_turns": []},
    })

    ctx = _ctx(temp_db, chat_id, 6, {})
    picks = pick_background_reactors(
        ctx, {"resolved_event": "The alarm blares.", "dialogue_log": []},
        cap=1)
    assert picks == ["Guard 1"]


def test_presence_with_no_scene_entity_keeps_benefit_of_the_doubt(temp_db):
    """A presence tracked from a dialogue speaker or a bare positions key has
    no entity record to judge -- chat 72's night clerk arrived exactly this
    way -- and its provenance is already person-shaped, so it must keep its
    voice. The verdict must not fail closed on absence of evidence."""
    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", {
        "location": "hotel", "time": "night",
        "rooms": {"lobby": {"name": "Lobby", "adjacent": []}},
        "positions": {"Hinami": "lobby"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    temp_db.wset(chat_id, "background_presences", {
        "Sleepy Hotel Clerk": {"first_turn": 3, "last_turn": 5,
                               "dialogue_turns": [4]},
    })

    ctx = _ctx(temp_db, chat_id, 6, {})
    picks = pick_background_reactors(
        ctx, {"resolved_event": "The bell rings again.", "dialogue_log": []},
        cap=1)
    assert picks == ["Sleepy Hotel Clerk"]


def test_speech_verdict_grades():
    """The verdict's three grades, on the engine's own vocabulary: animate
    kind (whole or word-wise) is a person, ubiquitous or inert is a thing,
    and a kind that decides neither -- "device" -- is undecided rather than
    guessed either way."""
    scene = {
        "entities": {
            "g1": {"name": "Guard 1", "kind": "person", "portable": False},
            "sec": {"name": "Watchman", "kind": "security guard",
                    "portable": False},
            "anchors": {"name": "Scranton Reality Anchors", "kind": "device",
                        "portable": False},
            "pa": {"name": "PA System", "kind": "intercom", "portable": False},
            "chair": {"name": "Interview Chair", "kind": "furniture",
                      "portable": False},
        },
    }
    assert _presence_speech_verdict(scene, "Guard 1") == "person"
    assert _presence_speech_verdict(scene, "g1") == "person"
    assert _presence_speech_verdict(scene, "Watchman") == "person"
    assert _presence_speech_verdict(scene, "Scranton Reality Anchors") == "undecided"
    assert _presence_speech_verdict(scene, "PA System") == "thing"
    assert _presence_speech_verdict(scene, "Interview Chair") == "thing"
    # No entity record: benefit of the doubt.
    assert _presence_speech_verdict(scene, "Sleepy Hotel Clerk") == "person"


# ---------------------------------------------------------------------------
# The dispatched presence owns the line that comes back
# ---------------------------------------------------------------------------

def test_reaction_speaker_is_resolved_to_the_dispatched_presence(temp_db, monkeypatch):
    """Chat 80 turn 7 delivered a line whose dialogue_log_entry.speaker was
    the raw entity id of the thing the beat was about, not the presence the
    stage was dispatched for. The stage resolves rather than trusts: whatever
    speaker the model echoes -- another name, an entity id -- the entry is
    stamped with the gate-picked presence, so a reaction can never be
    delivered under an identity nothing dispatched."""
    import agents.background as background

    chat_id = _make_chat(temp_db)
    temp_db.wset(chat_id, "scene", _guard_scene())
    temp_db.wset(chat_id, "background_presences", {
        "Guard 1": {"first_turn": 0, "last_turn": 5, "dialogue_turns": [2],
                    "mention_turns": []},
    })

    ctx = _ctx(temp_db, chat_id, 6, {
        "resolved_event": "The alarm blares.", "dialogue_log": [],
    })
    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {
        "reacts": True,
        "dialogue_log_entry": {
            "speaker": "ab1299cb69244904",
            "exact_quote": '"Stand down."', "volume": "normal",
            "intended_target": None, "tone": "flat",
        },
        "action": "",
    })

    result = background.background_react(ctx, nonce=0)
    assert result["fired"] is True
    assert result["dialogue_log_entry"]["speaker"] == "Guard 1"


# ---------------------------------------------------------------------------
# The scene-manager roster obeys the same personhood rule
# ---------------------------------------------------------------------------

def test_managed_roster_excludes_non_persons(temp_db):
    """The scene manager voices whoever is on its roster with no per-signal
    gate, so the roster itself must hold only persons. Chat 80's manager
    path blurb-minted the device's id-keyed twin a human face and let it
    speak; a device (undecided) and a fixture (thing) both stay off the
    roster, while a person stays on it."""
    import agents.background as background

    chat_id = _make_chat(temp_db)
    scene = {
        "location": "Site-19", "time": "night",
        "rooms": {"cell": {"name": "Cell", "adjacent": []}},
        "player_room": "cell",
        "positions": {"anchors": "cell", "g1": "cell", "Hinami": "cell"},
        "entities": {
            "anchors": {"name": "Scranton Reality Anchors", "kind": "device",
                        "portable": False},
            "g1": {"name": "Guard 1", "kind": "person", "portable": False},
        },
        "attire": {}, "overlays": {},
    }
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "background_presences", {
        "Scranton Reality Anchors": {"first_turn": 0, "last_turn": 5,
                                     "dialogue_turns": [3],
                                     "sketch": {"station_room": "cell"}},
        "Guard 1": {"first_turn": 0, "last_turn": 5, "dialogue_turns": [2],
                    "sketch": {"station_room": "cell"}},
    })

    ctx = _ctx(temp_db, chat_id, 6, {})
    managed, _room = background.managed_presences(ctx, cap=6)
    names = [n for _, n, _r, _rm in managed]
    assert "Guard 1" in names
    assert "Scranton Reality Anchors" not in names


def test_fold_helper_is_idempotent_on_healed_ledger():
    """The fold runs on every load (gate, stage, manager, commit), so a
    ledger already healed must pass through unchanged."""
    scene = {"entities": {"g1": {"name": "Guard 1", "kind": "person"}}}
    presences = {"Guard 1": {"first_turn": 0, "last_turn": 3,
                             "dialogue_turns": [1]}}
    once = _fold_duplicate_presences(dict(presences), scene)
    twice = _fold_duplicate_presences(json.loads(json.dumps(once)), scene)
    assert once == twice == presences
