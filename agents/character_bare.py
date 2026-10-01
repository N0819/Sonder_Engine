"""The bare character contract: a card about being the character, a reply
that carries only what a character can write, and the decision model for
everything else.

The owner, 2026-09-26: "I truly want an as bare bones character prompt as
possible. That still basically does the same thing thanks to jev... except
the character is now mostly reasoning about being the character it's been
given." Mind modelling and cross-turn notes stay the character's, in words
(`notebook`, `note`; `mind/notebook.py`); a short section of the card ships only when a detector
says the moment calls for it (the owner: "we can now gate parts of the
prompts, Jev can detect a disput and insert the disput payload
deterministically").

The only character contract since 2026-09-27 (the owner: "we are fully
committed to decision models on this branch"); the full card that wrote
every field itself, and the kernel that compiled it, are gone. This module
compiles the bare reply and the decision model's answers
(`mind/character_jev.py`) into the `CharacterOutput` shape everything after
the call reads -- validation, grounding, tells, the theory-of-mind caps, the
concealment floors, commit.
"""

from __future__ import annotations

import re

from llm.prompts import bare_character_prompt, character_bare_module, character_jev_options
from mind import affect, affect_pass, notebook
from mind import character_jev as jev

NOTE_CHARS = jev.NOTE_CHARS
#: How many times the reply is put to the decision model before the beat
#: stands on code alone.
READ_BACK_ATTEMPTS = 2


# --- what this mind holds, from its own payload -----------------------------------

def _text(value, n=jev.ITEM_CHARS):
    return jev._text(value, n)


#: The label perception gives the observer itself (`agents/composer.py`: "the
#: observer -> 'you'"). A mind is never one of the people it is with: the
#: bare replay had two lines addressed "to you".
SELF_LABEL = "you"


def _not_self(label, own):
    folded = label.casefold()
    return folded not in (own.casefold(), SELF_LABEL)


def _actor_labels(observations, own):
    out = []
    for o in observations or []:
        if not isinstance(o, dict):
            continue
        label = str(o.get("actor") or "").strip()
        if label and _not_self(label, own) and label not in out:
            out.append(label)
    return out[:jev.MAX_PEOPLE]


def _heard_lines(observations, own):
    """Lines others spoke that reached this mind this beat: the spoken
    percepts (`kind: speech`), never its own."""
    out = []
    for o in observations or []:
        if not isinstance(o, dict) or o.get("standing") or o.get("kind") != "speech":
            continue
        speaker = str(o.get("actor") or "").strip()
        text = ((o.get("observed") or {}).get("text") if isinstance(o.get("observed"), dict)
                else o.get("text"))
        if not _not_self(speaker, own) or not str(text or "").strip():
            continue
        out.append({"ref": str(o.get("observation_id") or ""), "text": _text(text), "speaker": speaker})
    return out[:jev.MAX_HEARD_LINES]


#: The payload's closing keys, in the order they are read, and the memory
#: block's own (owner, 2026-09-28).
PAYLOAD_CLOSES_WITH = ("memory", "perception")
MEMORY_CLOSES_WITH = ("recalled_old_memories", "recent_memories")


def _closing(mapping, last):
    out = {key: value for key, value in mapping.items() if key not in last}
    out.update((key, mapping[key]) for key in last if key in mapping)
    return out


def reading_order(payload):
    """The payload as the character reads it: everything else, then what it
    remembers -- the recalled older memories, then the recent turns -- and
    what reached it just now at the very end.

    THE PRESENT IS READ LAST, nearest the reply, because it is the most
    immediate thing the character has to answer, and the past runs up to it
    in order (owner, 2026-09-28: "Perception should be the very last as it is
    the most imediate concern"; 8 turns of recent memories "and before that
    in the payload 30 recalled older memories"). The order the blind judges
    preferred in round six of the bare-card replay had the moment last too
    (`docs/experiments/BARE_CARD_REPLAY_2026_09_27.md`). Applied to the wire
    payload after every key is in -- the late ones and the dispute section
    included -- so nothing lands after them. Order only: no key is added,
    dropped or changed."""
    if not isinstance(payload, dict):
        return payload
    out = _closing(payload, PAYLOAD_CLOSES_WITH)
    if isinstance(out.get("memory"), dict):
        out["memory"] = _closing(out["memory"], MEMORY_CLOSES_WITH)
    return out


def _delivered_memories(memory_context):
    from agents.character import _delivered_memory_rows
    out, seen = [], set()
    if not isinstance(memory_context, dict):
        return out
    rows, _summaries = _delivered_memory_rows(memory_context)
    for row, ref in rows:
        text = row.get("gist") or row.get("details") or row.get("it_comes_back_to_me")
        if ref in seen or not str(text or "").strip():
            continue
        seen.add(ref)
        out.append({"ref": ref, "text": _text(text), "origin": str(row.get("epistemic_origin") or "")})
    # EVERY DELIVERED MEMORY, not the first twelve. The walk meets the lanes in
    # the payload's order, and with the recent turns ahead of recall the
    # twelve were the recent rows alone: the recalled memories never reached
    # a dispute, an echo or a read-back (owner, 2026-09-28: the recent
    # memories belong in the decision model's run "alongside the 30 recalled
    # older memories").
    return out


