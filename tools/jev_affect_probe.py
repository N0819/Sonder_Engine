"""Does the decision model's event appraisal, with the mood math, say how a
character feels?

An experiment instrument for `mind/affect_appraisal.py` and
`mind/affect_mix.py` (designed with the owner on 2026-09-26,
`docs/design/DESIGN_JEV_CHARACTER_PASS.md`, "Emotion and mood" and "The mood
math"). On captured character calls that carry per-event perception:

`collect` -- per character and chat, in order, one call per beat: the events
the character perceived (quoted, with actors), the people it has a standing
with and its liking of each, the memories recall delivered, the story time
that passed, and the mood the character model reported on that call.

`ask` -- the appraisal through the engine's own module, by arm (`--arms`):
`E` the events alone; `M` + the delivered memories in the state, each asked
whether it stirs a feeling now; `C` + the character's unsettled concerns,
appraised like events (rumination); `P` the pass after the turn -- the
character's own speech, actions and held-back want, appraised as events it
brought about. `score --concern-weight` sets a concern's share of the
surface mood; `score --post` carries the `P` push into the next beat.

`label` -- the `utility` model (GLM on NanoGPT), which never sees Jev's
answers, names the emotion the character most likely feels about each event
and toward whom, from OCC's list.

`score` -- (a) per event, the strongest emotion the mix derives against the
label, exact and by sign, against a shuffled baseline; (b) the mood as its
OWN trajectory -- started from the first beat's mood and never again shown
the character's reports -- against what the character reported, level and
change; (c) both arms.

Usage:
    ENGINE_DB=<a copy> python tools/jev_affect_probe.py collect --chats 150,151 --out calls.json
    ENGINE_DB=<a copy> python tools/jev_affect_probe.py ask --calls calls.json --out appraisals.json
    ENGINE_DB=<a copy> python tools/jev_affect_probe.py label --calls calls.json
    python tools/jev_affect_probe.py score --calls calls.json --appraisals appraisals.json
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
#: `E` events; `M` + the delivered memories (in the state, and each asked
#: whether it stirs a feeling); `C` + the character's unsettled concerns,
#: appraised like events. `P` is the pass after the character's turn (the
#: owner: "a pass after the character turn finishes to see how their actions
#: speech and thoughts affect their mood"): its own speech, actions and the
#: want it held back, appraised as events it brought about.
ARMS = ("E", "EM", "EC", "ECM")
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


def _state(call, arm):
    b = call["blocks"]
    parts = [b["identity"], b["mood"], b["people"], b["happened"]]
    if "C" in arm and call.get("concerns"):
        parts.append("WHAT IS STILL UNSETTLED FOR YOU:\n" + "\n".join(f"- {c['ref']}: {c['text']}"
                                                                    for c in call["concerns"]))
    if "M" in arm:
        parts.append(b["remembered"])
    if arm == "P" and call.get("acts"):
        parts.append("WHAT YOU JUST DID:\n" + "\n".join(f"- {a['ref']}: {a['text']}" for a in call["acts"]))
    return "\n\n".join(p for p in parts if p)


def _appraised(call, arm):
    """The events an arm appraises: this beat's, plus the concerns in `C`;
    in `P`, the character's own acts."""
    if arm == "P":
        return call.get("acts") or []
    return call["events"] + (call.get("concerns") or [] if "C" in arm else [])


def _source(ref, arm):
    return "act" if arm == "P" else ("concern" if str(ref).startswith("c") else "event")


def ask(args):
    from mind import affect_appraisal as appraisal

    calls = json.loads(Path(args.calls).read_text())
    out = Path(args.out)
    done = json.loads(out.read_text()) if out.exists() else {}
    arms = [a for a in args.arms.split(",") if a in ARMS or a == "P"]
    jobs = [(c, arm) for c in calls for arm in arms if f"{c['capture']}:{arm}" not in done]

    def run(job):
        call, arm = job
        mems = call["memories"] if "M" in arm else ()
        return f"{call['capture']}:{arm}", appraisal.appraise(_state(call, arm), _appraised(call, arm),
                                                            call["people"], mems, language="en")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (key, result) in enumerate(pool.map(run, jobs), 1):
            done[key] = result
            if n % 20 == 0 or n == len(jobs):
                out.write_text(json.dumps(done), encoding="utf-8")
                print(f"{n} of {len(jobs)} appraisals")
    out.write_text(json.dumps(done), encoding="utf-8")


