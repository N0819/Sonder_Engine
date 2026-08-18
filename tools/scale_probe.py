#!/usr/bin/env python3
"""Does the model still keep minds apart when the room is crowded?

Speed and schema-validity are both measured with one or two characters in the
scene, and that is the easy case. The failures worth fearing appear at load and
are SILENT:

  * perception fans out per perceiver. With five people in a room, a weaker
    model can hand A's view to B, drop a perceiver entirely, or let something
    only C could perceive bleed into D's view. Every one of those is an
    information-firewall breach -- the thing this engine exists to prevent --
    and none of them raises. The turn completes and the story is quietly wrong.
  * the Director routes the beat: who reacts, who was addressed, what each act
    targets. Fumbled routing with five characters means the wrong people
    answer, and again nothing errors.

So this builds a deliberately crowded scene where every perceiver has ONE
sentinel fact that only they can perceive, sends the engine's real prompt, and
then checks the reply for cross-contamination rather than merely for valid
JSON. A model can pass every other test in this repo and fail here.

    python3 tools/scale_probe.py --step perception --models a,b --perceivers 5
    python3 tools/scale_probe.py --step director_interpret --models a,b

Run it SEQUENTIALLY and on its own. The rate limit is on the account, and
benchmarking two things at once manufactures 429s that read as model failure.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Five bodies, one room each sentinel is tied to, and a sixth room nobody is in.
# Each perceiver holds a distinct sentinel token; a token appearing in anybody
# else's view is a leak with a name on it.
PEOPLE = [
    ("Ada",   "hall",    "ADA_SENTINEL_a copper key pressed into her palm"),
    ("Bram",  "hall",    "BRAM_SENTINEL_a torn ticket stub in his cuff"),
    ("Cyra",  "hall",    "CYRA_SENTINEL_a name inked on her wrist"),
    ("Dov",   "gallery", "DOV_SENTINEL_a cracked lens in his pocket"),
    ("Eirn",  "gallery", "EIRN_SENTINEL_a folded map under her belt"),
]

SCENE = {
    "rooms": {
        "hall": {"name": "Great Hall",
                 "desc": "A long hall, lamps guttering, a stair at the north end.",
                 "adjacent": [{"to": "gallery", "barrier": "closed_door",
                               "dir": "n"}]},
        "gallery": {"name": "Upper Gallery",
                    "desc": "A railed gallery above the hall.",
                    "adjacent": [{"to": "hall", "barrier": "closed_door",
                                  "dir": "s"}]},
    },
    "positions": {name: room for name, room, _ in PEOPLE},
    "location": "A shuttered auction house after closing.",
}


def _perception_payload(n):
    people = PEOPLE[:n]
    return {
        "perceivers": [
            {"id": str(i + 2), "name": name, "room": room,
             "awareness": "awake",
             # The sentinel is delivered ONLY in this perceiver's own private
             # slot. Nothing legitimate can move it into another view.
             "private_body_state": f"You are carrying {sentinel}."}
            for i, (name, room, sentinel) in enumerate(people)
        ],
        "resolved_event": (
            "The lamps gutter. Someone on the stair says \"It is time.\" "
            "Ada turns toward the sound; Bram does not move; Cyra steps back "
            "from the table. In the gallery above, Dov leans on the rail and "
            "Eirn checks the door."),
        "scene": SCENE,
        "variant_seed": "scale",
    }


def _director_payload(n):
    people = PEOPLE[:n]
    return {
        "player_input": "\"Cyra, get the door. Dov, stay where you are.\" "
                        "You move toward the stair.",
        "player_name": "Wren",
        "scene": {**SCENE,
                  "positions": {**SCENE["positions"], "Wren": "hall"}},
        "cast": [{"id": i + 2, "name": name, "room": room}
                 for i, (name, room, _s) in enumerate(people)],
        "recent_turns": [],
        "spatial_facts": [f"{name} is in the {SCENE['rooms'][room]['name']}."
                          for name, room, _ in people],
        "variant_seed": "scale",
    }


def _post(prov, model, system, user, max_tokens, timeout):
    from llm import providers
    body = {"model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.4, "max_tokens": max_tokens}
    t0 = time.perf_counter()
    r = providers._session().post(
        prov["base_url"].rstrip("/") + "/chat/completions",
        headers=providers._headers(prov), json=body, timeout=timeout)
    dt = time.perf_counter() - t0
    if r.status_code >= 400:
        return None, dt, f"HTTP {r.status_code} {(r.text or '')[:110]}"
    data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {})
            .get("content") or "")
    return text, dt, None


def _check_perception(parsed, n):
    """Every perceiver present, nobody else's sentinel in anybody's view."""
    problems = []
    views = parsed.get("views")
    if not isinstance(views, dict):
        return ["no `views` object"]
    people = PEOPLE[:n]
    # Views may be keyed by id or by name; accept either, reject neither.
    keys = {str(k).strip().casefold() for k in views}
    for i, (name, _room, _s) in enumerate(people):
        if str(i + 2) not in keys and name.casefold() not in keys:
            problems.append(f"missing perceiver {name}")
    tokens = {name: sentinel.split("_")[0] + "_SENTINEL"
              for name, _r, sentinel in people}
    for key, view in views.items():
        text = str(view or "")
        owner = None
        for i, (name, _r, _s) in enumerate(people):
            if str(key).strip().casefold() in (str(i + 2), name.casefold()):
                owner = name
                break
        for name, token in tokens.items():
            if name != owner and token in text:
                problems.append(f"{name}'s sentinel leaked into {owner or key}")
    return problems


def _check_director(parsed, n):
    """Routing: the two named people are addressed, nobody invented."""
    problems = []
    # A body may legitimately be named OR keyed by its cast id -- the engine
    # accepts both, and both models used ids here. Rejecting ids read as
    # "addressed an invented body: 4" when 4 was simply Cyra, which is the
    # checker being wrong about the contract rather than the model.
    names = {name.casefold() for name, _r, _s in PEOPLE[:n]} | {"wren"}
    ids = {str(i + 2) for i in range(n)}
    known = names | ids
    by_name = {name.casefold(): str(i + 2)
               for i, (name, _r, _s) in enumerate(PEOPLE[:n])}
    blob = json.dumps(parsed).casefold()
    for expected in ("cyra", "dov"):
        if expected not in blob and by_name[expected] not in blob:
            problems.append(f"never routed to {expected}")
    flow = parsed.get("flow") or {}
    for field in ("addressed_to", "reactors"):
        for who in (flow.get(field) or []):
            if str(who).strip().casefold() not in known:
                problems.append(f"{field}: invented body {who!r}")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--step", default="perception",
                    choices=("perception", "director_interpret"))
    ap.add_argument("--models", required=True)
    ap.add_argument("--perceivers", type=int, default=5)
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
    n = max(1, min(args.perceivers, len(PEOPLE)))
    payload = (_perception_payload(n) if args.step == "perception"
               else _director_payload(n))
    system = prompts.DEFAULT_PROMPTS[args.step]
    checker = _check_perception if args.step == "perception" else _check_director

    print(f"step {args.step}  {n} bodies  system {len(system)} chars\n")
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"  {model}", flush=True)
        clean, times, notes = 0, [], []
        for _ in range(args.trials):
            text, dt, err = _post(prov, model, system,
                                  json.dumps(payload, ensure_ascii=False),
                                  args.max_tokens, args.timeout)
            times.append(dt)
            if err:
                notes.append(err)
                continue
            try:
                parsed = llm_quality.strict_json_parse(text)
            except Exception as exc:
                notes.append(f"parse: {str(exc)[:80]}")
                continue
            report = schemas.validate_llm_output_strict(
                args.step, parsed, source_payload=payload)
            if not report.valid:
                notes.append("schema: " + "; ".join(report.errors[:2])[:90])
                continue
            problems = checker(report.output or parsed, n)
            if problems:
                notes.extend(problems[:3])
            else:
                clean += 1
        med = statistics.median(times) if times else 0
        mark = "CLEAN" if clean == args.trials else (
            "part" if clean else "FAIL")
        print(f"      {mark}  {clean}/{args.trials} clean  {med:.2f}s",
              flush=True)
        for note in notes[:4]:
            print(f"        ! {note}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
