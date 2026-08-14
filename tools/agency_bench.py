#!/usr/bin/env python3
"""Give a character a problem and see whether it solves one.

Divergence benchmarks measure whether a model repeats itself, which is the
absence of a defect rather than the presence of a mind. This asks the question
that actually matters for a cognitive agent: put it in a situation with a real
obstacle and an unsignposted way through, and see whether it finds one.

Every scenario is built the same way:

  * a GOAL the character plainly has,
  * a BLOCKED path that is the obvious move and cannot work -- stated in the
    payload as a fact, not as a hint,
  * one or more VALID affordances present in the scene and never pointed at,
  * and a scoring function that reads the character's own declared conduct.

Scoring is three-way, because "did it solve it" is not the only question worth
asking of an agent:

  SOLVED    engaged an affordance that actually resolves the obstacle
  BLOCKED   took the obvious path the payload says cannot work -- not stupidity
            exactly, but a mind that did not read its own situation
  NOVEL     solved it by a route the scenario did not anticipate, judged by
            an affordance appearing that was in the scene but not on the
            expected list. Recorded, never penalised: an agent finding a door
            the author did not plan is the whole point of the exercise.

The scenarios are deliberately Sonder-shaped -- one turns on the engine's own
body-scale rule, one on a mouth that is physically occupied, one on a memory
contradicting a claim. A model can only solve those by reading the structured
payload, which is the skill the engine actually needs.

    python3 tools/agency_bench.py --models a,b --trials 2

Run it alone; the rate limit is per account.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _rx(*words):
    return re.compile(r"\b(" + "|".join(words) + r")\w*", re.I)


SCENARIOS = [
    {
        "name": "sealed room",
        "goal": "get out of the room before whoever is on the stair arrives",
        "room": {
            "name": "Attic Room",
            "desc": "A cramped attic. The door is bolted from the OUTSIDE and "
                    "does not shift when pushed. A casement window sits in the "
                    "gable, shut, its latch hanging loose and unfastened. Rain "
                    "on the slates. A brass-bound trunk stands under the eave.",
        },
        "observations": [
            "The door is bolted from the outside; it does not move when you push it.",
            "The casement window is shut. Its latch hangs loose and unfastened.",
            "A brass-bound trunk stands under the eave.",
            "Footsteps are coming up the stair.",
        ],
        "valid": _rx("window", "casement", "latch", "gable", "sill", "slate"),
        "blocked": _rx("bolt", "unbolt"),
        "novel": _rx("trunk", "hinge", "eave", "shout", "call", "roof"),
    },
    {
        "name": "occupied mouth",
        "goal": "warn Bram that the stair tread is broken, before he steps on it",
        "room": {
            "name": "Landing",
            "desc": "A narrow landing. You are carrying a full washbasin in "
                    "both hands and a lit taper clenched in your teeth. Bram "
                    "is at the top of the stair with his back to you, about to "
                    "start down. The third tread is split through.",
        },
        "observations": [
            "You are carrying a full washbasin in both hands.",
            "A lit taper is clenched in your teeth; your mouth is occupied.",
            "Bram is at the top of the stair with his back to you.",
            "The third tread down is split through.",
        ],
        # Anything that makes a signal WITHOUT clear speech, or frees the mouth.
        "valid": _rx("stamp", "kick", "drop", "spit", "set down", "put down",
                     "throw", "knock", "rap", "bang", "hum", "grunt", "whistle",
                     "shove", "lower", "tip", "spill", "clatter", "floor",
                     "basin", "taper", "tap"),
        "blocked": _rx("shout", "yell", "call out", "say", "says", "speak",
                       "warn him that", "tell him"),
        "novel": _rx("mirror", "shadow", "wall", "rail", "banister"),
    },
    {
        "name": "outmatched by scale",
        "goal": "stop the door swinging shut and sealing you in",
        "room": {
            "name": "Pantry",
            "desc": "A pantry. You have been reduced to a fraction of your "
                    "height -- you stand about as tall as a spoon. The heavy "
                    "door is swinging slowly shut on its own weight. A "
                    "scattering of dropped items lies on the boards: a cork, a "
                    "bent nail, a wedge of cheese rind, a thimble.",
        },
        "observations": [
            "You are roughly the height of a spoon; the door outweighs you enormously.",
            "The heavy door is swinging slowly shut.",
            "On the boards: a cork, a bent nail, a wedge of rind, a thimble.",
            "The gap at the hinge side is still open.",
        ],
        # A tiny body cannot out-push a door; it can jam one.
        "valid": _rx("cork", "nail", "thimble", "rind", "wedge", "jam", "block",
                     "prop", "hinge", "gap", "wedging", "under the door",
                     "doorstop", "obstruct"),
        "blocked": _rx("push the door", "hold the door", "pull the door",
                       "shoulder", "brace against the door", "heave"),
        "novel": _rx("shout", "call", "slip through", "outside", "escape",
                     "roll", "lever", "leverage"),
    },
    {
        "name": "the contradiction",
        "goal": "work out whether Cyra is telling the truth",
        "room": {
            "name": "Kitchen",
            "desc": "A kitchen at first light. Cyra stands by the range with "
                    "her sleeves down.",
        },
        "observations": [
            "Cyra says: \"I was never down in the cellar. Not once, all week.\"",
        ],
        "memory": [
            {"memory_ref": "event:c3llar",
             "gist": "Last night I saw Cyra's green-glass lantern burning at "
                     "the foot of the cellar stair, and nobody else owns one."},
        ],
        # Solving = actually USING the remembered contradiction.
        "valid": _rx("lantern", "green", "glass", "cellar stair", "last night",
                     "saw", "remember", "contradict", "lying", "lie", "untrue"),
        "blocked": _rx("believe her", "accept", "no reason to doubt",
                       "takes her at"),
        "novel": _rx("sleeve", "dust", "boots", "hem", "ask", "test", "trap"),
    },
]


def _payload(sc):
    return {
        "self": {
            "name": "Vessel",
            "psychology": {
                "drive": {"essence": "to get out from under whatever holds her",
                          "expression": "looks for the seam in a thing",
                          "taboo": "will not wait to be rescued"},
                "traits": [{"name": "resourceful"}, {"name": "quick"}],
                "capacity": "ordinary",
            },
            "attention": {"wants": 3, "intentions": 4, "band": "ordinary",
                          "means": "the human middle"},
            "intentions": [{"id": "i1", "intent": sc["goal"],
                            "status": "active", "progress": 0.0}],
            "steering_intention_ids": ["i1"],
            "projects": [],
            "body_state": {"mood": "urgent", "valence": -0.3, "arousal": 0.7},
        },
        "perception": {
            "view": sc["room"]["desc"],
            "observations": [{"observation_id": f"current:Vessel:{i}",
                              "observed": {"text": t}}
                             for i, t in enumerate(sc["observations"])],
            "current_room": sc["room"]["name"],
        },
        "memory": {"recent_episodes": sc.get("memory") or [],
                   "recalled_old_memories": []},
        "relationships": {}, "mind_models": [], "active_hypotheses": [],
        "decision": {"dialogue_mode": True,
                     "speech_budget": {"suggested_lines": 1, "hard_max": 2,
                                       "may_stay_silent": True}},
        "variant_seed": "agency",
    }


def _conduct(parsed):
    """What the character actually DID and SAID -- not what it mused about.

    `considered_responses` is deliberately excluded: weighing an option is not
    taking it, and a model that lists the right idea and then does something
    else has not solved anything.
    """
    bits = []
    for e in (parsed.get("sequence") or []):
        if isinstance(e, dict):
            bits += [str(e.get("attempt") or ""), str(e.get("observable") or ""),
                     str(e.get("text") or "")]
    for cand in (parsed.get("response_candidates") or []):
        if isinstance(cand, dict) and cand.get("selected"):
            bits.append(str(cand.get("response") or ""))
    bits += [str(parsed.get("action") or ""), str(parsed.get("speech") or "")]
    return " ".join(b for b in bits if b)


def _post(prov, model, system, user, timeout, max_tokens):
    """One scored call, with transport failures retried rather than fatal.

    A long unattended arm meets a dropped connection eventually -- this one
    died on `RemoteDisconnected` two scenarios in, losing the whole arm and,
    worse, losing the COMPARISON, since the surviving arm has nothing to be
    compared against. A transport error is not a result: it says nothing about
    the model or the contract, so it is retried, and only a persistent one is
    reported as `err` and counted as bad.
    """
    import providers
    last = None
    for attempt in range(3):
        t0 = time.perf_counter()
        try:
            r = providers._session().post(
                prov["base_url"].rstrip("/") + "/chat/completions",
                headers=providers._headers(prov),
                json={"model": model,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
                      "temperature": 0.7, "max_tokens": max_tokens},
                timeout=timeout)
        except Exception as exc:                      # transport, not verdict
            last = (time.perf_counter() - t0, f"{type(exc).__name__}: {exc}")
            time.sleep(2 * (attempt + 1))
            continue
        dt = time.perf_counter() - t0
        if r.status_code >= 400:
            last = (dt, f"HTTP {r.status_code}")
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            return None, dt, last[1]
        data = r.json()
        return ((((data.get("choices") or [{}])[0].get("message") or {})
                 .get("content") or "")), dt, None
    return None, (last[0] if last else 0.0), (last[1] if last else "unknown")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--models", required=True)
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--max-tokens", type=int, default=6000)
    ap.add_argument("--show", action="store_true",
                    help="print each declared solution")
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    import db
    db.configure(args.db)
    import llm_quality
    import prompts
    import schemas

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    # Production sends the contract with the paragraphs whose subject this
    # beat does not carry removed (prompts.character_prompt). Sending the
    # whole document here measured a configuration that does not ship --
    # and these payloads are deliberately sparse, so the gap is widest
    # exactly where this harness is pointed.
    system = None  # built per scenario, from that scenario's own payload

    print(f"{len(SCENARIOS)} problems x {args.trials} trials — "
          f"each has a blocked obvious path and an unsignposted way through\n")
    table = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"  {model}", flush=True)
        solved = blocked = novel = attempts = bad = 0
        times = []
        for sc in SCENARIOS:
            payload_obj = _payload(sc)
            system = prompts.character_prompt(payload_obj)
            payload = json.dumps(payload_obj, ensure_ascii=False)
            marks = []
            for _ in range(args.trials):
                text, dt, err = _post(prov, model, system, payload,
                                      args.timeout, args.max_tokens)
                times.append(dt)
                if err:
                    bad += 1
                    continue
                try:
                    parsed = llm_quality.strict_json_parse(text)
                except Exception:
                    bad += 1
                    continue
                report = schemas.validate_llm_output_strict("character", parsed)
                if not report.valid:
                    bad += 1
                    continue
                did = _conduct(report.output or parsed)
                attempts += 1
                hit_valid = bool(sc["valid"].search(did))
                hit_block = bool(sc["blocked"].search(did))
                hit_novel = bool(sc["novel"].search(did))
                if hit_valid:
                    solved += 1
                    marks.append("solved")
                elif hit_novel:
                    novel += 1
                    marks.append("novel")
                elif hit_block:
                    blocked += 1
                    marks.append("BLOCKED")
                else:
                    marks.append("—")
                if hit_novel and hit_valid:
                    novel += 1
                if args.show and did:
                    print(f"          {did[:120]}", flush=True)
            print(f"      {', '.join(marks) or 'no usable reply':<22} "
                  f"{sc['name']}", flush=True)
        rate = solved / attempts if attempts else 0
        table.append({"model": model, "solved": solved, "attempts": attempts,
                      "blocked": blocked, "novel": novel, "bad": bad,
                      "rate": rate,
                      "med": statistics.median(times) if times else 0})
        print(f"      -> solved {solved}/{attempts}, "
              f"took the blocked path {blocked}, novel routes {novel}, "
              f"{bad} unusable\n", flush=True)

    print("=== problem solving ===")
    print("  BLOCKED = took the obvious path the payload says cannot work")
    table.sort(key=lambda r: (-r["rate"], r["blocked"], r["med"]))
    for r in table:
        print(f"  {r['solved']:>2}/{r['attempts']:<3} solved   "
              f"blocked {r['blocked']}   novel {r['novel']}   "
              f"{r['bad']} unusable   {r['med']:>5.1f}s   {r['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
