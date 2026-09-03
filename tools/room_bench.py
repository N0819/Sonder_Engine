#!/usr/bin/env python3
"""The Writers' Room's quality harness: publish, then play the next beat.

A package is good if the world takes it. Reading a transcript says the
Planner published three rooms and two neighbours; it does not say whether
the Director rendered the neighbour when the player opened the door, whether
the identity floor bound the mint to the plan, whether the room settled the
render, or whether the narration read as though the cobbler had always been
there. Those are the Phase A measures, applied downstream, and they need a
turn -- so this drives the real thing: `agents.story_planner.run_planner`
for the reply, then `agents.runtime.run_pipeline` for ONE beat that walks the
player into a room the package planned, then every stage's active variant
read against the others.

Two layers, run together or apart:

* THE BEAT HARNESS (`--grant`, `--walk`): the Planner reply with every tool
  call captured, the published packages, the beat, the stages, the measures.
* THE CRITIC (`--critic`): a `utility`-role model scores the package(s)
  1-5 on five axes with one sentence each and lists contradictions, beside
  deterministic checks that need no model. EVALUATION ONLY: nothing here is
  in the Planner's loop, and nothing it says reaches the story.

ALWAYS ON A COPY. The source database is copied with the sqlite backup API
over a read-only connection into a fresh scratch directory, `ENGINE_DB` is
pointed at the copy before the engine is imported, and `require_copy`
refuses to run against any path the harness did not create or that is not
under a scratch directory -- a turn commits for real, and the Planner writes
mandates, packages and thread lines.

    python3 tools/room_bench.py --db engine.db --chat 12 \\
        --grant "You may plan rooms and people ahead of me ..." \\
        --planner 3:google/gemini-3.7-flash --critic --out /tmp/room-bench

Model overrides are `provider_id:model` and are written into the COPY's
`agent_models` setting only. `--no-turn` stops after the reply; `--walk`
names the player's line for the beat (else one is derived from the first
planned room adjacent to the player). Never run this against an explicit
scenario on a provider that refuses such content.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: The directory prefix the harness creates; `require_copy` accepts a path
#: under it, under the tempdir, or under a `jobs` scratch tree, and nothing
#: else.
SCRATCH_PREFIX = "room-bench-"

#: The stage keys read for the beat, in plan order. A `character:<id>` step
#: is read for every id the turn ran.
STAGE_KEYS = ("director_interpret", "compile_world_context", "perception_act",
              "reaction_loop", "interaction_loop", "director_resolve",
              "background_react", "perception_outcome", "narrator", "commit")

#: The critic's five axes, scored 1-5 each with one sentence.
CRITIC_AXES = ("naturalness", "consistency", "agreement", "specificity", "setup")
#: Tokens the critic may answer with.
CRITIC_MAX_TOKENS = 1500
#: Characters of narration and of the package text shown to the critic.
CRITIC_TEXT_CHARS = 6000
#: Lore hits shown to the critic (the Planner's own reads, deduplicated).
CRITIC_LORE_HITS = 12

#: The one prompt this harness owns. Not a language-pack card: it is read by
#: an evaluator, never by a story, and its verdict reaches nothing but the
#: report.
CRITIC_SYSTEM = (
    "You judge what a Writers' Room prepared for an interactive story. You are "
    "given the player's grant in their own words, the lore the room read, the "
    "package(s) it published (rooms, people, things, events, lore), the room's "
    "reply to the player, and the narration of the next beat, in which the "
    "player walked into what was prepared. Score each axis from 1 (fails) to 5 "
    "(exemplary) with ONE sentence of reason that names the particular you "
    "judged by: naturalness (reads as something that happened in the world, "
    "not arranged for the player); consistency (agrees with the lore and the "
    "map it was given; nothing contradicts them); agreement (does what the "
    "player's words allowed and asked, no more, no less); specificity "
    "(particulars -- names, trades, objects, habits -- not gists); setup "
    "(something planted that can pay off later, not only furniture). Then list "
    "every contradiction you found between the package, the lore, the reply "
    "and the narration, each as one sentence naming both sides. Judge what is "
    "there; do not propose. Reply with one JSON object and nothing else: "
    '{"scores": {"naturalness": {"score": n, "reason": "..."}, "consistency": '
    '{...}, "agreement": {...}, "specificity": {...}, "setup": {...}}, '
    '"contradictions": ["..."]}')


# ---------------------------------------------------------------------------
# The copy
# ---------------------------------------------------------------------------

def prepare_copy(source):
    """Copy ``source`` into a fresh scratch directory over a read-only
    connection and point `ENGINE_DB` at the copy. Returns (workdir, copy)."""
    source = os.path.abspath(source)
    if not os.path.exists(source):
        raise SystemExit("no database at %s" % source)
    workdir = tempfile.mkdtemp(prefix=SCRATCH_PREFIX)
    copy = os.path.join(workdir, "bench.db")
    src = sqlite3.connect("file:%s?mode=ro" % source, uri=True)
    dst = sqlite3.connect(copy)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    os.environ["ENGINE_DB"] = copy
    return workdir, copy


def require_copy(path):
    """Refuse a database the harness did not make. A path is a copy when it
    sits under a `room-bench-` directory, under the tempdir, or under a
    `jobs` scratch tree; the owner's `engine.db` is none of these."""
    resolved = os.path.abspath(str(path or ""))
    parts = resolved.split(os.sep)
    tmp = os.path.abspath(tempfile.gettempdir())
    ok = (any(p.startswith(SCRATCH_PREFIX) for p in parts)
          or resolved.startswith(tmp + os.sep)
          or "jobs" in parts)
    if not ok or os.path.basename(resolved) == "engine.db":
        raise SystemExit("Refusing to run against %s: the harness runs only on a "
                         "copy it made (or a path under a scratch directory)." % resolved)
    return resolved


