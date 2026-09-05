"""One line, one proximity floor: the onset pass and the outcome pass must
ask the same question of the same beat.

Live: `docs/experiments/PLAY_2026_09_05C_rush.md` § PR5, "Rush", 2026-09-05.
Turn 1's act view read "You hear Vesna Kolar shout: 'TOMO! ...'" and turn 1's
OUTCOME view, of the same line in the same beat, read "A muffled voice:
...Lisak... nurse... landing...". F61's class, at the proximity gate.

`composer.line_hear_level` states the contract in its own docstring: pass only
a MEASURED tier, because `proximity_rel` returns "near" both as a reading and
as its fallback when nobody wrote stations -- measured live, 6.7% of bodies
carry an anchored station and 8.6% of multi-occupant rooms have two -- and
`hear_level` degrades a same-room mutter to a fragment at "near". Reading the
fallback as evidence of separation deletes authored dialogue wholesale.
`perception_outcome` passed `measured_proximity_rel` and `perception_act`
passed the raw tier, so a quiet line spoken in a room with no station data was
a fragment on the way in and whole on the way out.

The two other halves PR5 names are in files this work did not own and are
written up with it: the addressed rescue returns "full" AFTER the senses gate
has run, so a shout two rooms off arrives whole to a hard-of-hearing listener
in the same view where a sentence into her good ear arrives as three ellipsed
words; and `spatial.sense_adjusted` has no rung above `full` for a -1 offset
to eat, so a dulled ear is total deafness for content at every volume and
every distance.
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

STAIRWELL = "stairwell"
LINE = "Lower him one flight and no further."


def _ctx(temp_db, *, stations=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Rush", "", time.time()))
    sheet = default_character_data("Mirela")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mirela", json.dumps(sheet), "{}", time.time(), "char_mirela"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    scene = {
        "location": "Ulica Rudarska", "time": "night",
        "rooms": {STAIRWELL: {
            "name": "the Second Landing", "light": "lit",
            "size": "large",
            "anchors": {"banister": {"desc": "the banister", "dir": "w"},
                        "flat_door": {"desc": "the door of flat two",
                                      "dir": "e"}},
            "adjacent": []}},
        "positions": {"The Stranger": STAIRWELL, "Mirela": STAIRWELL},
        "entities": {}, "attire": {}, "overlays": {},
    }
    if stations:
        scene["stations"] = stations
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "known", {"Mirela": ["The Stranger", "Mirela"],
                                    "The Stranger": ["The Stranger", "Mirela"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, LINE, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Rush", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input=LINE,
                      created=time.time()),
        cast=cast, input=LINE)
    ctx.director_interpret = {
        "sequence": [{"type": "speech", "text": LINE, "volume": "mutter",
                      "tone": "urgent", "visibility": "overt",
                      "conceal_from": []}],
        "speech": LINE, "speech_volume": "mutter", "action": None,
        "flow": {"reactors": [char_id], "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    ctx.director_resolve = {
        "resolved_event": "She says it under her breath.",
        "dialogue_log": [{"speaker": "The Stranger", "exact_quote": LINE,
                          "volume": "mutter", "tone": "urgent",
                          "intended_target": None, "visibility": "overt",
                          "conceal_from": []}],
        "state_diff": {},
    }
    ctx["background_react"] = {
        "fired": False, "name": None, "reactions": [], "selected": [],
        "mode": "background_react",
    }
    return ctx, char_id


def test_a_quiet_line_is_graded_the_same_on_both_passes(temp_db):
    """PR5. Nobody wrote stations, so "near" is not a measurement and must
    not silence a conversation. Both passes deliver the words."""
    from agents.perception import perception_act, perception_outcome

    ctx, char_id = _ctx(temp_db)
    onset = perception_act(ctx, "n0")["views"][str(char_id)]
    outcome = perception_outcome(ctx, "n1")["views"][str(char_id)]
    assert LINE in onset, onset
    assert LINE in outcome, outcome


def test_a_measured_gap_still_costs_the_words_on_both_passes(temp_db):
    """The complement: where two stations ARE written, "near" is evidence,
    and the fix must not have turned the tier off. A mutter across a
    measured gap is a fragment on both passes, not on one."""
    from agents.perception import perception_act, perception_outcome

    ctx, char_id = _ctx(temp_db, stations={
        "The Stranger": {"at": "banister"}, "Mirela": {"at": "flat_door"}})
    onset = perception_act(ctx, "n0")["views"][str(char_id)]
    outcome = perception_outcome(ctx, "n1")["views"][str(char_id)]
    assert LINE not in onset, onset
    assert LINE not in outcome, outcome


def test_the_onset_pass_asks_for_a_measurement(temp_db, monkeypatch):
    """The gate itself, so the fix cannot be undone by a rename: the tier the
    onset pass hands the composer is None where no station was written.

    Patched on `agents.composer`, which DEFINES `speech_percept` --
    `perception` resolves it as an attribute of that module at call time, so
    this is the module a patch has to reach."""
    import agents.composer as composer
    from agents.perception import perception_act

    ctx, char_id = _ctx(temp_db)
    captured = {}
    original = composer.speech_percept

    def _spy(entry, rel, observer_name, **kw):
        captured[observer_name] = kw.get("proximity")
        return original(entry, rel, observer_name, **kw)

    monkeypatch.setattr(composer, "speech_percept", _spy)
    perception_act(ctx, "n0")
    assert "Mirela" in captured, captured
    assert captured["Mirela"] is None, captured
