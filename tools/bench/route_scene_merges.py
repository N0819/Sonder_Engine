"""How many times one `director_resolve` merges the scene, and what it costs.

`world.spatial.merge_scene_with_diff` deep-copies the whole scene and re-runs
every derivation pass. Review 2026-09-07 (C6) found `director_resolve` doing
that once per route or placement question -- the movement backstop, the
near-group repair, the travel continuation, the following carry, the
unreachable-position floor over the charter view, and the two mint-placement
floors -- each asking the same inputs the same question.

This REPLAYS stored resolve beats. It reads each turn's stored
`director_interpret` and `director_resolve` variants and the previous turn's
checkpoint scene, serves the stored resolve output back through the specialist
fan-out (`tests.helpers.fanout_resolve_agent`), and runs the real
`director_resolve` over it. So it makes NO model calls, and everything it
counts is the deterministic floor work a live beat does.

It writes only to a scratch database of its own, and reads the story database
read-only. Point it at a COPY, never a live one::

    python tools/bench/route_scene_merges.py <chat_id> <path/to/copy.db>
    python tools/bench/route_scene_merges.py 117 copy.db --answers out.json

`--answers` writes every beat's route decisions -- the resolved positions, the
refusals, the travel record, the planning needs, the warnings, the follow ops,
the stations and the identity bindings -- to a JSON file. Running it before and
after a change and diffing the two files is what makes "the same answer,
faster" a measurement rather than a claim.

PIN THE HASH SEED WHEN YOU DIFF: `PYTHONHASHSEED=0`. One warning the near-group
repair emits renders a dict built by iterating a `set` of body names
(`_reconcile_near_group_positions`, "contradictory positions were"), so its key
ORDER moves between processes on its own. With the seed pinned two runs of this
script agree byte for byte; without it they do not, and the difference is that
one string.

Measured 2026-09-07 with PYTHONHASHSEED=0, before -> after C6:

    chat 117, the descent, 123 beats, 38 rooms at its widest
        4.06 merges/beat, 43.6 ms/beat  ->  1.80 merges/beat, 22.5 ms/beat
    chat 114, the charter town, 13 beats
        2.85 merges/beat,  9.4 ms/beat  ->  1.38 merges/beat,  5.3 ms/beat

with both answer files byte-identical. The resolve wall clock this script
reports is higher than a live beat's: it stages every body the story ever
positioned as registered cast, which is not what any of those stories ran.
The merge line is the part the change touches, and it is measured the same
way on both sides.
"""

from __future__ import annotations

import json
import os
import sqlite3
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def stored_beats(path, chat):
    """``[(turn idx, scene before, resolve output, interpret), ...]``."""
    src = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    scenes = {}
    for idx, blob in src.execute(
            "SELECT turn_idx, blob FROM checkpoints WHERE chat_id=?", (chat,)):
        try:
            world = (json.loads(blob).get("world") or {}).get("scene")
        except (TypeError, ValueError):
            continue
        if isinstance(world, str):
            try:
                world = json.loads(world)
            except ValueError:
                continue
        if isinstance(world, dict):
            scenes[idx] = world

    def variants(key):
        out = {}
        for idx, content in src.execute(
                "SELECT t.idx, v.content FROM variants v "
                "JOIN steps s ON s.id=v.step_id JOIN turns t ON t.id=s.turn_id "
                "WHERE t.chat_id=? AND s.key=? AND v.active=1", (chat, key)):
            try:
                out[idx] = json.loads(content)
            except ValueError:
                continue
        return out

    interprets = variants("director_interpret")
    resolves = variants("director_resolve")
    src.close()
    beats = []
    for idx in sorted(resolves):
        # The scene the beat STARTED from: the previous turn's checkpoint,
        # falling back to this one's for the first stored beat.
        scene = scenes.get(idx - 1) or scenes.get(idx)
        if isinstance(scene, dict):
            beats.append((idx, scene, resolves[idx], interprets.get(idx) or {}))
    return beats


def _scratch_chat(db, scene, names):
    """A chat of our own carrying that scene and a cast of those names."""
    from story.character_schema import default_character_data
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("route-scene bench", "", time.time()))
    pid = db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                ("Player", json.dumps({"name": "Player"})))
    db.q("UPDATE chats SET persona_id=? WHERE id=?", (pid, cid))
    for name in names:
        char = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}", time.time(),
             "bench_" + name))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,?)", (cid, char, "active", "{}"))
    db.wset(cid, "scene", scene)
    return cid


def _copy_world_rows(db, cid, path, chat):
    """Every world row but the scene, so a charter story's registry is there
    and `common.charter_view_for_rooms` stands its bodies."""
    src = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    for key, value in src.execute(
            "SELECT key, value FROM world WHERE chat_id=?", (chat,)):
        if key == "scene":
            continue
        db.q("INSERT OR REPLACE INTO world(chat_id,key,value) VALUES(?,?,?)",
             (cid, key, value))
    src.close()


