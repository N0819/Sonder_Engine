"""Does the decision model's appraisal, with the mood math, say how a
character feels?

An experiment instrument for `mind/affect_appraisal.py` and
`mind/affect_mix.py` (designed with the owner on 2026-09-26,
`docs/design/DESIGN_JEV_CHARACTER_PASS.md`, "Emotion and mood" and "The mood
math"). On captured character calls that carry per-event perception:

`collect` -- per character and chat, in order, one call per beat: the events
the character perceived (quoted, with actors), the people it has a standing
with and its liking of each, its unsettled concerns, its own speech, actions
and held-back want, the story time that passed, and the mood the character
model reported on that call.

`ask` -- two requests per beat through the engine's own module: `V`, the
events and concerns appraised and the mood read directly (twelve spectrums,
eleven standalone moods); `VP`, the pass after the turn on the character's
own acts.

`label` and `dimlabel` -- the `utility` model (GLM on NanoGPT), blind to the
decision model's answers, names each event's likely emotion from OCC's list
and rates every mood coordinate from the same state.

`score` -- event emotions against the labels by family and sign (shuffled
baselines); the undercurrent against the characters' reports; what own acts
produce; each mood coordinate three ways -- read directly, derived from the
emotions by the math, and the direct reading settled with inertia -- against
the rating; valence and arousal against the reports; and which coordinates
the direct readings move together on.

Usage:
    ENGINE_DB=<a copy> python tools/jev_affect_probe.py collect --chats 150,151 --out calls.json
    ENGINE_DB=<a copy> python tools/jev_affect_probe.py ask --calls calls.json --out appraisals.json
    ENGINE_DB=<a copy> python tools/jev_affect_probe.py label --calls calls.json
    ENGINE_DB=<a copy> python tools/jev_affect_probe.py dimlabel --calls calls.json
    python tools/jev_affect_probe.py score --calls calls.json --appraisals appraisals.json --post
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

MAX_EVENTS = 8
MAX_PEOPLE = 3
MAX_MEMORIES = 8
MAX_CONCERNS = 4
MAX_ACTS = 6
LABELS = ("joy", "distress", "hope", "fear", "satisfaction", "disappointment", "relief",
          "fears_confirmed", "pride", "shame", "admiration", "reproach", "gratitude", "anger",
          "gratification", "remorse", "happy_for", "pity", "resentment", "gloating", "desire", "none")
LABEL_SYSTEM = (
    "You judge how a character most likely feels about each event they just perceived, from their own "
    "situation, aims and standing with people. For each event id answer with ONE emotion from this "
    "list, or none: " + ", ".join(LABELS) + " -- and who or what it is toward. Return JSON only: "
    "{\"events\": {\"<id>\": {\"emotion\": \"...\", \"toward\": \"...\"}}} with every id.")


def _clip(text, n):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + "..."


def _liking(r):
    if isinstance(r.get("emotional_valence"), (int, float)):
        return max(-1.0, min(1.0, float(r["emotional_valence"])))
    parts = [float(r.get(k) or 0) for k in ("warmth", "trust")] + [-float(r.get(k) or 0) for k in ("suspicion", "fear")]
    return max(-1.0, min(1.0, sum(parts) / 2))


def collect(args):
    import jev_memory_probe as probe
    from agents.common import jparse
    from core.db import q

    chats = [int(c) for c in args.chats.split(",") if c.strip()]
    caps = q(f"SELECT c.id, c.turn_id, c.seq, c.payload_hashes, c.response_hash, t.chat_id, t.idx "
             f"FROM llm_capture c JOIN turns t ON t.id=c.turn_id WHERE c.role='character_major' "
             f"AND t.chat_id IN ({','.join('?' * len(chats))}) ORDER BY t.chat_id, t.idx, c.seq", chats)
    seen, calls = set(), []
    for cap in caps:
        h = json.loads(cap["payload_hashes"] or "{}")
        self_ = probe._blob(q, h.get("self")) if h.get("self") else None
        if not isinstance(self_, dict):
            continue
        who = str(self_.get("entity_id") or self_.get("name"))
        if (cap["chat_id"], cap["idx"], who) in seen:
            continue
        seen.add((cap["chat_id"], cap["idx"], who))
        perception = probe._blob(q, h.get("perception")) if h.get("perception") else {}
        rows = [e for e in (perception or {}).get("events") or [] if isinstance(e, dict)]
        events = [{"ref": str(e.get("observation_id") or f"o{i}"),
                   "text": _clip((e.get("observed") or {}).get("text"), 300),
                   "actor": str(e.get("actor") or "")}
                  for i, e in enumerate(sorted(rows, key=lambda e: e.get("order") or 0))
                  if not e.get("standing") and (e.get("observed") or {}).get("text")][:MAX_EVENTS]
        body = q("SELECT body FROM llm_blobs WHERE hash=?", (cap["response_hash"],), one=True) \
            if cap["response_hash"] else None
        raw = body["body"] if body else None
        reply = jparse(raw.decode() if isinstance(raw, bytes) else raw) if raw else None
        affect = (((reply or {}).get("state") or {}).get("active") or {}).get("affect") or {}
        if not events or not isinstance(affect, dict) or not affect.get("surface"):
            continue
        # What the character did, said and held back this beat -- the pass
        # after its turn appraises these as events it brought about.
        acts = []
        for i, s in enumerate(x for x in (reply or {}).get("sequence") or [] if isinstance(x, dict)):
            if s.get("type") == "speech" and str(s.get("text") or "").strip():
                acts.append({"ref": f"s{i}", "text": _clip(f"You said: \"{s['text']}\"", 300), "actor": ""})
            elif s.get("type") == "action" and (s.get("attempt") or s.get("observable")):
                acts.append({"ref": f"s{i}", "text": _clip(f"You {s.get('attempt') or s.get('observable')}", 300),
                             "actor": ""})
        state_ = (reply or {}).get("state") or {}
        wants = {str(w.get("id")): w.get("want") for w in ((state_.get("active") or {}).get("wants") or [])
                 if isinstance(w, dict)}
        held = str((state_.get("decision") or {}).get("suppress") or "")
        if held and wants.get(held):
            acts.append({"ref": "held", "text": _clip(f"You held back from: {wants[held]}", 300), "actor": ""})
        acts = acts[:MAX_ACTS]
        rel = probe._blob(q, h.get("relationships")) if h.get("relationships") else {}
        people = sorted(({"name": name, "liking": round(_liking(r), 3), "familiar": float(r.get("familiarity") or 0)}
                         for name, r in (rel or {}).items() if isinstance(r, dict)),
                        key=lambda p: -p["familiar"])[:MAX_PEOPLE]
        memory = probe._blob(q, h.get("memory")) if h.get("memory") else {}
        memories = [{"ref": str(m.get("event_key") or m.get("memory_ref") or f"m{i}"),
                     "text": _clip(m.get("details") or m.get("gist"), 300)}
                    for i, m in enumerate((memory or {}).get("recalled_old_memories") or [])
                    if isinstance(m, dict) and (m.get("details") or m.get("gist"))][:MAX_MEMORIES]
        active = self_.get("active_state") or {}
        entering = active.get("affect") or {}
        # What is still unsettled for the character: appraised like an event
        # (the `C` arms), since a standing worry is fear of what may yet come
        # -- rumination, which a beat's own events cannot produce.
        concerns = [{"ref": f"c{i}", "text": _clip(f"Still unsettled for you: {t}", 300), "actor": ""}
                    for i, t in enumerate(str(x.get("text") if isinstance(x, dict) else x)
                                          for x in active.get("active_concerns") or [])
                    if t and t != "None"][:MAX_CONCERNS]
        psy = self_.get("psychology") or {}
        drive = psy.get("drive") or {}
        tp = probe._blob(q, h.get("time_passing")) if h.get("time_passing") else {}
        under = affect.get("undercurrent") if isinstance(affect.get("undercurrent"), dict) else {}
        identity = "\n".join(p for p in (
            f"YOU ARE {self_.get('name')}.",
            ("WHAT DRIVES YOU: " + _clip(drive.get("essence"), 300)) if isinstance(drive, dict) and drive.get("essence") else "",
            ("WHAT YOU VALUE: " + "; ".join(_clip(v.get("name"), 60) for v in psy.get("values") or [] if isinstance(v, dict))) if psy.get("values") else "",
            ("WHAT YOU ARE TRYING TO DO: " + _clip(active.get("goal"), 300)) if active.get("goal") else "",
        ) if p)
        surf = entering.get("surface") or {}
        mood_line = (f"HOW YOU FELT COMING INTO THIS: {_clip(surf.get('label'), 120)}" if surf.get("label") else "")
        people_line = ("THE PEOPLE YOU KNOW HERE: " + "; ".join(
            f"{p['name']} (you {'like' if p['liking'] > 0.1 else 'dislike' if p['liking'] < -0.1 else 'are neutral toward'} them)"
            for p in people)) if people else ""
        happened = "WHAT JUST REACHED YOU:\n" + "\n".join(
            f"- {e['ref']}: {e['actor'] + ': ' if e['actor'] and not e['text'].startswith(e['actor']) else ''}{e['text']}"
            for e in events)
        remembered = ("WHAT YOU REMEMBER RIGHT NOW:\n" + "\n".join(f"- {m['text']}" for m in memories)) if memories else ""
        base = entering.get("baseline") or {}
        calls.append({
            "capture": cap["id"], "chat": cap["chat_id"], "turn_idx": cap["idx"], "who": who,
            "name": self_.get("name"), "events": events, "people": people, "memories": memories,
            "concerns": concerns, "acts": acts,
            "elapsed_seconds": float((tp or {}).get("elapsed_seconds") or 0),
            "blocks": {"identity": identity, "mood": mood_line, "people": people_line,
                       "happened": happened, "remembered": remembered},
            "entering": {"valence": surf.get("valence"), "arousal": surf.get("arousal")},
            "home": {"valence": base.get("valence"), "arousal": base.get("arousal")},
            "told": {"surface": affect["surface"].get("label"), "valence": affect["surface"].get("valence"),
                     "arousal": affect["surface"].get("arousal"), "undercurrent": under.get("label"),
                     "under_valence": under.get("valence")},
        })
    Path(args.out).write_text(json.dumps(calls, indent=1), encoding="utf-8")
    names = {}
    for c in calls:
        names[(c["chat"], c["name"])] = names.get((c["chat"], c["name"]), 0) + 1
    print(f"{len(calls)} beats with per-event perception and a reported mood: {names}")


def _state(call, concerns=True, acts=False):
    b = call["blocks"]
    parts = [b["identity"], b["mood"], b["people"], b["happened"]]
    if concerns and call.get("concerns"):
        parts.append("WHAT IS STILL UNSETTLED FOR YOU:\n" + "\n".join(
            f"- {c['ref']}: {c['text']}" for c in call["concerns"]))
    if acts and call.get("acts"):
        parts.append("WHAT YOU JUST DID:\n" + "\n".join(f"- {a['ref']}: {a['text']}" for a in call["acts"]))
    return "\n\n".join(p for p in parts if p)


def ask(args):
    """Two requests per beat through the engine's own module: `V`, the
    beat's events and the character's unsettled concerns appraised and the
    mood read directly; `VP`, the pass after the turn on its own acts."""
    from mind import affect_appraisal as appraisal

    calls = json.loads(Path(args.calls).read_text())
    out = Path(args.out)
    done = json.loads(out.read_text()) if out.exists() else {}
    jobs = [(c, arm) for c in calls for arm in ("V", "VP") if f"{c['capture']}:{arm}" not in done]

    def run(job):
        call, arm = job
        if arm == "V":
            result = appraisal.appraise(_state(call), call["events"] + (call.get("concerns") or []),
                                        call["people"], mood=True, language="en")
        else:
            result = appraisal.appraise(_state(call, acts=True), acts=call.get("acts") or [], language="en")
        return f"{call['capture']}:{arm}", result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (key, result) in enumerate(pool.map(run, jobs), 1):
            done[key] = result
            if n % 20 == 0 or n == len(jobs):
                out.write_text(json.dumps(done), encoding="utf-8")
                print(f"{n} of {len(jobs)} requests")
    out.write_text(json.dumps(done), encoding="utf-8")


def label(args):
    """The `utility` model names, per event, the emotion the character most
    likely feels about it -- blind to the decision model's answers."""
    from agents.common import jparse
    from llm.providers import chat_complete

    path = Path(args.calls)
    calls = json.loads(path.read_text())
    todo = [c for c in calls if "labels" not in c]

    def run(call):
        user = _state(call, concerns=False) + "\n\nEVENT IDS: " + ", ".join(e["ref"] for e in call["events"])
        reply = jparse(chat_complete("utility", LABEL_SYSTEM, user, json_mode=True, temperature=0.0,
                                     max_tokens=1500, reasoning_effort="off")) or {}
        out = {}
        for ref, v in (reply.get("events") or {}).items():
            if isinstance(v, dict) and str(v.get("emotion") or "").strip().lower() in LABELS:
                out[str(ref)] = {"emotion": v["emotion"].strip().lower(), "toward": str(v.get("toward") or "")}
        return call["capture"], out

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        got = dict(pool.map(run, todo))
    for c in calls:
        if c["capture"] in got:
            c["labels"] = got[c["capture"]]
    path.write_text(json.dumps(calls, indent=1), encoding="utf-8")
    print(f"labelled {sum(1 for c in calls if c.get('labels'))} of {len(calls)} beats")


