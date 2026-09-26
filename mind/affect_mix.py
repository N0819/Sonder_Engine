"""Emotion and mood as arithmetic: what a beat's events, memories and the
character's own acts make it feel, and the mood those feelings average into.

Designed with the owner on 2026-09-26 (`docs/design/DESIGN_JEV_CHARACTER_PASS.md`,
"Emotion and mood" and "The mood math"). The decision model appraises
(`mind/affect_appraisal.py`); this module is the code half and holds no model.

- **Emotions** an event stirs, each with its object -- what it is about:
  the feelings the model names for it, from OCC's event emotions (Ortony,
  Clore and Collins, "The Cognitive Structure of Emotions", 1988) and the
  standalone moods offered together, each by its share times how strongly
  the event stirs the character. The character's own acts, appraised after
  its turn, add pride, shame and the cost of restraint.
- **Mood as a high-dimensional object** (the owner: "spectrums of moods as
  coordinates as well as some moods that truly stand as their own", and "We
  are trying to cover all moods and make a coordinate system out of them"):
  fourteen bipolar spectrum coordinates in [-1, 1] and forty standalone
  moods in [0, 1], named by the language pack. Each emotion pushes the
  coordinates it moves (`EMOTION_EFFECTS`); a beat's emotions average into a
  target per coordinate, and the mood moves part of the way toward it -- the
  shape measured to beat carrying the previous mood alone. Between beats
  spectrums decay toward home and standalone moods fade. The decision
  model's direct reading of the mood can settle it too (`settle`).
- **The layer beneath**: what a recalled memory or a standing concern stirs
  is the undercurrent, what the present stirs the surface (the owner: some
  moods "may be purely memory related ... or their undercurrents at least").
  A memory stirs the standalone moods the model names for it -- nostalgia,
  grief, regret and the rest -- and a plain pleasant or unpleasant feeling
  for what none of them covers; a concern stirs what it is named to stir, in
  proportion to how much it weighs on the character now.
- **Habituation** of a memory's evoked feeling, the owner's model: full for a
  few recalls, less after, full again after a rest.

`mind/affect_pass.py` runs it around each character call. Every knob below,
and every number in `EMOTION_EFFECTS`, is the owner's to set; the values are
placeholders.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: The mood's bipolar coordinates and its standalone moods -- the keys the
#: language pack's `affect_appraisal.options.dimensions` and `.standalone`
#: name. Grounded in the validated mood inventories: the Profile of Mood
#: States, PANAS-X, Matthews' UWIST (energetic apart from tense arousal) and
#: Fontaine et al. 2007 (valence, power, arousal, novelty); approach against
#: avoidance (`boldness`) is its own axis because anger approaches and fear
#: withdraws at the same displeasure (Carver and Harmon-Jones, 2009), and
#: wanting company is apart from feeling connected, which is how loneliness
#: differs from a solitude one chose. The standalone moods cover every
#: category Cowen and Keltner (2017) found self-report keeps distinct that no
#: spectrum already holds -- desire in three (romance, sexual desire, and a
#: craving that is neither: the owner, "there is non romantic and sexual
#: desire to consider") -- then Plutchik's anticipation, the self-conscious
#: and hostile moods their list lacks, numbness (which no point near neutral
#: can tell from calm), and the moods whose object is the past, which memory
#: stirs.
SPECTRUMS = ("pleasure", "energy", "tension", "control", "clarity", "connection", "openness",
             "playfulness", "hope", "self_regard", "safety", "engagement", "boldness", "sociability")
STANDALONE = ("romance", "sexual_desire", "craving", "greed", "curiosity", "anticipation", "awe",
              "admiration", "aesthetic", "amusement", "moved", "tenderness", "compassion",
              "gratitude", "anger", "contempt", "disgust", "horror", "jealousy", "envy", "guilt",
              "embarrassment", "sadness", "surprise", "resolve", "numbness", "nostalgia", "grief",
              "regret", "longing", "homesickness", "haunted", "protectiveness", "dread",
              "suspicion", "urgency", "mastery", "triumph", "relief", "contentment")

#: How each emotion moves the mood: a value per coordinate it touches
#: (spectrums in [-1, 1], standalone moods in [0, 1]). The OCC emotions and
#: `frustration` (the cost of a restraint the character's own act paid), then
#: one row per standalone mood -- itself in full and the spectrums it moves.
#: An event or a concern stirs any of them by name, a memory the standalone
#: moods. Four names are both (admiration, gratitude, anger, relief): OCC's
#: emotion and the standalone mood are one feeling. Hand-set, coarse, the
#: owner's.
EMOTION_EFFECTS = {
    "joy": {"pleasure": .8, "energy": .4, "tension": -.3, "hope": .3, "playfulness": .3,
            "engagement": .3, "sociability": .2},
    "distress": {"pleasure": -.7, "tension": .4, "control": -.3, "hope": -.3, "energy": -.2,
                 "sadness": .3},
    "hope": {"pleasure": .4, "hope": .8, "energy": .3, "engagement": .3, "boldness": .2},
    "fear": {"pleasure": -.6, "tension": .8, "safety": -.8, "control": -.5, "energy": .3,
             "openness": -.3, "boldness": -.6},
    "satisfaction": {"pleasure": .6, "tension": -.4, "hope": .3, "control": .3},
    "disappointment": {"pleasure": -.5, "hope": -.5, "energy": -.3, "sadness": .4},
    "relief": {"relief": 1.0, "pleasure": .5, "tension": -.6, "safety": .5},
    "fears_confirmed": {"pleasure": -.6, "safety": -.6, "hope": -.6, "tension": .5, "control": -.5},
    "pride": {"pleasure": .5, "self_regard": .8, "control": .4, "energy": .3, "boldness": .3},
    "shame": {"pleasure": -.5, "self_regard": -.8, "openness": -.4, "control": -.3, "boldness": -.4,
              "sociability": -.4, "guilt": .4},
    "reproach": {"pleasure": -.3, "openness": -.3, "connection": -.3, "anger": .5, "contempt": .3},
    "gratification": {"pleasure": .7, "self_regard": .6, "control": .4, "energy": .4},
    "remorse": {"pleasure": -.5, "self_regard": -.7, "hope": -.3, "energy": -.3, "guilt": .8,
                "regret": .5},
    "happy_for": {"pleasure": .5, "connection": .5, "openness": .4, "tenderness": .3},
    "pity": {"pleasure": -.3, "connection": .3, "compassion": .8},
    "resentment": {"pleasure": -.4, "connection": -.4, "openness": -.3, "anger": .3, "envy": .6},
    "gloating": {"pleasure": .4, "self_regard": .3, "connection": -.3, "amusement": .3, "contempt": .3},
    "frustration": {"pleasure": -.4, "tension": .5, "control": -.3, "anger": .3},
    # the standalone moods
    "romance": {"romance": 1.0, "pleasure": .4, "connection": .5, "openness": .4, "energy": .2,
                "sociability": .5},
    "sexual_desire": {"sexual_desire": 1.0, "energy": .5, "engagement": .5, "tension": .2,
                      "pleasure": .3, "boldness": .3, "sociability": .4},
    "craving": {"craving": 1.0, "energy": .4, "engagement": .4, "tension": .3, "boldness": .3},
    "greed": {"greed": 1.0, "engagement": .4, "tension": .2, "boldness": .3, "connection": -.2,
              "openness": -.2},
    "curiosity": {"curiosity": 1.0, "engagement": .6, "openness": .4, "energy": .3, "boldness": .3},
    "anticipation": {"anticipation": 1.0, "hope": .5, "energy": .4, "engagement": .5, "tension": .2,
                     "pleasure": .3},
    "awe": {"awe": 1.0, "engagement": .5, "openness": .4, "control": -.3, "clarity": -.2},
    "admiration": {"admiration": 1.0, "pleasure": .4, "connection": .4, "openness": .4,
                   "engagement": .3},
    "aesthetic": {"aesthetic": 1.0, "pleasure": .5, "engagement": .4, "tension": -.3},
    "amusement": {"amusement": 1.0, "pleasure": .6, "playfulness": .7, "tension": -.3},
    "moved": {"moved": 1.0, "connection": .6, "openness": .5, "pleasure": .3},
    "tenderness": {"tenderness": 1.0, "connection": .6, "pleasure": .4, "tension": -.2,
                   "sociability": .4},
    "compassion": {"compassion": 1.0, "connection": .4, "pleasure": -.3, "sociability": .3},
    "gratitude": {"gratitude": 1.0, "pleasure": .5, "connection": .6, "openness": .5,
                  "sociability": .3},
    "anger": {"anger": 1.0, "pleasure": -.6, "tension": .6, "energy": .5, "control": .3,
              "openness": -.4, "boldness": .6},
    "contempt": {"contempt": 1.0, "pleasure": -.2, "self_regard": .3, "connection": -.5,
                 "openness": -.3},
    "disgust": {"disgust": 1.0, "pleasure": -.6, "openness": -.4, "boldness": -.3, "sociability": -.2},
    "horror": {"horror": 1.0, "pleasure": -.8, "safety": -.8, "tension": .8, "control": -.5,
               "clarity": -.3, "boldness": -.5},
    "jealousy": {"jealousy": 1.0, "pleasure": -.5, "tension": .5, "safety": -.3, "connection": -.3,
                 "self_regard": -.3},
    "envy": {"envy": 1.0, "pleasure": -.4, "self_regard": -.4, "craving": .3},
    "guilt": {"guilt": 1.0, "pleasure": -.5, "self_regard": -.5, "tension": .3},
    "embarrassment": {"embarrassment": 1.0, "self_regard": -.4, "tension": .4, "openness": -.3,
                      "boldness": -.3, "sociability": -.4},
    "sadness": {"sadness": 1.0, "pleasure": -.7, "energy": -.5, "hope": -.3, "sociability": -.3},
    "surprise": {"surprise": 1.0, "energy": .4, "clarity": -.4, "engagement": .4},
    "resolve": {"resolve": 1.0, "energy": .4, "control": .4, "boldness": .6, "hope": .3, "clarity": .3},
    "numbness": {"numbness": 1.0, "pleasure": -.2, "engagement": -.6, "energy": -.4,
                 "connection": -.4, "openness": -.3},
    "nostalgia": {"nostalgia": 1.0, "pleasure": .2, "connection": .3, "self_regard": .1, "hope": .1},
    "grief": {"grief": 1.0, "sadness": .6, "pleasure": -.7, "energy": -.4, "hope": -.3,
              "connection": -.3},
    "regret": {"regret": 1.0, "pleasure": -.4, "self_regard": -.4, "hope": -.2},
    "longing": {"longing": 1.0, "pleasure": -.2, "connection": -.3, "sociability": .4},
    "homesickness": {"homesickness": 1.0, "longing": .5, "pleasure": -.3, "safety": -.3,
                     "connection": -.4},
    "haunted": {"haunted": 1.0, "pleasure": -.4, "tension": .5, "safety": -.5, "clarity": -.3},
    # added 2026-09-26 from what a blind rater kept naming as uncovered
    # across 272 rated beats (docs/experiments/JEV_MEMORY_PROBE_2026_09_26.md)
    "protectiveness": {"protectiveness": 1.0, "boldness": .5, "tension": .4, "connection": .4,
                       "engagement": .4, "control": .2},
    "dread": {"dread": 1.0, "pleasure": -.6, "tension": .7, "safety": -.6, "hope": -.5,
              "control": -.4},
    "suspicion": {"suspicion": 1.0, "openness": -.6, "connection": -.4, "tension": .4,
                  "safety": -.3, "engagement": .3},
    "urgency": {"urgency": 1.0, "tension": .6, "energy": .6, "engagement": .5, "boldness": .3},
    "mastery": {"mastery": 1.0, "pleasure": .5, "self_regard": .5, "control": .6, "engagement": .6,
                "clarity": .3},
    "triumph": {"triumph": 1.0, "pleasure": .7, "self_regard": .6, "control": .5, "energy": .5,
                "boldness": .4},
    "contentment": {"contentment": 1.0, "pleasure": .6, "tension": -.5, "energy": -.2,
                    "safety": .3, "hope": .2},
}
#: The part of a memory's evoked feeling that none of the standalone moods
#: named moves the mood the way the emotion its tone resembles does: a
#: remembered pleasure like joy, a remembered pain like distress.
MEMORY_TONE_EMOTION = {True: "joy", False: "distress"}
#: Where each source's feelings sit: the present -- a perceived event, the
#: character's own act -- is the surface; the past and the unsettled -- a
#: recalled memory, a standing concern -- the layer beneath.
BENEATH = frozenset({"memory", "concern"})
#: Mehrabian's octants, by the signs of pleasure, arousal and dominance (read
#: here as pleasure, the mean of energy and tension, and control).
OCTANTS = {
    (1, 1, 1): "exuberant", (-1, -1, -1): "bored", (1, 1, -1): "dependent",
    (-1, -1, 1): "disdainful", (1, -1, 1): "relaxed", (-1, 1, -1): "anxious",
    (1, -1, -1): "docile", (-1, 1, 1): "hostile",
}

# --- the owner's knobs (placeholders, none tuned) ---------------------------
#: The share of the way toward this beat's target a full-strength push moves
#: a coordinate. 2026-09-26's probe fitted about 0.2 against the characters'
#: own reports, which anchor on their previous answer.
REACTIVITY = 0.25
#: Psych units for a spectrum to halve its distance from home, and for a
#: standalone mood to halve toward nothing -- the engine's surface half-life,
#: so a unit is a turn in a clockless story and a minute of story time in a
#: clocked one.
SPECTRUM_HALF_LIFE = 8.0
STANDALONE_HALF_LIFE = 8.0
#: Bad is stronger than good (Baumeister et al., 2001): an unpleasant
#: emotion's weight in a target, and how much slower pleasure below home
#: decays. Neutral since 2026-09-26: at 1.5 and 1.5 the owner judged it "way
#: too strong", and measured on 98 captured beats the derived mood's valence
#: tracked the characters' reports at r 0.26 (The Doctor) and 0.08 (Mirelle),
#: against 0.33 and 0.11 at 1.0 and 1.0 (0.37 and 0.12 at 0.75 and 1.0).
NEGATIVITY_WEIGHT = 1.0
NEGATIVE_DECAY_FACTOR = 1.0
#: A memory-evoked feeling's weight against an event's.
MEMORY_WEIGHT = 0.5
#: A standing concern's feeling -- what is still unsettled, appraised each
#: beat (rumination) -- against an event's. Measured 2026-09-26 on 38 of The
#: Doctor's beats: concerns named the undercurrent the character reported on
#: 32 of 32 beats (events alone: 11), but every share of the surface they
#: took cost its tracking -- own-trajectory valence r 0.39 at weight 0, 0.33
#: at 0.25, 0.27 at 0.5, 0.19 at 1. So a concern is the layer BENEATH: its
#: feeling names the undercurrent and does not move the surface mood.
CONCERN_WEIGHT = 0.0
#: The weight of each source in a target.
SOURCE_WEIGHT = {"event": 1.0, "memory": MEMORY_WEIGHT, "concern": CONCERN_WEIGHT, "act": 1.0}
#: How far an act that eased the feeling returns the mood toward home, or
#: one that stoked it pushes the mood further out (affect labelling --
#: Lieberman et al., 2007 -- against venting -- Bushman, 2002).
EASE_RATE = 0.2
#: The owner's habituation: each landing adds a step; at or below the grace
#: level a recall delivers its full feeling; above it the feeling shrinks
#: toward (1 - ceiling); resting halves habituation every half-life.
HABITUATION_STEP = 0.2
HABITUATION_GRACE = 0.6
HABITUATION_CEILING = 0.8
HABITUATION_HALF_LIFE = 5.0
#: A feeling beneath -- a memory's or a concern's -- must reach this to be
#: named the undercurrent.
UNDERCURRENT_FLOOR = 0.15
#: Salience floors for `mood_profile`.
PROFILE_SPECTRUM_FLOOR = 0.3
PROFILE_STANDALONE_FLOOR = 0.25


def _clamp(x, lo=-1.0, hi=1.0):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(x):
        return 0.0
    return max(lo, min(hi, x))


def _bounds(name):
    return (0.0, 1.0) if name in STANDALONE else (-1.0, 1.0)


@dataclass
class Emotion:
    """One felt emotion: its name (a key of EMOTION_EFFECTS), how strong
    (0-1), what it is about, what stirred it -- an `event`, a `memory`, a
    standing `concern`, or the character's own `act` -- and which one."""
    name: str
    intensity: float
    about: str = ""
    source: str = "event"
    ref: str = ""

    @property
    def effects(self):
        return EMOTION_EFFECTS[self.name]

    @property
    def valence(self):
        return self.effects.get("pleasure", 0.0)


