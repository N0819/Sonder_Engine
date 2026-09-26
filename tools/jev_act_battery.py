"""Does the pass after a character's turn feel pride where pride belongs?

The own-act half of the affect pass (`mind/affect_pass.after_call`) asks the
decision model how the character's own speech and deeds land on it
(`affect_appraisal.ACT_QUESTIONS`) and `affect_mix.emotions_from_act` turns
the answers into pride, shame and frustration. Played on four test stories
(2026-09-26) own acts read as pride 39 / 27 / 39 / 60 against shame
0 / 1 / 0 / 1, and since the wiring that pride is the label a character
carries after it speaks. The owner: "adjust the pride tilt a bit".

The act battery (`tools/mood_battery/acts.json`) holds acts of four kinds,
each lived by a person when it names one (the mood battery's persons):
ordinary acts that merely fit the character's values (pride should stay
low), praiseworthy acts that cost something (pride high), blameworthy acts
(shame high), and one act two kinds of people do. Each is asked the pack's
questions and any candidate pride questions (`--variants`, a list of
question texts); `report` scores pride and shame under the current math and
the alternatives, per kind. Answers are cached by the state and the
question's own text, so a new wording asks only itself.

Usage:
    ENGINE_DB=<a copy> python tools/jev_act_battery.py run --out acts.json [--variants v.json]
    python tools/jev_act_battery.py report --results acts.json [--variants v.json]
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

ACTS = Path(__file__).resolve().parent / "mood_battery" / "acts.json"
#: A reading at or above this is present; at or below LOW_AT, absent (the
#: mood battery's thresholds).
HIGH_AT = 0.6
LOW_AT = 0.34
REF = "a0"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _state(case, persons):
    from jev_mood_battery import _person_block

    parts = [f"YOU ARE {case['who']}."]
    if case.get("person"):
        parts.append(_person_block(persons[case["person"]]))
    parts.append("WHAT JUST HAPPENED:\n" + "\n".join(f"- {t}" for t in case.get("context") or []))
    parts.append(f"WHAT YOU JUST DID:\n- {REF}: {case['act']}")
    return "\n\n".join(parts)


def _questions(case, variants, language="en"):
    from mind import affect_appraisal as appraisal

    qs = appraisal.questions_for(acts=[{"ref": REF, "text": case["act"], "actor": ""}], language=language)
    grade = appraisal._labels("grade", language)
    for i, text in enumerate(variants or []):
        qs[f"var:{i}"] = {"type": "choice", "instructions": f"WHAT YOU DID: {case['act']}\n{text}",
                          "criteria": dict(grade)}
    return qs


def _key(q, state):
    return hashlib.sha1(json.dumps([state, q["instructions"], q["criteria"]], ensure_ascii=False,
                                   sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run(args):
    from jev_mood_battery import BATTERY, resolve_persons
    from llm import decisions

    acts = _load(args.acts)["acts"]
    persons = resolve_persons(_load(BATTERY))
    variants = _load(args.variants) or []
    out = Path(args.out)
    done = _load(out) if out.exists() else {}
    jobs = []
    for case in acts:
        state = _state(case, persons)
        have = done.setdefault(case["id"], {})
        todo = {k: q for k, q in _questions(case, variants).items() if _key(q, state) not in have}
        if todo:
            jobs.append((case["id"], state, todo))
    print(f"{len(acts)} acts; {sum(len(j[2]) for j in jobs)} questions to ask")

    def ask(job):
        cid, state, todo = job
        answers = decisions.decide(state, todo)
        return cid, {_key(q, state): answers.get(k) for k, q in todo.items() if answers.get(k) is not None}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for cid, got in pool.map(ask, jobs):
            done[cid].update(got)
    out.write_text(json.dumps(done), encoding="utf-8")


def _answers(case, results, persons, variants):
    """The case's answers keyed the way `affect_appraisal.read` reads them."""
    state = _state(case, persons)
    cached = results.get(case["id"]) or {}
    return {k: cached.get(_key(q, state)) for k, q in _questions(case, variants).items()}


