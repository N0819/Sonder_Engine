"""Emotion and mood as arithmetic (mind/affect_mix.py).

Designed with the owner on 2026-09-26: the decision model appraises what a
character perceived, did and recalled -- naming what each event stirs --
and code turns appraisals into emotions and moves a high-dimensional mood -- fourteen
spectrum coordinates and forty moods that stand on their own ("spectrums of
moods as coordinates as well as some moods that truly stand as their own",
"cover all moods") -- part of the way toward the targets the beat's emotions
set, decays it, eases or stokes it by the character's own acts, and
habituates a memory's evoked feeling the owner's way.

Pinned here: an event stirs what was named for it -- OCC's event emotions
and the standalone moods alike -- by share of how strongly it stirs, and
every feeling it can be named moves the mood; desire is three moods; each
feeling is about its item; a memory's feeling splits between
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


# --- what one perceived event stirs ----------------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_every_feeling_an_event_can_be_named_moves_the_mood(language):
    """The naming question offers OCC's event emotions and the standalone
    moods together; a name without a row would move nothing."""
    offered = {**affect_appraisal_options("event_emotions", language),
               **affect_appraisal_options("standalone", language)}
    assert set(offered) <= set(mix.EMOTION_EFFECTS), set(offered) - set(mix.EMOTION_EFFECTS)


def test_an_event_stirs_what_was_named_for_it_by_share_of_its_strength():
    """Named, not derived (2026-09-26): OCC's rules read a fear made MORE
    LIKELY as a fear come true and a hope brought CLOSER as a hope
    fulfilled, and matched two blind raters' feeling family at chance; the
    feeling named directly matched them nearly as well as they matched
    each other."""
    named = _names(mix.emotions_from_appraisal(
        {"stir": 0.9, "stirs": {"fears_confirmed": 0.5, "dread": 0.3, "none": 0.2}}, ref="o1", about="the letter"))
    assert named["fears_confirmed"].intensity == pytest.approx(0.45)
    assert named["dread"].intensity == pytest.approx(0.27) and named["dread"].about == "the letter"
    assert {e.source for e in named.values()} == {"event"} and "none" not in named


def test_what_an_event_stirs_is_its_share_of_how_strongly_it_stirs():
    named = _names(mix.emotions_from_appraisal(
        {"stir": 0.9, "stirs": {"sexual_desire": 0.6, "romance": 0.3, "none": 0.1}}, ref="h", about="the kiss"))
    assert named["sexual_desire"].intensity == pytest.approx(0.54)
    assert named["romance"].intensity == pytest.approx(0.27) and named["romance"].about == "the kiss"
    assert "none" not in named and "craving" not in named


def test_an_event_that_stirs_nothing_or_nothing_named_feels_nothing():
    assert mix.emotions_from_appraisal({"stir": 0.8, "stirs": {"none": 1.0}}, ref="o2") == []
    assert mix.emotions_from_appraisal({"stir": 0.0, "stirs": {"joy": 1.0}}, ref="o2") == []
    assert mix.emotions_from_appraisal({"stirs": {"joy": 1.0}}, ref="o2") == []
    assert mix.emotions_from_appraisal({}, ref="o2") == []


# --- the character's own acts --------------------------------------------------------

def test_an_act_against_ones_values_is_shame_and_one_that_honours_them_pride():
    against = _names(mix.emotions_from_act({"against_values": 0.8}, ref="s1"))
    honours = _names(mix.emotions_from_act({"honors_values": 0.8, "self_regard": 0.8}, ref="s2"))
    assert "shame" in against and "pride" not in against
    assert "pride" in honours and honours["pride"].source == "act"


def test_an_act_that_only_fits_ones_values_is_not_pride():
    """Pride needs the act to honour a value AND leave the mind thinking
    better of itself: "Papers, please." honoured a guard's values at 0.80 and
    moved his self-regard 0.01 (the act battery, 2026-09-26)."""
    routine = _names(mix.emotions_from_act({"honors_values": 0.8, "self_regard": 0.01}, ref="s4"))
    brave = _names(mix.emotions_from_act({"honors_values": 0.99, "self_regard": 0.88}, ref="s5"))
    assert routine.get("pride") is None or routine["pride"].intensity <= 0.01
    assert brave["pride"].intensity == pytest.approx(0.88)


def test_frustration_is_what_holding_back_costs_and_an_act_alone_has_none():
    """How much the mind minds not having done what it held back is the
    frustration; an act's own answers carry none (asked of every act, the
    held-back want made each one say yes)."""
    held = _names(mix.emotions_from_act({"held_back": 0.7}, ref="held"))
    assert held["frustration"].intensity == pytest.approx(0.7) and held["frustration"].source == "act"
    spoken = _names(mix.emotions_from_act({"honors_values": 0.9, "self_regard": 0.5}, ref="s0"))
    assert "frustration" not in spoken


def test_shame_is_going_against_what_one_believes_right_not_feeling_worse():
    """An act that leaves the mind thinking worse of itself without breaking
    what it believes right -- reading one's own name in print, a fumble
    alone -- is not shame; one that goes against it is."""
    worse_only = _names(mix.emotions_from_act({"self_regard": -0.6, "against_values": 0.05}, ref="s0"))
    wrong = _names(mix.emotions_from_act({"self_regard": -0.6, "against_values": 0.9}, ref="s1"))
    assert worse_only.get("shame") is None or worse_only["shame"].intensity <= 0.05
    assert wrong["shame"].intensity == pytest.approx(0.9)


def test_guilt_needs_the_act_to_have_hurt_someone_and_to_be_wrong():
    """A psychopath's kicked cup hurt someone and read 0.65 on the harm
    question alone; guilt needs the mind to hold the act wrong too."""
    callous = _names(mix.emotions_from_act({"hurt_someone": 0.7, "against_values": 0.0}, ref="s0"))
    snapped = _names(mix.emotions_from_act({"hurt_someone": 0.9, "against_values": 0.8}, ref="s1"))
    assert "guilt" not in callous
    assert snapped["guilt"].intensity == pytest.approx(0.8) and snapped["guilt"].source == "act"


def test_embarrassment_is_being_seen_a_fool_and_needs_no_wrong():
    tripped = _names(mix.emotions_from_act({"looked_foolish": 0.85, "against_values": 0.1}, ref="s0"))
    assert tripped["embarrassment"].intensity == pytest.approx(0.85)
    assert tripped["shame"].intensity == pytest.approx(0.1)
    assert "guilt" not in tripped


def test_falling_short_is_what_neither_shame_nor_embarrassment_names():
    """Below what one expects of oneself, alone and wronging no one -- the
    fumble in an empty practice room -- is falling short; the same answer
    beside a wrong or an audience is left to shame and embarrassment."""
    alone = _names(mix.emotions_from_act({"fell_short": 0.75}, ref="s0"))
    seen = _names(mix.emotions_from_act({"fell_short": 0.8, "looked_foolish": 0.9}, ref="s1"))
    wrong = _names(mix.emotions_from_act({"fell_short": 0.9, "against_values": 0.95}, ref="s2"))
    assert alone["falling_short"].intensity == pytest.approx(0.75)
    assert seen["falling_short"].intensity == pytest.approx(0.08) and seen["embarrassment"].intensity == 0.9
    assert wrong["falling_short"].intensity == pytest.approx(0.045, abs=1e-3)


def test_dissonance_takes_the_pride_out_of_an_act():
    torn = _names(mix.emotions_from_act({"honors_values": 0.8, "self_regard": 0.8,
                                         "against_values": 0.8}, ref="s3"))
    clean = _names(mix.emotions_from_act({"honors_values": 0.8, "self_regard": 0.8}, ref="s3"))
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
    worry = {"stir": 0.8, "stirs": {"dread": 1.0}}
    whole = _names(mix.concern_emotions(worry, 1.0, ref="c0"))
    light = _names(mix.concern_emotions(worry, 0.25, ref="c0"))
    assert whole["dread"].source == "concern" and whole["dread"].intensity == pytest.approx(0.8)
    assert light["dread"].intensity == pytest.approx(whole["dread"].intensity * 0.25)
    assert mix.concern_emotions(worry, 0.0, ref="c0") == []
    unasked = _names(mix.concern_emotions(worry, None, ref="c0"))
    assert unasked["dread"].intensity == pytest.approx(whole["dread"].intensity)


def test_a_feeling_is_about_its_item_never_about_someone():
    """A concern has no actor, and under OCC's rules its blame landed on the
    word "someone": "anger (someone)" is what the magistrate in the lie test
    story was handed as the layer beneath his mood (2026-09-26), which tells
    a mind nothing. A named feeling is about its item -- the concern's own
    text, or the event's, which names whoever acted."""
    lie = {"stir": 0.9, "stirs": {"reproach": 0.7, "anger": 0.3}}
    felt = _names(mix.concern_emotions(lie, 1.0, ref="c0", about="she lied to him"))
    assert felt["reproach"].about == "she lied to him" and felt["anger"].about == "she lied to him"
    named = _names(mix.emotions_from_appraisal(lie, ref="o1", about="Margit: says she was home all night"))
    assert {e.about for e in named.values()} == {"Margit: says she was home all night"}