def set_model_overrides(planner=None, dramaturge=None):
    """Write `provider_id:model` overrides into the COPY's agent_models."""
    from core.db import get_setting, set_setting
    from llm import providers
    models = json.loads(get_setting("agent_models") or "{}")
    changed = {}
    for role, spec in (("story_planner", planner), ("dramaturge", dramaturge)):
        if not spec:
            continue
        if role not in providers.ROLES:
            changed[role] = "no such role; override ignored"
            continue
        prov, model = str(spec).split(":", 1)
        models[role] = {"provider": int(prov), "model": model}
        changed[role] = models[role]
    if changed:
        set_setting("agent_models", json.dumps(models))
    return changed


# ---------------------------------------------------------------------------
# The reply, with every tool call captured
# ---------------------------------------------------------------------------

def run_planner_with_capture(cid, frame_id, text):
    """`run_planner` with the tool calls it made recorded: name, args, a
    bounded result, seconds. The Planner imports `run_tool` at call time, so
    the module attribute is the seam."""
    from agents import story_planner as sp
    from story import room_tools

    calls = []
    real = room_tools.run_tool

    def recording(cid_, name, args=None, **kw):
        started = time.perf_counter()
        try:
            result = real(cid_, name, args, **kw)
        except Exception as exc:
            result = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])}
            calls.append({"tool": name, "args": args, "result": result,
                          "seconds": round(time.perf_counter() - started, 3)})
            raise
        calls.append({"tool": name, "args": args,
                      "result": json.loads(json.dumps(result, default=str))
                      if isinstance(result, (dict, list)) else result,
                      "seconds": round(time.perf_counter() - started, 3)})
        return result

    room_tools.run_tool = recording
    started = time.perf_counter()
    try:
        out = sp.run_planner(cid, frame_id, text=text)
    finally:
        room_tools.run_tool = real
    lore_hits = []
    seen = set()
    for call in calls:
        if call["tool"] in ("search_lore", "read_lore", "scan_lore"):
            result = call["result"] if isinstance(call["result"], dict) else {}
            rows = result.get("hits") or result.get("entries") or (
                [result] if result.get("citation") else [])
            for row in rows:
                cit = row.get("citation")
                if cit and cit not in seen:
                    seen.add(cit)
                    lore_hits.append({"citation": cit, "title": row.get("title"),
                                      "excerpt": row.get("excerpt") or
                                      str(row.get("content") or "")[:280]})
    return {"reply": out, "calls": calls, "lore_hits": lore_hits,
            "seconds": round(time.perf_counter() - started, 2)}


# ---------------------------------------------------------------------------
# What was published, and where to walk
# ---------------------------------------------------------------------------

