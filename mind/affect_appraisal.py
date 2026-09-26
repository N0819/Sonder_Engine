"""The decision model's appraisal of what a character perceived, did and
recalled, and its reading of the character's mood: the model half of
`mind/affect_mix.py`.

Designed with the owner on 2026-09-26 (`docs/design/DESIGN_JEV_CHARACTER_PASS.md`,
"Emotion and mood"). Three batteries, each item quoted in its own question:

- **Events** the character perceived, appraised the way an emotion arises
  (Lazarus; Scherer's component process model): how good or bad for the
  character; what it makes more likely ahead; whether it bears on a fear
  (easing or confirming it) or a hope (bringing it closer or pushing it
  away); whose doing it is -- the event's own actor named as an option; right
  or wrong by the character's standards; how much the character can do about
  it; how strongly it stirs the character, and which of the standalone moods
  it stirs most; and, per person the character has a standing with, how good
  or bad it is for them. Refined 2026-09-26 after the first round read a
  character's own lines as other people's doing and blurred relief into
  satisfaction (the evidence doc, "The affect pass").
- **Standing concerns** -- what is still unsettled for the character -- get
  the event questions and one more: how much it weighs on the character now.
- **The character's own acts**, after its turn (the owner: "a pass after the
  character turn finishes to see how their actions speech and thoughts
  affect their mood"): did it go against something the character values
  (dissonance), honour something it values, cost something it wanted
  instead, ease the feeling or stoke it, and how does it leave the
  character feeling about itself.
- **Recalled memories**: does recalling this stir a feeling now, is it
  pleasant, and which of the standalone moods does it stir most -- where the
  moods whose object is the past (nostalgia, grief, regret, longing) come
  from.
- **The mood**, read directly: mood as a high-dimensional object (the owner:
  "spectrums of moods as coordinates as well as some moods that truly stand
  as their own", and "cover all moods") -- fourteen bipolar spectrums, one
  five-step question each, and thirty-two moods that stand on their own, one
  graded question each.

The text is the language pack's (`system_prompts.affect_appraisal`). One
request per character: every question in a request reads the whole state,
so two minds in one request would share a context. The state is the
caller's, built only from the character's own gated payload.

NOT WIRED. Nothing in the turn calls this yet.
"""

from __future__ import annotations

from llm import decisions
from llm.prompts import affect_appraisal_options, affect_appraisal_text

#: The option set each question is answered from. `stir` is every
#: standalone mood, worded by the pack's `standalone`, plus "none of these".
OPTION_SET = {
    "desirability": "goodness", "ahead": "prospect", "fear_change": "fear_change",
    "hope_change": "hope_change", "doer": "doer", "standards": "standards", "control": "grade",
    "stir_strength": "grade", "stir_mood": "stir", "fortune": "goodness",
    "concern_weight": "grade",
    "act_against_values": "grade", "act_honors_values": "grade", "act_wanted_instead": "grade",
    "act_eased_or_stoked": "ease", "act_self_regard": "regard",
    "evoke_strength": "grade", "evoke_tone": "tone", "evoke_mood": "stir",
    "dimension": "steps", "mood_strength": "grade",
}
#: The per-event questions, in the order they are asked; a standing concern
#: gets them too.
EVENT_QUESTIONS = ("desirability", "ahead", "fear_change", "hope_change", "doer", "standards",
                   "control", "stir_strength", "stir_mood")
#: The questions asked of each recalled memory, and the key each reads into.
MEMORY_QUESTIONS = {"evoke_strength": "strength", "evoke_tone": "tone", "evoke_mood": "kinds"}
#: The questions asked of each of the character's own acts.
ACT_QUESTIONS = ("act_against_values", "act_honors_values", "act_wanted_instead",
                 "act_eased_or_stoked", "act_self_regard")
