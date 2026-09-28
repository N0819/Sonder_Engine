"""Shared fakes for tests that run the Director.

The Director writes prose and one encoder builds the beat's events
(`agents/director_prose.py`); both calls go through `director._agent_json`,
which is the seam these fakes replace. The causal Director they used to
answer for -- a ledger author and five specialist hands, each its own model
call -- was deleted 2026-09-27, and its step keys (`director_interpret`,
`director_resolve`, `director_<hand>`) are no longer asked.

Pair any of these with the `prose_director` fixture (`tests/conftest.py`),
which answers the decision model deterministically.
"""

from __future__ import annotations

import json
import time
import uuid

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data


BASE_SCENE = {
    "location": "Blackthorn Lighthouse",
    "time": "night",
    "rooms": {
        "keeper_room": {
            "name": "Keeper's Room",
            "adjacent": [
                {"to": "lamp_room", "barrier": "open", "distance": "near"},
            ],
        },
        "lamp_room": {"name": "Lamp Room", "adjacent": []},
    },
    "positions": {"The Stranger": "keeper_room", "Mara": "keeper_room"},
    "entities": {},
    "attire": {},
    "overlays": {},
}


def _make_ctx(temp_db, *, scene=None, interp=None, player_input="hello"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(),
         f"char_mara_{uuid.uuid4().hex[:8]}"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene",
                 json.loads(json.dumps(scene or BASE_SCENE)))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, player_input, time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input=player_input, created=time.time()),
        cast=cast, input=player_input,
    )
    ctx.director_interpret = interp or _speech_interp()
    return ctx


