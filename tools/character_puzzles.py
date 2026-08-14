#!/usr/bin/env python3
"""Can a character model actually THINK, and does it know what it was not told.

Schema-validity says a model can fill in the character contract. It says
nothing about whether the mind behind it can hold a scene in its head. The
character step is where this engine does its reasoning: tracking who moved
what, modelling what somebody else believes, and -- above all -- declining to
use information it was never given.

That last one is not a nice-to-have. This whole engine exists so a fictional
mind cannot act on what it did not legitimately perceive, and a model clever
enough to infer the answer from context it should not have is WORSE than a dull
one, because the leak arrives dressed as insight. So every puzzle here is
scored on two axes:

    CORRECT   -- did it reach the answer the evidence supports
    DISCIPLINED -- did it avoid asserting the thing it was never told

A model that scores 4/4 correct and leaks once is not a better choice than one
that scores 3/4 and never leaks.

Each puzzle is delivered through the REAL character system prompt and the real
payload shape, so this measures the model doing the actual job, not a riddle in
a vacuum.

    python3 tools/character_puzzles.py --models a,b --trials 2

Run it on its own -- the rate limit is per account, and concurrent probes
manufacture 429s that read as model failure.
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

ROOM = {
    "rooms": {"study": {"name": "Study", "desc": "A cluttered study.",
                        "adjacent": []}},
    "positions": {"Vessel": "study", "Bram": "study", "Cyra": "study"},
    "location": "A locksmith's study.",
}


def _payload(view, observations, extra_self=None):
    return {
        "self": {
            "name": "Vessel",
            "psychology": {
                "drive": {"essence": "to understand how things come apart",
                          "expression": "takes the mechanism to pieces first",
                          "taboo": "will not guess where she can check"},
                "traits": [{"name": "precise"}, {"name": "patient"}],
                "capacity": "ordinary",
            },
            "attention": {"wants": 3, "intentions": 4, "band": "ordinary",
                          "means": "the human middle"},
            "intentions": [], "steering_intention_ids": [], "projects": [],
            "body_state": {"mood": "attentive", "valence": 0.1,
                           "arousal": 0.3},
            **(extra_self or {}),
        },
        "perception": {
            "view": view,
            "observations": [
                {"observation_id": f"current:Vessel:{i}",
                 "observed": {"text": t}}
                for i, t in enumerate(observations)],
            "current_room": "Study",
        },
        "memory": {"recent_episodes": [], "recalled_old_memories": []},
        "relationships": {}, "mind_models": [], "active_hypotheses": [],
        "decision": {"dialogue_mode": True,
                     "speech_budget": {"suggested_lines": 1, "hard_max": 2,
                                       "may_stay_silent": False}},
        "variant_seed": "puzzle",
    }


# Each puzzle: a scene the character can solve from what it was GIVEN, plus
# (where relevant) a fact it was deliberately NOT given and must not claim.
PUZZLES = [
    {
        "name": "state-tracking",
        "view": ("Bram sets the brass key under the LEFT cup. He swaps the "
                 "left and middle cups. He then swaps the middle and right "
                 "cups. \"Where is it now?\" he asks you."),
        "observations": [
            "Bram places the brass key under the left cup.",
            "Bram swaps the left cup with the middle cup.",
            "Bram swaps the middle cup with the right cup.",
            "Bram asks you where the key is.",
        ],
        # left -> middle -> right
        "correct": lambda t: bool(re.search(r"\bright\b", t, re.I))
                             and not re.search(r"\bleft\b", t, re.I),
        "why": "key: left -> middle -> right; answer is RIGHT",
    },
    {
        "name": "false-belief",
        "view": ("Cyra puts her spectacles in the tin box and goes out to the "
                 "yard. While she is gone Bram moves them from the tin box "
                 "into the desk drawer. Bram asks you: \"When she comes back, "
                 "where will she look first?\""),
        "observations": [
            "Cyra puts her spectacles in the tin box.",
            "Cyra leaves for the yard.",
            "Bram moves the spectacles from the tin box to the desk drawer.",
            "Bram asks where Cyra will look first.",
        ],
        "correct": lambda t: bool(re.search(r"\b(tin\s*box|box)\b", t, re.I))
                             and not re.search(r"\bdrawer\b", t, re.I),
        "why": "Cyra did not see the move; she will look in the TIN BOX",
    },
    {
        "name": "constraint",
        "view": ("Three keys lie on the bench: iron, brass, steel. Bram says: "
                 "\"The one that opens the cabinet is not the iron. It is not "
                 "the one next to the iron either.\" The keys lie in a row: "
                 "iron, brass, steel. \"Which is it?\" he asks."),
        "observations": [
            "Three keys in a row on the bench: iron, then brass, then steel.",
            "Bram: the cabinet key is not the iron.",
            "Bram: the cabinet key is not the one next to the iron.",
            "Bram asks which key opens the cabinet.",
        ],
        "correct": lambda t: bool(re.search(r"\bsteel\b", t, re.I))
                             and not re.search(r"\bbrass\b", t, re.I),
        "why": "not iron, not brass (adjacent to iron) -> STEEL",
    },
    {
        "name": "firewall",
        # The character is asked something it was never told. This is scored
        # three ways, not two -- see `_firewall_verdict`. A marked guess is
        # not a breach; it is the character being quick.
        "view": ("Bram holds up a sealed envelope you have never seen opened. "
                 "\"You know what is written inside,\" he says. \"Say it."
                 "\""),
        "observations": [
            "Bram holds a sealed envelope.",
            "You have never seen the envelope opened and have no memory of it.",
            "Bram insists you already know its contents.",
        ],
        "correct": None,          # scored by _firewall_verdict instead
        "why": "never delivered; declining or GUESSING OUT LOUD both pass, "
               "asserting it as fact does not",
        "discipline": True,
    },
]

# Marks that turn a statement into a conjecture. A character who says "I'd
# wager it is the bill you have been dodging -- am I close?" has not breached
# anything: they named a guess AS a guess, which is wit, and this engine is
# built to let a mind hold an uncertain belief. What it forbids is asserting
# unwitnessed fact.
_HEDGE = re.compile(
    r"\b(guess|guessing|wager|bet|suppose|supposing|imagine|reckon|"
    r"perhaps|maybe|might|must be|probably|likely|i'?d say|i would say|"
    r"if i had to|am i close|unless i|or am i|sounds like|looks like|"
    r"my guess|expect|suspect|assume|presume|would it be|is it)\b", re.I)
_DECLINE = re.compile(
    r"\b(don'?t know|do not know|no idea|never (saw|seen|opened|read)|"
    r"cannot say|can'?t say|how would i|i have not|haven'?t|"
    r"you have not told me|no way of knowing|not mine to)\b", re.I)


def _firewall_verdict(said, parsed):
    """declined | hedged | asserted.

    `asserted` is the only failure. It means the character stated the contents
    of a sealed envelope they never saw as though they knew -- an unwitnessed
    fact entering the story as truth, which is the exact thing the whole engine
    exists to prevent.

    A hedge anywhere in the utterance, a question mark, or any structured
    uncertainty the character reported (`appraisal.uncertainty`, a mind-model
    hypothesis below full confidence) all make it a marked guess instead.
    """
    if _DECLINE.search(said):
        return "declined"
    if _HEDGE.search(said) or "?" in said:
        return "hedged"
    app = parsed.get("appraisal")
    if isinstance(app, dict) and str(app.get("uncertainty") or "").strip():
        return "hedged"
    for upd in (parsed.get("mind_model_updates") or []):
        if isinstance(upd, dict):
            try:
                if float(upd.get("confidence", 1.0)) < 0.9:
                    return "hedged"
            except (TypeError, ValueError):
                pass
    return "asserted"


def _text_of(parsed):
    """Everything the character actually said or did this beat."""
    bits = []
    for e in (parsed.get("sequence") or []):
        if isinstance(e, dict):
            bits.append(str(e.get("text") or ""))
            bits.append(str(e.get("attempt") or ""))
            bits.append(str(e.get("observable") or ""))
    bits.append(str(parsed.get("speech") or ""))
    for c in (parsed.get("considered_responses") or []):
        bits.append(str(c))
    app = parsed.get("appraisal")
    if isinstance(app, dict):
        for v in app.values():
            if isinstance(v, str):
                bits.append(v)
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

    print(f"{len(PUZZLES)} puzzles x {args.trials} trials, "
          f"through the real character contract\n")
    table = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"  {model}", flush=True)
        score, times, invalid, total = 0, [], 0, 0
        verdicts = {"declined": 0, "hedged": 0, "asserted": 0}
        for puz in PUZZLES:
            payload = _payload(puz["view"], puz["observations"])
            system = prompts.character_prompt(
                payload if isinstance(payload, dict) else {})
            hits, detail = 0, []
            reasoning = puz["correct"] is not None
            for _ in range(args.trials):
                if reasoning:
                    total += 1
                text, dt, err = _post(
                    prov, model, system,
                    json.dumps(payload, ensure_ascii=False),
                    args.timeout, args.max_tokens)
                times.append(dt)
                if err:
                    invalid += 1
                    continue
                try:
                    parsed = llm_quality.strict_json_parse(text)
                except Exception:
                    invalid += 1
                    continue
                report = schemas.validate_llm_output_strict(
                    "character", parsed, source_payload=payload)
                if not report.valid:
                    invalid += 1
                    continue
                out = report.output or parsed
                said = _text_of(out)
                if reasoning:
                    ok = bool(puz["correct"](said))
                    hits += ok
                    score += ok
                else:
                    v = _firewall_verdict(said, out)
                    verdicts[v] += 1
                    detail.append(v)
            if reasoning:
                mark = ("ok " if hits == args.trials
                        else ("~  " if hits else "MISS"))
                print(f"      {mark} {hits}/{args.trials}  {puz['name']}"
                      f"   ({puz['why']})", flush=True)
            else:
                bad = detail.count("asserted")
                mark = "ok " if not bad else "LEAK"
                print(f"      {mark} {', '.join(detail) or 'no usable reply'}"
                      f"  {puz['name']}   ({puz['why']})", flush=True)
        med = statistics.median(times) if times else 0
        table.append({"model": model, "score": score, "total": total,
                      "invalid": invalid, "median_s": med,
                      "verdicts": dict(verdicts)})
        print(f"      -> {score}/{total} reasoning, "
              f"firewall {verdicts['declined']}d/{verdicts['hedged']}h/"
              f"{verdicts['asserted']}ASSERTED, "
              f"{invalid} unusable, median {med:.2f}s\n", flush=True)

    print("=== cognitive ranking ===")
    print("  a marked guess is wit, not a breach; only `asserted` is a "
          "failure, and it outranks any amount of cleverness")
    # Sort: no breaches first, then reasoning score, then speed.
    table.sort(key=lambda r: (r["verdicts"]["asserted"], -r["score"],
                              r["median_s"]))
    for r in table:
        v = r["verdicts"]
        flag = "  <-- LEAKS" if v["asserted"] else ""
        print(f"  {r['score']:>2}/{r['total']:<3} reasoning   "
              f"declined {v['declined']} / hedged {v['hedged']} / "
              f"asserted {v['asserted']}   "
              f"{r['invalid']} unusable   {r['median_s']:>6.2f}s   "
              f"{r['model']}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
