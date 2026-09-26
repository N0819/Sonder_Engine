"""Does each mood question read what it names -- and only that -- and does it
read different people differently?

A test bed for the mood's coordinates (`mind/affect_appraisal.py`,
`mind/affect_mix.py`), agreed with the owner on 2026-09-26: "We'll likely have
to invent stories to test moods ... take inspiration from popular stories and
real psychological information as our test bed", "we have a lot of moods to go
over and stress test", "and likely quite a bit of wording refinement to do",
"We'll need to run varied psychology fields with it, person types basically",
and "how well does the mood system align with particular types of people is
good stress test data."

The battery (`tools/mood_battery/battery.json`) holds three things:

- **situations**, each retold in its own words from a psychology paradigm or a
  well-known story beat (`inspired_by` names which), each declaring what it
  should do: which standalone moods run high (`high`), which of their
  look-alikes must stay low (`low`), which way a spectrum leans (`+`, `-`);
- **persons**, psychology profiles written in the card's own fields (drive,
  values as trade-offs, traits, self-model), each grounded in a typology
  (`inspired_by`);
- **person tests**: one situation lived by several persons, with the order
  psychology predicts on a coordinate -- tiers, every person in an earlier
  tier reading higher than every person in a later one.

Every reading is asked exactly as the engine asks it -- the pack's templates
and wordings, through `affect_appraisal.questions_for` -- plus any candidate
wordings under test (`--variants`, a JSON map of coordinate to phrases; a
spectrum's phrase is "low pole|high pole").

`run` asks what is not cached yet -- answers are cached per situation (or
situation@person) by the question's own text and the state it was asked of,
so a re-run with one new wording asks only that wording, and a reworded
situation or person is asked again; `report` scores each coordinate -- targets
reached, near-misses kept low, where it fires unasked -- and each person test
by the share of predicted pairs Jev orders right. Jev is deterministic, so a
wording's numbers reproduce exactly.

These situations test where a wording draws its line and whether a profile
moves it; they do not measure play. The captured-story probe
(`tools/jev_affect_probe.py`) does that.

Usage:
    ENGINE_DB=<a copy> python tools/jev_mood_battery.py run --out results.json [--variants variants.json]
    python tools/jev_mood_battery.py report --results results.json [--variants variants.json] [--only romance,craving]
    python tools/jev_mood_battery.py show --results results.json --id jealousy-old-flame@anxious
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BATTERY = Path(__file__).resolve().parent / "mood_battery" / "battery.json"
#: A standalone mood graded at least this reads as present (the grade scale's
#: "clearly" is 2/3); at most LOW_AT as absent ("slightly" is 1/3). A
#: spectrum past LEAN_AT reads as leaning that way (one step is 0.5).
HIGH_AT = 0.6
LOW_AT = 0.34
LEAN_AT = 0.25
#: In a person test, a person reads higher than another only by more than
#: this -- a tie is a failure to tell two kinds of people apart.
ORDER_MARGIN = 0.02


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def card_block(sheet):
    """A real card's psychology in full -- drive, values with what they
    conflict with, traits, self-model, what makes the character proud or
    ashamed, and the cues its learning has charged -- as the decision model
    would read the character's own card."""
    psy = (sheet or {}).get("psychology") or {}
    drive = psy.get("drive") or {}
    parts = []
    if drive.get("essence"):
        parts.append("WHAT DRIVES YOU: " + " ".join(str(drive[k]) for k in ("essence", "expression") if drive.get(k))
                     + (f" What you will not do: {drive['taboo']}" if drive.get("taboo") else ""))
    values = [v for v in psy.get("values") or [] if isinstance(v, dict) and v.get("name")]
    if values:
        parts.append("WHAT YOU VALUE, MOST FIRST: " + "; ".join(
            f"{v['name']} -- {v.get('expression') or ''}".rstrip(" -")
            + (f" (at odds with: {', '.join(v['conflicts_with'])})" if v.get("conflicts_with") else "")
            for v in sorted(values, key=lambda v: -float(v.get("priority") or 0))))
    traits = [t for t in psy.get("traits") or [] if isinstance(t, dict) and t.get("name")]
    if traits:
        parts.append("HOW YOU ARE: " + "; ".join(f"{t['name']} -- {t.get('expression') or ''}".rstrip(" -")
                                                 for t in traits))
    model = psy.get("self_model") or {}
    if model.get("summary"):
        parts.append("HOW YOU SEE YOURSELF: " + model["summary"]
                     + (" What makes you proud: " + "; ".join(model["pride_triggers"]) + "."
                        if model.get("pride_triggers") else "")
                     + (" What shames you: " + "; ".join(model["shame_triggers"]) + "."
                        if model.get("shame_triggers") else ""))
    cues = [a for a in (psy.get("learning") or {}).get("associations") or [] if isinstance(a, dict) and a.get("cue")]
    if cues:
        parts.append("WHAT STIRS YOU, LEARNED: " + "; ".join(
            f"{a['cue']} -> {a.get('appraisal_bias') or ''}".rstrip(" ->") for a in cues))
    return "\n".join(parts)


