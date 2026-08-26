"""Sparse LLM-compiled history for characters whose lives follow an itinerary.

This is not Charter with the rooms removed.  A journey is an ordered ledger of
world visits and consequential intersections.  Canon mode accepts only cited
card/lore evidence; generated mode is an explicit author licence to invent a
bounded past.  Both compile into the same chronological memory surface.

The affect and ranking vocabulary is the resident path's, imported rather than
restated: a journey memory and a resident memory land in the same bank and are
read back by the same retrieval surfaces, so a second vocabulary here would
only be a vocabulary that drifts.
"""

from __future__ import annotations

import copy
import hashlib
import json


# How many events the author may ask one journey for.  The floor is the
# existing generated-mode usability floor; the default matches the resident
# path's PERSONAL_MEMORY_TARGET (and the "10-16 separate memories" the engine's
# own UI already advertises for it), because a journey that can span centuries
# defaulting to six was the asymmetry.  The ceiling protects a SINGLE model
# call: at 45-180 words per recollection plus its fields, twenty events is
# already the largest reply this seam budgets for, and past it one call
# degrades into exactly the plot-synopsis list this generator exists to stop
# writing.
JOURNEY_EVENT_MIN = 3
JOURNEY_EVENT_DEFAULT = 12
JOURNEY_EVENT_MAX = 20

# A generated recollection shorter than this is a dossier line, not a moment.
# Cited mode is exempt: it may only summarize the evidence it was handed, and
# cannot be ordered to invent the detail that would make the count.
_GENERATED_MEMORY_FLOOR_WORDS = 30

_SYSTEM = """Create a vivid chronological travel history for one fictional
character. Return JSON only: {summary,events:[{sequence,when,place,people,
kind,memory,consequence,source_ids,tone,lesson,valence,arousal,salience}]}.
Produce the requested number of distinct events and never more than the
stated maximum.

Each event becomes its OWN retrievable memory row. The memory is 45-180 words
of concrete first-person autobiographical recollection of ONE moment, not a
career: name who was there, the physical place, what was wanted or said and
what was at stake, the character's own choice or reaction, and one sensory
detail that distinguishes this occasion from every other. Write it as the
character remembering -- I, we, my -- never as a narrator describing them, and
never as a plot synopsis. A memory that never speaks in the first person is
discarded.

Never open with an ordinal or a connective: no "Later", no "Early on", no
"Then", no "Most recently", no date followed by a colon. When and place are
separate fields and the recollection must stand on its own; situate time
inside the prose only when the moment turns on it. consequence says what
remained changed, unresolved, learned, owed, feared, or practically different
afterward. kind is a short label for the sort of occasion it was -- arrival,
encounter, decision, promise, debt, loss, discovery, companion change,
departure, or another that fits. Vary them; do not write one event repeatedly.

tone and lesson use the supplied closed vocabularies. valence is -1 to 1 for
how the moment felt, arousal 0 to 1 for how activating it was, and salience 0
to 1 for how much of the character's attention this moment still holds. Spread
salience honestly: an ordinary crossing and the night a promise was made must
not rank alike.

A journey ends where the story begins. When an arrival location is supplied,
the final one or two events run toward it -- the decision, passage, debt,
summons, or accident that brought the character to this place, now, and what
they saw on the approach. Arriving is not residing: the approach may name the
road, the crossing, the reason, and the first sight of the place, but grants
no residence, tenure, post, employment, or local history there. Do not make
the character a resident of the opening location.

In cited mode, every event must cite supplied source_ids and may only
summarize or connect facts in those sources. Do not fill canon gaps, invent a
destination, merge distinct incidents, or turn rumor into certainty.
In generated mode, the author explicitly permits invention within the card,
opening, lore constraints, and guidance. Generated events become the factual
ledger only after validation. Never contradict an authored fact. The summary
must summarize only the returned events."""


def journey_event_count(value, default=JOURNEY_EVENT_DEFAULT):
    """Normalize an author-supplied event count into the supported band.

    The browser's number input is a convenience, never an authority: whatever
    a stale tab, an archive, or a stored route carries is re-normalized here,
    and a route minted before the count existed reads as the default.
    """
    try:
        count = int(float(str(value).strip()))
    except (TypeError, ValueError):
        count = int(default)
    return max(JOURNEY_EVENT_MIN, min(JOURNEY_EVENT_MAX, count))


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _content_key(prefix, value):
    """Mint an identity that survives chat, character, and lore-id remapping."""
    material = json.dumps(value, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:18]
    return f"{prefix}:{digest}"


