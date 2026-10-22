"""A mind's own work in a skip changes the things it worked on.

`docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md` § 4.4 ("Things", its phase 2)
and § 5's phase 2, "things moved in a skip". The skip stage
(`agents/skip_stage.py`) asks every cast member what it does over a stretch the
players' input passes over, lives each answer in code, and leaves each mind
where its own day took it. Bodies moved and THINGS DID NOT. Measured on the
lighthouse replayed on 8e3c60f2 (job tmp `fixes/live_skip6`, chat 3, turns 25
and 26): the keeper put the lamp out at dawn, lit it at dusk and sorted the
station mail, in rows the executor marked `done`, and the lamp, the mail and
every crate stood as the stretch had found them -- while the memory job wrote
that he had done it all. The owner, of exactly this: "And do they actually
change position to reflect their actions?"

THE RULE: a stretch a mind lived and carried out changes the things it worked
on, and nothing else a skip tells does.

  * WHICH ROWS (`told_rows`): `done`, in a room the world holds (`room`, never
    `away`), awake, with a doing of its own -- from either executor's log, the
    mind's own or the town's. A `failed` row did not come off; a `not_known`
    row's outcome is not known (another's response, or what it went without);
    off the map the world holds no thing, and what a mind carries there stays
    carried as it is; a sleep is no work. A routine done on many days is told
    once, on its last.
  * HOW THEY ARE TYPED (`type_mind`). The rows are told in time order as a short
    account of the mind's own doing (`told_account`): deterministic, from each
    row's `doing` and its room -- never its `why`, never what it saw of anyone.
    The engine's ENCODER, the typing authority that turns the Director's prose
    into typed world changes, is asked ONCE per mind with such rows, through
    the Director's own seam (`director_prose._call_encoder`: the same sheet
    assembly, role, schema and cache path), its sheet carrying the skip's own
    piece (`prose_contract.encoder_skip`, `prompts.unified_specialist_prompt`'s
    `stage="skip"`). It holds the channels that change THINGS and no other
    (`WORK_CHANNELS`, and `MATTER_CHANNEL` where the story keeps a matter
    ledger, `work_channels`), and the one part that switches a light or a sound
    (`WORK_PARTS`): never where a body is or how it stands, the clock, speech,
    awareness, or anyone's standing with anyone. Its payload is the account,
    the mind's own identity, and the world it needs to type it
    (`work_payload`): the things the mind had to hand on each told row
    (`to_hand`), those rows' rooms and their fixtures, the matter there.
  * HOW THEY ARE READ (`changes_of`): as every encoder answer is read
    (`director_prose.ledger_from_events`); each transform kept to the granted
    channels, its standing entity named, its identity handles spelled as the
    scene's subjects and validated as a state diff (`director.
    _hydrate_existing_entity_patch`, `director._resolve_identity_handles`,
    `schemas.validated_specialist_patch_channels`), its item names bound to the
    world's keys (`causal_program.bind_items`), and filed under the told row
    whose event id its event carries. A change filed under no told row has no
    time or place to stand at, and is dropped.
  * HOW THEY ARE APPLIED (`settle_work`). Every mind's changes in TIME ORDER --
    by the start of the row each belongs to, so two minds working one thing
    apply in the order they worked it -- each with its mind standing where its
    row was, through the floors a beat's own changes pass: what the mind did
    not have to hand is not its to change (`within_reach`: a thing where the
    row was spent, on the mind, or used by the row's own stretch; never a
    body, never a thing the world does not hold); a transfer from a holder
    that does not hold the thing is refused (`commit_scene_state.
    _refuse_unheld_transfers`); and the merge keeps its containment rules
    (`spatial.merge_scene_with_diff`). NO BODY IS PLACED BY THIS PATH -- no
    channel that places one is granted and no write that moves or holds one is
    kept -- so where every mind ends stays its own log's, and a walk stays its
    owner's (`director_prose.a_walk_is_its_owners` has nothing to refuse here:
    nothing walks).
  * WHERE THEY LAND: at the far end, beside the placements (`skip_stage.
    FarEnd`, through `work_scene`, `things_changed` and `lay_things`) -- an
    onset preview for every stage after the skip, and laid under the beat's own
    diff where the commit composes the scene (`commit_scene_state.
    compose_beat_scene`), so the account that follows the skip keeps the last
    word on every thing it touches. The step output keeps what the encoder was
    told and what passed (`minds[*].worked`), so a rerun from a later stage
    applies the same changes and a reroll of the skip asks again.

THE MEMORIES AGREE BY CONSTRUCTION: the out-of-band memory job
(`mind/skip_memories.py`) reads the same LOG rows through its own allowlist,
so a row it remembers as done is a row whose changes the world now carries. It
reads nothing of `worked`.
"""