def resolve_persons(battery, results=None):
    """The battery's persons, each with the text it is rendered as. A person
    written as `{"card": "<name>"}` is that character's own card, read from
    the database (`ENGINE_DB`) when one is open and otherwise from the block
    a run stored with its results -- so a report needs no database."""
    stored = (results or {}).get("_persons") or {}
    out = {}
    for pid, person in (battery.get("persons") or {}).items():
        if "card" not in person:
            out[pid] = dict(person, block=_person_block(person))
            continue
        block = stored.get(pid)
        if block is None:
            from core.db import q

            row = q("SELECT sheet FROM characters WHERE name = ? ORDER BY id LIMIT 1", (person["card"],), one=True)
            block = card_block(json.loads(row["sheet"] or "{}")) if row else ""
        out[pid] = dict(person, block=block)
    return out


def _person_block(person):
    """A person's psychology, rendered the way a card's fields read."""
    if "block" in person:
        return person["block"]
    return "\n".join(p for p in (
        "WHAT DRIVES YOU: " + person["drive"] if person.get("drive") else "",
        "WHAT YOU VALUE: " + "; ".join(person.get("values") or []) if person.get("values") else "",
        "HOW YOU ARE: " + "; ".join(person.get("traits") or []) if person.get("traits") else "",
        "HOW YOU SEE YOURSELF: " + person["self_model"] if person.get("self_model") else "",
    ) if p)


def _state(v, person=None):
    """A situation as the decision model reads it -- the shape the probe's
    captured states take -- lived by `person` when one is given."""
    parts = [f"YOU ARE {v['who']}."]
    if person:
        parts.append(_person_block(person))
    if v.get("about"):
        parts.append("ABOUT YOU: " + v["about"])
    if v.get("people"):
        parts.append("THE PEOPLE YOU KNOW HERE: " + v["people"])
    parts.append("WHAT JUST REACHED YOU:\n" + "\n".join(f"- o{i + 1}: {t}" for i, t in enumerate(v["happened"])))
    if v.get("remember"):
        parts.append("WHAT YOU REMEMBER RIGHT NOW:\n" + "\n".join(f"- {t}" for t in v["remember"]))
    return "\n\n".join(parts)


def _cells(battery, persons=None):
    """Every (cell id, situation, person) to ask: each situation alone, and
    each situation a person test gives to a person. `persons` is
    `resolve_persons`' answer; without it a card person renders empty."""
    persons = persons or {pid: dict(p) for pid, p in (battery.get("persons") or {}).items()}
    situations = {v["id"]: v for v in battery["situations"]}
    cells = [(v["id"], v, None) for v in battery["situations"]]
    seen = set()
    for test in battery.get("person_tests") or []:
        pids = list(test.get("persons") or [])
        for order in test.get("orders") or []:
            pids += [p for tier in order["tiers"] for p in tier if p not in pids]
        for pid in pids:
            cid = f"{test['situation']}@{pid}"
            if cid not in seen:
                seen.add(cid)
                cells.append((cid, situations[test["situation"]], persons[pid]))
    return cells


