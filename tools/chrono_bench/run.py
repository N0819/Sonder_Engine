"""Saltmere: a planted bank for chronological recall (2026-10-06).

The owner: "build a synthetic database or update a database to have everything
needed and test a character model against it." `bank.json` is Mara Vell's
memory over 310 turns in the engine's one-memory-per-turn form (436 rows with
the inference rows and a 20-row seeded past), written from a bible with 25
answers planted at exact turns and distractors planted after them, checked by
code and by five adversarial readers (`docs/experiments/CHRONO_RECALL_2026_10_06.md`
§2). `questions.json` holds Wren's 26 questions with their planted turns;
`router_heldout.json` 80 labelled questions (50 English, 30 Japanese) from
other stories, for the router alone.

    ENGINE_DB=<scratch db outside the tree> python tools/chrono_bench/run.py setup
    ENGINE_DB=... python tools/chrono_bench/run.py opening      # real pipeline, ~10 min
    ENGINE_DB=... python tools/chrono_bench/run.py renumber     # the opening becomes turn 311
    ENGINE_DB=... python tools/chrono_bench/run.py plant        # the bank, real embeddings
    ENGINE_DB=... python tools/chrono_bench/run.py known
    ENGINE_DB=<a copy> python tools/chrono_bench/run.py retrieval on|off out.jsonl [Q01,...]
    ENGINE_DB=<a copy> python tools/chrono_bench/run.py character A|B|C|D out.jsonl [Q01,...]
    ENGINE_DB=... python tools/chrono_bench/run.py router [router_heldout.json] out.json
    python tools/chrono_bench/run.py score on.jsonl[,on2.jsonl...] off.jsonl[,off2.jsonl...]
    python tools/chrono_bench/run.py marks before.jsonl[,...] after.jsonl[,...]   # routed vs routed

Providers and settings are copied read-only from the install's own database
(the main checkout's `engine.db`, found from any worktree), the owner's
routing untouched; the card comes from the engine's own generator. Arms:
A lookups off / routing off, B off / on, C on / off, D on / on. Each question is
asked at turn 312, after the opening at 311, as Wren's line to Mara: built as
the Director would interpret it, the engine's deterministic stages run on it,
then Mara's step -- nothing committed, so no question sees another.

Every arm keeps its decisions: the scratch database's `decision_capture` is on,
so each request the decision model answers lands in
`training/decisions/<database>/` beside it -- the bank is synthetic, so the
answers are training data with no story of the owner's in them
(`tools/decision_data/build.py` labels the moment checks from the planted
turns). `score` reads one run a side or several: with several it compares the
two sides question by question (an exact McNemar test on each question's
majority across runs) and counts the questions whose runs disagreed with
each other -- how much of a difference is the decision model's own noise.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

SKIP_SETTINGS = {"host_pw_hash", "host_pw_salt", "host_secret", "host_secret_hash", "host_username",
                 "freesound_key", "research_key"}
#: Seconds the bank's last memory sits before the story clock's zero (the
#: opening), so its ages read as they would that morning.
BANK_ENDS_BEFORE_CLOCK = 3 * 3600.0
OPENING_IDX, ASK_AT = 311, 312
KNOWN = ["Wren", "Oren Dask", "Ilse Harrow", "Bram Toller", "Aldous Toller", "Tobin Reyes", "Councillor Hesk"]

MARA = """Mara Vell, 38, ferry pilot of the Heron, a flat-bottomed ferry poled across the wide brown River Aune at the river town of Saltmere and steered with a long rudder oar at the stern. She lives in her boathouse at the East Landing (a loft reached by a ladder, a spare room she lets). Grew up in the reed marsh on the West Landing with her oldest friend Ilse Harrow, who runs the old mill there. Old Petra taught her the river and left her the Heron when she died two winters ago; Mara owes her everything. Practical, dry, protective of the people she carries, quietly stubborn, hates the town council's new curfew on the river after dark. Keeps her word; lies badly and hates it when she has to. Drive: that the crossing stays open to anyone who needs it, whatever the council says. Major character."""
PERSONA = {"name": "Wren",
           "appearance": "A wiry young woman of twenty-four with ink-stained fingers, cropped dark hair and a surveyor's oilskin coat.",
           "senses": "ordinary senses", "abilities": [],
           "public_history": "A surveyor's apprentice sent by the town council to map the reed marsh; she came over on Mara's last evening ferry forty-three days ago and has lodged in the boathouse's spare room since.",
           "private_history": ""}
