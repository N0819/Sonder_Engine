#!/usr/bin/env python3
"""Does relocating one name recover a 13,889-token cacheable prefix.

READ-ONLY. Sends API calls and reads `cached_tokens` off the response. Touches
no prompt, no setting and no database, so a negative result costs nothing but
the calls.

THE CLAIM UNDER TEST. `prompts.DEFAULT_PROMPTS["character"]` opens

    "You are the decision process of {name}, not a narrator..."

with `{name}` at byte 32 of a 55,558-character prompt. A provider caches a
PREFIX -- the hit runs from the start of the message up to the first byte that
differs -- so two characters in the same turn share only the 8 tokens before
the name. The other ~13,880 tokens of identical contract are re-ingested cold,
per character, per beat.

THE DECISIVE COMPARISON is not one call repeated. It is two DIFFERENT
characters back to back, because that is what actually happens in a turn and it
is the case the current layout cannot cache. Each arm therefore calls with
`Elyndra` and then `Hinami`, and reports what the second call cached:

  as-is       {name} at byte 32, single system message  -- expected ~0
  relocated   {name} clause moved to the END of the prompt
  split       prompt untouched; sent as TWO messages, invariant contract
              first, name line and payload second

`split` is the interesting arm: it changes packaging rather than wording, so
the model reads the same tokens in the same order and no high-salience opening
line gets moved. If it caches as well as `relocated`, the win is available
without editing a 55kB prompt anybody has tuned.

    python3 tools/cache_probe.py
    python3 tools/cache_probe.py --model moonshotai/kimi-k2.6

Run it alone -- the rate limit is per account, and a 429 mid-arm reads as a
cache miss.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NAMES = ("Elyndra", "Hinami")


def _payload(name):
    """Small on purpose. The question is what the PROMPT caches; a big payload
    would only add uncacheable tail and blur the reading."""
    return {
        "self": {"name": name,
                 "psychology": {"drive": {"essence": "to be owed nothing"}}},
        "perception": {"view": "Rain on the shutters. The lamp gutters.",
                       "observations": [], "current_room": "Tap Room"},
        "memory": {"recent_episodes": [], "recalled_old_memories": []},
        "relationships": {}, "mind_models": [], "active_hypotheses": [],
        "decision": {"dialogue_mode": True,
                     "speech_budget": {"suggested_lines": 1, "hard_max": 1,
                                       "may_stay_silent": True}},
        "variant_seed": "cacheprobe",
    }


def _arms(base):
    """(label, build) where build(name) -> list of chat messages."""
    head, tail = base[:len(base) // 1], ""

    def as_is(name):
        return [{"role": "system",
                 "content": base.replace("{name}", name) + "\n\n"
                 + json.dumps(_payload(name), ensure_ascii=False)}]

    def relocated(name):
        # The one clause carrying {name}, moved to the very end. Everything
        # before it becomes byte-identical across characters.
        stripped = base.replace(
            "You are the decision process of {name}, not a narrator",
            "You are the decision process of the character named at the end of "
            "this contract, not a narrator", 1)
        stripped = stripped.replace("{name}", "that character")
        return [{"role": "system",
                 "content": stripped
                 + f"\n\nYOU ARE: {name}. Everything above describes how you "
                   f"decide; this line says who is deciding.\n\n"
                 + json.dumps(_payload(name), ensure_ascii=False)}]

    def split(name):
        # Wording untouched. Only the message boundary moves.
        stripped = base.replace(
            "You are the decision process of {name}, not a narrator",
            "You are the decision process of the character named in the next "
            "message, not a narrator", 1)
        stripped = stripped.replace("{name}", "that character")
        return [{"role": "system", "content": stripped},
                {"role": "system",
                 "content": f"YOU ARE: {name}.\n\n"
                 + json.dumps(_payload(name), ensure_ascii=False)}]

    return [("as-is", as_is), ("relocated", relocated), ("split", split)]


def _call(prov, model, messages, timeout):
    from llm import providers
    t0 = time.perf_counter()
    r = providers._session().post(
        prov["base_url"].rstrip("/") + "/chat/completions",
        headers=providers._headers(prov),
        json={"model": model, "messages": messages,
              "temperature": 0.3, "max_tokens": 300},
        timeout=timeout)
    dt = time.perf_counter() - t0
    if r.status_code >= 400:
        return None, dt, f"HTTP {r.status_code} {(r.text or '')[:80]}"
    usage = (r.json() or {}).get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    cached = (usage.get("cached_tokens")
              or details.get("cached_tokens")
              or usage.get("prompt_cache_hit_tokens") or 0)
    return {"prompt": usage.get("prompt_tokens") or 0,
            "cached": cached,
            "out": usage.get("completion_tokens") or 0}, dt, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--model", default="Qwen/Qwen3.6-35B-A3B")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--gap", type=float, default=2.0,
                    help="seconds between the two calls in an arm")
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    from core import db
    db.configure(args.db)
    from llm import prompts

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    base = prompts.DEFAULT_PROMPTS["character"]
    print(f"model {args.model}   character prompt {len(base):,} chars "
          f"(~{len(base)//4:,} tok)")
    print(f"each arm: call as {NAMES[0]}, then as {NAMES[1]} -- "
          f"the second call is the measurement\n")

    results = []
    for label, build in _arms(base):
        print(f"  {label}", flush=True)
        second = None
        for i, name in enumerate(NAMES):
            got, dt, err = _call(prov, args.model, build(name), args.timeout)
            if err:
                print(f"      {name:<9} {err}", flush=True)
                continue
            share = got["cached"] / got["prompt"] * 100 if got["prompt"] else 0
            print(f"      {name:<9} prompt {got['prompt']:>6,}  "
                  f"cached {got['cached']:>6,}  ({share:>4.0f}%)  {dt:>5.1f}s",
                  flush=True)
            if i == 1:
                second = (got, dt)
            time.sleep(args.gap)
        results.append((label, second))
        print("", flush=True)

    print("=== second call of each arm (the one that matters) ===")
    for label, second in results:
        if not second:
            print(f"  {label:<11} no usable reply")
            continue
        got, dt = second
        share = got["cached"] / got["prompt"] * 100 if got["prompt"] else 0
        print(f"  {label:<11} cached {got['cached']:>6,} of {got['prompt']:>6,}"
              f"  ({share:>4.0f}%)   {dt:>5.1f}s")
    print("\nA second character caching ~0 means the prefix breaks at the name.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
