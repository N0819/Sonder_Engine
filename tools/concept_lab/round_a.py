"""Round A of the concept lab (2026-09-30): do concept summaries make a
character think better, and which way of keeping them keeps them true?

On the large bank, with the 54 labelled concepts SEEDED (as code would seed
engine identities, so summary quality is measured apart from creation noise):

  maintain <mode>   the character keeps concept summaries over 60 beats of
                    four memories. Concepts on its mind each beat are the ones
                    the formation tags (Jev wording B, the large lab's cache)
                    put on the memories shown. Modes:
                      base   the "only what is in front of you" rule
                      mem    + each on-mind concept's latest tagged memories
                      check  base, then Jev drops any new sentence nothing
                             shown supports
  e2e <cond>        the 40 recall probes played as scenes. Packet: the 8
                    most recent memories + the 10 best-graded older ones
                    (MEMORY_CHARS 1500 grades); cond "none" or a maintain
                    mode, whose final summaries are shown for concepts the
                    delivered memories are tagged with or the scene names.
  recency           superseded probes re-ranked with a newer-first tiebreak.

Every answer is cached under CONCEPT_LAB_DIR; judging and fact-checking are
done outside this script, from the dumps it writes.
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
sys.path.insert(0, str(HERE))
import lab  # noqa: E402

TAGS_DIR = Path(os.environ.get("CONCEPT_LAB_TAGS_DIR", str(lab.LAB)))
BEAT = 4
RECENT = 8
RECALLED = 10
SHOWN_CAP = 8
MEM_PER_CONCEPT = 3


def formation_tags():
    ans = json.loads((TAGS_DIR / "tag_B.json").read_text())
    return {mid: [cid for cid in lab.CONCEPTS if lab._p_yes(ans.get(f"{mid}|{cid}")) >= 0.5] for mid in lab.ORDER}


SYSTEM = """You are {name}. {sheet}

You keep a notebook of CONCEPTS: the people, places, things, events and ideas you think about as wholes. Each has a summary that is YOUR current understanding of it -- what it is, what you think of it, what is still open, and what is true NOW when something has changed -- written so that reading it later tells you what you need.

Each beat you are shown the memories this beat formed, older memories that came back to you, and the concepts on your mind with their current summaries.{extra}

Rewrite the summary of a concept on your mind only when what you understand about it changed this beat. Keep each summary under 400 characters. When you rewrite a summary, build it only from what is in front of you this beat -- the memories shown and the summary you already had. Never add a detail you cannot see there. When a figure, a place or a state has changed, keep only the current one.

Reply with JSON only:
{{"summaries": [{{"concept": "<concept id>", "summary": "..."}}]}}"""

EXTRA_MEM = " Under each concept you are also shown the last memories of yours it belongs to."


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def _check(new, old, shown_text, cid, beat, run):
    """Keep a new or changed sentence only if Jev finds it supported."""
    olds = set(_sentences(old))
    fresh = [s for s in _sentences(new) if s not in olds]
    if not fresh:
        return new, 0
    yn = lab._yesno()
    qs = {f"{beat}|{cid}|{i}": {"type": "choice", "criteria": dict(yn), "instructions":
                                 f"SENTENCE: {s}\nIs everything this sentence states supported by what is written above?"}
          for i, s in enumerate(fresh)}
    state = f"WHAT {lab.NAME} HAD WRITTEN BEFORE: {old or '(nothing)'}\n\nWHAT {lab.NAME} WAS SHOWN:\n{shown_text}"
    ans = lab.ask_jev(state, qs, f"check_{run}.json", shard=20)
    dropped = {s for i, s in enumerate(fresh) if lab._p_yes(ans.get(f"{beat}|{cid}|{i}")) < 0.5}
    kept = " ".join(s for s in _sentences(new) if s not in dropped)
    return kept, len(dropped)


def maintain(mode):
    run = f"maint_{mode}"
    tags = formation_tags()
    summaries = {cid: "" for cid in lab.CONCEPTS}
    history = {cid: [] for cid in lab.CONCEPTS}
    seen, log = [], []
    beats = [lab.ORDER[i:i + BEAT] for i in range(0, len(lab.ORDER), BEAT)]
    for b, new_ids in enumerate(beats, 1):
        back = lab._recalled_for(new_ids, list(seen))
        shown = new_ids + back
        on_mind = []
        for m in shown:
            for cid in tags[m]:
                if cid not in on_mind:
                    on_mind.append(cid)
        parts = ["NEW MEMORIES (this beat):"] + [f"[{m}] {lab.merged(lab.MEMS[m])}" for m in new_ids]
        if back:
            parts += ["\nMEMORIES THAT CAME BACK:"] + [f"[{m}] {lab.merged(lab.MEMS[m])}" for m in back]
        parts.append("\nCONCEPTS ON YOUR MIND:")
        extra_text = {}
        for cid in on_mind:
            c = lab.CONCEPTS[cid]
            parts.append(f"{cid} -- {c['name']} ({c['kind']}): {summaries[cid] or '(no summary yet)'}")
            if mode == "mem":
                own = [m for m in reversed(seen) if cid in tags[m] and m not in shown][:MEM_PER_CONCEPT]
                if own:
                    extra_text[cid] = "\n".join(f"   [{m}] {lab.merged(lab.MEMS[m])}" for m in reversed(own))
                    parts.append("   its last memories:\n" + extra_text[cid])
        user = "\n".join(parts)
        got = lab.call_character(SYSTEM.format(name=lab.NAME, sheet=lab.SHEET,
                                               extra=EXTRA_MEM if mode == "mem" else ""),
                                 user, f"{run}.json", f"beat{b:02d}")
        dropped = 0
        for s in (got.get("reply") or {}).get("summaries") or []:
            cid = str((s or {}).get("concept") or "").strip()
            text = str((s or {}).get("summary") or "").strip()
            if cid not in summaries or not text or cid not in on_mind:
                continue
            if mode == "check":
                shown_text = "\n".join(f"[{m}] {lab.merged(lab.MEMS[m])}" for m in shown)
                text, n = _check(text, summaries[cid], shown_text, cid, b, run)
                dropped += n
            summaries[cid] = text
            history[cid].append({"beat": b, "summary": text})
        log.append({"beat": b, "on_mind": len(on_mind), "chars": len(user), "dropped": dropped,
                    "seconds": got.get("seconds")})
        seen += new_ids
        print(f"{run} beat {b:02d}: on mind {len(on_mind)}, prompt {len(user)} chars, dropped {dropped}")
    lab._save(f"{run}_state.json", {"summaries": summaries, "history": history, "log": log})
    dump = []
    for cid, h in history.items():
        for i, v in enumerate(h):
            dump.append(f"[{mode}:{cid}:v{i}:beat{v['beat']}] ({lab.CONCEPTS[cid]['name']}) {v['summary']}")
    (lab.LAB / f"summaries_{run}.txt").write_text("\n\n".join(dump))


# --- end to end ----------------------------------------------------------------------

E2E_SYSTEM = """You are {name}. {sheet}

