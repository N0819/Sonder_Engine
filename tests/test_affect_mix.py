"""Emotion and mood as arithmetic (mind/affect_mix.py).

Designed with the owner on 2026-09-26: the decision model appraises what a
character perceived, did and recalled, and code turns appraisals into
emotions by the OCC rules and moves a high-dimensional mood -- fourteen
spectrum coordinates and thirty-one moods that stand on their own ("spectrums of
moods as coordinates as well as some moods that truly stand as their own",
"cover all moods") -- part of the way toward the targets the beat's emotions
set, decays it, eases or stokes it by the character's own acts, and
habituates a memory's evoked feeling the owner's way.

Pinned here: each OCC rule produces its emotion with its object; compounds
form only from both halves, never from a stirred mood; every standalone mood
can be stirred by name, desire as three; a memory's feeling splits between
the moods named for it and a plain remainder by its tone; a concern stirs in
proportion to its weight; own acts give pride, shame and frustration; a
coordinate's target is a weighted average in which a negativity weight tilts
toward bad and memories and concerns weigh less; the mood moves only the
coordinates the beat touched, by a share, inside their bounds; decay,
settling and easing move it the right way; habituation follows the owner's
model; the undercurrent is what the past and the unsettled stirred; the
code's coordinates are the pack's. The knob values are placeholders, so
every test reads them from the module instead of restating numbers.
"""

from __future__ import annotations

import pytest

from llm.prompts import affect_appraisal_options
from mind import affect_mix as mix
from mind.affect_mix import Emotion, Mood


def _names(emotions):
    return {e.name: e for e in emotions}


# --- the coordinates are the pack's -------------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_coordinates_are_the_packs(language):
    assert mix.SPECTRUMS == tuple(affect_appraisal_options("dimensions", language))
    assert mix.STANDALONE == tuple(affect_appraisal_options("standalone", language))


def test_every_emotion_moves_only_known_coordinates_within_their_bounds():
    for name, effects in mix.EMOTION_EFFECTS.items():
        for coord, value in effects.items():
            assert coord in mix.SPECTRUMS or coord in mix.STANDALONE, (name, coord)
            lo, hi = (0.0, 1.0) if coord in mix.STANDALONE else (-1.0, 1.0)
            assert lo <= value <= hi, (name, coord)


def test_every_standalone_mood_can_be_stirred_and_moves_itself_in_full():
    for name in mix.STANDALONE:
        assert mix.EMOTION_EFFECTS[name][name] == 1.0, name


def test_desire_is_three_moods():
    # the owner: "there is non romantic and sexual desire to consider"
    assert {"romance", "sexual_desire", "craving"} <= set(mix.STANDALONE)
    assert "desire" not in mix.STANDALONE and "desire" not in mix.EMOTION_EFFECTS


# --- OCC: emotions from one perceived event -------------------------------------------

def test_harm_another_did_wrongly_is_anger_at_them():
    named = _names(mix.emotions_from_appraisal(
        {"desirability": -0.8, "doer": {"actor": 1.0}, "standards": -0.8},
        ref="o1", actor="Hinami", about="the lie"))
    assert named["anger"].about == "Hinami" and named["anger"].intensity == pytest.approx(0.8)
    assert "reproach" not in named and "distress" not in named


def test_good_another_did_is_gratitude_toward_them():
    named = _names(mix.emotions_from_appraisal(
        {"desirability": 0.9, "doer": {"actor": 1.0}, "standards": 0.9}, ref="o2", actor="Hinami"))
    assert named["gratitude"].about == "Hinami"


def test_own_good_act_is_gratification_and_own_wrong_is_remorse():
    good = _names(mix.emotions_from_appraisal(
        {"desirability": 0.7, "doer": {"self": 1.0}, "standards": 0.7}, ref="a"))
    bad = _names(mix.emotions_from_appraisal(
        {"desirability": -0.7, "doer": {"self": 1.0}, "standards": -0.7}, ref="b"))
    assert "gratification" in good and "remorse" in bad


def test_a_compound_needs_both_halves():
    named = _names(mix.emotions_from_appraisal(
        {"desirability": -0.8, "doer": {"nobody": 1.0}, "standards": 0.0}, ref="c"))
    assert "anger" not in named and named["distress"].intensity == pytest.approx(0.8)