@dataclass
class Mood:
    """The mood: `coords` holds each spectrum in [-1, 1] and each standalone
    mood in [0, 1]; an absent key is neutral (0)."""
    coords: dict = field(default_factory=dict)

    def get(self, name):
        return float(self.coords.get(name, 0.0))

    def copy(self):
        return Mood(dict(self.coords))


# --- emotions from appraisals ---------------------------------------------------

def emotions_from_appraisal(appraisal, *, ref="", about=""):
    """What one perceived event stirs: each feeling the model named for it
    -- `stirs`, its distribution over OCC's event emotions and the
    standalone moods (the pack's `feel` options) -- by its share, times how
    strongly the event stirs the character (`stir` in [0, 1]). A share named
    as none of them stirs nothing. `about` is what the feelings are about.

    NAMED, NOT DERIVED (2026-09-26). Until then OCC's rules named an event's
    feelings from nine questions -- how good or bad, what it makes likely,
    what it does to a fear or a hope, whose doing, right or wrong, how much
    the character can do, each person's fortune. Against two blind raters
    on 264 events of the four test stories (`tools/jev_event_feelings.py`),
    the rules' strongest emotion shared a rater's feeling family 17% and 22%
    of the time -- 9% by chance, 44% for the raters with each other --
    because the change questions ask whether a fear grew MORE LIKELY and a
    hope came CLOSER, and the rules named a fear COME TRUE and a hope
    FULFILLED: 81 and 70 of the 264 events. Asked directly, the model's
    feeling shared the family 37% and 43%; a beat's feelings overlapped a
    rater's own strongest three 55% and 65% by family, against 58% between
    the raters; the stir strength tracked the raters' strength at r 0.74
    (0.63 between them); and the named feelings push the mood as well as the
    rules' did (spectrums r 0.44 against 0.40, standalone moods 0.46 against
    0.48, against the raters' reading of the mood)."""
    a = appraisal or {}
    return stirred(a.get("stir"), a.get("stirs"), ref=ref, about=about, source="event")


