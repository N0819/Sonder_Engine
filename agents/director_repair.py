"""Check and repair of the prose contract's encoder draft, targeted by Jev.

The prose contract encodes a beat in ONE call, and one call can stop short,
skip an act, or write a ledger wrong. Measured on the owner's own traffic
(2026-09-24): 3 of about 16 resolve calls encoded 0-2 events of a
2,852-5,104 character account -- turn 4398's second roll is one, and why its
ship never left the beach -- and the same beat's resolve call, re-sent, stopped
at 3-4 events in 15 of 53 samples. This pass finds what the draft lacks or
got wrong and has the encoder write exactly that, with the rest of the draft
in front of it.

A CHECK IS ANCHORED ON THE THING IT JUDGES, and each question has one
answerable meaning. Codex's checked encoder (`codex/jev-encoder-contract`)
asked about every channel legal at the stage for every sentence, had Jev
match sentences to events to writes itself, and counted "uncertain" as a
failure: its final runs ended with 220 of 225 ledger findings uncertain, and
1 of 12 real stages finished. Here:

1. The prose is split into sentences (`sentences`), and each event is
   attributed to the sentences its own text comes from (`attribute`) --
   by code, so the draft is the encoder's ordinary call, unchanged. Asking
   the encoder to cite them instead broke its answer outright: GLM 5.2
   opened the beat with an empty event holding every citation (3 of 3
   samples, chat 154 turn 4398, 2026-09-24), and with the field moved
   first it cited nothing (0 of 22 real events).
2. Code finds what is certain: a write the engine's own schema or reader
   would discard (`native_failures`).
3. Jev judges, per sentence, whether it states an occurrence no event
   records; per event and granted channel, whether a change of that
   channel's kind went unwritten; per write, whether it is wrong for its
   event (`prose_contract.check_*` in the card carries each TRUE/FALSE
   condition). Only a confident yes builds a job; anything less is logged.
4. The jobs go to ONE encoder call, by id, with the whole draft -- the
   ledgers as completed so far -- and the roster of things it minted in
   front of it (owner, 2026-09-24: keep the completed ledgers in the
   encoder's context on the repair pass). Jev picks the tools for a missing
   sentence, and places each recovered event among its neighbours.
5. Only the repaired writes are checked again, and nothing aborts the turn:
   whatever stays unresolved is committed with a warning. A user's Stop
   (`Aborted`) is the one thing that propagates.

Settings: `prose_contract_repair` (`0` default: off).
"""

from __future__ import annotations

import copy
import json
import re
import time
from itertools import groupby

from core.db import get_setting
from llm import decisions
from llm.prompts import prose_contract_text, unified_specialist_prompt

REPAIR_SETTING = "prose_contract_repair"
#: The yes-probability at which a check's finding builds a job. Anything
#: below is logged, never acted on: an unsure judgment costs no call and
#: fails no beat. Named per the owner's ask-before-limiting rule.
MISSING_EVENT_AT = 0.8
MISSING_LEDGER_AT = 0.8
WRONG_LEDGER_AT = 0.8
#: A Jev placement below this confidence falls back to the encoder's own
#: `after`, then to sentence order.
PLACEMENT_AT = 0.5
#: Jobs one beat may send to the repair call, most certain first.
MAX_JOBS = 12
#: Characters of one standing record or write shown to Jev.
_SHOWN = 280

_STOPS = ".!?。！？"
_OPENERS = {"“": "”", "‘": "’", "「": "」", "『": "』", "«": "»"}
_CLOSERS_AFTER_STOP = ('"', "'", "”", "’", "」", "』", "»")
_MARKER = re.compile(r"\[s\d+\]\s?")


def enabled() -> bool:
    return str(get_setting(REPAIR_SETTING) or "").strip().casefold() in ("1", "true", "on")


# ---- 1. numbered sentences ------------------------------------------------

def _closes_later(prose, start, mark):
    """Does a straight quote opened at `start` close before the paragraph
    ends? An unmatched `'em` or `'90s` is an apostrophe, not a quotation."""
    for j in range(start + 1, len(prose)):
        ch = prose[j]
        if ch == "\n":
            return False
        if ch == mark:
            before = prose[j - 1]
            after = prose[j + 1] if j + 1 < len(prose) else ""
            if not before.isspace() and not after.isalnum():
                return True
    return False


