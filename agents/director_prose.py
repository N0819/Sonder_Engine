"""The prose contract: a Director that only writes, one encoder that only builds.

An alternative to the causal ledger contract, selected per install by the
setting `director_contract = "prose"` and used by BOTH Director stages
(interpret and resolve). Everything downstream of the Director's engine input
is unchanged: the rows, the per-channel transforms, the bind/validate/fold in
`director._run_specialists`, every deterministic floor after it, commit,
perception and the narrator. What changes is who produces that input.

The causal contract asked the Director to be two things at once -- the author
of how a beat realistically unfolds, and its dispatcher: cutting spans,
allocating item handles, routing each row to channel categories -- and then
five hands re-read those rows positionally, with a forwarding round and a
recompiler to reconcile them. Measured on the live contract, that bookkeeping
competed with authorship for the Director's attention. This contract takes
all of it away from the author:

1. **The Director writes prose** (`prose_director_prompt`): what happens, and
   what follows from it, with wide latitude to add detail and consequence.
   Two limits only -- a declared act is not replaced, and another mind's
   choices are its own.
2. **The decision model picks the tools** (`llm.decisions`, TypeSafe's Jev):
   one yes/no question per engine channel the story keeps, all asked at
   once against the prose. It writes nothing, so it cannot start authoring.
3. **One encoder does every hand's job** (`unified_specialist_prompt`): its
   sheet is a small core plus exactly the selected channels' existing chunks,
   and its payload the world slices those channels' owners would have been
   given. It writes the beat as ORDERED EVENTS, each carrying its own
   transforms. With one writer, its output order is the chronology: there is
   nothing to recompile, forward, or reconcile across hands.
4. **Code converts** the events into the rows `normalize_causal_ledger`
   already reads (position is `chrono_id`; one handle per distinct item
   name; categories from the channels actually written) and splits each
   event's transforms by channel owner, so `_run_specialists` binds and
   folds them exactly as it would a hand's (`answer_for`).

The encoder may name a tool it needed and was not granted (`missing_tools`);
the engine grants it and asks ONCE more, and that answer replaces the first
whole -- a replacement, never a merge, so chronology stays trivial.

Settings (all optional): `director_contract` (`causal` default | `prose`),
`prose_contract_threshold` (a channel is granted at or above this Jev
probability; `DEFAULT_THRESHOLD`), `prose_contract_widen` (`1` default: allow
the one widening pass), and `llm.decisions`' own `jev_model`/`jev_provider`.
"""

from __future__ import annotations

import contextvars
import time
from concurrent.futures import ThreadPoolExecutor

from core.db import get_setting
from llm import decisions
from llm.prompts import (
    ROOM_AUTHOR_CHANNELS,
    jev_channel_questions,
    prose_director_prompt,
    unified_specialist_prompt,
)
from .director_fanout import _specialist_payload
from .director_scopes import (
    SPECIALISTS,
    _STRUCTURAL_CHANNEL_FACTS,
    channel_serves_stage,
)

CONTRACT_SETTING = "director_contract"
THRESHOLD_SETTING = "prose_contract_threshold"
WIDEN_SETTING = "prose_contract_widen"
#: A channel is granted when Jev's yes-probability reaches this. Named for
#: the owner's ask-before-limiting rule; tune it from the probabilities each
#: stage records. Measured 2026-09-22 against six stored beats of chat 153
#: (tmp jev_variants replay): at 0.3 the battery granted 7-17 channels a
#: beat and the encoder's input reached 33k tokens; at 0.5 it granted 2-9
#: and still covered every channel the encoder went on to write, except on
#: one beat where the causal contract wrote nothing either. The widening
#: pass is the backstop for a genuine miss.
DEFAULT_THRESHOLD = 0.5
#: The ctx key the stage's in-flight record rides on between the Director
#: call site and the fan-out site. In-memory only.
CTX_KEY = "_prose_contract"
#: Payload keys of a hand's own payload that belong to the several-hands
#: contract and have no meaning for the one encoder.
_HAND_ONLY_KEYS = frozenset({
    "source", "completion_contract", "ledgers", "director_note",
    "changes_asserted", "co_hands", "variant_seed",
})


#: Channels whose only possible subject is a record the world ALREADY holds
#: -- a crowd, a carried report, an unratified claim, a posted notice, a
#: destructible thing. Prose cannot tell the decision model such a record
#: exists, and measured on chat 153 it said yes to these on beats with none
#: of them, so they are asked only when the engine's own gate facts
#: (`director_scopes._gate_facts`) say one does. Any listed fact suffices;
#: a fact the facts object cannot answer fails open (the channel is asked).
_RECORD_FACTS = {
    "crowd_ops": ("crowds_present",),
    "courier_ops": ("couriers_present", "reports_carried"),
    "telling_ops": ("reports_carried", "crowds_present"),
    "ratified_claims": ("unratified_claims_present",),
    "contradicted_claims": ("unratified_claims_present",),
    "artifact_ops": ("notices_in_scene", "reports_carried"),
    "destruction": ("destructible_entity",),
}


def _fact(facts, key):
    try:
        return bool(facts[key])
    except Exception:
        return True


def enabled() -> bool:
    return str(get_setting(CONTRACT_SETTING) or "").strip().casefold() == "prose"


def _threshold() -> float:
    try:
        return float(get_setting(THRESHOLD_SETTING) or DEFAULT_THRESHOLD)
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD


def _widen_allowed() -> bool:
    return str(get_setting(WIDEN_SETTING) or "1").strip() not in ("0", "false", "off")