# --- the mood -----------------------------------------------------------------------------

def test_a_memory_is_felt_as_strongly_as_before_and_moves_the_mood_by_its_intensity():
    """The owner, 2026-09-28: "memory should have a subtler mood affect.
    unless it is a particularly intense memory." How strongly it is FELT is
    untouched; how far it moves the mood follows its strength, curved."""
    [faint] = mix.memory_emotions(0.3, -1.0, ref="faint")
    [intense] = mix.memory_emotions(1.0, -1.0, ref="intense")
    assert faint.intensity == pytest.approx(0.3) and intense.intensity == pytest.approx(1.0)
    assert faint.mood_weight == pytest.approx(0.3 ** (mix.MEMORY_MOOD_CURVE - 1))
    assert intense.mood_weight == pytest.approx(1.0)
    faint_push = mix.targets([faint])["pleasure"][1]
    linear_push = mix.targets([Emotion("distress", 0.3, source="memory")])["pleasure"][1]
    assert faint_push < linear_push / 10
    assert mix.targets([intense])["pleasure"][1] == pytest.approx(
        mix.targets([Emotion("distress", 1.0, source="memory")])["pleasure"][1])
    split = mix.memory_emotions(0.9, -1.0, {"grief": 0.5, "regret": 0.5}, ref="split")
    assert {round(e.mood_weight, 6) for e in split} == {round(0.9 ** (mix.MEMORY_MOOD_CURVE - 1), 6)}


