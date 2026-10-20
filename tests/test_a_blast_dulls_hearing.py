"""AFTER A BLAST, HEARING IS DULLED (DESIGN_SOUND_FIELD.md § 13, wave B1,
2026-10-20).

Real world: an impulse past about 120-140 dB at the ear -- a gunshot close,
an explosion -- leaves a temporary threshold shift: hearing is muffled and
rings, and recovers over minutes to hours (linearly in the logarithm of the
time since: Ward, Glorig & Sklar 1959; a shift under 40 dB is gone within
about sixteen hours). Before this, a body beside an explosion heard the
whisper that followed it as if nothing had happened.

The class:

  1. a listener exposed past `BLAST_DB` carries a shift -- a body state on
     the scene (`dulled_hearing`), written by the commit from what the
     outcome view measured at each ear;
  2. the shift lowers what reaches them: in the room a normal voice
     a few paces off comes in pieces, a raised one whole;
  3. it rings, and the listener knows it (interoception) -- nobody else is
     told;
  4. it recovers with the story clock, and the ringing's fading is said
     once.
"""

from __future__ import annotations

import json
import time

from agents import composer
from agents.composer import render_episode, render_view
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data
from world.spatial import (BLAST_DB, DULLED_RECOVERY_SECONDS, HEARING_KEY,
                           RINGING_DB, blast_shift_db, hear_level,
                           hearing_reason, next_hearing_ledger,
                           recovered_shift_db, sound_field,
                           spatial_rel_between)


# --- 1. the shift, and its recovery (unit) ------------------------------------

def test_a_blast_past_the_threshold_leaves_a_shift():
    assert BLAST_DB == 120.0
    assert blast_shift_db(119.9) == 0.0
    assert blast_shift_db(120.0) == 20.0
    assert blast_shift_db(135.0) == 35.0
    assert blast_shift_db(160.0) == 40.0           # past 40 it is not temporary


def test_the_shift_recovers_with_the_log_of_the_time():
    assert recovered_shift_db(30.0, 60) == 30.0     # whole for two minutes
    hour = recovered_shift_db(30.0, 3600)
    assert 12.0 < hour < 15.0                       # some 45% left after an hour
    assert recovered_shift_db(30.0, 8 * 3600) < 4.0
    assert recovered_shift_db(30.0, DULLED_RECOVERY_SECONDS) == 0.0


def test_the_ledger_ages_lays_on_and_drops():
    ledger = next_hearing_ledger({}, {"Mara": 135.0}, 1000.0)
    assert ledger["Mara"]["shift_db"] == 35.0
    later = next_hearing_ledger(ledger, {}, 1000.0 + 3600)
    assert 14.0 < later["Mara"]["shift_db"] < 18.0
    gone = next_hearing_ledger(later, {}, 1000.0 + DULLED_RECOVERY_SECONDS)
    assert gone == {}
    # A second blast restarts the recovery from the larger shift.
    again = next_hearing_ledger(later, {"Mara": 125.0}, 1000.0 + 3600)
    assert again["Mara"]["shift_db"] == 25.0
    assert again["Mara"]["since_seconds"] == 1000.0 + 3600


# --- 2. the shift lowers what reaches them -----------------------------------

def _room(cells, hearing=None):
    sc = {"rooms": {"hall": {"name": "the hall", "exposure": "enclosed",
                             "extent": {"w": 10, "d": 8}, "anchors": {},
                             "adjacent": []}},
          "positions": {k: "hall" for k in cells},
          "stations": {k: {"cell": list(v)} for k, v in cells.items()},
          "entities": {}, "poses": {}, "orientation": {}, "contained": {}}
    if hearing:
        sc[HEARING_KEY] = hearing
    return sc


def test_a_dulled_ear_takes_a_voice_across_the_room_in_pieces():
    cells = {"A": (1, 1), "C": (8, 6)}
    sc = _room(cells, {"C": {"shift_db": 30.0, "shift0_db": 30.0,
                             "since_seconds": 0.0}})
    rel = spatial_rel_between(sc, "C", "A", sound=sound_field(sc, "C"))
    assert hear_level(rel, "normal", addressed=True) == "fragment"
    assert hear_level(rel, "loud", addressed=True) == "full"
    assert hearing_reason(rel, "normal", addressed=True) == "hearing_dulled"
    # The same room, the same line, an undulled ear: whole.
    clear = _room(cells)
    rel = spatial_rel_between(clear, "C", "A", sound=sound_field(clear, "C"))
    assert hear_level(rel, "normal", addressed=True) == "full"