def holding_from(name, sheet, payload, observations, memory_context, active, *,
                 language=None, rupture_open=False, reasoning="", notebook_view=None):
    """`jev.Holding` for one mind, read off its own payload only.
    `notebook_view`: the notebook this call shows it (`mind.notebook.view`),
    kinds included -- the payload carries it without them (`for_payload`)."""
    self_ = (payload or {}).get("self") or {}
    psy = (sheet or {}).get("psychology") or {}
    drive = psy.get("drive") or {}
    aims = []
    if str(drive.get("essence") or "").strip():
        aims.append({"kind": "drive", "id": "drive", "text": drive["essence"]})
    steering = {str(i) for i in self_.get("steering_intention_ids") or []}
    for row in self_.get("intentions") or []:
        if isinstance(row, dict) and str(row.get("id") or "") in steering and row.get("intent"):
            aims.append({"kind": "intention", "id": str(row["id"]), "text": row["intent"]})
    for row in self_.get("projects") or []:
        if isinstance(row, dict) and row.get("project"):
            aims.append({"kind": "project", "id": str(row.get("id") or ""), "text": row["project"]})
    # Whole, never cut: a concern is struck and rewritten by the id the view
    # derived from its words (`notebook.concern_text`), and it is written back
    # as it is held. Questions and the state cut it for display.
    concerns = [t for t in (notebook.concern_text(c) for c in (active or {}).get("active_concerns") or []) if t]
    hedonic = (active or {}).get("hedonic") or {}
    return jev.Holding(
        name=name, language=language,
        psychology=affect_pass.psychology_text(sheet),
        events=affect_pass.events_from(observations)[:jev.MAX_EVENTS],
        people=_actor_labels(observations, name),
        known=[str(k) for k in ((payload or {}).get("relationships") or {})],
        memories=_delivered_memories(memory_context),
        aims=aims[:jev.MAX_AIMS],
        beliefs=[_text(b.get("belief")) for b in self_.get("learned_beliefs") or []
                 if isinstance(b, dict) and str(b.get("belief") or "").strip()][:jev.MAX_BELIEFS],
        associations=[a for a in self_.get("learned_associations") or []
                      if isinstance(a, dict) and str(a.get("cue") or "").strip()][:jev.MAX_ASSOCIATIONS],
        concerns=concerns,
        contacts=[{"ref": str(c.get("contact_ref") or ""), "text": _text(c.get("description"))}
                  for c in self_.get("standing_contacts") or [] if isinstance(c, dict)],
        promises=[p for p in self_.get("still_waiting_for") or [] if isinstance(p, dict)],
        strategies=[str(s.get("name") or "") for s in (psy.get("coping") or {}).get("strategies") or []
                    if isinstance(s, dict) and str(s.get("name") or "").strip()],
        heard=_heard_lines(observations, name),
        drive=dict(drive),
        charge=float(hedonic.get("charge") or 0.0),
        rupture_open=bool(rupture_open),
        crisis=bool(self_.get("crisis")),
        reasoning=str(reasoning or ""),
        notebook=dict(notebook_view or {}),
    )


# --- the notebook this call shows ---------------------------------------------------

def notebook_for(stored_state, payload, observations, name, turn_idx, *, absorption=0.0,
                 elapsed_seconds=None):
    """The notebook view this call shows (`mind.notebook.view`), built from
    this mind's own stored state and its own payload. In play: the people it
    perceives and the room it stands in, and anyone or anything named in
    what reached it, in its latest running note, or in the recall it asked
    for last beat -- so a note that is not shown is one `ponder` away."""
    st = stored_state if isinstance(stored_state, dict) else {}
    self_ = (payload or {}).get("self") or {}
    room = ((payload or {}).get("perception") or {}).get("current_room")
    present = _actor_labels(observations, name) + ([room] if isinstance(room, str) and room.strip() else [])
    texts = []
    for o in observations or []:
        if isinstance(o, dict):
            observed = o.get("observed")
            texts.append((observed or {}).get("text") if isinstance(observed, dict) else o.get("text"))
    notes = [n for n in st.get("my_notes") or [] if isinstance(n, dict)]
    if notes:
        texts.append(notes[-1].get("note"))
    ponder = st.get("memory_ponder")
    if isinstance(ponder, dict):
        texts.append(ponder.get("query"))
    active = self_.get("active_state") if isinstance(self_.get("active_state"), dict) else {}
    return notebook.view(st, turn_idx, present=present, texts=[t for t in texts if t],
                         absorption=absorption, elapsed_seconds=elapsed_seconds,
                         concerns=active.get("active_concerns") or [], projects=self_.get("projects") or [])


#: What `self.active_state` carries of the mood as numbers and ledgers. The
#: bare card gives the mood once, as `self.feelings` (`mind/affect_pass.py`),
#: and calls it given; the same mood twice more, as coordinates and as a
#: label, is two representations free to disagree. Measured on ten captured
#: payloads (2026-09-27): 1.3k-2.7k characters a beat.
MOOD_INTERNALS = frozenset(("affect", "mood", "valence", "arousal", "mood_coords", "mood_habits",
                            "mood_clock", "memory_echo", "affect_seconds", "affect_turn", "hedonic",
                            "stress"))


