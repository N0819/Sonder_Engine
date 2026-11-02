"""How long the player has been quiet is counted over the beats THIS mind saw.

`decision.quiet_for_beats` counted consecutive `director_interpret` beats on
which the player communicated nothing -- every beat of the story, whether or
not this mind was there -- and was handed over whenever the player is in
view now. A mind that walked in this beat was told the player had been
silent for six beats it never witnessed (review 2026-11-01,
agents_character_background F7). The count now stops at the first earlier
beat on which this mind's own act-stage view did not place the player
(`perception_act.company`, the bodies its view was composed about).
"""

from __future__ import annotations

import json
import time

from agents.character import _player_quiet_beats


def _seed(temp_db, beats):
    """beats: [(idx, player_spoke, {char_id: [names its view placed]})]"""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("Q", "", 0.0))
    for idx, spoke, company in beats:
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, idx, "", time.time()))
        interp = {"speech": "Hello." if spoke else "",
                  "sequence": ([{"type": "speech", "text": "Hello."}] if spoke else [])}
        act = {"views": {}, "company": {
            str(cid): [{"name": n, "label": n} for n in names]
            for cid, names in company.items()}}
        for key, content in (("director_interpret", interp), ("perception_act", act)):
            sid = temp_db.qi(
                "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                (tid, key, key, 0))
            temp_db.qi(
                "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                (sid, json.dumps(content), time.time()))
    return chat_id


def test_beats_this_mind_did_not_witness_are_not_its_silence(temp_db):
    # Mara (7) was elsewhere for beats 1-5 and saw the player only from 6 on.
    chat_id = _seed(temp_db, [(i, False, {7: []}) for i in range(1, 6)]
                    + [(6, False, {7: ["Tamsin"]})])
    assert _player_quiet_beats(chat_id, 7, None, char_id=7, player="Tamsin") == 2
    # The mind that watched all six beats is told all of them.
    chat_id = _seed(temp_db, [(i, False, {8: ["Tamsin"]}) for i in range(1, 7)])
    assert _player_quiet_beats(chat_id, 7, None, char_id=8, player="Tamsin") == 7


def test_speech_still_ends_the_run(temp_db):
    chat_id = _seed(temp_db, [(4, False, {7: ["Tamsin"]}), (5, True, {7: ["Tamsin"]}),
                              (6, False, {7: ["Tamsin"]})])
    assert _player_quiet_beats(chat_id, 7, None, char_id=7, player="Tamsin") == 2


def test_without_a_mind_the_count_is_the_beats_as_before(temp_db):
    chat_id = _seed(temp_db, [(i, False, {7: []}) for i in range(1, 7)])
    assert _player_quiet_beats(chat_id, 7, None) == 7
