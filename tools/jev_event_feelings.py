"""Which feeling does each event a character perceives stir -- and which
question lets the decision model name it the way readers do?

A character's `now` feelings (`mind/affect_pass.py`, `feelings_block`) are the
feelings named for its perceived events, and its `beneath` feelings those of
its standing concerns (`affect_mix.emotions_from_appraisal`,
`concern_emotions`). Until 2026-09-26 OCC's rules named them from nine
appraisal questions; this instrument measured that at chance against two
blind readers and found the direct question the pack now asks (`feel`). It
keeps measuring the engine's question against candidates.

`label` -- a blind rater (`utility`, routed per database copy to a different
model family) names, per event (or per concern, `--what concerns`), the
feeling it stirs in the character most from the combined vocabulary -- OCC's
event emotions and the standalone moods, each with a phrase -- or none, a
second feeling it stirs alongside, and how strongly. Stored in the beat file
under `event_labels` (`concern_labels`).

`ask` -- the decision model gets the pack's event and concern questions and
each candidate naming question (`--variants`: a list of templates carrying
`{event}`, or objects `{"template", "vocabulary": "all"|"occ"|"moods"|"words",
"none"}`; `--concern-variants` the same carrying `{concern}`), every
candidate's options the vocabulary plus none. Answers are cached by state and
question text.

`report` -- per event (or concern), each source's label against each rater:
the engine's strongest feeling and each candidate's top answer; exact, by
family (near-synonyms grouped) and by pleasant or unpleasant sign, with the
raters' agreement with each other as the ceiling and a shuffled baseline as
the floor.

Usage:
    ENGINE_DB=<rater copy> python tools/jev_event_feelings.py label --beats a.json,b.json [--what concerns]
    ENGINE_DB=<a copy> python tools/jev_event_feelings.py ask --beats a.json,b.json --out f.json --variants v.json
    python tools/jev_event_feelings.py report --beats a.json,b.json --raters r1:a.json,b.json r2:... --results f.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

#: OCC's event emotions in words a rater and the decision model can tell
#: apart: the pack's own words are single nouns (`emotion_words`), which
#: overlap the standalone moods too closely to be offered beside them bare.
OCC_PHRASES = {
    "joy": "joy, gladness at something good happening",
    "distress": "distress, being upset at something bad happening",
    "hope": "hope that something good will come of this",
    "fear": "fear that something bad will happen",
    "satisfaction": "satisfaction, something you hoped for coming true",
    "disappointment": "disappointment, something you hoped for falling through",
    "fears_confirmed": "a fear come true",
    "pride": "pride in something you did",
    "shame": "shame at something you did",
    "reproach": "disapproval of something someone did",
    "gratification": "gratification, pleased with something you did that turned out well",
    "remorse": "remorse, sorry for something you did that turned out badly",
    "happy_for": "gladness at good fortune for someone you care about",
    "pity": "pity, sorrow at misfortune for someone you care about",
    "resentment": "resentment of good fortune for someone you dislike",
    "gloating": "gloating over misfortune for someone you dislike",
}
#: Near-synonyms grouped, so a label is not scored wrong for naming the
#: feeling in a neighbouring word. Every name of the vocabulary is in one.
FAMILIES = {
    "glad": ("joy", "satisfaction", "gratification", "contentment", "triumph", "mastery", "pride",
             "gloating", "amusement", "relief"),
    "hope": ("hope", "anticipation"),
    "fear": ("fear", "dread", "horror", "suspicion"),
    "sad": ("distress", "disappointment", "fears_confirmed", "sadness", "grief", "longing",
            "homesickness", "nostalgia", "haunted"),
    "self-blame": ("shame", "guilt", "remorse", "regret", "embarrassment"),
    "hostile": ("reproach", "anger", "contempt", "disgust", "resentment", "jealousy", "envy"),
    "warm": ("admiration", "gratitude", "tenderness", "compassion", "pity", "moved", "happy_for",
             "protectiveness", "romance"),
    "desire": ("sexual_desire", "craving", "greed"),
    "interest": ("curiosity", "surprise", "awe", "aesthetic"),
    "drive": ("resolve", "urgency"),
    "numb": ("numbness",),
    "none": ("none",),
}
FAMILY = {name: fam for fam, names in FAMILIES.items() for name in names}
NONE_PHRASE = "Nothing much -- it barely touches you."
#: Below this, the mix's strongest emotion for an event counts as none.
MIX_FLOOR = 0.15


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _beats(paths):
    """[(story, call)] across the beat files, story named by file."""
    return [(Path(p).stem.split("_")[0], call) for p in paths for call in _load(p)]


def _state(call):
    from jev_affect_probe import _state as probe_state

    return probe_state(call)


def vocabulary(which="all", language="en"):
    """{name: phrase}: OCC's event emotions, the standalone moods, or both --
    or both as the pack's bare words (`words`), the way a label names them."""
    from llm.prompts import affect_appraisal_options

    moods = affect_appraisal_options("standalone", language)
    if which == "words":
        words = {**affect_appraisal_options("emotion_words", language),
                 **affect_appraisal_options("mood_words", language)}
        return {n: words[n] for n in {**OCC_PHRASES, **moods}}
    if which == "occ":
        return {**OCC_PHRASES, "relief": moods["relief"], "admiration": moods["admiration"],
                "gratitude": moods["gratitude"], "anger": moods["anger"]}
    if which == "moods":
        return dict(moods)
    return {**OCC_PHRASES, **moods}


