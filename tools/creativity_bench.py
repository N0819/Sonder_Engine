#!/usr/bin/env python3
"""Does the model invent, or does it converge on one beat and stay there.

Creativity is the axis everything else in this directory refuses to measure,
and the usual dodge is to score it by reading the output and liking it. That is
not a benchmark. But this engine already holds two opinions about what
repetition IS, both deterministic and both load-bearing in production:

  * `agents.character._self_line_refrain` -- the SHAPE a character's lines keep
    reusing. Written because one character opened nine consecutive lines the
    same way with genuinely fresh content in between every time. Each line
    passed the content test; the page read as a stuck record.
  * `theory_of_mind.claim_similarity` -- how alike two declared moves are, the
    same function `_first_repeated_move` uses to catch a character making the
    same offer twice in different words.

So creativity is scored here as the engine defines its own failure: sample the
SAME beat K times and ask how far apart the answers land. A model that returns
near-identical moves every time will, in play, be the character who always does
the same thing -- which is precisely the complaint those two functions exist to
catch.

Three numbers per model, all lower-is-worse except convergence:

  divergence   1 - mean pairwise claim_similarity across the K selected moves.
               0.0 means it wrote the same move K times.
  vocabulary   distinct words / total words across all K replies.
  specificity  proper nouns and concrete sensory nouns per 100 words -- the
               difference between "the room feels tense" and "the tallow
               guttered when the door moved".

And one hard flag: `refrain`, from the engine's own detector. A model whose K
independent replies share an opening or closing skeleton is templating, and
that is a defect rather than a low score.

    python3 tools/creativity_bench.py --models a,b --samples 5
    python3 tools/creativity_bench.py --step narrator --models a,b

Run it alone; the rate limit is per account.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCENE = {
    "rooms": {"tap": {"name": "Tap Room",
                      "desc": "A low tap room, rain on the shutters, one "
                              "lamp burning at the near end of the bar.",
                      "adjacent": []}},
    "positions": {"Vessel": "tap", "Wren": "tap"},
    "location": "A drovers' inn on the coast road, late.",
}

# A beat with no single right answer and plenty of room: someone the character
# has reason to distrust has just offered them something. What a mind DOES here
# is underdetermined, which is exactly the condition creativity is measured in.
BEAT = ("Wren slides a folded paper across the bar toward you without looking "
        "up. \"Before you say no,\" she says, \"read the second line.\"")

OBSERVATIONS = [
    "Wren slides a folded paper across the bar toward you.",
    "Wren does not look up as she does it.",
    "Wren says: \"Before you say no, read the second line.\"",
]

_STOP = frozenset("""a an the and or but of to in on at by for with from as is
are was were be been it its this that these those you your i my me he she they
her his their them not no so if then than there here what which who whom when
while into over under out up down off about""".split())

# Concrete sensory nouns -- the vocabulary of a scene somebody is actually IN.
_CONCRETE = re.compile(
    r"\b(rain|lamp|wick|tallow|smoke|salt|iron|brass|wool|leather|glass|"
    r"ash|grease|thumb|knuckle|wrist|collar|hem|stool|shutter|hinge|nail|"
    r"cork|rim|grain|splinter|draught|drip|creak|scrape|hiss|breath)\w*\b",
    re.I)


def _payload(step):
    if step == "narrator":
        return {"player_view": BEAT, "scene": SCENE, "variant_seed": "creative"}
    return {
        "self": {
            "name": "Vessel",
            "psychology": {
                "drive": {"essence": "to owe nobody anything",
                          "expression": "pays first, refuses favours",
                          "taboo": "will not take what she cannot return"},
                "traits": [{"name": "guarded"}, {"name": "dryly funny"}],
                "capacity": "ordinary",
            },
            "attention": {"wants": 3, "intentions": 4, "band": "ordinary",
                          "means": "the human middle"},
            "intentions": [], "steering_intention_ids": [], "projects": [],
            "body_state": {"mood": "wary", "valence": -0.2, "arousal": 0.45},
        },
        "perception": {
            "view": BEAT,
            "observations": [{"observation_id": f"current:Vessel:{i}",
                              "observed": {"text": t}}
                             for i, t in enumerate(OBSERVATIONS)],
            "current_room": "Tap Room",
        },
        "memory": {"recent_episodes": [], "recalled_old_memories": []},
        "relationships": {}, "mind_models": [], "active_hypotheses": [],
        "decision": {"dialogue_mode": True,
                     "speech_budget": {"suggested_lines": 1, "hard_max": 2,
                                       "may_stay_silent": False}},
        "variant_seed": "creative",
    }


def _move_of(parsed, step):
    """The one thing this reply committed to, for similarity scoring."""
    if step == "narrator":
        return str(parsed.get("prose") or "")
    for cand in (parsed.get("response_candidates") or []):
        if isinstance(cand, dict) and cand.get("selected"):
            return str(cand.get("response") or "")
    bits = []
    for e in (parsed.get("sequence") or []):
        if isinstance(e, dict):
            bits.append(str(e.get("text") or e.get("attempt") or ""))
    return " ".join(b for b in bits if b)


def _lines_of(parsed, step):
    if step == "narrator":
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+",
                                            str(parsed.get("prose") or ""))
                if s.strip()][:6]
    out = []
    for e in (parsed.get("sequence") or []):
        if isinstance(e, dict) and e.get("type") == "speech" and e.get("text"):
            out.append(str(e["text"]))
    return out


def _post(prov, model, system, user, timeout, max_tokens, seed_note):
    import providers
    t0 = time.perf_counter()
    r = providers._session().post(
        prov["base_url"].rstrip("/") + "/chat/completions",
        headers=providers._headers(prov),
        json={"model": model,
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
              # Production temperature for these roles, not a creativity dial:
              # the question is what the model does in the engine, not what it
              # can do if pushed.
              "temperature": 0.8, "max_tokens": max_tokens},
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
    ap.add_argument("--step", default="character",
                    choices=("character", "narrator"))
    ap.add_argument("--models", required=True)
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--max-tokens", type=int, default=6000)
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    import db
    db.configure(args.db)
    import llm_quality
    import prompts
    import schemas
    from theory_of_mind import claim_similarity
    from agents.character import _self_line_refrain

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    system = prompts.DEFAULT_PROMPTS[args.step]
    payload = json.dumps(_payload(args.step), ensure_ascii=False)

    print(f"step {args.step}   same beat x{args.samples}, temperature 0.8\n")
    table = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"  {model}", flush=True)
        moves, words, lines, times, bad = [], [], [], [], 0
        for _ in range(args.samples):
            text, dt, err = _post(prov, model, system, payload,
                                  args.timeout, args.max_tokens, None)
            times.append(dt)
            if err:
                bad += 1
                continue
            try:
                parsed = llm_quality.strict_json_parse(text)
            except Exception:
                bad += 1
                continue
            report = schemas.validate_llm_output_strict(args.step, parsed)
            if not report.valid:
                bad += 1
                continue
            out = report.output or parsed
            mv = _move_of(out, args.step)
            if mv:
                moves.append(mv)
            lines.extend(_lines_of(out, args.step))
            words.extend(re.findall(r"[a-z']+", json.dumps(out).lower()))

        if len(moves) < 2:
            print(f"      unusable ({bad} bad)\n", flush=True)
            table.append({"model": model, "div": None, "bad": bad,
                          "med": statistics.median(times) if times else 0})
            continue

        sims = [claim_similarity(a, b) for a, b in itertools.combinations(moves, 2)]
        divergence = 1.0 - (statistics.fmean(sims) if sims else 0.0)
        content = [w for w in words if w not in _STOP and len(w) > 2]
        vocab = len(set(content)) / max(1, len(content))
        blob = " ".join(moves + lines)
        n_words = max(1, len(re.findall(r"[A-Za-z']+", blob)))
        proper = len(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", blob))
        concrete = len(_CONCRETE.findall(blob))
        specificity = (proper + concrete) / n_words * 100
        refrain = _self_line_refrain(lines) if len(lines) >= 3 else None

        print(f"      divergence {divergence:.2f}   vocabulary {vocab:.2f}   "
              f"specificity {specificity:.1f}/100w"
              + (f"   REFRAIN {refrain}" if refrain else ""), flush=True)
        for m in moves[:2]:
            print(f"        · {m[:104]}", flush=True)
        print("", flush=True)
        table.append({"model": model, "div": divergence, "vocab": vocab,
                      "spec": specificity, "refrain": bool(refrain),
                      "bad": bad, "med": statistics.median(times)})

    print("=== invention (same beat, K samples) ===")
    print("  divergence 0.00 = wrote the same move every time; "
          "REFRAIN = templating, a defect not a score")
    usable = [r for r in table if r.get("div") is not None]
    usable.sort(key=lambda r: (r["refrain"], -r["div"]))
    for r in usable:
        flag = "  <-- TEMPLATES" if r["refrain"] else ""
        print(f"  div {r['div']:.2f}   vocab {r['vocab']:.2f}   "
              f"spec {r['spec']:>4.1f}   {r['bad']} bad   "
              f"{r['med']:>5.1f}s   {r['model']}{flag}")
    for r in table:
        if r.get("div") is None:
            print(f"  ----                                  {r['bad']} bad"
                  f"   {r['med']:>5.1f}s   {r['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
