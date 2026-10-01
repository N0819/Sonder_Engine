"""Does sending Jev less change what it answers? (2026-09-30)

The owner: "I want to reduce what we send jev as much as possible, and reduce
as many questions as asked as possible while still getting the task done."

On real captured beats (a `character_major` call's payload and the model's raw
reply, rebuilt into the engine's own `Holding` with
`character_bare.holding_from`), one battery is asked under several variants
and the answers compared question by question. The noise floor is the same
FULL variant asked twice: a trim is safe when it disagrees with FULL no more
than FULL disagrees with itself.

    battery  after | before        variants  full, full2, nomem, mem100
    python tools/concept_lab/jev_equiv.py run  --battery after --beats 8
    python tools/concept_lab/jev_equiv.py report --battery after

Reads engine.db read-only; Jev through the lab db's settings (OpenRouter).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

SRC = lab.ROOT / "engine.db"


def _beats(n):
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = src.execute("select c.turn_id, c.payload_hashes, c.response_hash from llm_capture c "
                       "join turns t on t.id=c.turn_id where c.role='character_major' and c.ok=1 "
                       "and t.created > 1790300000 order by c.id desc").fetchall()
    out, seen = [], set()
    for r in rows:
        if r["turn_id"] in seen:
            continue
        payload = {}
        for key, digest in json.loads(r["payload_hashes"] or "{}").items():
            b = src.execute("select body from llm_blobs where hash=?", (digest,)).fetchone()
            try:
                payload[key] = json.loads(b[0]) if b else None
            except (TypeError, ValueError):
                payload[key] = None
        body = src.execute("select body from llm_blobs where hash=?", (r["response_hash"],)).fetchone()
        try:
            reply = json.loads(body[0]) if body else None
        except (TypeError, ValueError):
            reply = None
        if not (payload.get("memory") and isinstance(reply, dict) and reply.get("sequence")):
            continue
        seen.add(r["turn_id"])
        out.append((r["turn_id"], payload, reply))
        if len(out) >= n:
            break
    return out


def _holding(payload):
    from agents import character_bare as cb
    name = ((payload.get("self") or {}).get("name")) or "you"
    return cb.holding_from(name, {}, payload, (payload.get("perception") or {}).get("events") or [],
                           payload["memory"], {})


def _state(h, reply, variant):
    from mind import character_jev as jev
    if variant in ("full", "full2"):
        return jev.state_text(h, reply)
    import copy
    h2 = copy.copy(h)
    if variant == "nomem":
        h2.memories = []
    elif variant == "mem100":
        h2.memories = [{**m, "text": str(m["text"])[:100]} for m in h.memories]
    return jev.state_text(h2, reply)


def _indexed(h, reply, qs):
    """The memory menu sent once: memories numbered in the state, and every
    option that quoted a memory now points at its number."""
    import re as _re
    from mind import character_jev as jev
    state = jev.state_text(h, reply)
    lines = [f"- {jev._text(m['text'])}" for m in h.memories]
    numbered = [f"- [m{i}] {jev._text(m['text'])}" for i, m in enumerate(h.memories)]
    state = state.replace("\n".join(lines), "\n".join(numbered), 1)
    out = {}
    for key, q in qs.items():
        crit = q["criteria"]
        if any(_re.fullmatch(r"[mar]\d+", c) for c in crit):
            new = {}
            for c, label in crit.items():
                m = _re.fullmatch(r"([mar])(\d+)", c)
                if not m:
                    new[c] = label
                elif m.group(1) == "m":
                    new[c] = f"The memory marked [m{m.group(2)}] above."
                elif m.group(1) == "a":
                    new[c] = f"You acted on the memory marked [m{m.group(2)}] above."
                else:
                    new[c] = f"You pushed against the memory marked [m{m.group(2)}] above."
            q = {**q, "criteria": new}
        out[key] = q
    return state, out


def _short(h, reply, qs, n):
    """The memory menu kept as text, each memory quoted to its first n chars."""
    import re as _re
    from mind import character_jev as jev
    state = jev.state_text(h, reply)
    out = {}
    for key, q in qs.items():
        crit = q["criteria"]
        if any(_re.fullmatch(r"[mar]\d+", c) for c in crit):
            new = {}
            for c, label in crit.items():
                m = _re.fullmatch(r"([mar])(\d+)", c)
                if not m:
                    new[c] = label
                    continue
                text = jev._text(h.memories[int(m.group(2))]["text"], n)
                new[c] = text if m.group(1) == "m" else (
                    f"You acted on this: {text}" if m.group(1) == "a" else f"You pushed against this: {text}")
            q = {**q, "criteria": new}
        out[key] = q
    return state, out


def run(battery, n):
    from mind import character_jev as jev
    cache = lab._load(f"equiv_{battery}.json", {})
    for tid, payload, reply in _beats(n):
        h = _holding(payload)
        qs = jev.after_questions(h, reply) if battery == "after" else jev.before_questions(h)
        if not qs:
            continue
        for variant in VARIANTS:
            key = f"{tid}|{variant}"
            if key in cache:
                continue
            if variant.startswith("short"):
                state, vqs = _short(h, reply if battery == "after" else None, qs, int(variant[5:]))
            elif variant == "idx":
                state, vqs = _indexed(h, reply if battery == "after" else None, qs)
            else:
                state, vqs = _state(h, reply if battery == "after" else None, variant), qs
            ans = jev.ask(state, vqs)
            cache[key] = {"chars": len(state) + len(json.dumps(vqs)), "n": len(qs),
                          "answers": {k: jev.pick(ans, k) for k in qs},
                          "probs": {k: jev._probabilities(ans.get(k)) for k in qs}}
            lab._save(f"equiv_{battery}.json", cache)
        print(tid, "questions", len(qs), "state", {v: cache[f'{tid}|{v}']['chars'] for v in ('full', 'nomem', 'mem100')})


VARIANTS = [v for v in os.environ.get("EQUIV_VARIANTS", "full,full2,nomem,mem100").split(",") if v]


def _family(key):
    return key.split(":")[0]


def report(battery):
    cache = lab._load(f"equiv_{battery}.json", {})
    tids = sorted({k.split("|")[0] for k in cache})
    agree = defaultdict(Counter)
    fam = defaultdict(lambda: defaultdict(Counter))
    chars = defaultdict(list)
    for tid in tids:
        base = cache.get(f"{tid}|full")
        if not base:
            continue
        for v in ("full2", "nomem", "mem100", "idx", "short80", "short50"):
            other = cache.get(f"{tid}|{v}")
            if not other:
                continue
            chars[v].append(other["chars"])
            for k, a in base["answers"].items():
                same = a == other["answers"].get(k)
                agree[v]["same" if same else "diff"] += 1
                fam[v][_family(k)]["same" if same else "diff"] += 1
        chars["full"].append(base["chars"])
    print(f"beats {len(tids)}")
    for v in ("full2", "nomem", "mem100", "idx", "short80", "short50"):
        a = agree[v]
        tot = a["same"] + a["diff"]
        if tot:
            print(f"full vs {v:7}: agree {a['same']}/{tot} = {a['same'] / tot:.1%}   mean state chars "
                  f"{sum(chars[v]) // len(chars[v])} (full {sum(chars['full']) // len(chars['full'])})")
    print("per family (agree share): full2 | short80 | short50")
    for f in sorted(set(fam["full2"]) | set(fam["nomem"])):
        cells = []
        for v in ("full2", "short80", "short50"):
            c = fam[v][f]
            t = c["same"] + c["diff"]
            cells.append(f"{c['same'] / t:.0%}({t})" if t else "-")
        print(f"  {f:14} " + " | ".join(cells))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--battery", default="after")
    ap.add_argument("--beats", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.battery, a.beats)
    else:
        report(a.battery)
