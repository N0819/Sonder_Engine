"""A background voice remembers what it said, and is not handed its act back.

Found in play on 2026-10-06 (scratch story 165, turns 4581-4582). A house hand
by the inn's fire was handed `recent_interaction: ['said "Search bell's been
pulling all evening..."; lifts his head from the bench near the hearth,
rolling the burned wrist once against his knee as he looks toward the
door.']` and on four reruns running his next act was "rolling the burned
wrist once against his knee" again -- under two card clauses telling him not
to repeat himself. The field exists for the conversation (the Charter captain
who forgot an introduction); the act rode along in the same string and was
copied. Where a body stands and what it holds come from the scene.
"""

from agents.background import _recent_words
from persist.commit import _append_manager_conduct


def test_a_row_written_now_carries_its_words_alone():
    presences = {"Niboold": {"name": "Niboold", "recent": []}}
    br = {"reactions": [{
        "fired": True, "name": "Niboold",
        "dialogue_log_entry": {"exact_quote": "Nobody's said who yet."},
        "action": "rolls the burned wrist once against his knee"}]}
    _append_manager_conduct(br, presences, 4)
    row = presences["Niboold"]["recent"][-1]
    assert "wrist" in row["text"], "the whole beat is still recorded"
    assert row["words"] == 'said "Nobody\'s said who yet."'
    assert _recent_words(row) == row["words"]


def test_an_older_row_gives_its_words_up_to_the_last_quote():
    row = {"turn": 3, "text": 'said "Search bell\'s been pulling all evening."; '
                              'lifts his head, rolling the burned wrist once'}
    assert _recent_words(row) == 'said "Search bell\'s been pulling all evening."'


def test_an_act_with_nothing_said_gives_nothing():
    assert _recent_words({"turn": 3, "text": "wipes the table down"}) == ""
