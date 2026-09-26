"""The decision model's appraisal of what a character perceived, did and
recalled, and its reading of the character's mood: the model half of
`mind/affect_mix.py`.

Designed with the owner on 2026-09-26 (`docs/design/DESIGN_JEV_CHARACTER_PASS.md`,
"Emotion and mood"). Three batteries, each item quoted in its own question:

- **Events** the character perceived: how strongly each stirs the
  character, and how it makes the character feel -- one choice over OCC's
  event emotions and the standalone moods together (the pack's `feel`
  options), or nothing much. Until 2026-09-26 an event was appraised the way
  an emotion arises (Lazarus; Scherer's component process model) in nine
  questions -- how good or bad, what it makes likely, what it does to a fear
  or a hope, whose doing, right or wrong, how much the character can do,
  each person's fortune -- and OCC's rules named the feeling from the
  answers; asked directly, the model names it the way readers do
  (`affect_mix.emotions_from_appraisal` has the measurement).
- **Standing concerns** -- what is still unsettled for the character -- get
  the event questions and one more: how much it weighs on the character now.
- **The character's own acts**, after its turn (the owner: "a pass after the
  character turn finishes to see how their actions speech and thoughts
  affect their mood"): did it go against something the character values
  (dissonance), honour something it values, ease the feeling or stoke it,
  and how does it leave the character feeling about itself -- and, of the
  want the character held back alone, how much it minds not having done it.
  Until 2026-09-26 every act was asked whether there was something else the
  character wanted to do instead, and with the held-back want listed beside
  it every act said yes: frustration was what the story kept of 15 of 16
  traced beats (`docs/experiments/AFFECT_TRACE_2026_09_26.md`).
- **Recalled memories**: does recalling this stir a feeling now, is it
  pleasant, and which of the standalone moods does it stir most -- where the
  moods whose object is the past (nostalgia, grief, regret, longing) come
  from.
- **The mood**, read directly: mood as a high-dimensional object (the owner:
  "spectrums of moods as coordinates as well as some moods that truly stand
  as their own", and "cover all moods") -- fourteen bipolar spectrums, one
  five-step question each, and forty moods that stand on their own, one
  graded question each.

The text is the language pack's (`system_prompts.affect_appraisal`). One
request per character: every question in a request reads the whole state,
so two minds in one request would share a context. The state is the
caller's, built only from the character's own gated payload. The caller is
`mind/affect_pass.py`, before and after each character call.
"""

from __future__ import annotations

from llm import decisions
from llm.prompts import affect_appraisal_options, affect_appraisal_text

#: The option set each question is answered from. `stir` is every
#: standalone mood, worded by the pack's `standalone`, plus "none of these";
#: `feel` is OCC's event emotions (the pack's `event_emotions`) and the
#: standalone moods together, plus "nothing much".
OPTION_SET = {
    "stir_strength": "grade", "feel": "feel",
    "concern_weight": "grade",
    "act_against_values": "grade", "act_honors_values": "grade", "act_held_back": "grade",
    "act_eased_or_stoked": "ease", "act_self_regard": "regard",
    "evoke_strength": "grade", "evoke_tone": "tone", "evoke_mood": "stir",
    "dimension": "steps", "mood_strength": "grade",
}
#: The per-event questions, in the order they are asked; a standing concern
#: gets them too.
EVENT_QUESTIONS = ("stir_strength", "feel")
#: The questions asked of each recalled memory, and the key each reads into.
MEMORY_QUESTIONS = {"evoke_strength": "strength", "evoke_tone": "tone", "evoke_mood": "kinds"}
#: The questions asked of each of the character's own acts.
ACT_QUESTIONS = ("act_against_values", "act_honors_values", "act_eased_or_stoked", "act_self_regard")
#: Asked of the want the character held back alone (an act marked `held`,
#: quoted by its `want`): how much it minds not having done it. On the
#: restraint battery (`tools/jev_restraint_battery.py`) it met 14 of 16
#: expectations, costly restraints 0.89 against cheap ones 0.25, where the
#: retired per-act "was there something else you wanted to do or say
#: instead?" met 10 (0.84 against 0.52) and read 0.72 of the ordinary acts
#: beside a held-back want.
HELD_QUESTION = "act_held_back"
#: Where each option sits, for the option sets read as a number.
SCALES = {
    "ease": {"eased_much": -1.0, "eased": -0.5, "neither": 0.0, "stoked": 0.5, "stoked_much": 1.0},
    "regard": {"much_worse": -1.0, "worse": -0.5, "neither": 0.0, "better": 0.5, "much_better": 1.0},
    "tone": {"very_unpleasant": -1.0, "unpleasant": -0.5, "neither": 0.0, "pleasant": 0.5,
             "very_pleasant": 1.0},
    "grade": {"none": 0.0, "slight": 1 / 3, "clear": 2 / 3, "strong": 1.0},
    "steps": {"s0": -1.0, "s1": -0.5, "s2": 0.0, "s3": 0.5, "s4": 1.0},
}