def _maths(a, proud):
    """Pride and shame from one act's appraisal, several ways.

    `now: both` is `emotions_from_act` as it ships since 2026-09-26: the act
    must honour a value AND leave the character thinking better of itself;
    `was: either` is the rule before it, either one enough; `honours only`
    drops the self-regard half; `proud` puts a candidate question in the
    honours slot. `shame: both` and `shame: against` keep the shipped pride
    and take shame as the act going against a value AND leaving the
    character thinking worse of itself, or as the first alone."""
    against = max(0.0, min(1.0, a.get("against_values") or 0.0))
    honours = max(0.0, min(1.0, a.get("honors_values") or 0.0))
    regard = max(-1.0, min(1.0, a.get("self_regard") or 0.0))
    shame = max(against, max(0.0, -regard))
    pride = min(honours, max(0.0, regard)) * (1 - against)
    out = {
        "now: both": (pride, shame),
        "was: either": (max(honours, max(0.0, regard)) * (1 - against), shame),
        "honours only": (honours * (1 - against), shame),
        "shame: both": (pride, min(against, max(0.0, -regard))),
        "shame: against": (pride, against),
    }
    for i, p in enumerate(proud):
        if p is not None:
            out[f"proud v{i}"] = (p * (1 - against), shame)
            out[f"proud v{i} x regard"] = (min(p, max(0.0, regard)) * (1 - against), shame)
    return out


def report(args):
    from jev_mood_battery import BATTERY, resolve_persons
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix

    acts = _load(args.acts)["acts"]
    persons = resolve_persons(_load(BATTERY))
    variants = _load(args.variants) or []
    results = _load(args.results)
    table = {}
    for case in acts:
        answers = _answers(case, results, persons, variants)
        a = appraisal.read({k: v for k, v in answers.items() if v is not None},
                           acts=[{"ref": REF, "text": case["act"], "actor": ""}])["acts"].get(REF) or {}
        proud = [appraisal._number({"v": answers.get(f"var:{i}")}, "v", "grade") for i in range(len(variants))]
        shipped = {e.name: e.intensity for e in mix.emotions_from_act(a)}
        maths = _maths(a, proud)
        assert abs(maths["now: both"][0] - shipped.get("pride", 0.0)) < 1e-3, (case["id"], maths, shipped)
        for name, (pride, shame) in maths.items():
            table.setdefault(name, []).append((case, pride, shame))
        if args.show:
            print(f"{case['id']:32} {case['kind']:12} honours {a.get('honors_values', 0):.2f} regard "
                  f"{a.get('self_regard', 0):+.2f} against {a.get('against_values', 0):.2f} | "
                  + "  ".join(f"{n}: pride {p:.2f}" for n, (p, _s) in maths.items() if n in ("now: both", "was: either")
                              or n.startswith("proud")) + f" | shame {maths['now: both'][1]:.2f}")
    print(f"{len(acts)} acts; pride and shame by kind (mean), and expectations met\n")
    for name, rows in table.items():
        by_kind = {}
        met = total = 0
        for case, pride, shame in rows:
            by_kind.setdefault(case["kind"], []).append((pride, shame))
            for coord, value in (("pride", pride), ("shame", shame)):
                want = (case.get("expect") or {}).get(coord)
                if want:
                    total += 1
                    met += (value >= HIGH_AT) if want == "high" else (value <= LOW_AT)
        kinds = "  ".join(f"{k} pride {sum(p for p, _ in v) / len(v):.2f} shame {sum(s for _, s in v) / len(v):.2f}"
                          for k, v in by_kind.items())
        print(f"{name:22} met {met}/{total}   {kinds}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("run")
    p.add_argument("--acts", default=str(ACTS))
    p.add_argument("--out", required=True)
    p.add_argument("--variants", default="")
    p.add_argument("--workers", type=int, default=6)
    p = sub.add_parser("report")
    p.add_argument("--acts", default=str(ACTS))
    p.add_argument("--results", required=True)
    p.add_argument("--variants", default="")
    p.add_argument("--show", action="store_true")
    args = parser.parse_args()
    {"run": run, "report": report}[args.mode](args)


if __name__ == "__main__":
    main()
