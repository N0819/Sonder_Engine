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
   would discard (`native_failures`), and an act the cast declared that no
   event carries, located by its own words (`declared_gaps`).
3. Jev judges, per sentence, whether it states an occurrence no event
   records; per event and granted channel, whether a change of that
   channel's kind went unwritten; per write, whether it is wrong for its
   event (`prose_contract.check_*` in the card carries each TRUE/FALSE
   condition). Only a confident yes builds a job; anything less is logged.
4. For a write it flags, Jev also says whether its change happens at
   another event, and which; code moves it there, and its fix job follows
   (owner, 2026-09-25: Jev can flag which ledger is wrong -- WHERE, measured,
   yes; WHICH condition fails, measured, no: see `explain_wrong`).
5. The jobs go to the encoder by id -- recovering events and mending writes
   as two calls in parallel -- with the whole draft (the ledgers as
   completed so far) and the roster of things it minted in front of it
   (owner, 2026-09-24: keep the completed ledgers in the encoder's context
   on the repair pass), and every job quoting the sentences that decide it:
   a flagged mistake is the prose's to settle, not the draft's, which can
   repeat it. Jev picks the tools for a missing sentence, and places each
   recovered event among its neighbours. A job skipped is asked once more.
6. Only the repaired writes are checked again, and nothing aborts the turn:
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
#: fails no beat. Named per the owner's ask-before-limiting rule. Set from
#: eight hand-labeled beats (chats 153/154 and the time-travel test story,
#: 2026-09-24, three runs each; Jev's probabilities rarely pass 0.8):
#: a missing event at 0.5 -- precision 0.67, recall 0.50 -- and a missing
#: ledger at 0.5 -- precision 0.46, recall 0.67 -- because a false alarm
#: costs only a job the repair declines: across 24 whole-pass runs the
#: repair declined every false alarm it was handed; a wrong write at 0.8 --
#: precision 1.00, recall 0.78 -- because a correct write sent to be
#: "fixed" can come back changed.
MISSING_EVENT_AT = 0.5
MISSING_LEDGER_AT = 0.5
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
#: The share of a SENTENCE an event must hold as ONE unbroken run of its
#: text to be attributed to it as well -- the event that tells three short
#: sentences at once ("The TARDIS groans. The sound deepens. ... the floor
#: gives a long, rolling lurch", replay of chat 153) is scored best against
#: the longest and holds the other two whole. One run, not scattered
#: trigrams: a short common sentence ("He does not move yet.") shares
#: trigrams with any long event about the same man.
ATTRIBUTION_HOLDS = 0.6


def _grams(text, n=3):
    text = " ".join(str(text or "").casefold().split())
    return {text[i:i + n] for i in range(len(text) - n + 1)} if len(text) >= n else set()


def _holds(event_text, sentence):
    """Does the event's text hold most of the sentence as one unbroken run?"""
    from difflib import SequenceMatcher
    sentence = " ".join(str(sentence or "").casefold().split())
    event_text = " ".join(str(event_text or "").casefold().split())
    if len(sentence) < 3 or not event_text:
        return False
    match = SequenceMatcher(None, sentence, event_text, autojunk=False).find_longest_match(
        0, len(sentence), 0, len(event_text))
    return match.size / len(sentence) >= ATTRIBUTION_HOLDS


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
        held = {j for j, unit in enumerate(units) if _holds(text, unit["text"])}
        near = {j for j in (best - 1, best + 1) if 0 <= j < len(units)
                and scores[j] >= max(ATTRIBUTION_MIN, ATTRIBUTION_SPAN * scores[best])}
        out.append([units[j]["id"] for j in sorted({best} | near | held)])
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


# ---- 2b. declared acts no event carries -----------------------------------------

#: The fields a declaration is found by in the prose, most exact first: a
#: line's own words, an act as it was seen, as it was meant, the player's
#: input as typed. Measured on the three captured drafts that left a
#: declaration uncarried (chat 154 turn 4398's second roll and two turns of
#: the time-travel test story, 2026-09-25): every line's `text` and every
#: act's `observable` landed on the sentence that tells it; an `attempt`
#: landed on the right one in 1 of 3.
_DECLARED_WORDS = ("text", "observable", "attempt", "raw_text")


