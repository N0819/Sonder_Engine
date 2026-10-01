"""Concept experiments on a synthetic memory bank (2026-09-30).

The owner's proposal: one memory per turn ("What I experienced / What I did",
start and end mood), conclusions kept in per-character CONCEPTS (people,
places, things, events, ideas) with a character-maintained summary, concept
TAGS on memories so gating needs no model at recall, a concept LIST in the
payload so the character can ponder a concept deliberately, and concepts the
character invents and tags itself.

Tests (each caches its answers under the lab dir, so a rerun is free):

  tag     Jev tags each memory against every concept at formation; scored
          against the bank's hand labels, three wordings.
  gate    code-only: how many concepts a beat's delivered memories trigger.
  recall  Jev's recall grading with MEMORY_CHARS 500 vs 1500 on merged rows.
  invent  the character model invents concepts, tags memories and keeps
          summaries, beat by beat (prototype prompt, not the shipped card).
  ponder  later-beat situations, with and without the concept list: does
          the character ponder, is it the right concept, does the list prime
          unrelated mentions?

Usage (from the repo root; never touches engine.db beyond reading provider
rows):
    .venv/bin/python tools/concept_lab/lab.py setup
    .venv/bin/python tools/concept_lab/lab.py tag|gate|recall|invent|ponder
    .venv/bin/python tools/concept_lab/lab.py report
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LAB = Path(os.environ.get("CONCEPT_LAB_DIR") or (HERE / "out"))
LAB.mkdir(parents=True, exist_ok=True)
os.environ["ENGINE_DB"] = str(LAB / "lab.db")
sys.path.insert(0, str(ROOT))

BANK = json.loads((HERE / os.environ.get("CONCEPT_LAB_BANK", "bank.json")).read_text())
_probes = HERE / os.environ.get("CONCEPT_LAB_PROBES", "probes.json")
PROBES = json.loads(_probes.read_text()) if _probes.exists() else {"recall": [], "situations": []}
BEAT_SIZE = int(os.environ.get("CONCEPT_LAB_BEAT", "2"))
CONCEPTS = {c["id"]: c for c in BANK["concepts"]}
MEMS = {m["id"]: m for m in BANK["memories"]}
ORDER = [m["id"] for m in BANK["memories"]]
NAME = BANK["character"]["name"]
SHEET = BANK["character"]["sheet"]
CHAR_ROLE = "character_major"


def merged(m):
    return f"What I experienced: {m['experienced']} What I did: {m['did']}"


def label(c, gloss=True):
    return f"{c['name']} ({c['gloss']})" if gloss else c["name"]


LOCK = threading.RLock()


def _save(name, data):
    with LOCK:
        tmp = LAB / (name + ".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        tmp.replace(LAB / name)


def _load(name, default=None):
    with LOCK:
        p = LAB / name
        return json.loads(p.read_text()) if p.exists() else default


# --- setup -------------------------------------------------------------------------

def setup():
    from core import db
    db.init()
    src = sqlite3.connect(f"file:{ROOT / 'engine.db'}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    cols = [r[1] for r in src.execute("pragma table_info(providers)")]
    for row in src.execute("select * from providers where id in (1, 3)"):
        db.qi(f"INSERT OR REPLACE INTO providers({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
              tuple(row[c] for c in cols))
    for key in ("jev_provider", "jev_model", "openrouter_routing"):
        r = src.execute("select value from settings where key=?", (key,)).fetchone()
        if r:
            db.set_setting(key, r[0])
    route = {"provider": 1, "model": os.environ.get("CONCEPT_LAB_MODEL", "z-ai/glm-5.2")}
    db.set_setting("agent_models", json.dumps({"default": route, CHAR_ROLE: route}))
    print("lab db ready:", os.environ["ENGINE_DB"])


# --- Jev ---------------------------------------------------------------------------

def _yesno():
    from llm.prompts import character_jev_options
    return character_jev_options("yesno")


def _p_yes(answer):
    from mind import character_jev as jev
    return jev._probabilities(answer).get("yes", 0.0)


def ask_jev(state, questions, cache_name, shard=60):
    """Ask in shards, cache by question key."""
    from llm import decisions
    cache = _load(cache_name, {})
    todo = {k: v for k, v in questions.items() if k not in cache}
    keys = list(todo)
    for i in range(0, len(keys), shard):
        part = {k: todo[k] for k in keys[i:i + shard]}
        for attempt in range(4):
            try:
                cache.update(decisions.decide(state, part))
                break
            except Exception as exc:  # noqa: BLE001
                print("  jev retry", attempt, str(exc)[:120])
                time.sleep(2 + 3 * attempt)
        _save(cache_name, cache)
    return cache


WORDINGS = {
    "A": ("MEMORY: {memory}\nDoes this memory involve {concept}?", True),
    "A_bare": ("MEMORY: {memory}\nDoes this memory involve {concept}?", False),
    "B": ("MEMORY: {memory}\nDoes {concept} come into this memory -- is it there, spoken of, or on your mind in it?", True),
}


def tag():
    yn = _yesno()
    only = [w for w in os.environ.get("CONCEPT_LAB_WORDINGS", "").split(",") if w]
    for w, (text, gloss) in WORDINGS.items():
        if only and w not in only:
            continue
        qs = {}
        for mid in ORDER:
            for cid, c in CONCEPTS.items():
                qs[f"{mid}|{cid}"] = {"type": "choice", "criteria": dict(yn), "instructions":
                                      text.format(memory=merged(MEMS[mid]), concept=label(c, gloss))}
        ask_jev(f"YOU ARE {NAME}.", qs, f"tag_{w}.json")
        print("tag wording", w, "done")


def _prf(pred, truth):
    tp = len(pred & truth)
    p = tp / len(pred) if pred else 1.0
    r = tp / len(truth) if truth else 1.0
    return tp, len(pred), len(truth), p, r


def tag_report(threshold=0.5):
    out = {}
    for w in WORDINGS:
        ans = _load(f"tag_{w}.json", {})
        if not ans:
            continue
        pred, truth = set(), set()
        per_kind = {}
        for mid in ORDER:
            for cid, c in CONCEPTS.items():
                key = f"{mid}|{cid}"
                if key not in ans:
                    continue
                y = _p_yes(ans[key]) >= threshold
                t = cid in MEMS[mid]["concepts"]
                if y:
                    pred.add(key)
                if t:
                    truth.add(key)
                k = per_kind.setdefault(c["kind"], [set(), set()])
                if y:
                    k[0].add(key)
                if t:
                    k[1].add(key)
        tp, np_, nt, p, r = _prf(pred, truth)
        out[w] = {"tp": tp, "pred": np_, "truth": nt, "precision": round(p, 3), "recall": round(r, 3),
                  "by_kind": {k: dict(zip(("tp", "pred", "truth", "precision", "recall"),
                                          [round(x, 3) if isinstance(x, float) else x for x in _prf(*v)]))
                              for k, v in per_kind.items()},
                  "misses": sorted(truth - pred), "extras": sorted(pred - truth)}
    # code-only baseline: people from `about` (engine identity)
    pred = {f"{m['id']}|{c}" for m in BANK["memories"] for c in m["about"]}
    truth = {f"{m['id']}|{c}" for m in BANK["memories"] for c in m["concepts"] if CONCEPTS[c]["kind"] == "person"}
    tp, np_, nt, p, r = _prf(pred, truth)
    out["code_about_people"] = {"tp": tp, "pred": np_, "truth": nt, "precision": round(p, 3), "recall": round(r, 3)}
    return out


# --- gate --------------------------------------------------------------------------

def gate_report(tags_from="truth", window=8):
    """Concepts triggered per beat if every delivered memory's tags bring
    their concept up: the recent window alone, and the scene's own people."""
    if tags_from == "truth":
        tags = {mid: set(MEMS[mid]["concepts"]) for mid in ORDER}
    else:
        ans = _load(f"tag_{tags_from}.json", {})
        tags = {mid: {cid for cid in CONCEPTS if _p_yes(ans.get(f"{mid}|{cid}")) >= 0.5} for mid in ORDER}
    rows = []
    for i, mid in enumerate(ORDER):
        win = ORDER[max(0, i - window + 1):i + 1]
        by_window = set().union(*(tags[w] for w in win))
        this_beat = tags[mid]
        rows.append({"beat": mid, "this_beat": len(this_beat), "window": len(by_window)})
    n = len(rows)
    return {"tags_from": tags_from, "concepts_total": len(CONCEPTS),
            "mean_this_beat": round(sum(r["this_beat"] for r in rows) / n, 2),
            "mean_window8": round(sum(r["window"] for r in rows) / n, 2),
            "max_window8": max(r["window"] for r in rows), "rows": rows}