from __future__ import annotations

import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from world import skip_itinerary as itin

#: The channels a mind's own work may write: what a thing is and what
#: condition it is in (`entities`), where a thing a body can move lies and who
#: holds it (`inventory_ops`), and what encloses a thing (`containment`).
#: Protocol tokens of the engine's channel table (`director_scopes.
#: SPECIALISTS`). Where any body is, its pose, the clock, speech, awareness and
#: anyone's standing with anyone are never this path's: the skip owns where
#: bodies are, and the rest is a beat's.
WORK_CHANNELS = ("entities", "inventory_ops", "containment")

#: Matter -- a fluid, a powder, a residue -- granted beside them where the
#: story keeps a matter ledger, a standing record a mind's work can mop up,
#: pour out or move (`work_channels`).
MATTER_CHANNEL = "substance_ops"

#: The encoder parts granted with them: the one that switches a light or a
#: sound on and off (`entities__emits`) -- a lamp lit at dusk and put out at
#: dawn is the commonest work a thing shows. Never a part that places a body
#: (`director_prose.BODY_PLACING_PARTS`), mints a thing (`entities__new`: what
#: work MAKES is not built here), joins two places (`entities__link`), or
#: authors what a close look finds (`entities__examined`: a skip tells what
#: the mind did, never what it found).
WORK_PARTS = ("entities__emits",)

#: The stage the encoder's sheet is assembled for, whose piece is
#: `prose_contract.encoder_skip` (`prompts._encoder_pieces`).
WORK_STAGE = "skip"

#: How many minds' work is typed at once: one encoder call each, the stage
#: waiting as long as the slowest. Named per the owner's rule on caps.
SKIP_WORK_WORKERS = 8

#: How many told rows one mind's account carries, nearest the far end kept,
#: after a routine repeated is told on its last day only (`told_rows`). The
#: account is paid once per mind; a week of distinct work fits. Named per the
#: owner's rule on caps.
SKIP_WORK_ROWS = 48

#: How the account names a told row: the event id its changes are filed
#: under, `stretch:<the row's place in the mind's log>`. A protocol token.
EVENT_PREFIX = "stretch:"

#: The ledgers a thing's change can reach, laid at the far end by key
#: (`things_changed`, `lay_things`); the matter ledger, a list, goes whole.
THING_LEDGERS = ("entities", "positions", "contained", "stations")


def _fold(text):
    return " ".join(str(text or "").split()).casefold()


def _words(text):
    return " ".join(str(text or "").split())


# --------------------------------------------------------------------------
# What is told
# --------------------------------------------------------------------------

def told_rows(log):
    """`[index]` -- the rows of one mind's LOG its own work is told from, in
    time order: `done`, in a room the world holds (`room`, never `away`),
    awake, with a doing of its own. A routine done on many days is told once,
    on its last -- what it leaves a thing is the last day's -- and the last
    `SKIP_WORK_ROWS` are kept."""
    picked = {}
    for n, row in enumerate(log or ()):
        if not isinstance(row, dict):
            continue
        doing = _words(row.get("doing"))
        if (row.get("outcome") != itin.OUTCOME_DONE or not row.get("room")
                or row.get("away") or row.get("asleep") or not doing):
            continue
        picked[(str(row["room"]), doing.casefold())] = n
    return sorted(picked.values())[-SKIP_WORK_ROWS:]


def event_id(n):
    return f"{EVENT_PREFIX}{n}"