def declarations(payload):
    """`[{event_id, source, speech, words}]`: every act this beat's
    `event_inputs` declare, with the words it is found by in the prose."""
    out = []
    for entry in (payload or {}).get("event_inputs") or []:
        if not isinstance(entry, dict):
            continue
        for act in entry.get("events") or []:
            if not isinstance(act, dict) or not str(act.get("event_id") or "").strip():
                continue
            words = [str(act[k]).strip() for k in _DECLARED_WORDS
                     if isinstance(act.get(k), str) and act[k].strip()]
            out.append({"event_id": str(act["event_id"]).strip(),
                        "source": str(entry.get("entity_id") or ""),
                        "speech": act.get("type") == "speech", "words": words})
    return out


def declared_gaps(events, units, payload):
    """`[{event_id, source, act, sentences}]`: every declared act no event
    carries -- none names it as its `source_event_id` -- with the sentences
    no event comes from that tell it.

    CERTAIN, AND NO MODEL IS ASKED. An act the cast declared is not replaced
    (the prose contract's own limit), so the prose tells it and the beat
    must carry it; a draft that names no event after it stopped before it.
    Measured on 33 real encoder calls (2026-09-24): it held for 6, all six
    real failures -- five empty answers and one that stopped two acts early
    -- and never for a draft that covered its prose. Where the act lies is
    code's too: its own words, attributed like an event's. A declaration
    whose sentences some event already comes from was encoded under another
    source, which is not a missing event, and one its words place nowhere
    is left to the sentence check -- `sentences` is empty for both."""
    carried = {str(e.get("source_event_id") or "").strip()
               for e in events or [] if isinstance(e, dict)}
    cited = citations(events, units) if units is not None else {}
    gaps = []
    for act in declarations(payload):
        if act["event_id"] in carried:
            continue
        found = []
        for words in act["words"]:
            found = attribute([{"event": words}], units)[0] if units is not None else []
            if found:
                break
        gaps.append({"event_id": act["event_id"], "source": act["source"],
                     "act": _clip(act["words"][0] if act["words"] else "", 300),
                     "sentences": [sid for sid in found if not cited.get(sid)]})
    return gaps


def declared_findings(gaps, confident, identities=None):
    """Jev's findings with every located declaration made certain: its
    sentences become missing-event findings at 1.0, carrying the act, so
    the job built for them says what the cast declared there."""
    by_sentence = {f["sentence"]: f for f in confident if f["kind"] == "event"}
    out = [f for f in confident if f["kind"] != "event"]
    for gap in gaps:
        who = (identities or {}).get(gap["source"]) or gap["source"]
        shown = {"event_id": gap["event_id"], "by": who, "act": gap["act"]}
        for sid in gap["sentences"]:
            finding = dict(by_sentence.get(sid) or {"kind": "event", "sentence": sid})
            finding["p"] = 1.0
            finding["declared"] = list(finding.get("declared") or []) + [shown]
            by_sentence[sid] = finding
    return out + list(by_sentence.values())


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
    identities = names_of(payload)
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


def names_of(payload):
    """`{key: name}` for every person and thing the payload knows -- an
    event's source may be an entity id, shown to Jev by what it is called."""
    names = {}
    for key, value in ((payload or {}).get("identity_index") or {}).items():
        if value:
            names[str(key)] = str(value)
    world = (payload or {}).get("world_index") or {}
    for source in ((payload or {}).get("entities") or {}, world.get("entities") or {}):
        for key, value in source.items() if isinstance(source, dict) else []:
            if isinstance(value, dict) and value.get("name"):
                names.setdefault(str(key), str(value["name"]))
    return names


def _event_line(ref, event, identities=None):
    source = str(event.get("source_entity_id") or "")
    who = (identities or {}).get(source) or source or "-"
    kind = "SAYS" if event.get("speech") else "DOES"
    return f'{ref} ({who} {kind}): "{_clip(event.get("event") or "", 300)}"'