def with_notebook(payload, notebook_view):
    """The payload this call sends, the notebook in place of the four
    renderings it replaces -- `mind_models` and `active_hypotheses` (its
    notes about people and things), `self.projects` and the concerns in
    `self.active_state` (two of its sections): one view, not four copies.
    The mood's internals leave `self.active_state` too (`MOOD_INTERNALS`):
    `self.feelings` is the mood this card is given."""
    out = dict(payload or {})
    self_ = dict(out.get("self") or {})
    self_.pop("projects", None)
    if isinstance(self_.get("active_state"), dict):
        self_["active_state"] = {k: v for k, v in self_["active_state"].items()
                                 if k != "active_concerns" and k not in MOOD_INTERNALS}
    self_["notebook"] = notebook.for_payload(notebook_view)
    out["self"] = self_
    out.pop("mind_models", None)
    out.pop("active_hypotheses", None)
    return out


# --- the card, with its gated sections --------------------------------------------

def modules_for(payload, *, disputed=(), rupture_open=False, rupture_forced=False):
    """The gated sections this beat's payload calls for, in the card's order:
    each ships only when the payload carries what it explains."""
    self_ = (payload or {}).get("self") or {}
    perception = (payload or {}).get("perception") or {}
    decision = (payload or {}).get("decision") or {}
    out = []
    # What the old card said on every beat, now said when it applies: a
    # silence that is someone's act, a turn owed, an offer about this mind,
    # how much to say, composure failing, and the signs given lately.
    if decision.get("they_said_nothing"):
        out.append("their_silence")
    if decision.get("awaiting_your_answer"):
        out.append("answer_owed")
    if decision.get("comes_to_you"):
        out.append("offers")
    if decision.get("speech_budget"):
        out.append("speech_budget")
    if self_.get("crisis"):
        out.append("crisis")
    if self_.get("recent_tells"):
        out.append("tell_variety")
    if self_.get("tell_grounds"):
        out.append("tell_payoff")
    # The engine's own detector found a shape the recent lines keep reusing
    # (`agents.character._self_line_refrain`): the full card's self-repetition
    # clause, said only then.
    if self_.get("recent_self_refrain"):
        out.append("repetition")
    if disputed:
        out.append("dispute")
    if rupture_open:
        out.append("drive_rupture")
        if rupture_forced:
            out.append("drive_rupture_forced")
    if self_.get("project_review"):
        out.append("project_review")
    if self_.get("still_waiting_for"):
        out.append("still_waiting")
    if perception.get("impossible_knowledge"):
        out.append("impossible_knowledge")
    if (payload or {}).get("carried_reports") or self_.get("carried_reports"):
        out.append("carried_reports")
    # Finding the way: the full card's spatial-frame, places and en-route
    # clauses as one class -- the frame rides on nearly every payload.
    if perception.get("spatial_frame"):
        out.append("ways_on")
    return out


def prompt(name, modules, language=None):
    """The bare card for one mind: its core, then each gated section."""
    text = bare_character_prompt(language)
    extra = [character_bare_module(m, language) for m in modules]
    if extra:
        head, sep, tail = text.partition("\n" + _output_line(text))
        text = (head + "\n\n" + "\n\n".join(extra) + sep + tail) if sep else text + "\n\n" + "\n\n".join(extra)
    return text.replace("{name}", name)


def _output_line(text):
    """The card's identity-and-output tail begins at its identity line."""
    for line in text.split("\n"):
        if "{name}" in line:
            return line
    return ""


# --- the answers, compiled into the engine's shape ---------------------------------

def _evidence(answers, prefix, h):
    """The delivered rows a line rests on: `[{event_id, fact}]`, possibly []."""
    out = []
    event = jev.indexed(answers, f"{prefix}:now", "e", h.events)
    if event:
        out.append({"event_id": event["ref"], "fact": _text(event["text"], 240)})
    memory = jev.indexed(answers, f"{prefix}:remembered", "m", h.memories)
    if memory:
        out.append({"event_id": memory["ref"], "fact": _text(memory["text"], 240)})
    return out


def _sure(entry):
    """The character's own sureness as confidence (its kind caps it later)."""
    return notebook.SURE_CONFIDENCE.get(entry.get("sure") or "", notebook.SURE_CONFIDENCE["likely"])


def _mind_note(op, row, claim, confidence, evidence):
    return {"op": op, "id": row["id"], "about_entity": row.get("about") or "",
            "kind": row.get("kind") or "observation", "claim": claim,
            "confidence": round(confidence, 3), "evidence": evidence, "alternatives": []}


