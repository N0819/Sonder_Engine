"""The bare character contract: a card about being the character, a reply
that carries only what a character can write, and the decision model for
everything else.

The owner, 2026-09-26: "I truly want an as bare bones character prompt as
possible. That still basically does the same thing thanks to jev... except
the character is now mostly reasoning about being the character it's been
given." Mind modelling and cross-turn notes stay the character's, in words
(`people`, `note`); a short section of the card ships only when a detector
says the moment calls for it (the owner: "we can now gate parts of the
prompts, Jev can detect a disput and insert the disput payload
deterministically").

Selected by the `character_contract` setting ("bare"); the full card
(`prompts/character.txt`, compiled by `agents/character_kernel.py`) stays
the default until the replay comparison has been read. This module compiles
the bare reply and the decision model's answers (`mind/character_jev.py`)
into the same `CharacterOutput` shape the kernel produces, so everything
after the call -- validation, grounding, tells, the theory-of-mind caps, the
concealment floors, commit -- reads one shape whichever card wrote the beat.
"""

from __future__ import annotations

import re

from core.db import get_setting
from llm.prompts import bare_character_prompt, character_bare_module
from mind import affect_pass
from mind import character_jev as jev

#: The setting that selects the contract, and the value that selects this one.
CONTRACT_SETTING = "character_contract"
BARE = "bare"
NOTE_CHARS = jev.NOTE_CHARS
#: How many times the reply is put to the decision model before the beat
#: stands on code alone.
READ_BACK_ATTEMPTS = 2


def enabled():
    return str(get_setting(CONTRACT_SETTING) or "").strip().casefold() == BARE


# --- what this mind holds, from its own payload -----------------------------------

def _text(value, n=jev.ITEM_CHARS):
    return jev._text(value, n)


def _actor_labels(observations, own):
    out = []
    for o in observations or []:
        if not isinstance(o, dict):
            continue
        label = str(o.get("actor") or "").strip()
        if label and label.casefold() != own.casefold() and label not in out:
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
        if speaker.casefold() == own.casefold() or not str(text or "").strip():
            continue
        out.append({"ref": str(o.get("observation_id") or ""), "text": _text(text), "speaker": speaker})
    return out[:jev.MAX_HEARD_LINES]


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
        out.append({"ref": ref, "text": _text(text)})
    return out[:jev.MAX_MEMORIES]


def holding_from(name, sheet, payload, observations, memory_context, active, *,
                 language=None, rupture_open=False, reasoning=""):
    """`jev.Holding` for one mind, read off its own payload only."""
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
    concerns = []
    for c in (active or {}).get("active_concerns") or []:
        text = c.get("text") if isinstance(c, dict) else c
        if str(text or "").strip() and str(text) != "None":
            concerns.append(_text(text))
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
        concerns=concerns[:jev.MAX_CONCERNS],
        contacts=[{"ref": str(c.get("contact_ref") or ""), "text": _text(c.get("description"))}
                  for c in self_.get("standing_contacts") or [] if isinstance(c, dict)],
        promises=[p for p in self_.get("still_waiting_for") or [] if isinstance(p, dict)],
        strategies=[str(s.get("name") or "") for s in (psy.get("coping") or {}).get("strategies") or []
                    if isinstance(s, dict) and str(s.get("name") or "").strip()],
        heard=_heard_lines(observations, name),
        drive=dict(drive),
        charge=float(hedonic.get("charge") or 0.0),
        rupture_open=bool(rupture_open),
        reasoning=str(reasoning or ""),
    )


# --- the card, with its gated sections --------------------------------------------

def modules_for(payload, *, disputed=(), rupture_open=False, rupture_forced=False):
    """The gated sections this beat's payload calls for, in the card's order."""
    self_ = (payload or {}).get("self") or {}
    perception = (payload or {}).get("perception") or {}
    out = []
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


def _people_picked(answers, prefix, h, reply_index):
    return [person for p, person in enumerate(h.people) if jev.yes(answers, f"{prefix}:{reply_index}:kept:{p}")]


