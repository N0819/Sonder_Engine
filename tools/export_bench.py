#!/usr/bin/env python3
"""The export-based debug harness: a few chats, not the whole database.

`tools/room_bench.prepare_copy` copies the owner's database whole with the
sqlite backup API. That was right when the file was 300 MB; at 3.4 GB on a
disk with 4 GB free it no longer fits, and most of what it copied (a hundred
chats, their memories, their charters) is not what a debug run reads. This
harness takes the other route: each chat is EXPORTED through the portable
archive (`persist/chat_archive.py`, the same code `GET /api/chats/{cid}/
export` runs) over a READ-ONLY connection to the source, a fresh scratch
database is created with `db.init()`, the archives are imported through the
same service the UI's import button uses, and then the rows a beat needs but
an archive does not carry -- the whole `providers` table and the whole
`settings` table less the host-auth rows -- are copied table-to-table with
ATTACH ... INSERT ... SELECT, so a provider's API key moves between two
files without ever being read into Python, let alone printed. `leaks(text)`
is the check the report writer runs on its own output before writing it: it
answers True/False and never says what it found; `scan` runs the same check
over every file a run wrote. The owner's ruling (2026-09-05): the scratch
database carries EVERYTHING the owner's engine holds for model wiring --
every provider row, the whole `agent_models` map (every role, its fallbacks,
its per-role parameters), and every setting a call reads -- not a subset.

The source is opened with `?mode=ro`. Any write against it raises
`sqlite3.OperationalError: attempt to write a readonly database`, which is
the guarantee the owner's database wants: it is evidence, and stays as it is.
(A read-only open of a WAL database still creates an empty `-wal` and a
`-shm` index beside it when none exist -- SQLite's own behaviour; the data
file is not touched, and `tests/test_export_bench.py` pins the digest.)

    .venv/bin/python tools/export_bench.py prepare --src engine.db \\
        --chats 114 115 --out /path/to/scratch/bench.db \\
        --model default=3:google/gemini-3.8-flash

    .venv/bin/python tools/export_bench.py beat --db bench.db --chat 1 \\
        --text "I step into the corridor." [--frame 0]

    .venv/bin/python tools/export_bench.py stages --db bench.db --chat 1 --turn 4
    .venv/bin/python tools/export_bench.py trace  --db bench.db --chat 1 --turn 4 --out dir/
    .venv/bin/python tools/export_bench.py scan   --db bench.db <file-or-dir> ...

The beat runner and the stage reader are `tools/room_bench.run_beat` and
`read_stages`, wrapped: `run_beat` here retries a beat whose stage failed on
a reasoning-only reply (`ReasoningBudgetExhausted`, DEBUG_RUN F1) from the
failed stage up to `F1_RETRIES` times and then records the beat as F1-class
and returns, so a run continues past a model tic instead of dying on it.
`room()` does the same for the Writers' Room's reply. Every reader here is a
READ of committed rows -- nothing in this module is in any agent's loop.

Tables the scratch database receives from the source, and nothing else:

* through the archive, per chat: chats, frames, turns, steps, variants,
  world (every key, frame-scoped keys included), chat_chars,
  chat_char_frames, chat_personas, memories, memory summaries, events,
  checkpoints, the normalized world tables (`chat_archive.WORLD_TABLES`:
  room_registry among them), turn_player_inputs, room messages, lorebooks
  and their entries and links, lore overlays, and the referenced characters
  and personas as resources (re-created in the scratch db under new ids);
* `providers`: every row, every column, table-to-table (`COPIED_TABLES`);
* `settings`: every row, table-to-table, except `SETTINGS_EXCLUDED` -- the
  host account (`host_username`, `host_pw_hash`, `host_pw_salt`,
  `host_secret`, `host_secret_hash`), which is login state and not model
  wiring. Everything `get_setting` reads on a beat therefore arrives as the
  owner has it: `agent_models` whole (every role, `fallbacks`, sampler
  keys), `reasoning_effort`, `max_output_tokens`, `openrouter_routing`,
  `providers_no_json_schema`, the prompt-cache lists, `prompt_presets` and
  `active_preset`, `director_fanout_mode`, `director_orchestration`,
  `resolve_deep_audit`, `narrator_history_turns`, `exemplars`,
  `attire_beneath`, `affect_habituation`, `auto_promote`, the log level,
  `ui_language`, the research provider and key, the extension settings.
* `SETTINGS_FORCED` is written last and is the harness's own policy, not
  wiring: adult content off (these runs use a third-party model whose terms
  forbid it), backdrops and ambience off (no image or sound calls), and
  CAPTURE ON with full bodies (`llm_capture_enabled=1`,
  `llm_capture_bodies=full`), because what each stage was SENT -- the
  Director's specialist sub-calls included, which have no step of their own
  -- is readable afterwards only through `persist.pipeline_trace.
  export_turn_debug(turn_id, include_content=True)`, and that reads the
  capture table. `read_trace` wraps it. Writers' Room calls are NOT captured
  (only `agents/runtime.py` records); a Room reply is read from its return
  value and its tool events, and that gap is noted, not built.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.room_bench import (STAGE_KEYS, read_stages as _read_stages,  # noqa: E402
                              require_copy, run_beat as _run_beat_once)

#: Tables copied whole, table-to-table, from the source. `providers` carries
#: the API keys; it is the reason the copy is SQL and not Python.
COPIED_TABLES = ("providers",)

#: Settings NOT copied: the host account. Login state, not model wiring;
#: a scratch database has no host and needs none.
SETTINGS_EXCLUDED = ("host_username", "host_pw_hash", "host_pw_salt",
                     "host_secret", "host_secret_hash")

#: Settings whose values are secrets `leaks` also screens for, beside every
#: provider key. Copied (the research tool needs its key); never printed.
SETTINGS_SECRET = ("research_key", "freesound_key")

#: Written after the copy, unconditionally. The harness's own policy.
SETTINGS_FORCED = {"nsfw_enabled": "0", "backdrops_enabled": "0",
                   "ambience_enabled": "0",
                   "llm_capture_enabled": "1", "llm_capture_bodies": "full"}

#: Reasoning-only replies tolerated before a beat is recorded as F1-class.
F1_RETRIES = 3

#: The text of the failure the F1 rule matches, from `llm.providers`.
F1_MARKS = ("ReasoningBudgetExhausted", "returned reasoning but no answer")

assert not set(SETTINGS_EXCLUDED) & set(SETTINGS_FORCED)


# ---------------------------------------------------------------------------
# The read-only source
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def read_only_session(source):
    """Point `core.db` at ``source`` through a connection opened with
    `?mode=ro`, for the duration. The engine's own `conn()` has no read-only
    mode and would open the file writable and set WAL on it; installing the
    connection into its thread-local slot is how every `q()` inside the
    block reads the source and no write can reach it. Restores the previous
    database afterwards."""
    from core import db
    source = os.path.abspath(source)
    previous = db.DB
    db.close_connection()
    ro = sqlite3.connect("file:%s?mode=ro" % source, uri=True,
                         timeout=30.0, check_same_thread=False)
    ro.row_factory = sqlite3.Row
    ro.execute("PRAGMA query_only=1")
    db.DB = source
    db._local.conn = ro
    db._local.db_path = source
    db._local.tx_depth = 0
    db.bump_world_epoch()
    try:
        yield ro
    finally:
        try:
            ro.close()
        finally:
            db._local.conn = None
            db._local.db_path = None
            db._local.tx_depth = 0
            db.DB = previous
            db.bump_world_epoch()


def export_chats(source, chat_ids):
    """The portable archive of each chat, read from ``source`` read-only.
    Returns {chat_id: archive}."""
    from web.app import chat_export
    archives = {}
    with read_only_session(source):
        for cid in chat_ids:
            archives[int(cid)] = json.loads(json.dumps(chat_export(int(cid)),
                                                       default=str))
    return archives


# ---------------------------------------------------------------------------
# The scratch database
# ---------------------------------------------------------------------------

def copy_rows(source, out_db):
    """`COPIED_TABLES` whole and every `settings` row but `SETTINGS_EXCLUDED`,
    source -> scratch, inside SQLite. Returns the table and setting names
    copied (never a value)."""
    source = os.path.abspath(source)
    # Opened as a URI so the ATTACH below may carry `?mode=ro`: a URI
    # filename is honoured only on a connection opened with URI handling.
    con = sqlite3.connect("file:%s" % out_db, uri=True)
    con.execute("ATTACH DATABASE ? AS src", ("file:%s?mode=ro" % source,))
    copied = {"tables": [], "settings": []}
    try:
        with con:
            for table in COPIED_TABLES:
                cols = [r[1] for r in con.execute("PRAGMA main.table_info(%s)" % table)]
                src_cols = {r[1] for r in con.execute("PRAGMA src.table_info(%s)" % table)}
                shared = [c for c in cols if c in src_cols]
                names = ",".join(shared)
                con.execute("DELETE FROM main.%s" % table)
                con.execute("INSERT INTO main.%s(%s) SELECT %s FROM src.%s"
                            % (table, names, names, table))
                copied["tables"].append(table)
            marks = ",".join("?" * len(SETTINGS_EXCLUDED))
            con.execute(
                "INSERT OR REPLACE INTO main.settings(key,value) "
                "SELECT key,value FROM src.settings WHERE key NOT IN (%s)" % marks,
                SETTINGS_EXCLUDED)
            copied["settings"] = [r[0] for r in con.execute(
                "SELECT key FROM src.settings WHERE key NOT IN (%s) ORDER BY key"
                % marks, SETTINGS_EXCLUDED)]
            for key, value in SETTINGS_FORCED.items():
                con.execute("INSERT OR REPLACE INTO main.settings(key,value) VALUES(?,?)",
                            (key, value))
        con.execute("DETACH DATABASE src")
    finally:
        con.close()
    return copied


def set_models(overrides):
    """`role=provider_id:model` overrides into the scratch `agent_models`.
    Returns what changed; refuses a role `providers.ROLES` does not know
    (`default` is the fallback every unlisted role reads)."""
    from core.db import get_setting, set_setting
    from llm import providers
    models = json.loads(get_setting("agent_models") or "{}")
    changed = {}
    for spec in overrides or ():
        role, _, rest = str(spec).partition("=")
        prov, _, model = rest.partition(":")
        if role != "default" and role not in providers.ROLES:
            changed[role] = "no such role; ignored"
            continue
        models[role] = {"provider": int(prov), "model": model}
        changed[role] = models[role]
    if changed:
        set_setting("agent_models", json.dumps(models))
    return changed


def prepare(source, chat_ids, out_db, *, models=None):
    """Export ``chat_ids`` from ``source`` (read-only), create ``out_db``
    fresh, import them, copy the rows a beat needs, apply model overrides.
    Leaves `core.db` configured on ``out_db``. Returns the recipe: the new
    chat id per source id and the tables and settings copied."""
    from core import db
    out_db = require_copy(os.path.abspath(out_db))
    source = os.path.abspath(source)
    if os.path.abspath(source) == out_db:
        raise SystemExit("source and scratch are the same file")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(out_db + suffix):
            os.remove(out_db + suffix)
    os.makedirs(os.path.dirname(out_db), exist_ok=True)
    os.environ["ENGINE_DB"] = out_db
    db.configure(out_db)
    db.init()
    # web.app is imported while the scratch database is current, so
    # whatever its import touches lands there and never in the source.
    from web.app import chat_import  # noqa: F401
    archives = export_chats(source, chat_ids)
    db.configure(out_db)
    db.init()
    mapping = {}
    for cid, archive in archives.items():
        row = chat_import({"data": archive})
        mapping[int(cid)] = int(row["id"])
    db.close_connection()
    copied = copy_rows(source, out_db)
    db.configure(out_db)
    changed = set_models(models)
    return {"out_db": out_db, "source": source, "chats": mapping,
            "copied": copied, "models": changed}


def leaks(text, out_db=None):
    """Does ``text`` contain any provider API key the scratch database
    holds? True/False only. The keys are compared inside this function and
    never returned; a report is written only when this says False."""
    from core import db
    path = out_db or db.DB
    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        keys = [r[0] for r in con.execute("SELECT api_key FROM providers")]
        for key in list(keys) + [r[0] for r in con.execute(
                "SELECT value FROM settings WHERE key IN (%s)"
                % ",".join("?" * len(SETTINGS_SECRET)), SETTINGS_SECRET)]:
            if key and len(str(key)) >= 8 and str(key) in str(text):
                return True
        return False
    finally:
        con.close()


# ---------------------------------------------------------------------------
# The beat and its readers
# ---------------------------------------------------------------------------

def _is_f1(failed):
    return bool(failed) and any(mark in str(failed) for mark in F1_MARKS)


def run_beat(cid, frame_id, text, *, retries=F1_RETRIES):
    """One real turn (`room_bench.run_beat`), retried from the failed stage
    when the failure is a reasoning-only reply, up to ``retries`` times.
    The result carries `attempts` and `f1_class` (True when the retries ran
    out); the run continues either way."""
    from core import db
    from agents.runtime import run_pipeline
    result = _run_beat_once(cid, frame_id, text)
    result["attempts"] = 1
    result["f1_class"] = False
    while _is_f1(result.get("failed")) and result["attempts"] <= retries:
        failed_key = db.q("SELECT key FROM steps WHERE turn_id=? ORDER BY ord DESC LIMIT 1",
                          (result["turn_id"],), one=True)
        from_key = failed_key["key"] if failed_key else None
        result["attempts"] += 1
        result["failed"] = None
        started = time.perf_counter()
        try:
            for event in run_pipeline(cid, result["turn_id"], from_key=from_key,
                                      frame_id=frame_id):
                if event.get("type") in ("error", "aborted"):
                    result["failed"] = str(event)[:300]
        except Exception as exc:
            result["failed"] = "%s: %s" % (type(exc).__name__, str(exc)[:300])
        result["seconds"] = round(result["seconds"] + time.perf_counter() - started, 2)
    result["f1_class"] = _is_f1(result.get("failed"))
    return result


def read_stages(turn_id):
    """`room_bench.read_stages`: every step's active variant and the engine
    warnings per step."""
    return _read_stages(turn_id)


def read_trace(turn_id, *, out_dir=None):
    """What every call of the turn was SENT and answered, in wall-clock
    order, through `persist.pipeline_trace.export_turn_debug` -- the only
    reader that reaches the Director's specialist sub-calls, which have no
    step of their own. Needs capture ON in the scratch db (`SETTINGS_FORCED`
    turns it on). Returns a digest (one row per call: role, model, step,
    seconds, sizes, ok) and, when ``out_dir`` is given, writes the full
    record to ``<out_dir>/trace_<turn_id>.json`` after the leak check."""
    from persist.pipeline_trace import export_turn_debug
    full = export_turn_debug(int(turn_id), include_content=True)
    calls = []
    for ev in full.get("timeline") or []:
        if ev.get("kind") != "call":
            continue
        sent = ev.get("sent") or {}
        payload = sent.get("payload") or {}
        calls.append({
            "seq": ev.get("seq"), "step": ev.get("step"), "role": ev.get("role"),
            "model": ev.get("model"), "seconds": round(float(ev.get("duration") or 0), 2),
            "ok": ev.get("ok"), "error": (ev.get("error") or "")[:200],
            "system_chars": len(str(sent.get("system") or "")),
            "payload_keys": sorted(payload) if isinstance(payload, dict) else None,
            "payload_chars": len(json.dumps(payload, default=str)) if payload else 0,
            "output_chars": len(json.dumps((ev.get("received") or {}).get("output"),
                                           default=str)),
        })
    path = None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        text = json.dumps(full, ensure_ascii=False, indent=1, default=str)
        if leaks(text):
            raise SystemExit("trace of turn %s would write a provider key; refusing"
                             % turn_id)
        path = os.path.join(out_dir, "trace_%s.json" % turn_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return {"calls": calls, "file": path,
            "captured": bool(calls), "capture_was_on": full.get("capture_was_on"),
            "events": len(full.get("timeline") or [])}


def scan(paths, out_db=None):
    """Every file under ``paths`` checked with `leaks`. Returns the files
    that would disclose a key -- [] is the answer a run must get before
    anything it wrote is kept or committed."""
    bad = []
    for root in paths:
        files = []
        if os.path.isdir(root):
            for dirpath, _dirs, names in os.walk(root):
                files.extend(os.path.join(dirpath, n) for n in names)
        elif os.path.exists(root):
            files.append(root)
        for path in files:
            if path.endswith((".db", ".db-wal", ".db-shm", ".sqlite")):
                continue
            try:
                with open(path, "rb") as f:
                    text = f.read().decode("utf-8", "replace")
            except OSError:
                continue
            if leaks(text, out_db):
                bad.append(path)
    return bad


def turn_id_of(cid, idx):
    from core.db import q
    row = q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (cid, idx), one=True)
    return row["id"] if row else None


def state_diff(stages):
    """The merged `state_diff` the resolve produced (the specialists are
    visible only as its channels), and the interpret's own diff when it
    wrote one. {'resolve': {...}, 'interpret': {...}}"""
    out = {}
    for key in ("director_resolve", "director_interpret", "director_establish"):
        blob = stages.get(key)
        if isinstance(blob, dict) and isinstance(blob.get("state_diff"), dict):
            out[key] = blob["state_diff"]
    return out


def scene_before_after(cid, idx):
    """The scene the turn started from (the checkpoint `agents.runtime`
    writes at `idx` before the first stage) and the one it left (the
    checkpoint at `idx + 1`, else the live scene). Returns (before, after);
    either may be None when no checkpoint was written."""
    from core.db import q, wget

    def _cp(i):
        row = q("SELECT blob FROM checkpoints WHERE chat_id=? AND turn_idx=?",
                (cid, i), one=True)
        if not row:
            return None
        blob = json.loads(row["blob"]) if isinstance(row["blob"], str) else row["blob"]
        return ((blob or {}).get("world") or {}).get("scene")

    before = _cp(idx)
    after = _cp(idx + 1)
    if after is None:
        after = wget(cid, "scene") or None
    return before, after


def registry_rows(cid):
    from core.db import q
    return [dict(r) for r in q(
        "SELECT room_uid,name,retired_turn_id,payload FROM room_registry WHERE chat_id=?",
        (cid,))]


def regions_of(cid):
    from core.db import wget
    return wget(cid, "regions") or {}


def scene_digest(scene):
    """Rooms, edges, geometry, sources, bodies: the fields a geometry run
    reads, in one screen."""
    scene = scene or {}
    rooms = {}
    for rid, r in (scene.get("rooms") or {}).items():
        if not isinstance(r, dict):
            continue
        rooms[rid] = {k: r.get(k) for k in (
            "name", "light", "size", "extent", "shape", "parts", "region",
            "exposure", "footprint", "height", "opacity", "planned") if k in r}
        rooms[rid]["anchors"] = {a: {k: v for k, v in (spec or {}).items()
                                     if k in ("dir", "offset", "cell", "footprint",
                                              "height", "opacity")}
                                 for a, spec in (r.get("anchors") or {}).items()
                                 if isinstance(spec, dict)}
        rooms[rid]["adjacent"] = [
            {k: e.get(k) for k in ("to", "barrier", "dir", "bearing", "axis",
                                   "offset", "width", "material", "sight_from")
             if k in e}
            for e in (r.get("adjacent") or []) if isinstance(e, dict)]
    ents = {}
    for eid, e in (scene.get("entities") or {}).items():
        if not isinstance(e, dict):
            continue
        keep = {k: e.get(k) for k in (
            "kind", "room", "light_source", "light_height", "cone", "facing",
            "aim", "sound_source", "steadiness", "portable", "mood") if k in e}
        if isinstance(e.get("state"), dict):
            keep["state"] = {k: v for k, v in e["state"].items()
                             if k in ("lit", "running", "on", "failing", "burning")}
        ents[eid] = keep
    return {"rooms": rooms, "entities": ents, "positions": scene.get("positions"),
            "stations": scene.get("stations"), "day_phase": scene.get("day_phase"),
            "time_of_day": scene.get("time_of_day"), "orientation": scene.get("orientation")}


def stage_digest(stages, warnings):
    """What a reader wants of each stage before deciding which to open in
    full: the interpret's flow and movement, the establish's rooms, the
    merged diff, every view's text, the narrator's prose, and every
    warning, cut per stage."""
    keep = {}
    for key, blob in stages.items():
        if not isinstance(blob, dict):
            keep[key] = str(blob)[:2000]
            continue
        if key == "director_interpret":
            keep[key] = {k: blob.get(k) for k in (
                "flow", "speech", "movement", "location_query", "state_diff",
                "author_notes", "_engine_notes") if k in blob}
        elif key == "director_establish":
            keep[key] = {k: blob.get(k) for k in (
                "location", "time", "rooms", "positions", "stations", "entities",
                "state_diff", "_engine_notes") if k in blob}
        elif key == "director_resolve":
            keep[key] = {k: blob.get(k) for k in (
                "state_diff", "events", "event_order", "world_pressure",
                "_engine_notes") if k in blob}
        elif key in ("perception_act", "perception_outcome", "perception_establish"):
            keep[key] = blob
        elif key == "narrator":
            keep[key] = (blob.get("text") or blob.get("prose") or blob.get("narration")
                         or json.dumps(blob, ensure_ascii=False))[:4000]
        else:
            keep[key] = json.dumps(blob, ensure_ascii=False)[:4000]
    return {"stages": keep, "warnings": warnings}


# ---------------------------------------------------------------------------
# The Writers' Room and the World Browser, from the same process
# ---------------------------------------------------------------------------

def tool(cid, name, args=None, *, frame_id=None):
    """`story.room_tools.run_tool` as the host. An error is returned, not
    raised, so a run keeps going."""
    from story.room_tools import run_tool
    try:
        return run_tool(cid, name, args or {}, frame_id=frame_id, host=True)
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, str(exc)[:400])}


def room(cid, frame_id, text, *, retries=F1_RETRIES):
    """The Writers' Room's reply to the player's line, with every tool call
    the Planner made and every model call captured; retried on a
    reasoning-only reply per the F1 rule."""
    from agents import story_planner as sp
    from tools.turn_bench import _CallCapture
    events = []
    out, attempts = None, 0
    started = time.perf_counter()
    cap = _CallCapture()
    with cap:
        while attempts <= retries:
            attempts += 1
            try:
                out = sp.run_planner(cid, frame_id, text=text, on_event=events.append)
                break
            except Exception as exc:
                out = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:600])}
                if not _is_f1(out["error"]):
                    break
    calls = [{"tool": e.get("tool") or e.get("name"), "args": e.get("args"),
              "result_head": str(e.get("result"))[:300]}
             for e in events if isinstance(e, dict) and (e.get("tool") or e.get("name"))]
    return {"seconds": round(time.perf_counter() - started, 1), "out": out,
            "attempts": attempts, "f1_class": _is_f1((out or {}).get("error")),
            "tool_calls": calls, "llm": cap.calls}


def browser(action, cid, *args, frame_id=None, body=None):
    """The World Browser's writers, called as the route functions the UI
    calls (`web/world_routes.py`), so the same allowlists and the same
    `_write_scene` path run. ``action`` is one of `room`, `entity`,
    `region`, `station`, `slice`, `grid`, `map`. A refusal (HTTPException)
    is returned as {'refused': status, 'detail': ...}."""
    from fastapi import HTTPException
    from web import world_routes as wr
    try:
        if action == "room":
            return wr.room_patch(cid, args[0], body or {}, frame_id=frame_id)
        if action == "entity":
            return wr.room_entity_patch(cid, args[0], args[1], body or {}, frame_id=frame_id)
        if action == "region":
            return wr.region_patch(cid, args[0], body or {}, frame_id=frame_id)
        if action == "station":
            return wr.body_station_put(cid, args[0], body or {}, frame_id=frame_id)
        if action == "slice":
            return wr.rooms_slice(cid, args[0], frame_id=frame_id)
        if action == "grid":
            return wr.rooms_grid(cid, args[0], frame_id=frame_id)
        if action == "map":
            return wr.map_index(cid, frame_id=frame_id)
        if action == "index":
            return wr.rooms_index(cid, frame_id=frame_id)
    except HTTPException as exc:
        return {"refused": exc.status_code, "detail": exc.detail}
    raise ValueError("no browser action %r" % action)


# ---------------------------------------------------------------------------
# A resumable run
# ---------------------------------------------------------------------------

class Run:
    """Phases written to ``report.json`` as they finish; a phase already in
    the file is skipped on the next run, so a crashed run resumes where it
    stopped (the scratch database carries the committed turns)."""

    def __init__(self, out_dir):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.path = os.path.join(out_dir, "report.json")
        self.report = {"phases": []}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                self.report = json.load(f)
        self.done = {p["phase"] for p in self.report["phases"]}

    def phase(self, name, make):
        if name in self.done:
            print("== skip", name, flush=True)
            return next(p for p in self.report["phases"] if p["phase"] == name)
        started = time.perf_counter()
        out = make()
        out = out if isinstance(out, dict) else {"value": out}
        out["phase"] = name
        out["seconds"] = round(time.perf_counter() - started, 1)
        text = json.dumps(out, ensure_ascii=False, default=str)
        if leaks(text):
            raise SystemExit("phase %s would write a provider key; refusing" % name)
        self.report["phases"].append(out)
        self.done.add(name)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.report, f, ensure_ascii=False, indent=1, default=str)
        print("== phase", name, "%.1fs" % out["seconds"], flush=True)
        return out

    def beat(self, cid, frame_id, text, *, label=None):
        """One beat, then every stage read, the scene before and after, the
        registry and the regions: the whole reading a suspect beat needs."""
        from core.db import q
        from tools.turn_bench import _CallCapture
        cap = _CallCapture()
        with cap:
            result = run_beat(cid, frame_id, text)
        stages, warnings = read_stages(result["turn_id"])
        before, after = scene_before_after(cid, result["idx"])
        try:
            trace = read_trace(result["turn_id"], out_dir=self.out_dir)
        except Exception as exc:
            trace = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])}
        return {"beat": result, "label": label, "trace": trace,
                "digest": stage_digest(stages, warnings),
                "state_diff": state_diff(stages),
                "scene_before": scene_digest(before), "scene_after": scene_digest(after),
                "registry": registry_rows(cid), "regions": regions_of(cid),
                "llm": cap.calls,
                "turns": q("SELECT count(*) n FROM turns WHERE chat_id=?", (cid,), one=True)["n"]}


def frame_of(cid):
    from core.db import q
    row = q("SELECT frame_id FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
            (cid,), one=True)
    return row["frame_id"] if row else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare", help="export chats read-only, import into a fresh scratch db")
    p.add_argument("--src", default="engine.db")
    p.add_argument("--chats", type=int, nargs="+", required=True)
    p.add_argument("--out", required=True, help="the scratch db (under a scratch dir)")
    p.add_argument("--model", action="append", default=[],
                   help="role=provider_id:model, repeatable")
    b = sub.add_parser("beat", help="one real turn on the scratch db")
    b.add_argument("--db", required=True)
    b.add_argument("--chat", type=int, required=True)
    b.add_argument("--text", required=True)
    b.add_argument("--frame", type=int, default=None)
    s = sub.add_parser("stages", help="every stage of a turn, the diff, the scene before/after")
    s.add_argument("--db", required=True)
    s.add_argument("--chat", type=int, required=True)
    s.add_argument("--turn", type=int, required=True)
    t = sub.add_parser("trace", help="what every call of a turn was sent (capture must be on)")
    t.add_argument("--db", required=True)
    t.add_argument("--chat", type=int, required=True)
    t.add_argument("--turn", type=int, required=True)
    t.add_argument("--out", default=None, help="write the full record here")
    sc = sub.add_parser("scan", help="refuse any file that carries a provider key")
    sc.add_argument("--db", required=True)
    sc.add_argument("paths", nargs="+")
    args = ap.parse_args(argv)

    if args.cmd == "prepare":
        recipe = prepare(args.src, args.chats, args.out, models=args.model)
        text = json.dumps(recipe, indent=1)
        assert not leaks(text, recipe["out_db"])
        print(text)
        return 0
    from core import db
    db.configure(require_copy(args.db))
    if args.cmd == "beat":
        frame = args.frame if args.frame is not None else frame_of(args.chat)
        result = run_beat(args.chat, frame, args.text)
        print(json.dumps(result, indent=1, default=str))
        return 0
    if args.cmd == "trace":
        tid = turn_id_of(args.chat, args.turn)
        if tid is None:
            raise SystemExit("no turn %s in chat %s" % (args.turn, args.chat))
        print(json.dumps(read_trace(tid, out_dir=args.out), indent=1, default=str))
        return 0
    if args.cmd == "scan":
        bad = scan(args.paths)
        print("\n".join(bad) if bad else "clean: no provider key in %d path(s)"
              % len(args.paths))
        return 1 if bad else 0
    if args.cmd == "stages":
        tid = turn_id_of(args.chat, args.turn)
        if tid is None:
            raise SystemExit("no turn %s in chat %s" % (args.turn, args.chat))
        stages, warnings = read_stages(tid)
        before, after = scene_before_after(args.chat, args.turn)
        out = {"digest": stage_digest(stages, warnings), "state_diff": state_diff(stages),
               "scene_before": scene_digest(before), "scene_after": scene_digest(after)}
        text = json.dumps(out, indent=1, ensure_ascii=False, default=str)
        assert not leaks(text)
        print(text)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