def published_packages(cid, frame_id, uids=None):
    from story.plot_packages import packages
    stored = packages(cid, frame_id)
    rows = [p for p in stored.values()
            if p.get("status") in ("published", "active", "resolved")]
    if uids:
        rows = [p for p in rows if p["uid"] in set(uids)]
    return rows


def package_plan(pkgs):
    """The rooms (id -> {name, adjacent}) and the people/things planned by
    the packages, read from their operations."""
    rooms, people = {}, []
    for pkg in pkgs:
        for op in pkg.get("operations") or ():
            if op.get("op") == "plan_rooms":
                for rid, room in (op.get("rooms") or {}).items():
                    rooms[str(rid)] = {"name": room.get("name") or rid,
                                       "adjacent": [str(e.get("to")) for e in
                                                    (room.get("adjacent") or ())
                                                    if isinstance(e, dict)]}
            elif op.get("op") == "plan_entity":
                people.append({"name": op.get("name"), "kind": op.get("kind"),
                               "aliases": list(op.get("aliases") or ()),
                               "where": (op.get("brief") or {}).get("where")})
    return rooms, people


def player_name(cid):
    from core.db import q
    from story.character_schema import persona_name
    from story.scene import persona_of
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    pers = persona_of(dict(chat) if chat else {})
    return pers.get("name") or persona_name(pers)


def derive_walk(cid, frame_id, pkgs):
    """The player's line for the beat: into the first planned room that is
    adjacent to the player's room (either direction), else the first
    planned room at all. Returns (room_id, text) or (None, None)."""
    from core.db import wget_for_frame
    scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
    who = player_name(cid)
    here = str((scene.get("positions") or {}).get(who) or "")
    here_adjacent = {str(e.get("to")) for e in
                     ((scene.get("rooms") or {}).get(here) or {}).get("adjacent") or ()
                     if isinstance(e, dict)}
    rooms, _people = package_plan(pkgs)
    ordered = sorted(rooms.items(), key=lambda kv: (
        0 if (here in kv[1]["adjacent"] or kv[0] in here_adjacent) else 1, kv[0]))
    if not ordered:
        return None, None
    rid, room = ordered[0]
    return rid, "You step through into the %s, looking about you." % room["name"]


def walk_is_adjacent(cid, frame_id, rid):
    """Does an edge join the player's room and ``rid`` in the scene or the
    plan? A walk into a room no edge reaches measures the Director's answer
    to a teleport, which is a different measurement (chat 114, 2026-09-03:
    the hand invented the edge)."""
    from core.db import wget_for_frame
    from world.structure import planned_room_ids
    if not rid:
        return None
    scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
    here = str((scene.get("positions") or {}).get(player_name(cid)) or "")
    edges = {str(e.get("to")) for e in
             ((scene.get("rooms") or {}).get(here) or {}).get("adjacent") or ()
             if isinstance(e, dict)}
    if rid in edges:
        return True
    try:
        from core.db import q
        for row in q("SELECT room_uid,payload FROM room_registry WHERE chat_id=? "
                     "AND retired_turn_id IS NULL", (cid,)):
            spec = (json.loads(row["payload"] or "{}") or {}).get("planned") or {}
            tos = {str(e.get("to")) for e in spec.get("adjacent") or () if isinstance(e, dict)}
            if (row["room_uid"] == rid and here in tos) or (row["room_uid"] == here and rid in tos):
                return True
    except Exception:
        pass
    return False


def duplicate_room_names(cid):
    """Live registry rooms sharing a name: the mark of a plan's room minted
    again beside itself. [] is the healthy answer."""
    from core.db import q
    from world.spatial import normalize_room_id
    by_name = {}
    for row in q("SELECT room_uid,name FROM room_registry WHERE chat_id=? "
                 "AND retired_turn_id IS NULL", (cid,)):
        by_name.setdefault(normalize_room_id(str(row["name"] or "")), []).append(row["room_uid"])
    return [{"name": k, "rooms": v} for k, v in sorted(by_name.items()) if k and len(v) > 1]


# ---------------------------------------------------------------------------
# The beat
# ---------------------------------------------------------------------------