def told_account(name, log, told, scene):
    """The account the encoder is told: one line per told row, in time order,
    each opening with the row's event id and naming the room it was spent in
    -- its name and its id -- then the mind and its own doing. Deterministic,
    and from nothing else: never the row's `why`, never what it saw of
    anyone."""
    from world.spatial import room_display_name
    rooms = (scene or {}).get("rooms") or {}
    lines = []
    for n in told:
        row = log[n]
        room = str(row.get("room"))
        where = room_display_name(rooms.get(room), room)
        lines.append(f"[{event_id(n)}] {where} ({room}) — {name}: {_words(row.get('doing'))}")
    return "\n".join(lines)


def work_channels(scene):
    """The channels the encoder holds for a mind's work: `WORK_CHANNELS`, and
    `MATTER_CHANNEL` where the story keeps a matter ledger -- a standing
    substance record somewhere in its world (`spatial.substance_ledger_index`)."""
    from world.spatial import substance_ledger_index
    out = list(WORK_CHANNELS)
    try:
        if substance_ledger_index(scene or {}):
            out.append(MATTER_CHANNEL)
    except Exception:  # noqa: BLE001 -- an unreadable ledger keeps none
        pass
    return out


def to_hand(scene, name, log, told, itinerary=(), named=None):
    """`{row index: {thing key}}` -- per told row, the things the mind had to
    hand for it: what stood where the row was spent and what it had on it
    as the row began (`skip_itinerary.Reach.in_reach`, a thing inside another
    where the outer one is), and what the row's own stretch used (its `uses`,
    as the stage's resolution named them -- `named`, `{words: {key}}` -- else
    by name exactly, `Reach.named`): a `done` row's uses were all to hand,
    fetched or not. Things only: never a body, never a fixture -- a fixture is
    where a thing is set, never a thing changed."""
    reach = itin.Reach(scene, name)
    things = {k for k in reach.labels if not k.startswith(itin.FIXTURE_PREFIX)}
    out = {}
    for n in told:
        row = log[n]
        keys = {k for k in things
                if reach.in_reach(k, row.get("room"), None, row.get("from_s"))}
        stretch = itin._stretch_under(itinerary, row) or {}
        for words in stretch.get("uses") or ():
            picked = (named or {}).get(words) or reach.named(words)
            keys |= {k for k in picked if k in things}
        out[n] = keys
    return out


def _worn(scene, name):
    attire = (scene or {}).get("attire") or {}
    entry = next((v for k, v in attire.items() if _fold(k) == _fold(name)), None)
    out = []
    for item in (entry or {}).get("wearing") or () if isinstance(entry, dict) else ():
        text = item if isinstance(item, str) else (item or {}).get("item") \
            if isinstance(item, dict) else ""
        if _words(text):
            out.append(_words(text))
    return out


def work_payload(name, key, log, told, scene, reach, channels, nonce=0):
    """The encoder's payload for one mind's work: the account, the mind's own
    identity and its rows as `event_inputs`, and the world it needs to type
    them -- the things it had to hand on its told rows (`reach`, with what
    encloses them), the rooms those rows were spent in and their fixtures,
    what it wears, and the matter there where the story keeps a ledger. Every
    key is one the Director's encoder payload carries, in the shape its card
    reads. Nothing private: the account is the mind's outward doing, and the
    rest is the world's own record, as the resolve's encoder is handed it."""
    from world.spatial import (effective_anchors, room_display_name,
                               substance_ledger_index)
    rooms = scene.get("rooms") or {}
    entities = scene.get("entities") or {}
    offered = sorted(set().union(*reach.values())) if reach else []
    places = []
    for n in told:
        room = str(log[n]["room"])
        if room not in places:
            places.append(room)
    fixtures = {}
    for room in places:
        authored = {str(aid): _words((anchor or {}).get("desc") or str(aid).replace("_", " "))
                    for aid, anchor in (effective_anchors(scene, room) or {}).items()
                    if not (anchor or {}).get("implicit")}
        if authored:
            fixtures[room] = authored
    payload = {
        "prose": told_account(name, log, told, scene),
        "event_inputs": [{"entity_id": key, "authority_mode": "autonomous",
                          "events": [{"event_id": event_id(n), "type": "stretch",
                                      "room": str(log[n]["room"])} for n in told]}],
        "identity_index": {key: name},
        "world_index": {},
        "standing_relations": {},
        "already_happened": "",
        "pronouns": {},
        "variant_seed": nonce or None,
        "rooms": {room: room_display_name(rooms.get(room), room) for room in places},
        "anchors": fixtures,
        "entities": {k: entities[k] for k in offered if isinstance(entities.get(k), dict)},
        "entity_names": {k: str(entities[k].get("name") or k) for k in offered
                         if isinstance(entities.get(k), dict)},
        "contained": {k: v for k, v in (scene.get("contained") or {}).items()
                      if k in offered and isinstance(v, dict)},
        "worn_garments": [{"name": garment, "worn_by": name}
                          for garment in _worn(scene, name)],
        "places_authored_elsewhere": False,
        "new_places": {},
        "requestable_tools": [],
    }
    if MATTER_CHANNEL in channels:
        where = set(offered) | set(places)
        payload["substances"] = [
            row for row in substance_ledger_index(scene)
            if str(row.get("target") or "") in where
            or _fold(row.get("target")) == _fold(name)]
    return payload


