"""The decision model around a bare character call.

The owner, 2026-09-26: "I truly want an as bare bones character prompt as
possible. That still basically does the same thing thanks to jev... except
the character is now mostly reasoning about being the character it's been
given." (`docs/design/DESIGN_JEV_CHARACTER_PASS.md`, "The bare contract".)

The bare reply (`llm.schemas.CharacterBareOutput`) carries only what a
character can write: what it says and does and why, what it wants and holds
back, what it makes of the people here, what changed in it, and a note to
itself. Everything the engine used to read off the long reply -- volume,
concealment, addressees, targets, a want's service, the update lanes, their
citations, the appraisal -- is asked of the decision model here, from the
reply, the model's own reasoning when the provider returned it, and what this
mind legitimately holds.

THE FIREWALL HOLDS BY CONSTRUCTION, as it does for `mind/affect_pass.py`:
`Holding` is built only from this character's own gated payload, the state
every question reads is built only from `Holding` and this character's own
reply, and one request serves one character. Every option offered is a row
this mind was delivered or an item it already holds, so a citation cannot be
invented: "none" is always an option, and a lane whose citation comes back
"none" is dropped exactly where commit would have dropped the model's.

Jev judges; code writes text. An answer is a choice or a grade, and every
string the engine stores is the character's own words or a delivered row's.

Every limit below is named, and every one is the owner's.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from llm import decisions
from llm.prompts import character_jev_options, character_jev_text
from mind.affect_appraisal import _fill, _probabilities

#: How much of what this mind holds is offered, per call.
MAX_PEOPLE = 6
MAX_EVENTS = 8
MAX_MEMORIES = 12
MAX_BELIEFS = 8
MAX_ASSOCIATIONS = 6
MAX_CONCERNS = 4
MAX_AIMS = 5
MAX_HEARD_LINES = 8
MAX_CHANGES = 6
MAX_READINGS = 6
MAX_STEPS = 8
#: Tells a reply may carry -- the full card's "at most two", now enforced
#: here instead of asked of the model.
MAX_TELLS = 2
#: How much of the model's reasoning trace the decision model reads.
REASONING_CHARS = 6000
#: How long an item may run in a question or an option before it is cut.
ITEM_CHARS = 300
#: The carried charge below which a release is not asked about.
RELEASE_ASK_FLOOR = 0.3
#: The yes-share at which a recalled memory is shown as one the moment may
#: cast in a new light (`memory.may_mean_otherwise`).
DISPUTE_FLOOR = 0.5
#: A relationship moves by REL_STEP per step on its five-step scale -- the
#: full card's "within +-0.05" -- and by REL_BREAK_STEP when the beat was a
#: real break, rescue or betrayal between the two (the code clamp is 0.2).
REL_STEP = 0.05
REL_BREAK_STEP = 0.2
#: The strength with which a held belief a beat bore out or cast doubt on is
#: reinforced or weakened.
BELIEF_SUPPORT = 0.6
#: An association fired this beat is reinforced by this much (the card's
#: default `amount`).
ASSOCIATION_STEP = 0.1
#: How many of its own notes a mind is shown, newest last (`self.my_notes`),
#: and how long one may run.
NOTES_KEPT = 5
NOTE_CHARS = 300

GRADE = {"none": 0.0, "slight": 1 / 3, "clear": 2 / 3, "strong": 1.0}
SIGNED = {"much_less": -1.0, "less": -0.5, "same": 0.0, "more": 0.5, "much_more": 1.0}
FIT = {"against_all": -1.0, "against": -0.5, "neither": 0.0, "fits": 0.5, "fits_all": 1.0}
TONE = {"very_unpleasant": -1.0, "unpleasant": -0.5, "neither": 0.0, "pleasant": 0.5,
        "very_pleasant": 1.0}
ABILITY = {"much_less": -1.0, "less": -0.5, "same": 0.0, "more": 0.5, "much_more": 1.0}
IMPACT = {"hurts_badly": -1.0, "hurts": -0.5, "none": 0.0, "helps": 0.5, "helps_greatly": 1.0}
CERTAIN = {"done": 0.9, "may": 0.5, "unclear": 0.3}
#: How hard a tell is to miss, as the engine's `subtlety` (a tell reaches an
#: observer whose acuity, familiarity and attention reach this far).
MISS = {"plain": 0.15, "noticeable": 0.4, "subtle": 0.65, "hidden": 0.9}
REL_AXES = ("trust", "warmth", "fear", "respect", "suspicion")


@dataclass
class Holding:
    """What this mind legitimately holds for one call: its own payload only."""
    name: str
    language: str | None = None
    psychology: str = ""
    events: list = field(default_factory=list)        # {ref, text, actor}
    people: list = field(default_factory=list)        # labels perceived here
    known: list = field(default_factory=list)         # names it has a standing with
    memories: list = field(default_factory=list)      # {ref, text}
    aims: list = field(default_factory=list)          # {kind, id, text}
    beliefs: list = field(default_factory=list)       # held belief texts
    associations: list = field(default_factory=list)  # {cue, appraisal_bias, response_tendency}
    concerns: list = field(default_factory=list)      # held concern texts
    contacts: list = field(default_factory=list)      # {ref, text}
    promises: list = field(default_factory=list)      # {from, what}
    strategies: list = field(default_factory=list)    # coping strategy names
    heard: list = field(default_factory=list)         # {ref, text, speaker}
    drive: dict = field(default_factory=dict)         # the card's drive
    charge: float = 0.0
    rupture_open: bool = False
    reasoning: str = ""


def _text(value, n=ITEM_CHARS):
    text = " ".join(str(value or "").split())
    return text if len(text) <= n else text[:n] + "..."


# --- the reply, as this module reads it ----------------------------------------

def steps(reply):
    """The reply's sequence as `(index, kind, row)`: kind is say, do or
    ponder; an element carrying none of them is skipped."""
    out = []
    for index, row in enumerate((reply or {}).get("sequence") or []):
        if not isinstance(row, dict):
            continue
        for kind in ("say", "do", "ponder"):
            if str(row.get(kind) or "").strip():
                out.append((index, kind, row))
                break
    return out[:MAX_STEPS]


def lines_of(reply, key, cap):
    return [_text(x) for x in ((reply or {}).get(key) or []) if str(x or "").strip()][:cap]


# --- the state every question reads -----------------------------------------------

def _aim_label(aim, language):
    labels = character_jev_options("aim_labels", language)
    return _fill(labels.get(aim["kind"], "{text}"), {"text": _text(aim["text"])})


def state_text(h, reply=None):
    """One state for one mind: who it is, what it holds, what reached it,
    what it remembers -- and after the call what it did, and its own
    thinking when the provider returned it."""
    parts = [f"YOU ARE {h.name}.", h.psychology]
    if h.aims:
        parts.append("WHAT YOU ARE AFTER:\n" + "\n".join(
            f"- {_aim_label(a, h.language)}" for a in h.aims))
    if h.beliefs:
        parts.append("WHAT YOU BELIEVE:\n" + "\n".join(f"- {_text(b)}" for b in h.beliefs))
    if h.concerns:
        parts.append("WHAT IS ON YOUR MIND:\n" + "\n".join(f"- {_text(c)}" for c in h.concerns))
    if h.people:
        parts.append("WHO IS HERE: " + ", ".join(h.people))
    if h.events:
        parts.append("WHAT JUST REACHED YOU:\n" + "\n".join(
            "- " + (f"{e['actor']}: " if e.get("actor") and not str(e["text"]).startswith(e["actor"]) else "")
            + _text(e["text"]) for e in h.events))
    if h.memories:
        parts.append("WHAT YOU REMEMBER RIGHT NOW:\n" + "\n".join(
            f"- {_text(m['text'])}" for m in h.memories))
    if reply:
        did = []
        for _index, kind, row in steps(reply):
            why = f" (why: {_text(row.get('why'))})" if str(row.get("why") or "").strip() else ""
            if kind == "say":
                to = f" to {_text(row.get('to'), 80)}" if str(row.get("to") or "").strip() else ""
                how = f", {_text(row.get('how'), 80)}" if str(row.get("how") or "").strip() else ""
                did.append(f'- You said{to}{how}: "{_text(row["say"])}"{why}')
            elif kind == "do":
                did.append(f"- You did: {_text(row['do'])}{why}")
            else:
                did.append(f"- You tried to remember: {_text(row['ponder'])}{why}")
        if did:
            parts.append("WHAT YOU DID:\n" + "\n".join(did))
        choice = [f"{label}: {_text(reply.get(key))}" for key, label in (
            ("want", "WHAT YOU WENT FOR"), ("held_back", "WHAT YOU HELD BACK"),
            ("hinge", "WHY"), ("unsure", "WHAT IS UNSETTLED")) if str(reply.get(key) or "").strip()]
        if choice:
            parts.append("\n".join(choice))
        if h.reasoning:
            parts.append("YOUR OWN THINKING AS YOU WORKED IT OUT (some of it you set aside):\n"
                         + _text(h.reasoning, REASONING_CHARS))
    return "\n\n".join(p for p in parts if p)


# --- questions ----------------------------------------------------------------------

def _choice(name, language, criteria, **values):
    return {"type": "choice", "instructions": _fill(character_jev_text(name, language), values),
            "criteria": {k: _fill(v, values) for k, v in criteria.items()}}


def _set(name, language):
    return character_jev_options(name, language)


def _options(items, none_key, language, prefix):
    """`{prefix<i>: label}` for items, plus the pack's `none_key` choice."""
    out = {f"{prefix}{i}": _text(label, 160) for i, label in enumerate(items)}
    if none_key:
        out[none_key] = _set("choices", language)[none_key]
    return out