def stirred(strength, shares, *, ref="", about="", source="event", multiplier=1.0):
    """The feelings one item stirs: `strength` in [0, 1] -- how strongly it
    stirs the character, scaled by `multiplier` -- times each feeling's share
    in `shares`, the model's distribution over which it stirs. Shares on
    anything that is not a feeling (the model's "none of these") stir
    nothing."""
    total = _clamp(strength, 0.0, 1.0) * _clamp(multiplier, 0.0, 1.0)
    out = []
    for name, share in (shares or {}).items():
        i = round(total * _clamp(share, 0.0, 1.0), 4)
        if name in EMOTION_EFFECTS and i > 1e-4:
            out.append(Emotion(name, i, about, source, ref))
    return out


def emotions_from_act(appraisal, *, ref="", about=""):
    """What the character's own act, appraised after its turn, makes it feel:
    pride where the act honoured its values AND left it thinking better of
    itself, shame where it went against them or left it thinking worse, and
    frustration for what it wanted to do instead. The act's easing or
    stoking of the feeling is not an emotion; `ease` applies it.

    PRIDE NEEDS BOTH (2026-09-26, the owner: "adjust the pride tilt a
    bit"). Almost anything a principled character says honours some value
    -- "Papers, please." read 0.80 on that question, "Gauze, Captain. Hold
    it ready." 0.74 -- so with either one enough, own acts on four test
    stories read as pride 39 / 27 / 39 / 60 against shame 0 / 1 / 0 / 1 and
    pride became the label a character carried after it spoke. Such acts
    barely move what a mind thinks of itself; a praiseworthy one does. On
    the act battery (`tools/jev_act_battery.py`) ordinary acts fell from
    pride 0.66 to 0.17 while carrying a comrade under fire kept 0.85."""
    a = appraisal or {}
    against = _clamp(a.get("against_values"), 0.0, 1.0)
    honours = _clamp(a.get("honors_values"), 0.0, 1.0)
    regard = _clamp(a.get("self_regard"))
    wanted = _clamp(a.get("wanted_instead"), 0.0, 1.0)
    raw = [("pride", min(honours, max(0.0, regard)) * (1 - against), about),
           ("shame", max(against, max(0.0, -regard)), about),
           ("frustration", wanted, about)]
    return [Emotion(n, round(i, 4), obj, "act", ref) for n, i, obj in raw if i > 1e-4]


