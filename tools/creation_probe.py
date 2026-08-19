#!/usr/bin/env python3
"""When the player opens a door that was never there, what gets built.

Speed, schema-validity, leak-safety and reasoning are all measured elsewhere in
this directory, and none of them says whether a model can WORLD-BUILD. The
Director and the mapping stage are the two agents that turn a player's
improvisation into durable structure: the player says "you shoulder open the
side door" and something has to mint a room, give it exits, hang things in it
and decide what the air is like in there.

A model can pass every other test and produce a room called "Room" with an
empty description and no way out. That room is technically valid and the story
dies in it.

WHAT DEPTH MEANS HERE IS NOT PROSE LENGTH. It is the fields the engine can
actually act on. `anchors` are what `derive_scene_stations` needs before "on
the bed" can mean anything; a barriered, directed `adjacent` edge is what
sight, sound and scent are computed from; `exposure` is what decides how much
weather a room gets; entity `state` and `aliases` are what let the Director
refer to a thing twice and mean the same thing. A gorgeous paragraph with none
of that is scenery painted on a wall.

OVER-CREATION IS ALSO A FAILURE, and is scored as one. A player opening one
door should not mint nine rooms and a cast of strangers. The engine has to
carry everything that gets made, forever.

    python3 tools/creation_probe.py --step mapping_stage --models a,b
    python3 tools/creation_probe.py --step director_resolve --models a,b

Run it alone. The rate limit is per account.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The engine does not key its prompts, its schemas and its provider roles the
# same way, so a probe that benches `--step X` cannot assume a prompt called X.
# ONE copy of that mapping, in the tool that first had to work it out: a second
# hand-kept copy is how `creation_probe --step director_resolve` came to raise
# KeyError while `contract_bench --step director_resolve` worked.
from contract_bench import PROMPT_KEY  # noqa: E402

# One known room, one door nobody has ever been through, and a player who just
# went through it. Everything past that door has to be invented.
SCENE = {
    "rooms": {
        "workshop": {
            "name": "Clockmaker's Workshop",
            "desc": "A low room of benches and brass shavings. A stove in the "
                    "corner. A narrow side door, painted over, that nobody "
                    "has opened in years.",
            "adjacent": [{"to": "street", "barrier": "closed_door",
                          "distance": 1, "dir": "s"}],
            "anchors": {"bench_a": {"desc": "A long bench under the window.",
                                    "dir": "w"}},
            "exposure": "enclosed",
        },
        "street": {"name": "Cobbled Street", "desc": "A wet cobbled street.",
                   "adjacent": [{"to": "workshop", "barrier": "closed_door",
                                 "distance": 1, "dir": "n"}],
                   "exposure": "outdoor"},
    },
    "positions": {"Wren": "workshop"},
    "entities": {
        "stove_1": {"name": "Iron Stove", "kind": "fixture",
                    "description": "A squat iron stove, barely warm.",
                    "aliases": ["stove"], "state": {"lit": False}},
    },
    "location": "A clockmaker's workshop on a wet evening.",
}

PLAYER = ("You put your shoulder to the painted-over side door until it gives, "
          "and step through into whatever is behind it.")

PAYLOADS = {
    "mapping_stage": {
        "player_input": PLAYER,
        "scene": SCENE,
        "cast": [],
        "recent_turns": [],
        "books": [],
        "variant_seed": "creation",
    },
    "director_resolve": {
        "interpretation": {
            "speech": "",
            "action": "shoulder open the painted-over side door and step through",
            "sequence": [{"type": "action",
                          "attempt": "shoulder the painted side door open and "
                                     "step through",
                          "observable": "Wren puts a shoulder to the painted "
                                        "door until it gives.",
                          "visibility": "overt", "commitment": "contestable"}],
        },
        "scene": SCENE,
        "cast": [],
        "character_results": {},
        "variant_seed": "creation",
    },
}


def _created(parsed, step):
    """The rooms and entities this reply actually minted."""
    if step == "mapping_stage":
        patch = parsed.get("scene_patch") or {}
    else:
        patch = parsed.get("state_diff") or {}
    rooms = patch.get("rooms") if isinstance(patch, dict) else {}
    ents = patch.get("entities") if isinstance(patch, dict) else {}
    rooms = rooms if isinstance(rooms, dict) else {}
    ents = ents if isinstance(ents, dict) else {}
    new_rooms = {k: v for k, v in rooms.items() if k not in SCENE["rooms"]}
    new_ents = {k: v for k, v in ents.items() if k not in SCENE["entities"]}
    return new_rooms, new_ents


def _score(parsed, step):
    """Depth, measured in fields the engine can act on. Returns a dict."""
    rooms, ents = _created(parsed, step)
    out = {"rooms": len(rooms), "entities": len(ents), "desc_chars": 0,
           "anchors": 0, "edges": 0, "edges_barriered": 0, "edges_directed": 0,
           "exposure": 0, "ent_described": 0, "ent_state": 0, "ent_aliases": 0,
           "grounded": 0, "overbuilt": 0, "notes": 0}
    descs = []
    for room in rooms.values():
        if not isinstance(room, dict):
            continue
        desc = str(room.get("desc") or "")
        descs.append(len(desc))
        anchors = room.get("anchors")
        out["anchors"] += len(anchors) if isinstance(anchors, dict) else 0
        if str(room.get("exposure") or "").strip():
            out["exposure"] += 1
        if str(room.get("notes") or "").strip():
            out["notes"] += 1
        for edge in (room.get("adjacent") or []):
            if not isinstance(edge, dict):
                continue
            out["edges"] += 1
            if str(edge.get("barrier") or "").strip():
                out["edges_barriered"] += 1
            if str(edge.get("dir") or "").strip():
                out["edges_directed"] += 1
    out["desc_chars"] = int(statistics.median(descs)) if descs else 0
    for ent in ents.values():
        if not isinstance(ent, dict):
            continue
        if len(str(ent.get("description") or "")) > 30:
            out["ent_described"] += 1
        if isinstance(ent.get("state"), dict) and ent["state"]:
            out["ent_state"] += 1
        if ent.get("aliases"):
            out["ent_aliases"] += 1
    # Grounded: did the new material pick up the fiction it came from, rather
    # than a generic room bolted on. The door was PAINTED OVER, in a
    # CLOCKMAKER'S workshop -- a good invention smells of both.
    blob = json.dumps({"rooms": rooms, "entities": ents}).casefold()
    for cue in ("clock", "brass", "paint", "workshop", "dust", "gear",
                "spring", "tool", "shaving", "watch"):
        if cue in blob:
            out["grounded"] += 1
    # Over-creation: one door was opened. More than two new rooms is the model
    # building a wing nobody asked for, and the engine carries it forever.
    out["overbuilt"] = max(0, len(rooms) - 2)
    return out


def _post(prov, model, system, user, timeout, max_tokens):
    from llm import providers
    t0 = time.perf_counter()
    r = providers._session().post(
        prov["base_url"].rstrip("/") + "/chat/completions",
        headers=providers._headers(prov),
        json={"model": model,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
              "temperature": 0.6, "max_tokens": max_tokens},
        timeout=timeout)
    dt = time.perf_counter() - t0
    if r.status_code >= 400:
        return None, dt, f"HTTP {r.status_code}"
    data = r.json()
    return ((((data.get("choices") or [{}])[0].get("message") or {})
             .get("content") or "")), dt, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--step", default="mapping_stage",
                    choices=sorted(PAYLOADS))
    ap.add_argument("--models", required=True)
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--max-tokens", type=int, default=8000)
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    from core import db
    db.configure(args.db)
    from llm import llm_quality
    from llm import prompts
    from llm import schemas

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    prompt_key = PROMPT_KEY.get(args.step, args.step)
    if prompt_key not in prompts.DEFAULT_PROMPTS:
        ap.error("step %r resolves to prompt %r, which this engine does not "
                 "have. Add it to contract_bench.PROMPT_KEY if the prompt is "
                 "named differently from the step." % (args.step, prompt_key))
    system = prompts.DEFAULT_PROMPTS[prompt_key]
    payload = PAYLOADS[args.step]
    print(f"step {args.step}   one door opened, everything past it invented\n")

    table = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"  {model}", flush=True)
        runs, times, bad = [], [], 0
        for _ in range(args.trials):
            text, dt, err = _post(prov, model, system,
                                  json.dumps(payload, ensure_ascii=False),
                                  args.timeout, args.max_tokens)
            times.append(dt)
            if err:
                bad += 1
                print(f"        ! {err}", flush=True)
                continue
            try:
                parsed = llm_quality.strict_json_parse(text)
            except Exception as exc:
                bad += 1
                print(f"        ! parse: {str(exc)[:70]}", flush=True)
                continue
            report = schemas.validate_llm_output_strict(
                args.step, parsed, source_payload=payload)
            if not report.valid:
                bad += 1
                print(f"        ! schema: "
                      f"{'; '.join(report.errors[:2])[:90]}", flush=True)
                continue
            s = _score(report.output or parsed, args.step)
            runs.append(s)
            print(f"        rooms {s['rooms']} (desc {s['desc_chars']}ch, "
                  f"anchors {s['anchors']}, exits {s['edges']} "
                  f"[{s['edges_barriered']} barriered, "
                  f"{s['edges_directed']} directed], "
                  f"exposure {s['exposure']})  "
                  f"entities {s['entities']} "
                  f"({s['ent_described']} described, {s['ent_state']} stateful)"
                  f"  grounded {s['grounded']}/10"
                  + (f"  OVERBUILT +{s['overbuilt']}" if s['overbuilt'] else ""),
                  flush=True)
        if runs:
            agg = {k: statistics.mean(r[k] for r in runs) for k in runs[0]}
            # One number, so configs can be compared: usable structure per
            # reply, minus a penalty for building a wing nobody asked for.
            depth = (agg["rooms"] * 2 + agg["anchors"] * 1.5
                     + agg["edges_barriered"] + agg["edges_directed"] * 0.5
                     + agg["exposure"] + agg["entities"]
                     + agg["ent_described"] + agg["ent_state"]
                     + agg["grounded"] * 0.5
                     + min(agg["desc_chars"], 400) / 100.0
                     - agg["overbuilt"] * 3)
            table.append({"model": model, "depth": round(depth, 1),
                          "agg": agg, "bad": bad,
                          "median_s": statistics.median(times)})
        else:
            table.append({"model": model, "depth": None, "agg": None,
                          "bad": bad, "median_s": statistics.median(times)})
        print("", flush=True)

    print("=== world-building depth (usable structure per reply) ===")
    table.sort(key=lambda r: (r["depth"] is None, -(r["depth"] or 0)))
    for r in table:
        if r["depth"] is None:
            print(f"    ---   {r['bad']} unusable   {r['model']}")
            continue
        a = r["agg"]
        print(f"  {r['depth']:>6.1f}   rooms {a['rooms']:.1f}  "
              f"anchors {a['anchors']:.1f}  "
              f"barriered exits {a['edges_barriered']:.1f}  "
              f"entities {a['entities']:.1f}  "
              f"grounded {a['grounded']:.1f}/10  "
              f"{r['median_s']:>5.1f}s   {r['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