def compile_bare(reply, answers, h):
    """`(compiled, warnings)`: the bare reply plus the decision model's
    answers, in the `CharacterOutput` shape `compile_character_kernel`
    returns."""
    reply = reply if isinstance(reply, dict) else {}
    answers = answers or {}
    warnings = []

    # --- conduct ---
    sequence, addresses, expects = [], [], False
    for index, kind, row in jev.steps(reply):
        if kind == "say":
            to = jev.pick(answers, f"say:{index}:to")
            if to is None:
                # Not read back: the line's own `to`, matched against the
                # people here -- a set the engine owns, never a vocabulary.
                target = _named_here(row.get("to"), h.people)
            else:
                target = (h.people[int(to[1:])] if to.startswith("p") and to[1:].isdigit()
                          and int(to[1:]) < len(h.people) else None)
            if target and target not in addresses:
                addresses.append(target)
            hidden = [p for p in _people_picked(answers, "say", h, index) if p != target]
            interrupts = jev.pick(answers, f"say:{index}:interrupts")
            speakers = sorted({x["speaker"] for x in h.heard if x.get("speaker")})
            cut = (speakers[int(interrupts[1:])] if interrupts and interrupts.startswith("p")
                   and interrupts[1:].isdigit() and int(interrupts[1:]) < len(speakers) else "")
            expects = expects or jev.yes(answers, f"say:{index}:expects")
            sequence.append({
                "type": "speech", "text": str(row["say"]).strip(),
                # Unread, a voice is pitched for the one it is said to: loud
                # enough for them and no louder (the engine's own `pitched`).
                "volume": jev.pick(answers, f"say:{index}:volume") or ("pitched" if target else "normal"),
                "tone": str(row.get("how") or "").strip(),
                "visibility": "concealed" if hidden else "overt",
                "conceal_from": hidden,
                "targets": [target] if target else [],
                "interrupts": cut,
            })
        elif kind == "do":
            act = str(row["do"]).strip()
            seen = jev.pick(answers, f"do:{index}:seen")
            target = jev.indexed(answers, f"do:{index}:target", "p", h.people)
            hidden = [p for p in _people_picked(answers, "do", h, index) if p != target]
            sequence.append({
                "type": "action", "attempt": act,
                # An act no one watching could see or hear is an inner act,
                # and an inner act is imperceptible (`observable: ''`).
                "observable": "" if seen == "no" else act,
                "visibility": "concealed" if hidden else "overt",
                "conceal_from": hidden,
                "targets": [target] if target else [],
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
    for j, line in enumerate(jev.lines_of(reply, "people", jev.MAX_READINGS)):
        about = jev.indexed(answers, f"person:{j}:about", "p", whom)
        evidence = _evidence(answers, f"person:{j}", h)
        if not about or not evidence:
            continue
        out["mind_model_updates"].append({
            "about_entity": about, "kind": jev.pick(answers, f"person:{j}:kind") or "observation",
            "claim": line, "confidence": round(jev.graded(answers, f"person:{j}:sure", jev.GRADE) or 0.5, 3),
            "evidence": evidence, "alternatives": []})
    new_concerns, belief_targets = [], {}
    steering = [a for a in h.aims if a["kind"] == "intention"]
    hinge = " ".join(str(reply.get("hinge") or "").split())[:240]
    for j, line in enumerate(jev.lines_of(reply, "changes", jev.MAX_CHANGES)):
        kind = jev.pick(answers, f"change:{j}:kind") or "other"
        evidence = _evidence(answers, f"change:{j}", h)
        sure = jev.graded(answers, f"change:{j}:sure", jev.GRADE)
        if kind == "belief":
            held = jev.indexed(answers, f"change:{j}:belief", "b", h.beliefs)
            if held is not None:
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
        if op:
            evidence = _evidence(answers, f"aim:{k}", h)
            out["intent_ops"].append({"op": op, "id": aim["id"], "why": hinge or _text(aim["text"]),
                                      "evidence": evidence})
    for k, belief in enumerate(h.beliefs):
        touched = jev.pick(answers, f"belief:{k}:touched")
        evidence = _evidence(answers, f"belief:{k}", h)
        if touched == "overturns" and belief in belief_targets:
            line, line_evidence, sure = belief_targets[belief]
            support = line_evidence or evidence
            if support:
                out["belief_updates"].append({
                    "belief": line, "operation": "revise", "target_belief": belief,
                    "confidence": round(0.6 if sure is None else max(0.1, sure), 3), "evidence": support})
        elif touched in ("confirms", "doubts", "overturns") and evidence:
            out["belief_updates"].append({
                "belief": belief, "operation": "reinforce" if touched == "confirms" else "weaken",
                "target_belief": "", "confidence": jev.BELIEF_SUPPORT, "evidence": evidence})
    for k, assoc in enumerate(h.associations):
        evidence = _evidence(answers, f"cue:{k}", h)
        if jev.yes(answers, f"cue:{k}") and evidence:
            out["association_updates"].append({
                "cue": str(assoc["cue"]), "appraisal_bias": str(assoc.get("appraisal_bias") or ""),
                "response_tendency": str(assoc.get("response_tendency") or ""),
                "operation": "reinforce", "amount": jev.ASSOCIATION_STEP, "evidence": evidence})
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
    kept_concerns = [c for k, c in enumerate(h.concerns) if not jev.yes(answers, f"concern:{k}")]
    for k, heard in enumerate(h.heard):
        if jev.yes(answers, f"keep:{k}"):
            out["remember_lines"].append({"quote": heard["text"], "why": hinge or heard["text"],
                                          "evidence": [{"event_id": heard["ref"],
                                                        "fact": _text(heard["text"], 240)}]})
    for k, memory in enumerate(h.memories):
        shaped = jev.pick(answers, f"mem:{k}:shaped")
        if shaped in ("integrated", "resisted", "dismissed"):
            out["memory_effects"].append({"memory_ref": memory["ref"], "use": "",
                                          "disposition": shaped, "changed": hinge})
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
    active_state["active_concerns"] = kept_concerns + new_concerns
    active_state["stress"] = {"coping_mode": (jev.indexed(answers, "coping_mode", "s", h.strategies) or "")}
    active_state["hedonic"] = {"released": jev.yes(answers, "released")}

    # --- presentation and the loop ---
    manifest = {"surface_demeanor": " ".join(str(reply.get("demeanor") or "").split())[:240], "tells": []}
    for j, tell in enumerate(jev.lines_of(reply, "tells", jev.MAX_TELLS)):
        subtlety = jev.graded(answers, f"tell:{j}:miss", jev.MISS)
        manifest["tells"].append({
            "cue": tell, "channel": jev.pick(answers, f"tell:{j}:channel") or "seen",
            "subtlety": round(0.5 if subtlety is None else subtlety, 3),
            "betrays": "suppressed_want" if held_index is not None else "undercurrent",
            "because": ""})
    urgency = jev.graded(answers, "urgency", jev.GRADE)
    salience = jev.graded(answers, "salience", jev.GRADE)
    compiled = {
        "appraisal": appraisal,
        "active_state": active_state,
        "sequence": sequence,
        "manifest": manifest,
        "interaction": {"addresses": addresses, "expects_response": expects, "yields_floor": True,
                        "urgency": round(urgency or 0.0, 3),
                        "conversation_complete_for_me": jev.yes(answers, "done_talking")},
        "salience": round(0.5 if salience is None else salience, 3),
        "decision_continuity": {
            "chosen": " ".join(str(reply.get("want") or "").split())[:240],
            "suppressed": " ".join(str(reply.get("held_back") or "").split())[:240],
            "why": hinge,
            "uncertainty": " ".join(str(reply.get("unsure") or "").split())[:240],
        },
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
            "somatic_echo": 0.0, "expectation": "", "anticipatory_emotion": "",
            "why": _text(echoed["text"], 240)}
    return out
