"""Does the pass after a character's turn feel the cost of what it held
back -- and only where holding back costs?

Traced on 2026-09-26 (`docs/experiments/AFFECT_TRACE_2026_09_26.md`), 15 of
16 characters' stored feeling after the call was frustration, whatever they
were handed before it: "Was there something else you wanted to do or say
instead?" was asked of every act, and with the held-back want listed beside
them every act answered yes. The restraint battery
(`tools/mood_battery/restraints.json`) gives each case one beat -- who, what
happened, what the character did in the pass's own words, and the want it
held back -- with `expect` high where holding back costs (duty against love,
a humiliation swallowed, a truth kept from a court) and low where it does
not (a second biscuit, a retort one is glad of).

Each candidate question (`--variants`, a JSON list of question texts
carrying `{act}`) is asked of every act of a case: its reading of the
held-back want is what frustration would be; its reading of the ordinary
acts is what it would leak if it were asked of them. Answers are cached by
state and question text.

Usage:
    ENGINE_DB=<a copy> python tools/jev_restraint_battery.py run --out r.json --variants v.json
    python tools/jev_restraint_battery.py report --results r.json --variants v.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CASES = Path(__file__).resolve().parent / "mood_battery" / "restraints.json"
#: A reading at or above this is present; at or below LOW_AT, absent (the
#: mood battery's thresholds).
HIGH_AT = 0.6
LOW_AT = 0.34


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _acts(case):
    """The case's acts as the pass words them, the held-back want last."""
    acts = [{"ref": f"s{i}", "text": text} for i, text in enumerate(case["acts"])]
    return acts + [{"ref": "held", "text": f"You held back from: {case['held']}"}]


def _state(case):
    parts = [f"YOU ARE {case['who']}.",
             "WHAT JUST HAPPENED:\n" + "\n".join(f"- {t}" for t in case.get("context") or []),
             "WHAT YOU JUST DID:\n" + "\n".join(f"- {a['ref']}: {a['text']}" for a in _acts(case))]
    return "\n\n".join(parts)


def _questions(case, variants):
    """Each template of every act (`{act}`: the act as the pass words it);
    a template naming `{want}` is asked of the held-back want alone, by its
    own words."""
    from mind import affect_appraisal as appraisal

    grade = appraisal._labels("grade", "en")
    qs = {}
    for v, template in enumerate(variants):
        for a in _acts(case):
            if "{want}" in template:
                if a["ref"] != "held":
                    continue
                text = template.replace("{want}", case["held"])
            else:
                text = template.replace("{act}", a["text"])
            qs[f"v{v}:{a['ref']}"] = {"type": "choice", "instructions": text, "criteria": dict(grade)}
    return qs


def _key(q, state):
    return hashlib.sha1(json.dumps([state, q["instructions"], q["criteria"]], ensure_ascii=False,
                                   sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run(args):
    from llm import decisions

    cases = _load(args.cases)["restraints"]
    variants = _load(args.variants)
    path = Path(args.out)
    done = _load(path) if path.exists() else {}
    jobs = []
    for case in cases:
        state = _state(case)
        have = done.setdefault(case["id"], {})
        todo = {k: q for k, q in _questions(case, variants).items() if _key(q, state) not in have}
        if todo:
            jobs.append((case["id"], state, todo))
    print(f"{len(cases)} cases; {sum(len(j[2]) for j in jobs)} questions to ask")

    def ask(job):
        cid, state, todo = job
        answers = decisions.decide(state, todo)
        return cid, {_key(q, state): answers.get(k) for k, q in todo.items() if answers.get(k) is not None}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for cid, got in pool.map(ask, jobs):
            done[cid].update(got)
    path.write_text(json.dumps(done), encoding="utf-8")


def report(args):
    from mind import affect_appraisal as appraisal

    cases = _load(args.cases)["restraints"]
    variants = _load(args.variants)
    results = _load(args.results)
    for v, template in enumerate(variants):
        held, ordinary, met, rows = {"high": [], "low": []}, {"high": [], "low": []}, 0, []
        for case in cases:
            state = _state(case)
            cached = results.get(case["id"]) or {}
            qs = _questions(case, variants)

            def val(ref):
                q = qs.get(f"v{v}:{ref}")
                return appraisal._number({"x": cached.get(_key(q, state))}, "x", "grade") if q else None

            h = val("held")
            if h is None:
                continue
            held[case["expect"]].append(h)
            ordinary[case["expect"]] += [x for a in _acts(case)[:-1] if (x := val(a["ref"])) is not None]
            ok = h >= HIGH_AT if case["expect"] == "high" else h <= LOW_AT
            met += ok
            rows.append((case["id"], case["expect"], h, ok))
        mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")  # noqa: E731
        n = len(rows)
        print(f"v{v} met {met}/{n}   held: costly {mean(held['high']):.2f}, cheap {mean(held['low']):.2f}, "
              f"gap {mean(held['high']) - mean(held['low']):+.2f}   asked of the ordinary acts: "
              f"{mean(ordinary['high'] + ordinary['low']):.2f}\n    {template.splitlines()[-1]}")
        if args.show:
            for cid, expect, h, ok in rows:
                print(f"      {'  ' if ok else 'X '}{cid:22} {expect:4} {h:.2f}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    for mode in ("run", "report"):
        p = sub.add_parser(mode)
        p.add_argument("--cases", default=str(CASES))
        p.add_argument("--variants", required=True)
        if mode == "run":
            p.add_argument("--out", required=True)
            p.add_argument("--workers", type=int, default=6)
        else:
            p.add_argument("--results", required=True)
            p.add_argument("--show", action="store_true")
    args = parser.parse_args()
    {"run": run, "report": report}[args.mode](args)


if __name__ == "__main__":
    main()
