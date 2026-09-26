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
events, the recalled memories and the concerns (each with its weight)
appraised and the mood read directly (every spectrum and standalone mood the
pack names); `VP`, the pass after the turn on the character's own acts.

`label` and `dimlabel` -- the `utility` model (GLM on NanoGPT), blind to the
decision model's answers, names each event's likely emotion from OCC's list,
rates every mood coordinate from the same state, and names any mood the
character is in that no coordinate covers.

`score` -- event emotions against the labels by family and sign (shuffled
baselines); the undercurrent -- what memories and concerns stirred, with and
without the concern gate -- against the characters' reports; which moods
memories stir; what own acts produce; each mood coordinate three ways --
read directly, derived from the emotions by the math (memories habituated
the owner's way), and the direct reading settled with inertia -- against the
rating; valence and arousal against the reports; which coordinates the
direct readings move together on; and what the rater found uncovered.

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


def _state(call, concerns=True, acts=False, memories=True):
    b = call["blocks"]
    parts = [b["identity"], b["mood"], b["people"], b["happened"]]
    if concerns and call.get("concerns"):
        parts.append("WHAT IS STILL UNSETTLED FOR YOU:\n" + "\n".join(
            f"- {c['ref']}: {c['text']}" for c in call["concerns"]))
    if memories and b.get("remembered"):
        parts.append(b["remembered"])
    if acts and call.get("acts"):
        parts.append("WHAT YOU JUST DID:\n" + "\n".join(f"- {a['ref']}: {a['text']}" for a in call["acts"]))
    return "\n\n".join(p for p in parts if p)


def ask(args):
    """Two requests per beat through the engine's own module: `V`, the
    beat's events, recalled memories and unsettled concerns appraised and the
    mood read directly; `VP`, the pass after the turn on its own acts."""
    from mind import affect_appraisal as appraisal

    calls = json.loads(Path(args.calls).read_text())
    out = Path(args.out)
    done = json.loads(out.read_text()) if out.exists() else {}
    arms = [a for a in args.arms.split(",") if a]
    jobs = [(c, arm) for c in calls for arm in arms if f"{c['capture']}:{arm}" not in done]

    def run(job):
        call, arm = job
        if arm == "V":
            result = appraisal.appraise(_state(call), call["events"], call["people"],
                                        memories=call.get("memories") or [], mood=True, language="en",
                                        concerns=call.get("concerns") or [])
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
    answers: each spectrum -2..2, each standalone mood 0..3 -- and names any
    mood the character is in that none of them covers."""
    from agents.common import jparse
    from llm.prompts import affect_appraisal_options
    from llm.providers import chat_complete

    poles = affect_appraisal_options("dimensions", "en")
    phrases = affect_appraisal_options("standalone", "en")
    system = ("You judge how a character most likely feels right now, from their own situation. Rate each "
              "SPECTRUM from -2 (entirely the first word) to 2 (entirely the second) and each MOOD from 0 "
              "(not at all) to 3 (strongly). Then, under \"uncovered\", name any mood or feeling the "
              "character is in right now that no spectrum or mood here captures, even in combination -- "
              "an empty list when they all do. Return JSON only: {\"spectrums\": {\"<name>\": n}, "
              "\"moods\": {\"<name>\": n}, \"uncovered\": [\"...\"]} with every name.\nSPECTRUMS: "
              + "; ".join(f"{n}: {p['low']} .. {p['high']}" for n, p in poles.items())
              + "\nMOODS: " + "; ".join(f"{n}: {t}" for n, t in phrases.items()))
    path = Path(args.calls)
    calls = json.loads(path.read_text())
    todo = [c for c in calls if "dims_ref" not in c]

    def run(call):
        reply = jparse(chat_complete("utility", system, _state(call), json_mode=True, temperature=0.0,
                                     max_tokens=2000, reasoning_effort="off")) or {}
        ref = {"spectrums": {}, "moods": {}}
        for part, scale in (("spectrums", 2.0), ("moods", 3.0)):
            for name, v in (reply.get(part) or {}).items():
                try:
                    ref[part][str(name)] = float(v) / scale
                except (TypeError, ValueError):
                    continue
        ref["uncovered"] = [str(x) for x in reply.get("uncovered") or [] if str(x).strip()]
        return call["capture"], ref

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        got = dict(pool.map(run, todo))
    for c in calls:
        if c["capture"] in got:
            c["dims_ref"] = got[c["capture"]]
    path.write_text(json.dumps(calls, indent=1), encoding="utf-8")
    print(f"rated {sum(1 for c in calls if c.get('dims_ref', {}).get('spectrums'))} of {len(calls)} beats")


DESIRES = ("romance", "sexual_desire", "craving")


def _emotions(call, appr, acts=False, multipliers=None, gate=True, parts=("events", "concerns", "memories")):
    """The mix's emotions for one beat, as (per item, all): per event (with
    the moods it stirred), per concern (scaled by its weight, unless `gate`
    is off), per recalled memory (the moods named for it and the plain rest by
    its tone, dulled by `multipliers` -- the owner's habituation); or, with
    `acts`, per own act."""
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
    if "events" in parts:
        for e in call["events"]:
            es = mix.emotions_from_appraisal((appr.get("events") or {}).get(e["ref"]) or {}, ref=e["ref"],
                                             actor=e["actor"], about=e["text"][:60], liking=liking)
            per_item[e["ref"]] = es
            everything += es
    if "concerns" in parts:
        for c in call.get("concerns") or []:
            a = (appr.get("concerns") or {}).get(c["ref"])
            if a is None:  # round two appraised concerns among the events
                a = (appr.get("events") or {}).get(c["ref"]) or {}
            es = mix.concern_emotions(a, a.get("weight") if gate else None, ref=c["ref"],
                                      about=c["text"][:60], liking=liking)
            per_item[c["ref"]] = es
            everything += es
    if "memories" in parts:
        for m in call.get("memories") or []:
            a = (appr.get("memories") or {}).get(m["ref"]) or {}
            es = mix.memory_emotions(a.get("strength"), a.get("tone"), a.get("kinds"), ref=m["ref"],
                                     about=m["text"][:60], multiplier=(multipliers or {}).get(m["ref"], 1.0))
            per_item[m["ref"]] = es
            everything += es
    return per_item, everything


def _occ_top(appr_event, actor, liking):
    """The strongest OCC emotion of one event, desire's three kinds counted
    among them -- what round two's labels can be compared with."""
    from mind import affect_mix as mix

    a = {k: v for k, v in (appr_event or {}).items() if k not in ("stir", "stirs")}
    es = mix.emotions_from_appraisal(a, actor=actor, liking=liking)
    es += mix.stirred((appr_event or {}).get("stir"),
                      {k: p for k, p in ((appr_event or {}).get("stirs") or {}).items() if k in DESIRES})
    es = sorted(es, key=lambda e: -e.intensity)
    return es[0].name if es and es[0].intensity >= 0.15 else "none"


def _r(x, y):
    import numpy as np

    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and x.std() > 0 and y.std() > 0 else float("nan")


def _habituation(calls, clock=False):
    """Per beat, the habituation multiplier of each memory recalled -- the
    owner's model, run along each character's own beats in order."""
    from mind import affect_mix as mix

    out = {}
    for key in sorted({(c["chat"], c["who"]) for c in calls}):
        state, now = {}, 0.0
        for c in sorted((c for c in calls if (c["chat"], c["who"]) == key), key=lambda c: c["turn_idx"]):
            now += c["elapsed_seconds"] / 60.0 if clock and c["elapsed_seconds"] else 1.0
            mults = {}
            for m in c.get("memories") or []:
                mults[m["ref"]], state = mix.recall_lands(state, m["ref"], now)
            out[c["capture"]] = mults
    return out


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
    mults = _habituation(calls, clock=args.clock)
    dulled = [m for per in mults.values() for m in per.values() if m < 1.0]
    print(f"  habituation: {len(dulled)} of {sum(len(p) for p in mults.values())} recalls dulled"
          + (f" (mean multiplier {np.mean(dulled):.2f})" if dulled else ""))

    # (a) event emotions against the utility model's labels, by family and sign
    pairs = []
    for c in calls:
        appr = appraisals[f"{c['capture']}:V"]
        liking = {p["name"]: p["liking"] for p in c["people"]}
        actors = {e["ref"]: e["actor"] for e in c["events"]}
        for ref, lab in (c.get("labels") or {}).items():
            if ref in actors:
                pairs.append((_occ_top((appr.get("events") or {}).get(ref), actors[ref], liking), lab["emotion"]))
    if pairs:
        fam = np.mean([FAMILY.get(a) == FAMILY.get(b) for a, b in pairs])
        sign = lambda n: 0 if n == "none" else (  # noqa: E731
            1 if mix.EMOTION_EFFECTS.get(n, mix.EMOTION_EFFECTS["joy"]).get("pleasure", 0) >= 0 else -1)
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

    # (b) the undercurrent: what the layer beneath stirred, against the reports
    told_neg = [(c["told"].get("under_valence") or 0) < 0 for c in calls]
    print(f"  undercurrent (a negative feeling beneath, at or above {mix.UNDERCURRENT_FLOOR}) on beats "
          f"reporting a negative one ({sum(told_neg)}) / reporting none ({len(calls) - sum(told_neg)}):")
    for label, parts, gate in (("concerns, ungated (round two)", ("concerns",), False),
                               ("concerns, gated by weight", ("concerns",), True),
                               ("memories", ("memories",), True),
                               ("memories and gated concerns", ("concerns", "memories"), True)):
        hits = []
        for c in calls:
            _per, beneath = _emotions(c, appraisals[f"{c['capture']}:V"], multipliers=mults.get(c["capture"]),
                                      gate=gate, parts=parts)
            hits.append(any(e.valence < 0 and e.intensity >= mix.UNDERCURRENT_FLOOR for e in beneath))
        tp = sum(h for h, t in zip(hits, told_neg) if t)
        fp = sum(h for h, t in zip(hits, told_neg) if not t)
        print(f"    {label:30} {tp:3} of {sum(told_neg)}   {fp:3} of {len(calls) - sum(told_neg)}")
    names, weights = {}, []
    for c in calls:
        appr = appraisals[f"{c['capture']}:V"]
        weights += [a["weight"] for a in (appr.get("concerns") or {}).values() if "weight" in a]
        _per, everything = _emotions(c, appr, multipliers=mults.get(c["capture"]))
        _surface, under = mix.surface_and_undercurrent(everything, mix.Mood())
        if isinstance(under, mix.Emotion) and under.source in mix.BENEATH:
            names[(under.source, under.name)] = names.get((under.source, under.name), 0) + 1
    if weights:
        print(f"  concern weights: mean {np.mean(weights):.2f}, share under 1/3 {np.mean([w < 1 / 3 for w in weights]):.0%}")
    print("  the undercurrent named, by source:", sorted(names.items(), key=lambda t: -t[1])[:12])

    # (c) which moods memories stir
    kinds, plain = {}, 0.0
    for c in calls:
        appr = appraisals[f"{c['capture']}:V"]
        _per, mem = _emotions(c, appr, multipliers=mults.get(c["capture"]), parts=("memories",))
        for e in mem:
            if e.name in mix.STANDALONE:
                kinds[e.name] = kinds.get(e.name, 0.0) + e.intensity
            else:
                plain += e.intensity
    total = sum(kinds.values()) + plain
    if total:
        print(f"  memories stir (share of all memory feeling): plain by tone {plain / total:.0%}; "
              + ", ".join(f"{k} {v / total:.0%}" for k, v in sorted(kinds.items(), key=lambda t: -t[1])[:10]))

    # (d) the character's own acts
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

    # (e) the mood, three ways, against the utility model's ratings and the reports
    coords = list(mix.SPECTRUMS) + list(mix.STANDALONE)
    rows = {"direct": {}, "derived": {}, "settled": {}, "ref": {}}
    va = {"direct": [], "derived": [], "settled": [], "told": []}
    # how many standalone moods each reader grades clearly or more, per beat
    selective = {"direct": [], "ref": []}
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
            _per, everything = _emotions(c, appr, multipliers=mults.get(c["capture"]), parts=args.parts.split(","))
            derived, _g = mix.mix(derived, home, everything, dt, reactivity=args.reactivity,
                                  negativity=args.negativity, negative_factor=args.negative_decay)
            settled = mix.settle(mix.decay(settled, home, dt, negative_factor=args.negative_decay), reading,
                                 reactivity=args.reactivity)
            ref = {**(c.get("dims_ref") or {}).get("spectrums", {}), **(c.get("dims_ref") or {}).get("moods", {})}
            if (c.get("dims_ref") or {}).get("moods"):
                selective["direct"].append(sum(1 for n in mix.STANDALONE if reading.get(n, 0) >= 0.6))
                selective["ref"].append(sum(1 for n in mix.STANDALONE if ref.get(n, 0) >= 0.6))
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
    print("  coordinate           n  direct  derived  settled   ref sd  (r against the utility model's rating)")
    means = {"direct": [], "derived": [], "settled": []}
    flat = []
    for name in coords:
        ref = rows["ref"].get(name) or []
        if len(ref) < 5:
            continue
        cells = {m: _r(rows[m][name], ref) for m in ("direct", "derived", "settled")}
        if all(v != v for v in cells.values()):
            flat.append(name)
            continue
        for m, v in cells.items():
            if v == v:
                means[m].append(v)
        print(f"    {name:16} {len(ref):3}  " + "  ".join(f"{cells[m]:7.2f}" for m in ("direct", "derived", "settled"))
              + f"   {np.std(ref):6.2f}")
    print("    mean r            " + "  ".join(f"{np.mean(v):7.2f}" for v in means.values())
          + f"   over {len(means['direct'])} coordinates")
    if flat:
        print("    no variance to score:", ", ".join(flat))
    if selective["ref"]:
        print(f"  standalone moods graded clearly or more per beat: Jev {np.mean(selective['direct']):.1f}, "
              f"the rater {np.mean(selective['ref']):.1f} (of {len(mix.STANDALONE)})")
    told = np.array(va["told"])
    for m in ("direct", "derived", "settled"):
        est = np.array(va[m])
        print(f"  {m:8} vs the character's own report: valence r {_r(est[:, 0], told[:, 0]):.2f}, "
              f"arousal r {_r(est[:, 1], told[:, 1]):.2f}")
    # (f) which coordinates Jev's direct readings move together on
    # every beat rated on both, so the columns line up beat for beat
    full = max((len(v) for v in rows["direct"].values()), default=0)
    names = [n for n in coords if full >= 5 and len(rows["direct"].get(n) or []) == full]
    mat = np.array([rows["direct"][n] for n in names])
    close = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = _r(mat[i], mat[j])
            if v == v and abs(v) >= args.redundant:
                close.append((names[i], names[j], round(v, 2)))
    print(f"  coordinate pairs Jev reads together (|r| >= {args.redundant}):",
          sorted(close, key=lambda t: -abs(t[2]))[:16])
    # (g) what the rater found no coordinate for
    uncovered = [u for c in calls for u in (c.get("dims_ref") or {}).get("uncovered") or []]
    rated = [c for c in calls if (c.get("dims_ref") or {}).get("spectrums")]
    if rated:
        some = sum(1 for c in rated if (c.get("dims_ref") or {}).get("uncovered"))
        words = {}
        for u in uncovered:
            words[u.strip().lower()] = words.get(u.strip().lower(), 0) + 1
        print(f"  uncovered: the rater named a mood no coordinate covers on {some} of {len(rated)} beats:",
              sorted(words.items(), key=lambda t: -t[1])[:25])


FAMILY = {}
for _fam, _names in {
    "good outcome": ("joy", "satisfaction", "gratification", "relief", "pride", "happy_for", "gloating"),
    "hope": ("hope",), "bad outcome": ("distress", "disappointment", "fears_confirmed", "remorse", "shame",
                                       "pity", "resentment", "frustration"),
    "fear": ("fear",), "toward someone, good": ("admiration", "gratitude"),
    "toward someone, bad": ("reproach", "anger"), "desire": ("desire",) + DESIRES, "none": ("none",),
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
    p.add_argument("--arms", default="V,VP", help="which requests to make per beat")
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
    p.add_argument("--parts", default="events,concerns,memories",
                   help="what feeds the derived mood: events, concerns, memories")
    p.add_argument("--negativity", type=float, default=None,
                   help="an unpleasant emotion's weight in a target (default affect_mix.NEGATIVITY_WEIGHT)")
    p.add_argument("--negative-decay", type=float, default=None,
                   help="how much slower pleasure below home decays (default affect_mix.NEGATIVE_DECAY_FACTOR)")
    args = parser.parse_args()
    {"collect": collect, "ask": ask, "label": label, "dimlabel": dimlabel, "score": score}[args.mode](args)


if __name__ == "__main__":
    main()