def _compile_notebook(reply, answers, h, out, warnings):
    """The reply's notebook entries and the decision model's reading of them,
    routed by what each is (`mind/notebook.py`):

    - what the mind thinks of someone or something -- a new note, a change,
      a strike, and the decision model's nudges on held notes this beat bore
      on -- into `mind_model_updates` (by note id);
    - a reminder into `notebook_ops`;
    - a worry into the concerns, what would settle it carried in its words;
    - a commitment into `project_ops` (adoption: an end outside the doing,
      two at most, on trial until lived into) -- or, with no end to name,
      an intention, because a commitment with no end is a task. One that
      adoption would refuse as circular or crowded out
      (`affect.adoption_refusal`) is kept as an intention too, what would
      finish it in its words: a commitment refused a slot was lost in the
      round-8 chains, and adoption's own warning says to serve it as one.

    A note about someone or something needs a subject and rests on something
    this mind was given, as every reading does; a thought with neither is not
    lost -- it is kept as a reminder in its own words.
    Returns `(notebook_ops, new_concerns, struck_concern_ids)`."""
    shown = jev._view_entries(h)
    subjects = jev.note_subjects(h)
    glue = character_jev_options("note_glue", h.language)
    ops, concerns, struck = [], [], set()
    entries = jev.notebook_entries(reply)
    # The projects adoption will weigh a new one against: those held, less
    # any this reply strikes (closures land before adoptions).
    freed = {e["id"] for e in entries if e["id"] and e["strike"]}
    live = [{"id": row["id"], "project": row.get("note") or ""}
            for row in (h.notebook or {}).get("what_you_are_about") or []
            if isinstance(row, dict) and row.get("id") and row["id"] not in freed]
    for j, entry in enumerate(entries):
        held = shown.get(entry["id"])
        if held:
            section, row = held
            if entry["strike"]:
                if section == "people_and_things":
                    out["mind_model_updates"].append(_mind_note("strike", row, row.get("note") or "", 0.0, []))
                elif section == "to_keep":
                    ops.append({"op": "strike", "id": row["id"]})
                elif section == "on_your_mind":
                    struck.add(row["id"])
                elif section == "what_you_are_about":
                    done = jev.pick(answers, f"nb:{j}:strike") == "done"
                    out["project_ops"].append({"op": "satisfy" if done else "displace", "id": row["id"],
                                               "why": entry["strike"]})
            elif section == "people_and_things":
                evidence = _evidence(answers, f"nb:{j}", h)
                if evidence:
                    out["mind_model_updates"].append(_mind_note("revise", row, entry["note"], _sure(entry), evidence))
                else:
                    warnings.append(f"a changed note rests on nothing this mind was given: {entry['note'][:80]!r}")
            elif section == "to_keep":
                ops.append({"op": "change", "id": row["id"], "note": entry["note"]})
            elif section == "on_your_mind":
                struck.add(row["id"])
                concerns.append(_fill_concern(glue, entry))
            else:
                warnings.append("a project is not reworded: strike it, and take up the one you mean now")
            continue
        if not entry["note"]:
            warnings.append(f"struck {entry['id']!r}, which this mind was not shown")
            continue
        kind = jev.pick(answers, f"nb:{j}:kind") or "keep"
        about = (jev.resolve_about(entry["about"], subjects) or entry["about"]
                 or jev.indexed(answers, f"nb:{j}:about", "p", subjects) or "")
        evidence = _evidence(answers, f"nb:{j}", h)
        if kind == "worry":
            concerns.append(_fill_concern(glue, entry))
        elif kind == "commitment":
            refused = affect.adoption_refusal(live, entry["note"], entry["until"])
            if entry["until"] and refused is None:
                out["project_ops"].append({"op": "adopt", "project": entry["note"],
                                           "satisfied_when": entry["until"], "about": ""})
                live.append({"id": "", "project": entry["note"]})
            elif refused and refused[0] == "restates":
                warnings.append(f"a commitment already held is not taken up again: {entry['note'][:80]!r}")
            else:
                intent = (jev._fill(glue["until"], {"text": entry["note"], "until": entry["until"]})
                          if entry["until"] else entry["note"])
                out["intent_ops"].append({"op": "add", "intent": intent, "why": entry["note"],
                                          "evidence": evidence})
        elif kind == "keep" or not about or not evidence:
            ops.append({"op": "add", "about": about, "note": entry["note"]})
        else:
            out["mind_model_updates"].append({
                "about_entity": about, "kind": kind, "claim": entry["note"],
                "confidence": round(_sure(entry), 3), "evidence": evidence, "alternatives": []})
    # The decision model's reading of the notes in play, asked BEFORE the
    # call (`jev.before_questions`); a note the reply changed or struck
    # itself is the reply's to move.
    written = {e["id"] for e in entries if e["id"]}
    for k, row in enumerate(jev.notes_in_play(h)):
        if row.get("id") in written:
            continue
        toward = notebook.NUDGE_TOWARD.get(jev.pick(answers, f"held:{k}:touched") or "")
        evidence = _evidence(answers, f"held:{k}", h)
        if toward is not None and evidence:
            out["mind_model_updates"].append(_mind_note("nudge", row, row.get("note") or "", toward, evidence))
    return ops, concerns, struck


#: How long a concern's own words, and what would settle it, may run: the
#: replay's characters wrote paragraphs, plans included, into a concern.
CONCERN_CHARS = 240
UNTIL_CHARS = 120


def _fill_concern(glue, entry):
    note = _text(entry.get("note"), CONCERN_CHARS)
    until = _text(entry.get("until"), UNTIL_CHARS)
    return jev._fill(glue["concern"], {"note": note, "until": until}) if until else note


def _distinct_concerns(concerns):
    """Each concern once, by the notebook's own identity for it
    (`notebook.concern_id`: the words, case and spacing aside), first kept
    -- a worry the reply files both as a `changes` line and as a notebook
    entry is one worry. Words merely CLOSE to another's are kept apart: two
    different worries scored 0.40-0.46 on the engine's similarity in the
    round-8 chains, and the one true paraphrase 0.455, so no threshold tells
    them apart. (The copies those chains showed were one concern cut at two
    lengths, which `notebook.concern_text` ended.)"""
    out, seen = [], set()
    for c in concerns:
        key = notebook.concern_id(c.get("text") if isinstance(c, dict) else c)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _named_here(to_text, people):
    """The person here a line's `to` names: an exact label first, else a
    label standing in it as a whole word; None when it names no one here."""
    text = " ".join(str(to_text or "").split())
    if not text:
        return None
    for person in people:
        if person.casefold() == text.casefold():
            return person
    for person in sorted(people, key=len, reverse=True):
        if re.search(r"(?<!\w)" + re.escape(person) + r"(?!\w)", text, re.IGNORECASE):
            return person
    return None