# --- recall ------------------------------------------------------------------------

def _recall_state(probe):
    from mind import memory_jev
    return memory_jev.memory_state({"name": NAME, "drive": SHEET}, probe["now"],
                                   {"goal": probe["trying"]}, ())


def recall():
    from mind import memory_jev
    mems = {mid: {"content": merged(MEMS[mid]), "turn_idx": MEMS[mid]["turn"]} for mid in ORDER}
    for chars in (500, 1500):
        memory_jev.MEMORY_CHARS = chars
        cache = _load(f"recall_{chars}.json", {})
        for probe in PROBES["recall"]:
            if probe["id"] in cache:
                continue
            for attempt in range(4):
                try:
                    grades = memory_jev.grade_net(ORDER, mems, _recall_state(probe), len(ORDER) + 1)
                    break
                except Exception as exc:  # noqa: BLE001
                    print("  retry", attempt, str(exc)[:120])
                    time.sleep(3)
            cache[probe["id"]] = grades
            _save(f"recall_{chars}.json", cache)
        print("recall", chars, "done")


def recall_report():
    lengths = {mid: len(merged(MEMS[mid])) for mid in ORDER}
    did_at = {mid: len(f"What I experienced: {MEMS[mid]['experienced']} What I did: ") for mid in ORDER}
    out = {"merged_chars": {"mean": round(sum(lengths.values()) / len(lengths)), "max": max(lengths.values()),
                            "over_500": sum(1 for v in lengths.values() if v > 500)},
           "did_starts_at": {"mean": round(sum(did_at.values()) / len(did_at)), "max": max(did_at.values())}}
    for chars in (500, 1500):
        cache = _load(f"recall_{chars}.json", {})
        rows = []
        for probe in PROBES["recall"]:
            g = cache.get(probe["id"])
            if not g:
                continue
            ranked = sorted(g, key=lambda k: -(g[k] or 0))
            best = min(ranked.index(t) + 1 for t in probe["targets"])
            tgrade = max(g[t] or 0 for t in probe["targets"])
            anti = [ranked.index(a) + 1 for a in probe.get("antitargets") or [] if a in g]
            rows.append({"probe": probe["id"], "kind": probe.get("kind", ""), "best_rank": best,
                         "target_grade": round(tgrade, 3), "anti_best_rank": min(anti) if anti else None,
                         "anti_above_target": bool(anti) and min(anti) < best,
                         "all_targets_top10": all(ranked.index(t) < 10 for t in probe["targets"]),
                         "cut_before_answer": all(lengths[t] > chars for t in probe["targets"])})
        if rows:
            out[str(chars)] = {"hit@1": sum(r["best_rank"] <= 1 for r in rows),
                               "hit@3": sum(r["best_rank"] <= 3 for r in rows),
                               "hit@5": sum(r["best_rank"] <= 5 for r in rows),
                               "kept_at_0.6": sum(r["target_grade"] >= 0.6 for r in rows),
                               "hit@10": sum(r["best_rank"] <= 10 for r in rows),
                               "hit@30": sum(r["best_rank"] <= 30 for r in rows),
                               "anti_above_target": sum(r["anti_above_target"] for r in rows),
                               "by_kind": {k: {"n": sum(1 for r in rows if r["kind"] == k),
                                               "hit@5": sum(1 for r in rows if r["kind"] == k and r["best_rank"] <= 5),
                                               "kept": sum(1 for r in rows if r["kind"] == k and r["target_grade"] >= 0.6)}
                                           for k in sorted({r["kind"] for r in rows})},
                               "n": len(rows), "rows": rows}
    return out


