"""The decision model's appraisal questions (mind/affect_appraisal.py).

Designed with the owner on 2026-09-26: each event a character perceived,
each standing concern and each of its own acts is appraised on its own,
quoted in every question; each recalled memory is asked whether it stirs a
feeling now and which mood; and the mood is read directly -- fourteen
spectrums, one five-step question each, and forty moods that stand on their
own, one graded question each. An event is asked how strongly it stirs the
character and how it makes the character feel -- named, not derived: OCC's
rules over nine appraisal questions named events at chance against two blind
raters, and the direct question nearly as well as the raters named them for
each other (`tools/jev_event_feelings.py`).

Pinned here: every question quotes what it judges and leaves no placeholder
behind, in its text or its answer labels; "how does this make you feel"
offers OCC's event emotions and every standalone mood together and nothing
much, while "which of these does recalling it stir" offers the standalone
moods and none of them; a concern gets the event questions and its weight,
apart from the events; the answer labels are the pack's; one request carries
every question; answers read into the scales the mix expects; an unanswered
question is left out rather than read as zero; and the Japanese pack carries
every question and option English does.
"""

from __future__ import annotations

import pytest

from llm import decisions
from llm.prompts import _prompt_card, affect_appraisal_options
from mind import affect_appraisal as appraisal
from mind import affect_mix as mix

EVENTS = [{"ref": "o1", "text": "says she took the key.", "actor": "Hinami"},
          {"ref": "o2", "text": "The console sparks and goes dark."}]
MEMORIES = [{"ref": "m7", "text": "The TARDIS flinched in the vortex scar."}]
ACTS = [{"ref": "s0", "text": 'You said: "Nothing of you is taken."'}]
CONCERNS = [{"ref": "c0", "text": "Still unsettled for you: who opened the lock."}]


def test_every_item_gets_its_questions_and_the_mood_its_coordinates():
    qs = appraisal.questions_for(EVENTS, MEMORIES, ACTS, mood=True, language="en", concerns=CONCERNS)
    for prefix, ref in (("ev", "o1"), ("ev", "o2"), ("con", "c0")):
        for name in appraisal.EVENT_QUESTIONS:
            assert f"{prefix}:{ref}:{name}" in qs
    assert "con:c0:weight" in qs
    for name in appraisal.ACT_QUESTIONS:
        assert f"act:s0:{name}" in qs
    assert {"mem:m7:strength", "mem:m7:tone", "mem:m7:kinds"} <= set(qs)
    assert {f"dim:{n}" for n in mix.SPECTRUMS} <= set(qs)
    assert {f"mood:{n}" for n in mix.STANDALONE} <= set(qs)
    assert len(qs) == (3 * len(appraisal.EVENT_QUESTIONS) + 1 + len(appraisal.ACT_QUESTIONS)
                       + len(appraisal.MEMORY_QUESTIONS) + len(mix.SPECTRUMS) + len(mix.STANDALONE))


def test_an_event_is_asked_how_strongly_and_what_it_makes_the_character_feel():
    assert appraisal.EVENT_QUESTIONS == ("stir_strength", "feel")


def test_each_question_quotes_what_it_judges_and_leaves_no_placeholder():
    qs = appraisal.questions_for(EVENTS, MEMORIES, ACTS, mood=True, language="en", concerns=CONCERNS)
    assert "Hinami: says she took the key." in qs["ev:o1:feel"]["instructions"]
    assert "The console sparks and goes dark." in qs["ev:o2:stir_strength"]["instructions"]
    assert "who opened the lock" in qs["con:c0:feel"]["instructions"]
    assert "Nothing of you is taken." in qs["act:s0:act_against_values"]["instructions"]
    assert "who opened the lock" in qs["con:c0:weight"]["instructions"]
    assert "unpleasant" in qs["dim:pleasure"]["instructions"] and "pleasant" in qs["dim:pleasure"]["criteria"]["s4"]
    # the pack's own phrase, whatever wording it has been refined to
    assert affect_appraisal_options("standalone", "en")["romance"] in qs["mood:romance"]["instructions"]
    for q in qs.values():
        assert "{" not in q["instructions"] and q["type"] == "choice"
        assert all("{" not in label for label in q["criteria"].values())


@pytest.mark.parametrize("language", ["en", "ja"])
def test_how_it_makes_you_feel_offers_every_event_emotion_and_mood_and_nothing_much(language):
    qs = appraisal.questions_for(EVENTS, memories=MEMORIES, language=language)
    offered = set(qs["ev:o1:feel"]["criteria"])
    events = set(affect_appraisal_options("event_emotions", language))
    assert offered == events | set(mix.STANDALONE) | {"none"}
    # every feeling offered moves the mood by its own row
    assert offered - {"none"} <= set(mix.EMOTION_EFFECTS)
    # a memory is asked which of the standalone moods recalling it stirs
    assert set(qs["mem:m7:kinds"]["criteria"]) == set(mix.STANDALONE) | {"none"}
    assert "The TARDIS flinched" in qs["mem:m7:kinds"]["instructions"]


