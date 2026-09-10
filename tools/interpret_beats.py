#!/usr/bin/env python3
"""Play the INTERPRET half of many beats with a real model, and nothing else.

`tools/model_playthrough.py` plays whole turns, which is the right harness for
"do the prompts land" and the wrong one for one narrow question: does the
Director's author FILL `changes_asserted`, and does what it files route?

What `tools/dispatch_replay.py` scores is a single unit -- one
`director_interpret` step, which already fans out to the prose author plus all
five specialists. The rest of a turn (perception, every character, resolve, the
narrator, the off-screen rungs) is most of the wall clock and all of the cost
and contributes nothing the replay reads. So this drives the real
`run_pipeline` and STOPS at the first `director_interpret` step event: six
calls a beat instead of about twenty.

That is safe because capture is flushed at each step's OWN persist point --
`agents/runtime.py`, around the `record_exchange` call -- and not at the turn's
commit. Stopping early keeps the rows.

WHAT IT COSTS IN FIDELITY, stated because it bounds every number it produces:
nothing commits, so the scene never advances and every beat's interpret reads
the same world. That makes this a poor STORY and a fair DISPATCH sample. The
beats below span the manifest's category vocabulary rather than following one
another, which a linear playthrough would not have done either. For prose, for
mechanism fire-rates, or for anything that depends on a world that moves, use
`tools/model_playthrough.py` and pay for the turns.

    ENGINE_DB=scratch.db NANOGPT_API_KEY=... python3 tools/interpret_beats.py
    ENGINE_DB=scratch.db python3 tools/interpret_beats.py --providers-from live.db

`--providers-from` mirrors the provider rows and the `agent_models` mapping out
of another database, read-only, so the run uses the configuration that actually
ships rather than this harness's defaults -- which matters here, because
whether a model fills a new field is a fact about that model. API keys are
copied into the scratch database and are never printed.

Costs real money. Measured 2026-09-09 on `google/gemini-3.8-flash`: twelve
beats, 6-83s each, zero errors. What it found is design note
`DESIGN_NARROW_MODEL_INTERFACE.md` section 3c-ter.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.offscreen_drive import _require_scratch  # noqa: E402

#: Ordinary things a player types. Each is an OCCASION for a category in
#: `_CATEGORY_CHANNELS`; none names a channel, a field or a specialist, because
#: what is measured is whether the author reaches for the manifest unprompted
#: and what vocabulary it reaches for. The comment on each says what it is an
#: occasion FOR and is never sent to the model.
BEATS = [
    # attire, and a pose that follows from it
    "I pull off my sword belt and drop it on the bench, then sit down heavily.",
    # inventory and a handover: two subjects in one declaration
    "I take the sealed letter out of my satchel and put it into Sera's hands.",
    # positions / rooms: a plain walk through a door
    "I walk out of the forge and shut the door behind me.",
    # contact: an ordinary touch, uncontested
    "I put my hand on Sera's shoulder and keep it there while she reads.",
    # substance: something poured and drunk
    "I pour two cups of the dark beer and drink mine off in one go.",
    # entities and destruction: a made thing, and a broken one
    "I bring the hammer down on the cracked hinge until it comes apart.",
    # conditions: a hurt taken to the body
    "I burn my palm on the quench tongs and swear at it.",
    # stations / world_facts: something fixed in place and legible
    "I nail the notice about the wells to the post outside the door.",
    # a CONTESTED act -- the manifest should not claim this one
    "I try to take the ledger out of the reeve's hands before he can read it.",
    # speech alone: an occasion for NO change at all
    "I ask Sera whether she has seen the reeve today.",
    # attire again, on someone else, by consent
    "I unbuckle the strap of Sera's pack and lift it off her back for her.",
    # a compound beat: move, then handle a thing on arrival
    "I cross to the well, kneel, and haul the bucket up on its rope.",
]


def mirror_providers(db, source_path):
    """Copy another database's provider rows and role mapping, read-only.

    The alternative is this harness's own defaults, and they answer a
    different question: whether a model fills a new field is a fact about
    THAT model, so a run meant to predict production has to use production's
    wiring. Nothing else is read from the source -- no chat, no turn, no
    memory -- and `api_key` is written only into the scratch database.
    """
    live = sqlite3.connect("file:%s?mode=ro" % source_path, uri=True)
    live.row_factory = sqlite3.Row
    try:
        rows = list(live.execute(
            "SELECT id,name,kind,base_url,api_key,enabled FROM providers"))
        setting = live.execute(
            "SELECT value FROM settings WHERE key='agent_models'").fetchone()
    finally:
        live.close()

    remap = {}
    for row in rows:
        if not (row["api_key"] or "").strip():
            continue                       # a keyless local endpoint; skip it
        remap[row["id"]] = db.qi(
            "INSERT INTO providers(name,kind,base_url,api_key,enabled) "
            "VALUES(?,?,?,?,?)",
            (row["name"], row["kind"], row["base_url"], row["api_key"],
             row["enabled"]))

    source_models = json.loads(setting["value"]) if setting else {}
    from llm.providers import ROLES
    fallback = source_models.get("default") or {}
    models = {}
    for role in list(ROLES) + list(source_models):
        if role in models:
            continue
        entry = dict(source_models.get(role) or fallback)
        if entry.get("provider") in remap:
            entry["provider"] = remap[entry["provider"]]
            models[role] = entry
    db.set_setting("agent_models", json.dumps(models))
    print("mirrored %d providers, %d roles: %s"
          % (len(remap), len(models),
             ", ".join(sorted({e.get("model") or "?"
                               for e in models.values()}))), flush=True)
    return models


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--beats", type=int, default=0,
                    help="play only the first N (0 = all)")
    ap.add_argument("--providers-from", default="", metavar="DB",
                    help="mirror providers and agent_models out of this "
                         "database instead of seeding from the environment")
    ap.add_argument("--json", default="", help="write the per-beat rows here")
    args = ap.parse_args()

    _require_scratch()
    from core import db as db_module
    db_module.init()

    if args.providers_from:
        mirror_providers(db_module, args.providers_from)
    else:
        from tools.model_playthrough import seed_providers
        seed_providers(db_module)

    # `dispatch_replay` reads `llm_capture`/`llm_blobs`, and bodies are
    # hash-only unless asked for. Without both of these the run is paid for
    # and scores nothing.
    db_module.set_setting("llm_capture_enabled", "1")
    db_module.set_setting("llm_capture_bodies", "full")

    from tools.model_playthrough import install
    from tools.quest_drive import QuestAuthor, build_story
    install(QuestAuthor())
    cid = build_story(db_module)

    from agents.runtime import run_pipeline

    inputs = BEATS[:args.beats] if args.beats else BEATS
    print("playing the interpret half of %d beats" % len(inputs), flush=True)
    rows = []
    for idx, text in enumerate(inputs, start=1):
        # START AT 1. `turn.idx == 0` is the OPENING turn, whose plan is
        # establish -> perception -> narrator -> commit and holds no
        # `director_interpret` at all. The first smoke beat sat on idx 0, ran
        # a whole opening and reported a manifest of zero -- a fact about the
        # plan, read as a fact about the model.
        tid = db_module.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, text, time.time(), None))
        started, error, content = time.time(), "", None
        try:
            for evt in run_pipeline(cid, tid):
                if evt.get("type") == "step" \
                        and evt.get("key") == "director_interpret":
                    content = evt.get("content")
                    break                   # everything after this is paid for
        except Exception as exc:            # noqa: BLE001 - reported, not hidden
            error = "%s: %s" % (type(exc).__name__, exc)

        out = content if isinstance(content, dict) else {}
        manifest = [m for m in (out.get("changes_asserted") or [])
                    if isinstance(m, dict)]
        notes = out.get("ledger_notes") or {}
        rows.append({
            "turn": idx, "turn_id": tid, "input": text, "error": error,
            "seconds": round(time.time() - started, 1),
            "entries": manifest,
            "categories": sorted({str(m.get("category")) for m in manifest}),
            "notes": sorted(notes) if isinstance(notes, dict) else [],
        })
        print("  beat %2d  %5.1fs  manifest=%-2d notes=%-2d  %s%s" % (
            idx, rows[-1]["seconds"], len(manifest), len(rows[-1]["notes"]),
            text[:46], "  ERROR " + error[:70] if error else ""), flush=True)

    filed = [r for r in rows if r["entries"]]
    seen = sorted({c for r in rows for c in r["categories"]})
    print()
    print("beats            : %d" % len(rows))
    print("errors           : %d" % len([r for r in rows if r["error"]]))
    print("filed a manifest : %d (%.0f%%)"
          % (len(filed), 100.0 * len(filed) / max(1, len(rows))))
    print("categories seen  : %s" % ", ".join(seen))

    # The measurement this harness exists for. A category the router cannot
    # resolve reaches no hand, so the change is one nobody was handed -- which
    # is the false negative `dispatch_replay` counts, arriving one layer
    # earlier as a vocabulary miss rather than a routing one.
    from agents.director import manifest_category_targets
    unroutable = [c for c in seen if not manifest_category_targets(c)]
    print("UNROUTABLE       : %s" % (", ".join(unroutable) or "none"))

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh, indent=1)
        print("wrote %s" % args.json)
    return 1 if unroutable else 0


if __name__ == "__main__":
    raise SystemExit(main())