def _outward_part(act, answers, index):
    """What of an act others are given (the observable floor,
    `jev.act_parts`): the parts someone watching could tell, in order. An act
    in one part is given whole. Unread -- the read-back failed -- only its
    first part, where the act's own doing stands and not what it is for: the
    floor must not lean on the model's cooperation, and a motive written in
    `do` sat after the act it explained in every leak measured."""
    parts = jev.act_parts(act)
    if len(parts) < 2:
        return act
    keys = [f"do:{index}:part:{q}" for q in range(len(parts))]
    if not any(k in answers for k in keys):
        return parts[0]
    return ", ".join(part for part, key in zip(parts, keys) if jev.pick(answers, key) != "inner")


def _people_picked(answers, prefix, h, reply_index):
    return [person for p, person in enumerate(h.people) if jev.yes(answers, f"{prefix}:{reply_index}:kept:{p}")]


def compile_bare(reply, answers, h):
    """`(compiled, warnings)`: the bare reply plus the decision model's
    answers, in the `CharacterOutput` shape every reader downstream
    consumes."""
    reply = reply if isinstance(reply, dict) else {}
    answers = answers or {}
    warnings = []

    # --- conduct ---
    sequence, addresses, expects = [], [], False
    speakers = sorted({x["speaker"] for x in h.heard if x.get("speaker")})
    for index, kind, row in jev.steps(reply):
        if kind == "say":
            if any(f"say:{index}:to:{p}" in answers for p in range(len(h.people))):
                targets = [person for p, person in enumerate(h.people)
                           if jev.yes(answers, f"say:{index}:to:{p}")]
            else:
                # Not read back: the line's own `to`, matched against the
                # people here -- a set the engine owns, never a vocabulary.
                named = _named_here(row.get("to"), h.people)
                targets = [named] if named else []
            for person in targets:
                if person not in addresses:
                    addresses.append(person)
            target = targets[0] if targets else None
            hidden = [p for p in _people_picked(answers, "say", h, index) if p not in targets]
            cut = jev.indexed(answers, f"say:{index}:interrupts", "p", speakers) or ""
            expects = expects or jev.yes(answers, f"say:{index}:expects")
            sequence.append({
                "type": "speech", "text": str(row["say"]).strip(),
                # Unread, a voice is an ordinary one (the owner, 2026-09-30:
                # "normal volume should be the default unless specified
                # otherwise"). `pitched` solved at arm's length came out a
                # mutter, so every unmarked line read "under their breath".
                "volume": jev.pick(answers, f"say:{index}:volume") or "normal",
                "tone": str(row.get("how") or "").strip(),
                "visibility": "concealed" if hidden else "overt",
                "conceal_from": hidden,
                "targets": targets,
                "interrupts": cut,
            })
        elif kind == "do":
            act = str(row["do"]).strip()
            seen = jev.pick(answers, f"do:{index}:seen")
            target = jev.indexed(answers, f"do:{index}:target", "p", h.people)
            hidden = [p for p in _people_picked(answers, "do", h, index) if p != target]
            faced = jev.indexed(answers, f"do:{index}:look", "p", h.people)
            swept = jev.pick(answers, f"do:{index}:look") == "around"
            sequence.append({
                "type": "action", "attempt": act,
                # An act that happens only inside the mind is imperceptible
                # (`observable: ''`); the smoke replay's first draft asked
                # "could someone watching see or hear it?" and a man entering
                # an empty schoolhouse was read as unseen. What others are
                # given of an outward act is only what a watcher could tell
                # (`_outward_part`); the Director reads the whole attempt.
                "observable": "" if seen == "inner" else _outward_part(act, answers, index),
                "visibility": "concealed" if hidden else "overt",
                "conceal_from": hidden,
                "targets": [target] if target else [],
                # Where it turns the body (the commit sets the facing from
                # it, `spatial_frames.look_bearing`; `around` is a sweep) and
                # whose words it cuts off (resolved in the interaction loop
                # against who has spoken -- a claim, not an outcome).
                "look": faced or ("around" if swept else ""),
                "interrupts": jev.indexed(answers, f"do:{index}:interrupts", "p", speakers) or "",
            })
        else:
            sequence.append({"type": "ponder", "query": str(row["ponder"]).strip(),
                             "why": str(row.get("why") or "").strip()})

    # --- the choice ---
    serve_keys = [a for a in h.aims]
    wants = []
    for key in ("want", "held_back"):
        text = " ".join(str(reply.get(key) or "").split())
        if not text:
            continue
        serves = "situational"
        chosen = jev.indexed(answers, f"{key}:serves", "a", serve_keys)
        if chosen:
            serves = "drive" if chosen["kind"] == "drive" else chosen["id"]
        urgency = jev.graded(answers, f"{key}:urgency", jev.GRADE)
        wants.append({"want": text[:240], "urgency": round(0.5 if urgency is None else urgency, 3),
                      "serves": serves, "key": key})
    active_state = {"wants": [{k: v for k, v in w.items() if k != "key"} for w in wants]}
    if wants and wants[0]["key"] == "want":
        active_state["enacted_want"] = 0
    held_index = next((i for i, w in enumerate(wants) if w["key"] == "held_back"), None)
    if held_index is not None:
        active_state["suppressed_want"] = held_index

    # --- what changed, and readings of people ---
    out = {"intent_ops": [], "belief_updates": [], "association_updates": [],
           "mind_model_updates": [], "relationship_updates": [], "remember_lines": [],
           "memory_disputes": [], "memory_effects": [], "waiting_ops": [], "contact_ops": [],
           "project_ops": [], "material_effects": []}
    whom = list(dict.fromkeys(h.people + h.known))[:jev.MAX_PEOPLE * 2]
    notebook_ops, new_concerns, struck_concerns = _compile_notebook(reply, answers, h, out, warnings)
    out["notebook_ops"] = notebook_ops
    belief_targets = {}
    steering = [a for a in h.aims if a["kind"] == "intention"]
    hinge = " ".join(str(reply.get("hinge") or "").split())[:240]
    for j, line in enumerate(jev.lines_of(reply, "changes", jev.MAX_CHANGES)):
        kind = jev.pick(answers, f"change:{j}:kind") or "other"
        evidence = _evidence(answers, f"change:{j}", h)
        sure = jev.graded(answers, f"change:{j}:sure", jev.GRADE)
        if kind == "belief":
            held = jev.indexed(answers, f"change:{j}:belief", "b", h.beliefs)
            # A held belief is rewritten only when the pair check says this
            # line IS that belief, changed (`jev.belief_pair_questions`);
            # otherwise -- a different thought, or no check -- the line is a
            # belief of its own and overwrites nothing.
            if held is not None and jev.pick(answers, f"change:{j}:replaces") == "changes":
                belief_targets.setdefault(held, (line, evidence, sure))
            elif evidence:
                out["belief_updates"].append({
                    "belief": line, "operation": "reinforce", "target_belief": "",
                    "confidence": round(0.6 if sure is None else max(0.1, sure), 3),
                    "evidence": evidence})
        elif kind == "reading":
            about = jev.indexed(answers, f"change:{j}:about", "p", whom)
            if about and evidence:
                out["mind_model_updates"].append({
                    "about_entity": about, "kind": jev.pick(answers, f"change:{j}:reading") or "observation",
                    "claim": line, "confidence": round(0.5 if sure is None else sure, 3),
                    "evidence": evidence, "alternatives": []})
        elif kind == "rereading":
            memory = jev.indexed(answers, f"change:{j}:memory", "m", h.memories)
            # The reading must rest on something other than the memory it
            # re-reads (`_ground_observation_citations`).
            support = [e for e in evidence if not memory or e["event_id"] != memory["ref"]]
            if memory and support:
                out["memory_disputes"].append({"memory_ref": memory["ref"], "now_reads": line,
                                               "evidence": support})
        elif kind == "worry":
            new_concerns.append(line)
        elif kind == "aim":
            out["intent_ops"].append({"op": "add", "intent": line, "why": hinge or line,
                                      "evidence": evidence})
        elif kind == "give_up":
            aim = jev.indexed(answers, f"change:{j}:aim", "a", steering)
            if aim:
                out["intent_ops"].append({"op": "abandon", "id": aim["id"], "why": line,
                                          "evidence": evidence})
        elif kind == "stop_waiting":
            promise = jev.indexed(answers, f"change:{j}:promise", "w", h.promises)
            if promise:
                out["waiting_ops"].append({"op": "abandon", "from": promise.get("from") or "",
                                           "what": promise.get("what") or "", "why": line})
        elif kind == "drive" and h.rupture_open:
            out["drive_shift"] = {"essence": line, "expression": str(h.drive.get("expression") or ""),
                                  "taboo": str(h.drive.get("taboo") or ""), "because": hinge or line}

    # --- what this mind already held, moved or settled ---
    for k, aim in enumerate(steering):
        moved = jev.pick(answers, f"aim:{k}:moved")
        op = {"progress": "progress", "blocked": "block", "done": "satisfy",
              "impossible": "nonviable"}.get(moved or "")
        evidence = _evidence(answers, f"aim:{k}", h)
        # A change in where an aim stands rests on something that just
        # happened: with nothing cited, it is not filed (the replay filed
        # 57 intention ops in 20 beats where the full card wrote 15).
        if op and evidence:
            out["intent_ops"].append({"op": op, "id": aim["id"], "why": hinge or _text(aim["text"]),
                                      "evidence": evidence})
    # HELD BELIEFS, BY THE NOTEBOOK'S RULE: the mind changes a belief in its
    # own words -- a `changes` line aimed at it, resting on something this
    # mind was given -- and the decision model's check of the moment only
    # moves the ones the reply left alone, never rewrites one. A revision
    # used to wait for the check to call the belief overturned as well, so
    # a mind's own inference was filed only when the decision model agreed
    # with it; and read against the whole state, which lists every belief,
    # the check leaned to "bore it out" (as the notes did).
    for belief, (line, line_evidence, sure) in belief_targets.items():
        k = h.beliefs.index(belief)
        support = line_evidence or _evidence(answers, f"belief:{k}", h)
        if support:
            out["belief_updates"].append({
                "belief": line, "operation": "revise", "target_belief": belief,
                "confidence": round(0.6 if sure is None else max(0.1, sure), 3), "evidence": support})
        else:
            warnings.append(f"a changed belief rests on nothing this mind was given: {line[:80]!r}")
    for k, belief in enumerate(h.beliefs):
        if belief in belief_targets:
            continue
        touched = jev.pick(answers, f"belief:{k}:touched")
        evidence = _evidence(answers, f"belief:{k}", h)
        if touched in ("confirms", "doubts", "overturns") and evidence:
            out["belief_updates"].append({
                "belief": belief, "operation": "reinforce" if touched == "confirms" else "weaken",
                "target_belief": "",
                # Overturned by what happened: the full weakening step.
                "confidence": 1.0 if touched == "overturns" else jev.BELIEF_SUPPORT, "evidence": evidence})
    # A LEARNED CUE THAT CAME: its reading proved true this time (reinforced)
    # or untrue (weakened -- the full card's `extinguish`); a cue that merely
    # appeared moves nothing. Every appearance used to reinforce, so a
    # learned fear could only ever grow.
    for k, assoc in enumerate(h.associations):
        evidence = _evidence(answers, f"cue:{k}", h)
        if not (jev.yes(answers, f"cue:{k}") and evidence):
            continue
        operation = {"bore_out": "reinforce", "belied": "extinguish"}.get(jev.pick(answers, f"cue:{k}:held") or "")
        if operation:
            out["association_updates"].append({
                "cue": str(assoc["cue"]), "appraisal_bias": str(assoc.get("appraisal_bias") or ""),
                "response_tendency": str(assoc.get("response_tendency") or ""),
                "operation": operation, "amount": jev.ASSOCIATION_STEP, "evidence": evidence})
    known = {k.casefold() for k in h.known}
    for p, person in enumerate(h.people):
        if person.casefold() not in known:
            continue
        step = jev.REL_BREAK_STEP if jev.yes(answers, f"rel:{p}:break") else jev.REL_STEP
        deltas = {}
        for axis in jev.REL_AXES:
            value = jev.graded(answers, f"rel:{p}:{axis}", jev.SIGNED)
            if value and abs(value) >= 0.25:
                deltas[f"{axis}_delta"] = round(value * step, 3)
        if deltas:
            trigger = _evidence(answers, f"rel:{p}", h)
            out["relationship_updates"].append({
                "target_entity": person, **deltas,
                "trigger_event_ids": [e["event_id"] for e in trigger]})
    # A concern ends when what would settle it has happened (the decision
    # model, reading its criterion in its own words) or when the character
    # strikes or rewrites it.
    kept_concerns = [c for k, c in enumerate(h.concerns)
                     if not (k < jev.MAX_CONCERNS and jev.yes(answers, f"concern:{k}"))
                     and notebook.concern_id(c) not in struck_concerns]
    for k, heard in enumerate(h.heard):
        if jev.yes(answers, f"keep:{k}"):
            out["remember_lines"].append({"quote": heard["text"], "why": hinge or heard["text"],
                                          "evidence": [{"event_id": heard["ref"],
                                                        "fact": _text(heard["text"], 240)}]})
    shaped = jev.pick(answers, "mem:shaped") or ""
    if shaped[:1] in ("a", "r") and shaped[1:].isdigit() and int(shaped[1:]) < len(h.memories):
        out["memory_effects"].append({
            "memory_ref": h.memories[int(shaped[1:])]["ref"], "use": "",
            "disposition": "integrated" if shaped[0] == "a" else "resisted", "changed": hinge})
    if jev.pick(answers, "follow"):
        follow = jev.pick(answers, "follow")
        if follow == "stop":
            out["follow_op"] = {"op": "stop", "reason": hinge}
        elif follow.startswith("start") and follow[5:].isdigit() and int(follow[5:]) < len(h.people):
            out["follow_op"] = {"op": "start", "target": h.people[int(follow[5:])], "reason": hinge}
    for c, contact in enumerate(h.contacts):
        if jev.yes(answers, f"contact:{c}") and contact["ref"]:
            out["contact_ops"].append({"op": "remove", "contact_ref": contact["ref"]})

    # --- the appraisal the engine reads ---
    appraisal = _appraisal(answers, h, hinge)
    active_state["active_concerns"] = _distinct_concerns(kept_concerns + new_concerns)
    active_state["stress"] = {"coping_mode": (jev.indexed(answers, "coping_mode", "s", h.strategies) or "")}
    active_state["hedonic"] = {"released": jev.yes(answers, "released")}

    # --- presentation and the loop ---
    manifest = {"surface_demeanor": " ".join(str(reply.get("demeanor") or "").split())[:240], "tells": []}
    for j, tell in enumerate(jev.lines_of(reply, "tells", jev.MAX_TELLS)):
        subtlety = jev.graded(answers, f"tell:{j}:miss", jev.MISS)
        subtlety = 0.5 if subtlety is None else subtlety
        if h.crisis:
            # COMPOSURE FAILING SHOWS: the full card asked the model for a
            # tell no subtler than 0.4 under `self.crisis`; held here instead.
            subtlety = min(subtlety, jev.MISS["noticeable"])
        manifest["tells"].append({
            "cue": tell, "channel": jev.pick(answers, f"tell:{j}:channel") or "seen",
            "subtlety": round(subtlety, 3),
            "betrays": "suppressed_want" if held_index is not None else "undercurrent",
            "because": ""})
    urgency = jev.graded(answers, "urgency", jev.GRADE)
    salience = jev.graded(answers, "salience", jev.GRADE)
    # THE THOUGHT LINE IS NOT CLEARED BY SILENCE. A reply that says nothing of
    # what it went for, held back, why, or what is unsettled makes no claim,
    # so it emits NO record: commit then keeps the earlier one with its own
    # turn stamp (`test_an_omitted_decision_keeps_its_original_turn_stamp`).
    # It used to emit four empty strings -- the explicit clear the full card
    # reserved for a mind that dropped its thought -- and wiped the line on
    # several beats of each concept-lab story run (2026-09-30).
    continuity = {
        "chosen": " ".join(str(reply.get("want") or "").split())[:240],
        "suppressed": " ".join(str(reply.get("held_back") or "").split())[:240],
        "why": hinge,
        "uncertainty": " ".join(str(reply.get("unsure") or "").split())[:240],
    }
    compiled = {
        "appraisal": appraisal,
        "active_state": active_state,
        "sequence": sequence,
        "manifest": manifest,
        "interaction": {"addresses": addresses, "expects_response": expects, "yields_floor": True,
                        "urgency": round(urgency or 0.0, 3),
                        "conversation_complete_for_me": jev.yes(answers, "done_talking")},
        "salience": round(0.5 if salience is None else salience, 3),
        **({"decision_continuity": continuity} if any(continuity.values()) else {}),
        "note": " ".join(str(reply.get("note") or "").split())[:NOTE_CHARS],
        **out,
    }
    return compiled, warnings