def memory_emotions(strength, tone, kinds=None, *, ref="", about="", multiplier=1.0):
    """What a recalled memory stirs, all of it scaled by `strength` in [0, 1]
    (does it stir something now) and the memory's habituation `multiplier`:
    each standalone mood the model named in `kinds` -- its distribution over
    which mood recalling it stirs most -- by its share, and the share that
    none of them covers (all of it when `kinds` was not asked) as a plain
    feeling in the direction of `tone` in [-1, 1]."""
    out = stirred(strength, kinds, ref=ref, about=about, source="memory", multiplier=multiplier)
    named = sum(_clamp(p, 0.0, 1.0) for k, p in (kinds or {}).items() if k in EMOTION_EFFECTS)
    rest = max(0.0, 1.0 - named) if kinds else 1.0
    tone = _clamp(tone)
    plain = _clamp(strength, 0.0, 1.0) * _clamp(multiplier, 0.0, 1.0) * abs(tone) * rest
    if plain > 1e-4:
        out.append(Emotion(MEMORY_TONE_EMOTION[tone >= 0], round(plain, 4), about, "memory", ref))
    return out


def concern_emotions(appraisal, weight=None, *, ref="", about=""):
    """What a standing concern -- something still unsettled, appraised each
    beat (rumination) -- stirs: the feelings named for it, as for an event,
    each scaled by how much the concern weighs on the character now
    (`weight` in [0, 1]; unasked, the concern passes whole) and tagged
    `concern`. Ungated, round two's concerns named a negative feeling on 65
    of 66 beats whose character reported none. Named directly, a concern's
    feeling shared two blind raters' family 47% and 56% of the time, against
    20% and 28% by OCC's rules and 54% between the raters (279 concerns,
    2026-09-26)."""
    w = 1.0 if weight is None else _clamp(weight, 0.0, 1.0)
    out = []
    for e in emotions_from_appraisal(appraisal, ref=ref, about=about):
        i = round(e.intensity * w, 4)
        if i > 1e-4:
            out.append(Emotion(e.name, i, e.about, "concern", ref))
    return out