def _count_merges():
    """Wrap `merge_scene_with_diff` wherever it was imported by name."""
    import importlib

    import world.spatial_merge as spatial_merge
    real = spatial_merge.merge_scene_with_diff
    tally = {"n": 0, "ms": 0.0}

    def counting(scene, diff, *a, **kw):
        started = time.perf_counter()
        merged = real(scene, diff, *a, **kw)
        tally["ms"] += (time.perf_counter() - started) * 1000
        tally["n"] += 1
        return merged

    spatial_merge.merge_scene_with_diff = counting
    for name in ("world.spatial", "world.paradox", "agents.common",
                 "agents.director", "agents.director_movement",
                 "agents.director_floors"):
        module = importlib.import_module(name)
        if getattr(module, "merge_scene_with_diff", None) is real:
            module.merge_scene_with_diff = counting
    return tally


def _run_beat(db, cid, scene, resolve_out, interpret, idx):
    from agents import director
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from tests.helpers import fanout_resolve_agent
    db.wset(cid, "scene", scene)
    row = db.q("SELECT * FROM chats WHERE id=?", (cid,))[0]
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
                (cid,))
    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, idx, "bench", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name=row["name"], persona_id=row["persona_id"],
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn, chat_id=cid, idx=idx, player_input="bench",
                      created=time.time()),
        cast=cast, input="bench")
    ctx.director_interpret = interpret
    saved = director._agent_json
    director._agent_json = fanout_resolve_agent(resolve_out)
    try:
        started = time.perf_counter()
        out = director.director_resolve(ctx, nonce=0)
        return out, (time.perf_counter() - started) * 1000, list(ctx.warnings)
    finally:
        director._agent_json = saved


def _answer(out, warnings):
    """What a route question DECIDED, and nothing about how it got there."""
    diff = out.get("state_diff") or {}
    return {
        "positions": diff.get("positions"),
        "movement_refused": diff.get("movement_refused"),
        "following_ops": diff.get("following_ops"),
        "stations": diff.get("stations"),
        "travel": out.get("travel"),
        "travel_interrupted": out.get("travel_interrupted"),
        "planning_needs": out.get("planning_needs"),
        "identity_bindings": out.get("identity_bindings"),
        "warnings": warnings,
    }


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    chat = int(argv[1])
    path = argv[2]
    answers_path = None
    if "--answers" in argv:
        answers_path = argv[argv.index("--answers") + 1]

    scratch = tempfile.mktemp(suffix=".db")
    os.environ["ENGINE_DB"] = scratch
    from core import db
    db.configure(scratch)
    db.init()

    beats = stored_beats(path, chat)
    if not beats:
        print("no stored resolve beats for chat %d in %s" % (chat, path))
        return 1
    names = sorted({str(key) for _, scene, _, _ in beats
                    for key in (scene.get("positions") or {}) if str(key)})
    cid = _scratch_chat(db, beats[0][1], names)
    _copy_world_rows(db, cid, path, chat)

    tally = _count_merges()
    answers, merges, merge_ms, resolve_ms, failed = {}, [], [], [], 0
    for idx, scene, resolve_out, interpret in beats:
        tally["n"], tally["ms"] = 0, 0.0
        try:
            out, elapsed, warnings = _run_beat(
                db, cid, scene, resolve_out, interpret, idx)
        except Exception as exc:                       # a beat we cannot stage
            answers[idx] = {"error": "%s: %s" % (type(exc).__name__, exc)}
            failed += 1
            continue
        answers[idx] = _answer(out, warnings)
        merges.append(tally["n"])
        merge_ms.append(tally["ms"])
        resolve_ms.append(elapsed)

    print("chat %d: %d stored beats, %d replayed, %d could not be staged"
          % (chat, len(beats), len(merges), failed))
    if merges:
        print("  scene merges per beat   mean %.2f  median %.1f  max %d"
              "  total %d"
              % (statistics.mean(merges), statistics.median(merges),
                 max(merges), sum(merges)))
        print("  merge ms per beat       mean %.2f  median %.2f  total %.1f"
              % (statistics.mean(merge_ms), statistics.median(merge_ms),
                 sum(merge_ms)))
        print("  resolve ms per beat     mean %.2f  median %.2f  total %.1f"
              % (statistics.mean(resolve_ms), statistics.median(resolve_ms),
                 sum(resolve_ms)))
    if answers_path:
        with open(answers_path, "w") as handle:
            json.dump(answers, handle, indent=1, sort_keys=True, default=str)
        print("  route answers written to %s" % answers_path)
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(scratch + suffix)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
