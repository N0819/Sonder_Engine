"""Does the worry question weigh what this moment brings forward?

A standing concern stirs feeling in proportion to how much it is on the mind
(`affect_mix.concern_emotions`, weighted by `concern_weight`). Measured on the
four test stories (2026-09-26) the decision model weighed every listed
concern about 0.75 -- the question asked whether it weighs on the character,
and a concern is on the list because it does -- so a worry the beat does not
touch stirred as much as the one it does. The concern battery
(`tools/mood_battery/concerns.json`) gives each situation one concern the
event touches (`expect: high`) and background ones it does not (`low`), and
scores the pack's question and any candidates (`--variants`, a JSON list of
question texts, `{concern}` where the concern goes) by what each reads high
and low, and by the gap between the touched and the untouched.

Usage:
    ENGINE_DB=<a copy> python tools/jev_concern_battery.py run --out c.json [--variants v.json]
    python tools/jev_concern_battery.py report --results c.json [--variants v.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CONCERNS = Path(__file__).resolve().parent / "mood_battery" / "concerns.json"
HIGH_AT = 0.6
LOW_AT = 0.34


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _state(sit):
    """The situation as the pass renders a beat with standing concerns."""
    return "\n\n".join([
        f"YOU ARE {sit['who']}.",
        "WHAT JUST REACHED YOU:\n" + "\n".join(f"- o{i + 1}: {t}" for i, t in enumerate(sit["happened"])),
        "WHAT IS STILL UNSETTLED FOR YOU:\n" + "\n".join(f"- {c['text']}" for c in sit["concerns"]),
    ])


def _questions(sit, variants, language="en"):
    from mind import affect_appraisal as appraisal

    grade = appraisal._labels("grade", language)
    qs = {}
    for i, c in enumerate(sit["concerns"]):
        qs[f"c{i}:pack"] = appraisal._choice("concern_weight", language, concern=c["text"])
        for j, text in enumerate(variants or []):
            qs[f"c{i}:v{j}"] = {"type": "choice", "instructions": text.replace("{concern}", c["text"]),
                                "criteria": dict(grade)}
    return qs


def _key(q, state):
    return hashlib.sha1(json.dumps([state, q["instructions"], q["criteria"]], ensure_ascii=False,
                                   sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run(args):
    from llm import decisions

    sits = _load(args.concerns)["situations"]
    variants = _load(args.variants) or []
    out = Path(args.out)
    done = _load(out) if out.exists() else {}
    jobs = []
    for sit in sits:
        state = _state(sit)
        have = done.setdefault(sit["id"], {})
        todo = {k: q for k, q in _questions(sit, variants).items() if _key(q, state) not in have}
        if todo:
            jobs.append((sit["id"], state, todo))
    print(f"{len(sits)} situations; {sum(len(j[2]) for j in jobs)} questions to ask")

    def ask(job):
        sid, state, todo = job
        answers = decisions.decide(state, todo)
        return sid, {_key(q, state): answers.get(k) for k, q in todo.items() if answers.get(k) is not None}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for sid, got in pool.map(ask, jobs):
            done[sid].update(got)
    out.write_text(json.dumps(done), encoding="utf-8")


def report(args):
    from mind import affect_appraisal as appraisal

    sits = _load(args.concerns)["situations"]
    variants = _load(args.variants) or []
    results = _load(args.results)
    readers = ["pack"] + [f"v{j}" for j in range(len(variants))]
    rows = {r: [] for r in readers}
    for sit in sits:
        state = _state(sit)
        qs = _questions(sit, variants)
        cached = results.get(sit["id"]) or {}
        for i, c in enumerate(sit["concerns"]):
            for r in readers:
                q = qs[f"c{i}:{r}"]
                value = appraisal._number({"v": cached.get(_key(q, state))}, "v", "grade")
                rows[r].append((sit["id"], c["text"], c.get("expect"), value))
    for r in readers:
        text = "the pack" if r == "pack" else variants[int(r[1:])]
        high = [v for _s, _t, e, v in rows[r] if e == "high" and v is not None]
        low = [v for _s, _t, e, v in rows[r] if e == "low" and v is not None]
        met = sum(v >= HIGH_AT for v in high) + sum(v <= LOW_AT for v in low)
        gap = (sum(high) / len(high) - sum(low) / len(low)) if high and low else float("nan")
        quiet = [round(v, 2) for s, _t, _e, v in rows[r] if s == "quiet-porch" and v is not None]
        print(f"{r:5} met {met}/{len(high) + len(low)}  touched {sum(high) / max(1, len(high)):.2f}  "
              f"untouched {sum(low) / max(1, len(low)):.2f}  gap {gap:+.2f}  quiet evening {quiet}  [{text[:70]}]")
        if args.show:
            for s, t, e, v in rows[r]:
                if e and v is not None and ((e == "high" and v < HIGH_AT) or (e == "low" and v > LOW_AT)):
                    print(f"      missed {s:18} {e:4} {v:.2f}  {t}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("run")
    p.add_argument("--concerns", default=str(CONCERNS))
    p.add_argument("--out", required=True)
    p.add_argument("--variants", default="")
    p.add_argument("--workers", type=int, default=6)
    p = sub.add_parser("report")
    p.add_argument("--concerns", default=str(CONCERNS))
    p.add_argument("--results", required=True)
    p.add_argument("--variants", default="")
    p.add_argument("--show", action="store_true")
    args = parser.parse_args()
    {"run": run, "report": report}[args.mode](args)


if __name__ == "__main__":
    main()