# --- the mood ----------------------------------------------------------------

def decay(mood, home, dt, *, spectrum_half_life=SPECTRUM_HALF_LIFE,
          standalone_half_life=STANDALONE_HALF_LIFE, negative_factor=NEGATIVE_DECAY_FACTOR):
    """The mood after `dt` psych units with nothing new: each spectrum halves
    its distance from home every half-life (pleasure below home more
    slowly), each standalone mood halves toward nothing."""
    dt = max(0.0, float(dt or 0))
    out = mood.copy()
    if dt == 0:
        return out
    for name in set(mood.coords) | set(home.coords):
        m = mood.get(name)
        if name in STANDALONE:
            out.coords[name] = m * 0.5 ** (dt / max(1e-6, standalone_half_life))
            continue
        h = home.get(name)
        hl = spectrum_half_life * (negative_factor if name == "pleasure" and m < h else 1.0)
        out.coords[name] = h + (m - h) * 0.5 ** (dt / max(1e-6, hl))
    return out


def targets(emotions, *, negativity=NEGATIVITY_WEIGHT, weights=None):
    """Per coordinate this beat's emotions touch: the target -- the weighted
    average of their values on it, weight = intensity x the source's weight x
    `negativity` where the emotion is unpleasant -- and the push strength,
    1 - prod(1 - i x source weight), which grows with every emotion that
    touches the coordinate and never passes 1."""
    weights = {**SOURCE_WEIGHT, **(weights or {})}
    acc, rest = {}, {}
    for e in emotions:
        scale = weights.get(e.source, 1.0)
        w = e.intensity * scale * (negativity if e.valence < 0 else 1.0)
        if w <= 0:
            continue
        for name, value in e.effects.items():
            total, weighted = acc.get(name, (0.0, 0.0))
            acc[name] = (total + w, weighted + w * value)
            rest[name] = rest.get(name, 1.0) * (1.0 - min(1.0, e.intensity * scale))
    return {name: (weighted / total, 1.0 - rest[name]) for name, (total, weighted) in acc.items()}