def _questions(variants, language="en"):
    """Every mood question the engine asks (`dim:<spectrum>`, `mood:<mood>`),
    and each candidate wording as `var:<coordinate>:<index>`."""
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix

    qs = appraisal.questions_for(mood=True, language=language)
    for coord, phrases in (variants or {}).items():
        for i, phrase in enumerate(phrases):
            if coord in mix.SPECTRUMS:
                low, high = phrase.split("|")
                qs[f"var:{coord}:{i}"] = appraisal._choice("dimension", language, low=low.strip(), high=high.strip())
            else:
                qs[f"var:{coord}:{i}"] = appraisal._choice("mood_strength", language, mood=phrase)
    return qs


def _key(q, state):
    """A cached answer's key: the question's own text AND the state it was
    asked of, so rewording a situation or a person asks again rather than
    reading an answer given to the old words."""
    return hashlib.sha1(json.dumps([state, q["instructions"], q["criteria"]], ensure_ascii=False,
                                   sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _coord(key):
    return key.split(":")[1]


def run(args):
    from llm import decisions
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix

    battery = _load(args.battery)
    qs = _questions(_load(args.variants))
    out = Path(args.out)
    done = _load(out) if out.exists() else {}
    # a card person is read fresh from the database, and the block it
    # rendered is kept with the results so a report needs no database
    persons = resolve_persons(battery)
    done["_persons"] = {pid: p["block"] for pid, p in persons.items() if "card" in p}
    jobs = []
    for cid, v, person in _cells(battery, persons):
        have = done.setdefault(cid, {})
        state = _state(v, person)
        todo = {k: q for k, q in qs.items() if _key(q, state) not in have}
        if todo:
            jobs.append((cid, state, todo))
    print(f"{len(done)} cells; {sum(len(j[2]) for j in jobs)} questions to ask")

    def ask(job):
        cid, state, todo = job
        answers = decisions.decide(state, todo)
        got = {}
        for k, q in todo.items():
            value = appraisal._number(answers, k, "steps" if _coord(k) in mix.SPECTRUMS else "grade")
            if value is not None:
                got[_key(q, state)] = round(value, 4)
        return cid, got

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (cid, got) in enumerate(pool.map(ask, jobs), 1):
            done[cid].update(got)
            if n % 10 == 0 or n == len(jobs):
                out.write_text(json.dumps(done), encoding="utf-8")
                print(f"{n} of {len(jobs)} cells")
    out.write_text(json.dumps(done), encoding="utf-8")


def _readers(coord, variants, spectrums):
    base = f"dim:{coord}" if coord in spectrums else f"mood:{coord}"
    return [("pack", base)] + [(f"v{i}", f"var:{coord}:{i}") for i in range(len(variants.get(coord) or []))]


def _judge(expect, value):
    """Whether one reading meets one expectation: `high` / `low` for a
    standalone mood, `+` / `-` for a spectrum's lean."""
    if value is None:
        return None
    return {"high": value >= HIGH_AT, "low": value <= LOW_AT,
            "+": value >= LEAN_AT, "-": value <= -LEAN_AT}[expect]


def _situation_report(battery, results, qs, variants, only, unasked_n):
    from mind import affect_mix as mix

    totals, trouble = {"pass": 0, "fail": 0}, []
    states = {v["id"]: _state(v) for v in battery["situations"]}
    for coord in only:
        for label, key in _readers(coord, variants, mix.SPECTRUMS):
            q = qs[key]
            hits, misses, kept, leaks, unasked = [], [], [], [], []
            for v in battery["situations"]:
                value = (results.get(v["id"]) or {}).get(_key(q, states[v["id"]]))
                want = (v.get("expect") or {}).get(coord)
                if want is None:
                    if coord in mix.STANDALONE and value is not None and value >= HIGH_AT:
                        unasked.append((v["id"], value))
                    continue
                ok = _judge(want, value)
                if ok is None:
                    continue
                if want in ("high", "+", "-"):
                    (hits if ok else misses).append((v["id"], value))
                else:
                    (kept if ok else leaks).append((v["id"], value))
            if label == "pack":
                totals["pass"] += len(hits) + len(kept)
                totals["fail"] += len(misses) + len(leaks)
                if misses or leaks:
                    trouble.append((len(misses) + len(leaks), coord))
            line = (f"{coord:14} {label:4} targets {len(hits)}/{len(hits) + len(misses)}"
                    f"  kept low {len(kept)}/{len(kept) + len(leaks)}"
                    + (f"  fires unasked {len(unasked)}" if coord in mix.STANDALONE else ""))
            print(line + (f"   [{q['instructions'][:90]}]" if label != "pack" else ""))
            for vid, value in misses:
                print(f"      missed  {vid:36} {value:+.2f}")
            for vid, value in leaks:
                print(f"      leaked  {vid:36} {value:+.2f}")
            for vid, value in sorted(unasked, key=lambda t: -t[1])[:unasked_n]:
                print(f"      unasked {vid:36} {value:+.2f}")
    n = totals["pass"] + totals["fail"]
    if n:
        print(f"\nsituations: the pack's wordings meet {totals['pass']} of {n} expectations "
              f"({totals['pass'] / n:.0%}); coordinates with a failure, most first: "
              + ", ".join(f"{c} {k}" for k, c in sorted(trouble, key=lambda t: (-t[0], t[1]))))


def _person_report(battery, results, qs, only):
    """Each person test: per predicted order, the persons' readings and the
    share of cross-tier pairs Jev orders right by more than ORDER_MARGIN."""
    from mind import affect_mix as mix

    right = total = 0
    by_person = {}
    states = {cid: _state(v, person) for cid, v, person in _cells(battery, resolve_persons(battery, results))}
    print("\nperson tests (tiers: every person in an earlier tier should read higher)")
    for test in battery.get("person_tests") or []:
        for order in test["orders"]:
            coord = order["coord"]
            if coord not in only:
                continue
            key = f"dim:{coord}" if coord in mix.SPECTRUMS else f"mood:{coord}"
            value = {}
            for p in (p for tier in order["tiers"] for p in tier):
                cid = f"{test['situation']}@{p}"
                value[p] = (results.get(cid) or {}).get(_key(qs[key], states[cid]))
            pairs = ok = 0
            for i, j in product(range(len(order["tiers"])), repeat=2):
                if j <= i:
                    continue
                for hi, lo in product(order["tiers"][i], order["tiers"][j]):
                    if value[hi] is None or value[lo] is None:
                        continue
                    good = value[hi] > value[lo] + ORDER_MARGIN
                    pairs += 1
                    ok += good
                    for p, won in ((hi, good), (lo, good)):
                        s = by_person.setdefault(p, [0, 0])
                        s[0] += won
                        s[1] += 1
            right += ok
            total += pairs
            tiers = " > ".join("/".join(f"{p} {value[p]:+.2f}" if value[p] is not None else f"{p} ?" for p in tier)
                               for tier in order["tiers"])
            mark = "ok " if pairs and ok == pairs else "   "
            print(f"  {mark}{test['situation']:30} {coord:13} {ok}/{pairs}   {tiers}")
    if total:
        print(f"\nperson tests: {right} of {total} predicted pairs ordered right ({right / total:.0%})")
        print("  by person (pairs they took part in, ordered right):",
              ", ".join(f"{p} {s[0]}/{s[1]}" for p, s in sorted(by_person.items(), key=lambda t: t[1][0] / t[1][1])))


def report(args):
    from mind import affect_mix as mix

    battery = _load(args.battery)
    variants = _load(args.variants)
    results = _load(args.results)
    qs = _questions(variants)
    coords = list(mix.SPECTRUMS) + list(mix.STANDALONE)
    only = [c for c in args.only.split(",") if c] if args.only else coords
    if not args.persons_only:
        _situation_report(battery, results, qs, variants, only, args.unasked)
    _person_report(battery, results, qs, only)


def check(args):
    """The battery is well formed: ids unique; every expectation names a
    coordinate the code has, `high`/`low` on a standalone mood and `+`/`-` on
    a spectrum; every person test names a situation and persons that exist.
    Prints what each coordinate is tested by."""
    from mind import affect_mix as mix

    battery = _load(args.battery)
    problems = []
    ids = [v["id"] for v in battery["situations"]]
    problems += [f"duplicate situation id {i}" for i in {i for i in ids if ids.count(i) > 1}]
    for v in battery["situations"]:
        for coord, want in (v.get("expect") or {}).items():
            if coord in mix.STANDALONE and want not in ("high", "low"):
                problems.append(f"{v['id']}: {coord} is a standalone mood, expects high or low, not {want!r}")
            elif coord in mix.SPECTRUMS and want not in ("+", "-"):
                problems.append(f"{v['id']}: {coord} is a spectrum, expects + or -, not {want!r}")
            elif coord not in mix.STANDALONE and coord not in mix.SPECTRUMS:
                problems.append(f"{v['id']}: no coordinate {coord!r}")
    for test in battery.get("person_tests") or []:
        if test["situation"] not in ids:
            problems.append(f"person test on unknown situation {test['situation']!r}")
        for order in test["orders"]:
            if order["coord"] not in mix.STANDALONE and order["coord"] not in mix.SPECTRUMS:
                problems.append(f"{test['situation']}: no coordinate {order['coord']!r}")
            for p in (p for tier in order["tiers"] for p in tier):
                if p not in battery["persons"]:
                    problems.append(f"{test['situation']}: no person {p!r}")
    for p in problems:
        print("PROBLEM", p)
    coverage = {}
    for v in battery["situations"]:
        for coord, want in (v.get("expect") or {}).items():
            coverage.setdefault(coord, {"target": 0, "kept low": 0})[
                "kept low" if want == "low" else "target"] += 1
    for test in battery.get("person_tests") or []:
        for order in test["orders"]:
            coverage.setdefault(order["coord"], {"target": 0, "kept low": 0}).setdefault("person orders", 0)
            coverage[order["coord"]]["person orders"] += 1
    for coord in list(mix.SPECTRUMS) + list(mix.STANDALONE):
        print(f"  {coord:14} {coverage.get(coord) or 'UNTESTED'}")
    cells = _cells(battery)
    print(f"{len(battery['situations'])} situations, {len(battery['persons'])} persons, "
          f"{len(battery.get('person_tests') or [])} person tests, {len(cells)} cells; "
          + ("well formed" if not problems else f"{len(problems)} problems"))
    return not problems


def show(args):
    """Every coordinate's reading for one cell, strongest first."""
    from mind import affect_mix as mix

    battery = _load(args.battery)
    results = _load(args.results)
    cells = {cid: (v, person) for cid, v, person in _cells(battery, resolve_persons(battery, results))}
    v, person = cells[args.id]
    have = results.get(args.id) or {}
    qs = _questions({})
    state = _state(v, person)
    print(state)
    print("\nexpects:", v.get("expect"))
    rows = [(_coord(k), have.get(_key(q, state))) for k, q in qs.items()]
    spect = sorted((r for r in rows if r[0] in mix.SPECTRUMS and r[1] is not None), key=lambda r: -abs(r[1]))
    moods = sorted((r for r in rows if r[0] in mix.STANDALONE and r[1] is not None), key=lambda r: -r[1])
    print("spectrums:", ", ".join(f"{c} {x:+.2f}" for c, x in spect))
    print("moods:    ", ", ".join(f"{c} {x:.2f}" for c, x in moods if x >= 0.2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("run")
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=8)
    p = sub.add_parser("report")
    p.add_argument("--results", required=True)
    p.add_argument("--only", default="")
    p.add_argument("--unasked", type=int, default=0, help="list this many situations each mood fires in unasked")
    p.add_argument("--persons-only", action="store_true")
    p = sub.add_parser("show")
    p.add_argument("--results", required=True)
    p.add_argument("--id", required=True, help="a situation id, or situation@person")
    sub.add_parser("check")
    for p in sub.choices.values():
        p.add_argument("--battery", default=str(BATTERY))
        p.add_argument("--variants", default="")
    args = parser.parse_args()
    result = {"run": run, "report": report, "show": show, "check": check}[args.mode](args)
    if result is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
