"""Round C of the concept lab (2026-09-30): the concern lifecycle, fixed with
two borrowed mechanisms, and the superseded-fact link.

  concerns   as round B, plus:
             - MERGE ON OPEN (Mem0's update-against-similar): a proposed
               concern is compared with the three most similar concerns, open
               or retired (word overlap here; the engine would use its
               vectors); Jev asks whether it is the same matter. Same matter
               -> the old concern is updated, or reopened with its history,
               instead of a stranger being opened.
             - RESOLUTION BY COMMITMENT (Klinger's current concerns: a concern
               lasts from commitment until the goal is reached or given up):
               a resolve the character proposes is checked by Jev -- achieved
               / given up by you / only quiet for now / still live -- and only
               the first two retire it.
  links      the superseded link (Zep's invalidation, adapted): each memory
             is compared with its five most similar older memories; Jev asks
             whether the new one changes something the older one states as
             true. A yes records superseded_by on the older row.
  e2e <cond> the 40 recall probes with the answer memories removed:
               concerns_c        round C's concerns, retired to memory
               concerns_c_links  + when a delivered memory is superseded and
                                 its successor is not delivered, the
                                 successor is pulled in beside it
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("CONCEPT_LAB_BANK", "bank_large.json")
os.environ.setdefault("CONCEPT_LAB_PROBES", "probes_large.json")
os.environ.setdefault("E2E_DROP_TARGETS", "1")
sys.path.insert(0, str(HERE))
import lab  # noqa: E402
import round_a as ra  # noqa: E402
import round_b as rb  # noqa: E402

STOP = set("the a an and or of to in on at for with from by my me i was were is it that this her his he she they them "
           "we our as be had have has not no but so if then than there their what when who which about into".split())


def _words(text):
    return [w for w in re.findall(r"[a-z']+", (text or "").casefold()) if w not in STOP and len(w) > 2]


def _sim(a, b):
    wa, wb = set(_words(a)), set(_words(b))
    return len(wa & wb) / math.sqrt(len(wa) * len(wb)) if wa and wb else 0.0


SETTLED = {"achieved": "It is achieved or answered: what would settle it has happened.",
           "given_up": "You have given it up, deliberately.",
           "quiet": "It is only quiet for now; nothing has actually settled it.",
           "live": "It is still live."}


DORMANT_AFTER = 30  # memory-turns untouched; mirrors affect.INTENT_DORMANT_AFTER


def concerns(run="concerns_c", merge=True, dormancy=None):
    concerns_all, active, log, seen = {}, set(), [], []
    retired_order = []
    next_id = 1
    events = Counter()
    beats = [lab.ORDER[i:i + ra.BEAT] for i in range(0, len(lab.ORDER), ra.BEAT)]
    for b, new_ids in enumerate(beats, 1):
        back = lab._recalled_for(new_ids, list(seen))
        shown = new_ids + back
        parts = ["NEW MEMORIES (this beat):"] + [f"[{m}] {lab.merged(lab.MEMS[m])}" for m in new_ids]
        if back:
            parts += ["\nMEMORIES THAT CAME BACK:"] + [f"[{m}] {lab.merged(lab.MEMS[m])}" for m in back]
        parts.append("\nYOUR ACTIVE CONCERNS:")
        parts += [f"{cid} -- {concerns_all[cid]['name']}: {concerns_all[cid]['summary']} "
                  f"(settled when: {concerns_all[cid]['settled_when']})" for cid in sorted(active)] or ["(none)"]
        user = "\n".join(parts)
        got = lab.call_character(rb.SYSTEM.format(name=lab.NAME, sheet=lab.SHEET), user, f"{run}.json", f"beat{b:02d}")
        reply = got.get("reply") or {}
        last = lab.MEMS[new_ids[-1]]
        shown_text = "\n".join(f"[{m}] {lab.merged(lab.MEMS[m])}" for m in shown)
        for u in reply.get("update") or []:
            cid = str((u or {}).get("id") or "").strip()
            if cid in active and str(u.get("summary") or "").strip():
                concerns_all[cid]["summary"] = u["summary"].strip()
                concerns_all[cid]["touched"] = last["turn"]
                concerns_all[cid]["history"].append({"beat": b, "summary": u["summary"].strip()})
        # resolution, checked
        proposals = [(str((r or {}).get("id") or "").strip(), str((r or {}).get("outcome") or "").strip())
                     for r in reply.get("resolve") or []]
        proposals = [(cid, out) for cid, out in proposals if cid in active]
        if proposals:
            qs = {f"{b}|{cid}": {"type": "choice", "criteria": dict(SETTLED), "instructions":
                                 f"A MATTER OF YOURS: {concerns_all[cid]['name']} -- {concerns_all[cid]['summary']} "
                                 f"(settled when: {concerns_all[cid]['settled_when']})\n"
                                 f"YOU SAY IT ENDED: {out}\nGiven what just happened, where does it stand?"}
                  for cid, out in proposals}
            ans = lab.ask_jev(f"YOU ARE {lab.NAME}.\n\nWHAT JUST HAPPENED:\n{shown_text}", qs, f"{run}_settle.json", shard=10)
            from mind import character_jev as jev
            for cid, out in proposals:
                verdict = jev.pick(ans, f"{b}|{cid}") or "live"
                events[f"resolve_{verdict}"] += 1
                if verdict in ("achieved", "given_up"):
                    c = concerns_all[cid]
                    active.discard(cid)
                    c["retired"] = {"day": last["day"], "turn": last["turn"], "outcome": out, "how": verdict}
                    retired_order.append(cid)
        # opening, merged against the similar
        for o in reply.get("open") or []:
            if not (isinstance(o, dict) and str(o.get("name") or "").strip()):
                continue
            text = f"{o['name']} {o.get('summary') or ''}"
            cands = sorted(concerns_all, key=lambda k: -_sim(text, concerns_all[k]["name"] + " " + concerns_all[k]["summary"]))[:3]
            cands = [k for k in cands if _sim(text, concerns_all[k]["name"] + " " + concerns_all[k]["summary"]) > 0.05]
            same = None
            if not merge:
                cands = [k for k in cands if concerns_all[k].get("retired")]
            if cands:
                opts = {k: f"{concerns_all[k]['name']} -- {concerns_all[k]['summary'][:200]}"
                           f"{' (settled earlier)' if concerns_all[k].get('retired') else ''}" for k in cands}
                opts["new"] = "None of these: it is a different matter."
                q = {f"{b}|open|{next_id}": {"type": "choice", "criteria": opts, "instructions":
                                             f"A MATTER YOU WANT TO START TRACKING: {o['name']} -- {o.get('summary') or ''}\n"
                                             f"Is it the same matter as one of these?"}}
                ans = lab.ask_jev(f"YOU ARE {lab.NAME}.", q, f"{run}_merge.json", shard=10)
                from mind import character_jev as jev
                pick = jev.pick(ans, f"{b}|open|{next_id}")
                same = pick if pick in concerns_all else None
            if same:
                c = concerns_all[same]
                if c.get("retired"):
                    events["reopened"] += 1
                    c["reopened"] = c.get("reopened", 0) + 1
                    c.pop("retired")
                    if same in retired_order:
                        retired_order.remove(same)
                else:
                    events["merged_into_open"] += 1
                active.add(same)
                c["touched"] = last["turn"]
                if str(o.get("summary") or "").strip():
                    c["summary"] = o["summary"].strip()
                    c["history"].append({"beat": b, "summary": c["summary"]})
            else:
                cid = f"c{next_id}"
                concerns_all[cid] = {"name": o["name"].strip(), "summary": str(o.get("summary") or "").strip(),
                                     "settled_when": str(o.get("settled_when") or "").strip(),
                                     "opened_day": last["day"], "history": [], "touched": last["turn"]}
                active.add(cid)
                events["opened_new"] += 1
            next_id += 1
        if dormancy:
            for cid in sorted(active):
                c = concerns_all[cid]
                if last["turn"] - c.get("touched", last["turn"]) >= dormancy:
                    active.discard(cid)
                    c["retired"] = {"day": last["day"], "turn": last["turn"], "how": "let_go",
                                    "outcome": "It went quiet; nothing moved it for a long while, and I let it go."}
                    retired_order.append(cid)
                    events["let_go"] += 1
        log.append({"beat": b, "day": last["day"], "active": len(active), "chars": len(user),
                    "seconds": got.get("seconds"), "error": got.get("error")})
        seen += new_ids
        print(f"beat {b:02d} day {last['day']}: active {len(active)} {dict(events)}")
    retired = [{"id": f"R{cid}", "name": concerns_all[cid]["name"], "day": concerns_all[cid]["retired"]["day"],
                "turn": concerns_all[cid]["retired"]["turn"], "opened_day": concerns_all[cid]["opened_day"],
                "text": f"{concerns_all[cid]['name']} -- resolved ({concerns_all[cid]['retired']['how'].replace('_', ' ')}). "
                        f"{concerns_all[cid]['summary']} How it ended: {concerns_all[cid]['retired']['outcome']}"}
               for cid in retired_order]
    open_ = {cid: {k: concerns_all[cid][k] for k in ("name", "summary", "settled_when", "opened_day")} for cid in active}
    lab._save(f"{run}_state.json", {"active": open_, "retired": retired, "all": concerns_all,
                                        "events": dict(events), "log": log})


# --- superseded links --------------------------------------------------------------------

def links():
    docs = {m: _words(lab.merged(lab.MEMS[m])) for m in lab.ORDER}
    df = Counter(w for ws in docs.values() for w in set(ws))
    n = len(docs)

    def vec(ws):
        tf = Counter(ws)
        v = {w: (1 + math.log(c)) * math.log(n / df[w]) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}

    vecs = {m: vec(ws) for m, ws in docs.items()}
    yn = lab._yesno()
    qs = {}
    for i, new in enumerate(lab.ORDER):
        older = lab.ORDER[:i]
        near = sorted(older, key=lambda o: -sum(vecs[new].get(w, 0) * x for w, x in vecs[o].items()))[:5]
        for o in near:
            qs[f"{new}|{o}"] = {"type": "choice", "criteria": dict(yn), "instructions":
                                f"OLDER MEMORY: {lab.merged(lab.MEMS[o])}\n\nNEWER MEMORY: {lab.merged(lab.MEMS[new])}\n\n"
                                f"Does the newer memory change something the older one states as true -- a figure, "
                                f"a state, where something is, who has it, whether something still holds?"}
    ans = lab.ask_jev(f"YOU ARE {lab.NAME}.", qs, "links.json", shard=20)
    sup = {}
    for key in qs:
        if lab._p_yes(ans.get(key)) >= 0.5:
            new, old = key.split("|")
            sup.setdefault(old, []).append(new)
    lab._save("links_final.json", sup)
    # check against the probes' superseded pairs: does following the chain
    # from an outdated row reach the current one?
    hits = total = 0
    for p in lab.PROBES["recall"]:
        if p["kind"] != "superseded":
            continue
        for a in p["antitargets"]:
            total += 1
            hits += bool(_chain(a, sup) & set(p["targets"]))
    print("asked", len(qs), "older memories marked superseded", len(sup), "links", sum(len(v) for v in sup.values()),
          f"| superseded-probe old rows linked to a target: {hits}/{total}")


def _chain(m, sup, limit=8):
    """Every memory reachable from m by superseded_by links."""
    seen, todo = set(), [m]
    while todo and len(seen) < 50:
        cur = todo.pop()
        for x in sup.get(cur, []):
            if x not in seen:
                seen.add(x)
                todo.append(x)
    return seen


def _chain_latest(m, sup, limit=6):
    """The newest memory reached by following superseded_by links."""
    cur = m
    for _ in range(limit):
        nxt = [x for x in sup.get(cur, []) if lab.MEMS[x]["turn"] > lab.MEMS[cur]["turn"]]
        if not nxt:
            return cur
        cur = max(nxt, key=lambda x: lab.MEMS[x]["turn"])
    return cur


def e2e(cond):
    tag = f"{cond}_drop"
    grades = ra._grades()
    run = "concerns_e" if cond.startswith("concerns_e") else "concerns_d" if cond.startswith("concerns_d") else "concerns_c"
    st = lab._load(f"{run}_state.json")
    retired = {r["id"]: r for r in st["retired"]}
    rgrades = lab._load("retired_c_grades.json" if run == "concerns_c" else f"retired_{run}_grades.json", {})
    sup = lab._load("links_final.json", {}) if "links" in cond else {}
    gate = _open_gate(st, run) if cond.endswith("gate") else None
    jobs, meta = [], {}
    for probe in lab.PROBES["recall"]:
        skip = set(probe["targets"])
        recent = [m for m in lab.ORDER[-ra.RECENT:] if m not in skip]
        g = {k: v for k, v in grades[probe["id"]].items() if k not in skip and k not in lab.ORDER[-ra.RECENT:]}
        g.update(rgrades.get(probe["id"], {}))
        scene = f"{probe['now']} {probe['trying']}"
        forced = [rid for rid, r in retired.items() if rb._named(scene, r["name"])]
        pool = forced + [k for k in sorted(g, key=lambda k: -(g[k] or 0)) if k not in forced]
        older = pool[:ra.RECALLED]
        pulled = []
        if sup:
            have = set(older) | set(recent)
            for k in list(older):
                if k in retired:
                    continue
                latest = _chain_latest(k, sup)
                if latest != k and latest not in have:
                    pulled.append(latest)
                    have.add(latest)
            older = older + pulled

        def when(k):
            return retired[k]["turn"] if k in retired else lab.MEMS[k]["turn"]

        older.sort(key=when)
        lines = [f"- (day {retired[k]['day']}) {retired[k]['text']}" if k in retired
                 else f"- (day {lab.MEMS[k]['day']}) {lab.merged(lab.MEMS[k])}" for k in older]
        parts = ["MEMORIES THAT CAME BACK TO YOU (older):"] + lines
        parts += ["\nYOUR MOST RECENT MEMORIES:"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in recent]
        open_ids = list(st["active"])
        if gate is not None:
            scored = sorted(((gate.get(f"{probe['id']}|{cid}", 0.0), cid) for cid in open_ids), reverse=True)
            open_ids = [cid for p_, cid in scored if p_ >= 0.5][:OPEN_CAP]
        if open_ids:
            parts.append("\nWHAT IS STILL OPEN FOR YOU:")
            parts += [f"- {st['active'][cid]['name']}: {st['active'][cid]['summary']} "
                      f"(settled when: {st['active'][cid]['settled_when']})" for cid in open_ids]
        parts.append(f"\nNOW: {probe['now']}")
        user = "\n".join(parts)
        meta[probe["id"]] = {"pulled": pulled, "pulled_targets": [p for p in pulled if p in skip], "chars": len(user)}
        jobs.append((user, probe["id"]))
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda j: lab.call_character(ra.E2E_SYSTEM.format(name=lab.NAME, sheet=lab.SHEET), j[0],
                                                   f"e2e_{tag}.json", j[1]), jobs))
    lab._save(f"e2e_{tag}_meta.json", meta)
    replies = lab._load(f"e2e_{tag}.json", {})
    out = [{"probe": p["id"], "kind": p["kind"], "reply": (replies.get(p["id"]) or {}).get("reply") or {}}
           for p in lab.PROBES["recall"]]
    (lab.LAB / f"e2e_{tag}_replies.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("e2e", tag, "done;", sum(len(v["pulled"]) for v in meta.values()), "pulled,",
          sum(len(v["pulled_targets"]) for v in meta.values()), "of them answer memories")


OPEN_CAP = 6


def _open_gate(st, run):
    """Jev: does this open matter bear on what is in front of you now?"""
    yn = lab._yesno()
    qs = {}
    for probe in lab.PROBES["recall"]:
        for cid, c in st["active"].items():
            qs[f"{probe['id']}|{cid}"] = {"type": "choice", "criteria": dict(yn), "instructions":
                                          f"A MATTER STILL OPEN FOR YOU: {c['name']} -- {c['summary']}\n"
                                          f"WHAT IS IN FRONT OF YOU NOW: {probe['now']}\n"
                                          f"Does this matter bear on what is in front of you now?"}
    ans = lab.ask_jev(f"YOU ARE {lab.NAME}.", qs, f"{run}_opengate.json", shard=40)
    return {k: lab._p_yes(ans.get(k)) for k in qs}


def grade(run="concerns_c"):
    st = lab._load(f"{run}_state.json")
    rows = {r["id"]: {"content": r["text"], "turn_idx": r["turn"]} for r in st["retired"]}
    name = "retired_c_grades.json" if run == "concerns_c" else f"retired_{run}_grades.json"
    cache = lab._load(name, {})
    for probe in lab.PROBES["recall"]:
        if probe["id"] in cache or not rows:
            continue
        from mind import memory_jev
        memory_jev.MEMORY_CHARS = 1500
        cache[probe["id"]] = rb._grade_retry(list(rows), rows, lab._recall_state(probe), len(lab.ORDER) + 1)
        lab._save(name, cache)
    print("graded", len(cache))


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {"concerns": lambda: concerns(arg or "concerns_c", merge=(arg or "concerns_c") == "concerns_c",
                                  dormancy=DORMANT_AFTER if arg == "concerns_e" else None),
     "links": links, "grade": lambda: grade(arg or "concerns_c"), "e2e": lambda: e2e(arg)}[cmd]()
