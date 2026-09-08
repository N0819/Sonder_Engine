"""Measure the six per-beat hygiene costs of review 2026-09-07 item C20.

Each probe reports the SQL statements a beat issues and the bytes it writes,
so a "write on change" or "load once" fix can be shown to have changed the
count and nothing else. Nothing here runs a beat or calls a model: every
probe reads stored rows and calls the derivation directly.

Run it against a COPY of a story database (never a live one -- probe 1 and 2
write)::

    python tools/bench/bench_commit_hygiene.py --db /path/to/copy.db --chat 117

Probes, and what each one counts:

1. ``ledger_writes``   -- `persist.commit_mapping`'s per-beat `lore_cache` /
   `active_books` / `known` writes: INSERTs issued and bytes written when the
   value is byte-identical to what is stored (which it is on most beats).
2. ``planning_needs``  -- `world.planning_needs.record_planning_needs` filing
   this beat's needs onto the frame ledger, plus whether
   `schedule_planning_needs` queues a drain job the drain cannot answer.
3. ``beneath``         -- `attire_beneath` setting reads per composed attire
   view (`agents.common.attire_delivery` / `scene_compact_attire`).
4. ``presence``        -- world-row reads for the crowds / couriers / notices
   a perception stage delivers to each perceiver.
5. ``ledger_queries``  -- the stored-variant window queries the character
   stage issues per character (`_recent_self_lines`, `_recent_self_moves`,
   `_unanswered_question_note`, `_player_quiet_beats`).
6. ``manifest``        -- sheet normalizations inside
   `agents.perception._delivered_manifest` for one observer's sources.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from core import db  # noqa: E402


class Counter:
    """SQL statements seen on this thread's connection, by leading verb."""

    def __init__(self):
        self.statements = []

    def __call__(self, sql):
        self.statements.append(" ".join(str(sql).split()))

    def verbs(self):
        out = {}
        for sql in self.statements:
            verb = sql.split(" ", 1)[0].upper()
            out[verb] = out.get(verb, 0) + 1
        return out

    def matching(self, needle):
        return [s for s in self.statements if needle in s]


@contextmanager
def counted():
    counter = Counter()
    connection = db.conn()
    connection.set_trace_callback(counter)
    try:
        yield counter
    finally:
        connection.set_trace_callback(None)


def probe_ledger_writes(cid, frame_id=None):
    """C20a: the three per-beat world writes commit_mapping makes."""
    from core.db import wget

    values = {key: wget(cid, key, default)
              for key, default in (("lore_cache", []), ("active_books", []),
                                   ("known", {}))}
    payload = sum(len(json.dumps(v)) for v in values.values())
    with counted() as counter:
        for key, value in values.items():
            _write_ledger(cid, key, value)
    writes = len(counter.matching("INSERT INTO world"))
    return {"writes": writes,
            "bytes": payload if writes else 0,
            "identical_bytes_offered": payload,
            "statements": counter.verbs()}


def _write_ledger(cid, key, value):
    """Whichever write commit_mapping has: the change-guarded one if the
    tree carries it, else the unconditional one."""
    if hasattr(db, "wset_if_changed"):
        return db.wset_if_changed(cid, key, value)
    return db.wset(cid, key, value)


def probe_planning_needs(cid, frame_id=None, needs=2):
    """C20b: filing this beat's needs, and the drain job scheduled after."""
    from world import planning_needs as pn

    stored = pn.planning_needs(cid, frame_id)
    beat = [{"kind": "room", "reason": "location_query_unmatched",
             "subject": "bench probe room %d" % i} for i in range(needs)]
    with counted() as counter:
        pn.record_planning_needs(cid, beat, frame_id=frame_id)
    written = len(counter.matching("INSERT INTO world"))
    ledger_bytes = len(json.dumps(pn.planning_needs(cid, frame_id)))
    # Put the ledger back the way it was: this probe writes.
    pn.save_planning_needs(cid, stored, frame_id=frame_id)
    return {"needs_filed": needs,
            "reads": len(counter.matching("SELECT value FROM world")),
            "writes": written,
            "bytes": written * ledger_bytes,
            # What the out-of-band drain job is scheduled against: the drain
            # answers person-needs alone, so a ledger of open room/thing needs
            # is a job with nothing to do.
            "open_needs": len(pn.open_planning_needs(cid, frame_id)),
            "open_person_needs": len(
                pn.open_planning_needs(cid, frame_id, kind="person"))}


def probe_beneath(cid, bodies=12, observers=6):
    """C20c: `attire_beneath` reads per composed attire view."""
    from agents import common
    from core.db import wget

    scene = wget(cid, "scene", {}) or {}
    ledger = dict(scene.get("attire") or {})
    if not ledger:
        return {"skipped": "no attire ledger in this chat"}
    template = next(iter(ledger.values()))
    for i in range(len(ledger), bodies):
        ledger["bench body %d" % i] = json.loads(json.dumps(template))
    scene = dict(scene, attire=ledger)
    names = list(ledger)
    with counted() as counter:
        common.scene_compact_attire(scene)
        for observer in names[:observers]:
            common.observer_body_regions(
                scene, observer,
                body_labels={name: name for name in names})
    return {"bodies": len(names), "observers": min(observers, len(names)),
            "setting_reads": len(
                counter.matching("SELECT value FROM settings")),
            "statements": counter.verbs()}