def label(args):
    from agents.common import jparse
    from llm.providers import chat_complete

    path = Path(args.calls)
    calls = json.loads(path.read_text())
    todo = [c for c in calls if "labels" not in c]

    def run(call):
        user = _state(call, "E") + "\n\nEVENT IDS: " + ", ".join(e["ref"] for e in call["events"])
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


def _emotions(call, appr, habit, now, arm="E"):
    """The mix's emotions for one beat: per event (and per concern in the `C`
    arms), and per memory with its habituation. Returns (per-event emotion
    lists, all emotions, habit)."""
    from mind import affect_mix as mix

    liking = {p["name"]: p["liking"] for p in call["people"]}
    per_event, everything = {}, []
    for e in _appraised(call, arm):
        es = mix.emotions_from_appraisal((appr.get("events") or {}).get(e["ref"]) or {}, ref=e["ref"],
                                         actor=e["actor"], about=e["text"][:60], liking=liking)
        for x in es:
            x.source = _source(e["ref"], arm)
        per_event[e["ref"]] = es
        everything += es
    for m in call["memories"]:
        a = (appr.get("memories") or {}).get(m["ref"])
        if not a:
            continue
        multiplier, habit = mix.recall_lands(habit, m["ref"], now)
        me = mix.memory_emotion(a.get("strength", 0), a.get("tone", 0), ref=m["ref"],
                                about=m["text"][:60], multiplier=multiplier)
        if me:
            everything.append(me)
    return per_event, everything, habit


