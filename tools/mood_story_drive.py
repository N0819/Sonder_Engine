#!/usr/bin/env python3
"""Play a mood test story through the real pipeline, a chunk of turns at a time.

The owner, 2026-09-26, said yes to playing test stories built to make the
mood's coordinates rise and fall ("We'll likely have to invent stories to test
moods"), with "new invented characters with fully filled out and nuanced
sheets". This drives the app's own seams -- `persona_create`, `chat_new`,
`chat_edit`, `chat_add_char`, and `turn_new` with its detached pipeline
drained on the calling thread -- against a scratch database with debug
capture on (`llm_capture_enabled`, `llm_capture_bodies=full`), so the affect
probe (`tools/jev_affect_probe.py collect`) reads every character call
afterwards. Nothing is authored for the model: the cast comes from the card
author (`story.importers.generate_character`), the opening from the Writers'
Room's own opening plan, and each player turn is prose -- action and
dialogue -- written by whoever runs this, a chunk at a time, after reading
what the story did.

After each turn it waits for the chat's out-of-band jobs to finish (never
`jobs.drain()`, which cancels them) and prints the narration and each
character's own reported mood, so the next chunk can answer the story rather
than a script.

Usage (ENGINE_DB must name a scratch database outside the tree):
    python tools/mood_story_drive.py start --name "The rival and the prize" \\
        --scenario-file premise.txt --persona-file persona.json \\
        --cast "Isolde Varga,Celestine Moreau" --known-cast "Isolde Varga,Celestine Moreau" \\
        --opening "Tomas steps off the night coach..."
    python tools/mood_story_drive.py play --chat 1 --inputs-file chunk.txt   # turns split by a line '---'
    python tools/mood_story_drive.py show --chat 1 --last 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.bubble_drive import _require_scratch  # noqa: E402

#: How long to wait for a chat's out-of-band jobs after a turn before moving
#: on anyway (memory consolidation and the like); named, not buried.
JOB_WAIT_SECONDS = 600


def _app():
    """The app, with its detached pipeline drained on the calling thread --
    `turn_new` looks `_detach` up at call time, so one patch makes every
    turn synchronous and keeps its events for inspection."""
    import web.app as app

    def _sync(gen):
        events = []
        app._drain_on_own_thread(gen, events.append).join()
        app.LAST_EVENTS = events

    app._detach = _sync
    return app


def _names():
    from core.db import q

    return {r["id"]: r["name"] for r in q("SELECT id, name FROM characters")}


def _narration(turn_id):
    from core.db import q

    row = q("SELECT v.content FROM variants v JOIN steps s ON s.id = v.step_id "
            "WHERE s.turn_id = ? AND s.key = 'narrator' AND v.active = 1", (turn_id,), one=True)
    if not row:
        return ""
    try:
        out = json.loads(row["content"]) or {}
        return out.get("prose") or out.get("text") or ""
    except (json.JSONDecodeError, TypeError, AttributeError):
        return str(row["content"])[:3000]


def _mood_line(who, result):
    """One character's own reported feeling, from a character call's result
    -- a standalone `character:<id>` step, or one entry of an interaction
    loop's `character_results`."""
    active = (result.get("active_state") or ((result.get("state") or {}).get("active")) or {})
    affect = active.get("affect") or {}
    surface = (affect.get("surface") or {}).get("label") if isinstance(affect.get("surface"), dict) else ""
    under = (affect.get("undercurrent") or {}).get("label") if isinstance(affect.get("undercurrent"), dict) else ""
    emotion = (result.get("appraisal") or {}).get("emotion") or ""
    return (f"{who}: {surface or '-'}" + (f" / beneath: {under}" if under else "")
            + (f"  (appraisal: {emotion})" if emotion else ""))


def _moods(turn_id):
    """Each character's own reported surface and undercurrent this turn."""
    from core.db import q

    names = _names()
    out = []
    for r in q("SELECT s.key, v.content FROM variants v JOIN steps s ON s.id = v.step_id "
               "WHERE s.turn_id = ? AND (s.key LIKE 'character:%' OR s.key = 'interaction_loop') AND v.active = 1",
               (turn_id,)):
        try:
            content = json.loads(r["content"]) or {}
        except (json.JSONDecodeError, TypeError):
            continue
        if r["key"] == "interaction_loop":
            for cid, result in (content.get("character_results") or {}).items():
                who = names.get(int(cid)) if str(cid).isdigit() else cid
                if isinstance(result, dict):
                    out.append(_mood_line(who, result))
            continue
        cid = r["key"].split(":", 1)[1]
        out.append(_mood_line(names.get(int(cid)) if cid.isdigit() else cid, content))
    return out