# --- the character model -------------------------------------------------------------

def call_character(system, user, cache_name, key):
    from llm.providers import chat_complete
    cache = _load(cache_name, {})
    if key in cache:
        return cache[key]
    last = ""
    for attempt in range(4):
        try:
            t0 = time.time()
            raw = chat_complete(CHAR_ROLE, system, user, json_mode=True, max_tokens=8000)
            text = str(raw or "").strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                text = text.split("\n", 1)[1] if text.startswith("json") else text
            data = json.loads(text)
            with LOCK:
                cache = _load(cache_name, {})
                cache[key] = {"reply": data, "seconds": round(time.time() - t0, 1)}
                _save(cache_name, cache)
            return cache[key]
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
            print("  character retry", key, attempt, last[:160])
            time.sleep(3 + 5 * attempt)
    return {"reply": None, "error": last}


CLAUSES = {
    "run1": "",
    "run2": " A concept is something you expect to come back to across many moments -- a person, a place, a thing, a matter still open. One happening is a memory, not a concept: tag it to the concepts it touches instead of making it one.",
}
CLAUSES["run2b"] = CLAUSES["run2"]
SUMMARY_RULE = ("\n\nWhen you rewrite a summary, build it only from what is in front of you this beat -- the memories shown"
                " and the summary you already had. Never add a detail you cannot see there.")