# --------------------------------------------------------------------------
# The call, and what it is read as
# --------------------------------------------------------------------------

def _encode(ctx, channels, payload):
    """`(answer, attempt)` -- the encoder's answer, asked through the
    Director's own seam (`director_prose._call_encoder`) with the work's
    grant and the skip's sheet piece."""
    from agents.director_prose import _call_encoder
    answer, _exchange, attempt = _call_encoder(ctx, list(channels), payload,
                                               list(WORK_PARTS), stage=WORK_STAGE)
    return (answer if isinstance(answer, dict) else {}), attempt


def changes_of(answer, told, name, key, scene, reach, channels):
    """`(changes, record)` -- the encoder's answer as `[{row, patch}]`, each
    change one transform of an event filed under a told row (`row`, its place
    in the log), in the order the encoder wrote them; and what was set aside
    reading it. See the module docstring, "HOW THEY ARE READ"."""
    from agents.director import (_hydrate_existing_entity_patch,
                                 _resolve_identity_handles)
    from agents.director_prose import ledger_from_events
    from llm import schemas
    from world.causal_program import bind_items
    events = [e for e in ((answer or {}).get("events") or []) if isinstance(e, dict)]
    record = {"events": len(events)}
    rows, transforms = ledger_from_events(events, known_channels=list(channels))
    rows_by_id = {event_id(n): n for n in told}
    identity = {key: name}
    pending, foreign, invalid, unfiled = [], set(), [], 0
    for row in rows:
        writes = [t for t in transforms.get(row["chrono_id"]) or () if t.get("patch")]
        n = rows_by_id.get(_words(row.get("source_event_id")))
        if n is None:
            unfiled += len(writes)
            continue
        names = list(row.get("item_names") or [])
        handles = list(row.get("item_ids") or [])
        for write in writes:
            foreign |= {ch for ch in write["patch"] if ch not in channels}
            patch = {ch: v for ch, v in write["patch"].items() if ch in channels}
            if not patch:
                continue
            patch = _resolve_identity_handles(
                _hydrate_existing_entity_patch(scene, patch), identity)
            try:
                patch, dropped = schemas.validated_specialist_patch_channels(
                    "director_objects", patch)
            except Exception as exc:  # noqa: BLE001 -- one transform, not the work
                invalid.append(f"{type(exc).__name__}: {str(exc)[:120]}")
                continue
            invalid.extend(dropped or ())
            if not patch:
                continue
            item = str(write.get("item") or "")
            pending.append({"item_id": handles[names.index(item)] if item in names else 0,
                            "chrono_id": row["chrono_id"], "object_name": item,
                            "patch": patch, "row": n})
    changes = []
    if pending:
        # Item names bound to the world's keys among the things it was shown.
        shown = {"entities": {k: (scene.get("entities") or {}).get(k)
                              for k in set().union(*reach.values())
                              if isinstance((scene.get("entities") or {}).get(k), dict)}}
        bound, _bindings, notes = bind_items(pending, shown)
        if notes:
            record["binding_notes"] = [str(n)[:160] for n in notes]
        changes = [{"row": int(item["row"]), "patch": item["patch"]} for item in bound]
    if unfiled:
        record["unfiled"] = unfiled
    # What it said it lacked, kept for the reader: the grant is fixed, so a
    # tool it asks for is never granted here, and a referent it misses is a
    # thing the world does not hold (what work makes is not built).
    for said in ("missing_tools", "missing_referents", "notes"):
        values = [str(v)[:160] for v in ((answer or {}).get(said) or [])
                  if str(v or "").strip()]
        if values:
            record[said] = values
    if foreign:
        record["channels_dropped"] = sorted(foreign)
    if invalid:
        record["invalid"] = invalid
    record["typed"] = len(changes)
    return changes, record