def run_beat(cid, frame_id, text):
    """One real turn through `run_pipeline`, timed per stage."""
    from core import db
    from agents.runtime import run_pipeline
    with db.transaction():
        last = db.q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
                    (cid,), one=True)
        idx = (last["idx"] + 1) if last else 0
        tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                    "VALUES(?,?,?,?,?)", (cid, idx, text, time.time(), frame_id))
    stages, failed = {}, None
    last_at = start = time.perf_counter()
    try:
        for event in run_pipeline(cid, tid, frame_id=frame_id):
            kind = event.get("type")
            if kind == "step":
                now = time.perf_counter()
                key = event.get("key") or "?"
                stages[key] = round(stages.get(key, 0.0) + (now - last_at), 2)
                last_at = now
            elif kind in ("error", "aborted"):
                failed = str(event)[:300]
    except Exception as exc:
        failed = "%s: %s" % (type(exc).__name__, str(exc)[:300])
    return {"turn_id": tid, "idx": idx, "input": text, "stages": stages,
            "failed": failed, "seconds": round(time.perf_counter() - start, 2)}


def read_stages(turn_id):
    """Every step's active variant for the turn, keyed by step key, plus the
    engine notes' warnings per step."""
    from core.db import q
    out, warnings = {}, {}
    for step in q("SELECT id,key FROM steps WHERE turn_id=? ORDER BY ord", (turn_id,)):
        row = q("SELECT content FROM variants WHERE step_id=? AND active=1",
                (step["id"],), one=True)
        if not row:
            continue
        try:
            blob = json.loads(row["content"])
        except (TypeError, ValueError):
            blob = {"text": row["content"]}
        out[step["key"]] = blob
        notes = blob.get("_engine_notes") if isinstance(blob, dict) else None
        if isinstance(notes, dict) and notes.get("warnings"):
            warnings[step["key"]] = [str(w) for w in notes["warnings"]]
    return out, warnings


def _mentions(text, names):
    text = str(text or "").casefold()
    return [n for n in names if n and n.casefold() in text]


def measure(cid, frame_id, *, before_plans, before_needs, stages, warnings, pkgs):
    """The Phase A measures for the beat, from the stages read against the
    ledgers before and after."""
    from world.planned_entities import planned_entities
    from world.planning_needs import planning_needs
    rooms, people = package_plan(pkgs)
    names = [p["name"] for p in people if p.get("name")]
    for p in people:
        names.extend(a for a in p.get("aliases") or () if a)

    resolve = stages.get("director_resolve") or {}
    diff = resolve.get("state_diff") if isinstance(resolve, dict) else {}
    diff = diff if isinstance(diff, dict) else {}
    entities = diff.get("entities") if isinstance(diff.get("entities"), dict) else {}
    rendered, bound = [], []
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        label = " ".join(str(x) for x in (eid, ent.get("name"),
                                          *(ent.get("aliases") or ())))
        hit = _mentions(label, names)
        if hit:
            rendered.append({"entity": eid, "name": ent.get("name"), "plans": hit})
        if ent.get("plan_ref"):
            bound.append({"entity": eid, "plan_ref": ent["plan_ref"]})

    after_plans = planned_entities(cid, frame_id)
    settled = [uid for uid, p in after_plans.items()
               if p.get("rendered") and not (before_plans.get(uid) or {}).get("rendered")]
    after_needs = planning_needs(cid, frame_id)
    needs_filed = [n for n in after_needs
                   if n["uid"] not in {m["uid"] for m in before_needs}]

    compiled = stages.get("compile_world_context") or {}
    movement = compiled.get("movement") if isinstance(compiled, dict) else None
    narrator = stages.get("narrator") or {}
    prose = ""
    if isinstance(narrator, dict):
        prose = str(narrator.get("prose") or narrator.get("text") or "")
    positions = diff.get("positions") if isinstance(diff.get("positions"), dict) else {}
    who = player_name(cid)
    return {
        "movement": movement,
        "player_moved_to": positions.get(who),
        "planned_rooms": sorted(rooms),
        "planned_people": names,
        "rendered_planned_figures": rendered,
        "floor_bound": bound,
        "settled_plans": settled,
        "planning_needs_filed": [{"uid": n["uid"], "kind": n["kind"],
                                  "subject": n["subject"], "reason": n["reason"]}
                                 for n in needs_filed],
        "narrator_mentions": _mentions(prose, names),
        "narration": prose[:CRITIC_TEXT_CHARS],
        "warnings": warnings,
        "duplicate_rooms": duplicate_room_names(cid),
        "warning_count": sum(len(v) for v in warnings.values()),
        "character_steps": sorted(k for k in stages if k.startswith("character:")),
        "stages_present": [k for k in STAGE_KEYS if k in stages],
    }