def _owner(channel):
    for name, spec in SPECIALISTS.items():
        if channel in spec["channels"]:
            return name
    return None


def candidate_channels(stage, facts=None):
    """Every channel this story keeps that this stage can carry, in canonical
    hand order. Extension families are left out: their sheets are not built
    from the engine's chunks, so the one encoder cannot absorb them."""
    facts = facts if facts is not None else {}
    out = []
    for spec in SPECIALISTS.values():
        if spec.get("ext_id"):
            continue
        for channel in spec["channels"]:
            if not channel_serves_stage(channel, stage):
                continue
            if not facts.get(_STRUCTURAL_CHANNEL_FACTS.get(channel), True):
                continue
            needs = _RECORD_FACTS.get(channel)
            if needs and facts and not any(_fact(facts, key) for key in needs):
                continue
            out.append(channel)
    return out


def _agent_json(*args, **kwargs):
    """Every model call goes through `director._agent_json`, resolved at call
    time, so the seam the Director's tests stub intercepts this contract's
    calls too (a direct import would bind the unpatched function)."""
    from . import director
    return director._agent_json(*args, **kwargs)


def already_happened(ctx):
    """What the player's side already put into the world this beat, for the
    resolve.

    Asserted human input is deliberately ABSENT from `event_inputs` -- it
    entered the preview world at interpret and must not be performed twice.
    The causal Director only routed, so it never needed it: the hands saw the
    asserted state in their world slices. A Director that AUTHORS
    consequences does need it, and without it wrote straight past it --
    measured on chat 153 turn 26, where the player asserted the ship "begins
    to land" and the prose Director, never told, wrote it settling into
    flight, which the encoder then committed over the landing. Interpret's
    own prose when interpret ran this contract; otherwise its asserted rows.
    """
    interp = getattr(ctx, "director_interpret", None) or {}
    if not isinstance(interp, dict):
        return ""
    prose = (((interp.get("orchestration") or {}).get("prose_contract") or {})
             .get("prose"))
    if prose:
        return str(prose)
    lines = []
    for row in interp.get("causal_ledger") or interp.get("ledgers") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("commitment") or "asserted") != "asserted":
            continue
        text = str(row.get("event") or "").strip()
        if text:
            lines.append(text)
    if not lines:
        for row in interp.get("sequence") or []:
            if not isinstance(row, dict) or row.get("commitment") == "contestable":
                continue
            text = str(row.get("text") or row.get("attempt")
                       or row.get("observable") or "").strip()
            if text:
                lines.append(text)
    return " ".join(lines)


def pronouns_of_people(ctx):
    """`{name: {subject, object, possessive}}` for the cast and the player,
    read off their cards through the engine's one identity reader -- the
    same map the resolve's authority readings use.

    A DIRECTOR THAT WRITES PROSE WRITES PRONOUNS. The causal Director never
    did, so its payload carried names alone; measured on the playerless
    Aldermill run (2026-09-23), the prose Director wrote Sal Weatherby, whose
    card says she/her, as "he" on every beat. Not a model fault: the fact
    was never handed over."""
    from story.character_schema import character_identity, normalized_character_of_row
    out = {}
    for row in getattr(ctx, "cast", None) or ():
        try:
            sheet = normalized_character_of_row(row)
        except Exception:
            sheet = None
        if not sheet:
            continue
        ident = character_identity(sheet)
        if ident.get("name") and isinstance(ident.get("pronouns"), dict) and ident["pronouns"]:
            out[ident["name"]] = ident["pronouns"]
    try:
        from story.character_schema import persona_name
        from story.scene import persona_of
        pers = persona_of(ctx.chat) or {}
        name = pers.get("name") or persona_name(pers)
        pp = ((pers.get("identity") or {}).get("pronouns") or pers.get("pronouns") or {})
        if name and isinstance(pp, dict) and pp:
            out.setdefault(name, pp)
    except Exception:
        pass
    return out


# ---- 1. the Director writes ----------------------------------------------

def author(ctx, stage, model_payload):
    out = _agent_json(
        "director",
        "director_prose",
        prose_director_prompt(stage, ctx.language),
        model_payload,
        temperature=0.7 if stage == "resolve" else 0.4,
        max_tokens=None,
    )
    prose = str((out or {}).get("prose") or "").strip()
    if not prose:
        raise RuntimeError(f"{stage}: the prose Director returned no prose")
    places = (out or {}).get("places")
    return prose, (places if isinstance(places, list) else [])


# ---- 2. the decision model picks the tools -------------------------------

def _jev_state(prose, model_payload):
    """What Jev judges: the passage, plus the two facts a channel question
    can turn on and prose alone may not settle -- who the people are, and
    which places already exist (a room question asks about a NEW place)."""
    identities = sorted({str(v) for v in identities_with_figures(model_payload).values() if v})
    rooms = sorted({str(v) for v in ((model_payload.get("object_index") or {}).get("rooms") or {}).values() if v})
    lines = ["PASSAGE:", prose, ""]
    if identities:
        lines.append("PEOPLE: " + ", ".join(identities))
    if rooms:
        lines.append("PLACES ALREADY KNOWN: " + ", ".join(rooms))
    return "\n".join(lines)


#: Jev question keys for "does the beat enter this planned room".
_ENTER_PREFIX = "enter__"