def sentences(prose):
    """`[{id, start, end, text}]`, lossless: every character of `prose` in
    exactly one sentence, a quotation kept whole with its sentence.

    Codex's `source_units`, with one change: a straight quote only opens a
    quotation when it closes before the paragraph ends, so a stray `'em`
    cannot fold the rest of the passage into one sentence."""
    prose = str(prose or "")
    ends, quote = [], None
    for i, ch in enumerate(prose):
        before = prose[i - 1] if i else ""
        after = prose[i + 1] if i + 1 < len(prose) else ""
        if ch in ("'", "’") and before.isalnum() and after.isalnum():
            continue  # an apostrophe, never a quotation mark
        if quote:
            if ch == quote:
                quote = None
                if before in _STOPS and (not after or after.isspace()):
                    ends.append(i + 1)
            continue
        if ch in _OPENERS:
            quote = _OPENERS[ch]
            continue
        if ch in ('"', "'") and not before.isalnum() and _closes_later(prose, i, ch):
            quote = ch
            continue
        if ch == "\n" or (ch in _STOPS and (not after or after.isspace())):
            ends.append(i + 1)
        elif ch in _CLOSERS_AFTER_STOP and before in _STOPS and (not after or after.isspace()):
            ends.append(i + 1)
    if not ends or ends[-1] != len(prose):
        ends.append(len(prose))
    units, start = [], 0
    for end in sorted(set(ends)):
        if end <= start:
            continue
        piece = prose[start:end]
        if units and not piece.strip():
            units[-1]["end"] = end
            units[-1]["text"] += piece
        else:
            units.append({"id": f"s{len(units) + 1}", "start": start, "end": end,
                          "text": piece})
        start = end
    return units


def numbered(units):
    """The prose with each sentence's address in front of it: `[s1] ...`."""
    out = []
    for unit in units:
        text = unit["text"]
        lead = len(text) - len(text.lstrip())
        out.append(text[:lead] + f"[{unit['id']}] " + text[lead:])
    return "".join(out)


def _walk(value, visit):
    if isinstance(value, str):
        return visit(value)
    if isinstance(value, list):
        return [_walk(item, visit) for item in value]
    if isinstance(value, dict):
        return {key: _walk(item, visit) for key, item in value.items()}
    return value


def strip_markers(events):
    """No sentence address survives into anything the world keeps: the
    encoder was told they are addresses, and a copied one in a spoken line
    would break the line's match to its quotation."""
    out = []
    for event in events or []:
        if not isinstance(event, dict):
            out.append(event)
            continue
        sources = event.get("sources")
        clean = _walk({k: v for k, v in event.items() if k != "sources"},
                      lambda text: _MARKER.sub("", text) if "[s" in text else text)
        if sources is not None:
            clean["sources"] = sources
        out.append(clean)
    return out


def refs_of(events):
    return [f"e{i + 1}" for i in range(len(events or []))]


#: The share of an event's own text a sentence must hold for the event to
#: be attributed to it at all, and the share a neighbouring sentence needs
#: (of the best one's) to be attributed too, for an event told across two.
ATTRIBUTION_MIN = 0.2
ATTRIBUTION_SPAN = 0.6


def _grams(text, n=3):
    text = " ".join(str(text or "").casefold().split())
    return {text[i:i + n] for i in range(len(text) - n + 1)} if len(text) >= n else set()


def attribute(events, units):
    """`[[sentence id, ...] per event]`: the sentences each event's own text
    comes from, by the share of its character trigrams each sentence holds.
    Language-blind (trigrams, not words), and untroubled by the encoder
    reordering acts because each event is scored on its own. Measured on the
    owner's capture 3979 (chat 154 turn 4398): all 17 events' best sentence
    was theirs, 15 of them at 0.87-1.00."""
    sentence_grams = [_grams(unit["text"]) for unit in units]
    out = []
    for event in events or []:
        text = ""
        if isinstance(event, dict):
            text = str(event.get("event") or "") or str(event.get("observable") or "")
        grams = _grams(text)
        if not grams or not units:
            out.append([])
            continue
        scores = [len(grams & g) / len(grams) for g in sentence_grams]
        best = max(range(len(units)), key=lambda j: scores[j])
        if scores[best] < ATTRIBUTION_MIN:
            out.append([])
            continue
        out.append([units[j]["id"] for j in (best - 1, best, best + 1)
                    if 0 <= j < len(units)
                    and (j == best or scores[j] >= max(ATTRIBUTION_MIN,
                                                       ATTRIBUTION_SPAN * scores[best]))])
    return out


def citations(events, units):
    """`{sentence id: [event index, ...]}`, from `attribute`."""
    cited = {unit["id"]: [] for unit in units}
    for index, sources in enumerate(attribute(events, units)):
        for sid in sources:
            if index not in cited[sid]:
                cited[sid].append(index)
    return cited


# ---- 2. what code knows for certain ----------------------------------------

def _named_entities(patches):
    names = {}
    for patch in patches:
        entities = patch.get("entities") if isinstance(patch, dict) else None
        if not isinstance(entities, dict):
            continue
        for key, value in entities.items():
            if isinstance(value, dict) and str(value.get("name") or "").strip():
                names.setdefault(str(key), copy.deepcopy(value))
    return names