def battery(units, events, channels, language=None, identities=None, parts=None):
    """`{key: noul question}`, every check this draft needs, and `{key:
    what it is about}` for reading the answers back.

    EACH QUESTION CARRIES ITS OWN MATERIAL -- the sentence and the events it
    is compared with, the event and its writes -- rather than naming them for
    Jev to look up in the state. Measured 2026-09-24 on eight labeled beats:
    asked by reference, a sentence event 1 copies word for word still scored
    0.52-0.58 "missing", and an obligation already written scored up to 0.74
    "missing"; the one check that carried its write in the question was the
    one that worked (precision 0.84, recall 0.89)."""
    from llm.prompts import ENCODER_PART_SEP, encoder_definition, encoder_parts
    refs = refs_of(events)
    cited = citations(events, units)
    missing_event = prose_contract_text("check_missing_event", language)
    missing_ledger = prose_contract_text("check_missing_ledger", language)
    wrong_ledger = prose_contract_text("check_wrong_ledger", language)
    definitions = {c: encoder_definition(c, language) for c in channels or ()}
    definitions = {c: d for c, d in definitions.items() if d}
    # A PART IS ASKED BY ITS OWN DEFINITION. The rarer kinds of change a
    # big record holds have parts of their own in the encoder card, and the
    # record's opening does not reach them: asked as `entities`, a ship
    # breaking free of the beach scored 0.37 missing; its transit part
    # says a moving room is moved by its entity's state. Every part of a
    # held record is asked, whatever routing picked -- a missed write is
    # what routing can miss too.
    if parts is None:
        parts = [part for channel in definitions for part in encoder_parts(channel, language)]
    part_definitions = {p: encoder_definition(p, language) for p in parts
                        if p.split(ENCODER_PART_SEP, 1)[0] in definitions}
    part_definitions = {p: d for p, d in part_definitions.items() if d}
    questions, about = {}, {}
    for unit in units:
        if not re.search(r"\w", unit["text"]):
            continue
        own, near = _neighbours(cited, units, unit["id"])
        shown = "; ".join(_event_line(refs[i], events[i], identities)
                          for i in own + near) or "none"
        key = f"ev:{unit['id']}"
        questions[key] = {"type": "noul", "instructions": _fill(
            missing_event, sentence=unit["id"], sentence_text=unit["text"].strip(),
            events=shown)}
        about[key] = {"kind": "event", "sentence": unit["id"]}
    for ref, event in zip(refs, events):
        line = _event_line(ref, event, identities)
        written = {}
        for index, transform in enumerate(event.get("transforms") or []):
            patch = transform.get("patch") if isinstance(transform, dict) else None
            for channel, value in (patch or {}).items() if isinstance(patch, dict) else []:
                written.setdefault(channel, []).append(value)
                if channel not in definitions:
                    continue
                key = f"bad:{ref}:{index}:{channel}"
                questions[key] = {"type": "noul", "instructions": _fill(
                    wrong_ledger, event=line, channel=channel,
                    definition=definitions[channel], write=_clip(value))}
                about[key] = {"kind": "fix", "event": ref, "index": index, "channel": channel}
        # A MISSING LEDGER IS ASKED ONLY WHERE THE EVENT WRITES NOTHING TO IT.
        # Whether a write already records the change is a fact code holds;
        # asked of Jev inside the same question, it was ignored -- events
        # carrying an obligation, a pose or a hatch write scored 0.61-0.78
        # "missing" on 2026-09-24's labeled beats. A write that is present
        # but wrong is the wrong-ledger check's.
        for channel, definition in definitions.items():
            if channel in written:
                continue
            key = f"led:{ref}:{channel}"
            questions[key] = {"type": "noul", "instructions": _fill(
                missing_ledger, event=line, channel=channel, definition=definition)}
            about[key] = {"kind": "ledger", "event": ref, "channel": channel}
        for part, definition in part_definitions.items():
            channel = part.split(ENCODER_PART_SEP, 1)[0]
            if channel in written:
                continue
            key = f"led:{ref}:{part}"
            questions[key] = {"type": "noul", "instructions": _fill(
                missing_ledger, event=line, channel=channel, definition=definition)}
            about[key] = {"kind": "ledger", "event": ref, "channel": channel, "part": part}
    return questions, about