def _sign(name):
    from mind import affect_mix as mix

    if name == "none" or name not in mix.EMOTION_EFFECTS:
        return 0
    p = mix.EMOTION_EFFECTS[name].get("pleasure", 0.0)
    return 0 if abs(p) < 0.2 else (1 if p > 0 else -1)


# --- the raters -----------------------------------------------------------------

#: What `label` names, per kind of item: the beat's field, the state's
#: heading for the items, and where the labels are stored.
ITEMS = {"events": ("events", "each event they just perceived", "EVENT IDS", "event_labels"),
         "concerns": ("concerns", "each thing still unsettled for them, as it sits with them right now",
                      "UNSETTLED IDS", "concern_labels")}


def label(args):
    """The `utility` model names each event's (or each concern's) feeling,
    blind to the decision model's answers, from the same state it reads."""
    from agents.common import jparse
    from llm.providers import chat_complete

    vocab = vocabulary()
    field, what, heading, store = ITEMS[args.what]
    system = (f"You judge how a character most likely feels about {what}, from their own situation, aims "
              "and standing with people. For each id name, under \"feeling\", the feeling it stirs in "
              "them most, from the FEELINGS below -- or \"none\" when it stirs nothing worth naming; under "
              "\"also\", a second feeling it stirs in them at the same time, or \"none\"; and under "
              "\"strength\", how strongly the first stirs them, from 0 (barely) to 3 (strongly). Use the "
              "names exactly as given. Return JSON only: {\"items\": {\"<id>\": {\"feeling\": \"<name>\", "
              "\"also\": \"<name>\", \"strength\": n}}} with every id."
              "\nFEELINGS: " + "; ".join(f"{n}: {p}" for n, p in vocab.items()) + "; none: nothing worth naming")
    for path in args.beats.split(","):
        path = Path(path)
        calls = _load(path)
        todo = [c for c in calls if c.get(field) and (store not in c or args.redo)]

        def run(call):
            user = _state(call) + f"\n\n{heading}: " + ", ".join(e["ref"] for e in call[field])
            reply = jparse(chat_complete("utility", system, user, json_mode=True, temperature=0.0,
                                         max_tokens=2500, reasoning_effort="off")) or {}
            out = {}
            for ref, v in (reply.get("items") or reply.get(field) or {}).items():
                if not isinstance(v, dict):
                    continue
                first = str(v.get("feeling") or "").strip().lower().replace(" ", "_")
                also = str(v.get("also") or "none").strip().lower().replace(" ", "_")
                if first not in vocab and first != "none":
                    continue
                try:
                    strength = float(v.get("strength"))
                except (TypeError, ValueError):
                    strength = None
                out[str(ref)] = {"feeling": first, "also": also if also in vocab else "none",
                                 "strength": strength}
            return call["capture"], out

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            got = dict(pool.map(run, todo))
        for c in calls:
            if c["capture"] in got:
                c[store] = got[c["capture"]]
        path.write_text(json.dumps(calls, indent=1, ensure_ascii=False), encoding="utf-8")
        n = sum(len(c.get(store) or {}) for c in calls)
        print(f"{path.name}: {n} of {sum(len(c.get(field) or []) for c in calls)} {field} labelled")


# --- the decision model -----------------------------------------------------------

def _variants(spec):
    out = []
    for v in spec or []:
        out.append({"template": v, "vocabulary": "all"} if isinstance(v, str) else v)
    return out