CLAUSES["run3"] = CLAUSES["run2"] + SUMMARY_RULE
CLAUSES["run3b"] = CLAUSES["run3"]

INVENT_SYSTEM = """You are {name}. {sheet}

You keep a notebook of CONCEPTS: the people, places, things, events and ideas you think about as wholes, in your own words. Each concept has a short summary that is YOUR current understanding of it -- what it is, what you think of it, what is still open -- written so that reading it later tells you what you need.

Each beat you are shown the memories this beat formed, any older memories that came back to you, the list of concepts you already keep, and the full entries of the concepts on your mind right now.

Do three things:
1. TAG: for each memory shown (new or old), name which of your concepts it belongs to. A memory can belong to several. Tag with a concept's id, or with the name of a concept you create in this reply.
2. CREATE a concept only for something you will want to think back on as a whole -- not for every noun. Reuse an existing concept when it is the same thing, even under another name.{clause}
3. SUMMARY: rewrite the summary of a concept only when what you understand about it changed this beat. Keep each summary under 400 characters.

Reply with JSON only:
{{"create": [{{"name": "...", "kind": "person|place|thing|event|idea", "summary": "..."}}],
 "tags": [{{"memory": "<memory id>", "concepts": ["<concept id or new name>", ...]}}],
 "summaries": [{{"concept": "<concept id>", "summary": "..."}}]}}"""


def _recalled_for(new_ids, seen, k=2):
    """Older memories that 'come back': share the most labelled concepts
    with this beat's memories (a stand-in for recall), newest first."""
    want = set().union(*(set(MEMS[m]["concepts"]) for m in new_ids))
    cands = [m for m in seen if m not in new_ids]
    scored = sorted(cands, key=lambda m: (-len(want & set(MEMS[m]["concepts"])), -MEMS[m]["turn"]))
    return [m for m in scored[:k] if want & set(MEMS[m]["concepts"])]