def spectrums(language=None):
    """The mood's bipolar coordinates, in the pack's order."""
    return tuple(affect_appraisal_options("dimensions", language))


def standalone_moods(language=None):
    """The moods that stand on their own, in the pack's order."""
    return tuple(affect_appraisal_options("standalone", language))


def _fill(text, values):
    # a plain replace, never str.format: quoted text may carry braces
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _labels(option_set, language=None):
    if option_set == "stir":
        return {**affect_appraisal_options("standalone", language),
                **affect_appraisal_options("stir", language)}
    if option_set == "feel":
        return {**affect_appraisal_options("event_emotions", language),
                **affect_appraisal_options("standalone", language),
                **affect_appraisal_options("feel", language)}
    return affect_appraisal_options(option_set, language)


def _choice(name, language=None, criteria=None, **values):
    """One question: the pack's template with its placeholders filled, and
    the pack's labels for its option set (filled the same way)."""
    labels = criteria if criteria is not None else _labels(OPTION_SET[name], language)
    return {"type": "choice", "instructions": _fill(affect_appraisal_text(name, language), values),
            "criteria": {k: _fill(v, values) for k, v in labels.items()}}


def event_line(event):
    """How an event is quoted to the model: its actor's label, when the
    perception gave one, and its text."""
    text = " ".join(str(event.get("text") or "").split())
    actor = str(event.get("actor") or "").strip()
    return f"{actor}: {text}" if actor and not text.startswith(actor) else text


def _event_questions(prefix, event, language=None):
    ref, line = str(event["ref"]), event_line(event)
    return {f"{prefix}:{ref}:{name}": _choice(name, language, event=line) for name in EVENT_QUESTIONS}


def questions_for(events=(), memories=(), acts=(), mood=False, language=None, concerns=()):
    """`{key: question}` for one character. Keys: `ev:<ref>:<question>`; a
    concern's the same under `con:` plus `con:<ref>:weight`;
    `act:<ref>:<question>`, and for an act marked `held` (its `want`, the
    want held back) `act:<ref>:act_held_back`;
    `mem:<ref>:<strength|tone|kinds>`; with `mood`, `dim:<spectrum>` and
    `mood:<standalone mood>`."""
    qs = {}
    for event in events:
        qs.update(_event_questions("ev", event, language))
    for concern in concerns:
        qs.update(_event_questions("con", concern, language))
        text = " ".join(str(concern.get("text") or "").split())
        qs[f"con:{concern['ref']}:weight"] = _choice("concern_weight", language, concern=text)
    for act in acts:
        ref = str(act["ref"])
        text = " ".join(str(act.get("text") or "").split())
        for name in ACT_QUESTIONS:
            qs[f"act:{ref}:{name}"] = _choice(name, language, act=text)
        if act.get("held"):
            want = " ".join(str(act.get("want") or text).split())
            qs[f"act:{ref}:{HELD_QUESTION}"] = _choice(HELD_QUESTION, language, want=want)
    for memory in memories:
        ref = str(memory["ref"])
        text = " ".join(str(memory.get("text") or "").split())
        for name, part in MEMORY_QUESTIONS.items():
            qs[f"mem:{ref}:{part}"] = _choice(name, language, memory=text)
    if mood:
        poles = affect_appraisal_options("dimensions", language)
        for name in spectrums(language):
            pole = poles[name]
            qs[f"dim:{name}"] = _choice("dimension", language, low=pole["low"], high=pole["high"])
        phrases = affect_appraisal_options("standalone", language)
        for name in standalone_moods(language):
            qs[f"mood:{name}"] = _choice("mood_strength", language, mood=phrases[name])
    return qs


