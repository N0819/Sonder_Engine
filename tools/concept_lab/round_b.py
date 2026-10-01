"""Round B of the concept lab (2026-09-30): the owner's simpler design.

  "an active concern summary concerning unresolved things that are present,
   then retire those to memory when resolved, with a category name, so it
   comes up if relevant, and leave a majority of concept modelling to mind
   modelling."

  concerns          the character keeps ACTIVE CONCERNS over the large bank's
                    60 beats: open one (name, summary, settled when), update
                    its summary, or resolve it with an outcome. Resolving
                    retires it as a memory row named after the concern.
  grade             Jev grades each retired record against every recall
                    probe, the same questions and state as the bank's rows.
  e2e <cond>        the 40 recall probes with the answer memories REMOVED
                    (recall missed). Conditions:
                      concerns   open concerns shown; retired records join
                                 the recall pool (Jev-graded like any row;
                                 one whose name the scene says always comes)
                      concerns_people  + Round A base summaries for PERSON
                                 concepts only, tag-gated (stand-in for mind
                                 modelling)
"""

from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("CONCEPT_LAB_BANK", "bank_large.json")
os.environ.setdefault("CONCEPT_LAB_PROBES", "probes_large.json")
os.environ.setdefault("E2E_DROP_TARGETS", "1")
sys.path.insert(0, str(HERE))
import lab  # noqa: E402
import round_a as ra  # noqa: E402

SYSTEM = """You are {name}. {sheet}

You keep a short list of ACTIVE CONCERNS: matters still unresolved for you that are live in your life right now -- a question you need answered, a danger, a debt, a decision, a person's trouble you are part of. Not every person or thing: only what is open. Each concern has a summary of where it stands NOW (what you know, what you suspect, what is still open) and what would settle it.

Each beat you are shown the memories this beat formed, older memories that came back to you, and your active concerns.

For each beat:
- OPEN a concern when something new becomes an unresolved matter for you that you will carry across days. Not for a single passing happening.
- UPDATE a concern's summary when where it stands changed this beat. Keep only the current state; build it only from what is in front of you; under 400 characters.
- RESOLVE a concern when it is settled -- answered, done, or given up -- and say how it ended.
Keep the list short: only what is truly open.

Reply with JSON only:
{{"open": [{{"name": "...", "summary": "...", "settled_when": "..."}}],
 "update": [{{"id": "<concern id>", "summary": "..."}}],
 "resolve": [{{"id": "<concern id>", "outcome": "how it ended, in a sentence or two"}}]}}"""


def concerns():
    run = "concerns"
    active, retired, log, seen = {}, [], [], []
    next_id = 1
    beats = [lab.ORDER[i:i + ra.BEAT] for i in range(0, len(lab.ORDER), ra.BEAT)]
    for b, new_ids in enumerate(beats, 1):
        back = lab._recalled_for(new_ids, list(seen))
        parts = ["NEW MEMORIES (this beat):"] + [f"[{m}] {lab.merged(lab.MEMS[m])}" for m in new_ids]
        if back:
            parts += ["\nMEMORIES THAT CAME BACK:"] + [f"[{m}] {lab.merged(lab.MEMS[m])}" for m in back]
        parts.append("\nYOUR ACTIVE CONCERNS:")
        parts += [f"{cid} -- {c['name']}: {c['summary']} (settled when: {c['settled_when']})"
                  for cid, c in active.items()] or ["(none)"]
        user = "\n".join(parts)
        got = lab.call_character(SYSTEM.format(name=lab.NAME, sheet=lab.SHEET), user, f"{run}.json", f"beat{b:02d}")
        reply = got.get("reply") or {}
        last = lab.MEMS[new_ids[-1]]
        opened = resolved = 0
        for u in reply.get("update") or []:
            cid = str((u or {}).get("id") or "").strip()
            if cid in active and str(u.get("summary") or "").strip():
                active[cid]["summary"] = u["summary"].strip()
                active[cid]["updates"] += 1
        for r in reply.get("resolve") or []:
            cid = str((r or {}).get("id") or "").strip()
            if cid in active:
                c = active.pop(cid)
                outcome = str(r.get("outcome") or "").strip()
                retired.append({"id": f"R{cid}", "name": c["name"], "day": last["day"], "turn": last["turn"],
                                "opened_day": c["opened_day"],
                                "text": f"{c['name']} -- resolved. {c['summary']} How it ended: {outcome}"})
                resolved += 1
        for o in reply.get("open") or []:
            if isinstance(o, dict) and str(o.get("name") or "").strip():
                cid = f"c{next_id}"
                next_id += 1
                active[cid] = {"name": o["name"].strip(), "summary": str(o.get("summary") or "").strip(),
                               "settled_when": str(o.get("settled_when") or "").strip(),
                               "opened_day": last["day"], "updates": 0}
                opened += 1
        log.append({"beat": b, "day": last["day"], "active": len(active), "opened": opened, "resolved": resolved,
                    "chars": len(user), "seconds": got.get("seconds"), "error": got.get("error")})
        seen += new_ids
        print(f"beat {b:02d} day {last['day']}: +{opened} -{resolved} active {len(active)}")
    lab._save("concerns_state.json", {"active": active, "retired": retired, "log": log})