def _questions(call, variants, language="en", concern_variants=()):
    """{key: question}: the pack's event and concern questions (`ev:<ref>:...`,
    `con:<ref>:...`), each candidate naming question per event
    (`nm<i>:<ref>`) and per concern (`cn<i>:<ref>`, templates carrying
    `{concern}`)."""
    from mind import affect_appraisal as appraisal

    qs = appraisal.questions_for(call["events"], language=language,
                                 concerns=call.get("concerns") or [] if concern_variants else [])
    for i, v in enumerate(variants):
        criteria = {**vocabulary(v.get("vocabulary", "all"), language), "none": v.get("none", NONE_PHRASE)}
        for e in call["events"]:
            qs[f"nm{i}:{e['ref']}"] = {"type": "choice",
                                       "instructions": v["template"].replace("{event}", appraisal.event_line(e)),
                                       "criteria": criteria}
    for i, v in enumerate(concern_variants):
        criteria = {**vocabulary(v.get("vocabulary", "all"), language), "none": v.get("none", NONE_PHRASE)}
        for c in call.get("concerns") or []:
            text = " ".join(str(c["text"]).split())
            qs[f"cn{i}:{c['ref']}"] = {"type": "choice", "instructions": v["template"].replace("{concern}", text),
                                       "criteria": criteria}
    return qs


def _key(q, state):
    return hashlib.sha1(json.dumps([state, q["instructions"], q["criteria"]], ensure_ascii=False,
                                   sort_keys=True).encode("utf-8")).hexdigest()[:16]


def ask(args):
    from llm import decisions

    beats = _beats(args.beats.split(","))
    variants = _variants(_load(args.variants))
    concern_variants = _variants(_load(args.concern_variants))
    out = Path(args.out)
    done = _load(out) if out.exists() else {}
    jobs = []
    for story, call in beats:
        state = _state(call)
        have = done.setdefault(f"{story}:{call['capture']}", {})
        todo = {k: q for k, q in _questions(call, variants, concern_variants=concern_variants).items()
                if _key(q, state) not in have}
        if todo:
            jobs.append((f"{story}:{call['capture']}", state, todo))
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


# --- scoring ----------------------------------------------------------------------

def _sources(story, call, cached, variants, concern_variants=(), what="events"):
    """{source: {ref: [(name, weight), strongest first]}} for one beat's
    events or concerns: `engine`, what `affect_mix` makes of the pack's own
    questions ("none" first where its strongest feeling is under
    MIX_FLOOR), and each candidate's distribution."""
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix

    state = _state(call)
    qs = _questions(call, variants, concern_variants=concern_variants)
    answers = {k: cached.get(_key(q, state)) for k, q in qs.items()}
    answers = {k: v for k, v in answers.items() if v is not None}
    concerns = call.get("concerns") or [] if concern_variants else []
    read = appraisal.read(answers, call["events"], concerns=concerns)
    prefix, items, alts = (("cn", concerns, concern_variants) if what == "concerns"
                           else ("nm", call["events"], variants))
    out = {"engine": {}, **{f"{prefix}{i}": {} for i in range(len(alts))}}
    for item in items:
        ref = item["ref"]
        a = read[what].get(ref) or {}
        if not a:
            continue
        es = (mix.concern_emotions(a, a.get("weight"), ref=ref) if what == "concerns"
              else mix.emotions_from_appraisal(a, ref=ref))
        ranked = _ranked_emotions(es)
        out["engine"][ref] = ranked if ranked and ranked[0][1] >= MIX_FLOOR else [("none", 1.0)] + ranked
        for i in range(len(alts)):
            dist = appraisal._distribution(answers, f"{prefix}{i}:{ref}") or {}
            out[f"{prefix}{i}"][ref] = sorted(dist.items(), key=lambda kv: -kv[1])
    return out


def _ranked_emotions(emotions):
    best = {}
    for e in emotions:
        best[e.name] = max(best.get(e.name, 0.0), e.intensity)
    return sorted(best.items(), key=lambda kv: -kv[1])


def _rater_tables(specs, store="event_labels"):
    """[(name, {(story, capture): {ref: label}})] from `name:file,file`."""
    out = []
    for spec in specs:
        name, files = spec.split(":", 1)
        table = {}
        for story, call in _beats(files.split(",")):
            table[(story, call["capture"])] = call.get(store) or {}
        out.append((name, table))
    return out


def _agree(a, b, how):
    if how == "exact":
        return a == b
    if how == "family":
        return FAMILY.get(a, a) == FAMILY.get(b, b)
    return _sign(a) == _sign(b)