def before_questions(h):
    """Asked before the call, and only when something reached this mind:
    does it change what a recalled memory meant? A yes gates the dispute
    module and its payload section into this call."""
    if not (h.events and h.memories):
        return {}
    yesno = _set("yesno", h.language)
    return {f"dispute:{i}": _choice("dispute", h.language, yesno, memory=_text(m["text"]))
            for i, m in enumerate(h.memories)}


def read_before(answers, h):
    """The memories the moment may cast in a new light, by the yes-share."""
    out = []
    for i, m in enumerate(h.memories):
        if _probabilities(answers.get(f"dispute:{i}")).get("yes", 0.0) >= DISPUTE_FLOOR:
            out.append(m)
    return out


def after_questions(h, reply):
    """Everything asked after the call, keyed `<family>:<index>:<part>`."""
    lang = h.language
    qs = {}
    yesno = _set("yesno", lang)
    grade = _set("grade", lang)
    none_str = _set("choices", lang)["not_stated"]
    people = h.people
    heard_speakers = sorted({x["speaker"] for x in h.heard if x.get("speaker")})
    events = [e["text"] for e in h.events]
    memories = [m["text"] for m in h.memories]
    any_do = False
    any_say = False

    # --- the sequence, typed ---
    for index, kind, row in steps(reply):
        why = _text(row.get("why")) or none_str
        if kind == "say":
            any_say = True
            line, how = _text(row["say"]), _text(row.get("how")) or none_str
            to = _text(row.get("to")) or none_str
            qs[f"say:{index}:volume"] = _choice("line_volume", lang, _set("volume", lang), line=line, how=how)
            if people:
                criteria = _options(people, None, lang, "p")
                criteria["everyone"] = _set("choices", lang)["everyone"]
                criteria["nobody"] = _set("choices", lang)["nobody"]
                qs[f"say:{index}:to"] = _choice("line_to", lang, criteria, line=line, to=to)
                for p, person in enumerate(people):
                    qs[f"say:{index}:kept:{p}"] = _choice(
                        "line_kept_from", lang, yesno, line=line, how=how, why=why, person=person)
            qs[f"say:{index}:expects"] = _choice("line_expects", lang, yesno, line=line)
            if heard_speakers:
                qs[f"say:{index}:interrupts"] = _choice(
                    "line_interrupts", lang, {**_options(heard_speakers, "nobody", lang, "p")}, line=line)
        elif kind == "do":
            any_do = True
            act = _text(row["do"])
            qs[f"do:{index}:seen"] = _choice("act_seen", lang, _set("act_kind", lang), act=act)
            # A measurement, not a gate: how often the act's own words carry
            # what no watcher could see (the observable is the model's words).
            qs[f"do:{index}:private"] = _choice("act_private", lang, yesno, act=act)
            if people:
                qs[f"do:{index}:target"] = _choice("act_target", lang, _options(people, "no_target", lang, "p"),
                                                   act=act)
                for p, person in enumerate(people):
                    qs[f"do:{index}:kept:{p}"] = _choice(
                        "act_kept_from", lang, yesno, act=act, why=why, person=person)
    if any_do:
        if people:
            choices = _set("choices", lang)
            criteria = {f"start{p}": _fill(choices["follow_start"], {"person": person})
                        for p, person in enumerate(people)}
            criteria["stop"] = choices["follow_stop"]
            criteria["neither"] = choices["follow_neither"]
            qs["follow"] = _choice("follow", lang, criteria)
        for c, contact in enumerate(h.contacts):
            qs[f"contact:{c}"] = _choice("contact_end", lang, yesno, contact=_text(contact["text"]))

    # --- the choice ---
    aims = [_aim_label(a, lang) for a in h.aims]
    serve_options = _options(aims, None, lang, "a")
    serve_options["situational"] = _set("choices", lang)["situational"]
    for key in ("want", "held_back"):
        text = _text((reply or {}).get(key))
        if text:
            qs[f"{key}:serves"] = _choice("want_serves", lang, serve_options, want=text)
            qs[f"{key}:urgency"] = _choice("want_urgency", lang, grade, want=text)
    for j, tell in enumerate(lines_of(reply, "tells", MAX_TELLS)):
        qs[f"tell:{j}:channel"] = _choice("tell_channel", lang, _set("channel", lang), tell=tell)
        qs[f"tell:{j}:miss"] = _choice("tell_subtlety", lang, _set("miss", lang), tell=tell)
    if any_say or heard_speakers:
        qs["done_talking"] = _choice("done_talking", lang, yesno)
    qs["urgency"] = _choice("urgency", lang, grade)
    qs["salience"] = _choice("salience", lang, grade)

    # --- readings of people, and what changed ---
    whom = list(dict.fromkeys(people + h.known))[:MAX_PEOPLE * 2]
    for j, line in enumerate(lines_of(reply, "people", MAX_READINGS)):
        if whom:
            qs[f"person:{j}:about"] = _choice("about_whom", lang, _options(whom, "nobody", lang, "p"), text=line)
        qs[f"person:{j}:kind"] = _choice("reading_kind", lang, _set("reading_kind", lang), text=line)
        qs[f"person:{j}:sure"] = _choice("sure", lang, grade, text=line)
        _evidence_questions(qs, f"person:{j}", line, events, memories, lang)
    kinds = dict(_set("change_kind", lang))
    if not h.rupture_open:
        kinds.pop("drive", None)
    if not h.promises:
        kinds.pop("stop_waiting", None)
    steering = [a for a in h.aims if a["kind"] == "intention"]
    for j, line in enumerate(lines_of(reply, "changes", MAX_CHANGES)):
        qs[f"change:{j}:kind"] = _choice("change_kind", lang, kinds, change=line)
        qs[f"change:{j}:sure"] = _choice("sure", lang, grade, text=line)
        if h.beliefs:
            qs[f"change:{j}:belief"] = _choice(
                "belief_target", lang, _options(h.beliefs, "no_belief", lang, "b"), change=line)
        if whom:
            qs[f"change:{j}:about"] = _choice("about_whom", lang, _options(whom, "nobody", lang, "p"), text=line)
            qs[f"change:{j}:reading"] = _choice("reading_kind", lang, _set("reading_kind", lang), text=line)
        if memories:
            qs[f"change:{j}:memory"] = _choice(
                "which_memory", lang, _options(memories, "no_memory", lang, "m"), text=line)
        if steering:
            qs[f"change:{j}:aim"] = _choice(
                "which_aim", lang, _options([a["text"] for a in steering], "no_aim", lang, "a"), text=line)
        if h.promises:
            qs[f"change:{j}:promise"] = _choice(
                "which_promise", lang,
                _options([f"{p.get('what')} ({p.get('from')})" for p in h.promises], "no_promise", lang, "w"),
                text=line)
        _evidence_questions(qs, f"change:{j}", line, events, memories, lang)

    # --- what this mind already holds, moved or settled ---
    moved = _set("aim_moved", lang)
    for k, aim in enumerate(steering):
        qs[f"aim:{k}:moved"] = _choice("aim_moved", lang, moved, aim=_text(aim["text"]))
        if events:
            qs[f"aim:{k}:now"] = _choice("based_now", lang, _options(events, "nothing_now", lang, "e"),
                                         text=_text(aim["text"]))
    touched = dict(_set("belief_touched", lang))
    for k, belief in enumerate(h.beliefs):
        qs[f"belief:{k}:touched"] = _choice("belief_touched", lang, touched, belief=_text(belief))
        if events:
            qs[f"belief:{k}:now"] = _choice("based_now", lang, _options(events, "nothing_now", lang, "e"),
                                            text=_text(belief))
    for k, assoc in enumerate(h.associations):
        qs[f"cue:{k}"] = _choice("cue_present", lang, yesno, cue=_text(assoc["cue"]))
        if events:
            qs[f"cue:{k}:now"] = _choice("based_now", lang, _options(events, "nothing_now", lang, "e"),
                                         text=_text(assoc["cue"]))
    axes = _set("rel_axes", lang)
    signed = _set("signed", lang)
    known = {k.casefold() for k in h.known}
    for p, person in enumerate(people):
        if person.casefold() not in known:
            continue
        for axis in REL_AXES:
            qs[f"rel:{p}:{axis}"] = _choice("rel_axis", lang, signed, person=person, axis=axes[axis])
        qs[f"rel:{p}:break"] = _choice("rel_break", lang, yesno, person=person)
        if events:
            qs[f"rel:{p}:now"] = _choice("based_now", lang, _options(events, "nothing_now", lang, "e"),
                                         text=person)
    for k, concern in enumerate(h.concerns):
        qs[f"concern:{k}"] = _choice("concern_settled", lang, yesno, concern=_text(concern))
    for k, heard in enumerate(h.heard):
        qs[f"keep:{k}"] = _choice("keep_line", lang, yesno, person=heard.get("speaker") or "",
                                  line=_text(heard["text"]))
    shaped = _set("memory_shaped", lang)
    for k, memory in enumerate(memories):
        qs[f"mem:{k}:shaped"] = _choice("memory_shaped", lang, shaped, memory=_text(memory))
    if h.charge >= RELEASE_ASK_FLOOR and (any_do or any_say):
        qs["released"] = _choice("released", lang, yesno)

    # --- the appraisal the engine reads (stress, pain and pleasure, goals) ---
    if events:
        qs["novelty"] = _choice("novelty", lang, grade)
        qs["control"] = _choice("control", lang, grade)
        qs["coping"] = _choice("coping", lang, grade)
        qs["norm"] = _choice("norm", lang, _set("fit", lang))
        qs["self_fit"] = _choice("self_fit", lang, _set("fit", lang))
        qs["pleasant"] = _choice("pleasant", lang, _set("tone", lang))
        for e, event in enumerate(events):
            qs[f"pain:{e}"] = _choice("pain", lang, grade, event=_text(event))
            qs[f"pleasure:{e}"] = _choice("body_pleasure", lang, grade, event=_text(event))
        for a, aim in enumerate(h.aims):
            label = _aim_label(aim, lang)
            qs[f"impact:{a}"] = _choice("impact", lang, _set("impact", lang), aim=label)
            qs[f"impact:{a}:certain"] = _choice("impact_certain", lang, _set("certain", lang), aim=label)
            qs[f"impact:{a}:agency"] = _choice("impact_agency", lang, _set("agency", lang), aim=label)
            qs[f"impact:{a}:now"] = _choice("based_now", lang, _options(events, "nothing_now", lang, "e"),
                                            text=label)
        if memories:
            qs["echo"] = _choice("echo", lang, _options(memories, "no_memory", lang, "m"))
            for k, memory in enumerate(memories):
                qs[f"echo:{k}:familiar"] = _choice("echo_familiar", lang, grade, memory=_text(memory))
                qs[f"echo:{k}:threat"] = _choice("echo_threat", lang, grade, memory=_text(memory))
                qs[f"echo:{k}:coping"] = _choice("echo_coping", lang, _set("ability", lang), memory=_text(memory))
        if h.strategies:
            qs["coping_mode"] = _choice("coping_mode", lang, _options(h.strategies, "no_strategy", lang, "s"))
    return qs


