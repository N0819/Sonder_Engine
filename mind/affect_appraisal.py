"""The decision model's appraisal of what a character just perceived and
recalled: the model half of `mind/affect_mix.py`.

Designed with the owner on 2026-09-26 (`docs/design/DESIGN_JEV_CHARACTER_PASS.md`,
"Emotion and mood"). An emotion is the outcome of appraising an event against
what one cares about (Lazarus; Scherer's component process model), so each
event is asked about on its own, quoted:

- how good or bad it is for the character, whether it has happened or might,
  how likely if not, whether it settles a hope or a fear, who brought it
  about, whether that was right by the character's standards, how much the
  character can do about it, and how much it stirs desire;
- for each person the character has a standing with, how good or bad it is
  for them;

and each recalled memory on its own: does recalling it stir a feeling now,
and is that feeling pleasant.

The questions are the language pack's (`system_prompts.affect_appraisal`),
one request per character: every question in a request reads the whole
state, so two minds in one request would share a context. The state is the
caller's, built only from the character's own gated payload.

NOT WIRED. Nothing in the turn calls this yet.
"""

from __future__ import annotations

from llm import decisions
from llm.prompts import affect_appraisal_options, affect_appraisal_text

#: The option set each question is answered from.
OPTION_SET = {
    "desirability": "goodness", "status": "status", "likelihood": "likelihood",
    "confirmation": "confirmation", "agency": "agency", "standards": "standards",
    "control": "grade", "desire": "grade", "fortune": "goodness",
    "evoke_strength": "grade", "evoke_tone": "tone",
}
#: The per-event questions, in the order they are asked.
EVENT_QUESTIONS = ("desirability", "status", "likelihood", "confirmation", "agency",
                   "standards", "control", "desire")
#: Where each option sits, for the option sets read as a number.
SCALES = {
    "goodness": {"very_bad": -1.0, "bad": -0.5, "neutral": 0.0, "good": 0.5, "very_good": 1.0},
    "standards": {"very_wrong": -1.0, "wrong": -0.5, "neither": 0.0, "right": 0.5, "very_right": 1.0},
    "tone": {"very_unpleasant": -1.0, "unpleasant": -0.5, "neither": 0.0, "pleasant": 0.5,
             "very_pleasant": 1.0},
    "grade": {"none": 0.0, "slight": 1 / 3, "clear": 2 / 3, "strong": 1.0},
    "likelihood": {"none": 0.0, "slight": 1 / 3, "clear": 2 / 3, "strong": 1.0},
}
#: Read as a distribution rather than a number.
DISTRIBUTIONS = {"confirmation", "agency", "status"}


def _choice(name, language=None, **values):
    """One question: the pack's template with its placeholders filled (a
    plain replace, never str.format -- quoted text may carry braces), and
    the pack's labels for its option set."""
    text = affect_appraisal_text(name, language)
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return {"type": "choice", "instructions": text,
            "criteria": affect_appraisal_options(OPTION_SET[name], language)}


def event_line(event):
    """How an event is quoted to the model: its actor's label, when the
    perception gave one, and its text."""
    text = " ".join(str(event.get("text") or "").split())
    actor = str(event.get("actor") or "").strip()
    return f"{actor}: {text}" if actor and not text.startswith(actor) else text


def questions_for(events=(), people=(), memories=(), language=None):
    """`{key: question}`: the per-event questions for every event, one
    `fortune` question per event and person, and two per memory. Keys are
    `ev:<ref>:<name>`, `ev:<ref>:fortune:<index into people>` and
    `mem:<ref>:<strength|tone>`."""
    qs = {}
    for event in events:
        ref, line = str(event["ref"]), event_line(event)
        for name in EVENT_QUESTIONS:
            qs[f"ev:{ref}:{name}"] = _choice(name, language, event=line)
        for index, person in enumerate(people):
            qs[f"ev:{ref}:fortune:{index}"] = _choice("fortune", language, event=line,
                                                      person=person["name"])
    for memory in memories:
        ref = str(memory["ref"])
        text = " ".join(str(memory.get("text") or "").split())
        qs[f"mem:{ref}:strength"] = _choice("evoke_strength", language, memory=text)
        qs[f"mem:{ref}:tone"] = _choice("evoke_tone", language, memory=text)
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


def read(answers, events=(), people=(), memories=()):
    """The appraisals, in the shape `affect_mix.emotions_from_appraisal`
    reads: per event `desirability`, `standards` in [-1, 1]; `likelihood`,
    `control`, `desire` in [0, 1]; `happened` the probability it has
    happened; `confirmation` and `agency` as distributions; `fortune` per
    person's name. Per memory `strength` in [0, 1] and `tone` in [-1, 1].
    A question the model did not answer is left out, never read as zero."""
    answers = answers or {}

    def number(key, option_set):
        probs = _probabilities(answers.get(key))
        scale = SCALES[option_set]
        mass = sum(p for k, p in probs.items() if k in scale)
        if mass <= 0:
            return None
        return sum(scale[k] * p for k, p in probs.items() if k in scale) / mass

    out = {"events": {}, "memories": {}}
    for event in events:
        ref = str(event["ref"])
        a = {}
        for name in EVENT_QUESTIONS:
            key = f"ev:{ref}:{name}"
            if name in DISTRIBUTIONS:
                probs = _probabilities(answers.get(key))
                if not probs:
                    continue
                if name == "status":
                    a["happened"] = probs.get("happened", 0.0) / max(1e-9, sum(probs.values()))
                else:
                    a[name] = probs
            else:
                value = number(key, OPTION_SET[name])
                if value is not None:
                    a[name] = value
        fortune = {}
        for index, person in enumerate(people):
            value = number(f"ev:{ref}:fortune:{index}", "goodness")
            if value is not None:
                fortune[person["name"]] = value
        if fortune:
            a["fortune"] = fortune
        out["events"][ref] = a
    for memory in memories:
        ref = str(memory["ref"])
        m = {}
        for part, option_set in (("strength", "grade"), ("tone", "tone")):
            value = number(f"mem:{ref}:{part}", option_set)
            if value is not None:
                m[part] = value
        out["memories"][ref] = m
    return out


def appraise(state, events=(), people=(), memories=(), language=None):
    """Ask the decision model every appraisal question for one character and
    read the answers. `state` is that character's own context; `events` are
    `{"ref", "text", "actor"?}`; `people` are `{"name", ...}`; `memories` are
    `{"ref", "text"}`. Raises `decisions.DecisionError` when nothing could be
    asked -- the caller decides what failing open means."""
    qs = questions_for(events, people, memories, language)
    if not qs:
        return {"events": {}, "memories": {}}
    return read(decisions.decide(state, qs), events, people, memories)