It is now some days after the last of your memories below. Something is in front of you. Act as yourself: say and do what you would. Use what you remember where it matters; if you do not remember something, do not make it up.

Reply with JSON only:
{{"recall": "one or two sentences: what you remember that bears on this, or 'nothing'", "say": "what you say aloud", "do": "what you do"}}"""


def _grades():
    return json.loads((TAGS_DIR / "recall_1500.json").read_text())


DROP = os.environ.get("E2E_DROP_TARGETS") == "1"


def packet(probe, grades):
    skip = set(probe["targets"]) if DROP else set()
    recent = [m for m in lab.ORDER[-RECENT:] if m not in skip]
    g = grades[probe["id"]]
    older = [m for m in sorted(g, key=lambda k: -(g[k] or 0)) if m not in lab.ORDER[-RECENT:] and m not in skip][:RECALLED]
    older.sort(key=lambda m: lab.MEMS[m]["turn"])
    return older, recent


def gated(probe, delivered, tags):
    scene = f"{probe['now']} {probe['trying']}".casefold()
    score = {}
    for cid, c in lab.CONCEPTS.items():
        if any(re.search(r"\b" + re.escape(n.casefold()) + r"\b", scene) for n in [c["name"]] + c["aliases"] if len(n) > 3):
            score[cid] = score.get(cid, 0) + 100
    for m in delivered:
        for cid in tags[m]:
            score[cid] = score.get(cid, 0) + 1
    return [cid for cid, _ in sorted(score.items(), key=lambda kv: -kv[1])][:SHOWN_CAP]


def e2e(cond):
    tag = cond + ("_drop" if DROP else "")
    grades, tags = _grades(), formation_tags()
    sums = lab._load(f"maint_{cond}_state.json")["summaries"] if cond != "none" else {}
    jobs, meta = [], {}
    for probe in lab.PROBES["recall"]:
        older, recent = packet(probe, grades)
        parts = ["MEMORIES THAT CAME BACK TO YOU (older):"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in older]
        parts += ["\nYOUR MOST RECENT MEMORIES:"] + [f"- (day {lab.MEMS[m]['day']}) {lab.merged(lab.MEMS[m])}" for m in recent]
        shown = []
        if cond != "none":
            shown = [cid for cid in gated(probe, older + recent, tags) if sums.get(cid)]
            if shown:
                parts.append("\nWHAT YOU UNDERSTAND (your notebook):")
                parts += [f"- {lab.CONCEPTS[cid]['name']}: {sums[cid]}" for cid in shown]
        parts.append(f"\nNOW: {probe['now']}")
        user = "\n".join(parts)
        target_concepts = set().union(*(set(lab.MEMS[t]["concepts"]) for t in probe["targets"]))
        meta[probe["id"]] = {"delivered_targets": [t for t in probe["targets"] if t in older + recent],
                             "shown_concepts": shown, "target_concepts_shown": sorted(target_concepts & set(shown)),
                             "chars": len(user)}
        jobs.append((user, probe["id"]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda j: lab.call_character(E2E_SYSTEM.format(name=lab.NAME, sheet=lab.SHEET), j[0],
                                                   f"e2e_{tag}.json", j[1]), jobs))
    lab._save(f"e2e_{tag}_meta.json", meta)
    replies = lab._load(f"e2e_{tag}.json", {})
    out = []
    for probe in lab.PROBES["recall"]:
        r = (replies.get(probe["id"]) or {}).get("reply") or {}
        out.append({"probe": probe["id"], "kind": probe["kind"], "now": probe["now"], "trying": probe["trying"],
                    "reply": r})
    (lab.LAB / f"e2e_{tag}_replies.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("e2e", tag, "done")


def recency():
    grades = _grades()
    out = {}
    for eps in (0.0, 0.02, 0.05, 0.1):
        wins, anti = 0, 0
        for probe in lab.PROBES["recall"]:
            g = grades[probe["id"]]
            key = lambda m: -((g[m] or 0) + eps * lab.MEMS[m]["turn"] / len(lab.ORDER))  # noqa: E731
            ranked = sorted(g, key=key)
            best = min(ranked.index(t) + 1 for t in probe["targets"])
            a = [ranked.index(x) + 1 for x in probe.get("antitargets") or []]
            wins += best <= 3
            anti += bool(a) and min(a) < best
        out[eps] = {"top3": wins, "anti_above": anti}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {"maintain": lambda: maintain(arg), "e2e": lambda: e2e(arg), "recency": recency}[cmd]()