def _evidence_questions(qs, prefix, text, events, memories, lang):
    """Which delivered rows a line rests on: one choice over what just
    reached this mind, one over what it remembers -- each with none."""
    if events:
        qs[f"{prefix}:now"] = _choice("based_now", lang, _options(events, "nothing_now", lang, "e"), text=text)
    if memories:
        qs[f"{prefix}:remembered"] = _choice(
            "based_memory", lang, _options(memories, "nothing_remembered", lang, "m"), text=text)


# --- reading the answers ------------------------------------------------------------

def pick(answers, key):
    """The option the model chose (its most probable), or None."""
    probs = _probabilities(answers.get(key))
    if not probs:
        answer = answers.get(key) or {}
        chosen = answer.get("choice") if isinstance(answer, dict) else None
        return str(chosen) if chosen else None
    return max(probs.items(), key=lambda kv: kv[1])[0]


def yes(answers, key):
    return pick(answers, key) == "yes"


def graded(answers, key, scale):
    """The expected position on `scale`, or None when unanswered."""
    probs = _probabilities(answers.get(key))
    mass = sum(p for k, p in probs.items() if k in scale)
    if mass <= 0:
        return None
    return sum(scale[k] * p for k, p in probs.items() if k in scale) / mass


def indexed(answers, key, prefix, items):
    """The item an `<prefix><i>` choice picked, or None for its none."""
    chosen = pick(answers, key)
    if not chosen or not chosen.startswith(prefix):
        return None
    try:
        i = int(chosen[len(prefix):])
    except ValueError:
        return None
    return items[i] if 0 <= i < len(items) else None


def ask(state, questions):
    """Ask one mind's questions; `{}` for none. Raises
    `decisions.DecisionError` when nothing could be asked."""
    if not questions:
        return {}
    return decisions.decide(state, questions)
