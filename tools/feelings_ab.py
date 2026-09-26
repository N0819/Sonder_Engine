"""Does a character act better for being handed its feelings -- and for
being handed them named well?

A blind A/B on captured character calls (`llm_capture`, role
`character_major`) from turns the affect pass ran on (`mind/affect_pass.py`).
Each call is answered again three ways, the system prompt and the payload
exactly as captured but for `self.feelings`:

- `none` -- the block removed;
- `old` -- the block as captured, named by the engine of that turn;
- `new` -- `now` and `beneath` named again by today's affect pass from the
  same inputs (the call's perception, recall and concerns, and the
  character's card), the captured `mood` words kept, so the arms differ only
  in how the moment's feelings are named.

A blind judge (the `utility` role, routed to a different model family on
each database copy) then compares two of a beat's answers at a time, in a
random order, on conduct alone -- what the character says and does -- and
says which is the better next move for this character and in which the
feelings come through more.

`collect` needs a Jev provider (ENGINE_DB = any copy with one); `run` the
character route of the stories (ENGINE_DB = a story copy); `judge` a rater
copy per judge. Every step caches, so a pilot (`run --limit`) grows into the
whole set by running again.

Usage:
    ENGINE_DB=<copy> python tools/feelings_ab.py collect --db a.db b.db --out items.json
    ENGINE_DB=<story copy> python tools/feelings_ab.py run --items items.json --out replies.json [--limit 8]
    ENGINE_DB=<rater copy> python tools/feelings_ab.py judge --items items.json --replies replies.json --out v.json
    python tools/feelings_ab.py report --items items.json --replies replies.json --verdicts glm:v1.json gemini:v2.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sqlite3
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ARMS = ("none", "old", "new")
PAIRS = (("none", "old"), ("none", "new"), ("old", "new"))
JUDGE_SYSTEM = (
    "You judge interactive fiction. Below are one character, what just reached them, and two drafts of "
    "their next move, written from the same moment: A and B. Judge which is the better next move for THIS "
    "character in THIS moment -- truer to what this person would feel and do, given who they are and what "
    "just happened; specific to the moment rather than generic; feeling shown through what they say and do "
    "rather than stated. Then say in which draft the character's feelings come through more. Return JSON "
    "only: {\"better\": \"A\" | \"B\" | \"same\", \"feelings_clearer\": \"A\" | \"B\" | \"same\", "
    "\"why\": \"one sentence\"}. Use \"same\" only when neither is better.")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _blob(con, digest):
    row = con.execute("SELECT body FROM llm_blobs WHERE hash=?", (digest,)).fetchone() if digest else None
    if not row:
        return None
    return row[0].decode("utf-8") if isinstance(row[0], bytes) else row[0]


def _value(text):
    """A payload key as the capture stored it: JSON, or the string itself."""
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def _sheet(con, chat_id, entity_id):
    """The character's card: the per-story card where it carries a
    psychology, else the reusable one."""
    try:
        cid = int(str(entity_id).split(":")[-1])
    except ValueError:
        return {}
    for sql, args in (("SELECT sheet FROM chat_chars WHERE chat_id=? AND char_id=?", (chat_id, cid)),
                      ("SELECT sheet FROM characters WHERE id=?", (cid,))):
        row = con.execute(sql, args).fetchone()
        sheet = _value(row[0]) if row and row[0] else None
        if isinstance(sheet, dict) and sheet.get("psychology"):
            return sheet
    return {}


def _new_feelings(item):
    """`now` and `beneath` named by today's affect pass from the call's own
    inputs -- what `before_call` asks, less the mood reading -- with the
    captured `mood` words kept."""
    from mind import affect_appraisal as appraisal
    from mind import affect_mix as mix
    from mind import affect_pass as ap

    payload, sheet = item["payload"], item["sheet"]
    self_ = payload["self"]
    words = (self_.get("feelings") or {}).get("mood") or []
    events = ap.events_from((payload.get("perception") or {}).get("events"))
    memories = ap.memories_from(payload.get("memory"))
    concerns = ap.concerns_from(self_.get("active_state"))
    people = ap.people_from(payload.get("relationships"))
    state = ap.state_text(item["name"], sheet, events, people, memories, concerns, words)
    out = appraisal.appraise(state, events, memories=memories, concerns=concerns, language="en")
    emotions = []
    for e in events:
        emotions += mix.emotions_from_appraisal(out["events"].get(e["ref"]) or {}, ref=e["ref"],
                                                about=ap._text(e["text"], ap.ABOUT_CHARS))
    for c in concerns:
        a = out["concerns"].get(c["ref"]) or {}
        emotions += mix.concern_emotions(a, a.get("weight"), ref=c["ref"], about=ap._text(c["text"], ap.ABOUT_CHARS))
    for m in memories:
        a = out["memories"].get(m["ref"]) or {}
        emotions += mix.memory_emotions(a.get("strength"), a.get("tone"), a.get("kinds"), ref=m["ref"],
                                        about=ap._text(m["text"], ap.ABOUT_CHARS))
    block = ap.feelings_block(ap.Felt(mood=mix.Mood(), home=mix.Mood(), emotions=emotions, language="en",
                                      asked=True))
    return {"now": block["now"], "beneath": block["beneath"], "mood": words}


def collect(args):
    items, seen = [], set()
    for path in args.db:
        story = Path(path).stem.split("_")[0]
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT c.id, c.system_hash, c.payload_hashes, t.idx, t.chat_id FROM llm_capture c "
            "JOIN turns t ON t.id=c.turn_id WHERE c.role='character_major' AND c.ok=1 "
            "ORDER BY t.idx, c.seq").fetchall()
        for cap_id, system_hash, hashes, idx, chat_id in rows:
            payload = {k: _value(_blob(con, h)) for k, h in json.loads(hashes or "{}").items()}
            self_ = payload.get("self")
            if not isinstance(self_, dict) or not self_.get("feelings"):
                continue
            # a beat's first call per mind: later rounds and repairs repeat it
            if (story, idx, self_.get("entity_id")) in seen:
                continue
            seen.add((story, idx, self_.get("entity_id")))
            items.append({"id": f"{story}:{cap_id}", "story": story, "turn": idx, "name": self_.get("name"),
                          "system": _blob(con, system_hash), "payload": payload,
                          "sheet": _sheet(con, chat_id, self_.get("entity_id"))})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        news = list(pool.map(_new_feelings, items))
    for item, new in zip(items, news):
        item["feelings"] = {"old": item["payload"]["self"]["feelings"], "new": new}
    Path(args.out).write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"{len(items)} calls with feelings, from {', '.join(sorted({i['story'] for i in items}))}")


def _payload(item, arm):
    payload = copy.deepcopy(item["payload"])
    if arm == "none":
        payload["self"].pop("feelings", None)
    else:
        payload["self"]["feelings"] = item["feelings"][arm]
    return payload


def run(args):
    from agents.common import _agent_json

    items = _load(args.items)[: args.limit or None]
    path = Path(args.out)
    done = _load(path) if path.exists() else {}
    jobs = [(it, arm) for it in items for arm in ARMS if not (done.get(it["id"]) or {}).get(arm, {}).get("out")]
    print(f"{len(jobs)} character calls to make")

    def call(job):
        item, arm = job
        start = time.time()
        try:
            out, error = _agent_json("character_major", "character_kernel", item["system"], _payload(item, arm)), ""
        except Exception as exc:  # noqa: BLE001 -- recorded; the run goes on
            out, error = None, f"{type(exc).__name__}: {str(exc)[:200]}"
        return item["id"], arm, {"out": out, "error": error, "seconds": round(time.time() - start, 1)}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (iid, arm, res) in enumerate(pool.map(call, jobs), 1):
            done.setdefault(iid, {})[arm] = res
            path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"{n} of {len(jobs)}: {iid} {arm} {res['seconds']}s {res['error'] or 'ok'}")


def conduct(out):
    """What a reader sees of an answer: its speech and actions, in order."""
    lines = []
    for s in (out or {}).get("sequence") or []:
        if not isinstance(s, dict):
            continue
        if s.get("type") == "speech" and str(s.get("text") or "").strip():
            tone = f" ({s['tone']})" if s.get("tone") else ""
            lines.append(f"Says{tone}: \"{s['text']}\"")
        elif s.get("type") == "action" and (s.get("attempt") or s.get("observable")):
            lines.append(f"Does: {s.get('attempt') or s.get('observable')}")
    return "\n".join(lines) or "(does nothing)"


def _scene(item):
    from mind import affect_pass as ap

    events = ap.events_from((item["payload"].get("perception") or {}).get("events"))
    who = f"THE CHARACTER: {item['name']}.\n{ap.psychology_text(item['sheet'])}"
    happened = "WHAT JUST REACHED THEM:\n" + "\n".join(f"- {e['text']}" for e in events) if events else ""
    return "\n\n".join(p for p in (who, happened) if p)


def _order(item_id, pair):
    """A stable coin per beat and pair: which arm is shown as A."""
    seed = int(hashlib.sha1(f"{item_id}|{pair[0]}|{pair[1]}".encode()).hexdigest()[:8], 16)
    return pair if random.Random(seed).random() < 0.5 else (pair[1], pair[0])


def judge(args):
    from agents.common import jparse
    from llm.providers import chat_complete

    items = {it["id"]: it for it in _load(args.items)}
    replies = _load(args.replies)
    path = Path(args.out)
    done = _load(path) if path.exists() else {}
    jobs = []
    for iid, arms in replies.items():
        for pair in PAIRS:
            key = f"{iid}|{pair[0]}|{pair[1]}"
            if key in done or not all((arms.get(a) or {}).get("out") for a in pair):
                continue
            jobs.append((key, items[iid], arms, pair))

    def ask(job):
        key, item, arms, pair = job
        a, b = _order(item["id"], pair)
        drafts = "\n\n".join(f"DRAFT {label}:\n{conduct(arms[arm]['out'])}" for label, arm in (("A", a), ("B", b)))
        user = _scene(item) + "\n\n" + drafts
        reply = jparse(chat_complete("utility", JUDGE_SYSTEM, user, json_mode=True, temperature=0.0,
                                     max_tokens=600, reasoning_effort="off")) or {}
        pick = {"A": a, "B": b}
        return key, {"shown": [a, b], "better": pick.get(str(reply.get("better") or "").strip().upper(), "same"),
                     "feelings_clearer": pick.get(str(reply.get("feelings_clearer") or "").strip().upper(), "same"),
                     "why": str(reply.get("why") or "")}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for key, verdict in pool.map(ask, jobs):
            done[key] = verdict
    path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(done)} verdicts")


def report(args):
    items = {it["id"]: it for it in _load(args.items)}
    replies = _load(args.replies)
    judges = [(spec.split(":", 1)[0], _load(spec.split(":", 1)[1])) for spec in args.verdicts]
    ok = [iid for iid, arms in replies.items() if all((arms.get(a) or {}).get("out") for a in ARMS)]
    print(f"{len(ok)} beats answered in all three arms; "
          f"failures: {sum(1 for arms in replies.values() for r in arms.values() if not r.get('out'))}")
    for first, second in PAIRS:
        print(f"\n{first} against {second}:")
        agreed = Counter()
        for name, verdicts in judges:
            better, clearer = Counter(), Counter()
            for iid in ok:
                v = verdicts.get(f"{iid}|{first}|{second}")
                if v:
                    better[v["better"]] += 1
                    clearer[v["feelings_clearer"]] += 1
            print(f"  {name:8} better: {first} {better[first]}, {second} {better[second]}, same {better['same']}"
                  f"   feelings clearer: {first} {clearer[first]}, {second} {clearer[second]}, same {clearer['same']}")
        for iid in ok:
            vs = [verdicts.get(f"{iid}|{first}|{second}") for _n, verdicts in judges]
            if all(vs) and len({v["better"] for v in vs}) == 1:
                agreed[vs[0]["better"]] += 1
        if len(judges) > 1:
            print(f"  both judges agree: {first} {agreed[first]}, {second} {agreed[second]}, same {agreed['same']}")
    if args.pairs:
        lines = ["# Feelings A/B: the replies side by side", ""]
        for iid in ok:
            item = items[iid]
            lines += [f"## {iid} -- {item['name']}, turn {item['turn']}", "", "```", _scene(item), "```", ""]
            for arm in ARMS:
                feel = item["feelings"].get(arm) if arm != "none" else None
                lines += [f"**{arm}**" + (f" -- given `{json.dumps(feel, ensure_ascii=False)}`" if feel else ""),
                          "", "```", conduct(replies[iid][arm]["out"]), "```", ""]
            for first, second in PAIRS:
                for name, verdicts in judges:
                    v = verdicts.get(f"{iid}|{first}|{second}") or {}
                    lines.append(f"- {name}, {first} v {second}: better {v.get('better')}, "
                                 f"clearer {v.get('feelings_clearer')} -- {v.get('why', '')}")
            lines.append("")
        Path(args.pairs).write_text("\n".join(lines), encoding="utf-8")
        print(f"\npairs written to {args.pairs}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--db", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=4)
    p = sub.add_parser("run")
    p.add_argument("--items", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=3)
    p = sub.add_parser("judge")
    p.add_argument("--items", required=True)
    p.add_argument("--replies", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=4)
    p = sub.add_parser("report")
    p.add_argument("--items", required=True)
    p.add_argument("--replies", required=True)
    p.add_argument("--verdicts", nargs="+", required=True)
    p.add_argument("--pairs", default="")
    args = parser.parse_args()
    {"collect": collect, "run": run, "judge": judge, "report": report}[args.mode](args)


if __name__ == "__main__":
    main()
