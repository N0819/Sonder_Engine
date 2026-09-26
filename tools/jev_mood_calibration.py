"""Does the decision model read a character's mood the way readers do, and
which questions -- and which per-mood calibration -- read it best?

The reference is two blind raters (`jev_affect_probe.py dimlabel`, each on
its own database with `utility` routed to a different model family), rating
every coordinate from the same state the decision model sees; their mean is
the consensus. The beats are a probe's collected calls (`jev_affect_probe.py
collect`), one file per story, so a calibration can be fitted on three
stories and scored on the fourth.

`ask` puts the pack's mood questions to the decision model for every beat,
plus any candidates (`--variants`: `{"<mood>": ["phrase", ...]}` asked with
the pack's own template, and `"_template"`: ["...{mood}..."] -- a whole
template for every standalone mood), and one `dominant` question: which of
the moods it feels most. Answers are cached by state and question text.

`report` scores each reader against the consensus: per-coordinate r, moods
read clearly per beat, overlap of the four strongest moods with the
consensus's four, and which moods crowd the four the character would be
given. `fit` learns a per-mood linear calibration on three stories and
scores it on the fourth.

Usage:
    ENGINE_DB=<a copy> python tools/jev_mood_calibration.py ask --beats a.json,b.json --out m.json [--variants v.json]
    python tools/jev_mood_calibration.py report --beats ... --raters r1:a.json,b.json r2:... --results m.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CLEARLY = 2 / 3
TOP = 4


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _beats(paths):
    """[(story, capture, call)] across the beat files, story named by file."""
    out = []
    for path in paths:
        story = Path(path).stem.split("_")[0]
        for call in _load(path):
            out.append((story, call["capture"], call))
    return out


def _state(call):
    from jev_affect_probe import _state as probe_state

    return probe_state(call)


def _questions(variants, language="en"):
    from llm.prompts import affect_appraisal_options
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix

    qs = appraisal.questions_for(mood=True, language=language)
    grade = appraisal._labels("grade", language)
    phrases = affect_appraisal_options("standalone", language)
    for coord, alts in (variants or {}).items():
        if coord == "_template":
            for t, template in enumerate(alts):
                for name in mix.STANDALONE:
                    qs[f"tpl{t}:{name}"] = {"type": "choice", "instructions": template.replace("{mood}", phrases[name]),
                                            "criteria": dict(grade)}
            continue
        for i, phrase in enumerate(alts):
            qs[f"var:{coord}:{i}"] = appraisal._choice("mood_strength", language, mood=phrase)
    qs["dominant"] = {"type": "choice", "instructions": "Right now, which of these do you feel most?",
                      "criteria": {**{n: phrases[n] for n in mix.STANDALONE}, "none": "None of these."}}
    return qs


def _key(q, state):
    return hashlib.sha1(json.dumps([state, q["instructions"], q["criteria"]], ensure_ascii=False,
                                   sort_keys=True).encode("utf-8")).hexdigest()[:16]


def ask(args):
    from llm import decisions

    beats = _beats(args.beats.split(","))
    qs = _questions(_load(args.variants))
    out = Path(args.out)
    done = _load(out) if out.exists() else {}
    jobs = []
    for story, cap, call in beats:
        state = _state(call)
        have = done.setdefault(f"{story}:{cap}", {})
        todo = {k: q for k, q in qs.items() if _key(q, state) not in have}
        if todo:
            jobs.append((f"{story}:{cap}", state, todo))
    print(f"{len(beats)} beats; {sum(len(j[2]) for j in jobs)} questions to ask")

    def run(job):
        bid, state, todo = job
        answers = decisions.decide(state, todo)
        return bid, {_key(q, state): answers.get(k) for k, q in todo.items() if answers.get(k) is not None}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (bid, got) in enumerate(pool.map(run, jobs), 1):
            done[bid].update(got)
            if n % 20 == 0 or n == len(jobs):
                out.write_text(json.dumps(done), encoding="utf-8")
                print(f"{n} of {len(jobs)} beats")
    out.write_text(json.dumps(done), encoding="utf-8")


def _readings(beats, results, variants):
    """{reader: {coord: [value per beat]}} -- the pack, each candidate template
    and the dominant distribution, all as numbers in the coordinate's range."""
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix

    qs = _questions(variants)
    readers = {"pack": {}}
    for t in range(len((variants or {}).get("_template") or [])):
        readers[f"tpl{t}"] = {}
    readers["dominant"] = {}
    for story, cap, call in beats:
        state = _state(call)
        cached = results.get(f"{story}:{cap}") or {}

        def val(key, option_set):
            return appraisal._number({"v": cached.get(_key(qs[key], state))}, "v", option_set)

        for coord in list(mix.SPECTRUMS) + list(mix.STANDALONE):
            key = f"dim:{coord}" if coord in mix.SPECTRUMS else f"mood:{coord}"
            readers["pack"].setdefault(coord, []).append(val(key, "steps" if coord in mix.SPECTRUMS else "grade"))
            for t in range(len((variants or {}).get("_template") or [])):
                if coord in mix.STANDALONE:
                    readers[f"tpl{t}"].setdefault(coord, []).append(val(f"tpl{t}:{coord}", "grade"))
                else:  # a template varies only the standalone moods
                    readers[f"tpl{t}"].setdefault(coord, []).append(readers["pack"][coord][-1])
        dist = appraisal._distribution({"v": cached.get(_key(qs["dominant"], state))}, "v") or {}
        for coord in mix.STANDALONE:
            readers["dominant"].setdefault(coord, []).append(float(dist.get(coord, 0.0)))
    return readers


