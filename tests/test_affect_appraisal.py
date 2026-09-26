"""The decision model's appraisal questions (mind/affect_appraisal.py).

Designed with the owner on 2026-09-26: each event a character perceived is
appraised on its own, quoted in every question, and each recalled memory is
asked whether it stirs a feeling now; the answers become numbers and
distributions `mind/affect_mix.py` turns into emotions.

Pinned here: every question quotes its event, person or memory and leaves no
placeholder behind; the answer labels are the pack's; one request carries
them all; answers read into the scales the mix expects; an unanswered
question is left out rather than read as zero; and the Japanese pack carries
every question and option English does.
"""

from __future__ import annotations

import pytest

from llm import decisions
from llm.prompts import _prompt_card
from mind import affect_appraisal as appraisal
from mind import affect_mix as mix

EVENTS = [{"ref": "o1", "text": "says she took the key.", "actor": "Hinami"},
          {"ref": "o2", "text": "The console sparks and goes dark."}]
PEOPLE = [{"name": "Hinami"}]
MEMORIES = [{"ref": "m7", "text": "The TARDIS flinched in the vortex scar."}]


def test_every_event_gets_every_question_and_a_fortune_per_person():
    qs = appraisal.questions_for(EVENTS, PEOPLE, MEMORIES, language="en")
    for ref in ("o1", "o2"):
        for name in appraisal.EVENT_QUESTIONS:
            assert f"ev:{ref}:{name}" in qs
        assert f"ev:{ref}:fortune:0" in qs
    assert {"mem:m7:strength", "mem:m7:tone"} <= set(qs)
    assert len(qs) == 2 * (len(appraisal.EVENT_QUESTIONS) + 1) + 2


def test_each_question_quotes_what_it_judges_and_leaves_no_placeholder():
    qs = appraisal.questions_for(EVENTS, PEOPLE, MEMORIES, language="en")
    assert "Hinami: says she took the key." in qs["ev:o1:desirability"]["instructions"]
    assert "Hinami" in qs["ev:o2:fortune:0"]["instructions"]
    assert "vortex scar" in qs["mem:m7:tone"]["instructions"]
    for q in qs.values():
        assert "{" not in q["instructions"] and q["type"] == "choice"


def test_the_answer_labels_are_the_packs():
    qs = appraisal.questions_for(EVENTS[:1], language="en")
    card = _prompt_card("en")["affect_appraisal"]["options"]
    assert qs["ev:o1:agency"]["criteria"] == card["agency"]
    assert set(qs["ev:o1:desirability"]["criteria"]) == set(appraisal.SCALES["goodness"])


def _answer(**probs):
    return {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs}


def test_answers_read_into_the_scales_the_mix_expects():
    answers = {
        "ev:o1:desirability": _answer(very_bad=0.8, bad=0.2),
        "ev:o1:status": _answer(happened=0.9, might=0.1),
        "ev:o1:agency": _answer(other=0.9, self=0.1),
        "ev:o1:standards": _answer(very_wrong=0.5, wrong=0.5),
        "ev:o1:control": _answer(clear=1.0),
        "ev:o1:fortune:0": _answer(good=1.0),
        "mem:m7:strength": _answer(strong=1.0),
        "mem:m7:tone": _answer(unpleasant=1.0),
    }
    out = appraisal.read(answers, EVENTS[:1], PEOPLE, MEMORIES)
    a = out["events"]["o1"]
    assert a["desirability"] == pytest.approx(-0.9)
    assert a["happened"] == pytest.approx(0.9)
    assert a["agency"]["other"] == pytest.approx(0.9)
    assert a["standards"] == pytest.approx(-0.75)
    assert a["control"] == pytest.approx(2 / 3)
    assert a["fortune"] == {"Hinami": pytest.approx(0.5)}
    assert out["memories"]["m7"] == {"strength": pytest.approx(1.0), "tone": pytest.approx(-0.5)}
    # the mix reads it: harm by another, done wrongly -> anger at her
    emotions = mix.emotions_from_appraisal(a, ref="o1", actor="Hinami")
    assert "anger" in {e.name for e in emotions}


def test_an_unanswered_question_is_left_out_not_read_as_zero():
    out = appraisal.read({"ev:o1:desirability": _answer(good=1.0)}, EVENTS[:1])
    assert out["events"]["o1"] == {"desirability": pytest.approx(0.5)}


def test_one_request_carries_every_question(monkeypatch):
    seen = []

    def jev(state, questions):
        seen.append((state, set(questions)))
        return {key: _answer(**{next(iter(q["criteria"])): 1.0}) for key, q in questions.items()}

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    out = appraisal.appraise("YOU ARE The Doctor.", EVENTS, PEOPLE, MEMORIES, language="en")
    assert len(seen) == 1 and seen[0][0] == "YOU ARE The Doctor."
    assert set(out["events"]) == {"o1", "o2"} and set(out["memories"]) == {"m7"}


def test_nothing_to_ask_asks_nothing(monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda s, q: pytest.fail("asked"))
    assert appraisal.appraise("state") == {"events": {}, "memories": {}}


@pytest.mark.parametrize("language", ["ja"])
def test_every_pack_carries_every_question_and_option(language):
    english = _prompt_card("en")["affect_appraisal"]
    other = _prompt_card(language)["affect_appraisal"]
    assert set(other) == set(english)
    for option_set, labels in english["options"].items():
        assert set(other["options"][option_set]) == set(labels)
    qs = appraisal.questions_for(EVENTS, PEOPLE, MEMORIES, language=language)
    assert all("{" not in q["instructions"] for q in qs.values())