def _channel_failure(channel, value, clean, dropped):
    if channel in dropped or channel not in clean:
        return "the engine's schema for this channel would discard it"
    if channel == "sensory_events" and value:
        from world.spatial import normalize_sensory_event
        missing = [i for i, event in enumerate(clean[channel])
                   if normalize_sensory_event(event) is None]
        if missing:
            return ("the engine would discard sensory_events "
                    + ", ".join(f"[{i}]" for i in missing)
                    + ": each needs the room it is in")
    if channel == "stations" and isinstance(value, dict):
        missing = set(value) - set(clean.get(channel) or {})
        if missing:
            return "the engine would discard stations for " + ", ".join(sorted(map(str, missing)))
    if channel == "poses" and isinstance(value, dict):
        fields = {"posture", "support", "relative_to", "relation", "constraint", "detail"}
        empty = [str(subject) for subject, pose in value.items()
                 if isinstance(pose, dict) and pose and not (set(pose) & fields)
                 and set(pose) != {"from_event"}]
        if empty:
            return "these poses carry no pose field: " + ", ".join(sorted(empty))
    return ""


def _native_errors(step, channel, value):
    from llm import schemas
    model = (schemas.StateDiff if channel in schemas._fields(schemas.StateDiff)
             else schemas.SCHEMA_MAP[step])
    try:
        model(**{channel: copy.deepcopy(value)})
    except schemas.ValidationError as exc:
        return ["{}: {}".format(".".join(map(str, error["loc"])), error["msg"])
                for error in exc.errors()]
    except (TypeError, ValueError):
        pass
    return []


def native_failures(events, scene, payload):
    """`[{ref, index, channel, detail}]`: every write the engine's own
    assembly would discard, found with the same identity, hydration, shape
    and owner models the Director's assembly uses. Ported from Codex's
    `inspect_native_writes`; a failure here is certain, so it needs no
    judgment -- only a replacement."""
    from . import director
    from llm import schemas
    from world.causal_program import bind_items
    from .director_prose import ledger_from_events

    identities = (payload or {}).get("identity_index") or {}
    refs = refs_of(events)
    ledgers, _ = ledger_from_events(events)
    owners = {channel: spec["step_key"] for spec in director.SPECIALISTS.values()
              for channel in spec["channels"]}
    rows = []
    for ref, event, ledger in zip(refs, events, ledgers):
        names = dict(zip(ledger["item_ids"], ledger["item_names"]))
        for index, transform in enumerate(event.get("transforms") or []):
            patch = transform.get("patch") if isinstance(transform, dict) else None
            if not isinstance(patch, dict) or not patch:
                continue
            item = director._transform_item_id(
                ledger, transform, next(iter(names), 0), [], ledger["chrono_id"] - 1)
            rows.append({"ref": ref, "transform_index": index,
                         "chrono_id": ledger["chrono_id"], "item_id": item or 0,
                         "object_name": names.get(item, ""),
                         "speech": bool(event.get("speech")),
                         "patch": director._resolve_identity_handles(
                             copy.deepcopy(patch), identities)})
    bound, _, _ = bind_items(rows, scene)
    failures, minted = [], {}
    for _, span_rows in groupby(bound, key=lambda row: row["chrono_id"]):
        span = list(span_rows)
        same_span = {**minted, **_named_entities(row["patch"] for row in span)}
        accepted = []
        for row in span:
            patch = director._hydrate_existing_entity_patch(scene, row["patch"], same_span)
            patch = director._resolve_identity_handles(patch, identities)
            patch = schemas.normalize_causal_patch_shape(patch)
            for channel, value in patch.items():
                step = owners.get(channel)
                clean, dropped = {}, []
                if step not in schemas.SCHEMA_MAP:
                    detail = "no engine schema owns this channel"
                else:
                    try:
                        clean, dropped = schemas.validated_specialist_patch_channels(
                            step, {channel: value})
                        detail = _channel_failure(channel, value, clean, dropped)
                    except (TypeError, ValueError) as exc:
                        detail = "the engine's validation failed: " + str(exc)
                    if detail:
                        errors = _native_errors(step, channel, value)
                        if errors:
                            detail = "the engine's schema would discard it: " + "; ".join(errors)
                if channel == "world_facts" and value and row["speech"]:
                    detail = "a spoken line does not establish objective world_facts"
                if detail:
                    failures.append({"ref": row["ref"], "index": row["transform_index"],
                                     "channel": channel, "detail": detail[:400]})
                else:
                    accepted.append(clean)
        minted.update(_named_entities(accepted))
    return failures


# ---- 3. what Jev judges --------------------------------------------------------

def _clip(value, n=_SHOWN):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= n else text[:n] + "…"


