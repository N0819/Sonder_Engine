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

    python3 tools/contract_bench.py --step character_bare --models a,b --trials 3
    python3 tools/contract_bench.py --step narrator --models a,b,c

The request sent is the request the pipeline sends -- same system prompt, same
role's reasoning effort, same JSON mode -- because a bench that quietly leaves
reasoning on measures a regime production never runs, and does it worst for
the thinking models it is meant to rank.

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
    "narrator": {
        "present_scene": "You cross to the window. The latch does not give. "
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
    "character_bare": {
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


# The engine does not key its prompts, its schemas and its provider roles the
# same way, and benching the wrong one of the three fails silently or not at
# all: a step whose prompt goes by another id is mapped here. None does since
# the causal Director (whose resolve prompt was `director_resolve_lean`) was
# deleted, 2026-09-27. The prose Director's sheets are built per stage from
# their own card (`prompts.prose_director_prompt`), and no step here benches
# them yet.
PROMPT_KEY: dict = {}

# Which provider role's reasoning effort each step runs under in production,
# so _post can send what the pipeline sends. `character` has three tiers and
# is benched at the most demanding one; a background character running cheaper
# is a floor, not a ceiling.
STEP_ROLE = {
    "director_establish": "director",
    "character_bare": "character_major",
    "narrator": "narrator",
}


def providers_reasoning_effort(role):
    """What the run will actually send, reported in the header. The whole
    point of the fix below is that this is no longer implicitly 'whatever the
    model defaults to'; printing it is how a reader knows which regime the
    numbers came from."""
    from llm import providers
    return providers.reasoning_effort_for(role)


def _post(prov, model, system, user, max_tokens, timeout, role, step):
    from llm import providers
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
    # The step's schema, exactly as complete_validated_json now supplies it --
    # an enforced grammar where the backend can compile one. Without this the
    # bench measured the advisory `json_object` flag, which on a llama.cpp host
    # is honoured only sometimes (narrator: 0/5 valid) while the engine's real
    # path is enforced (5/5). Benching the weaker of the two would rank models
    # on a failure mode production no longer has.
    from llm import llm_quality
    providers._apply_json_mode(body, prov, model, True,
                               llm_quality._step_json_schema(step))
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
    from llm import llm_quality
    from llm import schemas
    role = STEP_ROLE.get(step, "default")
    passes, times, outs, errors = 0, [], [], []
    for _ in range(trials):
        got, elapsed, err = _post(prov, model, system,
                                  json.dumps(payload, ensure_ascii=False),
                                  max_tokens, timeout, role, step)
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
    ap.add_argument("--step", default="character_bare",
                    choices=sorted(PAYLOADS))
    ap.add_argument("--models", required=True)
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    from core import db
    db.configure(args.db)
    from llm import prompts

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