def mix(mood, home, emotions, dt, *, reactivity=REACTIVITY, negativity=NEGATIVITY_WEIGHT,
        weights=None, spectrum_half_life=SPECTRUM_HALF_LIFE,
        standalone_half_life=STANDALONE_HALF_LIFE, negative_factor=NEGATIVE_DECAY_FACTOR):
    """One beat: decay over `dt`, then move each coordinate the beat's
    emotions touch toward its target by `reactivity` x its push strength.
    Returns the new mood and the targets."""
    moved = decay(mood, home, dt, spectrum_half_life=spectrum_half_life,
                  standalone_half_life=standalone_half_life, negative_factor=negative_factor)
    goals = targets(emotions, negativity=negativity, weights=weights)
    k = _clamp(reactivity, 0.0, 1.0)
    for name, (target, strength) in goals.items():
        lo, hi = _bounds(name)
        m = moved.get(name)
        moved.coords[name] = _clamp(m + k * strength * (target - m), lo, hi)
    return moved, goals


def settle(mood, reading, *, reactivity=REACTIVITY):
    """Move the mood toward the decision model's direct reading of it
    (`{coordinate: value}`, the shape `affect_appraisal.read` gives under
    `spectrums` and `moods`) by `reactivity`."""
    out = mood.copy()
    k = _clamp(reactivity, 0.0, 1.0)
    for name, value in (reading or {}).items():
        lo, hi = _bounds(name)
        m = out.get(name)
        out.coords[name] = _clamp(m + k * (_clamp(value, lo, hi) - m), lo, hi)
    return out