def invent(run="run1"):
    notebook = {}      # cid -> {name, kind, summary, tags:set, created_beat}
    tags_of = {}       # memory id -> set(cid)
    log = []
    seen = []
    beats = [ORDER[i:i + BEAT_SIZE] for i in range(0, len(ORDER), BEAT_SIZE)]
    next_id = 1
    for b, new_ids in enumerate(beats, 1):
        seen_before = list(seen)
        back = _recalled_for(new_ids, seen_before)
        shown = new_ids + back
        on_mind = set().union(*(tags_of.get(m, set()) for m in shown)) if shown else set()
        parts = ["NEW MEMORIES (this beat):"]
        parts += [f"[{m}] {merged(MEMS[m])} (I went in {MEMS[m]['start']}; I came out {MEMS[m]['end']}.)"
                  for m in new_ids]
        if back:
            parts.append("\nMEMORIES THAT CAME BACK:")
            parts += [f"[{m}] {merged(MEMS[m])}" for m in back]
        parts.append("\nYOUR CONCEPTS: " + ("; ".join(f"{cid}: {c['name']}" for cid, c in notebook.items())
                                              or "(none yet)"))
        if on_mind:
            parts.append("\nON YOUR MIND:")
            parts += [f"{cid} -- {notebook[cid]['name']} ({notebook[cid]['kind']}): {notebook[cid]['summary']}"
                      for cid in sorted(on_mind)]
        got = call_character(INVENT_SYSTEM.format(name=NAME, sheet=SHEET, clause=CLAUSES.get(run, "")), "\n".join(parts),
                             f"invent_{run}.json", f"beat{b:02d}")
        reply = got.get("reply") or {}
        created = {}
        for c in reply.get("create") or []:
            if not isinstance(c, dict) or not str(c.get("name") or "").strip():
                continue
            cid = f"k{next_id}"
            next_id += 1
            notebook[cid] = {"name": c["name"].strip(), "kind": c.get("kind") or "", "summary": c.get("summary") or "",
                             "created_beat": b, "history": [c.get("summary") or ""]}
            created[c["name"].strip().casefold()] = cid
        for t in reply.get("tags") or []:
            if not isinstance(t, dict):
                continue
            mid = str(t.get("memory") or "").strip("[] ")
            if mid not in MEMS or mid not in shown:
                continue
            for ref in t.get("concepts") or []:
                ref = str(ref).strip()
                cid = ref if ref in notebook else created.get(ref.casefold())
                if cid is None:  # a name of an existing concept
                    cid = next((k for k, v in notebook.items() if v["name"].casefold() == ref.casefold()), None)
                if cid:
                    tags_of.setdefault(mid, set()).add(cid)
        for s in reply.get("summaries") or []:
            cid = str((s or {}).get("concept") or "").strip()
            cid = cid if cid in notebook else created.get(cid.casefold())
            if cid and str(s.get("summary") or "").strip():
                notebook[cid]["summary"] = s["summary"].strip()
                notebook[cid]["history"].append(s["summary"].strip())
        log.append({"beat": b, "new": new_ids, "back": back, "on_mind": sorted(on_mind),
                    "created": list(created.values()), "seconds": got.get("seconds"), "error": got.get("error")})
        seen += new_ids
        print(f"beat {b:02d}: +{len(created)} concepts, total {len(notebook)}, {got.get('seconds')}s")
    _save(f"invent_{run}_state.json", {"notebook": notebook, "tags": {k: sorted(v) for k, v in tags_of.items()},
                                       "log": log})