def grade():
    from mind import memory_jev
    memory_jev.MEMORY_CHARS = 1500
    st = lab._load("concerns_state.json")
    rows = {r["id"]: {"content": r["text"], "turn_idx": r["turn"]} for r in st["retired"]}
    cache = lab._load("retired_grades.json", {})
    for probe in lab.PROBES["recall"]:
        if probe["id"] in cache or not rows:
            continue
        cache[probe["id"]] = _grade_retry(list(rows), rows, lab._recall_state(probe), len(lab.ORDER) + 1)
        lab._save("retired_grades.json", cache)
    print("graded", len(cache), "probes over", len(rows), "retired records")


def _named(text, name):
    words = [w for w in re.findall(r"[a-z']+", name.casefold()) if len(w) > 3]
    t = text.casefold()
    return bool(words) and sum(w in t for w in words) >= max(1, len(words) // 2 + (len(words) > 2))


def e2e(cond):
    tag = f"{cond}_drop"
    grades, tags = ra._grades(), ra.formation_tags()
    st = lab._load("concerns_state.json")
    retired = {r["id"]: r for r in st["retired"]}
    rgrades = lab._load("retired_grades.json", {})
    people = lab._load("maint_base_state.json")["summaries"] if cond == "concerns_people" else {}
    jobs, meta = [], {}
    for probe in lab.PROBES["recall"]:
        skip = set(probe["targets"])
        recent = [m for m in lab.ORDER[-ra.RECENT:] if m not in skip]
        g = {k: v for k, v in grades[probe["id"]].items() if k not in skip and k not in lab.ORDER[-ra.RECENT:]}
        g.update(rgrades.get(probe["id"], {}))
        scene = f"{probe['now']} {probe['trying']}"
        forced = [rid for rid, r in retired.items() if _named(scene, r["name"])]
        pool = forced + [k for k in sorted(g, key=lambda k: -(g[k] or 0)) if k not in forced]
        older = pool[:ra.RECALLED]

        def when(k):
            return retired[k]["turn"] if k in retired else lab.MEMS[k]["turn"]

        older.sort(key=when)
        lines = []
        for k in older:
            if k in retired:
                lines.append(f"- (day {retired[k]['day']}) {retired[k]['text']}")
            else:
                lines.append(f"- (day {lab.MEMS[k]['day']}) {lab.merged(lab.MEMS[k])}")
        parts = ["MEMORIES THAT CAME BACK TO YOU (older):"] + lines
        parts += ["\nYOUR MOST RECENT MEMORIES:"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in recent]
        if st["active"]:
            parts.append("\nWHAT IS STILL OPEN FOR YOU:")
            parts += [f"- {c['name']}: {c['summary']} (settled when: {c['settled_when']})" for c in st["active"].values()]
        shown_people = []
        if people:
            gated = ra.gated(probe, [k for k in older if k not in retired] + recent, tags)
            shown_people = [cid for cid in gated if lab.CONCEPTS[cid]["kind"] == "person" and people.get(cid)]
            if shown_people:
                parts.append("\nWHAT YOU MAKE OF PEOPLE HERE:")
                parts += [f"- {lab.CONCEPTS[cid]['name']}: {people[cid]}" for cid in shown_people]
        parts.append(f"\nNOW: {probe['now']}")
        user = "\n".join(parts)
        meta[probe["id"]] = {"retired_delivered": [k for k in older if k in retired], "forced": forced,
                             "people_shown": shown_people, "chars": len(user)}
        jobs.append((user, probe["id"]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda j: lab.call_character(ra.E2E_SYSTEM.format(name=lab.NAME, sheet=lab.SHEET), j[0],
                                                   f"e2e_{tag}.json", j[1]), jobs))
    lab._save(f"e2e_{tag}_meta.json", meta)
    replies = lab._load(f"e2e_{tag}.json", {})
    out = [{"probe": p["id"], "kind": p["kind"], "reply": (replies.get(p["id"]) or {}).get("reply") or {}}
           for p in lab.PROBES["recall"]]
    (lab.LAB / f"e2e_{tag}_replies.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("e2e", tag, "done")


# --- the owner's refinement: concern TAGS on memories ----------------------------------
#
# "all memories can be tagged with active concern, which then later when it
#  finally gets resolved gets its own concept tag. And the final active concern
#  summary gets shown whenever a memory with that concept shows up."
#
# Each memory formed while a concern was open is asked (Jev) whether it bears
# on the concern; a yes tags it. At recall, every concern tagged on a delivered
# memory shows its summary -- the final one and how it ended when resolved,
# the current one when open -- and open concerns always show. The tag question
# names the concern by its LATEST summary, which a live engine would not yet
# have when the memory formed: slightly optimistic.

def _grade_retry(*args):
    import time
    from mind import memory_jev
    for attempt in range(5):
        try:
            return memory_jev.grade_net(*args)
        except Exception as exc:  # noqa: BLE001
            print("  grade retry", attempt, str(exc)[:100])
            time.sleep(5 + 5 * attempt)
    raise RuntimeError("grading failed five times")


def _concern_rows():
    st = lab._load("concerns_state.json")
    first_turn = {}
    for mid in lab.ORDER:
        first_turn.setdefault(lab.MEMS[mid]["day"], lab.MEMS[mid]["turn"])
    rows = []
    for cid, c in st["active"].items():
        rows.append({"id": cid, "name": c["name"], "summary": c["summary"], "open": True,
                     "from": first_turn[c["opened_day"]], "to": len(lab.ORDER),
                     "shown": f"{c['name']} (still open): {c['summary']} (settled when: {c['settled_when']})"})
    for r in st["retired"]:
        rows.append({"id": r["id"], "name": r["name"], "summary": r["text"], "open": False,
                     "from": first_turn[r["opened_day"]], "to": r["turn"],
                     "shown": f"(settled day {r['day']}) {r['text']}"})
    return rows


def tag_concerns():
    yn = lab._yesno()
    qs = {}
    for c in _concern_rows():
        for mid in lab.ORDER:
            if c["from"] <= lab.MEMS[mid]["turn"] <= c["to"]:
                qs[f"{mid}|{c['id']}"] = {"type": "choice", "criteria": dict(yn), "instructions":
                                          f"MEMORY: {lab.merged(lab.MEMS[mid])}\nDoes this memory bear on this matter of "
                                          f"yours -- {c['name']}: {c['summary']}"}
    ans = lab.ask_jev(f"YOU ARE {lab.NAME}.", qs, "concern_tags.json", shard=40)
    tags = {}
    for key in qs:
        if lab._p_yes(ans.get(key)) >= 0.5:
            mid, cid = key.split("|")
            tags.setdefault(mid, []).append(cid)
    lab._save("concern_tags_final.json", tags)
    print("asked", len(qs), "tagged memories", len(tags), "tags", sum(len(v) for v in tags.values()))


def e2e_tags(cond):
    tag = f"{cond}_drop"
    grades, ftags = ra._grades(), ra.formation_tags()
    ctags = lab._load("concern_tags_final.json", {})
    rows = {c["id"]: c for c in _concern_rows()}
    people = lab._load("maint_base_state.json")["summaries"] if cond == "ctags_people" else {}
    jobs, meta = [], {}
    for probe in lab.PROBES["recall"]:
        older, recent = ra.packet(probe, grades)
        delivered = older + recent
        count = {}
        for m in delivered:
            for cid in ctags.get(m, []):
                count[cid] = count.get(cid, 0) + 1
        shown = [cid for cid, c in rows.items() if c["open"]]
        shown += [cid for cid, _ in sorted(count.items(), key=lambda kv: -kv[1]) if cid not in shown]
        shown = shown[:ra.SHOWN_CAP]
        parts = ["MEMORIES THAT CAME BACK TO YOU (older):"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in older]
        parts += ["\nYOUR MOST RECENT MEMORIES:"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in recent]
        if shown:
            parts.append("\nMATTERS THESE MEMORIES BELONG TO:")
            parts += [f"- {rows[cid]['shown']}" for cid in shown]
        shown_people = []
        if people:
            gated = ra.gated(probe, delivered, ftags)
            shown_people = [cid for cid in gated if lab.CONCEPTS[cid]["kind"] == "person" and people.get(cid)]
            if shown_people:
                parts.append("\nWHAT YOU MAKE OF PEOPLE HERE:")
                parts += [f"- {lab.CONCEPTS[cid]['name']}: {people[cid]}" for cid in shown_people]
        parts.append(f"\nNOW: {probe['now']}")
        user = "\n".join(parts)
        meta[probe["id"]] = {"concerns_shown": shown, "people_shown": shown_people, "chars": len(user)}
        jobs.append((user, probe["id"]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda j: lab.call_character(ra.E2E_SYSTEM.format(name=lab.NAME, sheet=lab.SHEET), j[0],
                                                   f"e2e_{tag}.json", j[1]), jobs))
    lab._save(f"e2e_{tag}_meta.json", meta)
    replies = lab._load(f"e2e_{tag}.json", {})
    out = [{"probe": p["id"], "kind": p["kind"], "reply": (replies.get(p["id"]) or {}).get("reply") or {}}
           for p in lab.PROBES["recall"]]
    (lab.LAB / f"e2e_{tag}_replies.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("e2e", tag, "done")


# --- the concern tag and summary WITH JEV (the owner, same day) ----------------------------
#
# 1. jev_gate: which matters to show is asked of Jev against the scene, one
#    question per concern, instead of counted from the delivered memories' tags.
# 2. regrade: recall grading sees each memory's concerns ("part of: ...") the
#    way it already sees who was with it, and the open concerns as what is
#    still unsettled.

def _gate_answers():
    rows = _concern_rows()
    yn = lab._yesno()
    out = {}
    for probe in lab.PROBES["recall"]:
        qs = {f"{probe['id']}|{c['id']}": {"type": "choice", "criteria": dict(yn), "instructions":
                                           f"A MATTER OF YOURS: {c['name']} -- {c['summary']}\n"
                                           f"Does this matter bear on what is in front of you now?"}
              for c in rows}
        state = f"YOU ARE {lab.NAME}.\n\nWHAT IS IN FRONT OF YOU NOW: {probe['now']}"
        out.update(lab.ask_jev(state, qs, "concern_gate.json", shard=40))
    return out


def e2e_jevgate(cond="cgate"):
    tag = f"{cond}_drop"
    grades = ra._grades()
    rows = {c["id"]: c for c in _concern_rows()}
    ans = _gate_answers()
    jobs, meta = [], {}
    for probe in lab.PROBES["recall"]:
        older, recent = ra.packet(probe, grades)
        scored = sorted(((lab._p_yes(ans.get(f"{probe['id']}|{cid}")), cid) for cid in rows), reverse=True)
        shown = [cid for p, cid in scored if p >= 0.5][:ra.SHOWN_CAP]
        parts = ["MEMORIES THAT CAME BACK TO YOU (older):"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in older]
        parts += ["\nYOUR MOST RECENT MEMORIES:"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in recent]
        if shown:
            parts.append("\nMATTERS OF YOURS THAT BEAR ON THIS:")
            parts += [f"- {rows[cid]['shown']}" for cid in shown]
        parts.append(f"\nNOW: {probe['now']}")
        user = "\n".join(parts)
        meta[probe["id"]] = {"concerns_shown": shown, "chars": len(user)}
        jobs.append((user, probe["id"]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda j: lab.call_character(ra.E2E_SYSTEM.format(name=lab.NAME, sheet=lab.SHEET), j[0],
                                                   f"e2e_{tag}.json", j[1]), jobs))
    lab._save(f"e2e_{tag}_meta.json", meta)
    replies = lab._load(f"e2e_{tag}.json", {})
    out = [{"probe": p["id"], "kind": p["kind"], "reply": (replies.get(p["id"]) or {}).get("reply") or {}}
           for p in lab.PROBES["recall"]]
    (lab.LAB / f"e2e_{tag}_replies.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("e2e", tag, "done")


def regrade():
    from mind import memory_jev
    memory_jev.MEMORY_CHARS = 1500
    ctags = lab._load("concern_tags_final.json", {})
    rows = {c["id"]: c for c in _concern_rows()}
    st = lab._load("concerns_state.json")
    unsettled = [f"{c['name']}: {c['summary']}" for c in st["active"].values()]
    mems = {}
    for mid in lab.ORDER:
        names = [rows[c]["name"] for c in ctags.get(mid, []) if c in rows]
        label = f"(part of: {'; '.join(names)}) " if names else ""
        mems[mid] = {"content": label + lab.merged(lab.MEMS[mid]), "turn_idx": lab.MEMS[mid]["turn"]}
    cache = lab._load("regrade_1500.json", {})
    for probe in lab.PROBES["recall"]:
        if probe["id"] in cache:
            continue
        state = memory_jev.memory_state({"name": lab.NAME, "drive": lab.SHEET}, probe["now"],
                                        {"goal": probe["trying"]}, unsettled)
        cache[probe["id"]] = _grade_retry(lab.ORDER, mems, state, len(lab.ORDER) + 1)
        lab._save("regrade_1500.json", cache)
    print("regraded", len(cache))


def regrade_report():
    old, new = ra._grades(), lab._load("regrade_1500.json", {})
    out = {}
    for name, g_all in (("plain", old), ("concern_labels", new)):
        rows = []
        for probe in lab.PROBES["recall"]:
            g = g_all.get(probe["id"])
            if not g:
                continue
            ranked = sorted(g, key=lambda k: -(g[k] or 0))
            best = min(ranked.index(t) + 1 for t in probe["targets"])
            anti = [ranked.index(a) + 1 for a in probe.get("antitargets") or []]
            rows.append((probe["kind"], best, bool(anti) and min(anti) < best))
        out[name] = {"hit@1": sum(b <= 1 for _, b, _ in rows), "hit@3": sum(b <= 3 for _, b, _ in rows),
                     "hit@10": sum(b <= 10 for _, b, _ in rows), "anti_above": sum(a for _, _, a in rows),
                     "n": len(rows)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {"concerns": concerns, "grade": grade, "e2e": lambda: e2e(arg), "tag": tag_concerns,
     "e2e_tags": lambda: e2e_tags(arg), "e2e_jevgate": lambda: e2e_jevgate(), "regrade": regrade,
     "regrade_report": regrade_report}[cmd]()
