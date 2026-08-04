#!/usr/bin/env python3
"""How fast is a model at the work THIS engine actually asks of it.

"Fastest" is not tokens per second on a toy prompt. Every role in this pipeline
sends a very large system prompt (the character contract alone is 55kB), a
structured payload, and demands parseable JSON back. A model that streams
quickly and then returns prose where a schema was required costs a retry, and a
retry is slower than any model in the catalogue.

So each candidate is scored on three things, in this order:

  1. does it come back at all, and with valid JSON of the requested shape
  2. total wall clock for a realistic call -- prompt ingestion included, since
     a 55kB system prompt is most of the latency on a short reply
  3. output tokens per second, which only matters once 1 and 2 hold

Prompt ingestion is measured separately from generation by running each model
twice at different output lengths and solving for the two terms. That matters
here more than in most benchmarks: this engine's calls are enormously
prompt-heavy, so a model with a slow prefill and a fast decoder can lose to one
that looks worse on any tokens-per-second chart.

    python3 tools/model_bench.py --provider 1 --subscriber-only
    python3 tools/model_bench.py --models a,b,c --trials 3 --json out.json

Concurrency defaults to 1 because a shared endpoint under parallel load
measures queueing, not the model.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A payload shaped like the smallest real structured call in the pipeline:
# a spatial refresh. Short output, so the timing is dominated by prompt
# ingestion -- which is what this engine's cost actually looks like.
SHORT_SYSTEM = (
    "You maintain the spatial state of an interactive fiction scene. "
    "Reply with ONE JSON object and nothing else, matching exactly:\n"
    '{"room":"<id>","occupants":["<name>",...],"exits":[{"to":"<id>",'
    '"barrier":"open|closed_door|wall|window|bars|membrane"}],'
    '"notable":["<short phrase>",...]}\n'
    "No prose, no markdown fence, no commentary."
)
SHORT_USER = json.dumps({
    "scene": {
        "rooms": {
            "inn_room": {"name": "Inn Room",
                         "desc": "A modest second-floor room with worn timber "
                                 "walls, a hearth burned to embers, a wide bed "
                                 "and a writing desk. A casement window is shut "
                                 "but unlatched.",
                         "adjacent": [{"to": "inn_hallway",
                                       "barrier": "closed_door"}]},
            "inn_hallway": {"name": "Hallway", "desc": "A narrow landing.",
                            "adjacent": [{"to": "inn_room",
                                          "barrier": "closed_door"}]},
        },
        "positions": {"Wren": "inn_room", "Vessel": "inn_room"},
    },
    "beat": "Wren crosses to the window and tries the latch.",
}, ensure_ascii=False)

# The same call with a long generation, so the per-token cost separates from
# the fixed cost of reading the prompt.
LONG_SYSTEM = (
    "You are the narrator of an interactive fiction engine. Reply with ONE "
    'JSON object: {"prose":"<text>"} and nothing else. No markdown fence.'
)
LONG_USER = (
    "Render this beat as continuous second-person prose of roughly 400 words. "
    "The player is in a mountain waystation inn room at night; the hearth has "
    "burned to embers, a cold draught works at an unlatched casement, and "
    "someone else in the room has just gone very quiet. Do not invent dialogue. "
    "Return only the JSON object."
)

SHORT_KEYS = ("room", "occupants", "exits")


def _post(prov, model, system, user, max_tokens, timeout):
    import providers
    base = prov["base_url"].rstrip("/")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    start = time.perf_counter()
    r = providers._session().post(base + "/chat/completions",
                                  headers=providers._headers(prov),
                                  json=body, timeout=timeout)
    elapsed = time.perf_counter() - start
    if r.status_code >= 400:
        return {"ok": False, "seconds": elapsed,
                "error": f"{r.status_code} {(r.text or '')[:160]}"}
    data = r.json()
    choice = (data.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content") or "").strip()
    usage = data.get("usage") or {}
    return {
        "ok": True,
        "seconds": elapsed,
        "text": text,
        "out_tokens": usage.get("completion_tokens"),
        "in_tokens": usage.get("prompt_tokens"),
        "reasoning": (usage.get("completion_tokens_details") or {}).get(
            "reasoning_tokens"),
    }


def _extract_json(text):
    """The same tolerance the engine itself applies: a fenced or trailing-comma
    object still counts as a model that answered in JSON, because the engine
    would have recovered it too."""
    import re
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", match.group(0)))
    except (ValueError, TypeError):
        return None


def bench_one(prov, model, trials, timeout):
    short, long_ = [], []
    verdict = {"model": model, "schema_ok": 0, "schema_tried": 0,
               "errors": [], "reasoning_tokens": 0}
    for _ in range(trials):
        r = _post(prov, model, SHORT_SYSTEM, SHORT_USER, 400, timeout)
        verdict["schema_tried"] += 1
        if not r["ok"]:
            verdict["errors"].append(r["error"])
            continue
        short.append(r)
        parsed = _extract_json(r["text"])
        if isinstance(parsed, dict) and all(k in parsed for k in SHORT_KEYS):
            verdict["schema_ok"] += 1
        verdict["reasoning_tokens"] += int(r.get("reasoning") or 0)
    if short:
        r = _post(prov, model, LONG_SYSTEM, LONG_USER, 1200, timeout)
        if r["ok"]:
            long_.append(r)
        else:
            verdict["errors"].append(r["error"])

    if not short:
        verdict["status"] = "failed"
        return verdict

    verdict["status"] = "ok"
    verdict["short_seconds"] = round(statistics.median(
        s["seconds"] for s in short), 3)
    verdict["short_out_tokens"] = statistics.median(
        s["out_tokens"] or 0 for s in short)
    verdict["prompt_tokens"] = short[0].get("in_tokens")
    if long_:
        l = long_[0]
        verdict["long_seconds"] = round(l["seconds"], 3)
        verdict["long_out_tokens"] = l["out_tokens"]
        d_t = l["seconds"] - verdict["short_seconds"]
        d_n = (l["out_tokens"] or 0) - (verdict["short_out_tokens"] or 0)
        if d_t > 0 and d_n > 0:
            verdict["tok_per_s"] = round(d_n / d_t, 1)
            # Everything that is not generation: connection, queueing, and
            # reading a prompt this engine cannot make smaller.
            verdict["overhead_s"] = round(
                max(0.0, verdict["short_seconds"]
                    - (verdict["short_out_tokens"] or 0) / (d_n / d_t)), 2)
    return verdict


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    ap.add_argument("--provider", type=int, default=1)
    ap.add_argument("--models", default=None,
                    help="comma-separated; omit to use --subscriber-only")
    ap.add_argument("--subscriber-only", action="store_true")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    os.environ["ENGINE_DB"] = args.db
    import db
    db.configure(args.db)
    import providers

    prov = dict(db.q("SELECT * FROM providers WHERE id=?",
                     (args.provider,), one=True))
    if args.models:
        names = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        catalogue = providers.list_models(prov)
        names = [m["id"] for m in catalogue
                 if m.get("included") or not args.subscriber_only]

    results = []
    for i, model in enumerate(names, 1):
        print(f"[{i}/{len(names)}] {model}", flush=True)
        try:
            v = bench_one(prov, model, args.trials, args.timeout)
        except Exception as exc:
            v = {"model": model, "status": "failed", "errors": [str(exc)[:160]]}
        results.append(v)
        if v.get("status") == "ok":
            print(f"      short {v.get('short_seconds')}s  "
                  f"long {v.get('long_seconds')}s  "
                  f"{v.get('tok_per_s', '?')} tok/s  "
                  f"schema {v['schema_ok']}/{v['schema_tried']}"
                  + (f"  reasoning {v['reasoning_tokens']}"
                     if v.get("reasoning_tokens") else ""), flush=True)
        else:
            print(f"      FAILED  {(v.get('errors') or ['?'])[0]}", flush=True)

    ok = [v for v in results if v.get("status") == "ok"]
    ok.sort(key=lambda v: v.get("short_seconds", 1e9))
    print("\n=== ranked by short-call wall clock ===")
    print(f"{'short':>7} {'long':>7} {'tok/s':>7} {'ovhd':>6} {'schema':>7}  model")

    def cell(value, width, fmt):
        # A MISSING measurement is not a zero. Rendering `None` as 0.00 made a
        # model whose long call never returned (TheDrummer/Cydonia-24B-v4.1)
        # print as `0.00s / 0.0 tok/s` -- which sorts and reads like the best
        # row in the table instead of the absence of a result.
        if value is None:
            return f"{'--':>{width}}"
        return f"{value:>{width}{fmt}}"

    for v in ok:
        print(f"{cell(v.get('short_seconds'), 7, '.2f')} "
              f"{cell(v.get('long_seconds'), 7, '.2f')} "
              f"{cell(v.get('tok_per_s'), 7, '.1f')} "
              f"{cell(v.get('overhead_s'), 6, '.2f')} "
              f"{v['schema_ok']}/{v['schema_tried']:<5}  {v['model']}")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
