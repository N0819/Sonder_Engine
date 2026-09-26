"""Emotion and mood as arithmetic (mind/affect_mix.py).

Designed with the owner on 2026-09-26: the decision model appraises events,
and code turns appraisals into emotions by the OCC rules, averages the beat's
emotions into a centre in pleasure-arousal-dominance space, moves the mood
part of the way toward it, decays it home, and habituates a memory's evoked
feeling the owner's way -- full for a few recalls, then less, then full again
after a rest.

Pinned here: each OCC rule produces its emotion with its object; compounds
form only from both halves and do not double the push; the centre is a
weighted average in which bad outweighs good; the mood moves toward it by a
share and never past it; decay returns it home, pleasure below home more
slowly; habituation follows the owner's model; names follow Mehrabian's
octants. The knob values are placeholders, so every test reads them from the
module instead of restating numbers.
"""

from __future__ import annotations

import math

import pytest

from mind import affect_mix as mix
from mind.affect_mix import Emotion, Mood


def _names(emotions):
    return {e.name: e for e in emotions}


# --- OCC: emotions from one event's appraisal ----------------------------------

def test_harm_another_brought_about_wrongly_is_anger_at_them():
    emotions = mix.emotions_from_appraisal(
        {"desirability": -0.8, "happened": 1.0, "agency": {"other": 1.0},
         "standards": -0.8}, ref="o1", actor="Hinami", about="the lie")
    named = _names(emotions)
    assert "anger" in named and named["anger"].about == "Hinami"
    # the compound absorbed its halves rather than pushing three times
    assert named["anger"].intensity == pytest.approx(0.8)
    assert "reproach" not in named and "distress" not in named


def test_good_done_by_another_is_gratitude_toward_them():
    named = _names(mix.emotions_from_appraisal(
        {"desirability": 0.9, "happened": 1.0, "agency": {"other": 1.0}, "standards": 0.9},
        ref="o2", actor="Hinami", about="the rescue"))
    assert named["gratitude"].about == "Hinami"


def test_own_good_act_is_gratification_and_own_wrong_is_remorse():
    good = _names(mix.emotions_from_appraisal(
        {"desirability": 0.7, "happened": 1.0, "agency": {"self": 1.0}, "standards": 0.7}, ref="a"))
    bad = _names(mix.emotions_from_appraisal(
        {"desirability": -0.7, "happened": 1.0, "agency": {"self": 1.0}, "standards": -0.7}, ref="b"))
    assert "gratification" in good and "remorse" in bad


def test_a_compound_needs_both_halves():
    named = _names(mix.emotions_from_appraisal(
        {"desirability": -0.8, "happened": 1.0, "agency": {"nobody": 1.0}, "standards": 0.0}, ref="c"))
    assert "anger" not in named and named["distress"].intensity == pytest.approx(0.8)


def test_fear_is_about_what_might_happen_and_distress_about_what_did():
    ahead = _names(mix.emotions_from_appraisal(
        {"desirability": -0.8, "happened": 0.0, "likelihood": 1.0, "control": 0.0}, ref="d"))
    done = _names(mix.emotions_from_appraisal({"desirability": -0.8, "happened": 1.0}, ref="e"))
    assert "fear" in ahead and "distress" not in ahead
    assert "distress" in done and "fear" not in done


def test_control_makes_a_threat_less_frightening():
    helpless = _names(mix.emotions_from_appraisal(
        {"desirability": -0.8, "happened": 0.0, "likelihood": 1.0, "control": 0.0}, ref="f"))
    able = _names(mix.emotions_from_appraisal(
        {"desirability": -0.8, "happened": 0.0, "likelihood": 1.0, "control": 1.0}, ref="f"))
    assert able["fear"].intensity < helpless["fear"].intensity


def test_a_fear_averted_is_relief_and_a_hope_dashed_is_disappointment():
    relief = _names(mix.emotions_from_appraisal(
        {"desirability": 0.6, "happened": 1.0, "confirmation": {"averts_fear": 1.0}}, ref="g"))
    dashed = _names(mix.emotions_from_appraisal(
        {"desirability": -0.6, "happened": 1.0, "confirmation": {"dashes_hope": 1.0}}, ref="h"))
    assert "relief" in relief and "disappointment" in dashed