def test_many_faint_memories_barely_move_the_moment():
    """About 69 memories reach a beat now against at most 8 events. Three
    pleasant events and sixty faintly sore memories: curved, the faint ones
    shift the target a little; felt at full weight they would take all the
    say the moment allows them."""
    events = [Emotion("joy", 0.5, ref=f"e{i}") for i in range(3)]
    memories = [e for i in range(60) for e in mix.memory_emotions(0.25, -1.0, ref=f"m{i}")]
    linear = [Emotion(e.name, e.intensity, e.about, e.source, e.ref) for e in memories]
    alone = mix.targets(events)["pleasure"][0]
    curved = mix.targets(events + memories)["pleasure"][0]
    full = mix.targets(events + linear)["pleasure"][0]
    assert curved > 0
    assert alone - curved < (alone - full) / 2


def test_the_memories_together_never_outpull_the_present_moment():
    """The owner, 2026-09-28: memory's "intensity still shouldn't exceed presen
    moment but it should definetly be noticeable". Twenty intense, sore
    memories against one mildly pleasant event, with the mood where it stood
    at neutral: the moment keeps at least half the say in where the mood
    goes, and the memories still plainly move it."""
    present = [Emotion("joy", 0.4, ref="e")]
    memories = [e for i in range(20) for e in mix.memory_emotions(1.0, -1.0, ref=f"m{i}")]
    stood = Mood()
    joy = mix.EMOTION_EFFECTS["joy"]["pleasure"]
    sore = mix.EMOTION_EFFECTS["distress"]["pleasure"]
    target = mix.targets(present + memories, hold=stood)["pleasure"][0]
    alone = mix.targets(present, hold=stood)["pleasure"][0]
    # the memories' half of the say pulls toward `sore`; the moment's half
    # sits between the event and where the mood stood
    assert target >= sore / 2 + min(joy, stood.get("pleasure")) / 2 - 1e-9
    assert target < alone - 0.25 * (alone - sore), "and the memories are plainly felt"