SCENARIO = """Saltmere, a river town on the wide brown River Aune. It is early morning on the forty-fourth day since Wren, a surveyor's apprentice mapping the reed marsh for the town council, came over on Mara Vell's last evening ferry; the first frost is on the slipway. Mara pilots the town's ferry, the Heron, and lives in her boathouse at the East Landing; Wren lodges in its spare room. The Heron is tied up at the slip below, the river is grey and still, and the two of them are alone in the boathouse by the stove."""
OPENING = "I climb down from the spare room with two mugs of tea, hand one to Mara, and sit on the upturned crate across from her by the stove."


def _state_path():
    return Path(os.environ["ENGINE_DB"]).with_suffix(".story.json")


def _load():
    return json.loads(_state_path().read_text())


def _save(d):
    _state_path().write_text(json.dumps(d, indent=1))


def _install_db():
    """The install's own database, beside the main checkout: a worktree has
    none (`git rev-parse --git-common-dir` names the checkout from any)."""
    roots = [ROOT]
    try:
        common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        if common:
            roots.append(Path(os.path.abspath(os.path.join(ROOT, common))).parent)
    except Exception:  # noqa: BLE001
        pass
    for root in roots:
        src = root / "engine.db"
        if src.exists():
            try:
                con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
                if con.execute("SELECT COUNT(*) FROM providers").fetchone()[0]:
                    return src
            except sqlite3.Error:
                continue
    raise SystemExit("no install engine.db with providers in " + ", ".join(map(str, roots)))


def _app():
    import tools.mood_story_drive as msd
    return msd._app()