def test_fortunes_of_others_follow_liking():
    liking = {"Hinami": 0.8, "Rassilon": -0.8}
    named = _names(mix.emotions_from_appraisal(
        {"desirability": 0.0, "happened": 1.0, "fortune": {"Hinami": -0.8, "Rassilon": 0.8}},
        ref="i", liking=liking))
    assert named["pity"].about == "Hinami"
    assert named["resentment"].about == "Rassilon"
    assert "gloating" not in named and "happy_for" not in named


def test_desire_is_its_own_emotion():
    named = _names(mix.emotions_from_appraisal({"desire": 0.9, "happened": 1.0}, ref="j"))
    assert named["desire"].intensity == pytest.approx(0.9)


def test_a_memory_stirs_the_direction_of_its_tone_scaled_by_habituation():
    warm = mix.memory_emotion(0.8, 0.9, ref="m1")
    sore = mix.memory_emotion(0.8, -0.9, ref="m2")
    dulled = mix.memory_emotion(0.8, 0.9, ref="m1", multiplier=0.5)
    assert warm.name == "joy" and sore.name == "distress" and warm.source == "memory"
    assert dulled.intensity == pytest.approx(warm.intensity * 0.5)
    assert mix.memory_emotion(0.8, 0.0) is None


# --- the mood ---------------------------------------------------------------------

def test_the_centre_is_a_weighted_average_where_bad_outweighs_good():
    joy, distress = Emotion("joy", 0.5), Emotion("distress", 0.5)
    even, _ = mix.centre([joy, distress], negativity=1.0)
    biased, _ = mix.centre([joy, distress], negativity=mix.NEGATIVITY_WEIGHT)
    assert even[0] == pytest.approx((mix.EMOTION_PAD["joy"][0] + mix.EMOTION_PAD["distress"][0]) / 2)
    assert biased[0] < even[0]


@pytest.mark.parametrize("source", ["memory", "concern"])
def test_memories_and_concerns_weigh_less_than_events(source):
    event, other = Emotion("joy", 0.5), Emotion("distress", 0.5, source=source)
    c, _ = mix.centre([event, other], negativity=1.0)
    assert c[0] > (mix.EMOTION_PAD["joy"][0] + mix.EMOTION_PAD["distress"][0]) / 2
    even, _ = mix.centre([event, other], negativity=1.0, weights={source: 1.0})
    assert even[0] == pytest.approx((mix.EMOTION_PAD["joy"][0] + mix.EMOTION_PAD["distress"][0]) / 2)


def test_several_emotions_push_harder_than_one_but_never_past_one():
    _, one = mix.centre([Emotion("joy", 0.6)])
    _, two = mix.centre([Emotion("joy", 0.6), Emotion("pride", 0.6)])
    _, many = mix.centre([Emotion("joy", 1.0)] * 5)
    assert one < two <= 1.0 and many == pytest.approx(1.0)


def test_the_mood_moves_part_of_the_way_toward_the_centre():
    home = Mood()
    moved, trace = mix.mix(home, home, [Emotion("joy", 1.0)], dt=0, reactivity=0.25)
    expected = tuple(0.25 * x for x in mix.EMOTION_PAD["joy"])
    assert moved.vector() == pytest.approx(expected)
    assert trace["strength"] == pytest.approx(1.0)
    # a full push with full reactivity lands ON the centre, never past it
    landed, _ = mix.mix(home, home, [Emotion("joy", 1.0)], dt=0, reactivity=1.0)
    assert landed.vector() == pytest.approx(mix.EMOTION_PAD["joy"])


def test_nothing_felt_leaves_only_decay():
    mood, home = Mood(0.6, 0.4, 0.2), Mood()
    moved, trace = mix.mix(mood, home, [], dt=0)
    assert moved.vector() == pytest.approx(mood.vector()) and trace["centre"] is None