def ease(mood, home, eased_or_stoked, *, rate=EASE_RATE):
    """An act that eased the feeling (negative) returns the mood toward home
    by |value| x rate; one that stoked it (positive) pushes each coordinate
    further from home by value x rate."""
    e = _clamp(eased_or_stoked)
    out = mood.copy()
    for name in list(out.coords):
        lo, hi = _bounds(name)
        h = 0.0 if name in STANDALONE else home.get(name)
        m = out.get(name)
        step = rate * abs(e)
        out.coords[name] = _clamp(m + step * ((h - m) if e < 0 else (m - h)), lo, hi)
    return out


# --- habituation of a memory's evoked feeling ---------------------------------

def habituation_after(h, dt, *, half_life=HABITUATION_HALF_LIFE):
    """A memory's habituation after `dt` psych units of rest."""
    return _clamp(h, 0.0, 1.0) * 0.5 ** (max(0.0, float(dt or 0)) / max(1e-6, half_life))


def habituation_multiplier(h, *, grace=HABITUATION_GRACE, ceiling=HABITUATION_CEILING):
    """How much of its feeling a memory delivers at habituation `h`: all of it
    at or below the grace level, shrinking toward (1 - ceiling) above it."""
    h = _clamp(h, 0.0, 1.0)
    if h <= grace:
        return 1.0
    return 1.0 - _clamp(ceiling, 0.0, 1.0) * (h - grace) / max(1e-6, 1.0 - grace)