#: Where each option sits, for the option sets read as a number.
SCALES = {
    "goodness": {"very_bad": -1.0, "bad": -0.5, "neutral": 0.0, "good": 0.5, "very_good": 1.0},
    "prospect": {"much_worse": -1.0, "worse": -0.5, "neither": 0.0, "better": 0.5, "much_better": 1.0},
    # negative: the feared thing grows less likely (relief); positive: more
    "fear_change": {"much_less": -1.0, "less": -0.5, "none": 0.0, "more": 0.5, "much_more": 1.0},
    # negative: the hoped-for thing is pushed away; positive: brought closer
    "hope_change": {"much_further": -1.0, "further": -0.5, "none": 0.0, "closer": 0.5, "much_closer": 1.0},
    "standards": {"very_wrong": -1.0, "wrong": -0.5, "neither": 0.0, "right": 0.5, "very_right": 1.0},
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


def _event_questions(prefix, event, people, language=None):
    ref, line = str(event["ref"]), event_line(event)
    actor = str(event.get("actor") or "").strip()
    qs = {}
    for name in EVENT_QUESTIONS:
        if name == "doer":
            # the event's own actor is an option by name; no actor, no option
            labels = {k: v for k, v in affect_appraisal_options("doer", language).items()
                      if k != "actor" or actor}
            qs[f"{prefix}:{ref}:doer"] = _choice("doer", language, labels, event=line, actor=actor)
        else:
            qs[f"{prefix}:{ref}:{name}"] = _choice(name, language, event=line)
    for index, person in enumerate(people):
        qs[f"{prefix}:{ref}:fortune:{index}"] = _choice("fortune", language, event=line,
                                                        person=person["name"])
    return qs


def questions_for(events=(), people=(), memories=(), acts=(), mood=False, language=None, concerns=()):
    """`{key: question}` for one character. Keys: `ev:<ref>:<question>` and
    `ev:<ref>:fortune:<index into people>`; a concern's the same under `con:`
    plus `con:<ref>:weight`; `act:<ref>:<question>`;
    `mem:<ref>:<strength|tone|kinds>`; with `mood`, `dim:<spectrum>` and
    `mood:<standalone mood>`."""
    qs = {}
    for event in events:
        qs.update(_event_questions("ev", event, people, language))
    for concern in concerns:
        qs.update(_event_questions("con", concern, people, language))
        text = " ".join(str(concern.get("text") or "").split())
        qs[f"con:{concern['ref']}:weight"] = _choice("concern_weight", language, concern=text)
    for act in acts:
        ref = str(act["ref"])
        text = " ".join(str(act.get("text") or "").split())
        for name in ACT_QUESTIONS:
            qs[f"act:{ref}:{name}"] = _choice(name, language, act=text)
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


#: Where an event question's answer lands in the appraisal, when not under
#: its own name.
_EVENT_KEY = {"stir_strength": "stir", "stir_mood": "stirs"}


def _read_event(answers, prefix, ref, people):
    a = {}
    for name in EVENT_QUESTIONS:
        key = f"{prefix}:{ref}:{name}"
        if OPTION_SET[name] in ("doer", "stir"):
            value = _distribution(answers, key)
        else:
            value = _number(answers, key, OPTION_SET[name])
        if value is not None:
            a[_EVENT_KEY.get(name, name)] = value
    fortune = {}
    for index, person in enumerate(people):
        value = _number(answers, f"{prefix}:{ref}:fortune:{index}", "goodness")
        if value is not None:
            fortune[person["name"]] = value
    if fortune:
        a["fortune"] = fortune
    return a


def read(answers, events=(), people=(), memories=(), acts=(), mood=False, language=None, concerns=()):
    """The appraisals, in the shapes `affect_mix` reads:

    - per event: `desirability`, `ahead`, `fear_change`, `hope_change`,
      `standards` in [-1, 1]; `control`, `stir` in [0, 1]; `doer` as a
      distribution over self / actor / other / nobody; `stirs` as a
      distribution over the standalone moods and `none`; `fortune` per name;
    - per concern: the same, and `weight` in [0, 1];
    - per act: `against_values`, `honors_values`, `wanted_instead` in [0, 1];
      `eased_or_stoked`, `self_regard` in [-1, 1];
    - per memory: `strength` in [0, 1], `tone` in [-1, 1], `kinds` as a
      distribution over the standalone moods and `none`;
    - with `mood`: `spectrums` {name: [-1, 1]} and `moods` {name: [0, 1]}.

    A question the model did not answer is left out, never read as zero."""
    answers = answers or {}
    out = {"events": {}, "concerns": {}, "acts": {}, "memories": {}}
    for event in events:
        out["events"][str(event["ref"])] = _read_event(answers, "ev", str(event["ref"]), people)
    for concern in concerns:
        ref = str(concern["ref"])
        a = _read_event(answers, "con", ref, people)
        weight = _number(answers, f"con:{ref}:weight", "grade")
        if weight is not None:
            a["weight"] = weight
        out["concerns"][ref] = a
    for act in acts:
        ref = str(act["ref"])
        a = {}
        for name in ACT_QUESTIONS:
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


def appraise(state, events=(), people=(), memories=(), acts=(), mood=False, language=None, concerns=()):
    """Ask the decision model every question for one character and read the
    answers. `events`, `concerns` and `acts` are `{"ref", "text", "actor"?}`;
    `people` `{"name", ...}`; `memories` `{"ref", "text"}`. Raises
    `decisions.DecisionError` when nothing could be asked -- the caller
    decides what failing open means."""
    qs = questions_for(events, people, memories, acts, mood, language, concerns)
    if not qs:
        return {"events": {}, "concerns": {}, "acts": {}, "memories": {}}
    return read(decisions.decide(state, qs), events, people, memories, acts, mood, language, concerns)
