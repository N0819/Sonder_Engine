#!/usr/bin/env python3
"""Can a model satisfy this engine's actual contracts, and how fast.

`tools/model_bench.py` measures raw call speed against a small invented schema,
and that is not enough -- it is actively misleading. A model scored 2/2 on a
three-key JSON object, was promoted to `director` on the strength of it, and
then failed the real `director_interpret` contract three times in a row on the
first live turn, burning 102 seconds to produce nothing. The toy schema proved
only that the model can emit JSON.

So this sends the engine's OWN system prompt for a step, a payload of the shape
that step really receives, and validates the reply with
`schemas.validate_llm_output_strict` -- the same gate the pipeline uses, with
the same Pydantic model and the same semantic checks. A pass here means the
model can actually do the job.

    python3 tools/contract_bench.py --step director_interpret --models a,b,c
    python3 tools/contract_bench.py --step character --models a,b --trials 3
    python3 tools/contract_bench.py --step director_body --models a,b

The request sent is the request the pipeline sends -- same system prompt, same
role's reasoning effort, same JSON mode -- because a bench that quietly leaves
reasoning on measures a regime production never runs, and does it worst for
the thinking models it is meant to rank.

The six Director specialists are benchable steps in their own right. They are
scoped structural tasks and are where a smaller, cheaper model most plausibly
belongs (design note 19), so they are the stages worth measuring before tiering
anything down.

Order the candidates by `model_bench` first; run the survivors through this.
Speed is only interesting among models that work.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Payloads shaped like the real thing: a two-character scene, a declared
# player act, and enough spatial context that the reply has to be about
# something. Deliberately not minimal -- a contract test on an empty scene
# tests the schema, not the model's ability to hold a beat in mind.
SCENE = {
    "rooms": {
        "inn_room": {"name": "Inn Room",
                     "desc": "A second-floor room, hearth down to embers, a "
                             "wide bed, a writing desk, a shut casement.",
                     "adjacent": [{"to": "inn_hallway",
                                   "barrier": "closed_door", "dir": "e"}]},
        "inn_hallway": {"name": "Hallway", "desc": "A narrow landing.",
                        "adjacent": [{"to": "inn_room",
                                      "barrier": "closed_door", "dir": "w"}]},
    },
    "positions": {"Wren": "inn_room", "Vessel": "inn_room"},
    "location": "A waystation inn on a mountain pass.",
}

PAYLOADS = {
    "director_interpret": {
        "player_input": "You cross to the window and try the latch, then say "
                        "\"It is stuck fast.\"",
        "player_name": "Wren",
        "scene": SCENE,
        "cast": [{"id": 2, "name": "Vessel", "room": "inn_room"}],
        "recent_turns": [
            {"idx": 33, "player_input": "You look around the room.",
             "narration": "The room is quiet, the hearth low."},
        ],
        "spatial_facts": ["Wren is in the Inn Room.",
                          "Vessel is in the Inn Room.",
                          "The casement window is shut but unlatched."],
        "variant_seed": "bench",
    },
    "director_resolve": {
        "interpretation": {
            "speech": "It is stuck fast.",
            "action": "cross to the window and try the latch",
            "sequence": [],
        },
        "scene": SCENE,
        "cast": [{"id": 2, "name": "Vessel", "room": "inn_room"}],
        "character_results": {},
        "variant_seed": "bench",
    },
    "narrator": {
        "player_view": "You cross to the window. The latch does not give. "
                       "You hear Vessel say: \"Leave it.\"",
        "scene": SCENE,
        "variant_seed": "bench",
    },
    # The two heaviest contracts in the engine. A model can pass one role's
    # schema and fail another's outright -- they ask for different SHAPES, not
    # merely different content -- so every role a config assigns has to be
    # tested on its own terms.
    # NO "perception". Perception is deterministic -- every view is composed
    # from the typed IR in agents/composer.py, and agents/perception.py imports
    # no model seam at all -- so no model this tool ranked would ever be called
    # for it. The prompt and schema survive so pre-change turns still validate
    # and replay; a BENCH row is a different thing, and offering one reports a
    # model's fitness for work it will never be given. Same argument as
    # providers.ROLES makes for not offering a perception settings row.
    "character": {
        "self": {
            "name": "Vessel",
            "psychology": {
                "drive": {"essence": "to be needed by someone who could leave",
                          "expression": "makes herself useful before she is asked",
                          "taboo": "will not ask anyone to stay"},
                "traits": [{"name": "watchful"}, {"name": "wry"}],
                "capacity": "ordinary",
            },
            "attention": {"wants": 3, "intentions": 4, "band": "ordinary",
                          "means": "the human middle"},
            "intentions": [{"id": "i1", "intent": "find out why Wren is "
                                                 "leaving at night",
                            "status": "active", "progress": 0.2}],
            "steering_intention_ids": ["i1"],
            "projects": [],
            "body_state": {"mood": "wary", "valence": -0.1, "arousal": 0.4},
        },
        "perception": {
            "view": "Wren crosses to the casement and works at the latch. It "
                    "does not give. \"It is stuck fast,\" she says.",
            "observations": [
                {"observation_id": "current:Vessel:0",
                 "observed": {"text": "Wren works at the window latch; it "
                                      "does not give."}},
                {"observation_id": "current:Vessel:1",
                 "observed": {"text": "Wren says: \"It is stuck fast.\""}},
            ],
            "current_room": "Inn Room",
        },
        "memory": {"recent_episodes": [], "recalled_old_memories": []},
        "relationships": {}, "mind_models": [], "active_hypotheses": [],
        "decision": {"dialogue_mode": True,
                     "speech_budget": {"suggested_lines": 1, "hard_max": 2,
                                       "may_stay_silent": True}},
        "variant_seed": "bench",
    },
}


# THE SIX SPECIALISTS, which had no payloads here at all -- so the stages that
# actually decide whether a smaller model can be tiered in were the only ones
# that could not be measured. Each gets the shared beat view (design note 19:
# the beat, the declared acts, the final dice, the roster) plus its OWN
# ledgers, and nothing else. Built at resolve, where every specialist runs.
_SPEC_BASE = {
    "source": "resolved_beat",
    "player": "Wren",
    "cast": ["Vessel"],
    "declared_actions": [{"actor": "Wren",
                          "attempt": "cross to the window and try the latch",
                          "commitment": "contestable"}],
    "dice_results_final": [],
    "resolved_event": "Wren crosses to the casement and works the latch; it "
                      "does not give. Her coat slips from one shoulder as she "
                      "leans into it. \"It is stuck fast,\" she says.",
    "dialogue_log": [{"speaker": "Wren", "exact_quote": "It is stuck fast."}],
    "variant_seed": "bench",
}
_ROOMS_INDEX = {"inn_room": "Inn Room", "inn_hallway": "Hallway"}

PAYLOADS.update({
    "director_body": {
        **_SPEC_BASE,
        "attire": {"Wren": {"wearing": ["wool coat", "linen shirt", "boots"]},
                   "Vessel": {"wearing": ["grey robe"]}},
        "overlays": {}, "active_awareness": {"Wren": "awake", "Vessel": "awake"},
        "simulation_clock": {"time_of_day": "late evening"},
        "rooms": _ROOMS_INDEX,
    },
    "director_social": {**_SPEC_BASE, "background_presences": ["innkeeper"]},
    "director_contact": {
        **_SPEC_BASE,
        "contacts": [], "contained": {}, "scales": {},
        "rooms": _ROOMS_INDEX,
        "entity_names": {"casement": "casement window", "desk": "writing desk"},
        "worn_garments": [{"name": "wool coat", "worn_by": "Wren"},
                          {"name": "grey robe", "worn_by": "Vessel"}],
    },
    "director_objects": {
        **_SPEC_BASE,
        "entities": {"casement": {"name": "casement window", "kind": "fixture",
                                  "portable": False,
                                  "state": {"latch": "stuck"}}},
        "rooms": _ROOMS_INDEX, "notices": [],
        "worn_garments": [{"name": "wool coat", "worn_by": "Wren"}],
    },
    "director_spatial": {
        **_SPEC_BASE,
        "rooms": SCENE["rooms"], "positions": SCENE["positions"],
        "stations": {"Wren": "at the casement"},
        "poses": {}, "contained": {}, "movement": None, "movers": {},
    },
    "director_offscreen": {
        **_SPEC_BASE,
        "crowds": [], "couriers": [], "carried_reports": [],
        "unratified_claims": [],
        "offscreen_planning": {"enabled": False, "plans": []},
        "rooms": _ROOMS_INDEX,
    },
})

# The engine does not key its prompts, its schemas and its provider roles the
# same way, and benching the wrong one of the three fails silently or not at
# all. `director_resolve` is the clearest case: a real SCHEMA_MAP step with no
# prompt of that name, because the monolith is gone (design note 19) and the
# prose author's prompt is `director_resolve_lean`. `--step director_resolve`
# therefore raised KeyError, and the resolve contract -- the one every live
# failure has been about -- could not be benched at all.
PROMPT_KEY = {"director_resolve": "director_resolve_lean"}

# Which provider role's reasoning effort each step runs under in production,
# so _post can send what the pipeline sends. `character` has three tiers and
# is benched at the most demanding one; a background character running cheaper
# is a floor, not a ceiling.
STEP_ROLE = {
    "director_interpret": "director",
    "director_resolve": "director",
    "director_establish": "director",
    "character": "character_major",
    "narrator": "narrator",
    "mapping": "mapping",
    **{f"director_{n}": f"director_{n}" for n in
       ("body", "social", "contact", "objects", "spatial", "offscreen")},
}


def providers_reasoning_effort(role):
    """What the run will actually send, reported in the header. The whole
    point of the fix below is that this is no longer implicitly 'whatever the
    model defaults to'; printing it is how a reader knows which regime the
    numbers came from."""
    import providers
    return providers.reasoning_effort_for(role)


def _post(prov, model, system, user, max_tokens, timeout, role):
    import providers
    base = prov["base_url"].rstrip("/")
    body = {"model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": 0.4, "max_tokens": max_tokens}
    # BENCH WHAT PRODUCTION SENDS. Hand-built, this body carried neither the
    # role's reasoning effort nor JSON mode, so a thinking model was measured
    # WITH reasoning while the pipeline runs it with reasoning off -- inflating
    # latency and output tokens for exactly the models this tool exists to
    # rank, and by a wide margin (measured elsewhere at 8.1x on one step).
    # A tool that ranks models has to send the request the engine sends.
    providers._apply_reasoning_effort(body, prov, role)
    providers._apply_json_mode(body, prov, model, True)
    start = time.perf_counter()
    r = providers._session().post(base + "/chat/completions",
                                  headers=providers._headers(prov),
                                  json=body, timeout=timeout)
    elapsed = time.perf_counter() - start
    if r.status_code >= 400:
        return None, elapsed, f"{r.status_code} {(r.text or '')[:140]}"
    data = r.json()
    text = (((data.get("choices") or [{}])[0].get("message") or {})
            .get("content") or "")
    usage = data.get("usage") or {}
    return {"text": text, "out": usage.get("completion_tokens"),
            "inp": usage.get("prompt_tokens")}, elapsed, None


def bench(prov, model, step, payload, system, trials, timeout, max_tokens):
    import llm_quality
    import schemas
    role = STEP_ROLE.get(step, "default")
    passes, times, outs, errors = 0, [], [], []
    for _ in range(trials):
        got, elapsed, err = _post(prov, model, system,
                                  json.dumps(payload, ensure_ascii=False),
                                  max_tokens, timeout, role)
        times.append(elapsed)
        if err:
            errors.append(err)
            continue
        outs.append(got.get("out") or 0)
        try:
            parsed = llm_quality.strict_json_parse(got["text"])
        except Exception as exc:
            errors.append(f"parse: {str(exc)[:90]}")
            continue
        report = schemas.validate_llm_output_strict(
            step, parsed, source_payload=payload)
        if report.valid:
            passes += 1
        else:
            errors.append("; ".join(report.errors[:2])[:120])
    return {"model": model, "passes": passes, "trials": trials,
            "median_s": round(statistics.median(times), 2) if times else None,
            "out_tokens": int(statistics.median(outs)) if outs else 0,
            "prompt_tokens": None,
            "errors": errors[:3]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--step", default="director_interpret",
                    choices=sorted(PAYLOADS))
    ap.add_argument("--models", required=True)
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    import db
    db.configure(args.db)
    import prompts

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    system = prompts.DEFAULT_PROMPTS[PROMPT_KEY.get(args.step, args.step)]
    payload = PAYLOADS[args.step]
    role = STEP_ROLE.get(args.step, "default")
    effort = providers_reasoning_effort(role)
    print(f"step {args.step}  system {len(system)} chars  "
          f"payload {len(json.dumps(payload))} chars  "
          f"role {role}  reasoning {effort or 'unset'}\n")

    rows = []
    for name in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"  {name}", flush=True)
        try:
            r = bench(prov, name, args.step, payload, system,
                      args.trials, args.timeout, args.max_tokens)
        except Exception as exc:
            r = {"model": name, "passes": 0, "trials": args.trials,
                 "median_s": None, "out_tokens": 0,
                 "errors": [str(exc)[:120]]}
        rows.append(r)
        mark = "PASS" if r["passes"] == r["trials"] else (
            "part" if r["passes"] else "FAIL")
        print(f"      {mark}  {r['passes']}/{r['trials']}  "
              f"{r['median_s']}s  {r['out_tokens']} out tok", flush=True)
        for e in r["errors"]:
            print(f"        ! {e}", flush=True)

    ok = [r for r in rows if r["passes"] == r["trials"]]
    ok.sort(key=lambda r: r["median_s"] or 1e9)
    print(f"\n=== {args.step}: models that satisfy the real contract ===")
    if not ok:
        print("  none")
    for r in ok:
        print(f"  {r['median_s']:>7.2f}s  {r['out_tokens']:>6} tok  {r['model']}")
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(rows, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