def type_mind(ctx, name, key, mind, scene, *, named=None, nonce=0):
    """`(worked, reach)` for one mind: None and {} when it has no row to tell
    (no call is made); else `worked` is `{told, changes, record}` -- the rows
    told, what its encoder answer was read as (`changes_of`), and what was
    asked and set aside -- and `reach` the things it had to hand on each
    told row (`to_hand`), which `settle_work` holds its changes to."""
    from llm.providers import Aborted
    log = (mind or {}).get("log") or []
    told = told_rows(log)
    if not told:
        return None, {}
    channels = work_channels(scene)
    reach = to_hand(scene, name, log, told, (mind or {}).get("itinerary") or (), named)
    payload = work_payload(name, key, log, told, scene, reach, channels, nonce)
    record = {"told": len(told), "channels": list(channels),
              "shown": len(payload["entities"])}
    t0 = time.time()
    try:
        answer, attempt = _encode(ctx, channels, payload)
    except Aborted:
        raise
    except Exception as exc:  # noqa: BLE001 -- the things stand as they were
        record["failed"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        return {"told": told, "changes": [], "record": record}, reach
    record["seconds"] = round(time.time() - t0, 3)
    if attempt:
        record["attempt"] = attempt
    changes, read = changes_of(answer, told, name, key, scene, reach, channels)
    record.update(read)
    return {"told": told, "changes": changes, "record": record}, reach


def type_the_work(ctx, minds, scene, ids, *, named=None, nonce=0):
    """The skip stage's last step: every asked mind's own work, typed and
    settled, on its step entry as `worked` -- None for a mind with no row to
    tell, else `{told, changes, record}`. One encoder call per mind with rows,
    in parallel, each in a copy of the stage's context so its call is filed
    under the stage; then every mind's changes are settled together, in time
    order, against the stored world (`settle_work`), and what a floor took out
    is said. `ids` is `{folded mind name: cast id}`; `named` `{mind name:
    {words: {key}}}`, the stage's resolution of what each mind's stretches
    use."""
    from llm.providers import Aborted
    named = named or {}
    jobs = {}
    for name, mind in minds.items():
        mind["worked"] = None
        cid = ids.get(_fold(name))
        if cid is not None and told_rows((mind or {}).get("log")):
            jobs[name] = cid
    if not jobs:
        return
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(SKIP_WORK_WORKERS, len(jobs)))) as pool:
        futures = {name: pool.submit(copy_context().run, type_mind, ctx, name,
                                     f"character:{cid}", minds[name], scene,
                                     named=named.get(name), nonce=nonce)
                   for name, cid in jobs.items()}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Aborted:
                raise
            except Exception as exc:  # noqa: BLE001 -- one mind, not the beat
                results[name] = ({"told": told_rows(minds[name].get("log")), "changes": [],
                                  "record": {"failed": f"{type(exc).__name__}: "
                                                       f"{str(exc)[:160]}"}}, {})
    reach = {}
    for name in sorted(results):
        worked, reach[name] = results[name]
        minds[name]["worked"] = worked
        if (worked or {}).get("record", {}).get("failed"):
            ctx.add_warning(f"skip: what {name}'s own work changed was not typed "
                            f"({worked['record']['failed']}); the things stand as "
                            "the stretch found them")

    def report(name, kind, detail):
        record = (minds[name].get("worked") or {}).setdefault("record", {})
        record.setdefault(kind, []).append(str(detail)[:240])
        ctx.add_warning(f"skip: {name}'s work -- {kind}: {str(detail)[:200]}")

    settle_work(scene, minds, reach, report=report)
    for name in results:
        worked = minds[name].get("worked")
        if isinstance(worked, dict):
            worked.setdefault("record", {})["landed"] = len(worked.get("changes") or ())
    if hasattr(ctx, "note_decision"):
        for name in sorted(results):
            worked = minds[name].get("worked") or {}
            ctx.note_decision("skip_work", name,
                              "failed" if worked.get("record", {}).get("failed")
                              else "typed",
                              json.dumps(worked.get("record") or {},
                                         ensure_ascii=False)[:400])