def _probabilities(answer):
    probs = (answer or {}).get("probabilities") or {}
    out = {}
    for key, value in probs.items():
        try:
            out[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def _number(answers, key, option_set):
    probs = _probabilities(answers.get(key))
    scale = SCALES[option_set]
    mass = sum(p for k, p in probs.items() if k in scale)
    if mass <= 0:
        return None
    return sum(scale[k] * p for k, p in probs.items() if k in scale) / mass


def _distribution(answers, key):
    probs = _probabilities(answers.get(key))
    total = sum(probs.values())
    return {k: v / total for k, v in probs.items()} if total > 0 else None


def _read_event(answers, prefix, ref):
    a = {}
    strength = _number(answers, f"{prefix}:{ref}:stir_strength", "grade")
    if strength is not None:
        a["stir"] = strength
    named = _distribution(answers, f"{prefix}:{ref}:feel")
    if named is not None:
        a["stirs"] = named
    return a


def read(answers, events=(), memories=(), acts=(), mood=False, language=None, concerns=()):
    """The appraisals, in the shapes `affect_mix` reads:

    - per event: `stir` in [0, 1], how strongly it stirs the character, and
      `stirs`, the distribution over what it makes the character feel --
      OCC's event emotions, the standalone moods and `none`;
    - per concern: the same, and `weight` in [0, 1];
    - per act: `against_values`, `honors_values` in [0, 1]; `eased_or_stoked`,
      `self_regard` in [-1, 1]; of the held-back want, `held_back` in [0, 1];
    - per memory: `strength` in [0, 1], `tone` in [-1, 1], `kinds` as a
      distribution over the standalone moods and `none`;
    - with `mood`: `spectrums` {name: [-1, 1]} and `moods` {name: [0, 1]}.

    A question the model did not answer is left out, never read as zero."""
    answers = answers or {}
    out = {"events": {}, "concerns": {}, "acts": {}, "memories": {}}
    for event in events:
        out["events"][str(event["ref"])] = _read_event(answers, "ev", str(event["ref"]))
    for concern in concerns:
        ref = str(concern["ref"])
        a = _read_event(answers, "con", ref)
        weight = _number(answers, f"con:{ref}:weight", "grade")
        if weight is not None:
            a["weight"] = weight
        out["concerns"][ref] = a
    for act in acts:
        ref = str(act["ref"])
        a = {}
        for name in ACT_QUESTIONS + (HELD_QUESTION,):
            value = _number(answers, f"act:{ref}:{name}", OPTION_SET[name])
            if value is not None:
                a[name[len("act_"):]] = value
        out["acts"][ref] = a
    for memory in memories:
        ref = str(memory["ref"])
        m = {}
        for name, part in MEMORY_QUESTIONS.items():
            key = f"mem:{ref}:{part}"
            option_set = OPTION_SET[name]
            value = _distribution(answers, key) if option_set == "stir" else _number(answers, key, option_set)
            if value is not None:
                m[part] = value
        out["memories"][ref] = m
    if mood:
        out["spectrums"] = {name: v for name in spectrums(language)
                            if (v := _number(answers, f"dim:{name}", "steps")) is not None}
        out["moods"] = {name: v for name in standalone_moods(language)
                        if (v := _number(answers, f"mood:{name}", "grade")) is not None}
    return out


def appraise(state, events=(), memories=(), acts=(), mood=False, language=None, concerns=()):
    """Ask the decision model every question for one character and read the
    answers. `events`, `concerns` and `acts` are `{"ref", "text", "actor"?}`;
    `memories` `{"ref", "text"}`. Raises `decisions.DecisionError` when
    nothing could be asked -- the caller decides what failing open means."""
    qs = questions_for(events, memories, acts, mood, language, concerns)
    if not qs:
        return {"events": {}, "concerns": {}, "acts": {}, "memories": {}}
    return read(decisions.decide(state, qs), events, memories, acts, mood, language, concerns)