def _subjects(events, identities):
    """Every name and key the beat's events touch, for the standing records
    worth showing."""
    names = {str(v) for v in (identities or {}).values() if v}
    found = set()
    for event in events or []:
        if not isinstance(event, dict):
            continue
        source = str(event.get("source_entity_id") or "")
        found.add(str((identities or {}).get(source) or source))
        found.update(str(x) for x in event.get("item_names") or [])
        found.update(str(x) for x in event.get("targets") or [])
        for transform in event.get("transforms") or []:
            patch = transform.get("patch") if isinstance(transform, dict) else None
            for value in (patch or {}).values() if isinstance(patch, dict) else []:
                if isinstance(value, dict):
                    found.update(str(k) for k in value)
    found.discard("")
    return found | (names & found)


#: Standing slices of the encoder payload shown to Jev as BEFORE THE BEAT,
#: filtered to the subjects the beat touches.
_BEFORE_SLICES = ("positions", "stations", "poses", "attire", "worn_garments",
                  "entities", "active_conditions", "pending_obligations", "contained")


def before_lines(payload, events):
    subjects = _subjects(events, (payload or {}).get("identity_index"))
    folded = {s.casefold() for s in subjects}
    lines = []
    for key in _BEFORE_SLICES:
        value = (payload or {}).get(key)
        if isinstance(value, dict):
            for name, record in value.items():
                if str(name).casefold() in folded:
                    shown = record.get("state") if key == "entities" and isinstance(record, dict) \
                        and record.get("state") else record
                    label = record.get("name") if key == "entities" and isinstance(record, dict) else name
                    lines.append(f"{key}: {label} = {_clip(shown)}")
        elif isinstance(value, list):
            for record in value:
                text = _clip(record)
                if any(s in text for s in subjects):
                    lines.append(f"{key}: {text}")
    contacts = ((payload or {}).get("standing_relations") or {}).get("contacts") or []
    for contact in contacts if isinstance(contacts, list) else []:
        if isinstance(contact, dict) and (str(contact.get("actor")) in subjects
                                          or str(contact.get("target")) in subjects):
            lines.append("contact: {}.{} -> {}.{} ({})".format(
                contact.get("actor"), contact.get("actor_part") or "",
                contact.get("target"), contact.get("target_part") or "",
                contact.get("manner") or ""))
    return lines[:80]


def jev_state(units, events, payload):
    """What every check is judged against: the numbered prose, the draft's
    events in order with their writes, and the standing records of what the
    beat touches."""
    identities = (payload or {}).get("identity_index") or {}
    lines = ["PROSE:"] + [f"[{u['id']}] {u['text'].strip()}" for u in units if u["text"].strip()]
    lines += ["", "EVENTS, in the order they happen:"]
    attributed = attribute(events, units)
    for ref, event, sources in zip(refs_of(events), events, attributed):
        source = str(event.get("source_entity_id") or "")
        who = identities.get(source) or source or "-"
        cites = ", ".join(sources) or "none"
        kind = "SAYS" if event.get("speech") else "DOES"
        lines.append(f"{ref} (cites {cites}) {who} {kind}: {_clip(event.get('event') or '', 400)}")
        for transform in event.get("transforms") or []:
            patch = transform.get("patch") if isinstance(transform, dict) else None
            for channel, value in (patch or {}).items() if isinstance(patch, dict) else []:
                lines.append(f"   writes {channel}: {_clip(value)}")
    before = before_lines(payload, events)
    lines += ["", "BEFORE THE BEAT:"] + (before or ["(nothing recorded for these subjects)"])
    return "\n".join(lines)


def _neighbours(cited, units, sid):
    """Refs of the events citing this sentence, and of those citing the
    sentences either side -- an event cited one sentence off is still
    compared."""
    order = [u["id"] for u in units]
    at = order.index(sid)
    own = cited.get(sid) or []
    near = []
    for other in order[max(0, at - 1):at + 2]:
        if other != sid:
            near.extend(i for i in cited.get(other) or [] if i not in own and i not in near)
    return own, near


def _fill(text, **values):
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def battery(units, events, channels, language=None):
    """`{key: noul question}`, every check this draft needs, and `{key:
    what it is about}` for reading the answers back."""
    from llm.prompts import jev_channel_questions
    refs = refs_of(events)
    cited = citations(events, units)
    missing_event = prose_contract_text("check_missing_event", language)
    missing_ledger = prose_contract_text("check_missing_ledger", language)
    wrong_ledger = prose_contract_text("check_wrong_ledger", language)
    kinds = jev_channel_questions(list(channels or ()), language)
    questions, about = {}, {}
    for unit in units:
        if not re.search(r"\w", unit["text"]):
            continue
        own, near = _neighbours(cited, units, unit["id"])
        shown = ", ".join(refs[i] for i in own + near) or "none"
        key = f"ev:{unit['id']}"
        questions[key] = {"type": "noul", "instructions": _fill(
            missing_event, sentence=unit["id"], events=shown)}
        about[key] = {"kind": "event", "sentence": unit["id"]}
    for ref, event in zip(refs, events):
        written = {}
        for index, transform in enumerate(event.get("transforms") or []):
            patch = transform.get("patch") if isinstance(transform, dict) else None
            for channel, value in (patch or {}).items() if isinstance(patch, dict) else []:
                written.setdefault(channel, []).append(index)
                if channel not in kinds:
                    continue
                key = f"bad:{ref}:{index}:{channel}"
                questions[key] = {"type": "noul", "instructions": _fill(
                    wrong_ledger, event=ref, channel=channel, question=kinds[channel],
                    write=_clip(value))}
                about[key] = {"kind": "fix", "event": ref, "index": index, "channel": channel}
        for channel, question in kinds.items():
            key = f"led:{ref}:{channel}"
            questions[key] = {"type": "noul", "instructions": _fill(
                missing_ledger, event=ref, channel=channel, question=question)}
            about[key] = {"kind": "ledger", "event": ref, "channel": channel}
    return questions, about