# --------------------------------------------------------------------------
# The floors, and the changes applied in time order
# --------------------------------------------------------------------------

class _Notes:
    """What `_refuse_unheld_transfers` says, kept rather than told: a refusal
    of a skip's change is the skip's record, never a note to this beat's
    Director, which never wrote it."""

    def __init__(self):
        self.notes = []

    def tell_director(self, note):
        self.notes.append(str(note))

    def add_warning(self, note):
        pass


def _steps(minds):
    """Every mind's changes, in TIME ORDER: by the start of the row each
    belongs to, then its end, then the mind's name, then the order its
    encoder wrote them -- two minds working one thing apply in the order they
    worked it."""
    out = []
    for name in sorted(minds or {}):
        mind = minds[name] or {}
        worked = mind.get("worked")
        if not isinstance(worked, dict):
            continue
        log = mind.get("log") or []
        for order, change in enumerate(worked.get("changes") or ()):
            n = change.get("row") if isinstance(change, dict) else None
            if not isinstance(n, int) or not 0 <= n < len(log):
                continue
            row = log[n] or {}
            if not row.get("room"):
                continue
            out.append({"from_s": float(row.get("from_s") or 0.0),
                        "until_s": float(row.get("until_s") or 0.0),
                        "name": name, "order": order, "row": n,
                        "room": str(row["room"]), "change": change})
    out.sort(key=lambda s: (s["from_s"], s["until_s"], s["name"], s["order"]))
    return out


def _stand(scene, name, room):
    """The mind where its row was, in a working copy of the world: a change
    is judged against the room its mind did the work in, and a body carried
    or held where the stretch began is not where the stretch put it."""
    positions = scene.setdefault("positions", {})
    key = next((k for k in positions if _fold(k) == _fold(name)), name)
    if positions.get(key) == room:
        return
    positions[key] = room
    for ledger in ("stations", "contained"):
        table = scene.get(ledger)
        if isinstance(table, dict):
            for k in [k for k in table if _fold(k) == _fold(name)]:
                table.pop(k, None)


def within_reach(scene, name, room, patch, uses=()):
    """`(kept, dropped)` -- `patch` with every write past what the mind had to
    hand for this row taken out, and what was taken.

    A MIND'S WORK CHANGES ONLY WHAT IT HAD TO HAND. A thing it changes is one
    the world holds and no body: standing where the row was spent (inside
    another thing there included), on the mind, or used by the row's own
    stretch (`uses`, its keys) -- a `done` row's uses were to hand, fetched or
    not. A thing it moves comes from, and goes to, the mind itself, the
    room the row was spent in, one of that room's fixtures, or such a thing;
    what encloses a thing is the mind or such a thing; and matter it moves is
    on or from one of those. Never another body: what another mind holds or
    carries is that mind's to change, and no body is ever moved or held by
    this path. `scene` is the world at that moment, the mind standing in
    `room` (`settle_work`)."""
    from world.spatial import effective_anchors, substance_ledger_index
    reach = itin.Reach(scene, name)
    used = {str(k) for k in uses or ()}
    fixtures = {str(a) for a in (effective_anchors(scene, room) or {})}

    def thing(ref):
        key = _words(ref)
        return (bool(key) and key in reach.labels
                and not key.startswith(itin.FIXTURE_PREFIX)
                and (key in used or reach.in_reach(key, room)))

    def holder(ref):
        return _fold(ref) == _fold(name) or thing(ref)

    def place(ref):
        ref = _words(ref)
        return bool(ref) and (holder(ref) or ref == str(room) or ref in fixtures)

    standing = None
    kept, dropped = {}, []
    for channel, value in (patch or {}).items():
        if channel == "entities" and isinstance(value, dict):
            ok = {k: v for k, v in value.items() if thing(k)}
            dropped += [f"entities.{k}" for k in value if k not in ok]
        elif channel == "inventory_ops" and isinstance(value, list):
            ok = [op for op in value if isinstance(op, dict)
                  and thing(op.get("object_id")) and place(op.get("to_id"))
                  and (not _words(op.get("from_id")) or place(op.get("from_id")))]
            dropped += ["inventory_ops: " + json.dumps(op, ensure_ascii=False)[:160]
                        for op in value if op not in ok]
        elif channel == "containment" and isinstance(value, dict):
            ok = {k: v for k, v in value.items() if thing(k) and (
                v is None or (isinstance(v, dict) and holder(v.get("in"))))}
            dropped += [f"containment.{k}" for k in value if k not in ok]
        elif channel == MATTER_CHANNEL and isinstance(value, list):
            if standing is None:
                standing = {str(r.get("substance_id")): r
                            for r in substance_ledger_index(scene)}
            ok = []
            for op in value:
                if not isinstance(op, dict):
                    continue
                pools = [_words(op.get(f)) for f in ("substance_id", "source_substance_id")
                         if _words(op.get(f))]
                good = all(p in standing and place(standing[p].get("target")) for p in pools)
                if _words(op.get("target")):
                    good = good and place(op.get("target"))
                elif not pools:
                    good = False
                if _words(op.get("source")):
                    good = good and place(op.get("source"))
                if good:
                    ok.append(op)
                else:
                    dropped.append(f"{MATTER_CHANNEL}: "
                                   + json.dumps(op, ensure_ascii=False)[:160])
        else:
            ok = None
            dropped.append(channel)
        if ok:
            kept[channel] = ok
    return kept, dropped


