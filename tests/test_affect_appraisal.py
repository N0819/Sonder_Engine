"""The decision model's appraisal questions (mind/affect_appraisal.py).

Designed with the owner on 2026-09-26: each event a character perceived and
each of its own acts is appraised on its own, quoted in every question; each
recalled memory is asked whether it stirs a feeling now; and the mood is read
directly -- twelve spectrums, one five-step question each, and eleven moods
that stand on their own, one graded question each.

Pinned here: every question quotes what it judges and leaves no placeholder
behind, in its text or its answer labels; the event's own actor is named as
an option of "whose doing" and no actor, no such option; the answer labels
are the pack's; one request carries every question; answers read into the
scales the mix expects; an unanswered question is left out rather than read
as zero; and the Japanese pack carries every question and option English
does.
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
ACTS = [{"ref": "s0", "text": 'You said: "Nothing of you is taken."'}]


def test_every_item_gets_its_questions_and_the_mood_its_coordinates():
    qs = appraisal.questions_for(EVENTS, PEOPLE, MEMORIES, ACTS, mood=True, language="en")
    for ref in ("o1", "o2"):
        for name in appraisal.EVENT_QUESTIONS:
            assert f"ev:{ref}:{name}" in qs
        assert f"ev:{ref}:fortune:0" in qs
    for name in appraisal.ACT_QUESTIONS:
        assert f"act:s0:{name}" in qs
    assert {"mem:m7:strength", "mem:m7:tone"} <= set(qs)
    assert {f"dim:{n}" for n in mix.SPECTRUMS} <= set(qs)
    assert {f"mood:{n}" for n in mix.STANDALONE} <= set(qs)
    assert len(qs) == (2 * (len(appraisal.EVENT_QUESTIONS) + 1) + len(appraisal.ACT_QUESTIONS) + 2
                       + len(mix.SPECTRUMS) + len(mix.STANDALONE))


def test_each_question_quotes_what_it_judges_and_leaves_no_placeholder():
    qs = appraisal.questions_for(EVENTS, PEOPLE, MEMORIES, ACTS, mood=True, language="en")
    assert "Hinami: says she took the key." in qs["ev:o1:desirability"]["instructions"]
    assert "Nothing of you is taken." in qs["act:s0:act_against_values"]["instructions"]
    assert "unpleasant" in qs["dim:pleasure"]["instructions"] and "pleasant" in qs["dim:pleasure"]["criteria"]["s4"]
    assert "romantic or sexual desire" in qs["mood:desire"]["instructions"]
    for q in qs.values():
        assert "{" not in q["instructions"] and q["type"] == "choice"
        assert all("{" not in label for label in q["criteria"].values())


def test_whose_doing_names_the_events_own_actor_and_only_when_there_is_one():
    qs = appraisal.questions_for(EVENTS, language="en")
    assert qs["ev:o1:doer"]["criteria"]["actor"] == "Hinami's."
    assert "actor" not in qs["ev:o2:doer"]["criteria"]


def _answer(**probs):
    return {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs}


def test_answers_read_into_the_scales_the_mix_expects():
    answers = {
        "ev:o1:desirability": _answer(very_bad=0.8, bad=0.2),
        "ev:o1:ahead": _answer(worse=1.0),
        "ev:o1:fear_change": _answer(much_more=1.0),
        "ev:o1:doer": _answer(actor=0.9, self=0.1),
        "ev:o1:standards": _answer(very_wrong=0.5, wrong=0.5),
        "ev:o1:control": _answer(clear=1.0),
        "ev:o1:fortune:0": _answer(good=1.0),
        "act:s0:act_against_values": _answer(slight=1.0),
        "act:s0:act_eased_or_stoked": _answer(eased=1.0),
        "mem:m7:strength": _answer(strong=1.0),
        "mem:m7:tone": _answer(unpleasant=1.0),
        "dim:tension": _answer(s4=1.0),
        "mood:grief": _answer(clear=1.0),
    }
    out = appraisal.read(answers, EVENTS[:1], PEOPLE, MEMORIES, ACTS, mood=True, language="en")
    a = out["events"]["o1"]
    assert a["desirability"] == pytest.approx(-0.9) and a["ahead"] == pytest.approx(-0.5)
    assert a["fear_change"] == pytest.approx(1.0) and a["doer"]["actor"] == pytest.approx(0.9)
    assert a["standards"] == pytest.approx(-0.75) and a["control"] == pytest.approx(2 / 3)
    assert a["fortune"] == {"Hinami": pytest.approx(0.5)}
    assert out["acts"]["s0"] == {"against_values": pytest.approx(1 / 3), "eased_or_stoked": pytest.approx(-0.5)}
    assert out["memories"]["m7"] == {"strength": pytest.approx(1.0), "tone": pytest.approx(-0.5)}
    assert out["spectrums"] == {"tension": pytest.approx(1.0)}
    assert out["moods"] == {"grief": pytest.approx(2 / 3)}
    # the mix reads it: harm by her, done wrongly -> anger at her; the feared thing worse
    names = {e.name for e in mix.emotions_from_appraisal(a, ref="o1", actor="Hinami")}
    assert {"anger", "fears_confirmed", "fear"} <= names


def test_an_unanswered_question_is_left_out_not_read_as_zero():
    out = appraisal.read({"ev:o1:desirability": _answer(good=1.0)}, EVENTS[:1])
    assert out["events"]["o1"] == {"desirability": pytest.approx(0.5)}


def test_one_request_carries_every_question(monkeypatch):
    seen = []

    def jev(state, questions):
        seen.append((state, set(questions)))
        return {key: _answer(**{next(iter(q["criteria"])): 1.0}) for key, q in questions.items()}

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    out = appraisal.appraise("YOU ARE The Doctor.", EVENTS, PEOPLE, MEMORIES, ACTS, mood=True, language="en")
    assert len(seen) == 1 and seen[0][0] == "YOU ARE The Doctor."
    assert set(out["events"]) == {"o1", "o2"} and set(out["acts"]) == {"s0"}
    assert set(out["spectrums"]) == set(mix.SPECTRUMS)


def test_nothing_to_ask_asks_nothing(monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda s, q: pytest.fail("asked"))
    assert appraisal.appraise("state") == {"events": {}, "acts": {}, "memories": {}}


@pytest.mark.parametrize("language", ["ja"])
def test_every_pack_carries_every_question_and_option(language):
    english = _prompt_card("en")["affect_appraisal"]
    other = _prompt_card(language)["affect_appraisal"]
    assert set(other) == set(english)
    for option_set, labels in english["options"].items():
        assert set(other["options"][option_set]) == set(labels), option_set
    qs = appraisal.questions_for(EVENTS, PEOPLE, MEMORIES, ACTS, mood=True, language=language)
    for q in qs.values():
        assert "{" not in q["instructions"] and all("{" not in v for v in q["criteria"].values())
