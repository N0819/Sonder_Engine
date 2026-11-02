"""A question owed is read off the beat in the order it was asked.

`_unanswered_question_note` read an interaction-loop row through its MERGED
per-mind results (`character_results`), where a mind's `sequence` is every
line it said and its `interaction` is its LATEST round's -- so which debt a
mind was told it owed depended on the dict order of the minds and on whether
the asker's last round expected an answer. The same stored row holds the
loop's `rounds`, each with its speaker and its own result, in the order they
happened (`agents/loops.py`), and the note now walks those.

Measured (review 2026-11-01, agents_character_background F9, probe
`snip/debt_probe.py`): Tamamo asks Q1, the Doctor answers, Tamamo asks Q2 --
Tamamo-first merged dict gave no debt at all, Doctor-first gave Q2; and a Q1
followed by a later round addressed to Hinami lost Q1's debt to the
latest-wins `interaction`.
"""

from __future__ import annotations

import json

from agents.character import _unanswered_question_note

Q1 = "What does this hall seem to you, Doctor?"
A1 = "It seems very old to me."
Q2 = "And who do you think built it, Doctor?"
ASK = {"expects_response": True, "addresses": ["The Doctor"]}


def _sp(text):
    return {"type": "speech", "text": text}


def _note(rounds, merged):
    """The note as the Doctor (74) reads beat 9 from beat 10, every line of
    the beat delivered to him."""
    content = {"rounds": rounds, "character_results": merged}
    row = {"idx": 9, "step_key": "interaction_loop", "content": json.dumps(content)}
    view = {"idx": 9, "step_key": "perception_act",
            "content": json.dumps({"views": {"74": " ".join((Q1, A1, Q2))}})}
    cache = {"prior_variants": {("debt", 1, 7, 10, None): [row, view]}}
    return _unanswered_question_note(1, "The Doctor", 74, 10, None, n_turns=3,
                                     rows_cache=cache)


ROUNDS = [
    {"round": 0, "speaker_id": 75,
     "result": {"name": "Tamamo", "sequence": [_sp(Q1)], "interaction": ASK}},
    {"round": 1, "speaker_id": 74,
     "result": {"name": "The Doctor", "sequence": [_sp(A1)]}},
    {"round": 2, "speaker_id": 75,
     "result": {"name": "Tamamo", "sequence": [_sp(Q2)], "interaction": ASK}},
]
TAMAMO = {"name": "Tamamo", "sequence": [_sp(Q1), _sp(Q2)], "interaction": ASK}
DOCTOR = {"name": "The Doctor", "sequence": [_sp(A1)],
          "interaction": {"expects_response": False}}


def test_the_question_asked_after_the_answer_is_owed_whatever_the_dict_order():
    for merged in ({"75": TAMAMO, "74": DOCTOR}, {"74": DOCTOR, "75": TAMAMO}):
        owed = _note(ROUNDS, merged).get("awaiting_your_answer")
        assert owed, "a question asked after he spoke is still his to answer"
        assert owed["asked"] == Q2 and owed["from"] == "Tamamo"


def test_a_later_round_to_someone_else_does_not_cancel_the_question():
    aside = "Hinami, fetch the tea."
    to_hinami = {"expects_response": False, "addresses": ["Hinami"]}
    rounds = [
        {"round": 0, "speaker_id": 75,
         "result": {"name": "Tamamo", "sequence": [_sp(Q1)], "interaction": ASK}},
        {"round": 1, "speaker_id": 75,
         "result": {"name": "Tamamo", "sequence": [_sp(aside)],
                    "interaction": to_hinami}},
    ]
    merged = {"75": {"name": "Tamamo", "sequence": [_sp(Q1), _sp(aside)],
                     "interaction": to_hinami}}
    owed = _note(rounds, merged).get("awaiting_your_answer")
    assert owed and owed["asked"] == Q1


def test_a_row_with_no_rounds_is_still_read_through_its_merged_results():
    """Legacy rows (and the reaction loop's merged map) keep their reading."""
    owed = _note([], {"75": {"name": "Tamamo", "sequence": [_sp(Q1)],
                             "interaction": ASK}}).get("awaiting_your_answer")
    assert owed and owed["asked"] == Q1


def test_answering_in_a_later_round_clears_the_question():
    rounds = ROUNDS[:2]
    merged = {"75": {"name": "Tamamo", "sequence": [_sp(Q1)], "interaction": ASK},
              "74": DOCTOR}
    assert _note(rounds, merged) == {}