def bridge(confident, cited):
    """A sentence no event comes from, lying between two sentences found
    missing, joins them: one occurrence told across several sentences is
    often judged sentence by sentence, and a line of dialogue cut into
    fragments reads as narration once its quotation marks are elsewhere
    ("Odds are this is the smoothest flight you'll ever have." scored 0.11
    in the middle of a six-sentence line nothing encoded, chat 154 turn
    4398's second roll). Joined, the repair sees the whole span."""
    flagged = sorted(int(f["sentence"][1:]) for f in confident if f["kind"] == "event")
    extra = []
    for low, high in zip(flagged, flagged[1:]):
        gap = [f"s{n}" for n in range(low + 1, high)]
        if gap and all(not cited.get(sid) for sid in gap):
            extra.extend({"kind": "event", "sentence": sid, "p": 0.0, "bridged": True}
                         for sid in gap)
    return list(confident) + extra


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
    # CONSECUTIVE MISSING SENTENCES ARE ONE JOB. One occurrence is often
    # told across several sentences -- a speech the splitter cut at its own
    # stops -- and a job per sentence invites the repair to write it once
    # per sentence (chat 154 turn 4398's second roll: one line of dialogue
    # across six sentences, none encoded).
    runs = []
    for finding in sorted((f for f in confident if f["kind"] == "event"),
                          key=lambda f: int(f["sentence"][1:])):
        n = int(finding["sentence"][1:])
        if runs and n == runs[-1]["last"] + 1:
            runs[-1]["sentences"].append(finding["sentence"])
            runs[-1]["last"] = n
            runs[-1]["p"] = max(runs[-1]["p"], finding["p"])
        else:
            runs.append({"kind": "event", "sentence": finding["sentence"],
                         "sentences": [finding["sentence"]], "last": n, "p": finding["p"]})
        for act in finding.get("declared") or ():
            if act not in runs[-1].setdefault("declared", []):
                runs[-1]["declared"].append(act)
    for run in runs:
        run.pop("last")
    confident = runs + [f for f in confident if f["kind"] != "event"]
    ranked = sorted(confident, key=lambda f: (-f["p"], {"event": 0, "fix": 1, "ledger": 2}[f["kind"]]))
    ledger_jobs = {}
    for finding in ranked:
        if finding["kind"] == "event":
            key = ("event", finding["sentence"])
        elif finding["kind"] == "fix":
            key = ("fix", finding["event"], finding["index"], finding["channel"])
        else:
            key = ("ledger", finding["event"], finding["channel"])
            if (finding["event"], finding["channel"]) in fixing:
                continue
            # A record and its part found missing on one event are one job,
            # carrying the part so the repair holds its rules.
            if key in ledger_jobs:
                if finding.get("part"):
                    ledger_jobs[key].setdefault("parts", [])
                    if finding["part"] not in ledger_jobs[key]["parts"]:
                        ledger_jobs[key]["parts"].append(finding["part"])
                continue
        if key in seen:
            continue
        seen.add(key)
        job = {k: v for k, v in finding.items() if k not in ("key", "part")}
        if finding.get("part"):
            job["parts"] = [finding["part"]]
        if finding["kind"] == "ledger":
            ledger_jobs[key] = job
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


def _job_view(job, units, sources=None):
    """What the repair is shown of one job -- always with the sentences it
    concerns quoted, because the prose decides a flagged mistake, not the
    draft: shown a fix by reference alone, the repair of chat 154 turn 4398
    copied the beach route back in from the draft's other transit writes.
    `sources` maps an event reference to the sentences it encodes."""
    view = {"id": job["id"], "kind": job["kind"]}
    if job["kind"] == "event":
        sentences = job.get("sentences") or [job["sentence"]]
        text = " ".join(u["text"].strip() for u in units if u["id"] in sentences)
        view.update(sentences=sentences, text=text)
        if job.get("declared"):
            view["declared"] = [dict(act) for act in job["declared"]]
    else:
        view.update(event=job["event"], channel=job["channel"])
        sentences = list((sources or {}).get(job["event"]) or [])
        if sentences:
            view.update(sentences=sentences, text=" ".join(
                u["text"].strip() for u in units if u["id"] in sentences))
        if job.get("parts"):
            view["parts"] = list(job["parts"])
        if job["kind"] == "fix":
            view["write"] = job.get("write")
            if job.get("reason"):
                view["reason"] = job["reason"]
    return view


