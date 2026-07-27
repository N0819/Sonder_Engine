"""A character must react to the beat in front of it, not the one before.

Found in a live 61-turn chat ("The Doctor — Hinami ⎇14 ⎇17 ⎇16 ⎇23 ⎇54"),
where the Doctor kept answering the previous line. On the turn where the
player said "Why are you looking at me like that, you brought me here?", the
Doctor's considered_responses were about asking what she meant by "future is
weird" -- the line from the turn BEFORE -- and its cited observation resolved
to a `memories` row stamped turn_idx 59 on turn 60.

The cause is structural rather than a stale read. `observations_used` asks the
character to cite an `event_id`; the ONLY ids in its payload belong to memory
rows, and `recent_memory_buffer` deliberately excludes the current turn (audit
#10 -- a mind must not see how the turn it is deciding turned out). So the
present beat arrived as an uncitable prose string while the past arrived with
ids attached, and the model reached for what it could cite. Across that chat:
15 citations of a previous turn, 0 of the current one, ever.
"""

from __future__ import annotations

import json
import time

import memory
from character_schema import default_character_data


def _chat_and_char(db, name="Alice"):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )
    return chat_id, char_id


def test_the_present_beat_is_citable(temp_db):
    """Without an id of its own the current beat cannot be cited, and the
    character's evidence can only ever point backwards."""
    ctx = memory.build_character_memory_context(
        chat_id=1, char_id=1, current_turn_idx=5,
        current_view="She says: 'Why are you looking at me like that?'",
        active_state={"mood": "attentive", "goal": "investigate"})

    wm = ctx["working_memory"]
    assert wm["event_id"] == "current"
    assert "Why are you looking at me" in wm["current_perception"]


def test_every_real_event_id_is_older_than_this_turn(temp_db):
    """Documents WHY the sentinel is needed rather than only asserting it: the
    exclusion below is correct and deliberate, so the present beat can never
    acquire a real id before it commits.

    Asserted against a NON-EMPTY bank on purpose. The same assertion over an
    empty bank passes vacuously and would have kept passing through audit F1,
    when `search_memories` had no turn cutoff at all.
    """
    chat_id, char_id = _chat_and_char(temp_db)

    # Turn 5 is the turn being decided; its outcome memory is already
    # committed, which is exactly the state a reroll or a rerun-from-stage
    # replays the onset in. Turn 6 stands in for a later play-order row --
    # a branch or another frame can leave one sitting ahead of this turn.
    memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                      "The door opened and the stranger shot me.", turn_idx=5,
                      gist="shot by the stranger")
    memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                      "A door opens somewhere later.", turn_idx=6,
                      gist="a door opens later")
    # An older memory, so the recall is not empty for a boring reason.
    memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                      "A door opened onto the ward last week.", turn_idx=2,
                      gist="a door opened onto the ward")

    ctx = memory.build_character_memory_context(
        chat_id=chat_id, char_id=char_id, current_turn_idx=5,
        current_view="A door opens.", active_state={})

    episodes = ctx["recent_episodes"] + ctx["recalled_old_memories"]
    assert episodes, "bank must be non-empty or this test is vacuous"
    for episode in episodes:
        assert episode.get("turn_idx") is None or episode["turn_idx"] < 5
    contents = " ".join(str(e.get("content") or "") for e in episodes)
    assert "shot me" not in contents
    assert "somewhere later" not in contents
    assert "onto the ward" in contents


def test_the_prompt_says_which_one_to_cite():
    """The payload change alone is not enough -- the model reached for real
    ids because they looked authoritative, so the rule is stated too."""
    source = open("prompts.py", encoding="utf-8").read()
    assert "its FIRST entry must come from perception.view" in source
    assert 'cited as event_id \\"current\\"' in source
    # The reason, not just the instruction: a rule without its why is the
    # first thing an editor drops.
    assert "answering the previous line instead of the one just" in source