def setup():
    from core import db
    db.init()
    src = sqlite3.connect(f"file:{_install_db()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    cols = [r[1] for r in src.execute("pragma table_info(providers)")]
    for row in src.execute("select * from providers"):
        db.qi(f"INSERT OR REPLACE INTO providers({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
              tuple(row[c] for c in cols))
    for k, v in src.execute("select key, value from settings"):
        if k not in SKIP_SETTINGS:
            db.set_setting(k, v)
    models = json.loads(src.execute("select value from settings where key='agent_models'").fetchone()[0])
    for k, v in (("backdrops_enabled", "0"), ("ambience_enabled", "0"),
                 ("llm_capture_enabled", "1"), ("llm_capture_bodies", "full")):
        db.set_setting(k, v)
    app = _app()
    mara = None
    # The card author runs on `utility` (unset on most installs, so `default`);
    # tried on a thinking route first, the install's routing restored after.
    for route in ({"provider": 1, "model": "z-ai/glm-5.2:thinking"},
                  {"provider": 1, "model": "z-ai/glm-5.3:thinking"}):
        db.set_setting("agent_models", json.dumps(dict(models, utility=route)))
        try:
            mara = app.char_generate({"prompt": MARA, "language": "en"})
            break
        except Exception as exc:  # noqa: BLE001
            print("card generation failed on", route, ":", str(exc)[:160], flush=True)
    db.set_setting("agent_models", json.dumps(models))
    assert mara, "no route generated a card"
    row = db.q("SELECT sheet FROM characters WHERE id=?", (mara["id"],), one=True)
    sheet = json.loads(row["sheet"])
    sheet.setdefault("simulation", {})["tier"] = "major"
    db.q("UPDATE characters SET sheet=? WHERE id=?", (json.dumps(sheet), mara["id"]))
    pid = app.persona_create({"sheet": PERSONA})["id"]
    chat = app.chat_new({"name": "Saltmere: the ferry pilot", "language": "en", "scenario": SCENARIO})
    app.chat_edit(chat["id"], {"persona_id": pid})
    app.chat_add_char(chat["id"], {"char_id": mara["id"], "already_known": True, "already_known_cast": True})
    _save({"chat": chat["id"], "mara": mara["id"], "persona": pid})
    print("chat", chat["id"], "mara", mara["id"], "card warnings:", mara.get("warnings"))


def opening():
    import tools.mood_story_drive as msd
    st = _load()
    tid, errors = msd.turn(_app(), st["chat"], OPENING)
    st["opening_turn"] = tid
    _save(st)
    print("opening turn", tid, "errors", errors)


def renumber():
    """The opening becomes turn OPENING_IDX, so the bank's turns 1-310 come
    before it (`visible_memory_rows` reads turn_idx below the deciding turn)."""
    from core.db import q, transaction
    st = _load()
    with transaction():
        q("UPDATE turns SET idx=? WHERE id=? AND idx=0", (OPENING_IDX, st["opening_turn"]))
        q("UPDATE checkpoints SET turn_idx=? WHERE chat_id=? AND turn_idx=0", (OPENING_IDX, st["chat"]))
        q("UPDATE memories SET turn_idx=? WHERE chat_id=? AND turn_idx=0", (OPENING_IDX, st["chat"]))


def plant():
    """The bank through `add_memories_batch`, as play writes it (keyword index,
    real embeddings); every row dated before the clock's zero."""
    from mind.memory import PRESTORY_TURN_IDX, add_memories_batch
    st = _load()
    bank = json.loads((HERE / "bank.json").read_text())
    last = max(t["seconds"] for t in bank["turns"])
    rows = []
    for t in bank["turns"]:
        base = {"chat_id": st["chat"], "char_id": st["mara"], "turn_id": None, "turn_idx": t["turn"],
                "encoded_at_seconds": t["seconds"] - last - BANK_ENDS_BEFORE_CLOCK,
                "location": t["location"], "about": list(t["about"])}
        rows.append({**base, "kind": "episodic", "category": "episode", "provenance": "witnessed",
                     "salience": 0.6, "content": t["content"], "confidence": 1.0,
                     "event_key": f"saltmere:{t['turn']}:episode"})
        for j, inf in enumerate(t.get("inferences") or []):
            rows.append({**base, "kind": "inference", "category": "inference", "provenance": "inferred",
                         "salience": 0.5, "content": inf["text"], "confidence": 0.7,
                         "event_key": f"saltmere:{t['turn']}:inference:{j}"})
    for p in bank["past"]:
        rows.append({"chat_id": st["chat"], "char_id": st["mara"], "turn_id": None,
                     "turn_idx": PRESTORY_TURN_IDX, "encoded_at_seconds": None, "kind": "episodic",
                     "category": "episode", "provenance": "remembered", "salience": 0.6,
                     "content": p["content"], "confidence": 1.0, "event_key": f"saltmere:past:{p['order']:02d}"})
    for i in range(0, len(rows), 24):
        add_memories_batch(rows[i:i + 24])
    print("planted", len(rows))


def known():
    from core.db import q, wget, wset
    from story.character_schema import character_name
    st = _load()
    me = character_name(json.loads(q("SELECT sheet FROM characters WHERE id=?", (st["mara"],), one=True)["sheet"]))
    k = wget(st["chat"], "known", {}) or {}
    k[me] = list(dict.fromkeys([*(k.get(me) or []), *KNOWN]))
    k["Wren"] = list(dict.fromkeys([*(k.get("Wren") or []), me]))
    wset(st["chat"], "known", k)


QUESTIONS = {q["id"]: q for q in json.loads((HERE / "questions.json").read_text())["questions"]}


def _setup_arm(tools, routes):
    from core import db
    db.init()
    db.set_setting("character_tools", "character_major" if tools else "")
    db.set_setting("ponder_routes", "on" if routes else "off")
    db.set_setting("cache_affinity_allow", "nanogpt")
    db.set_setting("llm_capture_enabled", "0")
    db.set_setting("decision_capture", "on")
    st = _load()
    row = db.q("SELECT id FROM turns WHERE chat_id=? AND idx=?", (st["chat"], ASK_AT), one=True)
    turn_id = row["id"] if row else db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                                          (st["chat"], ASK_AT, "", time.time()))
    return db, st, turn_id