def test_what_it_makes_likely_ahead_is_hope_or_fear_and_control_eases_fear():
    ahead_good = _names(mix.emotions_from_appraisal({"ahead": 0.8}, ref="d"))
    helpless = _names(mix.emotions_from_appraisal({"ahead": -0.8, "control": 0.0}, ref="d"))
    able = _names(mix.emotions_from_appraisal({"ahead": -0.8, "control": 1.0}, ref="d"))
    assert "hope" in ahead_good and "fear" in helpless
    assert able["fear"].intensity < helpless["fear"].intensity


def test_a_fear_eased_is_relief_and_confirmed_is_fears_confirmed():
    eased = _names(mix.emotions_from_appraisal({"fear_change": -0.8}, ref="e"))
    worse = _names(mix.emotions_from_appraisal({"fear_change": 0.8}, ref="e"))
    assert "relief" in eased and "fears_confirmed" in worse


def test_a_hope_brought_closer_is_satisfaction_and_pushed_away_disappointment():
    closer = _names(mix.emotions_from_appraisal({"hope_change": 0.8}, ref="f"))
    further = _names(mix.emotions_from_appraisal({"hope_change": -0.8}, ref="f"))
    assert "satisfaction" in closer and "disappointment" in further


def test_fortunes_of_others_follow_liking():
    named = _names(mix.emotions_from_appraisal(
        {"fortune": {"Hinami": -0.8, "Rassilon": 0.8}}, ref="g",
        liking={"Hinami": 0.8, "Rassilon": -0.8}))
    assert named["pity"].about == "Hinami" and named["resentment"].about == "Rassilon"
    assert "gloating" not in named and "happy_for" not in named


def test_what_an_event_stirs_is_its_share_of_how_strongly_it_stirs():
    named = _names(mix.emotions_from_appraisal(
        {"stir": 0.9, "stirs": {"sexual_desire": 0.6, "romance": 0.3, "none": 0.1}}, ref="h", about="the kiss"))
    assert named["sexual_desire"].intensity == pytest.approx(0.54)
    assert named["romance"].intensity == pytest.approx(0.27) and named["romance"].about == "the kiss"
    assert "none" not in named and "craving" not in named


def test_a_stirred_mood_never_becomes_half_of_a_compound():
    # joy and a stirred admiration are not gratitude: only OCC's own halves compound
    named = _names(mix.emotions_from_appraisal(
        {"desirability": 0.8, "stir": 1.0, "stirs": {"admiration": 1.0}}, ref="i"))
    assert "gratitude" not in named
    assert named["joy"].intensity == pytest.approx(0.8) and named["admiration"].intensity == pytest.approx(1.0)


# --- the character's own acts --------------------------------------------------------

def test_an_act_against_ones_values_is_shame_and_one_that_honours_them_pride():
    against = _names(mix.emotions_from_act({"against_values": 0.8}, ref="s1"))
    honours = _names(mix.emotions_from_act({"honors_values": 0.8}, ref="s2"))
    assert "shame" in against and "pride" not in against
    assert "pride" in honours and honours["pride"].source == "act"


def test_what_was_wanted_instead_is_frustration():
    assert "frustration" in _names(mix.emotions_from_act({"wanted_instead": 0.7}, ref="held"))


def test_dissonance_takes_the_pride_out_of_an_act():
    torn = _names(mix.emotions_from_act({"honors_values": 0.8, "against_values": 0.8}, ref="s3"))
    clean = _names(mix.emotions_from_act({"honors_values": 0.8}, ref="s3"))
    assert torn["pride"].intensity < clean["pride"].intensity


# --- memories ---------------------------------------------------------------------------

def test_a_memory_without_kinds_stirs_the_direction_of_its_tone_scaled_by_habituation():
    [warm], [sore] = mix.memory_emotions(0.8, 0.9, ref="m1"), mix.memory_emotions(0.8, -0.9, ref="m2")
    [dulled] = mix.memory_emotions(0.8, 0.9, ref="m1", multiplier=0.5)
    assert warm.name == "joy" and sore.name == "distress" and warm.source == "memory"
    assert dulled.intensity == pytest.approx(warm.intensity * 0.5)
    assert mix.memory_emotions(0.8, 0.0) == []


def test_a_memory_stirs_the_moods_named_for_it_and_its_tone_carries_the_rest():
    # the owner: some moods "may be purely memory related"
    named = _names(mix.memory_emotions(1.0, -0.5, {"grief": 0.5, "regret": 0.3, "none": 0.2},
                                       ref="m3", multiplier=0.8))
    assert named["grief"].intensity == pytest.approx(0.4) and named["regret"].intensity == pytest.approx(0.24)
    assert named["distress"].intensity == pytest.approx(1.0 * 0.8 * 0.5 * 0.2)
    assert {e.source for e in named.values()} == {"memory"}
    fully_named = _names(mix.memory_emotions(1.0, 0.9, {"nostalgia": 1.0}, ref="m4"))
    assert set(fully_named) == {"nostalgia"}


