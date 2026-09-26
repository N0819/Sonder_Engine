"""Emotion and mood as arithmetic: what a beat's events, memories and the
character's own acts make it feel, and the mood those feelings average into.

Designed with the owner on 2026-09-26 (`docs/design/DESIGN_JEV_CHARACTER_PASS.md`,
"Emotion and mood" and "The mood math"). The decision model appraises
(`mind/affect_appraisal.py`); this module is the code half and holds no model.

- **Emotions** from appraisals by the OCC rules (Ortony, Clore and Collins,
  "The Cognitive Structure of Emotions", 1988), each with its object -- who
  or what it is about -- and OCC's compounds formed where both halves are
  present (gratitude, anger, gratification, remorse). The character's own
  acts, appraised after its turn, add pride, shame and the cost of restraint.
- **Mood as a high-dimensional object** (the owner: "spectrums of moods as
  coordinates as well as some moods that truly stand as their own"): twelve
  bipolar spectrum coordinates in [-1, 1] and eleven standalone moods in
  [0, 1], named by the language pack. Each emotion pushes the coordinates it
  moves (`EMOTION_EFFECTS`); a beat's emotions average into a target per
  coordinate, and the mood moves part of the way toward it -- the shape
  measured to beat carrying the previous mood alone. Between beats spectrums
  decay toward home and standalone moods fade. The decision model's direct
  reading of the mood can settle it too (`settle`).
- **Habituation** of a memory's evoked feeling, the owner's model: full for a
  few recalls, less after, full again after a rest.

NOT WIRED. Nothing in the turn calls this yet. Every knob below, and every
number in `EMOTION_EFFECTS`, is the owner's to set; the values are
placeholders.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: The mood's bipolar coordinates and its standalone moods -- the keys the
#: language pack's `affect_appraisal.options.dimensions` and `.standalone`
#: name. Grounded in the validated mood inventories: the Profile of Mood
#: States, PANAS-X, Matthews' UWIST (energetic apart from tense arousal) and
#: Fontaine et al. 2007 (valence, power, arousal, novelty); the standalone
#: moods are categories Cowen and Keltner (2017) found self-report keeps
#: distinct.
SPECTRUMS = ("pleasure", "energy", "tension", "control", "clarity", "connection", "openness",
             "playfulness", "hope", "self_regard", "safety", "engagement")
STANDALONE = ("desire", "awe", "nostalgia", "grief", "disgust", "jealousy", "guilt", "tenderness",
              "amusement", "anger", "compassion")

#: How each emotion moves the mood: a value per coordinate it touches
#: (spectrums in [-1, 1], standalone moods in [0, 1]). The OCC emotions, plus
#: the engine's own `desire` (OCC has none) and `frustration` (the cost of a
#: restraint the character's own act paid). Hand-set, coarse, the owner's.
EMOTION_EFFECTS = {
    "joy": {"pleasure": .8, "energy": .4, "tension": -.3, "hope": .3, "playfulness": .3,
            "engagement": .3, "amusement": .3},
    "distress": {"pleasure": -.7, "tension": .4, "control": -.3, "hope": -.3, "energy": -.2},
    "hope": {"pleasure": .4, "hope": .8, "energy": .3, "engagement": .3},
    "fear": {"pleasure": -.6, "tension": .8, "safety": -.8, "control": -.5, "energy": .3,
             "openness": -.3},
    "satisfaction": {"pleasure": .6, "tension": -.4, "hope": .3, "control": .3},
    "disappointment": {"pleasure": -.5, "hope": -.5, "energy": -.3},
    "relief": {"pleasure": .5, "tension": -.6, "safety": .5},
    "fears_confirmed": {"pleasure": -.6, "safety": -.6, "hope": -.6, "tension": .5, "control": -.5},
    "pride": {"pleasure": .5, "self_regard": .8, "control": .4, "energy": .3},
    "shame": {"pleasure": -.5, "self_regard": -.8, "openness": -.4, "control": -.3, "guilt": .4},
    "admiration": {"pleasure": .4, "connection": .4, "openness": .4, "engagement": .3, "awe": .3},
    "reproach": {"pleasure": -.3, "openness": -.3, "connection": -.3, "anger": .5},
    "gratitude": {"pleasure": .5, "connection": .6, "openness": .5, "tenderness": .3},
    "anger": {"pleasure": -.6, "tension": .6, "energy": .5, "control": .3, "openness": -.4, "anger": 1.0},
    "gratification": {"pleasure": .7, "self_regard": .6, "control": .4, "energy": .4},
    "remorse": {"pleasure": -.5, "self_regard": -.7, "hope": -.3, "energy": -.3, "guilt": .8},
    "happy_for": {"pleasure": .5, "connection": .5, "openness": .4, "tenderness": .3},
    "pity": {"pleasure": -.3, "connection": .3, "compassion": .8},
    "resentment": {"pleasure": -.4, "connection": -.4, "openness": -.3, "anger": .4, "jealousy": .5},
    "gloating": {"pleasure": .4, "self_regard": .3, "connection": -.3, "amusement": .3},
    "desire": {"desire": 1.0, "energy": .5, "pleasure": .3, "engagement": .4, "tension": .2},
    "frustration": {"pleasure": -.4, "tension": .5, "control": -.3},
}
#: A memory's evoked feeling moves the mood the way the emotion its tone
#: resembles does: a remembered pleasure like joy, a remembered pain like
#: distress.
MEMORY_TONE_EMOTION = {True: "joy", False: "distress"}
#: OCC's compounds, formed within one event where both halves are present.
COMPOUNDS = {
    ("admiration", "joy"): "gratitude", ("reproach", "distress"): "anger",
    ("pride", "joy"): "gratification", ("shame", "distress"): "remorse",
}
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
#: Both halves of a compound must reach this before it forms.
COMPOUND_FLOOR = 0.15
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

def emotions_from_appraisal(appraisal, *, ref="", actor="", about="", liking=None):
    """OCC's rules over one perceived event's appraisal (the shape
    `affect_appraisal.read` returns): its consequence for the character now
    (joy, distress) and ahead (hope, fear -- a threat one cannot master is
    more frightening); what it does to a fear (relief, fears confirmed) or a
    hope (satisfaction, disappointment); the act of whoever did it (pride,
    shame, admiration, reproach); its consequences for people the character
    has a standing with (happy-for, pity, resentment, gloating); desire --
    then the compounds.

    `liking` maps each person's name to the character's liking of them in
    [-1, 1]; `actor` names the event's agent when it had one; `about` is what
    the event-directed emotions are about."""
    a = appraisal or {}
    d = _clamp(a.get("desirability"))
    ahead = _clamp(a.get("ahead"))
    fear_change = _clamp(a.get("fear_change"))
    hope_change = _clamp(a.get("hope_change"))
    control = _clamp(a.get("control", 0.5), 0.0, 1.0)
    standards = _clamp(a.get("standards"))
    doer = a.get("doer") or {}
    raw = [
        ("joy", max(0.0, d), about), ("distress", max(0.0, -d), about),
        ("hope", max(0.0, ahead), about),
        ("fear", max(0.0, -ahead) * (1 - 0.5 * control), about),
        ("relief", max(0.0, -fear_change), about), ("fears_confirmed", max(0.0, fear_change), about),
        ("satisfaction", max(0.0, hope_change), about),
        ("disappointment", max(0.0, -hope_change), about),
    ]
    me = _clamp(doer.get("self"), 0.0, 1.0)
    other = _clamp(doer.get("actor", 0.0), 0.0, 1.0) + _clamp(doer.get("other", 0.0), 0.0, 1.0)
    praise, blame = max(0.0, standards), max(0.0, -standards)
    who = actor or "someone"
    raw += [("pride", me * praise, about), ("shame", me * blame, about),
            ("admiration", min(1.0, other) * praise, who), ("reproach", min(1.0, other) * blame, who)]
    for person, fortune in (a.get("fortune") or {}).items():
        f = _clamp(fortune)
        like = _clamp((liking or {}).get(person, 0.0))
        raw += [("happy_for", max(0.0, f) * max(0.0, like), person),
                ("pity", max(0.0, -f) * max(0.0, like), person),
                ("resentment", max(0.0, f) * max(0.0, -like), person),
                ("gloating", max(0.0, -f) * max(0.0, -like), person)]
    raw.append(("desire", _clamp(a.get("desire"), 0.0, 1.0), about))
    emotions = [Emotion(n, round(i, 4), obj, "event", ref) for n, i, obj in raw if i > 1e-4]
    return form_compounds(emotions)


def emotions_from_act(appraisal, *, ref="", about=""):
    """What the character's own act, appraised after its turn, makes it feel:
    pride where the act honoured its values or left it thinking better of
    itself, shame where it went against them or left it thinking worse, and
    frustration for what it wanted to do instead. The act's easing or
    stoking of the feeling is not an emotion; `ease` applies it."""
    a = appraisal or {}
    against = _clamp(a.get("against_values"), 0.0, 1.0)
    honours = _clamp(a.get("honors_values"), 0.0, 1.0)
    regard = _clamp(a.get("self_regard"))
    wanted = _clamp(a.get("wanted_instead"), 0.0, 1.0)
    raw = [("pride", max(honours, max(0.0, regard)) * (1 - against), about),
           ("shame", max(against, max(0.0, -regard)), about),
           ("frustration", wanted, about)]
    return [Emotion(n, round(i, 4), obj, "act", ref) for n, i, obj in raw if i > 1e-4]


def form_compounds(emotions):
    """OCC's compounds, within one event: where both halves reach
    COMPOUND_FLOOR, the compound takes their geometric mean and each half
    keeps only what the compound did not absorb -- so the mood is not pushed
    twice by one feeling. A compound is about the agent where one half is
    (gratitude and anger are toward someone), else about the event."""
    by_ref = {}
    for e in emotions:
        by_ref.setdefault(e.ref, {})[e.name] = e
    out = list(emotions)
    for (first, second), name in COMPOUNDS.items():
        for ref, named in by_ref.items():
            a, b = named.get(first), named.get(second)
            if not a or not b or min(a.intensity, b.intensity) < COMPOUND_FLOOR:
                continue
            strength = round(math.sqrt(a.intensity * b.intensity), 4)
            a.intensity = round(max(0.0, a.intensity - strength), 4)
            b.intensity = round(max(0.0, b.intensity - strength), 4)
            about = a.about if first in ("admiration", "reproach") else b.about
            out.append(Emotion(name, strength, about, "event", ref))
    return [e for e in out if e.intensity > 1e-4]


def memory_emotion(strength, tone, *, ref="", about="", multiplier=1.0):
    """The feeling a recalled memory stirs: `strength` in [0, 1] (does it stir
    something now), `tone` in [-1, 1] (pleasant or not), scaled by the
    memory's habituation multiplier. None when nothing is stirred."""
    tone = _clamp(tone)
    intensity = _clamp(strength, 0.0, 1.0) * abs(tone) * _clamp(multiplier, 0.0, 1.0)
    if intensity <= 1e-4:
        return None
    return Emotion(MEMORY_TONE_EMOTION[tone >= 0], round(intensity, 4), about, "memory", ref)


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
    """The strongest emotion of the beat, and beneath it the strongest one of
    the other pleasure sign -- or, where none was felt, the mood's most
    salient part when its pleasure disagrees with the surface's. Either may
    be None."""
    felt = sorted((e for e in emotions if e.intensity > 0), key=lambda e: -e.intensity)
    surface = felt[0] if felt else None
    if surface is None:
        return None, None
    positive = surface.valence >= 0
    other = next((e for e in felt[1:] if (e.valence >= 0) != positive), None)
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