def retrieval(routes, out_path, ids):
    from agents.character import _memory_person
    from mind import memory
    db, st, _ = _setup_arm(False, routes)
    person = _memory_person(json.loads(db.q("SELECT sheet FROM characters WHERE id=?", (st["mara"],), one=True)["sheet"]))
    with open(out_path, "a", encoding="utf-8") as out:
        for qid in ids:
            q = QUESTIONS[qid]
            ctx = memory.build_character_memory_context(
                st["chat"], st["mara"], ASK_AT, f'Wren says: "{q["en"]}"', {"goal": "", "mood": "easy"},
                here="The Boathouse", asked_query=q["en"], asked_why=f"Wren asked: {q['en']}",
                asked_by="Wren", person=person, language="en")
            lanes = {"recent": ctx.get("recent_memories") or [], "recalled": ctx.get("recalled_old_memories") or [],
                     "asked": (ctx.get("asked_recall") or {}).get("additional_episodes") or []}
            rec = {"id": qid, "routes": routes,
                   "refs": {k: [r.get("memory_ref") for r in v] for k, v in lanes.items()},
                   "marked": [(r.get("memory_ref"), r.get("in_time")) for v in lanes.values() for r in v
                              if r.get("in_time")],
                   "asked_record": (ctx.get("_internal") or {}).get("asked_ponder")}
            out.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            print(qid, rec["marked"][:1], flush=True)