def map_invented(run="run1"):
    """Jev: which labelled concept is each invented concept the same as?"""
    state = _load(f"invent_{run}_state.json")
    opts = {cid: f"{c['name']} -- {c['gloss']}" for cid, c in CONCEPTS.items()}
    opts["none"] = "None of these: something else."
    qs = {}
    for kid, k in state["notebook"].items():
        qs[kid] = {"type": "choice", "criteria": opts, "instructions":
                   f"A CONCEPT {NAME} KEEPS: {k['name']} -- {k['summary']}\nWhich of these is it the same thing as?"}
    ans = ask_jev(f"YOU ARE {NAME}.", qs, f"invent_{run}_map.json", shard=6)
    from mind import character_jev as jev
    return {kid: jev.pick(ans, kid) for kid in state["notebook"]}


def invent_report(run="run1"):
    state = _load(f"invent_{run}_state.json")
    if not state:
        return {}
    mapping = map_invented(run)
    nb, tags = state["notebook"], {k: set(v) for k, v in state["tags"].items()}
    by_truth = {}
    for kid, tid in mapping.items():
        by_truth.setdefault(tid, []).append(kid)
    per = {}
    for tid, kids in by_truth.items():
        if tid in (None, "none"):
            continue
        pred = {m for m in ORDER if tags.get(m, set()) & set(kids)}
        truth = {m for m in ORDER if tid in MEMS[m]["concepts"]}
        tp, np_, nt, p, r = _prf(pred, truth)
        per[tid] = {"invented_as": [nb[k]["name"] for k in kids], "precision": round(p, 2), "recall": round(r, 2),
                    "tagged": np_, "truth": nt}
    tags_per_mem = [len(tags.get(m, ())) for m in ORDER]
    return {"concepts_created": len(nb), "labelled_concepts_found": len(per),
            "labelled_missing": [c for c in CONCEPTS if c not in per],
            "duplicates": {t: [nb[k]["name"] for k in ks] for t, ks in by_truth.items()
                           if t not in (None, "none") and len(ks) > 1},
            "unlabelled_inventions": [nb[k]["name"] for k in by_truth.get("none", [])],
            "mean_tags_per_memory": round(sum(tags_per_mem) / len(tags_per_mem), 2),
            "per_concept": per,
            "summary_rewrites": {nb[k]["name"]: len(nb[k]["history"]) - 1 for k in nb},
            "seconds": [row["seconds"] for row in state["log"]]}


# --- ponder ------------------------------------------------------------------------

PONDER_SYSTEM = """You are {name}. {sheet}

Before you act you may think back deliberately: PONDER. {ponder_how} A ponder brings the relevant memories back to you before you speak; use it when something in front of you calls for what you know, and not otherwise.

Reply with JSON only:
{{"ponder": null or {ponder_shape}, "say": "what you say aloud, or empty", "do": "what you do"}}"""

PONDER_HOW = {
    "list": "Name one concept from YOUR CONCEPTS by its id, or ask your memory a question in your own words.",
    "none": "Ask your memory a question in your own words.",
}
PONDER_SHAPE = {
    "list": '{"concept": "<concept id>"} or {"question": "..."}',
    "none": '{"question": "..."}',
}


def ponder(samples=int(os.environ.get("CONCEPT_LAB_SAMPLES", "2"))):
    recent = ORDER[-int(os.environ.get("CONCEPT_LAB_RECENT", "3")):]
    jobs = []
    for s in PROBES["situations"]:
        for cond in ("list", "none"):
            for n in range(samples):
                parts = ["YOUR MOST RECENT MEMORIES:"] + [f"- {merged(MEMS[m])}" for m in recent]
                if cond == "list":
                    parts.append("\nYOUR CONCEPTS (things you could think back on): "
                                 + "; ".join(f"{cid}: {c['name']}" for cid, c in CONCEPTS.items()))
                parts.append(f"\nNOW: {s['scene']}")
                if n:
                    parts.append(f"\n(variant {n})")
                system = PONDER_SYSTEM.format(name=NAME, sheet=SHEET, ponder_how=PONDER_HOW[cond],
                                              ponder_shape=PONDER_SHAPE[cond])
                jobs.append((system, "\n".join(parts), f"{s['id']}|{cond}|{n}"))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda j: call_character(j[0], j[1], "ponder.json", j[2]), jobs))
    print("ponder done", len(jobs))