# ---------------------------------------------------------------------------
# The critic
# ---------------------------------------------------------------------------

def deterministic_checks(cid, frame_id, pkgs, *, reply, published):
    """What needs no model: reserved-name collisions, rooms exiting to
    nowhere, operations outside the standing mandates, and reply claims the
    transcript does not support."""
    from core.db import q, wget_for_frame
    from story import mandates
    from story.plot_packages import package_requirements
    from world.structure import planned_room_ids
    findings = []
    rooms, people = package_plan(pkgs)

    taken = {str(r["name"]).casefold() for r in q(
        "SELECT c.name FROM chat_chars cc JOIN characters c ON c.id=cc.char_id "
        "WHERE cc.chat_id=?", (cid,))}
    try:
        from world.charter_runtime import registry_for
        for item in (registry_for(cid, frame_id).get("items") or {}).values():
            for body in ((item.get("state") or {}).get("bodies") or {}).values():
                if body.get("name"):
                    taken.add(str(body["name"]).casefold())
    except Exception:
        pass
    for p in people:
        for name in [p.get("name")] + list(p.get("aliases") or ()):
            if name and str(name).casefold() in taken:
                findings.append({"check": "reserved_name",
                                 "detail": "plan %r reuses a held identity" % name})

    scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
    known = set(rooms) | {str(r) for r in (scene.get("rooms") or {})} | set(
        str(r) for r in planned_room_ids(cid))
    for rid, room in rooms.items():
        for to in room["adjacent"]:
            if to not in known:
                findings.append({"check": "exit_to_nowhere",
                                 "detail": "room %r exits to %r, which exists nowhere"
                                 % (rid, to)})

    for pkg in pkgs:
        needed = package_requirements(pkg)
        cov = mandates.coverage(cid, frame_id, needed)
        if not cov["ok"]:
            findings.append({"check": "outside_mandate", "package": pkg["uid"],
                             "detail": "no standing mandate covers %s"
                             % ", ".join(cov["missing"])})

    text = str(reply or "")
    claimed = _mentions(text, [r["name"] for r in rooms.values()] +
                        [p["name"] for p in people if p.get("name")])
    if claimed and not published:
        findings.append({"check": "reply_claims_unlanded",
                         "detail": "the reply names %s and nothing was published"
                         % ", ".join(claimed)})
    return findings