def report(args):
    beats = _beats(args.beats.split(","))
    variants = _variants(_load(args.variants))
    concern_variants = _variants(_load(args.concern_variants))
    results = _load(args.results)
    field, _what, _heading, store = ITEMS[args.what]
    raters = _rater_tables(args.raters, store)
    rows = []  # (story, capture, item, {source: ranked}, {rater: label})
    for story, call in beats:
        cached = results.get(f"{story}:{call['capture']}") or {}
        sources = _sources(story, call, cached, variants, concern_variants, args.what)
        for e in call.get(field) or []:
            labels = {name: t.get((story, call["capture"]), {}).get(e["ref"]) for name, t in raters}
            if not all(labels.values()):
                continue
            ranked = {s: v.get(e["ref"]) for s, v in sources.items() if v.get(e["ref"])}
            rows.append((story, call["capture"], e, ranked, labels))
    names = [n for n, _t in raters]
    print(f"{len(rows)} {field} labelled by {', '.join(names)}\n")
    a, b = names[0], names[-1]
    for how in ("exact", "family", "sign"):
        agree = sum(_agree(r[4][a]["feeling"], r[4][b]["feeling"], how) for r in rows) / len(rows)
        print(f"raters with each other, {how}: {agree:.0%}")
    agreed = [r for r in rows if _agree(r[4][a]["feeling"], r[4][b]["feeling"], "family")]
    print(f"events the raters put in one family: {len(agreed)}\n")
    sources = sorted({s for r in rows for s in r[3]}, key=lambda s: (s[:2] in ("nm", "cn"), s))
    print(f"{'source':12} {'exact':>12} {'family':>12} {'sign':>6} {'agreed fam':>11} {'in top 3':>9} "
          f"{'none':>6} {'shuffled':>9}")
    for s in sources:
        have = [r for r in rows if s in r[3]]
        if not have:
            continue
        top = [r[3][s][0][0] for r in have]
        per = {}
        for how in ("exact", "family", "sign"):
            per[how] = [sum(_agree(t, r[4][n]["feeling"], how) for t, r in zip(top, have)) / len(have)
                        for n in names]
        ag = [(t, r) for t, r in zip(top, have) if r in agreed]
        fam_agreed = sum(_agree(t, r[4][a]["feeling"], "family") for t, r in ag) / max(1, len(ag))
        top3 = sum(any(r[4][n]["feeling"] in [x for x, _p in r[3][s][:3]] for n in names)
                   for r in have) / len(have)
        rng = random.Random(7)
        shuffled = []
        for _ in range(200):
            t2 = list(top)
            rng.shuffle(t2)
            shuffled.append(sum(_agree(t, r[4][a]["feeling"], "family") for t, r in zip(t2, have)) / len(have))
        none = sum(t == "none" for t in top) / len(top)
        print(f"{s:12} {'/'.join(f'{x:.0%}' for x in per['exact']):>12} "
              f"{'/'.join(f'{x:.0%}' for x in per['family']):>12} "
              f"{sum(per['sign']) / len(per['sign']):>6.0%} {fam_agreed:>11.0%} {top3:>9.0%} {none:>6.0%} "
              f"{sum(shuffled) / len(shuffled):>9.0%}")
    for n in names:
        print(f"{n} names none on {sum(r[4][n]['feeling'] == 'none' for r in rows) / len(rows):.0%} of {field}")
    if args.confusions:
        for s in args.confusions.split(","):
            pairs = Counter((r[3][s][0][0], r[4][a]["feeling"]) for r in rows
                            if s in r[3] and not _agree(r[3][s][0][0], r[4][a]["feeling"], "family"))
            print(f"\n{s}: commonest family misses against {a} (source -> rater):")
            for (x, y), k in pairs.most_common(args.top):
                print(f"  {x:16} -> {y:16} {k}")
        for n in names:
            print(f"\n{n}'s labels: " + ", ".join(f"{k} {v}" for k, v in
                                                Counter(r[4][n]["feeling"] for r in rows).most_common(20)))
    if args.show:
        rng = random.Random(3)
        for r in rng.sample(rows, min(args.show, len(rows))):
            story, cap, e, ranked, labels = r
            print(f"\n[{story} {cap} {e['ref']}] {e['text'][:140]}")
            print("  raters: " + "; ".join(f"{n} {labels[n]['feeling']}+{labels[n]['also']}" for n in names))
            for s in sources:
                if s in ranked:
                    print(f"  {s:10} " + ", ".join(f"{x} {p:.2f}" for x, p in ranked[s][:3]))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("label")
    p.add_argument("--beats", required=True)
    p.add_argument("--what", choices=sorted(ITEMS), default="events")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--redo", action="store_true")
    p = sub.add_parser("ask")
    p.add_argument("--beats", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--variants", default="")
    p.add_argument("--concern-variants", default="")
    p.add_argument("--workers", type=int, default=6)
    p = sub.add_parser("report")
    p.add_argument("--beats", required=True)
    p.add_argument("--what", choices=sorted(ITEMS), default="events")
    p.add_argument("--raters", nargs="+", required=True)
    p.add_argument("--results", required=True)
    p.add_argument("--variants", default="")
    p.add_argument("--concern-variants", default="")
    p.add_argument("--confusions", default="")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--show", type=int, default=0)
    args = parser.parse_args()
    {"label": label, "ask": ask, "report": report}[args.mode](args)


if __name__ == "__main__":
    main()