def _answer(**probs):
    return {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs}


def test_answers_read_into_the_scales_the_mix_expects():
    answers = {
        "ev:o1:stir_strength": _answer(strong=1.0),
        "ev:o1:feel": _answer(reproach=0.5, fears_confirmed=0.3, contempt=0.1, none=0.1),
        "act:s0:act_against_values": _answer(slight=1.0),
        "act:s0:act_eased_or_stoked": _answer(eased=1.0),
        "mem:m7:strength": _answer(strong=1.0),
        "mem:m7:tone": _answer(unpleasant=1.0),
        "mem:m7:kinds": _answer(haunted=3.0, grief=1.0),
        "dim:tension": _answer(s4=1.0),
        "mood:grief": _answer(clear=1.0),
    }
    out = appraisal.read(answers, EVENTS[:1], MEMORIES, ACTS, mood=True, language="en")
    a = out["events"]["o1"]
    assert a["stir"] == pytest.approx(1.0)
    assert a["stirs"] == {"reproach": pytest.approx(0.5), "fears_confirmed": pytest.approx(0.3),
                          "contempt": pytest.approx(0.1), "none": pytest.approx(0.1)}
    assert out["acts"]["s0"] == {"against_values": pytest.approx(1 / 3), "eased_or_stoked": pytest.approx(-0.5)}
    m = out["memories"]["m7"]
    assert m["strength"] == pytest.approx(1.0) and m["tone"] == pytest.approx(-0.5)
    assert m["kinds"] == {"haunted": pytest.approx(0.75), "grief": pytest.approx(0.25)}
    assert out["spectrums"] == {"tension": pytest.approx(1.0)}
    assert out["moods"] == {"grief": pytest.approx(2 / 3)}
    # the mix reads it: what the event was named to stir, by share of its
    # strength, and nothing for the share named as none
    named = {e.name: e.intensity for e in mix.emotions_from_appraisal(a, ref="o1")}
    assert named == {"reproach": pytest.approx(0.5), "fears_confirmed": pytest.approx(0.3),
                     "contempt": pytest.approx(0.1)}
    assert {e.name for e in mix.memory_emotions(m["strength"], m["tone"], m["kinds"])} == {"haunted", "grief"}


def test_a_concern_reads_like_an_event_with_its_weight_and_apart_from_the_events():
    answers = {"con:c0:stir_strength": _answer(clear=1.0), "con:c0:feel": _answer(dread=1.0),
               "con:c0:weight": _answer(slight=1.0)}
    out = appraisal.read(answers, concerns=CONCERNS)
    assert out["events"] == {}
    concern = out["concerns"]["c0"]
    assert concern == {"stir": pytest.approx(2 / 3), "stirs": {"dread": pytest.approx(1.0)},
                       "weight": pytest.approx(1 / 3)}
    dread = _names_of(mix.concern_emotions(concern, concern["weight"], ref="c0"))["dread"]
    assert dread.source == "concern" and dread.intensity == pytest.approx(2 / 9, abs=1e-3)


def _names_of(emotions):
    return {e.name: e for e in emotions}


def test_an_unanswered_question_is_left_out_not_read_as_zero():
    out = appraisal.read({"ev:o1:stir_strength": _answer(slight=1.0)}, EVENTS[:1])
    assert out["events"]["o1"] == {"stir": pytest.approx(1 / 3)}


def test_one_request_carries_every_question(monkeypatch):
    seen = []

    def jev(state, questions):
        seen.append((state, set(questions)))
        return {key: _answer(**{next(iter(q["criteria"])): 1.0}) for key, q in questions.items()}

    monkeypatch.setattr(decisions, "OVERRIDE", jev)
    out = appraisal.appraise("YOU ARE The Doctor.", EVENTS, MEMORIES, ACTS, mood=True, language="en",
                             concerns=CONCERNS)
    assert len(seen) == 1 and seen[0][0] == "YOU ARE The Doctor."
    assert set(out["events"]) == {"o1", "o2"} and set(out["acts"]) == {"s0"}
    assert set(out["concerns"]) == {"c0"} and set(out["memories"]) == {"m7"}
    assert set(out["spectrums"]) == set(mix.SPECTRUMS)


def test_nothing_to_ask_asks_nothing(monkeypatch):
    monkeypatch.setattr(decisions, "OVERRIDE", lambda s, q: pytest.fail("asked"))
    assert appraisal.appraise("state") == {"events": {}, "concerns": {}, "acts": {}, "memories": {}}


@pytest.mark.parametrize("language", ["ja"])
def test_every_pack_carries_every_question_and_option(language):
    english = _prompt_card("en")["affect_appraisal"]
    other = _prompt_card(language)["affect_appraisal"]
    assert set(other) == set(english)
    for option_set, labels in english["options"].items():
        assert set(other["options"][option_set]) == set(labels), option_set
    qs = appraisal.questions_for(EVENTS, MEMORIES, ACTS, mood=True, language=language)
    for q in qs.values():
        assert "{" not in q["instructions"] and all("{" not in v for v in q["criteria"].values())