_AT = {"event": MISSING_EVENT_AT, "ledger": MISSING_LEDGER_AT, "fix": WRONG_LEDGER_AT}


def findings(about, answers):
    """`(confident, unsure)`: the checks answered yes at their threshold,
    and those answered between 0.5 and it, each with its probability."""
    confident, unsure = [], []
    for key, what in about.items():
        p = round(decisions.probability((answers or {}).get(key)), 4)
        if p >= _AT[what["kind"]]:
            confident.append(dict(what, key=key, p=p))
        elif p >= 0.5:
            unsure.append(dict(what, key=key, p=p))
    return confident, unsure


# ---- 4. targeted jobs -------------------------------------------------------------

def plan_jobs(native, confident, events):
    """The jobs for ONE repair call, most certain first, at most `MAX_JOBS`.
    A write both certain-bad and judged bad is one job; a ledger job for a
    channel whose write on the same event is being fixed is subsumed."""
    refs = refs_of(events)
    jobs, seen = [], set()
    # A fix rewrites that channel's write on its event, which covers a
    # missing part of the same change -- whichever finding scored higher.
    fixing = ({(f["ref"], f["channel"]) for f in native}
              | {(f["event"], f["channel"]) for f in confident if f["kind"] == "fix"})
    for failure in native:
        key = ("fix", failure["ref"], failure["index"], failure["channel"])
        if key in seen:
            continue
        seen.add(key)
        jobs.append({"kind": "fix", "event": failure["ref"], "index": failure["index"],
                     "channel": failure["channel"], "reason": failure["detail"], "p": 1.0})
    ranked = sorted(confident, key=lambda f: (-f["p"], {"event": 0, "fix": 1, "ledger": 2}[f["kind"]]))
    for finding in ranked:
        if finding["kind"] == "event":
            key = ("event", finding["sentence"])
        elif finding["kind"] == "fix":
            key = ("fix", finding["event"], finding["index"], finding["channel"])
        else:
            key = ("ledger", finding["event"], finding["channel"])
            if (finding["event"], finding["channel"]) in fixing:
                continue
        if key in seen:
            continue
        seen.add(key)
        job = {k: v for k, v in finding.items() if k not in ("key",)}
        jobs.append(job)
    jobs = jobs[:MAX_JOBS]
    for n, job in enumerate(jobs, 1):
        job["id"] = f"j{n}"
        if job["kind"] == "fix":
            event = events[refs.index(job["event"])]
            transform = (event.get("transforms") or [])[job["index"]]
            job["write"] = copy.deepcopy((transform.get("patch") or {}).get(job["channel"]))
    return jobs


def _minted(events):
    """`{key: name}` for every thing the draft mints."""
    out = {}
    for event in events or []:
        for transform in (event.get("transforms") or []) if isinstance(event, dict) else []:
            patch = transform.get("patch") if isinstance(transform, dict) else None
            entities = (patch or {}).get("entities") if isinstance(patch, dict) else None
            for key, value in (entities or {}).items() if isinstance(entities, dict) else []:
                if isinstance(value, dict) and str(value.get("name") or "").strip():
                    out.setdefault(str(key), str(value["name"]))
    return out


def _draft(events, units):
    return [dict(copy.deepcopy(event), ref=ref, sources=sources)
            for ref, event, sources in zip(refs_of(events), events, attribute(events, units))]


def _job_view(job, units):
    view = {"id": job["id"], "kind": job["kind"]}
    if job["kind"] == "event":
        text = next((u["text"].strip() for u in units if u["id"] == job["sentence"]), "")
        view.update(sentence=job["sentence"], text=text)
    else:
        view.update(event=job["event"], channel=job["channel"])
        if job["kind"] == "fix":
            view["write"] = job.get("write")
            if job.get("reason"):
                view["reason"] = job["reason"]
    return view