def select_channels(ctx, stage, prose, model_payload, facts=None, planned=None):
    """`(selected, record)`. Fails OPEN: if the decision model cannot answer,
    every candidate is granted -- a larger sheet, never a lost change.

    The same one call also asks, for each PLANNED room in reach (the
    Writers' Room's stubs, `planned_room_brief`), whether the passage enters
    or reveals it; `record["entered"]` lists those, which the room author
    then develops from the plan. Fails open there too: every stub in reach."""
    candidates = candidate_channels(stage, facts)
    questions = jev_channel_questions(candidates, ctx.language)
    planned = planned if isinstance(planned, dict) else {}
    record = {"candidates": candidates, "threshold": _threshold()}
    t0 = time.time()
    battery = {channel: {"type": "noul", "instructions": text}
               for channel, text in questions.items()}
    for rid, brief in planned.items():
        name = str((brief or {}).get("name") or rid)
        battery[_ENTER_PREFIX + str(rid)] = {
            "type": "noul",
            "instructions": f"Does the passage enter, open onto or reveal the place "
                            f"called \"{name}\"? Answer no when it is only mentioned "
                            "or lies beyond a door nobody opens."}
    try:
        answers = decisions.decide(_jev_state(prose, model_payload), battery)
    except Exception as exc:
        record.update(failed=str(exc), seconds=round(time.time() - t0, 3))
        ctx.add_warning(f"{stage}: decision model unavailable, every channel "
                        f"granted (fail-open): {exc}")
        record["selected"] = list(candidates)
        record["entered"] = list(planned)
        return list(candidates), record
    probabilities = {channel: round(decisions.probability(answers.get(channel)), 4)
                     for channel in questions}
    selected = [channel for channel in candidates
                if channel not in questions
                or probabilities.get(channel, 0.0) >= record["threshold"]]
    entered = [rid for rid in planned
               if decisions.probability(answers.get(_ENTER_PREFIX + str(rid)))
               >= record["threshold"]]
    record.update(probabilities=probabilities, selected=selected,
                  entered=entered, seconds=round(time.time() - t0, 3))
    return selected, record


# ---- 3. one encoder builds -----------------------------------------------

def identities_with_figures(model_payload):
    """The identity index, plus every body standing in view by its own name.

    The prose makes whoever is here act; the encoder attributes each step to
    `source_entity_id`, and a body the index did not list had no key -- so the
    step went to the cast member the beat was about (playerless Aldermill
    round 3, 2026-09-23: a hand's sacks on the scale filed as Sal's own act,
    and her view never showed the weighing she watched for eight beats). A
    figure's key is its display name, which is what a ledger row's unknown
    source already resolves to downstream."""
    index = dict(model_payload.get("identity_index") or {})
    named = {str(v).casefold() for v in index.values() if v}
    for row in model_payload.get("present_figures") or []:
        name = str((row or {}).get("name") or "").strip()
        if name and name.casefold() not in named:
            index[name] = name
            named.add(name.casefold())
    return index


def encoder_payload(ctx, sc, prose, model_payload, view, extras, channels):
    """The prose, the Director's own inputs, and the union of the world
    slices each selected channel's owner would have received. A key two
    owners both supply is taken once (the first owner in canonical order)."""
    payload = {
        "prose": prose,
        "event_inputs": model_payload.get("event_inputs") or [],
        "identity_index": identities_with_figures(model_payload),
        "world_index": model_payload.get("world_index") or {},
        "standing_relations": model_payload.get("standing_relations") or {},
        "already_happened": model_payload.get("already_happened") or "",
        "pronouns": model_payload.get("pronouns") or {},
        "granted_tools": list(channels),
        "variant_seed": model_payload.get("variant_seed"),
    }
    hands = [name for name in SPECIALISTS
             if any(_owner(channel) == name for channel in channels)]
    for name in hands:
        try:
            own = _specialist_payload(name, ctx, sc, view, extras)
        except Exception as exc:
            ctx.add_warning(f"prose contract: {name} slice unavailable: {exc}")
            continue
        for key, value in own.items():
            if key in _HAND_ONLY_KEYS or key in payload:
                continue
            payload[key] = value
    return payload


def implied_tools(events, scene=None):
    """Tools the encoder's own output proves it needs, read from engine
    vocabulary rather than from prose:

    - a relocation (`movement.to_room`) is a `positions` write;
    - a destination that is not a room the scene holds, nor one this answer
      creates, needs `rooms` to exist at all. Measured on chat 137 turn 45
      (4295): with no `rooms` granted, the encoder put the swallowed player
      at a CHARACTER id, because the interior it needed was not a room yet
      and it had no tool to make one (the rooms chunk says how: an interior
      is a room with `parent_entity`)."""
    tools = []
    known = set(((scene or {}).get("rooms") or {}).keys()) if isinstance(scene, dict) else set()
    destinations, created = [], set()
    for event in events or []:
        if not isinstance(event, dict):
            continue
        movement = event.get("movement")
        if isinstance(movement, dict) and str(movement.get("to_room") or "").strip():
            destinations.append(str(movement["to_room"]).strip())
            if "positions" not in tools:
                tools.append("positions")
        for transform in event.get("transforms") or []:
            patch = transform.get("patch") if isinstance(transform, dict) else None
            if not isinstance(patch, dict):
                continue
            if isinstance(patch.get("rooms"), dict):
                created.update(str(key) for key in patch["rooms"])
            if isinstance(patch.get("positions"), dict):
                destinations.extend(str(value) for value in patch["positions"].values()
                                    if isinstance(value, str) and value.strip())
    if known and any(dest not in known and dest not in created
                     and not dest.startswith(NEW_PLACE_PREFIX)
                     for dest in destinations):
        tools.append("rooms")
    return tools


# ---- 3b. the room author, in parallel ---------------------------------------

