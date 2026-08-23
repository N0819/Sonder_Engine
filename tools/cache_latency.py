#!/usr/bin/env python3
"""Does a cache HIT actually make the call faster.

`tools/cache_probe.py` answers whether a prefix caches. It does not answer
whether that helps, and those turned out to be different questions: on
`gemma-4-26b-a4b-it` relocating one name took a call from 33.1s to 4.0s, while
on `kimi-k2.6` the 98%-cached arm was 6.5x SLOWER than the uncached one. A
cache percentage is not a latency measurement and must not be reported as one.

A plausible reason for the inversion is that a cached request has to route to
whichever backend instance holds the KV cache, and that instance may be busier
than free routing -- you win on prefill and lose on queueing. This tool does
not test that theory. It measures the thing that actually matters:

    call 1  cold  (nothing cached yet)
    calls 2..N    warm (prefix should hit)

Same model, same prompt layout, same bounded output, back to back. The gap
between call 1 and the median of the rest is the cache's real worth, and the
`cached` column shows whether a hit even occurred on the calls being compared.

    python3 tools/cache_latency.py --models a,b --layout relocated --calls 5

Run it alone. A 429 or a busy shared endpoint mid-run reads as a cache miss.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NAMES = ("Elyndra", "Hinami", "Tamamo", "Wren", "Vessel", "Bram")


def _payload(name):
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
        "variant_seed": "cachelat",
    }


def build(base, layout, name):
    if layout == "as-is":
        return [{"role": "system",
                 "content": base.replace("{name}", name) + "\n\n"
                 + json.dumps(_payload(name), ensure_ascii=False)}]
    stripped = base.replace(
        "You are the decision process of {name}, not a narrator",
        "You are the decision process of the character named below, not a "
        "narrator", 1).replace("{name}", "that character")
    tail = (f"\n\nYOU ARE: {name}.\n\n"
            + json.dumps(_payload(name), ensure_ascii=False))
    if layout == "relocated":
        return [{"role": "system", "content": stripped + tail}]
    return [{"role": "system", "content": stripped},
            {"role": "system", "content": tail.strip()}]


def _call(prov, model, messages, timeout, max_tokens, affinity=False):
    from llm import providers
    body = {"model": model, "messages": messages,
            # Fixed and small, so generation cannot confound the reading.
            "temperature": 0.0, "max_tokens": max_tokens}
    if affinity:
        # Same content-free role hint production uses when this provider is
        # opted into cache_affinity_allow.
        body["user"] = "sonder:character_major"
    t0 = time.perf_counter()
    r = providers._session().post(
        prov["base_url"].rstrip("/") + "/chat/completions",
        headers=providers._headers(prov),
        json=body,
        timeout=timeout)
    dt = time.perf_counter() - t0
    if r.status_code >= 400:
        return None, dt, f"HTTP {r.status_code}"
    usage = (r.json() or {}).get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    cached = (usage.get("cached_tokens") or details.get("cached_tokens")
              or usage.get("prompt_cache_hit_tokens") or 0)
    return {"prompt": usage.get("prompt_tokens") or 0, "cached": cached,
            "out": usage.get("completion_tokens") or 0}, dt, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--models", required=True)
    ap.add_argument("--layout", default="relocated",
                    choices=("as-is", "relocated", "split"))
    ap.add_argument("--calls", type=int, default=5)
    ap.add_argument("--max-tokens", type=int, default=120)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--gap", type=float, default=1.5)
    ap.add_argument("--affinity", action="store_true",
                    help="send production's content-free character role hint")
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    from core import db
    db.configure(args.db)
    from llm import prompts

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    base = prompts.DEFAULT_PROMPTS["character"]
    print(f"layout {args.layout}   {args.calls} sequential calls   "
          f"max_tokens {args.max_tokens}\n")

    table = []
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        print(f"  {model}", flush=True)
        times, hits = [], []
        for i in range(args.calls):
            name = NAMES[i % len(NAMES)]
            got, dt, err = _call(prov, model, build(base, args.layout, name),
                                 args.timeout, args.max_tokens, args.affinity)
            if err:
                print(f"      {i+1}. {err}", flush=True)
                times.append(None)
                hits.append(0)
                time.sleep(args.gap)
                continue
            share = got["cached"] / got["prompt"] * 100 if got["prompt"] else 0
            tag = "cold" if i == 0 else "warm"
            print(f"      {i+1}. {tag:<4} {dt:>6.2f}s   cached "
                  f"{got['cached']:>6,} ({share:>3.0f}%)   "
                  f"{got['out']:>4} out", flush=True)
            times.append(dt)
            hits.append(share)
            time.sleep(args.gap)
        warm = [t for t in times[1:] if t is not None]
        cold = times[0]
        warm_hits = [h for h in hits[1:] if h]
        if cold and warm:
            med = statistics.median(warm)
            delta = (cold - med) / cold * 100
            verdict = ("FASTER" if med < cold * 0.9 else
                       "SLOWER" if med > cold * 1.1 else "same")
            table.append((model, cold, med, delta, verdict,
                          statistics.mean(warm_hits) if warm_hits else 0))
            print(f"      -> cold {cold:.2f}s, warm median {med:.2f}s "
                  f"({delta:+.0f}%)  {verdict}\n", flush=True)
        else:
            print("      -> unusable\n", flush=True)

    print("=== does a cache hit make it faster ===")
    print(f"  {'cold':>7} {'warm':>7} {'change':>8} {'hit%':>6}  model")
    for model, cold, med, delta, verdict, hit in sorted(table, key=lambda r: r[2]):
        print(f"  {cold:>7.2f} {med:>7.2f} {delta:>7.0f}% {hit:>5.0f}%  "
              f"{model}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