def _source_rows(sheet, lore):
    from story.character_schema import (
        character_private_history, character_public_history,
        normalize_character_data)

    normalized = normalize_character_data(sheet)
    rows = []
    public = _text(character_public_history(normalized), 7000)
    if public:
        rows.append({"source_id": "card:public_history", "text": public})
    for index, entry in enumerate(character_private_history(normalized)[:20]):
        if isinstance(entry, dict) and entry.get("content"):
            rows.append({
                "source_id": f"card:private_history:{index}",
                "text": _text(entry["content"], 1000),
            })
    for index, entry in enumerate(lore or ()):
        if not isinstance(entry, dict):
            continue
        content = _text(entry.get("content") or entry.get("summary"), 2400)
        if not content:
            continue
        source_id = "lore:" + str(entry.get("id") or index)
        rows.append({
            "source_id": source_id,
            "title": _text(entry.get("title"), 240), "text": content,
        })
    return rows[:48]


def _model_value(payload, model_call=None):
    if model_call is None:
        from llm.providers import chat_complete
        # One call carries every requested recollection, and a recollection is
        # now a paragraph rather than a dossier line, so the budget follows the
        # author's count instead of a constant sized for six.
        count = journey_event_count(payload.get("maximum_events"))
        raw = chat_complete(
            "utility", _SYSTEM, json.dumps(payload, ensure_ascii=False),
            temperature=.55 if payload["mode"] == "generated" else .3,
            max_tokens=min(14000, 2000 + 600 * count), json_mode=True)
        value = json.loads(raw)
    else:
        value = model_call(copy.deepcopy(payload))
    from llm.schemas import PrestoryJourneyHistory
    parsed = PrestoryJourneyHistory(**(value if isinstance(value, dict) else {}))
    return parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()


def ground_journey_history(value, sources, *, generated=False,
                           cap=JOURNEY_EVENT_MAX):
    """Validate citations, order, density, perspective, and identification."""
    from language_runtime import linguistic
    from world.charter_history import (
        PERSONAL_LESSONS, PERSONAL_SALIENCE_CAP, PERSONAL_TONES, _number)

    # The live narration-person machinery's detector, not a second one written
    # here: it is pack-scoped, so a story told in another language is judged by
    # that language's first-person markers rather than by English pronouns.
    first_person = linguistic("agents.common", "_FIRST_PERSON_RE")
    valid = {str(row.get("source_id")) for row in sources}
    events, dropped, seen = [], [], set()
    for raw in value.get("events") or ():
        if not isinstance(raw, dict):
            continue
        cited = list(dict.fromkeys(str(item) for item in raw.get("source_ids") or ()
                                   if str(item)))
        if not generated and (not cited or any(item not in valid for item in cited)):
            dropped.append({"sequence": raw.get("sequence"), "reason": "uncited"})
            continue
        memory = _text(raw.get("memory"), 1400)
        place = _text(raw.get("place"), 240)
        if not memory or not place:
            dropped.append({"sequence": raw.get("sequence"),
                            "reason": "missing_memory_or_place"})
            continue
        # The prompt has asked for first person since this generator existed,
        # and 15% of live episodic rows still never say "I": an instruction a
        # model is free to ignore is not a guarantee. A third-person synopsis
        # cannot be rewritten into a perspective its author never took without
        # inventing what was felt, so the answer is subtraction.
        if not first_person.findall(memory):
            dropped.append({"sequence": raw.get("sequence"),
                            "reason": "not_first_person"})
            continue
        if generated and len(memory.split()) < _GENERATED_MEMORY_FLOOR_WORDS:
            dropped.append({"sequence": raw.get("sequence"),
                            "reason": "thin_memory"})
            continue
        try:
            sequence = int(raw.get("sequence"))
        except (TypeError, ValueError):
            sequence = len(events) + 1
        key = (sequence, memory.casefold())
        if key in seen:
            continue
        seen.add(key)
        tone = str(raw.get("tone") or "neutral").strip().casefold()
        lesson = str(raw.get("lesson") or "none").strip().casefold()
        if tone not in PERSONAL_TONES:
            tone = "neutral"
        if lesson not in PERSONAL_LESSONS:
            lesson = "none"
        events.append({
            "sequence": sequence, "when": _text(raw.get("when"), 160),
            "place": place,
            "people": list(dict.fromkeys(_text(item, 160)
                                          for item in raw.get("people") or ()
                                          if _text(item, 160)))[:8],
            "kind": _text(raw.get("kind") or "journey_event", 80),
            "memory": memory,
            "consequence": _text(raw.get("consequence"), 600),
            "source_ids": cited if not generated else [],
            # A protocol tag, not model prose: the felt-affect surface every
            # retrieval reader parses is a closed vocabulary on both paths.
            "emotional_context": f"tone:{tone};lesson:{lesson}",
            "tone": tone, "lesson": lesson,
            "valence": max(-1.0, min(1.0, _number(raw.get("valence")))),
            "arousal": max(0.0, min(1.0, _number(raw.get("arousal")))),
            "salience": round(max(0.35, min(PERSONAL_SALIENCE_CAP,
                                            _number(raw.get("salience"), .58))), 4),
        })
    events.sort(key=lambda row: (row["sequence"], row["when"], row["place"]))
    events = events[:journey_event_count(cap)]
    for index, event in enumerate(events, 1):
        event["sequence"] = index
        # Citations can be remapped by an archive import and sequence can be
        # renumbered by grounding. Neither changes which remembered event this
        # is, so identity comes only from its durable autobiographical surface.
        # Affect is a reading OF that event rather than a different event, so
        # it stays out of the key: an old seven-field record re-imports under
        # the same event_key and still dedupes against its own memory rows.
        identity = {
            key: event[key]
            for key in ("when", "place", "people", "memory", "consequence")
        }
        event["event_id"] = _content_key("journey", identity)
    return {
        "summary": _text(value.get("summary"), 1800), "events": events,
        "grounding": {"dropped": dropped[:24], "generated": bool(generated)},
    }