def repair_tools(ctx, stage, units, jobs, model_payload, facts, channels, parts):
    """The tools the targeted encoder holds: whatever the ledger and fix
    jobs name, and for a missing sentence whatever Jev picks for THAT
    sentence -- falling back to the beat's own tools."""
    from .director_prose import part_channel, select_channels
    tools = [job["channel"] for job in jobs if job["kind"] in ("ledger", "fix")]
    picked_parts = []
    missing = [job["sentence"] for job in jobs if job["kind"] == "event"]
    record = {}
    if missing:
        text = " ".join(u["text"].strip() for u in units if u["id"] in missing)
        chosen, routing = select_channels(ctx, stage, text, model_payload, facts)
        record = {"sentences": missing, "selected": chosen, "parts": routing.get("parts"),
                  "seconds": routing.get("seconds"), "failed": routing.get("failed")}
        tools += [c for c in chosen if c in channels or not channels]
        picked_parts = list(routing.get("parts") or [])
    tools = list(dict.fromkeys(t for t in tools if t))
    if not tools:
        tools = list(channels)
    parts = [p for p in dict.fromkeys(list(parts or []) + picked_parts)
             if part_channel(p) in tools]
    return tools, parts, record


def call_repair(ctx, sc, units, events, jobs, tools, parts, model_payload, view, extras,
                rooms_elsewhere=False, new_places=None, base_payload=None):
    """One encoder call for every job, with the completed draft in front of it.
    `base_payload` stands in for the slices the stage would assemble -- a
    replay of a captured encoder call has them and nothing to rebuild them
    from."""
    from .director_prose import _agent_json, encoder_payload
    language = ctx.language
    sheet = unified_specialist_prompt(tools, language, parts)
    sheet += "\n" + prose_contract_text("encoder_repair", language)
    payload = (dict(base_payload, prose=numbered(units)) if base_payload is not None
               else encoder_payload(ctx, sc, numbered(units), model_payload, view, extras, tools))
    payload["places_authored_elsewhere"] = bool(rooms_elsewhere)
    payload["new_places"] = dict(new_places or {})
    payload["granted_tools"] = list(tools) + list(parts)
    payload["draft"] = _draft(events, units)
    payload["minted"] = _minted(events)
    payload["jobs"] = [_job_view(job, units) for job in jobs]
    out = _agent_json("director_specialist", "director_repair", sheet, payload,
                      temperature=0.2, max_tokens=None) or {}
    return list(out.get("answers") or []), list(out.get("notes") or [])


# ---- 5. placing and applying -------------------------------------------------

def _window(cited, units, sid):
    """Indexes of the events citing this sentence and its two neighbours,
    in draft order."""
    order = [u["id"] for u in units]
    at = order.index(sid) if sid in order else 0
    found = set()
    for other in order[max(0, at - 1):at + 2]:
        found.update(cited.get(other) or [])
    return sorted(found)


def _sentence_slot(cited, units, sid):
    """Default placement: after the last event citing an earlier sentence
    or this one; before everything when none does."""
    order = [u["id"] for u in units]
    at = order.index(sid) if sid in order else len(order)
    earlier = [i for other in order[:at + 1] for i in cited.get(other) or []]
    return max(earlier) if earlier else -1