def critique(*, pkgs, grant, lore_hits, narration, reply, transcript):
    """The model-judged rubric. EVALUATION ONLY. Returns the parsed verdict
    or `{"error": ...}`; never raises into the harness."""
    from agents.common import jparse
    from llm import providers
    shown = []
    for pkg in pkgs:
        shown.append({"title": pkg.get("title"), "premise": pkg.get("premise"),
                      "truths": pkg.get("truths"), "questions": pkg.get("questions"),
                      "operations": pkg.get("operations")})
    packages_text = json.dumps(shown, ensure_ascii=False, default=str)
    if len(packages_text) > CRITIC_TEXT_CHARS * 2:
        packages_text = packages_text[:CRITIC_TEXT_CHARS * 2] + " …(truncated)"
    payload = {
        "grant": grant,
        "lore_read": lore_hits[:CRITIC_LORE_HITS],
        "packages": packages_text,
        "reply_to_player": str(reply or "")[:CRITIC_TEXT_CHARS],
        "narration_of_next_beat": str(narration or "")[:CRITIC_TEXT_CHARS],
        "tool_calls": [{"tool": c["tool"], "ok": "error" not in (c.get("result") or {})
                        if isinstance(c.get("result"), dict) else True}
                       for c in transcript][:60],
    }
    try:
        raw = providers.chat_complete("utility", CRITIC_SYSTEM,
                                      json.dumps(payload, ensure_ascii=False),
                                      json_mode=True, max_tokens=CRITIC_MAX_TOKENS)
    except Exception as exc:
        return {"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])}
    out = jparse(raw)
    if not isinstance(out, dict) or not isinstance(out.get("scores"), dict):
        return {"error": "the critic did not answer in the rubric's shape",
                "raw": str(raw)[:600]}
    scores = {}
    for axis in CRITIC_AXES:
        row = out["scores"].get(axis) if isinstance(out["scores"].get(axis), dict) else {}
        try:
            score = int(row.get("score"))
        except (TypeError, ValueError):
            score = None
        scores[axis] = {"score": score if score is None else max(1, min(5, score)),
                        "reason": str(row.get("reason") or "")[:400]}
    return {"scores": scores,
            "contradictions": [str(c)[:400] for c in (out.get("contradictions") or [])
                               if str(c or "").strip()][:20]}


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def render_report(summary):
    lines = ["# Writers' Room bench", ""]
    lines.append("- chat %s, frame %s, copy `%s`" % (
        summary.get("chat"), summary.get("frame_id"), summary.get("copy")))
    if summary.get("models"):
        lines.append("- model overrides: `%s`" % json.dumps(summary["models"]))
    lines.append("- grant: %s" % summary.get("grant"))
    reply = summary.get("planner") or {}
    lines += ["", "## The reply", "",
              "- %ss, %s steps, %s tool calls, stopped: %s, published: %s" % (
                  reply.get("seconds"), (reply.get("out") or {}).get("steps"),
                  (reply.get("out") or {}).get("calls"),
                  (reply.get("out") or {}).get("stopped"),
                  ", ".join((reply.get("out") or {}).get("published") or []) or "nothing"),
              "", "> " + str((reply.get("out") or {}).get("reply") or "").replace("\n", "\n> ")]
    if reply.get("calls"):
        lines += ["", "| tool | seconds | result |", "|---|---|---|"]
        for c in reply["calls"]:
            result = c.get("result")
            head = (json.dumps(result, ensure_ascii=False, default=str)
                    if not isinstance(result, str) else result)[:120]
            lines.append("| %s | %s | %s |" % (c["tool"], c["seconds"],
                                              head.replace("|", "\\|")))
    beat = summary.get("beat")
    if beat:
        lines += ["", "## The beat", "", "- input: %s" % beat.get("input"),
                  "- %ss total; failed: %s" % (beat.get("seconds"), beat.get("failed"))]
        for key, secs in sorted((beat.get("stages") or {}).items(), key=lambda kv: -kv[1]):
            lines.append("  - %s: %ss" % (key, secs))
    m = summary.get("measures")
    if m:
        lines += ["", "## Measures", "",
                  "- movement: `%s`; player moved to: %s" % (json.dumps(m.get("movement")),
                                                           m.get("player_moved_to")),
                  "- planned rooms: %s" % ", ".join(m.get("planned_rooms") or []),
                  "- planned people: %s" % ", ".join(m.get("planned_people") or []),
                  "- rendered planned figures: %s" % json.dumps(m.get("rendered_planned_figures")),
                  "- floor bound (plan_ref): %s" % json.dumps(m.get("floor_bound")),
                  "- settled plans: %s" % ", ".join(m.get("settled_plans") or []) or "none",
                  "- planning needs filed: %s" % json.dumps(m.get("planning_needs_filed")),
                  "- narrator mentions: %s" % ", ".join(m.get("narrator_mentions") or []),
                  "- warnings: %s" % m.get("warning_count"),
                  "- character steps: %s" % ", ".join(m.get("character_steps") or [])]
        for key, ws in (m.get("warnings") or {}).items():
            for w in ws:
                lines.append("  - [%s] %s" % (key, w))
        lines += ["", "### Narration", "", "> " + str(m.get("narration") or "").replace("\n", "\n> ")]
    if summary.get("roles"):
        lines += ["", "## Model time by role", "", "| role | model | calls | seconds |",
                  "|---|---|---|---|"]
        for row in summary["roles"]:
            lines.append("| %s | %s | %s | %s |" % (row["role"], row["model"],
                                                   row["calls"], row["seconds"]))
    checks = summary.get("checks")
    if checks is not None:
        lines += ["", "## Deterministic checks", ""]
        lines += ["- %s: %s" % (f["check"], f["detail"]) for f in checks] or ["- none"]
    crit = summary.get("critic")
    if crit:
        lines += ["", "## Critic", ""]
        if crit.get("error"):
            lines.append("- error: %s" % crit["error"])
        else:
            for axis in CRITIC_AXES:
                row = crit["scores"].get(axis) or {}
                lines.append("- %s: **%s** -- %s" % (axis, row.get("score"), row.get("reason")))
            lines += ["", "contradictions:"]
            lines += ["- " + c for c in crit.get("contradictions") or []] or ["- none"]
    return "\n".join(lines) + "\n"


def write_report(out_dir, summary):
    os.makedirs(out_dir, exist_ok=True)
    md = os.path.join(out_dir, "report.md")
    js = os.path.join(out_dir, "summary.json")
    with open(md, "w", encoding="utf-8") as f:
        f.write(render_report(summary))
    with open(js, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    return md, js


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def run(cid, *, grant, walk=None, planner=None, dramaturge=None, critic=False,
        no_turn=False):
    from core import db
    from world.planned_entities import planned_entities
    from world.planning_needs import planning_needs
    from tools.turn_bench import _CallCapture

    require_copy(db.DB)
    summary = {"chat": cid, "copy": db.DB, "grant": grant,
               "models": set_model_overrides(planner, dramaturge)}
    last = db.q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
                (cid,), one=True)
    if last is None:
        raise SystemExit("chat %s has no turns; the harness needs a played story" % cid)
    frame_id = last["frame_id"]
    summary["frame_id"] = frame_id

    before_plans = planned_entities(cid, frame_id)
    before_needs = planning_needs(cid, frame_id)
    before_uids = {p["uid"] for p in published_packages(cid, frame_id)}

    capture = _CallCapture()
    with capture:
        planner_run = run_planner_with_capture(cid, frame_id, grant)
        summary["planner"] = {"seconds": planner_run["seconds"],
                              "out": planner_run["reply"],
                              "calls": planner_run["calls"],
                              "lore_hits": planner_run["lore_hits"]}
        pkgs = [p for p in published_packages(cid, frame_id) if p["uid"] not in before_uids]
        summary["published"] = [{"uid": p["uid"], "title": p["title"],
                                 "operations": [op["op"] for op in p["operations"]]}
                                for p in pkgs]
        summary["checks"] = deterministic_checks(
            cid, frame_id, pkgs, reply=planner_run["reply"].get("reply"),
            published=planner_run["reply"].get("published"))
        if not no_turn and pkgs:
            room_id, text = (None, walk) if walk else derive_walk(cid, frame_id, pkgs)
            summary["walk_target"] = room_id
            summary["walk_adjacent"] = walk_is_adjacent(cid, frame_id, room_id)
            if text:
                summary["beat"] = run_beat(cid, frame_id, text)
                stages, warnings = read_stages(summary["beat"]["turn_id"])
                summary["measures"] = measure(
                    cid, frame_id, before_plans=before_plans, before_needs=before_needs,
                    stages=stages, warnings=warnings, pkgs=pkgs)
        elif not pkgs:
            summary["beat"] = None
            summary["note"] = "nothing published; no beat run"
        if critic:
            summary["critic"] = critique(
                pkgs=pkgs, grant=grant, lore_hits=planner_run["lore_hits"],
                narration=(summary.get("measures") or {}).get("narration"),
                reply=planner_run["reply"].get("reply"), transcript=planner_run["calls"])
    summary["roles"] = [{"role": role, "model": model, "calls": v["calls"],
                         "seconds": round(v["seconds"], 1)}
                        for (role, model), v in capture.summary().items()]
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--grant", required=True, help="the player's line, a grant in words")
    ap.add_argument("--walk", default=None, help="the player's line for the beat")
    ap.add_argument("--planner", default=None, help="provider_id:model for story_planner")
    ap.add_argument("--dramaturge", default=None, help="provider_id:model for dramaturge")
    ap.add_argument("--critic", action="store_true")
    ap.add_argument("--no-turn", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    workdir, copy = prepare_copy(args.db)
    print("copied %s -> %s" % (args.db, copy), flush=True)
    from core import db
    db.configure(copy)
    db.init()
    summary = run(args.chat, grant=args.grant, walk=args.walk, planner=args.planner,
                  dramaturge=args.dramaturge, critic=args.critic, no_turn=args.no_turn)
    md, js = write_report(args.out or workdir, summary)
    print(render_report(summary))
    print("report: %s\nsummary: %s" % (md, js))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
