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

import memory


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
    acquire a real id before it commits."""
    ctx = memory.build_character_memory_context(
        chat_id=1, char_id=1, current_turn_idx=5,
        current_view="A door opens.", active_state={})

    for episode in ctx["recent_episodes"] + ctx["recalled_old_memories"]:
        assert episode.get("turn_idx") is None or episode["turn_idx"] < 5


def test_the_prompt_says_which_one_to_cite():
    """The payload change alone is not enough -- the model reached for real
    ids because they looked authoritative, so the rule is stated too."""
    source = open("prompts.py", encoding="utf-8").read()
    assert "its FIRST entry must come from perception.view" in source
    assert 'cited as event_id \\"current\\"' in source
    # The reason, not just the instruction: a rule without its why is the
    # first thing an editor drops.
    assert "answering the previous line instead of the one just" in source