def turn(app, cid, text):
    """One turn through `turn_new`; returns (turn id, errors)."""
    from core import jobs
    from core.db import q

    started = time.time()
    out = app.turn_new(cid, {"input": text}, detach=1)
    events = getattr(app, "LAST_EVENTS", []) or []
    errors = [e for e in events if isinstance(e, dict) and e.get("type") in ("error", "aborted")]
    if isinstance(out, dict) and out.get("error"):
        errors.append(out)
    tid = (out or {}).get("turn_id") if isinstance(out, dict) else None
    deadline = time.time() + JOB_WAIT_SECONDS
    while jobs.active_jobs(cid) and time.time() < deadline:
        time.sleep(2)
    idx = (q("SELECT idx FROM turns WHERE id = ?", (tid,), one=True) or {"idx": "?"})["idx"] if tid else "?"
    print(f"\n=== turn {idx} (id {tid}, {time.time() - started:.0f}s)"
          + (f"  ERRORS: {json.dumps(errors)[:800]}" if errors else ""), flush=True)
    print(f">>> {text}", flush=True)
    if tid:
        print(_narration(tid), flush=True)
        for line in _moods(tid):
            print(f"  [mood] {line}", flush=True)
    return tid, errors


def start(args):
    from core.db import q

    app = _app()
    persona = json.loads(Path(args.persona_file).read_text(encoding="utf-8"))
    pid = app.persona_create({"sheet": persona})["id"]
    chat = app.chat_new({"name": args.name, "language": "en",
                         "scenario": Path(args.scenario_file).read_text(encoding="utf-8").strip()})
    cid = chat["id"]
    app.chat_edit(cid, {"persona_id": pid})
    known_player = {n.strip() for n in args.known_player.split(",") if n.strip()}
    known_cast = {n.strip() for n in args.known_cast.split(",") if n.strip()}
    for name in (n.strip() for n in args.cast.split(",") if n.strip()):
        row = q("SELECT id FROM characters WHERE name = ? ORDER BY id DESC LIMIT 1", (name,), one=True)
        if not row:
            raise SystemExit(f"no character named {name!r}")
        app.chat_add_char(cid, {"char_id": row["id"], "already_known": name in known_player,
                                "already_known_cast": name in known_cast})
    print(f"chat {cid}: persona {pid}, cast {args.cast}", flush=True)
    turn(app, cid, args.opening)


def play(args):
    app = _app()
    text = Path(args.inputs_file).read_text(encoding="utf-8")
    inputs = [chunk.strip() for chunk in text.split("\n---\n") if chunk.strip()]
    for line in inputs:
        _tid, errors = turn(app, args.chat, line)
        if errors:
            raise SystemExit("stopping at the first turn that errored")


def show(args):
    from core.db import q

    for r in q("SELECT id, idx, player_input FROM turns WHERE chat_id = ? ORDER BY idx DESC LIMIT ?",
               (args.chat, args.last))[::-1]:
        print(f"\n=== turn {r['idx']} (id {r['id']})\n>>> {r['player_input']}\n{_narration(r['id'])}")
        for line in _moods(r["id"]):
            print(f"  [mood] {line}")


def main():
    _require_scratch(os.environ.get("ENGINE_DB"))
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("start")
    p.add_argument("--name", required=True)
    p.add_argument("--scenario-file", required=True)
    p.add_argument("--persona-file", required=True)
    p.add_argument("--cast", required=True)
    p.add_argument("--known-player", default="", help="cast members who already know the player")
    p.add_argument("--known-cast", default="", help="cast members who already know each other")
    p.add_argument("--opening", required=True)
    p = sub.add_parser("play")
    p.add_argument("--chat", type=int, required=True)
    p.add_argument("--inputs-file", required=True)
    p = sub.add_parser("show")
    p.add_argument("--chat", type=int, required=True)
    p.add_argument("--last", type=int, default=3)
    args = parser.parse_args()
    {"start": start, "play": play, "show": show}[args.mode](args)


if __name__ == "__main__":
    main()
