"""The character's mood, computed by the engine and given to it.

The owner, 2026-09-26: "we should remove all mood related machinery from the
character prompt. and just have it fed to the character in it's packet. And
have it update the moods again post character actions."
(`docs/design/DESIGN_JEV_CHARACTER_PASS.md`, "Wiring the affect pass".)

- **Before a character call** (`before_call`): the mood the character carries
  decays over the psych units since it was last touched; the decision model
  appraises what this character legitimately holds -- its own card, this
  call's perception, its recalled memories, its concerns, its people -- in one
  request (the state is built only from this character's own payload, so no
  other mind shares its context); `affect_mix` turns the appraisals into
  emotions, mixes them into the mood and settles it toward the model's direct
  reading.
- **After the call** (`after_call`): the character's own speech, actions and
  held-back want are appraised; pride, shame, frustration, and whether the act
  eased or stoked the feeling, move the mood.
- `given_affect` renders the mood in the engine's `active_state.affect` shape
  -- the field commit's `affect.resolve_affect` reads -- so every reader of
  the character's affect now reads the engine's mood where it read the
  model's report; `feelings_block` renders it for the packet; `persisted` is
  what the character's state keeps (`mood_coords`, `mood_habits`,
  `mood_clock`).

FAILS OPEN: when the decision model cannot be asked, the carried mood stands,
decayed, and the reason travels with it -- a turn never waits on a mood.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llm.prompts import affect_appraisal_options
from mind import affect_appraisal as appraisal
from mind import affect_mix as mix

#: How much the decision model is asked about in one call, and how much of
#: the mood the packet names. Named so they can be read and changed, not
#: buried: every one is the owner's.
MAX_EVENTS = 8
MAX_PEOPLE = 3
MAX_MEMORIES = 8
MAX_CONCERNS = 4
MOOD_WORDS = 4
#: How long an object may run in a feeling's label before it is cut.
ABOUT_CHARS = 60


@dataclass
class Felt:
    """The mood around one character call: carried in, moved by what the call
    brought, then by what the character did."""
    mood: mix.Mood
    home: mix.Mood
    habits: dict = field(default_factory=dict)
    clock: float = 0.0
    emotions: list = field(default_factory=list)
    state_text: str = ""
    people: list = field(default_factory=list)
    language: str | None = None
    asked: bool = False
    note: str = ""

    def parts(self):
        """The surface and the undercurrent of what was felt."""
        return mix.surface_and_undercurrent(self.emotions, self.mood)


# --- the carried mood ----------------------------------------------------------

def home_mood(baseline):
    """Temperament as a point in the mood: the card's resting valence as
    pleasure, its resting arousal (0-1) as energy and tension."""
    b = baseline or {}
    valence = mix._clamp(b.get("valence"))
    arousal = mix._clamp(b.get("arousal", 0.5), 0.0, 1.0) * 2.0 - 1.0
    return mix.Mood({"pleasure": valence, "energy": arousal, "tension": arousal})


def carried(active, baseline, units, earlier=None):
    """The mood this call starts from: an earlier round's this beat, as it
    left it (`earlier`, that round's `persisted` form -- no time has passed);
    else the stored one, decayed over `units` psych units toward home; else
    home. Returns (mood, home, habits, clock)."""
    home = home_mood(baseline)
    if isinstance(earlier, dict) and isinstance(earlier.get("mood_coords"), dict):
        return (mix.Mood({k: float(v) for k, v in earlier["mood_coords"].items()}), home,
                dict(earlier.get("mood_habits") or {}), float(earlier.get("mood_clock") or 0.0))
    active = active or {}
    coords = active.get("mood_coords")
    clock = float(active.get("mood_clock") or 0.0) + max(0.0, float(units or 0.0))
    habits = dict(active.get("mood_habits") or {})
    if not isinstance(coords, dict) or not coords:
        return home.copy(), home, habits, clock
    mood = mix.decay(mix.Mood({k: float(v) for k, v in coords.items()}), home, units)
    return mood, home, habits, clock


def persisted(felt):
    """What the character's state keeps between calls."""
    return {"mood_coords": {k: round(float(v), 4) for k, v in felt.mood.coords.items() if abs(float(v)) > 1e-4},
            "mood_habits": felt.habits, "mood_clock": round(felt.clock, 4)}


# --- what the decision model reads: this character's own payload only ----------

def _text(value, n=300):
    text = " ".join(str(value or "").split())
    return text if len(text) <= n else text[:n] + "..."


def _own_act(observation):
    """A mind's own conduct handed back to it by a later round of its beat
    (`loops.self_micro_view`): its id names the same body as perceiver and
    as speaker (`current:<me>:micro:<round>:<me>:<n>`). Its feeling was
    appraised once, after it acted (`after_call`); read again as a perceived
    event it counted twice, and a magistrate's second round in the lie test
    story was handed "gratification (You said: ...)" as how he felt NOW
    (2026-09-26)."""
    parts = str(observation.get("observation_id") or "").split(":")
    return len(parts) >= 6 and parts[0] == "current" and parts[2] == "micro" \
        and parts[1] == parts[4]


def events_from(observations):
    """This call's perceived events, as the model will quote them -- what
    the world and the others did, never the mind's own earlier conduct."""
    rows = [o for o in (observations or []) if isinstance(o, dict) and not _own_act(o)]
    rows.sort(key=lambda o: o.get("order") or 0)
    out = []
    for i, o in enumerate(rows):
        text = (o.get("observed") or {}).get("text") if isinstance(o.get("observed"), dict) else o.get("text")
        if o.get("standing") or not str(text or "").strip():
            continue
        out.append({"ref": str(o.get("observation_id") or f"o{i}"), "text": _text(text),
                    "actor": str(o.get("actor") or "")})
    return out[:MAX_EVENTS]


def memories_from(memory_context):
    """The memories recall delivered to this call."""
    out = []
    for i, m in enumerate((memory_context or {}).get("recalled_old_memories") or []):
        if not isinstance(m, dict):
            continue
        text = m.get("details") or m.get("gist") or m.get("text")
        if str(text or "").strip():
            key = str(m.get("event_key") or m.get("memory_ref") or m.get("id") or "")
            # `keyed` gates habituation: a row with no stable key is named by
            # its place in this packet, and a place is not a memory -- keying
            # habits by it would tire whichever row lands there next.
            out.append({"ref": key or f"m{i}", "keyed": bool(key), "text": _text(text)})
    return out[:MAX_MEMORIES]


def concerns_from(active):
    """What is still unsettled for this character, as it holds it."""
    out = []
    for i, c in enumerate((active or {}).get("active_concerns") or []):
        text = c.get("text") if isinstance(c, dict) else c
        if str(text or "").strip() and str(text) != "None":
            out.append({"ref": f"c{i}", "text": _text(text), "actor": ""})
    return out[:MAX_CONCERNS]


def liking(row):
    """How much this character likes someone, from its own relationship row."""
    row = row or {}
    if isinstance(row.get("emotional_valence"), (int, float)):
        return mix._clamp(row["emotional_valence"])
    parts = [float(row.get(k) or 0) for k in ("warmth", "trust")] + \
            [-float(row.get(k) or 0) for k in ("suspicion", "fear")]
    return mix._clamp(sum(parts) / 2)


def people_from(relationships):
    """The people this character has a standing with, most familiar first."""
    rows = [{"name": str(name), "liking": round(liking(r), 3), "familiar": float((r or {}).get("familiarity") or 0)}
            for name, r in (relationships or {}).items() if isinstance(r, dict)]
    rows.sort(key=lambda p: -p["familiar"])
    return rows[:MAX_PEOPLE]


def psychology_text(sheet):
    """The character's own card psychology, as the decision model reads it."""
    psy = (sheet or {}).get("psychology") or {}
    drive = psy.get("drive") or {}
    lines = []
    if drive.get("essence"):
        lines.append("WHAT DRIVES YOU: " + _text(" ".join(str(drive[k]) for k in ("essence", "expression")
                                                            if drive.get(k)), 600))
    values = [v for v in psy.get("values") or [] if isinstance(v, dict) and v.get("name")]
    if values:
        lines.append("WHAT YOU VALUE, MOST FIRST: " + "; ".join(
            _text(v["name"], 80) for v in sorted(values, key=lambda v: -float(v.get("priority") or 0))))
    traits = [t for t in psy.get("traits") or [] if isinstance(t, dict) and t.get("name")]
    if traits:
        lines.append("HOW YOU ARE: " + "; ".join(_text(f"{t['name']} -- {t.get('expression') or ''}", 160)
                                                 for t in traits))
    model = psy.get("self_model") or {}
    if model.get("summary"):
        lines.append("HOW YOU SEE YOURSELF: " + _text(model["summary"], 400))
    cues = [a for a in (psy.get("learning") or {}).get("associations") or [] if isinstance(a, dict) and a.get("cue")]
    if cues:
        lines.append("WHAT STIRS YOU, LEARNED: " + "; ".join(
            _text(f"{a['cue']} -> {a.get('appraisal_bias') or ''}", 160) for a in cues))
    return "\n".join(lines)


def state_text(name, sheet, events, people, memories, concerns, mood_words=()):
    """The one state every question of this character's request reads."""
    parts = [f"YOU ARE {name}.", psychology_text(sheet)]
    if mood_words:
        parts.append("HOW YOU FELT COMING INTO THIS: " + ", ".join(mood_words))
    if people:
        parts.append("THE PEOPLE YOU KNOW HERE: " + "; ".join(
            f"{p['name']} (you {'like' if p['liking'] > 0.1 else 'dislike' if p['liking'] < -0.1 else 'are neutral toward'} them)"
            for p in people))
    if events:
        parts.append("WHAT JUST REACHED YOU:\n" + "\n".join(
            f"- {e['ref']}: {appraisal.event_line(e)}" for e in events))
    if concerns:
        parts.append("WHAT IS STILL UNSETTLED FOR YOU:\n" + "\n".join(f"- {c['text']}" for c in concerns))
    if memories:
        parts.append("WHAT YOU REMEMBER RIGHT NOW:\n" + "\n".join(f"- {m['text']}" for m in memories))
    return "\n\n".join(p for p in parts if p)


# --- the two passes -------------------------------------------------------------

def before_call(name, sheet, active, baseline, units, observations=(), memory_context=None,
                relationships=None, language=None, earlier=None):
    """The mood for this call. Never raises: a decision model that cannot be
    asked leaves the carried mood, decayed, with `asked` False and a note."""
    mood, home, habits, clock = carried(active, baseline, units, earlier)
    events = events_from(observations)
    memories = memories_from(memory_context)
    concerns = concerns_from(active)
    people = people_from(relationships)
    felt = Felt(mood=mood, home=home, habits=habits, clock=clock, people=people, language=language)
    felt.state_text = state_text(name, sheet, events, people, memories, concerns, mood_words(felt, language))
    if not (events or memories or concerns):
        felt.note = "nothing new to appraise"
        return felt
    try:
        out = appraisal.appraise(felt.state_text, events, people, memories, mood=True, language=language,
                                 concerns=concerns)
    except Exception as exc:  # noqa: BLE001 -- the pass fails open; the turn never does
        felt.note = f"the decision model could not be asked ({type(exc).__name__}: {str(exc)[:120]})"
        return felt
    likes = {p["name"]: p["liking"] for p in people}
    emotions = []
    for e in events:
        emotions += mix.emotions_from_appraisal(out["events"].get(e["ref"]) or {}, ref=e["ref"], actor=e["actor"],
                                                about=_text(e["text"], ABOUT_CHARS), liking=likes)
    for c in concerns:
        a = out["concerns"].get(c["ref"]) or {}
        emotions += mix.concern_emotions(a, a.get("weight"), ref=c["ref"], about=_text(c["text"], ABOUT_CHARS),
                                         liking=likes)
    for m in memories:
        a = out["memories"].get(m["ref"]) or {}
        multiplier = 1.0
        if m.get("keyed", True):
            multiplier, felt.habits = mix.recall_lands(felt.habits, m["ref"], felt.clock)
        emotions += mix.memory_emotions(a.get("strength"), a.get("tone"), a.get("kinds"), ref=m["ref"],
                                        about=_text(m["text"], ABOUT_CHARS), multiplier=multiplier)
    felt.mood, _targets = mix.mix(felt.mood, home, emotions, 0.0)
    felt.mood = mix.settle(felt.mood, {**(out.get("spectrums") or {}), **(out.get("moods") or {})})
    felt.emotions = emotions
    felt.asked = True
    return felt


def acts_from(reply):
    """What the character did, said and held back this call, as the model
    will quote it."""
    acts = []
    for i, s in enumerate(x for x in (reply or {}).get("sequence") or [] if isinstance(x, dict)):
        if s.get("type") == "speech" and str(s.get("text") or "").strip():
            acts.append({"ref": f"s{i}", "text": _text(f'You said: "{s["text"]}"'), "actor": ""})
        elif s.get("type") == "action" and (s.get("attempt") or s.get("observable")):
            acts.append({"ref": f"s{i}", "text": _text(f"You {s.get('attempt') or s.get('observable')}"),
                         "actor": ""})
    active = (reply or {}).get("active_state") or {}
    wants = active.get("wants") or []
    held = active.get("suppressed_want")
    if isinstance(held, int) and 0 <= held < len(wants) and isinstance(wants[held], dict) and wants[held].get("want"):
        acts.append({"ref": "held", "text": _text(f"You held back from: {wants[held]['want']}"), "actor": ""})
    return acts


def after_call(felt, reply):
    """The mood after the character's own acts. Never raises."""
    acts = acts_from(reply)
    if not acts:
        return felt
    state = felt.state_text + "\n\nWHAT YOU JUST DID:\n" + "\n".join(f"- {a['ref']}: {a['text']}" for a in acts)
    try:
        out = appraisal.appraise(state, acts=acts, language=felt.language)
    except Exception as exc:  # noqa: BLE001 -- the pass fails open; the turn never does
        felt.note = (felt.note + "; " if felt.note else "") + \
            f"own acts not appraised ({type(exc).__name__}: {str(exc)[:120]})"
        return felt
    own, eases = [], []
    for a in acts:
        got = out["acts"].get(a["ref"]) or {}
        own += mix.emotions_from_act(got, ref=a["ref"], about=_text(a["text"], ABOUT_CHARS))
        if got.get("eased_or_stoked") is not None:
            eases.append(got["eased_or_stoked"])
    felt.mood, _targets = mix.mix(felt.mood, felt.home, own, 0.0)
    if eases:
        felt.mood = mix.ease(felt.mood, felt.home, sum(eases) / len(eases))
    felt.emotions = felt.emotions + own
    return felt


# --- words ------------------------------------------------------------------------

def mood_words(felt, language=None, top=MOOD_WORDS):
    """The mood's most salient parts, in the pack's words."""
    return [part_word(name, value, language) for name, value in mix.mood_profile(felt.mood, top=top)]


def _word(name, language=None):
    words = affect_appraisal_options("emotion_words", language)
    if name in words:
        return str(words[name])
    moods = affect_appraisal_options("mood_words", language)
    return str(moods.get(name) or name)


def part_word(name, value, language=None):
    """One part of the mood in words: a spectrum by the pole it leans to."""
    poles = affect_appraisal_options("dimensions", language)
    if name in poles:
        return str(poles[name]["high" if value > 0 else "low"])
    return _word(name, language)


def label(emotion, language=None):
    """One felt emotion in words, with what it is about."""
    if emotion is None:
        return ""
    about = _text(emotion.about, ABOUT_CHARS)
    return _word(emotion.name, language) + (f" ({about})" if about else "")


def _emotion_va(emotion):
    effects = emotion.effects
    arousal = (float(effects.get("energy", 0.0)) + float(effects.get("tension", 0.0))) / 2
    return round(float(effects.get("pleasure", 0.0)), 4), round((arousal + 1.0) / 2.0, 4)


def given_affect(felt):
    """The mood in the engine's `active_state.affect` shape: the surface --
    the call's strongest present feeling, or the mood itself when nothing was
    felt -- with the mood's own valence and arousal, and the undercurrent."""
    surface, under = felt.parts()
    words = mood_words(felt, felt.language)
    va = mix.engine_affect(felt.mood)
    out = {"surface": {"label": label(surface, felt.language) or ", ".join(words[:2]) or "",
                       "valence": va["valence"], "arousal": va["arousal"]},
           "undercurrent": None}
    if isinstance(under, mix.Emotion):
        valence, arousal = _emotion_va(under)
        out["undercurrent"] = {"label": label(under, felt.language), "valence": valence, "arousal": arousal,
                               "source": f"{under.source}: {_text(under.about, ABOUT_CHARS)}", "serves": ""}
    elif isinstance(under, str) and under:
        out["undercurrent"] = {"label": part_word(under, felt.mood.get(under), felt.language),
                               "valence": va["valence"], "arousal": va["arousal"], "source": "mood",
                               "serves": ""}
    return out


def feelings_block(felt):
    """How the character feels, for its packet: `now` (what this moment
    stirs), `beneath` (what sits under it), `mood` (its mood in words)."""
    affect = given_affect(felt)
    return {"now": affect["surface"]["label"],
            "beneath": (affect.get("undercurrent") or {}).get("label") or "",
            "mood": mood_words(felt, felt.language)}