def _consensus(beats, rater_files):
    """{coord: [mean of the raters per beat]}, standalone moods in [0, 1] and
    spectrums in [-1, 1], from `name:file,file` specs."""
    from mind import affect_mix as mix

    tables = []
    for spec in rater_files:
        _name, files = spec.split(":", 1)
        refs = {}
        for path in files.split(","):
            story = Path(path).stem.split("_")[0]
            for call in _load(path):
                refs[(story, call["capture"])] = call.get("dims_ref") or {}
        tables.append(refs)
    out = {}
    for coord in list(mix.SPECTRUMS) + list(mix.STANDALONE):
        part = "spectrums" if coord in mix.SPECTRUMS else "moods"
        vals = []
        for story, cap, _call in beats:
            got = [t.get((story, cap), {}).get(part, {}).get(coord) for t in tables]
            got = [g for g in got if g is not None]
            vals.append(sum(got) / len(got) if got else None)
        out[coord] = vals
    return out


def _r(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    x, y = np.array(pairs, float).T
    if x.std() < 1e-9 or y.std() < 1e-9:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _top(values_by_coord, i, coords, k=TOP):
    vals = [(c, values_by_coord[c][i]) for c in coords if values_by_coord[c][i] is not None]
    return {c for c, v in sorted(vals, key=lambda cv: -cv[1])[:k] if v > 0}


def _score(name, reading, consensus, n):
    from mind import affect_mix as mix

    rs = [r for r in (_r(reading.get(c) or [None] * n, consensus[c]) for c in reading) if r is not None]
    moods = [c for c in mix.STANDALONE if c in reading]
    clear = np.mean([sum(1 for c in moods if (reading[c][i] or 0) >= CLEARLY) for i in range(n)])
    ref_clear = np.mean([sum(1 for c in moods if (consensus[c][i] or 0) >= CLEARLY) for i in range(n)])
    overlap = np.mean([len(_top(reading, i, moods) & _top(consensus, i, moods)) for i in range(n)])
    crowd = Counter(c for i in range(n) for c in _top(reading, i, moods))
    ref_crowd = Counter(c for i in range(n) for c in _top(consensus, i, moods))
    print(f"{name:10} r {np.mean(rs):.2f} over {len(rs)}   clearly per beat {clear:.1f} (readers {ref_clear:.1f})"
          f"   top-{TOP} overlap {overlap:.2f}")
    over = sorted(((crowd[c] - ref_crowd[c], c) for c in crowd), reverse=True)[:5]
    print("           most over-given in the four: "
          + ", ".join(f"{c} {crowd[c]} vs {ref_crowd[c]}" for d, c in over if d > 0))
    return np.mean(rs), overlap


def report(args):
    beats = _beats(args.beats.split(","))
    variants = _load(args.variants)
    readers = _readings(beats, _load(args.results), variants)
    consensus = _consensus(beats, args.raters)
    n = len(beats)
    print(f"{n} beats; consensus of {len(args.raters)} raters\n")
    for name, reading in readers.items():
        _score(name, reading, consensus, n)
    if args.per_coord:
        from mind import affect_mix as mix
        print("\nper coordinate, pack reading against the consensus:")
        for c in list(mix.SPECTRUMS) + list(mix.STANDALONE):
            r = _r(readers["pack"][c], consensus[c])
            print(f"  {c:15} {'  --' if r is None else f'{r:+.2f}'}")


def fit(args):
    """A per-mood linear map from the pack reading to the consensus, fitted on
    the other stories and scored on each held-out one."""
    from mind import affect_mix as mix

    beats = _beats(args.beats.split(","))
    readers = _readings(beats, _load(args.results), _load(args.variants))
    consensus = _consensus(beats, args.raters)
    pack = readers["pack"]
    stories = sorted({s for s, _c, _call in beats})
    fitted = {c: [None] * len(beats) for c in pack}
    params = {}
    for held in stories:
        train = [i for i, (s, _c, _x) in enumerate(beats) if s != held]
        test = [i for i, (s, _c, _x) in enumerate(beats) if s == held]
        for c in pack:
            xs = np.array([pack[c][i] for i in train if pack[c][i] is not None and consensus[c][i] is not None])
            ys = np.array([consensus[c][i] for i in train if pack[c][i] is not None and consensus[c][i] is not None])
            if len(xs) < 5 or xs.std() < 1e-9:
                slope, icept = 1.0, 0.0
            else:
                slope, icept = np.polyfit(xs, ys, 1)
            params.setdefault(c, []).append((slope, icept))
            lo, hi = (-1.0, 1.0) if c in mix.SPECTRUMS else (0.0, 1.0)
            for i in test:
                x = pack[c][i]
                fitted[c][i] = None if x is None else float(min(hi, max(lo, slope * x + icept)))
    n = len(beats)
    print("held-out, one story at a time:")
    _score("pack", pack, consensus, n)
    _score("calibrated", fitted, consensus, n)
    if args.show:
        for c, ps in params.items():
            s, b = np.mean([p[0] for p in ps]), np.mean([p[1] for p in ps])
            print(f"  {c:15} slope {s:+.2f} intercept {b:+.2f}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("ask")
    p.add_argument("--beats", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--variants", default="")
    p.add_argument("--workers", type=int, default=6)
    for mode in ("report", "fit"):
        p = sub.add_parser(mode)
        p.add_argument("--beats", required=True)
        p.add_argument("--raters", nargs="+", required=True)
        p.add_argument("--results", required=True)
        p.add_argument("--variants", default="")
        p.add_argument("--per-coord", action="store_true")
        p.add_argument("--show", action="store_true")
    args = parser.parse_args()
    {"ask": ask, "report": report, "fit": fit}[args.mode](args)


if __name__ == "__main__":
    main()
