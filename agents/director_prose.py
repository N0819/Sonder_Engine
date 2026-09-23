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

import time

from core.db import get_setting
from llm import decisions
from llm.prompts import (
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
    return prose


# ---- 2. the decision model picks the tools -------------------------------

def _jev_state(prose, model_payload):
    """What Jev judges: the passage, plus the two facts a channel question
    can turn on and prose alone may not settle -- who the people are, and
    which places already exist (a room question asks about a NEW place)."""
    identities = sorted({str(v) for v in (model_payload.get("identity_index") or {}).values() if v})
    rooms = sorted({str(v) for v in ((model_payload.get("object_index") or {}).get("rooms") or {}).values() if v})
    lines = ["PASSAGE:", prose, ""]
    if identities:
        lines.append("PEOPLE: " + ", ".join(identities))
    if rooms:
        lines.append("PLACES ALREADY KNOWN: " + ", ".join(rooms))
    return "\n".join(lines)


def select_channels(ctx, stage, prose, model_payload, facts=None):
    """`(selected, record)`. Fails OPEN: if the decision model cannot answer,
    every candidate is granted -- a larger sheet, never a lost change."""
    candidates = candidate_channels(stage, facts)
    questions = jev_channel_questions(candidates, ctx.language)
    record = {"candidates": candidates, "threshold": _threshold()}
    t0 = time.time()
    try:
        answers = decisions.decide(_jev_state(prose, model_payload), {
            channel: {"type": "noul", "instructions": text}
            for channel, text in questions.items()
        })
    except Exception as exc:
        record.update(failed=str(exc), seconds=round(time.time() - t0, 3))
        ctx.add_warning(f"{stage}: decision model unavailable, every channel "
                        f"granted (fail-open): {exc}")
        record["selected"] = list(candidates)
        return list(candidates), record
    probabilities = {channel: round(decisions.probability(answers.get(channel)), 4)
                     for channel in questions}
    selected = [channel for channel in candidates
                if channel not in questions
                or probabilities.get(channel, 0.0) >= record["threshold"]]
    record.update(probabilities=probabilities, selected=selected,
                  seconds=round(time.time() - t0, 3))
    return selected, record


# ---- 3. one encoder builds -----------------------------------------------

def encoder_payload(ctx, sc, prose, model_payload, view, extras, channels):
    """The prose, the Director's own inputs, and the union of the world
    slices each selected channel's owner would have received. A key two
    owners both supply is taken once (the first owner in canonical order)."""
    payload = {
        "prose": prose,
        "event_inputs": model_payload.get("event_inputs") or [],
        "identity_index": model_payload.get("identity_index") or {},
        "world_index": model_payload.get("world_index") or {},
        "standing_relations": model_payload.get("standing_relations") or {},
        "already_happened": model_payload.get("already_happened") or "",
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
                     for dest in destinations):
        tools.append("rooms")
    return tools


def _call_encoder(ctx, channels, payload):
    return _agent_json(
        "director_specialist",
        "director_specialist",
        unified_specialist_prompt(channels, ctx.language),
        dict(payload, granted_tools=list(channels)),
        temperature=0.2,
        max_tokens=None,
    ) or {}


def encode(ctx, stage, sc, prose, model_payload, view, extras, channels, facts=None):
    """`(answer, channels, record)`: the encoder's events and the tools it
    finally held. At most one widening pass, whose answer REPLACES the
    first."""
    record = {}
    payload = encoder_payload(ctx, sc, prose, model_payload, view, extras, channels)
    t0 = time.time()
    answer = _call_encoder(ctx, channels, payload)
    record["seconds"] = round(time.time() - t0, 3)
    known = set(candidate_channels(stage, facts))
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
    t0 = time.time()
    prose = author(ctx, stage, model_payload)
    author_seconds = round(time.time() - t0, 3)
    channels, jev = select_channels(ctx, stage, prose, model_payload, facts)
    answer, channels, encoding = encode(
        ctx, stage, sc, prose, model_payload, view, extras, channels, facts)
    rows, transforms = ledger_from_events(answer.get("events") or [])
    record = {
        "stage": stage,
        "prose": prose,
        "author_seconds": author_seconds,
        "jev": jev,
        "channels": channels,
        "encoder": encoding,
        "events": answer.get("events") or [],
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
            touched = {t["item"].casefold() for t in mine}
            settled = {str(item): "not_mine"
                       for item in (row or {}).get("item_names") or []
                       if str(item).casefold() not in touched}
            results.append({
                "transforms": mine,
                "status": "encoded" if mine else "not_mine",
                "required_channels": [], "reroute_to": "",
                "settled": settled,
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