def test_a_concern_stirs_in_proportion_to_how_much_it_weighs_now():
    worry = {"ahead": -0.8, "control": 0.0}
    whole = _names(mix.concern_emotions(worry, 1.0, ref="c0"))
    light = _names(mix.concern_emotions(worry, 0.25, ref="c0"))
    assert whole["fear"].source == "concern"
    assert light["fear"].intensity == pytest.approx(whole["fear"].intensity * 0.25)
    assert mix.concern_emotions(worry, 0.0, ref="c0") == []
    unasked = _names(mix.concern_emotions(worry, None, ref="c0"))
    assert unasked["fear"].intensity == pytest.approx(whole["fear"].intensity)


# --- the mood -----------------------------------------------------------------------------

def test_a_target_is_a_weighted_average_and_a_negativity_weight_tilts_it():
    joy, distress = Emotion("joy", 0.5), Emotion("distress", 0.5)
    even = mix.targets([joy, distress], negativity=1.0)["pleasure"][0]
    biased = mix.targets([joy, distress], negativity=1.5)["pleasure"][0]
    assert even == pytest.approx((mix.EMOTION_EFFECTS["joy"]["pleasure"]
                                  + mix.EMOTION_EFFECTS["distress"]["pleasure"]) / 2)
    assert biased < even


@pytest.mark.parametrize("source", ["memory", "concern"])
def test_memories_and_concerns_weigh_less_than_events(source):
    event, other = Emotion("joy", 0.5), Emotion("distress", 0.5, source=source)
    mean = (mix.EMOTION_EFFECTS["joy"]["pleasure"] + mix.EMOTION_EFFECTS["distress"]["pleasure"]) / 2
    assert mix.targets([event, other], negativity=1.0)["pleasure"][0] > mean
    even = mix.targets([event, other], negativity=1.0, weights={source: 1.0})["pleasure"][0]
    assert even == pytest.approx(mean)


def test_several_emotions_push_harder_than_one_but_never_past_one():
    one = mix.targets([Emotion("joy", 0.6)])["pleasure"][1]
    two = mix.targets([Emotion("joy", 0.6), Emotion("pride", 0.6)])["pleasure"][1]
    many = mix.targets([Emotion("joy", 1.0)] * 5)["pleasure"][1]
    assert one < two <= 1.0 and many == pytest.approx(1.0)


def test_the_mood_moves_part_of_the_way_and_only_where_the_beat_touched():
    home = Mood()
    moved, _ = mix.mix(home, home, [Emotion("fear", 1.0)], dt=0, reactivity=0.25)
    for coord, value in mix.EMOTION_EFFECTS["fear"].items():
        assert moved.get(coord) == pytest.approx(0.25 * value)
    assert moved.get("playfulness") == 0.0 and moved.get("awe") == 0.0


def test_a_full_push_with_full_reactivity_lands_on_the_target_never_past_it():
    home = Mood()
    landed, _ = mix.mix(home, home, [Emotion("anger", 1.0)], dt=0, reactivity=1.0)
    assert landed.get("anger") == pytest.approx(1.0)
    assert landed.get("pleasure") == pytest.approx(mix.EMOTION_EFFECTS["anger"]["pleasure"])


def test_standalone_moods_stay_between_nothing_and_full():
    mood, _ = mix.mix(Mood({"anger": 0.9}), Mood(), [Emotion("anger", 1.0)] * 3, dt=0, reactivity=1.0)
    assert 0.0 <= mood.get("anger") <= 1.0


def test_decay_returns_spectrums_home_fades_standalone_moods_and_lingers_below_home():
    home = Mood()
    up = mix.decay(Mood({"pleasure": 0.8, "anger": 0.8}), home, mix.SPECTRUM_HALF_LIFE, negative_factor=1.0)
    assert up.get("pleasure") == pytest.approx(0.4)
    assert up.get("anger") == pytest.approx(0.8 * 0.5 ** (mix.SPECTRUM_HALF_LIFE / mix.STANDALONE_HALF_LIFE))
    down = mix.decay(Mood({"pleasure": -0.8}), home, mix.SPECTRUM_HALF_LIFE, negative_factor=1.5)
    assert abs(down.get("pleasure")) > abs(up.get("pleasure"))
    toward = mix.decay(Mood({"pleasure": 0.0}), Mood({"pleasure": 0.5}), mix.SPECTRUM_HALF_LIFE,
                       negative_factor=1.0)
    assert toward.get("pleasure") == pytest.approx(0.25)