def _appraisal(answers, h, hinge):
    """The engine-shaped appraisal the full card asked the model for: the
    six axes, pain and pleasure with a named cause, one impact per live aim,
    and the memory the moment echoes."""
    out = {}
    for key, name, scale in (("novelty", "novelty", jev.GRADE), ("controllability", "control", jev.GRADE),
                             ("coping_potential", "coping", jev.GRADE),
                             ("norm_compatibility", "norm", jev.FIT),
                             ("self_congruence", "self_fit", jev.FIT),
                             ("intrinsic_pleasantness", "pleasant", jev.TONE)):
        value = jev.graded(answers, name, scale)
        if value is not None:
            out[key] = round(value, 3)
    pains = [(jev.graded(answers, f"pain:{e}", jev.GRADE) or 0.0, event) for e, event in enumerate(h.events)]
    pleasures = [(jev.graded(answers, f"pleasure:{e}", jev.GRADE) or 0.0, event)
                 for e, event in enumerate(h.events)]
    pain = max(pains, key=lambda x: x[0], default=(0.0, None))
    pleasure = max(pleasures, key=lambda x: x[0], default=(0.0, None))
    # A named cause is what licenses a magnitude (`resolve_hedonic` reads the
    # `why`): the event the grade came from, in its own words.
    cause = pain[1] if pain[0] >= pleasure[0] else pleasure[1]
    if cause is not None and max(pain[0], pleasure[0]) >= 1 / 3:
        out["somatic_impact"] = {
            "pain": round(pain[0], 3) if pain[0] >= 1 / 3 else 0.0,
            "pleasure": round(pleasure[0], 3) if pleasure[0] >= 1 / 3 else 0.0,
            "why": _text(cause["text"], 240),
            "evidence": [{"event_id": cause["ref"], "fact": _text(cause["text"], 240)}]}
    impacts = []
    for a, aim in enumerate(h.aims):
        impact = jev.graded(answers, f"impact:{a}", jev.IMPACT)
        event = jev.indexed(answers, f"impact:{a}:now", "e", h.events)
        if not impact or abs(impact) < 0.25 or not event:
            continue
        certain = jev.CERTAIN.get(jev.pick(answers, f"impact:{a}:certain") or "", 0.5)
        agency = jev.pick(answers, f"impact:{a}:agency") or "none"
        impacts.append({"serves": "drive" if aim["kind"] == "drive" else aim["id"],
                        "impact": round(impact, 3), "certainty": certain, "agency": agency,
                        "why": _text(event["text"], 240),
                        "evidence": [{"event_id": event["ref"], "fact": _text(event["text"], 240)}]})
    if impacts:
        out["goal_impacts"] = impacts
    echoed = jev.indexed(answers, "echo", "m", h.memories)
    if echoed:
        k = h.memories.index(echoed)
        out["memory_modulation"] = {
            "evidence": [{"event_id": echoed["ref"], "fact": _text(echoed["text"], 240)}],
            "familiarity": round(jev.graded(answers, f"echo:{k}:familiar", jev.GRADE) or 0.0, 3),
            "threat_bias": round(jev.graded(answers, f"echo:{k}:threat", jev.GRADE) or 0.0, 3),
            "coping_effect": round(jev.graded(answers, f"echo:{k}:coping", jev.ABILITY) or 0.0, 3),
            "somatic_echo": round(jev.graded(answers, f"echo:{k}:body", jev.BODY_ECHO) or 0.0, 3),
            "expectation": "", "anticipatory_emotion": "",
            "why": _text(echoed["text"], 240)}
    return out
