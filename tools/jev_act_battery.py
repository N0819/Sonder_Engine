"""Does the pass after a character's turn feel what its own act should make
it feel -- pride, shame, guilt, embarrassment -- where each belongs?

The own-act half of the affect pass (`mind/affect_pass.after_call`) asks the
decision model how the character's own speech and deeds land on it
(`affect_appraisal.ACT_QUESTIONS`) and `affect_mix.emotions_from_act` turns
the answers into feelings. Played on four test stories (2026-09-26) own acts
read as pride 39 / 27 / 39 / 60 against shame 0 / 1 / 0 / 1, and since the
wiring that pride is the label a character carries after it speaks. The
owner: "adjust the pride tilt a bit"; later the same day, "add embarrassment
and related fields".

The act battery (`tools/mood_battery/acts.json`) holds acts of several
kinds, each lived by a person when it names one (the mood battery's
persons): ordinary acts that merely fit the character's values, praiseworthy
acts that cost something, blameworthy acts, one act two kinds of people do,
social mishaps without moral fault (embarrassment, not shame), acts that
hurt someone (guilt), and fumbles with nobody watching (neither). Each is
asked the pack's questions and any candidate questions (`--variants`: a
list of pride questions, or a map of feeling to question texts); `report`
scores the shipped feelings against each case's `expect`, pride and shame
under their alternative rules, and each candidate. Answers are cached by
the state and the question's own text, so a new wording asks only itself.

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


def _candidates(variants):
    """(key, feeling, text) for each candidate question: a list is pride
    candidates (the battery's first use), a map names the feeling each of
    its lists reads."""
    if isinstance(variants, dict):
        return [(f"var:{feeling}:{i}", feeling, text) for feeling, texts in variants.items()
                for i, text in enumerate(texts)]
    return [(f"var:{i}", "pride", text) for i, text in enumerate(variants or [])]


def _questions(case, variants, language="en"):
    from mind import affect_appraisal as appraisal

    qs = appraisal.questions_for(acts=[{"ref": REF, "text": case["act"], "actor": ""}], language=language)
    grade = appraisal._labels("grade", language)
    for key, _feeling, text in _candidates(variants):
        qs[key] = {"type": "choice", "instructions": f"WHAT YOU DID: {case['act']}\n{text}",
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


def _maths(a, proud, shipped):
    """Pride and shame from one act's appraisal, several ways.

    `now` is `emotions_from_act` as it ships: pride needs the act to honour a
    value AND leave the character thinking better of itself, and shame is
    the act going against a value (OCC's own definition, since the owner's
    ruling of 2026-09-26). `pride was: either` is the pride rule before it;
    `honours only` drops the self-regard half; `shame was: or worse` counts
    any act that leaves the character thinking worse of itself as shame,
    the rule before; `shame: both` needs both, the mirror of pride; `proud`
    puts a candidate question in the honours slot."""
    against = max(0.0, min(1.0, a.get("against_values") or 0.0))
    honours = max(0.0, min(1.0, a.get("honors_values") or 0.0))
    regard = max(-1.0, min(1.0, a.get("self_regard") or 0.0))
    pride = min(honours, max(0.0, regard)) * (1 - against)
    out = {
        "now": (shipped.get("pride", 0.0), shipped.get("shame", 0.0)),
        "pride was: either": (max(honours, max(0.0, regard)) * (1 - against), against),
        "honours only": (honours * (1 - against), against),
        "shame was: or worse": (pride, max(against, max(0.0, -regard))),
        "shame: both": (pride, min(against, max(0.0, -regard))),
    }
    for i, p in enumerate(proud):
        if p is not None:
            out[f"proud v{i}"] = (p * (1 - against), against)
            out[f"proud v{i} x regard"] = (min(p, max(0.0, regard)) * (1 - against), against)
    return out


def _met(value, want):
    return value >= HIGH_AT if want == "high" else value <= LOW_AT


def report(args):
    from jev_mood_battery import BATTERY, resolve_persons
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix

    acts = _load(args.acts)["acts"]
    persons = resolve_persons(_load(BATTERY))
    variants = _load(args.variants) or []
    candidates = _candidates(variants)
    results = _load(args.results)
    table, shipped_rows, candidate_rows = {}, [], []
    for case in acts:
        answers = _answers(case, results, persons, variants)
        a = appraisal.read({k: v for k, v in answers.items() if v is not None},
                           acts=[{"ref": REF, "text": case["act"], "actor": ""}])["acts"].get(REF) or {}
        read = {key: appraisal._number({"v": answers.get(key)}, "v", "grade") for key, _f, _t in candidates}
        shipped = {e.name: e.intensity for e in mix.emotions_from_act(a)}
        shipped_rows.append((case, shipped))
        candidate_rows.append((case, read))
        proud = [read[key] for key, feeling, _t in candidates if feeling == "pride" and not isinstance(variants, dict)]
        for name, (pride, shame) in _maths(a, proud, shipped).items():
            table.setdefault(name, []).append((case, pride, shame))
        if args.show:
            print(f"{case['id']:32} {case['kind']:13} honours {a.get('honors_values', 0):.2f} regard "
                  f"{a.get('self_regard', 0):+.2f} against {a.get('against_values', 0):.2f} | shipped "
                  + ", ".join(f"{n} {v:.2f}" for n, v in sorted(shipped.items())))
    print(f"{len(acts)} acts\n\nthe shipped feelings against each case's expect:")
    for feeling in ("pride", "shame", "guilt", "embarrassment", "falling_short"):
        rows = [(c, s.get(feeling, 0.0)) for c, s in shipped_rows if (c.get("expect") or {}).get(feeling)]
        if rows:
            met = sum(_met(v, c["expect"][feeling]) for c, v in rows)
            misses = ", ".join(f"{c['id']} {v:.2f}" for c, v in rows if not _met(v, c["expect"][feeling]))
            print(f"  {feeling:14} met {met}/{len(rows)}" + (f"   missed: {misses}" if misses else ""))
    print("\npride and shame by kind (mean) under each rule, and their expectations met:")
    for name, rows in table.items():
        by_kind, met, total = {}, 0, 0
        for case, pride, shame in rows:
            by_kind.setdefault(case["kind"], []).append((pride, shame))
            for coord, value in (("pride", pride), ("shame", shame)):
                want = (case.get("expect") or {}).get(coord)
                if want:
                    total += 1
                    met += _met(value, want)
        kinds = "  ".join(f"{k} {sum(p for p, _ in v) / len(v):.2f}/{sum(s for _, s in v) / len(v):.2f}"
                          for k, v in by_kind.items())
        print(f"  {name:22} met {met}/{total}   pride/shame by kind: {kinds}")
    if candidates:
        print("\ncandidates, against their feeling's expectations:")
    for key, feeling, text in candidates:
        rows = [(c, r[key]) for c, r in candidate_rows
                if (c.get("expect") or {}).get(feeling) and r.get(key) is not None]
        met = sum(_met(v, c["expect"][feeling]) for c, v in rows)
        by_kind = {}
        for c, r in candidate_rows:
            if r.get(key) is not None:
                by_kind.setdefault(c["kind"], []).append(r[key])
        kinds = "  ".join(f"{k} {sum(v) / len(v):.2f}" for k, v in by_kind.items())
        print(f"  {key:18} met {met}/{len(rows)}   {kinds}\n      {text}")
        if args.show:
            for c, v in rows:
                if not _met(v, c["expect"][feeling]):
                    print(f"      missed {c['id']} ({c['expect'][feeling]}) {v:.2f}")


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
