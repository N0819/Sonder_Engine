"""Sparse LLM-compiled history for characters whose lives follow an itinerary.

This is not Charter with the rooms removed.  A journey is an ordered ledger of
world visits and consequential intersections.  Canon mode accepts only cited
card/lore evidence; generated mode is an explicit author licence to invent a
bounded past.  Both compile into the same chronological memory surface.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re


JOURNEY_EVENT_CAP = 8
JOURNEY_EVENT_TARGET = 6

_SYSTEM = """Create a semi-detailed chronological travel history for one
fictional character. Return JSON only: {summary,events:[{sequence,when,place,
people,memory,consequence,source_ids}]}. Produce about six distinct events,
up to eight. Each memory is a concise first-person autobiographical memory,
not a dossier sentence. Name the world/place and people involved whenever the
evidence or generation licence supports them. Vary the event types: arrival,
encounter, decision, promise/debt, loss, discovery, companion change, or
departure. Do not make the character a resident of the opening location.

In cited mode, every event must cite supplied source_ids and may only
summarize or connect facts in those sources. Do not fill canon gaps, invent a
destination, merge distinct incidents, or turn rumor into certainty.
In generated mode, the author explicitly permits invention within the card,
opening, lore constraints, and guidance. Generated events become the factual
ledger only after validation. Never contradict an authored fact. The summary
must summarize only the returned events."""


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
        raw = chat_complete(
            "utility", _SYSTEM, json.dumps(payload, ensure_ascii=False),
            temperature=.55 if payload["mode"] == "generated" else .3,
            max_tokens=5000, json_mode=True)
        value = json.loads(raw)
    else:
        value = model_call(copy.deepcopy(payload))
    from llm.schemas import PrestoryJourneyHistory
    parsed = PrestoryJourneyHistory(**(value if isinstance(value, dict) else {}))
    return parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()


def ground_journey_history(value, sources, *, generated=False):
    """Validate citations, order, density, and identification."""
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
        memory = _text(raw.get("memory"), 900)
        place = _text(raw.get("place"), 240)
        if not memory or not place:
            dropped.append({"sequence": raw.get("sequence"),
                            "reason": "missing_memory_or_place"})
            continue
        try:
            sequence = int(raw.get("sequence"))
        except (TypeError, ValueError):
            sequence = len(events) + 1
        key = (sequence, memory.casefold())
        if key in seen:
            continue
        seen.add(key)
        events.append({
            "sequence": sequence, "when": _text(raw.get("when"), 160),
            "place": place,
            "people": list(dict.fromkeys(_text(item, 160)
                                          for item in raw.get("people") or ()
                                          if _text(item, 160)))[:8],
            "memory": memory,
            "consequence": _text(raw.get("consequence"), 600),
            "source_ids": cited if not generated else [],
        })
    events.sort(key=lambda row: (row["sequence"], row["when"], row["place"]))
    events = events[:JOURNEY_EVENT_CAP]
    for index, event in enumerate(events, 1):
        event["sequence"] = index
        # Citations can be remapped by an archive import and sequence can be
        # renumbered by grounding. Neither changes which remembered event this
        # is, so identity comes only from its durable autobiographical surface.
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
                            frame_id=None, model_call=None):
    """Generate/compile, persist its ledger, and seed ordered memories."""
    from core.db import wget_for_frame, wset_for_frame
    from mind.memory import add_memories_batch
    from story.character_schema import character_name

    generated = str((route or {}).get("authority") or "") == "generated"
    sources = _source_rows(sheet, lore)
    payload = {
        "mode": "generated" if generated else "cited",
        "character": character_name(sheet),
        "opening": _text(opening, 2400),
        "author_guidance": _text((route or {}).get("guidance"), 2000),
        "sources": sources,
        "target_events": JOURNEY_EVENT_TARGET,
    }
    grounded = ground_journey_history(
        _model_value(payload, model_call=model_call), sources,
        generated=generated)
    if generated and len(grounded["events"]) < 3:
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
    for index, event in enumerate(grounded["events"]):
        prefix = ("Early in my travels, " if index == 0 else
                  "Most recently, " if index == len(grounded["events"]) - 1
                  else "Later, ")
        memory = event["memory"]
        content = prefix + memory
        if event["when"] and event["when"].casefold() not in content.casefold():
            content = f"{event['when']}: {content}"
        rows.append({
            "chat_id": cid, "char_id": char_id, "turn_id": None,
            "turn_idx": None, "frame_id": frame_id,
            "kind": "episodic", "provenance": "remembered",
            "salience": .52, "content": content,
            "location": event["place"], "entities": event["people"],
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
    "JOURNEY_EVENT_CAP", "JOURNEY_EVENT_TARGET", "compile_journey_history",
    "ground_journey_history",
]