# --- 3. it rings, and only the listener knows ----------------------------------

def test_a_ringing_ear_is_told_to_its_own_body_in_both_packs():
    ringing = composer.ear_percepts(30.0)
    assert [p.data["ears"] for p in ringing] == ["ringing"]
    assert ringing[0].channel == "interoception"
    en = render_view(ringing, mode="character", language="en").text
    ja = render_view(ringing, mode="character", language="ja").text
    assert en == "Your ears are ringing, and every sound comes to you muffled."
    assert ja == "耳鳴りがして、どの音もくぐもって聞こえる。"
    assert render_episode(ringing, language="en")[0] == \
        "My ears rang, and every sound came to me muffled."
    assert composer.ear_percepts(RINGING_DB - 1.0) == []


def test_the_ringing_fading_is_said_once():
    ringing = composer.ear_percepts(30.0)[0]
    faded = composer.ear_percepts(2.0, {ringing.dedupe_key})
    assert [p.data["ears"] for p in faded] == ["recovered"]
    assert render_view(faded, mode="character", language="en").text == \
        "The ringing in your ears has faded."
    # The next beat its ledger holds the fading, not the ringing: nothing.
    assert composer.ear_percepts(2.0, {faded[0].dedupe_key}) == []


# --- integration: the outcome measures, the commit writes ---------------------

def _ctx(temp_db, *, moon_cell=(2, 1)):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(default_persona_data("Hinami")), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Blast", "", time.time(), persona_id))
    moon_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Dr. Moon", json.dumps(default_character_data("Dr. Moon")), "{}",
         time.time(), "char_dr_moon_%d" % time.time_ns()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, moon_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "the yard", "time": "day",
        "rooms": {"hall": {"name": "the hall", "exposure": "enclosed",
                           "extent": {"w": 20, "d": 8}, "anchors": {},
                           "adjacent": []}},
        "positions": {"Hinami": "hall", "Dr. Moon": "hall"},
        "stations": {"Hinami": {"cell": [1, 1]},
                     "Dr. Moon": {"cell": list(moon_cell)}},
        "entities": {}, "attire": {}, "overlays": {}, "poses": {},
        "orientation": {}, "contained": {}})
    temp_db.wset(chat_id, "known", {"Dr. Moon": ["Hinami"], "Hinami": ["Dr. Moon"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Blast", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {"sequence": [], "flow": {"reactors": [moon_id]}}
    return ctx, chat_id


def _blast(ctx):
    import agents.perception as perception
    ctx.director_resolve = {
        "resolved_event": "The charge goes off beside the door.",
        "dialogue_log": [],
        "state_diff": {"sensory_events": [{
            "kind": "sound", "room": "hall", "source_room": "hall",
            "source": "Hinami", "level": "catastrophic",
            "detail": "an explosion"}]}}
    return perception.perception_outcome(ctx, nonce=0)


def test_the_outcome_measures_the_blast_at_each_ear(temp_db):
    ctx, _chat = _ctx(temp_db, moon_cell=(18, 6))
    out = _blast(ctx)
    exposures = out.get("hearing_exposures") or {}
    assert exposures.get("Hinami", 0) >= BLAST_DB
    # She is told her ears ring, the beat it happens. Dr. Moon, eighteen
    # paces off, is under the threshold (118 dB at his ear): no shift, and
    # his view says nothing of ringing -- of his ears or of hers.
    assert "Your ears are ringing" in out["views"]["player"]
    assert "Dr. Moon" not in exposures
    moon_views = [v for k, v in out["views"].items() if k != "player"]
    assert moon_views and all("ringing" not in (v or "").lower()
                              for v in moon_views)


def test_the_commit_writes_the_shift_and_the_hearing_rule_reads_it(temp_db):
    from persist.commit import _record_dulled_hearing
    ctx, _chat = _ctx(temp_db)
    ctx.perception_outcome = {"hearing_exposures": {"Hinami": 130.0}}
    sc = {}
    _record_dulled_hearing(ctx, sc, 500.0, {"elapsed_seconds": 480.0})
    assert sc[HEARING_KEY]["Hinami"]["shift_db"] == 30.0
    # A quiet beat an hour later ages it; nothing new lays on.
    ctx.perception_outcome = {}
    _record_dulled_hearing(ctx, sc, 500.0 + 3600, {"elapsed_seconds": 500.0})
    assert 12.0 < sc[HEARING_KEY]["Hinami"]["shift_db"] < 15.0
    _record_dulled_hearing(ctx, sc, 500.0 + DULLED_RECOVERY_SECONDS, {})
    assert HEARING_KEY not in sc