def dimlabel(args):
    """The `utility` model rates every mood coordinate for the character at
    the beat, from the same state the decision model saw and blind to its
    answers: each spectrum -2..2, each standalone mood 0..3."""
    from agents.common import jparse
    from llm.prompts import affect_appraisal_options
    from llm.providers import chat_complete

    poles = affect_appraisal_options("dimensions", "en")
    phrases = affect_appraisal_options("standalone", "en")
    system = ("You judge how a character most likely feels right now, from their own situation. Rate each "
              "SPECTRUM from -2 (entirely the first word) to 2 (entirely the second) and each MOOD from 0 "
              "(not at all) to 3 (strongly). Return JSON only: {\"spectrums\": {\"<name>\": n}, "
              "\"moods\": {\"<name>\": n}} with every name.\nSPECTRUMS: "
              + "; ".join(f"{n}: {p['low']} .. {p['high']}" for n, p in poles.items())
              + "\nMOODS: " + "; ".join(f"{n}: {t}" for n, t in phrases.items()))
    path = Path(args.calls)
    calls = json.loads(path.read_text())
    todo = [c for c in calls if "dims_ref" not in c]

    def run(call):
        reply = jparse(chat_complete("utility", system, _state(call), json_mode=True, temperature=0.0,
                                     max_tokens=1200, reasoning_effort="off")) or {}
        ref = {"spectrums": {}, "moods": {}}
        for part, scale in (("spectrums", 2.0), ("moods", 3.0)):
            for name, v in (reply.get(part) or {}).items():
                try:
                    ref[part][str(name)] = float(v) / scale
                except (TypeError, ValueError):
                    continue
        return call["capture"], ref

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        got = dict(pool.map(run, todo))
    for c in calls:
        if c["capture"] in got:
            c["dims_ref"] = got[c["capture"]]
    path.write_text(json.dumps(calls, indent=1), encoding="utf-8")
    print(f"rated {sum(1 for c in calls if c.get('dims_ref', {}).get('spectrums'))} of {len(calls)} beats")