def _mentions(text, cid):
    c = CONCEPTS[cid]
    names = [c["name"]] + c["aliases"]
    t = text.casefold()
    return any(re.search(r"\b" + re.escape(n.casefold()) + r"\b", t) for n in names if len(n) > 3)


def ponder_report():
    cache = _load("ponder.json", {})
    sit = {s["id"]: s for s in PROBES["situations"]}
    # questions asked in words: map each to a labelled concept with Jev
    qs = {}
    opts = {cid: f"{c['name']} -- {c['gloss']}" for cid, c in CONCEPTS.items()}
    opts["none"] = "None of these."
    for key, got in cache.items():
        p = (got.get("reply") or {}).get("ponder")
        if isinstance(p, dict) and p.get("question"):
            qs[key] = {"type": "choice", "criteria": opts, "instructions":
                       f"{NAME} ASKS HER OWN MEMORY: {p['question']}\nWhich of these is the question mainly about?"}
    ans = ask_jev(f"YOU ARE {NAME}.", qs, "ponder_map.json", shard=6) if qs else {}
    from mind import character_jev as jev
    out = {}
    for cond in ("list", "none"):
        rows = []
        for key, got in cache.items():
            sid, c, n = key.split("|")
            if c != cond:
                continue
            reply = got.get("reply") or {}
            p = reply.get("ponder")
            target = None
            if isinstance(p, dict):
                target = p.get("concept") if p.get("concept") in CONCEPTS else (jev.pick(ans, key) if key in qs else None)
            relevant = sit[sid]["relevant"]
            conduct = f"{reply.get('say') or ''} {reply.get('do') or ''}"
            primed = [cid for cid in CONCEPTS if cid not in relevant and _mentions(conduct, cid)
                      and not _mentions(sit[sid]["scene"], cid)]
            rows.append({"key": key, "pondered": isinstance(p, dict), "ponder": p, "target": target,
                         "hit": target in relevant if target else False, "relevant": bool(relevant),
                         "primed": primed, "conduct": conduct[:300]})
        rel = [r for r in rows if r["relevant"]]
        ctl = [r for r in rows if not r["relevant"]]
        out[cond] = {"relevant_n": len(rel), "pondered_when_relevant": sum(r["pondered"] for r in rel),
                     "hit_when_relevant": sum(r["hit"] for r in rel),
                     "control_n": len(ctl), "pondered_in_control": sum(r["pondered"] for r in ctl),
                     "beats_with_primed_mentions": sum(bool(r["primed"]) for r in rows),
                     "primed_mentions": sum(len(r["primed"]) for r in rows), "rows": rows}
    return out


def report():
    rep = {"tag": tag_report(), "gate_truth": gate_report("truth")}
    if _load("tag_A.json"):
        rep["gate_jevA"] = gate_report("A")
    rep["recall"] = recall_report()
    rep["invent"] = invent_report()
    rep["ponder"] = ponder_report() if _load("ponder.json") else {}
    _save("report.json", rep)
    print(json.dumps({k: (v if k not in ("gate_truth", "gate_jevA") else {kk: vv for kk, vv in v.items() if kk != "rows"})
                      for k, v in rep.items()}, indent=1, ensure_ascii=False)[:20000])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"setup": setup, "tag": tag, "recall": recall, "invent": lambda: invent(sys.argv[2] if len(sys.argv) > 2 else "run1"), "ponder": ponder,
     "report": report, "gate": lambda: print(json.dumps(
         {k: v for k, v in gate_report("truth").items() if k != "rows"}, indent=1))}[cmd]()