def repair_tools(ctx, stage, units, jobs, model_payload, facts, channels, parts):
    """The tools the targeted encoder holds: whatever the ledger and fix
    jobs name, and for a missing sentence whatever Jev picks for THAT
    sentence -- falling back to the beat's own tools."""
    from llm.prompts import encoder_parts
    from .director_prose import part_channel, select_channels
    tools = [job["channel"] for job in jobs if job["kind"] in ("ledger", "fix")]
    # A record being mended ships whole, parts and all: the transit fixes
    # of chat 154 turn 4398 were answered from the `entities` chunk alone,
    # never saw that a route is not the place a ship set off from, and wrote
    # the beach back in (the re-check still judged them wrong, 0.82-0.86).
    picked_parts = [part for job in jobs for part in job.get("parts") or ()]
    picked_parts += [part for channel in dict.fromkeys(tools)
                     for part in encoder_parts(channel, ctx.language)]
    missing = [sid for job in jobs if job["kind"] == "event"
               for sid in job.get("sentences") or [job["sentence"]]]
    record = {}
    if missing:
        text = " ".join(u["text"].strip() for u in units if u["id"] in missing)
        chosen, routing = select_channels(ctx, stage, text, model_payload, facts)
        record = {"sentences": missing, "selected": chosen, "parts": routing.get("parts"),
                  "seconds": routing.get("seconds"), "failed": routing.get("failed")}
        tools += [c for c in chosen if c in channels or not channels]
        picked_parts += list(routing.get("parts") or [])
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
    sources = dict(zip(refs_of(events), attribute(events, units)))
    payload["jobs"] = [_job_view(job, units, sources) for job in jobs]
    # THE REPAIR KEEPS THE GRAMMAR its role's draft call goes without: its
    # answers bind to their jobs by id, and sent free, GLM 5.2 answered a
    # sixteen-sentence job by re-encoding the whole beat in the draft's own
    # `events` shape, with a brace dropped seven levels deep (chat 154 turn
    # 4398's first roll, 2 of 3 runs, 2026-09-25).
    out = _agent_json("director_specialist", "director_repair", sheet, payload,
                      temperature=0.2, max_tokens=None,
                      response_format="json_schema") or {}
    return merge_answers(out.get("answers"), jobs), list(out.get("notes") or [])


def _job_of(answer_id, job_ids):
    """The job an answer is for: its own id, or the job id it extends with
    a suffix that is not a digit ("j1b", "j1-2" are j1's; "j12" is not)."""
    if answer_id in job_ids:
        return answer_id
    best = ""
    for job_id in job_ids:
        rest = answer_id[len(job_id):] if answer_id.startswith(job_id) else ""
        if rest and not rest[0].isdigit() and len(job_id) > len(best):
            best = job_id
    return best or None


def merge_answers(answers, jobs):
    """One answer per job, however the repair divided it: pieces carrying
    the same id, or the id with a suffix, are joined in the order they came
    -- their events and writes in sequence, the first piece's `after`
    placing the whole group. An answer for no job is kept, to be reported.

    THE REPAIR ANSWERS ONE JOB IN PIECES, and binding the first piece alone
    threw the rest away. Measured over every whole-pass run of 2026-09-24/25
    (eight versions, 198 runs that answered): 30 split an answer -- ten all
    `j1` with one event each; `j1`, `j1b` ... `j1h` -- and 192 of 844
    returned events were dropped, among them both acts the cast declared in
    a 26-sentence job (the time-travel test story, capture 3877)."""
    job_ids = [job["id"] for job in jobs or []]
    merged, order, stray = {}, [], []
    for answer in answers or []:
        if not isinstance(answer, dict):
            continue
        job_id = _job_of(str(answer.get("id") or ""), job_ids)
        if job_id is None:
            stray.append(answer)
            continue
        if job_id not in merged:
            merged[job_id] = dict(answer, id=job_id,
                                  events=list(answer.get("events") or []),
                                  transforms=list(answer.get("transforms") or []))
            order.append(job_id)
            continue
        whole = merged[job_id]
        whole["events"] += list(answer.get("events") or [])
        whole["transforms"] += list(answer.get("transforms") or [])
        whole["remove"] = bool(whole.get("remove") or answer.get("remove"))
        for key in ("move_to", "after", "none"):
            if not str(whole.get(key) or "").strip() and str(answer.get(key) or "").strip():
                whole[key] = answer[key]
    return [merged[job_id] for job_id in order] + stray


def _said_something(answer):
    return bool(answer.get("events") or answer.get("transforms") or answer.get("remove")
                or str(answer.get("move_to") or "").strip()
                or str(answer.get("none") or "").strip())