def test_settling_moves_toward_the_direct_reading():
    settled = mix.settle(Mood({"tension": 0.0}), {"tension": 0.8, "grief": 0.6}, reactivity=0.5)
    assert settled.get("tension") == pytest.approx(0.4) and settled.get("grief") == pytest.approx(0.3)


def test_an_act_that_eased_the_feeling_calms_and_one_that_stoked_it_inflames():
    home = Mood()
    angry = Mood({"tension": 0.6, "anger": 0.6})
    eased = mix.ease(angry, home, -1.0, rate=0.5)
    stoked = mix.ease(angry, home, 1.0, rate=0.5)
    assert eased.get("anger") < 0.6 < stoked.get("anger")
    assert eased.get("tension") < 0.6 < stoked.get("tension")


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
    again, _ = _recalls([8], mix.rehabituate(state, "m1"))
    assert again == [1.0]


def test_habituation_is_per_memory():
    _, state = _recalls(range(8), memory="m1")
    other, _ = _recalls([8], state, memory="m2")
    assert other == [1.0]


# --- names ---------------------------------------------------------------------------

def test_the_profile_names_the_most_salient_parts_first():
    profile = mix.mood_profile(Mood({"tension": 0.7, "grief": 0.9, "pleasure": -0.2, "awe": 0.1}))
    assert [name for name, _v in profile] == ["grief", "tension"]


@pytest.mark.parametrize("coords, octant", [
    ({"pleasure": 0.5, "energy": 0.5, "tension": 0.5, "control": 0.5}, "exuberant"),
    ({"pleasure": 0.5, "energy": -0.5, "tension": -0.5, "control": 0.5}, "relaxed"),
    ({"pleasure": -0.5, "energy": 0.5, "tension": 0.5, "control": -0.5}, "anxious"),
    ({"pleasure": -0.5, "energy": -0.5, "tension": -0.5, "control": -0.5}, "bored"),
])
def test_moods_are_named_by_mehrabians_octants(coords, octant):
    assert mix.mood_name(Mood(coords)) == octant


def test_the_undercurrent_is_the_strongest_feeling_of_the_other_sign():
    surface, under = mix.surface_and_undercurrent(
        [Emotion("joy", 0.8, about="the landing"), Emotion("fear", 0.4, about="the scar"),
         Emotion("hope", 0.3)], Mood())
    assert surface.name == "joy" and under.name == "fear" and under.about == "the scar"


def test_what_the_past_or_the_unsettled_stirred_is_the_undercurrent():
    beneath = mix.UNDERCURRENT_FLOOR + 0.1
    surface, under = mix.surface_and_undercurrent(
        [Emotion("nostalgia", 0.9, source="memory"), Emotion("joy", 0.5, about="the landing"),
         Emotion("fear", 0.4), Emotion("grief", beneath, source="memory", about="Gallifrey")], Mood())
    # the present is the surface even when a memory stirs harder; the
    # strongest feeling beneath is the undercurrent, whatever its sign
    assert surface.name == "joy" and under.name == "nostalgia"
    surface, under = mix.surface_and_undercurrent(
        [Emotion("joy", 0.5), Emotion("fear", 0.3, source="concern")], Mood())
    assert under.name == "fear" and under.source == "concern"


def test_a_faint_feeling_beneath_is_not_named():
    faint = mix.UNDERCURRENT_FLOOR / 2
    surface, under = mix.surface_and_undercurrent(
        [Emotion("joy", 0.5), Emotion("regret", faint, source="memory"), Emotion("fear", 0.3)], Mood())
    assert under.name == "fear"


def test_a_mood_that_disagrees_with_the_surface_is_the_undercurrent():
    surface, under = mix.surface_and_undercurrent([Emotion("joy", 0.5)],
                                                  Mood({"pleasure": -0.6, "tension": 0.7}))
    assert surface.name == "joy" and under == "tension"


def test_the_engine_scales():
    assert mix.engine_affect(Mood({"pleasure": 0.5})) == {"valence": 0.5, "arousal": 0.5}
    assert mix.engine_affect(Mood({"energy": 1.0, "tension": 1.0}))["arousal"] == pytest.approx(1.0)