def character(arm, out_path, ids):
    tools, routes = {"A": (False, False), "B": (False, True), "C": (True, False), "D": (True, True)}[arm]
    from agents.runtime import compute_step
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.scene import active_cast
    db, st, turn_id = _setup_arm(tools, routes)
    mara = st["mara"]
    with open(out_path, "a", encoding="utf-8") as out:
        for qid in ids:
            line = QUESTIONS[qid]["en"]
            chat = db.q("SELECT * FROM chats WHERE id=?", (st["chat"],), one=True)
            turn = dict(db.q("SELECT * FROM turns WHERE id=?", (turn_id,), one=True), player_input=line)
            ctx = PipelineContext(chat=ChatData.from_row(chat), turn=TurnData.from_row(turn),
                                  cast=active_cast(st["chat"], None), input=line, language="en")
            ctx.director_interpret = {
                "sequence": [{"type": "speech", "text": line, "volume": "normal", "visibility": "overt",
                              "conceal_from": [], "targets": [f"character:{mara}"],
                              "event_id": f"turn:{ASK_AT}:player:0:speech"}],
                "speech": line, "speech_volume": "normal", "action": None,
                "flow": {"reactors": [mara], "addressed_to": ["Mara Vell"], "authority_claims": [],
                         "resolution_flags": {}, "fiction_frame": {}, "tom_triggers": [], "dialogue_mode": True}}
            rec = {"id": qid, "arm": arm}
            t0 = time.time()
            try:
                ctx.compile_world_context = compute_step("compile_world_context", ctx, "w0")
                ctx.perception_act = compute_step("perception_act", ctx, "p0")
                step = compute_step(f"character:{mara}", ctx, "c0")
                seq = step.get("sequence") or []
                rec["say"] = [s.get("text") for s in seq if s.get("type") == "speech"]
                rec["do"] = [s.get("observable") or s.get("attempt") for s in seq if s.get("type") == "action"]
                rec["tool_calls"] = step.get("tool_calls")
            except Exception as exc:  # noqa: BLE001 -- one failed question is a row, not a lost run
                rec["error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
            rec["seconds"] = round(time.time() - t0, 2)
            out.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            print(qid, arm, rec.get("error") or rec.get("say"), flush=True)


def router(path, out_path):
    """A labelled item file against the pack's own router wording: order right,
    chronological questions routed, content kept, kind, who."""
    from mind import character_jev as jev
    from mind import memory_routes as mr
    from core import db
    db.init()
    db.set_setting("decision_capture", "on")
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    rows, score = [], {}
    for it in items:
        people, asker = list(it["people"]), it["asker"] or None
        route = mr.read_route(jev.ask(mr.question_state(it["question"], asker),
                                      mr.route_questions(people, it["lang"], asker)), people)
        s = score.setdefault(it["lang"], {"n": 0, "order": 0, "chrono": [0, 0], "content": [0, 0]})
        s["n"] += 1
        s["order"] += route["order"] in it["ok_order"]
        if it["ok_order"] == ["content"]:
            s["content"][1] += 1
            s["content"][0] += route["order"] == "content"
        elif "content" not in it["ok_order"]:
            s["chrono"][1] += 1
            s["chrono"][0] += route["order"] != "content"
        rows.append({"q": it["question"], "lang": it["lang"], "route": route, "want": it["ok_order"]})
    Path(out_path).write_text(json.dumps({"score": score, "rows": rows}, ensure_ascii=False, indent=1))
    print(json.dumps(score))


def _exact_mcnemar(only_a, only_b):
    """Two-sided exact McNemar: the discordant pairs against a fair coin."""
    from math import comb
    n, k = only_a + only_b, min(only_a, only_b)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def score(on_paths, off_paths):
    """Retrieval by code: the planted answer anywhere in the packet, and the
    marked moment the planted one (the moment itself for just before/after).
    One run a side, or several (`a.jsonl,b.jsonl`): then each question counts
    by its majority across a side's runs, the two sides are compared question
    by question, and the questions whose runs disagreed are counted."""
    def load(p):
        return {r["id"]: r for r in (json.loads(x) for x in open(p, encoding="utf-8"))}

    def turn(ref):
        m = re.match(r"saltmere:(\d+):", str(ref or ""))
        return int(m.group(1)) if m else ("past" if str(ref or "").startswith("saltmere:past") else None)

    def in_packet(rec, want):
        got = {turn(x) for refs in ((rec or {}).get("refs") or {}).values() for x in refs}
        return any(w in got for w in want)

    def marked(rec):
        return [turn(r) for r, _ in (rec or {}).get("marked") or []]

    on_runs = [load(p) for p in str(on_paths).split(",") if p]
    off_runs = [load(p) for p in str(off_paths).split(",") if p]
    asked = set.intersection(*(set(r) for r in on_runs + off_runs))
    per_run = []
    for side, runs in (("on", on_runs), ("off", off_runs)):
        for n, run in enumerate(runs):
            tot = {"side": side, "run": n + 1, "answerable": 0, "in_packet": 0, "marked_right": 0,
                   "marked_wrong": 0, "never": 0, "never_unmarked": 0}
            for qid in sorted(asked):
                q = QUESTIONS[qid]
                want = q["answer_turns"]
                right = [q["moment_turn"]] if q.get("moment_turn") is not None else want
                if not want:
                    tot["never"] += 1
                    tot["never_unmarked"] += not marked(run.get(qid))
                    continue
                tot["answerable"] += 1
                tot["in_packet"] += in_packet(run.get(qid), want)
                if marked(run.get(qid)):
                    tot["marked_right" if any(m in right for m in marked(run.get(qid))) else "marked_wrong"] += 1
            per_run.append(tot)
    out = {"runs": per_run}
    answerable = [qid for qid in sorted(asked) if QUESTIONS[qid]["answer_turns"]]

    def majority(runs, qid):
        hits = sum(in_packet(r.get(qid), QUESTIONS[qid]["answer_turns"]) for r in runs)
        return hits * 2 > len(runs), 0 < hits < len(runs)
    only_on = only_off = split_on = split_off = 0
    for qid in answerable:
        on, unsure_on = majority(on_runs, qid)
        off, unsure_off = majority(off_runs, qid)
        only_on += on and not off
        only_off += off and not on
        split_on += unsure_on
        split_off += unsure_off
    out["paired"] = {"questions": len(answerable), "only_on": only_on, "only_off": only_off,
                     "exact_mcnemar_p": round(_exact_mcnemar(only_on, only_off), 4),
                     "runs_disagree_on": split_on, "runs_disagree_off": split_off}
    print(json.dumps(out, indent=1))
    return out


def marks(before_paths, after_paths):
    """Two sets of routed runs (routing on both), question by question: each
    run's mark -- right, wrong or none -- and whether the planted answer reached
    the packet, then each question's majority across its runs, before against
    after. For a change to the search itself, where `score`'s on/off comparison
    cannot see a mark move. A mark is right when it is the planted turn, or the
    moment itself for just before / just after."""
    def load(p):
        return {r["id"]: r for r in (json.loads(x) for x in open(p, encoding="utf-8"))}

    def turn(ref):
        m = re.match(r"saltmere:(\d+):", str(ref or ""))
        return int(m.group(1)) if m else ("past" if str(ref or "").startswith("saltmere:past") else None)

    def mark(rec, q):
        got = [turn(r) for r, _ in (rec or {}).get("marked") or []]
        if not got:
            return "none"
        right = [q["moment_turn"]] if q.get("moment_turn") is not None else q["answer_turns"]
        return "right" if any(g in right for g in got) else "wrong"

    def reached(rec, q):
        got = {turn(x) for refs in ((rec or {}).get("refs") or {}).values() for x in refs}
        return any(w in got for w in q["answer_turns"])

    sides = {"before": [load(p) for p in str(before_paths).split(",") if p],
             "after": [load(p) for p in str(after_paths).split(",") if p]}
    asked = set.intersection(*(set(r) for runs in sides.values() for r in runs))
    out = {"runs": {}, "majority": {}, "changed": []}
    for side, runs in sides.items():
        out["runs"][side] = [dict(Counter(mark(r.get(qid), QUESTIONS[qid]) for qid in asked)) for r in runs]
    majority = {}
    for side, runs in sides.items():
        for qid in asked:
            q = QUESTIONS[qid]
            got = Counter(mark(r.get(qid), q) for r in runs).most_common(1)[0][0]
            hit = sum(reached(r.get(qid), q) for r in runs) * 2 > len(runs) if q["answer_turns"] else None
            majority[(side, qid)] = (got, hit)
    for side in sides:
        out["majority"][side] = dict(Counter(majority[(side, qid)][0] for qid in asked))
        out["majority"][side]["answer_reached"] = sum(1 for qid in asked if majority[(side, qid)][1])
    for qid in sorted(asked):
        if majority[("before", qid)] != majority[("after", qid)]:
            out["changed"].append({"id": qid, "before": majority[("before", qid)],
                                   "after": majority[("after", qid)], "question": QUESTIONS[qid]["en"]})
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "score":
        score(sys.argv[2], sys.argv[3])
        sys.exit(0)
    if cmd == "marks":
        marks(sys.argv[2], sys.argv[3])
        sys.exit(0)
    from tools.bubble_drive import _require_scratch
    _require_scratch(os.environ.get("ENGINE_DB"))
    if cmd in ("setup", "opening", "renumber", "plant", "known"):
        {"setup": setup, "opening": opening, "renumber": renumber, "plant": plant, "known": known}[cmd]()
    elif cmd == "retrieval":
        retrieval(sys.argv[2] == "on", sys.argv[3], sys.argv[4].split(",") if len(sys.argv) > 4 else list(QUESTIONS))
    elif cmd == "character":
        character(sys.argv[2], sys.argv[3], sys.argv[4].split(",") if len(sys.argv) > 4 else list(QUESTIONS))
    elif cmd == "router":
        args = sys.argv[2:]
        router(args[0] if len(args) > 1 else str(HERE / "router_heldout.json"), args[-1])