#: How the encoder names a place the room author is minting at the same
#: moment. The engine binds each reference to a minted room afterwards.
NEW_PLACE_PREFIX = "new:"
ROOM_AGENT_SETTING = "prose_contract_room_agent"
#: A Jev binding below this confidence leaves the reference unbound (and
#: reported) rather than guessing a room. Named per ask-before-limiting.
ROOM_BIND_CONFIDENCE = 0.5


def _isolated(context):
    """Run a call in a COPY of the caller's context, made in the caller's
    thread (a worker does not inherit contextvars), with the streaming sinks
    cleared: the room author produces structure, never player-facing text.
    The same isolation `director._run_specialists` gives each hand."""
    def run(fn, *args, **kwargs):
        def inner():
            from llm.providers import generation_event_sink, token_sink
            token_sink.set(None)
            generation_event_sink.set(None)
            return fn(*args, **kwargs)
        return context.run(inner)
    return run


def room_agent_enabled() -> bool:
    return str(get_setting(ROOM_AGENT_SETTING) or "1").strip() not in ("0", "false", "off")


def _room_payload(ctx, sc, prose, model_payload, view, extras, reserved, develop):
    payload = {
        "prose": prose,
        "already_happened": model_payload.get("already_happened") or "",
        "identity_index": model_payload.get("identity_index") or {},
        "world_index": model_payload.get("world_index") or {},
        "reserved_places": dict(reserved or {}),
        "develop": dict(develop or {}),
        "variant_seed": model_payload.get("variant_seed"),
    }
    try:
        own = _specialist_payload("spatial", ctx, sc, view, extras)
    except Exception as exc:
        ctx.add_warning(f"room author: spatial slice unavailable: {exc}")
        own = {}
    for key, value in own.items():
        if key not in _HAND_ONLY_KEYS and key not in payload:
            payload[key] = value
    return payload


def author_rooms(ctx, sc, prose, model_payload, view, extras, reserved=None,
                 develop=None, record=None, prepared=None):
    """The room designer (`agents/director_rooms.design_rooms`): a tool-using
    agent that develops the planned rooms the beat enters and builds the
    places the Director invented -- in pieces, looking at its work on the
    engine's grid and checking it with the engine's own layout check."""
    from llm.prompts import room_author_prompt
    from .director_rooms import design_rooms
    record = record if record is not None else {}
    payload = _room_payload(ctx, sc, prose, model_payload, view, extras, reserved, develop)
    if prepared:
        payload["prepared"] = sorted(prepared)
    owed = list(dict.fromkeys(list(develop or {}) + list(reserved or {})))

    def call(system, step_payload):
        return _agent_json("director_rooms", "director_rooms", system, step_payload,
                           temperature=0.4, max_tokens=None)

    return design_rooms(ctx, sc, payload, room_author_prompt(ctx.language), owed,
                        call, record, seed=prepared)


def _walk_strings(value, visit):
    """Every string leaf of a JSON value, rewritten by `visit`."""
    if isinstance(value, str):
        return visit(value)
    if isinstance(value, list):
        return [_walk_strings(item, visit) for item in value]
    if isinstance(value, dict):
        return {key: _walk_strings(item, visit) for key, item in value.items()}
    return value


def new_place_refs(events):
    """Every `new:<words>` the encoder wrote, in first-use order."""
    refs = []

    def visit(text):
        if text.startswith(NEW_PLACE_PREFIX):
            ref = text[len(NEW_PLACE_PREFIX):].strip()
            if ref and ref not in refs:
                refs.append(ref)
        return text
    _walk_strings(events or [], visit)
    return refs


def _fold_place(text):
    words = "".join(ch if ch.isalnum() else " " for ch in str(text or "").casefold()).split()
    while words and words[0] in ("the", "a", "an"):
        words = words[1:]
    return " ".join(words)