def compile_journey_history(cid, char_id, sheet, route, *, lore=(), opening="",
                            arrival_brief="", frame_id=None, model_call=None):
    """Generate/compile, persist its ledger, and seed ordered memories."""
    from core.db import wget_for_frame, wset_for_frame
    from language_runtime import story_language_scope
    from mind.memory import add_memories_batch
    from story.character_schema import character_name
    from world.charter_history import PERSONAL_LESSONS, PERSONAL_TONES

    generated = str((route or {}).get("authority") or "") == "generated"
    count = journey_event_count((route or {}).get("event_count"))
    sources = _source_rows(sheet, lore)
    payload = {
        "mode": "generated" if generated else "cited",
        "character": character_name(sheet),
        "opening": _text(opening, 2400),
        # Where the story starts. The journey may run TOWARD it; it never
        # confers tenure there -- residence is a route-topology decision this
        # generator does not make and cannot reach.
        "arrival_location": _text(arrival_brief, 1200),
        "author_guidance": _text((route or {}).get("guidance"), 2000),
        "sources": sources,
        "target_events": count,
        "maximum_events": count,
        "tone_vocabulary": sorted(PERSONAL_TONES),
        "lesson_vocabulary": sorted(PERSONAL_LESSONS),
    }
    # Grounding reads a pack-scoped first-person detector, so generation and
    # validation both run under the story's own language rather than English.
    with story_language_scope(cid):
        grounded = ground_journey_history(
            _model_value(payload, model_call=model_call), sources,
            generated=generated, cap=count)
    if generated and len(grounded["events"]) < JOURNEY_EVENT_MIN:
        raise ValueError("generated journey returned fewer than three usable events")

    rows = []
    if grounded["summary"]:
        summary_key = _content_key("prestory:journey:summary",
                                   grounded["summary"])
        rows.append({
            "chat_id": cid, "char_id": char_id, "turn_id": None,
            "turn_idx": None, "frame_id": frame_id,
            "kind": "semantic", "provenance": "remembered",
            "salience": .45, "content": grounded["summary"],
            "event_key": summary_key,
        })
    for event in grounded["events"]:
        # No welded ordinal, no "<when>: " glue. Both were generator
        # scaffolding handed to the character as their own recollection, and
        # when/place have their own fields: the row's location and entities are
        # embedded and FTS-mirrored, and chronology survives in the ledger's
        # sequence, so retrieval loses nothing by dropping the weld.
        rows.append({
            "chat_id": cid, "char_id": char_id, "turn_id": None,
            "turn_idx": None, "frame_id": frame_id,
            "kind": "episodic", "provenance": "remembered",
            "salience": event["salience"], "content": event["memory"],
            "location": event["place"], "entities": event["people"],
            "emotional_context": event["emotional_context"],
            "valence": event["valence"], "arousal": event["arousal"],
            "confidence": 1.0 if generated else .9,
            "event_key": f"prestory:{event['event_id']}",
        })
    if rows:
        add_memories_batch(rows)

    record = wget_for_frame(cid, "character_journey_histories", frame_id, {}) or {}
    record[str(char_id)] = {
        "route": copy.deepcopy(route), "summary": grounded["summary"],
        "events": grounded["events"], "grounding": grounded["grounding"],
        "memory_event_keys": [row["event_key"] for row in rows],
        "source_ids": [row["source_id"] for row in sources],
    }
    wset_for_frame(cid, "character_journey_histories", record, frame_id)
    return record[str(char_id)]


__all__ = [
    "JOURNEY_EVENT_DEFAULT", "JOURNEY_EVENT_MAX", "JOURNEY_EVENT_MIN",
    "compile_journey_history", "ground_journey_history", "journey_event_count",
]