def place(ctx, units, events, groups):
    """`{job id: index the group goes after (-1 = first)}`. Jev chooses
    among the slots around the events of the sentence and its neighbours;
    below `PLACEMENT_AT` the encoder's own `after`, then sentence order."""
    refs = refs_of(events)
    cited = citations(events, units)
    question_text = prose_contract_text("check_placement", ctx.language)
    battery_, options, slots = {}, {}, {}
    for job_id, group in groups.items():
        sid = group["sentence"]
        window = _window(cited, units, sid)
        default = _sentence_slot(cited, units, sid)
        after = group.get("after")
        if after in refs:
            default = refs.index(after)
        slots[job_id] = default
        if not window:
            continue
        criteria = {f"before_{refs[window[0]]}": f"before {refs[window[0]]}"}
        for i in window:
            criteria[f"after_{refs[i]}"] = f"after {refs[i]}"
        options[job_id] = {key: (window[0] - 1 if key.startswith("before_")
                                 else refs.index(key[len("after_"):])) for key in criteria}
        text = " ".join(_clip(e.get("event") or "", 200) for e in group["events"])
        battery_[f"place:{job_id}"] = {"type": "choice", "instructions": _fill(
            question_text, event=text, sentence=sid), "criteria": criteria}
    if not battery_:
        return slots, {}
    state = jev_state(units, events, {})
    try:
        answers = decisions.decide(state, battery_)
    except Exception as exc:
        return slots, {"failed": str(exc)}
    chosen = {}
    for job_id in options:
        answer = answers.get(f"place:{job_id}") or {}
        pick = str(answer.get("choice") or "")
        try:
            confidence = float(answer.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        chosen[job_id] = {"choice": pick, "confidence": round(confidence, 4)}
        if pick in options[job_id] and confidence >= PLACEMENT_AT:
            slots[job_id] = options[job_id][pick]
    return slots, chosen


def apply_answers(events, units, jobs, answers, slots):
    """The draft with every answered job applied: writes added to their
    event, wrong writes replaced, removed or moved, recovered events
    inserted after their slot. Returns `(events, report)`."""
    events = copy.deepcopy(list(events))
    refs = refs_of(events)
    by_id = {job["id"]: job for job in jobs}
    report = {"applied": [], "unanswered": [], "unknown": [], "declined": {}}
    inserts = {}
    seen = set()
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        job = by_id.get(str(answer.get("id") or ""))
        if job is None:
            report["unknown"].append(str(answer.get("id") or ""))
            continue
        if job["id"] in seen:
            continue
        seen.add(job["id"])
        if str(answer.get("none") or "").strip() and not (
                answer.get("events") or answer.get("transforms") or answer.get("remove")
                or answer.get("move_to")):
            report["declined"][job["id"]] = str(answer["none"])[:300]
            continue
        if job["kind"] == "event":
            new = [e for e in answer.get("events") or [] if isinstance(e, dict)]
            if new:
                for event in new:
                    event.setdefault("sources", [job["sentence"]])
                inserts[job["id"]] = new
                report["applied"].append(job["id"])
            continue
        target = refs.index(job["event"]) if job["event"] in refs else None
        if target is None:
            report["unknown"].append(job["id"])
            continue
        writes = [t for t in answer.get("transforms") or []
                  if isinstance(t, dict) and isinstance(t.get("patch"), dict) and t["patch"]]
        if job["kind"] == "fix":
            transform = (events[target].get("transforms") or [None] * (job["index"] + 1))[job["index"]]
            if isinstance(transform, dict) and isinstance(transform.get("patch"), dict):
                transform["patch"].pop(job["channel"], None)
            move_to = str(answer.get("move_to") or "")
            if move_to in refs and move_to != job["event"] and job.get("write") is not None:
                events[refs.index(move_to)].setdefault("transforms", []).append(
                    {"item": (transform or {}).get("item", ""),
                     "patch": {job["channel"]: job["write"]}})
            elif writes:
                events[target].setdefault("transforms", []).extend(writes)
            report["applied"].append(job["id"])
        else:
            if writes:
                events[target].setdefault("transforms", []).extend(writes)
                report["applied"].append(job["id"])
    for event in events:
        if isinstance(event, dict) and event.get("transforms"):
            event["transforms"] = [t for t in event["transforms"]
                                   if not (isinstance(t, dict) and isinstance(t.get("patch"), dict)
                                           and not t["patch"])]
    report["unanswered"] = [job["id"] for job in jobs if job["id"] not in seen]
    # Insert from the back so earlier slots keep their indexes; a group whose
    # slot is -1 goes first. Two groups after one event keep job order.
    after = {}
    for job_id, new in inserts.items():
        after.setdefault(slots.get(job_id, len(events) - 1), []).append(new)
    out = []
    for group in after.get(-1, []):
        out.extend(group)
    for i, event in enumerate(events):
        out.append(event)
        for group in after.get(i, []):
            out.extend(group)
    return out, report


# ---- 6. the pass ---------------------------------------------------------------------

def _changed_writes(before, after):
    """`{(ref, index, channel)}` of writes in `after` that `before` lacks."""
    def keys(events):
        out = set()
        for ref, event in zip(refs_of(events), events):
            for index, transform in enumerate(event.get("transforms") or []):
                patch = transform.get("patch") if isinstance(transform, dict) else None
                for channel, value in (patch or {}).items() if isinstance(patch, dict) else []:
                    out.add((json.dumps(event.get("event"), ensure_ascii=False), channel,
                             json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)))
        return out
    old = keys(before)
    fresh = set()
    for ref, event in zip(refs_of(after), after):
        for index, transform in enumerate(event.get("transforms") or []):
            patch = transform.get("patch") if isinstance(transform, dict) else None
            for channel, value in (patch or {}).items() if isinstance(patch, dict) else []:
                sig = (json.dumps(event.get("event"), ensure_ascii=False), channel,
                       json.dumps(value, sort_keys=True, ensure_ascii=False, default=str))
                if sig not in old:
                    fresh.add((ref, index, channel))
    return fresh


def check_and_repair(ctx, stage, sc, units, events, channels, parts, model_payload,
                     view, extras, facts=None, rooms_elsewhere=False, new_places=None,
                     base_payload=None):
    """`(events, record)`. Never raises except for a user's Stop: any
    failure returns the draft as it came, with a warning."""
    from llm.providers import Aborted
    record = {"sentences": len(units)}
    t0 = time.time()
    try:
        events, record = _check_and_repair(
            ctx, stage, sc, units, events, channels, parts, model_payload, view, extras,
            facts, rooms_elsewhere, new_places, record, base_payload)
    except Aborted:
        raise
    except Exception as exc:
        record["failed"] = f"{type(exc).__name__}: {exc}"[:400]
        ctx.add_warning(f"{stage}: encoder check failed, draft kept as encoded: {exc}")
    record["seconds"] = round(time.time() - t0, 3)
    return events, record