def probe_presence(cid, perceivers=6):
    """C20d: crowds/couriers/notices world reads across a stage's perceivers."""
    from agents import common
    from core.db import wget

    scene = wget(cid, "scene", {}) or {}
    rooms = list((scene.get("rooms") or {}))[:perceivers] or [""]
    with counted() as counter:
        # The stage's shared fetch is inside the count: after the fix it is
        # where the three ledger reads happen.
        inputs = common.chatter_inputs(cid, scene)
        for room in rooms:
            common.crowds_for_room(cid, scene, room, inputs)
            _call_with_inputs(common.couriers_for_room, cid, scene, room,
                              inputs)
            _call_with_inputs(common.artifacts_for_room, cid, scene, room,
                              inputs)
    return {"perceivers": len(rooms),
            "world_reads": len(counter.matching("SELECT value FROM world")),
            "statements": counter.verbs()}


def _call_with_inputs(fn, cid, scene, room, inputs):
    try:
        return fn(cid, scene, room, inputs)
    except TypeError:
        return fn(cid, scene, room)


def probe_ledger_queries(cid, frame_id=None, characters=3):
    """C20e: the stored-variant windows the character stage reads per mind."""
    from agents import character as ch
    from core.db import q

    row = q("SELECT MAX(idx) AS m FROM turns WHERE chat_id=?", (cid,),
            one=True)
    turn_idx = int((row["m"] if row else 0) or 0)
    char_ids = [r["char_id"] for r in
                q("SELECT char_id FROM chat_chars WHERE chat_id=?", (cid,))]
    while len(char_ids) < characters:
        char_ids.append(char_ids[-1] if char_ids else 1)
    char_ids = char_ids[:characters]
    shared = {}
    with counted() as counter:
        for char_id in char_ids:
            _cached(ch._recent_self_lines, shared, cid, "Bench Body", turn_idx,
                    frame_id=frame_id)
            _cached(ch._recent_self_moves, shared, cid, char_id, turn_idx,
                    frame_id=frame_id)
            _cached(ch._player_quiet_beats, shared, cid, turn_idx, frame_id)
            ch._unanswered_question_note(
                cid, "Bench Body", char_id, turn_idx, frame_id,
                cache={}, **_rows_cache_kwarg(ch, shared))
    joins = [s for s in counter.statements if "JOIN variants" in s]
    return {"characters": len(char_ids),
            "window_queries": len(joins),
            "statements": counter.verbs()}


def _cached(fn, shared, *args, **kwargs):
    try:
        return fn(*args, cache=shared, **kwargs)
    except TypeError:
        return fn(*args, **kwargs)


def _rows_cache_kwarg(module, shared):
    import inspect

    if "rows_cache" in inspect.signature(
            module._unanswered_question_note).parameters:
        return {"rows_cache": shared}
    return {}


def probe_manifest(cid, sources=8):
    """C20f: sheet normalizations per observer inside _delivered_manifest."""
    from agents import perception
    from core.db import q, wget

    scene = wget(cid, "scene", {}) or {}
    rows = q("SELECT sheet FROM chat_chars WHERE chat_id=?", (cid,))
    if not rows:
        return {"skipped": "no cast"}
    sheet = json.loads(rows[0]["sheet"] or "{}")
    names = list((scene.get("positions") or {})) or ["Bench Body"]
    while len(names) < sources:
        names.append("bench source %d" % len(names))
    names = names[:sources]

    class _Ctx:
        character_results = {i: {"manifest": {
            "surface_demeanor": "unreadable",
            "tells": [{"cue": "a hand flexes", "channel": "sight",
                       "subtlety": 0.2}]}} for i in range(len(names))}

    cast_by_name = {name: i for i, name in enumerate(names)}
    src = [{"name": name, "room": None} for name in names]
    calls = []
    original = perception._tell_acuity
    perception._tell_acuity = lambda sh: calls.append(1) or original(sh)
    runs = []
    try:
        for _ in range(5):
            started = time.perf_counter()
            perception._delivered_manifest(
                _Ctx(), scene, names[0], src, {}, cast_by_name, sheet)
            runs.append(time.perf_counter() - started)
    finally:
        perception._tell_acuity = original
    return {"sources": len(names), "acuity_reads": len(calls) // len(runs),
            "ms_best_of_5": round(min(runs) * 1000, 3)}


PROBES = {
    "ledger_writes": probe_ledger_writes,
    "planning_needs": probe_planning_needs,
    "beneath": probe_beneath,
    "presence": probe_presence,
    "ledger_queries": probe_ledger_queries,
    "manifest": probe_manifest,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True,
                        help="path to a COPY of a story database")
    parser.add_argument("--chat", type=int, required=True)
    parser.add_argument("--probe", action="append", choices=sorted(PROBES),
                        help="default: every probe")
    args = parser.parse_args()

    db.configure(args.db)
    out = {}
    for name in (args.probe or sorted(PROBES)):
        try:
            out[name] = PROBES[name](args.chat)
        except Exception as exc:  # a probe that cannot run says so
            out[name] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    print(json.dumps(out, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