def _speech_interp():
    """A pure-dialogue beat: no action, no movement, no dice."""
    return {
        "sequence": [{"type": "speech", "text": "Quiet night.",
                      "volume": "normal", "visibility": "overt",
                      "conceal_from": []}],
        "speech": "Quiet night.", "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


def _action_interp():
    """A physical beat: one declared action attempt."""
    return {
        "sequence": [{"type": "action", "attempt": "pull off my wool coat",
                      "commitment": "asserted", "targets": [],
                      "visibility": "overt", "conceal_from": []}],
        "speech": None, "action": {"attempt": "pull off my wool coat"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


def _fake_agent(calls, responses):
    """A `_agent_json` stand-in that answers per step_key and records every
    call, so a test can assert who was called, in what role, with what."""
    def fake(role, step_key, system, payload, **kw):
        calls.append({"role": role, "step_key": step_key,
                      "system": system, "payload": payload})
        value = responses.get(step_key, {})
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(payload)
        return json.loads(json.dumps(value))
    return fake


def _steps(calls):
    return [c["step_key"] for c in calls]


#: Channels whose value is a map keyed by the thing it changes -- a body, an
#: entity, a room. The fake files one transform per key, the owner's
#: one-transform-per-thing contract (2026-09-15), so `bind_items` never
#: mistakes two things written in one transform for one thing.
_KEYED_CHANNELS = frozenset({
    "attire", "conditions", "vitals", "overlays", "containment", "scales",
    "entities", "rooms", "positions", "stations", "poses",
})
#: Fields a list-valued channel's rows name their subject by, in the order
#: the fake tries them, for the transform's `item`.
_SUBJECT_FIELDS = ("actor", "subject", "who", "name", "target", "entity", "from")


def _row_subject(value):
    for row in value if isinstance(value, list) else ():
        if isinstance(row, dict):
            for field in _SUBJECT_FIELDS:
                text = str(row.get(field) or "").strip()
                if text:
                    return text
    return ""


def encoder_event(event, *, source="persona:primary", transforms=(), **fields):
    """One encoder event, as the encoder writes it: `event` is what happened,
    `transforms` its `{"item", "patch"}` changes, and any other row field
    (`speech`, `targets`, `movement`, `observable`, `commitment`, `look`,
    `seconds`...) rides in `fields`."""
    items = []
    for transform in transforms:
        item = str(transform.get("item") or "").strip()
        if item and item.casefold() not in {name.casefold() for name in items}:
            items.append(item)
    row = {
        "source_entity_id": source,
        "source_event_id": "",
        "event": event,
        "observable": "",
        "speech": False,
        "targets": [],
        "movement": None,
        "commitment": "asserted",
        "item_names": items,
        "transforms": [dict(transform) for transform in transforms],
    }
    row.update(fields)
    return row


def transforms_for(diff, *, strict=True):
    """A `state_diff`-shaped mapping as encoder transforms. Keyed channels
    split one transform per thing; any other channel is one transform, named
    for the subject of its first row. A channel no owner keeps raises: the
    prose Director writes no `state_diff` of its own, so a fixture channel
    without an owner has no path into the beat and a test relying on it would
    pass for the wrong reason. `strict=False` skips such a channel instead --
    for replaying a STORED diff, which carries keys the engine derives itself
    (`causal_steps`, `movement_refused` ...)."""
    from agents.director import SPECIALISTS

    owned = {channel for spec in SPECIALISTS.values() for channel in spec["channels"]}
    out = []
    for channel, value in (diff or {}).items():
        if value in (None, {}, [], ""):
            continue
        if channel not in owned:
            if not strict:
                continue
            raise ValueError(
                f"state_diff.{channel} has no channel owner; the prose Director "
                "cannot write it -- port the fixture, do not drop it")
        if channel in _KEYED_CHANNELS and isinstance(value, dict):
            for key, record in value.items():
                out.append({"item": str(key), "patch": {channel: {key: record}}})
        else:
            out.append({"item": _row_subject(value) or channel,
                        "patch": {channel: value}})
    return out


#: The ledger-row fields an encoder event carries under the same names.
_EVENT_FIELDS = ("targets", "movement", "observable", "commitment", "visibility",
                 "conceal_from", "volume", "look", "seconds", "act")


def prose_answers(output, *, source="persona:primary", strict=True):
    """A causal-era resolve output (`resolved_event`, `state_diff`) as the
    prose Director's two answers: the Director's prose, and the encoder's
    events carrying every channel of the diff.

    With no ledger rows that is ONE event whose text is the prose, so the
    beat's `resolved_event` (synthesized from the rows) reads the same. Rows
    the output does carry (`causal_ledger` or `ledgers`) become one event
    each, in order, keeping who acted and any movement; the diff's
    transforms ride the last of them."""
    output = output or {}
    prose = (str(output.get("resolved_event") or "").strip()
             or str(output.get("summary") or "").strip()
             or "The moment passes.")
    transforms = transforms_for(output.get("state_diff"), strict=strict)
    rows = [row for row in (output.get("causal_ledger") or output.get("ledgers") or [])
            if isinstance(row, dict)]
    if not rows:
        events = [encoder_event(prose, source=source, transforms=transforms)]
    else:
        events = []
        for index, row in enumerate(rows):
            fields = {key: row[key] for key in _EVENT_FIELDS
                      if row.get(key) not in (None, "", [])}
            events.append(encoder_event(
                str(row.get("event") or prose),
                source=str(row.get("source_entity_id") or source),
                transforms=transforms if index == len(rows) - 1 else (),
                speech="speech" in (row.get("categories") or []),
                **fields))
    return {
        "director_prose": {"prose": prose},
        "director_specialist": {"events": events, "missing_tools": [],
                                "missing_referents": [], "notes": []},
    }


def prose_resolve_agent(output, *, per_step=None, calls=None, source="persona:primary",
                        strict=True):
    """A fake `agents.director._agent_json` that serves a whole-beat resolve
    output (`resolved_event`, `state_diff`) through the prose Director -- the
    Director's prose, then one encoder event carrying the diff's channels,
    which `_run_specialists` binds, validates and folds exactly as it would a
    real encoder's answer.

    `per_step` overrides any step key outright; `calls` collects
    (step_key, payload) when a test wants to count; `strict` is
    `transforms_for`'s.
    """
    canned = {**prose_answers(output, source=source, strict=strict),
              **(per_step or {})}

    def fake(role, step_key, system, payload, **kw):
        if calls is not None:
            calls.append((step_key, payload))
        value = canned.get(step_key, {})
        if callable(value):
            value = value(payload)
        return json.loads(json.dumps(value))
    return fake