def settle_work(scene, minds, reach, report=None):
    """Every mind's typed changes applied to a copy of `scene` in time order
    (`_steps`), each with its mind standing where its row was (`_stand`),
    through the floors: `within_reach` (the things it had to hand, `reach`:
    `{mind: {row: {key}}}`), then `commit_scene_state._refuse_unheld_transfers`
    against the world at that moment, then the merge. Each change keeps, in
    place, only what passed -- so the step output says what lands -- and a
    change left with nothing goes. `report(mind, kind, detail)` hears every
    write a floor took out (`out_of_reach`, `unheld`). Returns the world
    after."""
    from persist.commit import _refuse_unheld_transfers
    from world.spatial import merge_scene_with_diff
    report = report or (lambda *_args: None)
    work = copy.deepcopy(scene if isinstance(scene, dict) else {})
    for step in _steps(minds):
        name, change = step["name"], step["change"]
        _stand(work, name, step["room"])
        patch, dropped = within_reach(work, name, step["room"], change.get("patch"),
                                      ((reach or {}).get(name) or {}).get(step["row"]) or ())
        for item in dropped:
            report(name, "out_of_reach", item)
        notes = _Notes()
        _refuse_unheld_transfers(notes, work, patch)
        for note in notes.notes:
            report(name, "unheld", note)
        patch = {ch: v for ch, v in patch.items() if v}
        change["patch"] = patch
        if patch:
            work = merge_scene_with_diff(work, patch, age_contacts=False)
    for mind in (minds or {}).values():
        worked = (mind or {}).get("worked")
        if isinstance(worked, dict):
            worked["changes"] = [c for c in worked.get("changes") or ()
                                 if isinstance(c, dict) and c.get("patch")]
    return work