def bind_new_places(refs, rooms, prose, scene=None):
    """`({ref: room_id}, record)`. Candidates are the rooms the author made
    and the rooms the scene already holds (an encoder may call an existing
    place new). A folded name or id match binds outright; the rest are asked
    of the decision model as one CHOICE each -- binding is exactly the bounded
    decision it exists for -- and a low-confidence answer stays unbound."""
    candidates = {}
    for source in (rooms or {}, ((scene or {}).get("rooms") or {})):
        for rid, room in source.items():
            if rid not in candidates:
                candidates[str(rid)] = room if isinstance(room, dict) else {}
    bound, record = {}, {"asked": {}, "unbound": []}
    remaining = []
    for ref in refs:
        folded = _fold_place(ref)
        hits = [rid for rid, room in candidates.items()
                if folded and folded in (_fold_place(rid), _fold_place(room.get("name")))]
        if len(hits) == 1:
            bound[ref] = hits[0]
        else:
            remaining.append(ref)
    if remaining and candidates:
        criteria = {rid: (f"{room.get('name') or rid}: "
                          f"{str(room.get('desc') or '')[:160]}").strip()
                    for rid, room in list(candidates.items())[:250]}
        criteria["none"] = "none of these places"
        try:
            answers = decisions.decide("PASSAGE:\n" + prose, {
                f"place_{index}": {
                    "type": "choice",
                    "instructions": f"In this passage, which of these places is "
                                    f"the one it calls \"{ref}\"?",
                    "criteria": criteria,
                } for index, ref in enumerate(remaining)})
        except Exception as exc:
            answers = {}
            record["failed"] = str(exc)
        for index, ref in enumerate(remaining):
            answer = answers.get(f"place_{index}") or {}
            choice = str(answer.get("choice") or "")
            try:
                confidence = float(answer.get("confidence") or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0
            record["asked"][ref] = {"choice": choice, "confidence": confidence}
            if choice in candidates and confidence >= ROOM_BIND_CONFIDENCE:
                bound[ref] = choice
    record["unbound"] = [ref for ref in refs if ref not in bound]
    return bound, record


def rewrite_new_places(events, bound):
    """Replace each bound `new:<words>` with its room id."""
    def visit(text):
        if text.startswith(NEW_PLACE_PREFIX):
            return bound.get(text[len(NEW_PLACE_PREFIX):].strip(), text)
        return text
    return _walk_strings(events or [], visit)


def reserve_places(places, scene=None):
    """`{room_id: {name, size, shape}}` for the Director's new places.

    Three simple fields and nothing else -- the room author does the complex
    work. The id is the engine's own fold of the name (`normalize_room_id`),
    so both parallel workers hold it before either starts. A place whose id
    the scene already holds is not new and is not reserved; a size or shape
    outside the engine's vocabulary falls back to the engine's default."""
    from world.spatial import (DEFAULT_ROOM_SIZE, DEFAULT_SHAPE, ROOM_SIZES,
                               SHAPES, normalize_room_id)
    held = set(((scene or {}).get("rooms") or {}).keys()) if isinstance(scene, dict) else set()
    reserved = {}
    for place in places or []:
        if not isinstance(place, dict):
            continue
        name = str(place.get("name") or "").strip()
        rid = normalize_room_id(name)
        if not rid or rid in held or rid in reserved:
            continue
        size = str(place.get("size") or "").strip().casefold()
        shape = str(place.get("shape") or "").strip().casefold()
        reserved[rid] = {
            "name": name,
            "size": size if size in ROOM_SIZES else DEFAULT_ROOM_SIZE,
            "shape": shape if shape in SHAPES else DEFAULT_SHAPE,
        }
    return reserved


def enforce_reserved(rooms_answer, reserved, warn=None):
    """Every reserved room exists, under its id, with the Director's name,
    size and shape. The author's detail stands; those three are the
    Director's. A room the author left out becomes the minimal record the
    three fields make, so the encoder's placements still land somewhere."""
    rooms_answer = dict(rooms_answer or {})
    rooms = dict(rooms_answer.get("rooms") or {})
    for rid, spec in (reserved or {}).items():
        room = rooms.get(rid)
        if not isinstance(room, dict):
            if warn:
                warn(f"room author did not write reserved place {rid!r}; "
                     "it stands on the Director's three fields")
            room = {"desc": spec["name"], "adjacent": []}
        rooms[rid] = dict(room, **spec)
    rooms_answer["rooms"] = rooms
    return rooms_answer


def _new_objects(events):
    """`{entity_id: {name, description}}` the encoder created this beat."""
    found = {}
    for event in events or []:
        for transform in (event.get("transforms") or []) if isinstance(event, dict) else []:
            patch = transform.get("patch") if isinstance(transform, dict) else None
            entities = (patch or {}).get("entities") if isinstance(patch, dict) else None
            if not isinstance(entities, dict):
                continue
            for eid, record in entities.items():
                if isinstance(record, dict) and str(record.get("name") or "").strip():
                    found.setdefault(str(eid), record)
    return found


def reconcile_rooms(ctx, rooms_answer, events, prose, scene=None):
    """`(rooms_answer, record)`: the room author's own furnishings that are
    the same thing as an object the encoder made this beat, removed.

    A SHORT CALL TO THE AUTHOR, not a pairwise classifier. Both workers ran
    at once, so a table the prose sets in a new room can be written twice.
    The encoder's object is the one the beat used, so it is kept. Only the
    author knows what each of its features is FOR -- a pairwise yes/no over
    names removed a TARDIS's central console as a "copy" of an entity keyed
    by the room (chat 153 turn 7, 2026-09-22) -- so it names its own
    duplicates, and code removes only what it names, and only when the
    object it names exists."""
    from llm.prompts import room_reconcile_prompt
    record = {}
    held = set(((scene or {}).get("rooms") or {}).keys()) if isinstance(scene, dict) else set()
    rooms = (rooms_answer or {}).get("rooms") or {}
    features = {rid: {aid: (a.get("desc") if isinstance(a, dict) else a)
                      for aid, a in (room.get("anchors") or {}).items()}
                for rid, room in rooms.items()
                if isinstance(room, dict) and room.get("anchors")}
    objects = {eid: {"name": o.get("name"), "description": o.get("description")}
               for eid, o in _new_objects(events).items() if eid not in rooms and eid not in held}
    if not features or not objects:
        return rooms_answer, record
    answer = _agent_json(
        "director_rooms", "director_rooms_reconcile", room_reconcile_prompt(ctx.language),
        {"prose": prose, "your_features": features, "objects_made": objects},
        temperature=0.0, max_tokens=None) or {}
    removed = []
    rooms = {rid: (dict(room, anchors=dict(room.get("anchors") or {}))
                   if isinstance(room, dict) else room) for rid, room in rooms.items()}
    for item in answer.get("duplicates") or []:
        if not isinstance(item, dict):
            continue
        rid, aid = str(item.get("room") or ""), str(item.get("feature") or "")
        same = str(item.get("same_as") or "")
        if same in objects and aid in ((rooms.get(rid) or {}).get("anchors") or {}):
            rooms[rid]["anchors"].pop(aid)
            removed.append({"room": rid, "feature": aid, "kept": same})
    record["removed"] = removed
    return dict(rooms_answer, rooms=rooms), record


def room_event(rooms_answer, events):
    """The places the author made, as the beat's FIRST event: a place exists
    before any body walks into it. None when the author made nothing."""
    rooms = rooms_answer.get("rooms") if isinstance(rooms_answer, dict) else None
    rooms = rooms if isinstance(rooms, dict) else {}
    removed = [r for r in (rooms_answer or {}).get("remove_rooms") or [] if r]
    severed = [r for r in (rooms_answer or {}).get("remove_adjacent") or [] if r]
    if not (rooms or removed or severed):
        return None
    first = next((e for e in events or [] if isinstance(e, dict)), {})
    transforms = [{"item": str((room or {}).get("name") or rid),
                   "patch": {"rooms": {rid: room}}}
                  for rid, room in rooms.items() if isinstance(room, dict)]
    if removed or severed:
        patch = {}
        if removed:
            patch["remove_rooms"] = removed
        if severed:
            patch["remove_adjacent"] = severed
        transforms.append({"item": "places", "patch": patch})
    return {
        "source_entity_id": first.get("source_entity_id") or "",
        "source_event_id": first.get("source_event_id") or "",
        "event": "The places this beat establishes.",
        "observable": "", "commitment": "asserted", "seconds": 0,
        "item_names": [t["item"] for t in transforms],
        "transforms": transforms,
    }


def _call_encoder(ctx, channels, payload):
    return _agent_json(
        "director_specialist",
        "director_specialist",
        unified_specialist_prompt(channels, ctx.language),
        dict(payload, granted_tools=list(channels)),
        temperature=0.2,
        max_tokens=None,
    ) or {}


def encode(ctx, stage, sc, prose, model_payload, view, extras, channels, facts=None,
           rooms_elsewhere=False, new_places=None):
    """`(answer, channels, record)`: the encoder's events and the tools it
    finally held. At most one widening pass, whose answer REPLACES the
    first. With `rooms_elsewhere`, places are the room author's: the encoder
    holds no room tool, may not ask for one, and names a new place as
    `new:<words>`."""
    record = {}
    payload = encoder_payload(ctx, sc, prose, model_payload, view, extras, channels)
    payload["places_authored_elsewhere"] = bool(rooms_elsewhere)
    payload["new_places"] = dict(new_places or {})
    t0 = time.time()
    answer = _call_encoder(ctx, channels, payload)
    record["seconds"] = round(time.time() - t0, 3)
    known = set(candidate_channels(stage, facts))
    if rooms_elsewhere:
        known -= set(ROOM_AUTHOR_CHANNELS)
    missing = [str(tool) for tool in (answer.get("missing_tools") or [])
               if str(tool) in known and str(tool) not in channels]
    # CODE CLOSES THE KNOWN DEPENDENCIES; the decision model only predicts.
    # An event's `movement` is core row shape, written whatever was granted,
    # and a body that changes room needs `positions` to be moved at all.
    # Measured on chat 153 turn 8 (4356): the encoder wrote the step into
    # the console room as movement, Jev scored positions 0.43 under a 0.5
    # threshold, and the player never changed rooms.
    for tool in implied_tools(answer.get("events") or [], sc):
        if tool in known and tool not in channels and tool not in missing:
            missing.append(tool)
    if missing:
        record["missing_tools"] = missing
        if _widen_allowed():
            first = answer
            channels = list(channels) + [tool for tool in dict.fromkeys(missing)]
            payload = encoder_payload(ctx, sc, prose, model_payload, view,
                                      extras, channels)
            payload["places_authored_elsewhere"] = bool(rooms_elsewhere)
            payload["new_places"] = dict(new_places or {})
            # THE RE-ASK SEES ITS OWN FIRST ANSWER and returns the WHOLE beat.
            # Measured on chat 153 turn 23: asked again with only the new
            # tool, the encoder returned the two events that tool touched,
            # and the replacement dropped every later step of the beat.
            payload["previous_events"] = list(first.get("events") or [])
            t1 = time.time()
            answer = _call_encoder(ctx, channels, payload)
            record["widened_to"] = list(channels)
            record["widen_seconds"] = round(time.time() - t1, 3)
            # A replacement, never a merge -- so a thinner replacement must
            # not win. Fewer events than the first answer means the beat was
            # not re-encoded whole; keep the first and report the tool.
            if len(answer.get("events") or []) < len(first.get("events") or []):
                record["widen_rejected"] = (
                    f"{len(answer.get('events') or [])} events against the "
                    f"first answer's {len(first.get('events') or [])}")
                ctx.add_warning(f"{stage}: widened encoder answer was thinner "
                                f"than the first; kept the first, {missing} "
                                "unencoded")
                answer = first
                channels = [tool for tool in channels if tool not in missing]
            still = [str(tool) for tool in (answer.get("missing_tools") or [])
                     if str(tool) in known and str(tool) not in channels]
            if still and "widen_rejected" not in record:
                record["unmet_tools"] = still
                ctx.add_warning(f"{stage}: encoder still lacked {still} after "
                                "widening; those changes are unencoded")
        else:
            ctx.add_warning(f"{stage}: encoder lacked {missing} (widening off)")
    return answer, list(channels), record


# ---- 4. code converts ------------------------------------------------------

_ROW_FIELDS = ("source_entity_id", "source_event_id", "event", "act",
               "observable", "commitment", "targets", "visibility",
               "conceal_from", "volume", "movement", "look", "seconds",
               "ability", "difficulty")


def ledger_from_events(events, known_channels=None):
    """`(rows, transforms)`: the encoder's ordered events as ledger rows, and
    each row's transforms keyed by its chrono id.

    Position is chronology (`chrono_id = index + 1`). One handle per distinct
    item name across the whole beat, the name folded for case -- the encoder
    was told to reuse one stable name per thing, and the handle is only ever
    code's join. A transform naming an item its event did not list adds it to
    that event. Categories are derived: the channels the event's transforms
    actually wrote, plus `speech` for a spoken event and `attention` for one
    that looks."""
    known = set(known_channels) if known_channels is not None else {
        channel for spec in SPECIALISTS.values() for channel in spec["channels"]}
    handles = {}
    rows, transforms = [], {}
    for index, event in enumerate(events or []):
        if not isinstance(event, dict):
            continue
        chrono = len(rows) + 1
        names = []
        for name in event.get("item_names") or []:
            name = str(name or "").strip()
            if name and name.casefold() not in {n.casefold() for n in names}:
                names.append(name)
        kept = []
        for transform in event.get("transforms") or []:
            if not isinstance(transform, dict):
                continue
            patch = transform.get("patch")
            if not isinstance(patch, dict) or not patch:
                continue
            item = str(transform.get("item") or "").strip()
            if not item:
                item = names[0] if names else ""
            if item and item.casefold() not in {n.casefold() for n in names}:
                names.append(item)
            kept.append({"item": item, "patch": patch})
        if not names:
            speaker = str(event.get("source_entity_id") or "").strip()
            if speaker:
                names.append(speaker)
        ids = []
        for name in names:
            folded = name.casefold()
            if folded not in handles:
                handles[folded] = len(handles) + 1
            ids.append(handles[folded])
        written = []
        for transform in kept:
            for channel in transform["patch"]:
                if channel in known and channel not in written:
                    written.append(channel)
        categories = list(written)
        if event.get("speech"):
            categories.append("speech")
        if str(event.get("look") or "").strip():
            categories.append("attention")
        row = {field: event.get(field) for field in _ROW_FIELDS
               if event.get(field) not in (None, "", [])}
        row.update(
            chrono_id=chrono,
            item_ids=ids,
            item_names=names,
            event=str(event.get("event") or "").strip(),
            resolution_notes=str(event.get("observable") or event.get("event") or "").strip(),
            categories=categories,
        )
        rows.append(row)
        transforms[chrono] = kept
    return rows, transforms


def run(ctx, stage, sc, model_payload, view, extras, facts=None):
    """Author, select, encode, convert. Returns the stage's model output
    (`{"ledgers": rows}`) exactly where the causal Director's used to land,
    and leaves the rest on `ctx[CTX_KEY]` for `dispatch`."""
    if stage == "resolve":
        happened = already_happened(ctx)
        if happened:
            model_payload = dict(model_payload, already_happened=happened)
    pronouns = pronouns_of_people(ctx)
    if pronouns:
        model_payload = dict(model_payload, pronouns=pronouns)
    t0 = time.time()
    prose, places = author(ctx, stage, model_payload)
    author_seconds = round(time.time() - t0, 3)
    reserved = reserve_places(places, sc)
    planned = extras.get("planned_rooms") if isinstance(extras, dict) else None
    planned = planned if isinstance(planned, dict) else {}
    channels, jev = select_channels(ctx, stage, prose, model_payload, facts, planned)
    develop = {rid: planned[rid] for rid in jev.get("entered") or () if rid in planned}
    # Designs prepared between turns for the planned rooms this beat enters.
    try:
        from .director_rooms import prepared_rooms
        chat = ctx.chat
        prepared = prepared_rooms(chat["id"] if isinstance(chat, dict) else chat.id,
                                  develop)
    except Exception:
        prepared = {}
    # THE ROOM CONTRACT RUNS BESIDE THE ENCODER, not inside it. It is the
    # heaviest sheet the encoder would carry, and a place is authored whole
    # or not at all, so it goes to its own full-fidelity author, started the
    # moment the decision model says the beat touches a place; the encoder
    # names any new place `new:<words>` and the engine binds the two after.
    rooms_elsewhere = room_agent_enabled()
    room_record, rooms_answer, room_future, pool = {}, None, None, None
    if reserved:
        room_record["reserved"] = reserved
    if develop:
        room_record["develop"] = sorted(develop)
    # Places the encoder may place into at once: the Director's invented
    # ones, and the planned rooms being developed, each under its own id.
    new_places = dict(reserved)
    for rid, brief in develop.items():
        new_places.setdefault(rid, {"name": str((brief or {}).get("name") or rid),
                                    "planned": True})
    if rooms_elsewhere and (reserved or develop
                            or any(c in ROOM_AUTHOR_CHANNELS for c in channels)):
        pool = ThreadPoolExecutor(max_workers=1)
        room_future = pool.submit(_isolated(contextvars.copy_context()),
                                  author_rooms, ctx, sc, prose, model_payload,
                                  view, extras, reserved, develop, room_record,
                                  prepared)
        room_record["ran"] = "parallel"
    encoder_channels = ([c for c in channels if c not in ROOM_AUTHOR_CHANNELS]
                        if rooms_elsewhere else channels)
    t_rooms = time.time()
    try:
        answer, encoder_channels, encoding = encode(
            ctx, stage, sc, prose, model_payload, view, extras,
            encoder_channels, facts, rooms_elsewhere=rooms_elsewhere,
            new_places=new_places if rooms_elsewhere else None)
    finally:
        if room_future is not None:
            try:
                rooms_answer = room_future.result()
            except Exception as exc:
                room_record["failed"] = str(exc)
                ctx.add_warning(f"{stage}: room author failed (fail-open): {exc}")
            room_record["seconds"] = round(time.time() - t_rooms, 3)
            pool.shutdown(wait=True)
    events = list(answer.get("events") or [])
    if rooms_elsewhere:
        refs = new_place_refs(events)
        if refs and room_future is None:
            # The decision model did not foresee a place; the encoder named
            # one. Serial fallback -- the author still writes it whole.
            t1 = time.time()
            try:
                rooms_answer = author_rooms(ctx, sc, prose, model_payload, view,
                                            extras, reserved, develop, room_record,
                                            prepared)
                room_record["ran"] = "serial"
            except Exception as exc:
                room_record["failed"] = str(exc)
                ctx.add_warning(f"{stage}: room author failed (fail-open): {exc}")
            room_record["seconds"] = round(time.time() - t1, 3)
        if refs:
            bound, binding = bind_new_places(
                refs, (rooms_answer or {}).get("rooms"), prose, sc)
            room_record["bindings"] = bound
            room_record["binding"] = binding
            for ref in binding.get("unbound") or []:
                ctx.add_warning(f"{stage}: new place {ref!r} bound to no room")
            events = rewrite_new_places(events, bound)
        if reserved:
            rooms_answer = enforce_reserved(rooms_answer, reserved, warn=ctx.add_warning)
        if rooms_answer and (rooms_answer.get("rooms") or {}):
            t2 = time.time()
            try:
                rooms_answer, reconciled = reconcile_rooms(ctx, rooms_answer, events,
                                                           prose, sc)
            except Exception as exc:
                reconciled = {"failed": str(exc)}
            if reconciled:
                reconciled["seconds"] = round(time.time() - t2, 3)
                room_record["reconcile"] = reconciled
        extra = room_event(rooms_answer or {}, events)
        if extra is not None:
            events = [extra] + events
            room_record["rooms"] = sorted(((rooms_answer or {}).get("rooms") or {}))
    channels = list(encoder_channels) + [
        c for c in ROOM_AUTHOR_CHANNELS
        if rooms_elsewhere and rooms_answer and (rooms_answer.get(c) or None)]
    rows, transforms = ledger_from_events(events)
    record = {
        "stage": stage,
        "prose": prose,
        "author_seconds": author_seconds,
        "jev": jev,
        "channels": channels,
        "encoder": encoding,
        "room_author": room_record,
        "events": events,
        "missing_referents": list(answer.get("missing_referents") or []),
        "notes": list(answer.get("notes") or []),
    }
    for note in record["notes"]:
        ctx.add_warning(f"encoder: {note}")
    ctx[CTX_KEY] = {"record": record, "transforms": transforms,
                    "channels": channels}
    return {"ledgers": rows}


def dispatch(ctx, stage):
    """`(dispatch, answer_for)` for `director._run_specialists`.

    A hand "runs" when a granted or written channel is its own; its answer is
    the encoder's transforms that touch its channels, positionally aligned to
    whatever rows `_run_specialists` handed it. The encoder is the only
    writer, so a channel it wrote without being granted is still its work:
    it joins the owner's scope rather than being reported as a hand's
    under-grant."""
    held = ctx.get(CTX_KEY) if hasattr(ctx, "get") else None
    held = held or {"transforms": {}, "channels": []}
    transforms = held["transforms"]
    written = {channel for rows in transforms.values()
               for transform in rows for channel in transform["patch"]}
    plan = {}
    for name, spec in SPECIALISTS.items():
        if spec.get("ext_id"):
            continue
        scope = [channel for channel in spec["channels"]
                 if (channel in held["channels"] or channel in written)
                 and channel_serves_stage(channel, stage)]
        plan[name] = {
            "run": bool(scope), "scope": scope, "gated": None,
            "addressed_by": ["decision_model"] if scope else [],
            "channels": list(spec["channels"]), "facts": {},
        }

    def answer_for(name, state):
        owned = set(SPECIALISTS[name]["channels"])
        results = []
        for row in state.get("ledger_items") or []:
            try:
                chrono = int((row or {}).get("chrono_id") or 0)
            except (TypeError, ValueError):
                chrono = 0
            mine = []
            for transform in transforms.get(chrono) or []:
                patch = {channel: value for channel, value in transform["patch"].items()
                         if channel in owned}
                if patch:
                    mine.append({"item": transform["item"], "patch": patch})
            # NO VERDICTS. `settled`, `not_mine` and the per-thing receipt are
            # the several-hands contract's: they tell "another hand owns this"
            # from "a hand dropped it". With ONE encoder there is no other
            # hand -- a thing it did not change was not changed -- so the
            # answer carries its transforms and nothing else, and
            # `_run_specialists(answer_for=)` skips the per-thing accounting.
            # (Faking `not_mine` receipts had left 56 of 61 alignment
            # warnings across 91 audited beats, every write valid.)
            results.append({
                "transforms": mine,
                "status": "encoded" if mine else "",
            })
        return {"results": results, "notes": []}

    return plan, answer_for


def attach_record(ctx, out):
    """Persist the stage's prose-contract record beside the orchestration
    record, after validation (whose schema dump would drop it)."""
    held = ctx.get(CTX_KEY) if hasattr(ctx, "get") else None
    if not held:
        return
    orchestration = out.setdefault("orchestration", {})
    if isinstance(orchestration, dict):
        orchestration["prose_contract"] = held["record"]
    try:
        ctx[CTX_KEY] = None
    except Exception:
        pass