def test_a_quiet_beat_is_coloured_by_memory_never_swamped():
    """Nothing new reached the mind: the moment still has its say and holds
    the mood where it stands, so what is remembered moves it noticeably and
    at most halfway toward itself -- one intense memory or twenty."""
    stood = Mood({"pleasure": 0.3})
    sore = mix.EMOTION_EFFECTS["distress"]["pleasure"]
    [one] = mix.memory_emotions(1.0, -1.0, ref="one")
    many = [e for i in range(20) for e in mix.memory_emotions(1.0, -1.0, ref=f"m{i}")]
    for memories in ([one], many):
        target, push = mix.targets(memories, hold=stood)["pleasure"]
        assert target == pytest.approx((stood.get("pleasure") + sore) / 2)
        # noticeable, and never harder than one intense memory's full pull
        assert 0.35 <= push <= mix.QUIET_PRESENT + 1e-9
    moved, _goals = mix.mix(stood, Mood(), [one], 0.0)
    assert moved.get("pleasure") < stood.get("pleasure") - 0.02, "noticeable"


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


def test_an_acts_feeling_is_the_surface_only_where_it_outweighs_the_moment():
    """Like for like: a moment's feelings split one stir among names, an
    act's feeling is whole. At "Go on, then", Wren's guilt (0.62, of a stir
    whose named feelings sum to 0.84) was stored under minding her words
    (0.67) until an act had to outweigh everything the moment stirred."""
    moment = [Emotion("guilt", 0.62, "Go on, then", "event", "o1"),
              Emotion("resolve", 0.12, "Go on, then", "event", "o1"),
              Emotion("moved", 0.10, "Go on, then", "event", "o1"),
              Emotion("dread", 0.30, "the coach", "event", "o2")]
    minded = Emotion("frustration", 0.67, "You held back from: saying nothing", "act", "held")
    surface, _under = mix.surface_and_undercurrent(moment + [minded], Mood())
    assert surface.name == "guilt" and surface.source == "event"
    overwhelming = Emotion("shame", 0.95, "You said it", "act", "s0")
    surface, _under = mix.surface_and_undercurrent(moment + [minded, overwhelming], Mood())
    assert surface.name == "shame"
    # with nothing from the moment, the act is the surface as before
    surface, _under = mix.surface_and_undercurrent([minded], Mood())
    assert surface.name == "frustration"


def test_the_moment_is_led_by_what_stirred_most_as_a_whole():
    """The moment's strongest item is the one that stirred most as a whole,
    not the one holding the largest single feeling: a mixed event splits
    its stir among names. At the Bellandi birthday (2026-09-26) Marco's
    announcement that he is emigrating stirred Rosa 0.99, spread over
    dread, sadness, longing and distress; his straightening in his chair
    stirred 0.62, nearly all dread -- and she was handed, and stored, dread
    about the chair, with frustration at a held-back want (0.96) taking the
    surface against the chair's 0.62 rather than the announcement's 0.99."""
    announcement = [Emotion("dread", 0.23, "I'm leaving for Melbourne", "event", "o3"),
                    Emotion("sadness", 0.15, "I'm leaving for Melbourne", "event", "o3"),
                    Emotion("longing", 0.14, "I'm leaving for Melbourne", "event", "o3"),
                    Emotion("distress", 0.14, "I'm leaving for Melbourne", "event", "o3"),
                    Emotion("anger", 0.13, "I'm leaving for Melbourne", "event", "o3")]
    chair = [Emotion("dread", 0.37, "He straightens in his chair", "event", "o2"),
             Emotion("anticipation", 0.17, "He straightens in his chair", "event", "o2")]
    surface, _under = mix.surface_and_undercurrent(chair + announcement, Mood())
    assert surface.ref == "o3" and surface.name == "dread"
    # an act is weighed against the announcement's whole stir (0.79)
    minded = Emotion("frustration", 0.75, "You held back from: opening the box", "act", "held")
    surface, _under = mix.surface_and_undercurrent(chair + announcement + [minded], Mood())
    assert surface.ref == "o3"
    surface, _under = mix.surface_and_undercurrent(
        chair + announcement + [Emotion("shame", 0.85, "You said it", "act", "s0")], Mood())
    assert surface.name == "shame"


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