def _repair_group(ctx, stage, sc, units, events, jobs, channels, parts, model_payload,
                  view, extras, facts, rooms_elsewhere, new_places, base_payload):
    """One repair call for one group of jobs, its one retry, and its writes
    held to its grant. Returns `{answers, notes, tools, retried, stray}`."""
    tools, tool_parts, routing = repair_tools(ctx, stage, units, jobs, model_payload,
                                              facts, channels, parts)
    answers, notes = call_repair(ctx, sc, units, events, jobs, tools, tool_parts,
                                 model_payload, view, extras, rooms_elsewhere, new_places,
                                 base_payload)
    # THE REPAIR CALL STOPS SHORT AS THE ENCODER DOES: on its first runs it
    # answered a fix and skipped the sixteen-sentence event job beside it,
    # answered another with one event where the next run gave twenty-five,
    # and answered three of nine jobs and skipped the four transit fixes in
    # the middle (chat 154 turn 4398, 2026-09-24). Any job left unanswered,
    # or answered with nothing and no reason, is asked ONCE more, alone.
    answered = {str(a.get("id") or ""): a for a in answers if isinstance(a, dict)}
    leftover = [job for job in jobs
                if job["id"] not in answered or not _said_something(answered[job["id"]])]
    retried = []
    if leftover:
        again, more_notes = call_repair(ctx, sc, units, events, leftover, tools, tool_parts,
                                        model_payload, view, extras, rooms_elsewhere,
                                        new_places, base_payload)
        retried = [job["id"] for job in leftover]
        redo = {str(a.get("id") or ""): a for a in again if isinstance(a, dict)}
        answers = [a for a in answers
                   if not (isinstance(a, dict) and str(a.get("id") or "") in redo)]
        answers += list(redo.values())
        notes = list(notes) + list(more_notes)
    # A repair writes only the tools it was granted; anything else is
    # dropped here and said (a first run wrote a doorway edge and a station
    # into an event it was asked to recover).
    granted = set(tools)
    stray = []
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        for holder in [answer] + [e for e in answer.get("events") or [] if isinstance(e, dict)]:
            for transform in holder.get("transforms") or []:
                patch = transform.get("patch") if isinstance(transform, dict) else None
                if not isinstance(patch, dict):
                    continue
                for channel in [c for c in patch if c not in granted]:
                    stray.append(channel)
                    patch.pop(channel, None)
    return {"answers": answers, "notes": list(notes), "retried": retried, "stray": stray,
            "tools": {"channels": tools, "parts": tool_parts,
                      **({"routing": routing} if routing else {})}}


# ---- 4b. what is wrong with a flagged write ---------------------------------

#: WHERE A FLAGGED WRITE'S CHANGE REALLY HAPPENS IS WHAT JEV CAN SAY. Asked
#: WHICH condition a flagged write fails -- its subject, its value, a change
#: its event lacks, another event, another record -- as a six-way choice it
#: answered 0.24-0.65 and called a wrong value a wrong subject; as five
#: yes/no questions it said yes to nearly all of them (0.52-0.80) for every
#: flagged write; and which record a change belongs in came back named even
#: for writes filed in the right one ("location 0.70" for a transit). Which
#: EVENT a misplaced change belongs to it named at 0.90-0.99 where the draft
#: had put it early or late (chat 154 turn 4398, the time-travel test story,
#: 2026-09-25). So that is the one thing asked.
#: The yes-probability that a flagged write's change happens elsewhere...
ELSEWHERE_AT = 0.5
#: ...and how sure the choice of WHERE must be before code moves it: the
#: choice presupposes a move and always names somebody.
MOVE_AT = 0.85