def _emotions(call, appr, acts=False):
    """The mix's emotions for one beat -- per event and concern (a concern's
    tagged as one), or per own act -- as (per item, all)."""
    from mind import affect_mix as mix

    per_item, everything = {}, []
    if acts:
        for a in call.get("acts") or []:
            es = mix.emotions_from_act((appr.get("acts") or {}).get(a["ref"]) or {}, ref=a["ref"],
                                       about=a["text"][:60])
            per_item[a["ref"]] = es
            everything += es
        return per_item, everything
    liking = {p["name"]: p["liking"] for p in call["people"]}
    for e in call["events"] + (call.get("concerns") or []):
        es = mix.emotions_from_appraisal((appr.get("events") or {}).get(e["ref"]) or {}, ref=e["ref"],
                                         actor=e["actor"], about=e["text"][:60], liking=liking)
        if e["ref"].startswith("c"):
            for x in es:
                x.source = "concern"
        per_item[e["ref"]] = es
        everything += es
    return per_item, everything


def _r(x, y):
    import numpy as np

    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and x.std() > 0 and y.std() > 0 else float("nan")


def score(args):
    import numpy as np

    from mind import affect_mix as mix

    if args.negativity is None:
        args.negativity = mix.NEGATIVITY_WEIGHT
    if args.negative_decay is None:
        args.negative_decay = mix.NEGATIVE_DECAY_FACTOR
    calls = json.loads(Path(args.calls).read_text())
    appraisals = json.loads(Path(args.appraisals).read_text())
    if args.chats:
        keep = {int(c) for c in args.chats.split(",")}
        calls = [c for c in calls if c["chat"] in keep]
    calls = [c for c in calls if f"{c['capture']}:V" in appraisals]
    print(f"{len(calls)} beats; characters {sorted({c['name'] for c in calls})}")

    # (a) event emotions against the utility model's labels, by family and sign
    pairs, under_told = [], []
    for c in calls:
        per, everything = _emotions(c, appraisals[f"{c['capture']}:V"])
        for ref, lab in (c.get("labels") or {}).items():
            es = sorted(per.get(ref) or [], key=lambda e: -e.intensity)
            pairs.append((es[0].name if es and es[0].intensity >= 0.15 else "none", lab["emotion"]))
        neg = any(e.valence < 0 and e.intensity >= 0.15 for e in everything)
        under_told.append(((c["told"].get("under_valence") or 0) < 0, neg))
    if pairs:
        fam = np.mean([FAMILY.get(a) == FAMILY.get(b) for a, b in pairs])
        sign = lambda n: 0 if n == "none" else (1 if mix.EMOTION_EFFECTS[n].get("pleasure", 0) >= 0 else -1)  # noqa: E731
        same = np.mean([sign(a) == sign(b) for a, b in pairs])
        rng = random.Random(3)
        ours = [a for a, _ in pairs]
        base_fam, base_sign = [], []
        for _ in range(300):
            rng.shuffle(ours)
            base_fam.append(np.mean([FAMILY.get(a) == FAMILY.get(b) for a, (_x, b) in zip(ours, pairs)]))
            base_sign.append(np.mean([sign(a) == sign(b) for a, (_x, b) in zip(ours, pairs)]))
        print(f"  events ({len(pairs)}): same family {fam:.0%} (shuffled {np.mean(base_fam):.0%}), "
              f"same sign {same:.0%} (shuffled {np.mean(base_sign):.0%})")
    told_neg = [f for t, f in under_told if t]
    told_not = [f for t, f in under_told if not t]
    print(f"  undercurrent: a negative feeling on {sum(told_neg)} of {len(told_neg)} beats reporting a negative "
          f"one, and on {sum(told_not)} of {len(told_not)} reporting none")

    # (b) the character's own acts
    act_top, eased = {}, []
    for c in calls:
        post = appraisals.get(f"{c['capture']}:VP") or {}
        per, _all = _emotions(c, post, acts=True)
        for a in c.get("acts") or []:
            es = sorted(per.get(a["ref"]) or [], key=lambda e: -e.intensity)
            top = es[0].name if es and es[0].intensity >= 0.15 else "none"
            act_top[top] = act_top.get(top, 0) + 1
            e = ((post.get("acts") or {}).get(a["ref"]) or {}).get("eased_or_stoked")
            if e is not None:
                eased.append(e)
    print("  own acts, strongest emotion:", sorted(act_top.items(), key=lambda t: -t[1]))
    if eased:
        print(f"  own acts, eased or stoked: eased {np.mean([e < -0.2 for e in eased]):.0%}, stoked "
              f"{np.mean([e > 0.2 for e in eased]):.0%}, mean {np.mean(eased):+.2f}")

    # (c) the mood, three ways, against the utility model's ratings and the reports
    coords = list(mix.SPECTRUMS) + list(mix.STANDALONE)
    rows = {"direct": {}, "derived": {}, "settled": {}, "ref": {}}
    va = {"direct": [], "derived": [], "settled": [], "told": []}
    for key in sorted({(c["chat"], c["who"]) for c in calls}):
        seq = sorted((c for c in calls if (c["chat"], c["who"]) == key), key=lambda c: c["turn_idx"])
        first = seq[0]

        def start(v, a):
            v = float(v if v is not None else 0.0)
            a = float(a if a is not None else 0.5) * 2 - 1
            return {"pleasure": v, "energy": a, "tension": a}

        home = mix.Mood(start(first["home"]["valence"], first["home"]["arousal"]))
        derived = mix.Mood(start(first["entering"]["valence"], first["entering"]["arousal"]))
        settled = derived.copy()
        for c in seq:
            dt = c["elapsed_seconds"] / 60.0 if args.clock and c["elapsed_seconds"] else 1.0
            appr = appraisals[f"{c['capture']}:V"]
            reading = {**(appr.get("spectrums") or {}), **(appr.get("moods") or {})}
            _per, everything = _emotions(c, appr)
            derived, _g = mix.mix(derived, home, everything, dt, reactivity=args.reactivity,
                                  negativity=args.negativity, negative_factor=args.negative_decay)
            settled = mix.settle(mix.decay(settled, home, dt, negative_factor=args.negative_decay), reading,
                                 reactivity=args.reactivity)
            ref = {**(c.get("dims_ref") or {}).get("spectrums", {}), **(c.get("dims_ref") or {}).get("moods", {})}
            for name in coords:
                if name in ref and name in reading:
                    rows["ref"].setdefault(name, []).append(ref[name])
                    rows["direct"].setdefault(name, []).append(reading[name])
                    rows["derived"].setdefault(name, []).append(derived.get(name))
                    rows["settled"].setdefault(name, []).append(settled.get(name))
            direct_mood = mix.Mood(reading)
            for name, mood in (("direct", direct_mood), ("derived", derived), ("settled", settled)):
                va[name].append(tuple(mix.engine_affect(mood).values()))
            va["told"].append((float(c["told"]["valence"] or 0), float(c["told"]["arousal"] or 0)))
            if args.post:
                post = appraisals.get(f"{c['capture']}:VP") or {}
                _pp, own = _emotions(c, post, acts=True)
                derived, _g2 = mix.mix(derived, home, own, 0, reactivity=args.reactivity,
                                       negativity=args.negativity, negative_factor=args.negative_decay)
                eases = [x.get("eased_or_stoked") for x in (post.get("acts") or {}).values()
                         if x.get("eased_or_stoked") is not None]
                if eases:
                    derived = mix.ease(derived, home, float(np.mean(eases)))
    print("  coordinate           n  direct  derived  settled   (r against the utility model's rating)")
    means = {"direct": [], "derived": [], "settled": []}
    for name in coords:
        ref = rows["ref"].get(name) or []
        if len(ref) < 5:
            continue
        cells = {m: _r(rows[m][name], ref) for m in ("direct", "derived", "settled")}
        for m, v in cells.items():
            if v == v:
                means[m].append(v)
        print(f"    {name:16} {len(ref):3}  " + "  ".join(f"{cells[m]:7.2f}" for m in ("direct", "derived", "settled")))
    print("    mean r            " + "  ".join(f"{np.mean(v):7.2f}" for v in means.values()))
    told = np.array(va["told"])
    for m in ("direct", "derived", "settled"):
        est = np.array(va[m])
        print(f"  {m:8} vs the character's own report: valence r {_r(est[:, 0], told[:, 0]):.2f}, "
              f"arousal r {_r(est[:, 1], told[:, 1]):.2f}")
    # (d) which coordinates Jev's direct readings move together on
    names = [n for n in coords if len(rows["direct"].get(n) or []) >= 5]
    mat = np.array([rows["direct"][n] for n in names])
    close = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = _r(mat[i], mat[j])
            if v == v and abs(v) >= args.redundant:
                close.append((names[i], names[j], round(v, 2)))
    print(f"  coordinate pairs Jev reads together (|r| >= {args.redundant}):",
          sorted(close, key=lambda t: -abs(t[2]))[:14])


