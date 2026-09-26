"""Emotion and mood as arithmetic: what a beat's events and memories make a
character feel, and the mood those feelings average into.

Designed with the owner on 2026-09-26 (`docs/design/DESIGN_JEV_CHARACTER_PASS.md`,
"Emotion and mood" and "The mood math"). The decision model appraises each
event a character perceived (`mind/affect_appraisal.py`); this module is the
code half, and holds no model:

- **Emotions** from appraisals by the OCC rules (Ortony, Clore and Collins,
  "The Cognitive Structure of Emotions", 1988), each with its object -- who
  or what it is about -- and OCC's compounds formed where both halves are
  present: gratitude, anger, gratification, remorse.
- **Mood** as a point in pleasure-arousal-dominance space (Mehrabian's PAD),
  moved the way ALMA moves it (Gebhard, "A Layered Model of Affect", 2005):
  this beat's emotions average into a centre, the mood moves part of the way
  toward it, and between beats it decays toward the character's home.
- **Habituation** of a memory's evoked feeling, the owner's model: "a
  character recalls a pleasant memory and gets a mood boost from it for a few
  turns of recalling before habituation reduces that effect. but that same
  memory if evoked some... number of turns later can once again deliver that
  pleasantness."

NOT WIRED. Nothing in the turn calls this yet. Every knob below is the
owner's to set; the values are placeholders, not tuned ones.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: OCC emotions as directions in PAD space: ALMA's table (Gebhard 2005,
#: table 1), plus one row of the engine's own -- `desire`, which OCC does not
#: have and the engine's scope needs.
EMOTION_PAD = {
    "admiration": (0.5, 0.3, -0.2), "anger": (-0.51, 0.59, 0.25), "disappointment": (-0.3, 0.1, -0.4),
    "distress": (-0.4, -0.2, -0.5), "fear": (-0.64, 0.6, -0.43), "fears_confirmed": (-0.5, -0.3, -0.7),
    "gloating": (0.3, -0.3, -0.1), "gratification": (0.6, 0.5, 0.4), "gratitude": (0.4, 0.2, -0.3),
    "happy_for": (0.4, 0.2, 0.2), "hope": (0.2, 0.2, -0.1), "joy": (0.4, 0.2, 0.1),
    "pity": (-0.4, -0.2, -0.5), "pride": (0.4, 0.3, 0.3), "relief": (0.2, -0.3, 0.4),
    "remorse": (-0.3, 0.1, -0.6), "reproach": (-0.3, -0.1, 0.4), "resentment": (-0.2, -0.3, -0.2),
    "satisfaction": (0.3, -0.2, 0.4), "shame": (-0.3, 0.1, -0.6),
    "desire": (0.4, 0.6, 0.1),
}
#: A memory's evoked feeling takes the direction of the OCC emotion its tone
#: resembles: a remembered pleasure feels like joy, a remembered pain like
#: distress.
MEMORY_TONE_EMOTION = {True: "joy", False: "distress"}
#: OCC's compounds, formed within one event where both halves are present.
COMPOUNDS = {
    ("admiration", "joy"): "gratitude", ("reproach", "distress"): "anger",
    ("pride", "joy"): "gratification", ("shame", "distress"): "remorse",
}
#: Mehrabian's octants, by the signs of pleasure, arousal and dominance.
OCTANTS = {
    (1, 1, 1): "exuberant", (-1, -1, -1): "bored", (1, 1, -1): "dependent",
    (-1, -1, 1): "disdainful", (1, -1, 1): "relaxed", (-1, 1, -1): "anxious",
    (1, -1, -1): "docile", (-1, 1, 1): "hostile",
}

# --- the owner's knobs (placeholders, none tuned) ---------------------------
#: The share of the way toward this beat's emotional centre a full-strength
#: push moves the mood. 2026-09-26's probe fitted about 0.2 against the
#: characters' own reports, which anchor on their previous answer.
REACTIVITY = 0.25
#: Psych units for the mood to halve its distance from home -- the engine's
#: surface half-life, so one unit is a turn in a clockless story and a minute
#: of story time in a clocked one.
MOOD_HALF_LIFE = 8.0
#: Bad is stronger than good (Baumeister et al., 2001): a negative emotion's
#: weight in the centre, and how much slower pleasure below home decays.
NEGATIVITY_WEIGHT = 1.5
NEGATIVE_DECAY_FACTOR = 1.5
#: A memory-evoked feeling's weight against an event's.
MEMORY_WEIGHT = 0.5
#: The owner's habituation: each landing adds a step; at or below the grace
#: level a recall delivers its full feeling; above it the feeling shrinks
#: toward (1 - ceiling); resting halves habituation every half-life.
HABITUATION_STEP = 0.2
HABITUATION_GRACE = 0.6
HABITUATION_CEILING = 0.8
HABITUATION_HALF_LIFE = 5.0
#: Both halves of a compound must reach this before it forms.
COMPOUND_FLOOR = 0.15
#: Mood intensity words by the PAD vector's length.
INTENSITY_WORDS = ((0.4, "slightly"), (0.8, "moderately"), (float("inf"), "fully"))


def _clamp(x, lo=-1.0, hi=1.0):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(x):
        return 0.0
    return max(lo, min(hi, x))


@dataclass
class Emotion:
    """One felt emotion: its OCC name, how strong (0-1), what it is about,
    whether an event or a memory stirred it, and which one."""
    name: str
    intensity: float
    about: str = ""
    source: str = "event"
    ref: str = ""

    @property
    def pad(self):
        return EMOTION_PAD[self.name]


@dataclass
class Mood:
    """A point in pleasure-arousal-dominance space, each axis in [-1, 1]."""
    p: float = 0.0
    a: float = 0.0
    d: float = 0.0

    def vector(self):
        return (self.p, self.a, self.d)

    @classmethod
    def of(cls, vector):
        p, a, d = (_clamp(x) for x in vector)
        return cls(p, a, d)


# --- emotions from one event's appraisal -------------------------------------

def emotions_from_appraisal(appraisal, *, ref="", actor="", about="", liking=None):
    """OCC's rules over one event's appraisal (the shape
    `affect_appraisal.read` returns): consequences of the event for the
    character (joy, distress, hope, fear, and the confirmation four), the
    action of whoever brought it about (pride, shame, admiration, reproach),
    and its consequences for people the character has a standing with
    (happy-for, pity, resentment, gloating) -- then the compounds.

    `liking` maps each person's name to the character's liking of them in
    [-1, 1]; `actor` names who the event's agent was, when it had one;
    `about` is what the event-directed emotions are about.
    """
    a = appraisal or {}
    d = _clamp(a.get("desirability"))
    happened = _clamp(a.get("happened", 1.0), 0.0, 1.0)
    likely = _clamp(a.get("likelihood", 0.0), 0.0, 1.0)
    control = _clamp(a.get("control", 0.5), 0.0, 1.0)
    standards = _clamp(a.get("standards"))
    confirmation = a.get("confirmation") or {}
    agency = a.get("agency") or {}
    raw = []
    good, bad = max(0.0, d), max(0.0, -d)
    raw.append(("joy", happened * good, about))
    raw.append(("distress", happened * bad, about))
    raw.append(("hope", (1 - happened) * likely * good, about))
    # Low control makes a threatened harm more frightening (Lazarus's core
    # relational themes: fear is uncertain threat one cannot master).
    raw.append(("fear", (1 - happened) * likely * bad * (1 - 0.5 * control), about))
    stake = abs(d)
    for key, name in (("confirms_hope", "satisfaction"), ("dashes_hope", "disappointment"),
                      ("confirms_fear", "fears_confirmed"), ("averts_fear", "relief")):
        raw.append((name, _clamp(confirmation.get(key), 0.0, 1.0) * stake, about))
    me, other = _clamp(agency.get("self"), 0.0, 1.0), _clamp(agency.get("other"), 0.0, 1.0)
    praise, blame = max(0.0, standards), max(0.0, -standards)
    raw.append(("pride", me * praise, about))
    raw.append(("shame", me * blame, about))
    who = actor or "someone"
    raw.append(("admiration", other * praise, who))
    raw.append(("reproach", other * blame, who))
    for person, fortune in (a.get("fortune") or {}).items():
        f = _clamp(fortune)
        like = _clamp((liking or {}).get(person, 0.0))
        raw.append(("happy_for", max(0.0, f) * max(0.0, like), person))
        raw.append(("pity", max(0.0, -f) * max(0.0, like), person))
        raw.append(("resentment", max(0.0, f) * max(0.0, -like), person))
        raw.append(("gloating", max(0.0, -f) * max(0.0, -like), person))
    raw.append(("desire", _clamp(a.get("desire"), 0.0, 1.0), about))
    emotions = [Emotion(n, round(i, 4), obj, "event", ref) for n, i, obj in raw if i > 1e-4]
    return form_compounds(emotions)


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

def decay(mood, home, dt, *, half_life=MOOD_HALF_LIFE, negative_factor=NEGATIVE_DECAY_FACTOR):
    """The mood after `dt` psych units with nothing new: each axis halves its
    distance from home every half-life, pleasure below home more slowly."""
    dt = max(0.0, float(dt or 0))
    if dt == 0:
        return Mood.of(mood.vector())
    out = []
    for axis, (m, h) in enumerate(zip(mood.vector(), home.vector())):
        hl = half_life * (negative_factor if axis == 0 and m < h else 1.0)
        out.append(h + (m - h) * 0.5 ** (dt / max(1e-6, hl)))
    return Mood.of(out)


def centre(emotions, *, negativity=NEGATIVITY_WEIGHT, memory_weight=MEMORY_WEIGHT):
    """This beat's emotional centre and push strength: the weighted average
    of the emotions' directions -- weight = intensity, times `negativity`
    where the emotion is unpleasant, times `memory_weight` where a memory
    stirred it -- and the strength of their joint push, 1 - prod(1 - i),
    which grows with every emotion and never passes 1. (None, 0) when no
    emotion is felt."""
    total, acc, rest = 0.0, [0.0, 0.0, 0.0], 1.0
    for e in emotions:
        scale = memory_weight if e.source == "memory" else 1.0
        w = e.intensity * scale * (negativity if e.pad[0] < 0 else 1.0)
        if w <= 0:
            continue
        total += w
        for k in range(3):
            acc[k] += w * e.pad[k]
        rest *= 1.0 - min(1.0, e.intensity * scale)
    if total <= 0:
        return None, 0.0
    return tuple(x / total for x in acc), 1.0 - rest


def mix(mood, home, emotions, dt, *, reactivity=REACTIVITY, half_life=MOOD_HALF_LIFE,
        negativity=NEGATIVITY_WEIGHT, negative_factor=NEGATIVE_DECAY_FACTOR,
        memory_weight=MEMORY_WEIGHT):
    """One beat: decay toward home over `dt`, then move toward this beat's
    centre by `reactivity` times the push strength. Returns the new mood and
    a trace of the centre and strength."""
    moved = decay(mood, home, dt, half_life=half_life, negative_factor=negative_factor)
    c, strength = centre(emotions, negativity=negativity, memory_weight=memory_weight)
    if c is not None:
        step = _clamp(reactivity, 0.0, 1.0) * strength
        moved = Mood.of(tuple(m + step * (ci - m) for m, ci in zip(moved.vector(), c)))
    return moved, {"centre": c, "strength": round(strength, 4)}


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

def mood_name(mood):
    """Mehrabian's octant with an intensity word: 'moderately relaxed'."""
    signs = tuple(1 if x >= 0 else -1 for x in mood.vector())
    length = math.sqrt(sum(x * x for x in mood.vector()))
    word = next(w for limit, w in INTENSITY_WORDS if length < limit)
    return f"{word} {OCTANTS[signs]}"


def surface_and_undercurrent(emotions, mood):
    """The strongest emotion of the beat, and beneath it the strongest one of
    the other pleasure sign -- or, where none was felt, the mood itself when
    its pleasure disagrees with the surface's. Either may be None."""
    felt = sorted((e for e in emotions if e.intensity > 0), key=lambda e: -e.intensity)
    surface = felt[0] if felt else None
    if surface is None:
        return None, None
    positive = surface.pad[0] >= 0
    other = next((e for e in felt[1:] if (e.pad[0] >= 0) != positive), None)
    if other is not None:
        return surface, other
    if (mood.p >= 0) != positive and abs(mood.p) > 0.1:
        return surface, mood_name(mood)
    return surface, None


def engine_affect(mood):
    """The mood on the engine's affect scales: valence in [-1, 1], arousal in
    [0, 1] (the `surface` shape `mind.affect` persists)."""
    return {"valence": round(mood.p, 4), "arousal": round((mood.a + 1.0) / 2.0, 4)}