def _choice(answer):
    pick = str((answer or {}).get("choice") or "")
    try:
        confidence = float((answer or {}).get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return pick, round(confidence, 4)


def explain_wrong(ctx, units, events, flagged, channels, identities, payload):
    """`{finding key: {elsewhere, to_event, to_event_p}}`: for each write Jev
    flagged wrong, whether its change happens at another event, and which --
    asked together in ONE request, each question independent."""
    language = ctx.language
    refs = refs_of(events)
    questions = {}
    for finding in flagged:
        ref, index, channel = finding["event"], finding["index"], finding["channel"]
        if ref not in refs:
            continue
        event = events[refs.index(ref)]
        transforms = event.get("transforms") or []
        if index >= len(transforms):
            continue
        write = _clip(((transforms[index] or {}).get("patch") or {}).get(channel))
        others = {r: _event_line(r, events[i], identities)
                  for i, r in enumerate(refs) if r != ref}
        if not others:
            continue
        key = finding["key"]
        questions[f"elsewhere:{key}"] = {"type": "noul", "instructions": _fill(
            prose_contract_text("check_elsewhere", language),
            event=_event_line(ref, event, identities), channel=channel, write=write)}
        questions[f"at:{key}"] = {"type": "choice", "criteria": others, "instructions": _fill(
            prose_contract_text("check_which_event", language),
            event=ref, channel=channel, write=write)}
    if not questions:
        return {}
    answers = decisions.decide(jev_state(units, events, payload), questions)
    out = {}
    for finding in flagged:
        key = finding["key"]
        if f"elsewhere:{key}" not in questions:
            continue
        to_event, to_event_p = _choice(answers.get(f"at:{key}"))
        out[key] = {"elsewhere": round(decisions.probability(answers.get(f"elsewhere:{key}")), 4),
                    "to_event": to_event, "to_event_p": to_event_p}
    return out


def _move_write(events, ref, index, channel, to_ref):
    """`(events, new index)`: the draft with one write moved to the event it
    belongs to, and where it now sits among that event's transforms."""
    events = copy.deepcopy(list(events))
    refs = refs_of(events)
    source = events[refs.index(ref)]
    transform = (source.get("transforms") or [])[index]
    value = (transform.get("patch") or {}).pop(channel, None)
    target = events[refs.index(to_ref)].setdefault("transforms", [])
    target.append({"item": transform.get("item", ""), "patch": {channel: value}})
    return events, len(target) - 1


def act_on_explanations(events, confident, explained, channels=None, language=None):
    """`(events, findings, moved)`: a flagged write whose change happens at
    another event -- both answers sure enough -- is moved there by code, and
    its fix job follows it, so the repair checks its value against the
    sentences it now belongs to. Moving alone put a ship's stray transit
    writes on the event where it commits still carrying the beach route
    (chat 154 turn 4398, 2026-09-25)."""
    moved, kept = [], []
    for finding in confident:
        answer = explained.get(finding.get("key")) if finding["kind"] == "fix" else None
        refs = refs_of(events)
        if not (answer and answer["elsewhere"] >= ELSEWHERE_AT
                and answer["to_event_p"] >= MOVE_AT
                and answer["to_event"] in refs and answer["to_event"] != finding["event"]):
            kept.append(finding)
            continue
        events, index = _move_write(events, finding["event"], finding["index"],
                                    finding["channel"], answer["to_event"])
        moved.append({"from": finding["event"], "to": answer["to_event"],
                      "channel": finding["channel"], "p": answer["to_event_p"]})
        kept.append(dict(finding, event=answer["to_event"], index=index,
                         key=f"moved:{answer['to_event']}:{index}:{finding['channel']}",
                         reason=f"It was on {finding['event']}; the change happens at this "
                                "event, so it was moved here. Make its value what the "
                                "sentences of this event make true."))
    return events, kept, moved


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
    report = {"applied": [], "unanswered": [], "unknown": [], "declined": {}, "empty": []}
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
        new = [e for e in answer.get("events") or [] if isinstance(e, dict)]
        writes = [t for t in answer.get("transforms") or []
                  if isinstance(t, dict) and isinstance(t.get("patch"), dict) and t["patch"]]
        move_to = str(answer.get("move_to") or "")
        moves = job["kind"] == "fix" and move_to in refs and move_to != job.get("event")
        removes = job["kind"] == "fix" and bool(answer.get("remove"))
        if not (new or writes or moves or removes):
            # AN EMPTY ANSWER CHANGES NOTHING. A fix used to drop the old
            # write before looking at what came back, so an answer with no
            # content deleted it (2026-09-24, first repair runs).
            if str(answer.get("none") or "").strip():
                report["declined"][job["id"]] = str(answer["none"])[:300]
            else:
                report["empty"].append(job["id"])
            continue
        if job["kind"] == "event":
            if new:
                for event in new:
                    event.setdefault("sources", list(job.get("sentences") or [job["sentence"]]))
                inserts[job["id"]] = new
                report["applied"].append(job["id"])
            else:
                report["empty"].append(job["id"])
            continue
        target = refs.index(job["event"]) if job["event"] in refs else None
        if target is None:
            report["unknown"].append(job["id"])
            continue
        if job["kind"] == "fix":
            transform = (events[target].get("transforms") or [None] * (job["index"] + 1))[job["index"]]
            if isinstance(transform, dict) and isinstance(transform.get("patch"), dict):
                transform["patch"].pop(job["channel"], None)
            if moves and job.get("write") is not None:
                events[refs.index(move_to)].setdefault("transforms", []).append(
                    {"item": (transform or {}).get("item", ""),
                     "patch": {job["channel"]: job["write"]}})
            elif writes:
                events[target].setdefault("transforms", []).extend(writes)
            report["applied"].append(job["id"])
        elif writes:
            events[target].setdefault("transforms", []).extend(writes)
            report["applied"].append(job["id"])
        else:
            report["empty"].append(job["id"])
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

    identities = names_of(payload)
    questions, about = battery(units, events, channels, ctx.language, identities)
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
    # A DECLARED ACT NO EVENT CARRIES IS CERTAIN, and located by code: its
    # sentences are missing whatever Jev scored them -- asked or not.
    gaps = declared_gaps(events, units, payload)
    if gaps:
        record["declared_gaps"] = [{"event_id": g["event_id"], "sentences": g["sentences"]}
                                   for g in gaps]
        confident = declared_findings(gaps, confident, identities)
    confident = bridge(confident, citations(events, units))
    record["unsure"] = len(unsure)

    # WHAT IS WRONG WITH A FLAGGED WRITE IS JEV'S TO SAY (owner, 2026-09-25:
    # "I don't think it would be particularly hard to get jev to flag which
    # ledger is wrong"). A write it flags went to the repair with no reason
    # while a code-found one carried its schema error; now one more request
    # says which condition fails, and where the change belongs. A change on
    # the wrong event is moved by code -- no model call.
    flagged = [f for f in confident if f["kind"] == "fix" and f.get("key")]
    if flagged:
        t_x = time.time()
        try:
            explained = explain_wrong(ctx, units, events, flagged, channels, identities, payload)
        except Exception as exc:
            explained = {}
            record["explain_failed"] = str(exc)[:300]
        record["explained"] = explained
        record["explain_seconds"] = round(time.time() - t_x, 3)
        events, confident, moved = act_on_explanations(events, confident, explained,
                                                       channels, ctx.language)
        if moved:
            record["moved"] = moved
    record["found"] = [{k: f[k] for k in f if k != "key"} for f in confident]
    record["check_seconds"] = round(time.time() - t1, 3)

    jobs = plan_jobs(native, confident, events)
    record["jobs"] = [{k: v for k, v in job.items() if k != "write"} for job in jobs]
    if not jobs:
        return _declared_left(ctx, stage, events, units, payload, record), record

    # TWO REPAIR CALLS, IN PARALLEL: recovering events writes long answers,
    # mending writes short ones, and one call doing both skipped the short
    # ones in the middle (three of nine jobs answered, chat 154 turn 4398).
    t2 = time.time()
    groups = [g for g in ([j for j in jobs if j["kind"] == "event"],
                          [j for j in jobs if j["kind"] != "event"]) if g]

    def run_group(group):
        return _repair_group(ctx, stage, sc, units, events, group, channels, parts,
                             model_payload, view, extras, facts, rooms_elsewhere,
                             new_places, base_payload)

    if len(groups) > 1:
        import contextvars
        from concurrent.futures import ThreadPoolExecutor
        from .director_prose import _isolated
        with ThreadPoolExecutor(max_workers=len(groups)) as pool:
            futures = [pool.submit(_isolated(contextvars.copy_context()), run_group, group)
                       for group in groups]
            results = [future.result() for future in futures]
    else:
        results = [run_group(groups[0])]
    record["repair_seconds"] = round(time.time() - t2, 3)
    answers_, notes = [], []
    record["tools"] = []
    for result in results:
        answers_ += result["answers"]
        notes += result["notes"]
        record["tools"].append(result["tools"])
        if result["retried"]:
            record.setdefault("retried", []).extend(result["retried"])
        if result["stray"]:
            record.setdefault("dropped_ungranted", [])
            record["dropped_ungranted"] = sorted(set(record["dropped_ungranted"]) | set(result["stray"]))
    if record.get("dropped_ungranted"):
        ctx.add_warning(f"{stage}: repair wrote ungranted {record['dropped_ungranted']}; dropped")
    answers_ = [dict(a, events=strip_markers(a.get("events") or []))
                if isinstance(a, dict) else a for a in answers_]
    record["answers"] = [
        {"id": str(a.get("id") or ""), "events": len(a.get("events") or []),
         "transforms": len(a.get("transforms") or []), "remove": bool(a.get("remove")),
         "move_to": str(a.get("move_to") or ""), "after": str(a.get("after") or ""),
         "none": str(a.get("none") or "")[:200]}
        for a in answers_ if isinstance(a, dict)]
    if notes:
        record["repair_notes"] = [str(n)[:300] for n in notes]
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
    recheck_q, recheck_about = battery(units, repaired, channels, ctx.language, identities)
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
    repaired = [e for e in repaired if isinstance(e, dict)]
    return _declared_left(ctx, stage, repaired, units, payload, record), record


def _declared_left(ctx, stage, events, units, payload, record):
    """The events as they are, with any declared act still carried by none
    of them recorded and said -- the one loss this pass can name for
    certain after it is done."""
    left = [gap["event_id"] for gap in declared_gaps(events, units, payload)]
    if left:
        record["declared_left"] = left
        ctx.add_warning(f"{stage}: no event carries declared act(s) {left}")
    return events