def _check_and_repair(ctx, stage, sc, units, events, channels, parts, model_payload,
                      view, extras, facts, rooms_elsewhere, new_places, record,
                      base_payload=None):
    from .director_prose import encoder_payload
    events = [e for e in events or [] if isinstance(e, dict)]
    cited = citations(events, units)
    record["cited"] = sum(1 for sid in cited if cited[sid])
    payload = (dict(base_payload) if base_payload is not None
               else encoder_payload(ctx, sc, numbered(units), model_payload, view, extras,
                                    channels))

    t1 = time.time()
    try:
        native = native_failures(events, sc, payload)
    except Exception as exc:
        native = []
        record["native_failed"] = str(exc)[:300]
    record["native"] = native

    questions, about = battery(units, events, channels, ctx.language)
    record["questions"] = len(questions)
    state = jev_state(units, events, payload)
    try:
        answers = decisions.decide(state, questions)
    except Exception as exc:
        # Unreachable Jev is a lost check, never a lost beat: act on what
        # code found for certain and say the rest was not checked.
        answers = {}
        record["jev_failed"] = str(exc)[:300]
        ctx.add_warning(f"{stage}: encoder check could not ask the decision model: {exc}")
    confident, unsure = findings(about, answers)
    record["found"] = [{k: f[k] for k in f if k != "key"} for f in confident]
    record["unsure"] = len(unsure)
    record["check_seconds"] = round(time.time() - t1, 3)

    jobs = plan_jobs(native, confident, events)
    record["jobs"] = [{k: v for k, v in job.items() if k != "write"} for job in jobs]
    if not jobs:
        return events, record

    t2 = time.time()
    tools, tool_parts, routing = repair_tools(ctx, stage, units, jobs, model_payload,
                                              facts, channels, parts)
    record["tools"] = {"channels": tools, "parts": tool_parts, **({"routing": routing} if routing else {})}
    answers_, notes = call_repair(ctx, sc, units, events, jobs, tools, tool_parts,
                                  model_payload, view, extras, rooms_elsewhere, new_places,
                                  base_payload)
    record["repair_seconds"] = round(time.time() - t2, 3)
    answers_ = [dict(a, events=strip_markers(a.get("events") or []))
                if isinstance(a, dict) else a for a in answers_]
    groups = {}
    for answer in answers_:
        job = next((j for j in jobs if isinstance(answer, dict)
                    and j["id"] == str(answer.get("id") or "") and j["kind"] == "event"), None)
        if job and answer.get("events"):
            groups[job["id"]] = {"sentence": job["sentence"], "events": answer["events"],
                                 "after": str(answer.get("after") or "")}
    slots, placed = place(ctx, units, events, groups) if groups else ({}, {})
    if placed:
        record["placed"] = placed
    repaired, report = apply_answers(events, units, jobs, answers_, slots)
    record["applied"] = report
    for note in notes:
        ctx.add_warning(f"encoder repair: {note}")

    # ONLY THE REPAIRED WRITES ARE CHECKED AGAIN. A new write the engine
    # would discard is dropped here rather than later, silently; one Jev
    # still judges wrong is kept and said.
    fresh = _changed_writes(events, repaired)
    try:
        bad = native_failures(repaired, sc, payload)
    except Exception:
        bad = []
    dropped = []
    for failure in bad:
        key = (failure["ref"], failure["index"], failure["channel"])
        if key not in fresh:
            continue
        event = repaired[refs_of(repaired).index(failure["ref"])]
        transform = event["transforms"][failure["index"]]
        transform["patch"].pop(failure["channel"], None)
        dropped.append(dict(failure))
    if dropped:
        record["dropped"] = dropped
        ctx.add_warning(f"{stage}: repair wrote {len(dropped)} write(s) the engine would "
                        "discard; dropped")
    recheck_q, recheck_about = battery(units, repaired, channels, ctx.language)
    recheck_q = {k: v for k, v in recheck_q.items()
                 if recheck_about[k]["kind"] == "fix"
                 and (recheck_about[k]["event"], recheck_about[k]["index"],
                      recheck_about[k]["channel"]) in fresh}
    if recheck_q:
        try:
            again = decisions.decide(jev_state(units, repaired, payload), recheck_q)
            still, _ = findings({k: recheck_about[k] for k in recheck_q}, again)
        except Exception as exc:
            still = []
            record["recheck_failed"] = str(exc)[:300]
        if still:
            record["still_wrong"] = [{k: f[k] for k in f if k != "key"} for f in still]
            ctx.add_warning(f"{stage}: {len(still)} repaired write(s) still judged wrong; "
                            "kept as written")
    for job_id in report["unanswered"]:
        ctx.add_warning(f"{stage}: encoder repair left job {job_id} unanswered")
    return [e for e in repaired if isinstance(e, dict)], record