FAMILY = {}
for _fam, _names in {
    "good outcome": ("joy", "satisfaction", "gratification", "relief", "pride", "happy_for", "gloating"),
    "hope": ("hope",), "bad outcome": ("distress", "disappointment", "fears_confirmed", "remorse", "shame",
                                       "pity", "resentment", "frustration"),
    "fear": ("fear",), "toward someone, good": ("admiration", "gratitude"),
    "toward someone, bad": ("reproach", "anger"), "desire": ("desire",), "none": ("none",),
}.items():
    for _n in _names:
        FAMILY[_n] = _fam


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--chats", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("ask")
    p.add_argument("--calls", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=4)
    for mode in ("label", "dimlabel"):
        p = sub.add_parser(mode)
        p.add_argument("--calls", required=True)
        p.add_argument("--workers", type=int, default=3)
    p = sub.add_parser("score")
    p.add_argument("--calls", required=True)
    p.add_argument("--appraisals", required=True)
    p.add_argument("--chats", default="")
    p.add_argument("--reactivity", type=float, default=0.25)
    p.add_argument("--clock", action="store_true", help="decay by story minutes instead of one unit a beat")
    p.add_argument("--post", action="store_true", help="carry the pass after the turn into the next beat")
    p.add_argument("--redundant", type=float, default=0.8)
    p.add_argument("--negativity", type=float, default=None,
                   help="an unpleasant emotion's weight in a target (default affect_mix.NEGATIVITY_WEIGHT)")
    p.add_argument("--negative-decay", type=float, default=None,
                   help="how much slower pleasure below home decays (default affect_mix.NEGATIVE_DECAY_FACTOR)")
    args = parser.parse_args()
    {"collect": collect, "ask": ask, "label": label, "dimlabel": dimlabel, "score": score}[args.mode](args)


if __name__ == "__main__":
    main()
