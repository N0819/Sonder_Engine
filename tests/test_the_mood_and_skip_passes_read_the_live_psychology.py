"""The passes that read a mind's psychology read it as it stands NOW.

The character's own payload shows its EFFECTIVE drive (`effective_drive`: a
rupture-installed `interior.drive_override` over the card's) and its live
belief and association ledgers (`interior.beliefs`, `interior.associations`
-- "the interior copy is the live one: credence moves there, not on the
card"). The decision passes around the same call read the CARD (review
2026-11-01, mind_affect_psychology F7):

* the affect pass appraised every event against "WHAT DRIVES YOU: <old
  essence>" after the drive broke, so the beat's strain accrued against a
  drive the mind no longer holds, and quoted an association the story had
  extinguished (strength 0) as "LEARNED" while never quoting one learned in
  play;
* the skip writer (`skip_memories.card_of`, `_person`) handed the old drive
  to the memory writer and to the recall picker.
"""

from __future__ import annotations

import json
import time

from mind import affect_pass, skip_memories

CARD = {
    "identity": {"name": "Ilse", "uid": "ilse"},
    "psychology": {
        "drive": {"essence": "Keep the ferry running for the village",
                  "expression": "", "taboo": ""},
        "learning": {"associations": [
            {"cue": "a bell at night", "appraisal_bias": "someone has drowned"}]},
        "self_model": {"beliefs": [{"belief": "The river owes me nothing", "confidence": 0.6}]},
    },
}
INTERIOR = {
    "drive_override": {"essence": "Find out who cut the ferry loose",
                       "expression": "asks everyone", "taboo": ""},
    "associations": [
        {"cue": "a bell at night", "appraisal_bias": "someone has drowned", "strength": 0.0},
        {"cue": "wet rope", "appraisal_bias": "sabotage", "strength": 0.4},
    ],
    "beliefs": [{"belief": "Someone in the village wants the ferry gone", "confidence": 0.7}],
}


def test_the_affect_pass_reads_the_drive_the_mind_holds_now():
    text = affect_pass.psychology_text(CARD, INTERIOR)
    assert "WHAT DRIVES YOU: Find out who cut the ferry loose" in text
    assert "Keep the ferry running" not in text


def test_an_extinguished_cue_is_no_longer_learned_and_a_new_one_is():
    text = affect_pass.psychology_text(CARD, INTERIOR)
    assert "wet rope" in text
    assert "a bell at night" not in text


def test_before_the_first_commit_the_card_is_the_only_copy():
    text = affect_pass.psychology_text(CARD, {})
    assert "Keep the ferry running" in text and "a bell at night" in text


def test_the_state_every_mood_question_reads_carries_the_live_drive():
    felt = affect_pass.before_call("Ilse", CARD, {}, {"valence": 0.0, "arousal": 0.5}, 1.0,
                                   interior=INTERIOR)
    assert "WHAT DRIVES YOU: Find out who cut the ferry loose" in felt.state_text


def test_the_skip_writer_and_its_picker_read_the_live_drive():
    who = skip_memories.card_of(CARD, INTERIOR)
    assert who["psychology"]["drive"]["essence"] == "Find out who cut the ferry loose"
    beliefs = [b["belief"] for b in who["psychology"]["self_model"]["beliefs"]]
    assert "Someone in the village wants the ferry gone" in beliefs
    assert skip_memories._person(CARD, INTERIOR)["drive"] == "Find out who cut the ferry loose"


def test_a_skip_pass_hands_its_writer_the_cast_row_s_own_interior(temp_db, monkeypatch):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))
    ilse = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                      ("Ilse", json.dumps(CARD), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,state) VALUES(?,?,?)",
               (chat, ilse, json.dumps({"interior": INTERIOR})))
    seen = {}

    def writer(name, count, payload, language=None):
        seen["who"] = payload["who"]
        return []
    monkeypatch.setattr(skip_memories, "write_episodes", writer)
    monkeypatch.setattr(skip_memories, "memory_packet",
                        lambda *a, **k: ({}, "recent"))
    skip_memories.remember_one(chat, {"id": 1, "idx": 3, "frame_id": None}, 1, "Ilse",
                               {"log": []}, {}, char_id=ilse, count=1, anchor=None,
                               length=None, room_names={}, known={})
    assert seen["who"]["psychology"]["drive"]["essence"] == "Find out who cut the ferry loose"