def work_scene(scene, minds):
    """The world after every mind's settled changes (`settle_work` wrote what
    passed onto the step): applied in the same order with each mind standing
    where its row was, under the one floor that reads only the world at that
    moment (`_refuse_unheld_transfers`, which refuses nothing a settled change
    still holds); then every mind that worked stood where the far end leaves
    it -- off the scene when it ends off the map -- so a thing it carries is
    where it is. Read by `skip_stage.FarEnd` through `things_changed`.

    ONE MERGE A ROW: a row's changes, consecutive in `_steps`' order, are
    folded into one patch in the order the encoder wrote them
    (`causality._merge_channel`, the beat's own fold) -- a merge is a whole
    scene's work, and the far end is laid for every stage after the skip."""
    from persist.commit import _refuse_unheld_transfers
    from world.causality import _merge_channel
    from world.spatial import derive_contained_positions, merge_scene_with_diff
    steps = _steps(minds)
    work = copy.deepcopy(scene if isinstance(scene, dict) else {})
    if not steps:
        return work
    rows = []
    for step in steps:
        if not rows or (rows[-1]["name"], rows[-1]["row"]) != (step["name"], step["row"]):
            rows.append({"name": step["name"], "row": step["row"], "room": step["room"],
                         "patch": {}})
        for channel, value in (step["change"].get("patch") or {}).items():
            _merge_channel(rows[-1]["patch"], channel, value)
    for row in rows:
        _stand(work, row["name"], row["room"])
        patch = row["patch"]
        _refuse_unheld_transfers(_Notes(), work, patch)
        patch = {ch: v for ch, v in patch.items() if v}
        if patch:
            work = merge_scene_with_diff(work, patch, age_contacts=False)
    positions = work.setdefault("positions", {})
    for name in sorted({step["name"] for step in steps}):
        far = ((minds.get(name) or {}).get("far_end") or {})
        key = next((k for k in positions if _fold(k) == _fold(name)), name)
        if far.get("room"):
            positions[key] = far["room"]
        else:
            positions.pop(key, None)
    derive_contained_positions(work)
    return work


def things_changed(before, after, minds):
    """`{ledger: {key: record or None}}` (and `substances`, whole, where matter
    moved) -- what the settled changes did to THINGS between `before` and
    `after` (`work_scene`): the records of every thing a change named, and of
    whatever lies inside one, in `THING_LEDGERS`; None where a record is gone.
    Never a body's record: where a body is stays the far end's."""
    from world.spatial import scene_names_body
    touched, matter = set(), False
    for step in _steps(minds):
        patch = step["change"].get("patch") or {}
        touched |= {str(k) for k in (patch.get("entities") or {})}
        touched |= {_words(op.get("object_id")) for op in patch.get("inventory_ops") or ()
                    if isinstance(op, dict)}
        touched |= {str(k) for k in (patch.get("containment") or {})}
        matter = matter or bool(patch.get(MATTER_CHANNEL))
    touched.discard("")
    for scene in (before, after):
        contained = (scene or {}).get("contained") or {}
        grew = True
        while grew:
            grew = False
            for key, record in contained.items():
                into = _words((record or {}).get("in")) if isinstance(record, dict) else ""
                if into in touched and str(key) not in touched:
                    touched.add(str(key))
                    grew = True
    touched = {k for k in touched
               if not scene_names_body(before, k) and not scene_names_body(after, k)}
    delta = {}
    for ledger in THING_LEDGERS:
        b = (before or {}).get(ledger) if isinstance((before or {}).get(ledger), dict) else {}
        a = (after or {}).get(ledger) if isinstance((after or {}).get(ledger), dict) else {}
        changed = {k: copy.deepcopy(a.get(k)) for k in sorted(touched) if b.get(k) != a.get(k)}
        if changed:
            delta[ledger] = changed
    if matter and (before or {}).get("substances") != (after or {}).get("substances"):
        delta["substances"] = copy.deepcopy((after or {}).get("substances") or [])
    return delta


def things_at_far_end(scene, minds):
    """`things_changed` over `work_scene`: what the minds' settled work does
    to the things of `scene`, a scene read from the store. {} -- and no copy
    of the world made -- when no mind's work changed anything."""
    if not _steps(minds):
        return {}
    return things_changed(scene, work_scene(scene, minds), minds)


def lay_things(scene, delta):
    """`delta` (`things_changed`) laid onto a scene read from the store, in
    place: each changed record set by its key, a record gone popped, the
    matter ledger replaced whole."""
    if not isinstance(scene, dict) or not delta:
        return scene
    for ledger in THING_LEDGERS:
        changed = delta.get(ledger)
        if not changed:
            continue
        table = scene.get(ledger)
        if not isinstance(table, dict):
            table = scene[ledger] = {}
        for key, value in changed.items():
            if value is None:
                table.pop(key, None)
            else:
                table[key] = copy.deepcopy(value)
    if "substances" in delta:
        scene["substances"] = copy.deepcopy(delta["substances"])
    return scene