def score(args):
    import numpy as np

    from mind import affect_mix as mix

    calls = json.loads(Path(args.calls).read_text())
    appraisals = json.loads(Path(args.appraisals).read_text())
    if args.chats:
        keep = {int(c) for c in args.chats.split(",")}
        calls = [c for c in calls if c["chat"] in keep]

    def r(x, y):
        x, y = np.asarray(x, float), np.asarray(y, float)
        return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and x.std() > 0 and y.std() > 0 else float("nan")

    print(f"{len(calls)} beats; characters {sorted({c['name'] for c in calls})}"
          + (f"; concern weight {args.concern_weight}" if args.concern_weight is not None else "")
          + ("; with the pass after the turn" if args.post else ""))
    weights = {"concern": args.concern_weight} if args.concern_weight is not None else None
    for arm in ARMS:
        if not all(f"{c['capture']}:{arm}" in appraisals for c in calls):
            continue
        # (a) event emotions against the utility model's labels
        pairs, under_found, under_told = [], 0, 0
        for c in calls:
            appr = appraisals.get(f"{c['capture']}:{arm}") or {}
            per_event, everything, _h = _emotions(c, appr, {}, c["turn_idx"], arm)
            if (c["told"].get("under_valence") or 0) < 0:
                under_told += 1
                under_found += any(e.pad[0] < 0 and e.intensity >= 0.15 for e in everything)
            for ref, lab in (c.get("labels") or {}).items():
                es = sorted(per_event.get(ref) or [], key=lambda e: -e.intensity)
                ours = es[0].name if es and es[0].intensity >= 0.15 else "none"
                pairs.append((ours, lab["emotion"]))
        if pairs:
            exact = np.mean([a == b for a, b in pairs])
            sign = lambda n: 0 if n == "none" else (1 if mix.EMOTION_PAD[n][0] >= 0 else -1)  # noqa: E731
            same = np.mean([sign(a) == sign(b) for a, b in pairs])
            rng = random.Random(3)
            ours = [a for a, _ in pairs]
            base_exact, base_sign = [], []
            for _ in range(200):
                shuffled = ours[:]
                rng.shuffle(shuffled)
                base_exact.append(np.mean([a == b for a, (_x, b) in zip(shuffled, pairs)]))
                base_sign.append(np.mean([sign(a) == sign(b) for a, (_x, b) in zip(shuffled, pairs)]))
            print(f"  {arm}: event emotion vs label ({len(pairs)} events): exact {exact:.0%} "
                  f"(shuffled {np.mean(base_exact):.0%}), same sign {same:.0%} (shuffled {np.mean(base_sign):.0%})")
        if under_told:
            print(f"  {arm}: a negative feeling (>= 0.15) on {under_found} of the {under_told} beats whose own "
                  f"reported undercurrent is negative")
        # (b) the mood as its own trajectory, per character and chat
        sims, tolds, dsims, dtolds = [], [], [], []
        for key in sorted({(c["chat"], c["who"]) for c in calls}):
            seq = sorted((c for c in calls if (c["chat"], c["who"]) == key), key=lambda c: c["turn_idx"])
            first = seq[0]
            hv = first["home"]["valence"] if first["home"]["valence"] is not None else 0.0
            ha = first["home"]["arousal"] if first["home"]["arousal"] is not None else 0.5
            home = mix.Mood(float(hv), float(ha) * 2 - 1, 0.0)
            ev = first["entering"]["valence"] if first["entering"]["valence"] is not None else hv
            ea = first["entering"]["arousal"] if first["entering"]["arousal"] is not None else ha
            mood = mix.Mood(float(ev), float(ea) * 2 - 1, 0.0)
            habit, clock, prev = {}, 0.0, None
            for c in seq:
                dt = c["elapsed_seconds"] / 60.0 if args.clock and c["elapsed_seconds"] else 1.0
                clock += dt
                appr = appraisals.get(f"{c['capture']}:{arm}") or {}
                _pe, everything, habit = _emotions(c, appr, habit, clock, arm)
                mood, _trace = mix.mix(mood, home, everything, dt, reactivity=args.reactivity,
                                       weights=weights)
                # The character reports during its call, so the comparison
                # point is here -- before the pass after its turn, whose push
                # is carried into the next beat.
                sim = mix.engine_affect(mood)
                told = (float(c["told"]["valence"] or 0), float(c["told"]["arousal"] or 0))
                sims.append((sim["valence"], sim["arousal"]))
                tolds.append(told)
                if prev is not None:
                    dsims.append((sim["valence"] - prev[0][0], sim["arousal"] - prev[0][1]))
                    dtolds.append((told[0] - prev[1][0], told[1] - prev[1][1]))
                prev = ((sim["valence"], sim["arousal"]), told)
                post = appraisals.get(f"{c['capture']}:P") if args.post else None
                if post:
                    _pp, own, _h2 = _emotions(c, post, {}, clock, "P")
                    mood, _t2 = mix.mix(mood, home, own, 0, reactivity=args.reactivity, weights=weights)
        s, t = np.array(sims), np.array(tolds)
        ds, dt_ = np.array(dsims), np.array(dtolds)
        print(f"  {arm}: own trajectory vs reports: valence r {r(s[:, 0], t[:, 0]):.2f} "
              f"(sign {np.mean(np.sign(s[:, 0]) == np.sign(t[:, 0])):.0%}), arousal r {r(s[:, 1], t[:, 1]):.2f}; "
              f"change: valence r {r(ds[:, 0], dt_[:, 0]):.2f}, arousal r {r(ds[:, 1], dt_[:, 1]):.2f}")
    if args.show:
        for c in calls[:args.show]:
            appr = appraisals.get(f"{c['capture']}:EM") or {}
            _pe, everything, _h = _emotions(c, appr, {}, c["turn_idx"])
            surface, under = mix.surface_and_undercurrent(everything, mix.Mood())
            top = sorted(everything, key=lambda e: -e.intensity)[:4]
            print(f"\n  chat {c['chat']} idx {c['turn_idx']} {c['name']}\n    told: {c['told']['surface']}"
                  f" | beneath: {c['told'].get('undercurrent')}\n    mix:  " + "; ".join(
                      f"{e.name} {e.intensity:.2f} ({e.about[:40]})" for e in top)
                  + (f"\n    labels: " + ", ".join(f"{k}: {v['emotion']}" for k, v in (c.get('labels') or {}).items())))


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
    p.add_argument("--arms", default="E,EM")
    p = sub.add_parser("label")
    p.add_argument("--calls", required=True)
    p.add_argument("--workers", type=int, default=3)
    p = sub.add_parser("score")
    p.add_argument("--calls", required=True)
    p.add_argument("--appraisals", required=True)
    p.add_argument("--chats", default="")
    p.add_argument("--reactivity", type=float, default=0.25)
    p.add_argument("--clock", action="store_true", help="decay by story minutes instead of one unit a beat")
    p.add_argument("--post", action="store_true", help="apply the pass after the turn (arm P)")
    p.add_argument("--concern-weight", type=float, default=None,
                   help="a concern's weight in the centre (default: affect_mix.CONCERN_WEIGHT)")
    p.add_argument("--show", type=int, default=0)
    args = parser.parse_args()
    {"collect": collect, "ask": ask, "label": label, "score": score}[args.mode](args)


if __name__ == "__main__":
    main()