def recall_lands(state, memory_id, now, *, step=HABITUATION_STEP, half_life=HABITUATION_HALF_LIFE,
                 grace=HABITUATION_GRACE, ceiling=HABITUATION_CEILING):
    """A recall of `memory_id` lands at psych time `now`: rest since its last
    landing drains habituation, this landing adds a step, and the multiplier
    for this recall's feeling is read at the new level. Returns (multiplier,
    new state); `state` maps memory id to {"h", "at"} and is not mutated."""
    state = dict(state or {})
    prior = state.get(str(memory_id)) or {}
    h = habituation_after(prior.get("h", 0.0), float(now) - float(prior.get("at", now)),
                          half_life=half_life)
    h = min(1.0, h + step)
    state[str(memory_id)] = {"h": round(h, 4), "at": float(now)}
    return habituation_multiplier(h, grace=grace, ceiling=ceiling), state


def rehabituate(state, memory_id):
    """New information about a memory -- a reinterpretation, a new event of
    the same kind -- resets its habituation at once."""
    state = dict(state or {})
    state.pop(str(memory_id), None)
    return state


# --- names ---------------------------------------------------------------------

def mood_profile(mood, *, top=4):
    """The mood's most salient parts, most salient first: standalone moods at
    or above PROFILE_STANDALONE_FLOOR and spectrums at least
    PROFILE_SPECTRUM_FLOOR from neutral, as (name, value) -- keys the
    language pack words."""
    parts = [(n, mood.get(n), mood.get(n)) for n in STANDALONE if mood.get(n) >= PROFILE_STANDALONE_FLOOR]
    parts += [(n, mood.get(n), abs(mood.get(n))) for n in SPECTRUMS
              if abs(mood.get(n)) >= PROFILE_SPECTRUM_FLOOR]
    return [(n, round(v, 3)) for n, v, _s in sorted(parts, key=lambda t: -t[2])[:top]]


def mood_name(mood):
    """Mehrabian's octant, read from pleasure, the mean of energy and tension,
    and control -- a compact label for logs and traces."""
    arousal = (mood.get("energy") + mood.get("tension")) / 2
    signs = tuple(1 if x >= 0 else -1 for x in (mood.get("pleasure"), arousal, mood.get("control")))
    return OCTANTS[signs]


def surface_and_undercurrent(emotions, mood):
    """The surface: the strongest feeling the present stirred -- a perceived
    event or the character's own act -- else the strongest felt at all. The
    undercurrent: the strongest feeling the past or the unsettled stirred --
    a recalled memory, a standing concern (`BENEATH`) -- that reaches
    UNDERCURRENT_FLOOR; where nothing beneath does, the strongest other
    feeling of the opposite pleasure sign, or the mood's most salient part
    when its pleasure disagrees with the surface's. Either may be None."""
    felt = sorted((e for e in emotions if e.intensity > 0), key=lambda e: -e.intensity)
    if not felt:
        return None, None
    present = [e for e in felt if e.source not in BENEATH]
    surface = present[0] if present else felt[0]
    beneath = next((e for e in felt if e.source in BENEATH and e is not surface
                    and e.intensity >= UNDERCURRENT_FLOOR), None)
    if beneath is not None:
        return surface, beneath
    positive = surface.valence >= 0
    other = next((e for e in felt if e is not surface and (e.valence >= 0) != positive), None)
    if other is not None:
        return surface, other
    if (mood.get("pleasure") >= 0) != positive and abs(mood.get("pleasure")) > 0.1:
        profile = mood_profile(mood, top=1)
        return surface, (profile[0][0] if profile else None)
    return surface, None


def engine_affect(mood):
    """The mood on the engine's affect scales: valence in [-1, 1] is the
    pleasure coordinate; arousal in [0, 1] the mean of energy and tension."""
    arousal = (mood.get("energy") + mood.get("tension")) / 2
    return {"valence": round(mood.get("pleasure"), 4), "arousal": round((arousal + 1.0) / 2.0, 4)}