def test_decay_returns_home_and_pleasure_below_home_lingers():
    home = Mood()
    up = mix.decay(Mood(0.8, 0.0, 0.0), home, mix.MOOD_HALF_LIFE, negative_factor=1.0)
    assert up.p == pytest.approx(0.4)
    down = mix.decay(Mood(-0.8, 0.0, 0.0), home, mix.MOOD_HALF_LIFE,
                     negative_factor=mix.NEGATIVE_DECAY_FACTOR)
    assert abs(down.p) > abs(up.p)
    assert mix.decay(Mood(0.5, 0.5, 0.5), home, 0).vector() == pytest.approx((0.5, 0.5, 0.5))


def test_the_mood_stays_inside_the_space():
    extreme, _ = mix.mix(Mood(0.99, 0.99, 0.99), Mood(), [Emotion("gratification", 1.0)] * 3,
                         dt=0, reactivity=1.0)
    assert all(-1.0 <= x <= 1.0 for x in extreme.vector())


# --- habituation, the owner's model ----------------------------------------------

def _recalls(times, state=None, memory="m1"):
    out = []
    for t in times:
        multiplier, state = mix.recall_lands(state, memory, t)
        out.append(multiplier)
    return out, state


def test_a_memory_delivers_fully_for_a_few_recalls_then_less():
    grace_recalls = int(round(mix.HABITUATION_GRACE / mix.HABITUATION_STEP))
    multipliers, _ = _recalls(range(grace_recalls + 2))
    # turn after turn: nearly no rest between recalls
    assert multipliers[:grace_recalls - 1] == pytest.approx([1.0] * (grace_recalls - 1))
    assert multipliers[-1] < multipliers[-2] < 1.0
    assert multipliers[-1] >= 1.0 - mix.HABITUATION_CEILING - 1e-9


def test_after_enough_rest_the_same_memory_delivers_fully_again():
    tired, state = _recalls(range(8))
    assert tired[-1] < 1.0
    later, _ = _recalls([7 + 6 * mix.HABITUATION_HALF_LIFE], state)
    assert later == [1.0]


def test_new_information_resets_a_memory_at_once():
    _, state = _recalls(range(8))
    state = mix.rehabituate(state, "m1")
    again, _ = _recalls([8], state)
    assert again == [1.0]


def test_habituation_is_per_memory():
    _, state = _recalls(range(8), memory="m1")
    other, _ = _recalls([8], state, memory="m2")
    assert other == [1.0]


# --- names -------------------------------------------------------------------------

@pytest.mark.parametrize("vector, octant", [
    ((0.5, 0.5, 0.5), "exuberant"), ((0.5, -0.5, 0.5), "relaxed"), ((-0.5, 0.5, -0.5), "anxious"),
    ((-0.5, 0.5, 0.5), "hostile"), ((-0.5, -0.5, -0.5), "bored"), ((0.5, -0.5, -0.5), "docile"),
])
def test_moods_are_named_by_mehrabians_octants(vector, octant):
    assert mix.mood_name(Mood(*vector)).endswith(octant)


def test_intensity_words_grow_with_distance_from_neutral():
    assert mix.mood_name(Mood(0.1, -0.1, 0.1)).startswith("slightly")
    assert mix.mood_name(Mood(0.9, -0.9, 0.9)).startswith("fully")


def test_the_undercurrent_is_the_strongest_feeling_of_the_other_sign():
    surface, under = mix.surface_and_undercurrent(
        [Emotion("joy", 0.8, about="the landing"), Emotion("fear", 0.4, about="the scar"),
         Emotion("hope", 0.3)], Mood(0.3, 0.2, 0.1))
    assert surface.name == "joy" and under.name == "fear" and under.about == "the scar"


def test_a_mood_that_disagrees_with_the_surface_is_the_undercurrent():
    surface, under = mix.surface_and_undercurrent([Emotion("joy", 0.5)], Mood(-0.6, 0.3, -0.2))
    assert surface.name == "joy" and isinstance(under, str) and "anxious" in under


def test_the_engine_scales():
    affect = mix.engine_affect(Mood(0.5, 0.0, 0.3))
    assert affect == {"valence": 0.5, "arousal": 0.5}
    assert math.isclose(mix.engine_affect(Mood(0.0, 1.0, 0.0))["arousal"], 1.0)
