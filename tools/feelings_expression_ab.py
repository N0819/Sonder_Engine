"""Does a character show a feeling as strongly as it feels it?

The owner, 2026-09-26: "How realistic would you say the characte responses
are in accordance to their mood? An not just mood overall." On the traced
beats (`docs/experiments/AFFECT_TRACE_2026_09_26.md`) conduct followed the
feelings handed over, but 32 of 36 spoken lines carried a restrained tone
("flat" 17 times), and the feelings block names what a character feels,
strongest first, but never how strongly. This replays the traced character
calls (`tools/affect_trace.py` records, the replay copies' own captures)
four ways:

- `A` -- the reply from play: the block as the engine gave it;
- `A2` -- the same payload answered again, the noise between two calls;
- `B` -- each feeling in the block carries its strength in a word
  (`STRENGTH`, from the intensity the pass gave it);
- `C` -- as `B`, and the character prompt's CURRENT FEELINGS clause adds
  `CLAUSE`: how much a feeling shows follows from who the character is and
  from how strongly it is felt.

A blind judge (the `utility` role, routed per database copy) sees the
character, what reached it, what it feels and how strongly, and two drafts
in a random order; says which is the more believable response of this
person feeling this at this strength; and rates how openly each shows its
feelings, 0 to 3. `report` counts each arm's register (restrained and open
tone words, line length), the judges' verdicts, and whether how openly a
reply shows its feelings rises with how strongly they are felt.

Usage:
    python tools/feelings_expression_ab.py collect --story name:trace.jsonl:replay.db ... --out items.json
    ENGINE_DB=<story copy> python tools/feelings_expression_ab.py run --items items.json --out replies.json
    ENGINE_DB=<rater copy> python tools/feelings_expression_ab.py judge --items items.json --replies replies.json --out v.json
    python tools/feelings_expression_ab.py report --items items.json --replies replies.json --verdicts glm:v1.json gemini:v2.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
import sqlite3
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

#: Strength words for a feeling's strength, strongest first: the first band
#: whose floor the strength reaches. The words and floors are the decision
#: model's own answer scale for "how strongly does this stir you?" (grade:
#: slightly 1/3, clearly 2/3, strongly 1), each answer owning the values
#: nearer it than its neighbours -- on the 264 labelled events that scale
#: reads slightly 18%, clearly 55%, strongly 28%, where one blind reader read
#: 17%, 59% and 18%. If adopted the words go to the language pack.
STRENGTH = ((5 / 6, "felt strongly"), (1 / 2, "felt clearly"), (1 / 6, "felt slightly"), (0.0, "barely felt"))
CLAUSE = ("How strongly you feel each thing is given with it. How much of it shows -- in what you say, how you "
          "say it, what you do -- follows from who you are and from how strongly you feel it, as it would in "
          "anyone.")
ARMS = ("A", "A2", "B", "C")
PAIRS = (("A", "A2"), ("A2", "B"), ("A2", "C"), ("B", "C"))
RESTRAINED = {"flat", "measured", "low", "quiet", "even", "clipped", "controlled", "precise", "level", "cold", "dry"}
JUDGE_SYSTEM = (
    "You judge interactive fiction for psychological realism. Below are one character, what just reached them, "
    "what they feel right now and how strongly -- true of them, whatever the drafts show -- and two drafts of "
    "their next move: A and B. Judge which draft is the more believable response of THIS person feeling THIS, "
    "at THIS strength, in what they say, how they say it and what they do. Then rate, for each draft, how openly "
    "the character's feelings show in it, from 0 (not at all) to 3 (fully). Return JSON only: {\"better\": "
    "\"A\" | \"B\" | \"same\", \"open_a\": n, \"open_b\": n, \"why\": \"one sentence\"}. Use \"same\" only when "
    "neither is more believable.")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def band(intensity):
    return next(word for floor, word in STRENGTH if intensity >= floor)


def _strengths(before):
    """{label: strength} for the block's labels. A feeling's intensity is
    its item's stir split by share among the names the model offered, so a
    strongly stirring, mixed moment reads faint name by name; a feeling's
    strength is instead its item's whole stir (the sum of the item's
    feelings, as the stored feeling weighs a moment) for the item's top
    feeling, and the others by their share against the top's."""
    from mind import affect_mix as mix
    from mind import affect_pass as ap

    items = {}
    for e in before.get("emotions") or []:
        items.setdefault((e["source"], e["ref"]), []).append(e)
    out = {}
    for group in items.values():
        total, top = sum(e["intensity"] for e in group), max(e["intensity"] for e in group)
        for e in group:
            label = ap.label(mix.Emotion(e["name"], e["intensity"], e["about"], e["source"], e["ref"]), "en")
            strength = min(1.0, total * e["intensity"] / top) if top > 0 else 0.0
            out[label] = max(out.get(label, 0.0), strength)
    return out


def with_strength(block, strengths):
    """The block with each feeling's strength in a word after its name."""
    out = dict(block or {})
    for part in ("now", "beneath"):
        items = []
        for label in (block or {}).get(part) or []:
            if label in strengths:
                word, sep, rest = label.partition(" (")
                label = f"{word}, {band(strengths[label])}" + (f" ({rest}" if sep else "")
            items.append(label)
        out[part] = items
    return out


def with_clause(system):
    anchor = "It is true of you."
    return system.replace(anchor, f"{anchor} {CLAUSE}", 1) if anchor in system else f"{system}\n\n{CLAUSE}"


def collect(args):
    from feelings_ab import _blob, _sheet, _value

    items = []
    for spec in args.story:
        story, trace, db = spec.split(":", 2)
        recs = [json.loads(line) for line in Path(trace).read_text(encoding="utf-8").splitlines() if line.strip()]
        turn_ids = {r["turn"]: r["turn_id"] for r in recs if r["kind"] == "turn"}
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for n, tid in sorted(turn_ids.items()):
            befores = [r for r in recs if r["kind"] == "before" and r["turn"] == n]
            replies = [r for r in recs if r["kind"] == "reply" and r["turn"] == n]
            caps = con.execute("SELECT c.system_hash, c.payload_hashes, t.chat_id FROM llm_capture c "
                               "JOIN turns t ON t.id = c.turn_id WHERE c.turn_id = ? AND c.role = 'character_major' "
                               "AND c.ok = 1 ORDER BY c.seq", (tid,)).fetchall()
            payloads = [({k: _value(_blob(con, h)) for k, h in json.loads(hashes or "{}").items()}, sh, chat)
                        for sh, hashes, chat in caps]
            used = set()
            for k, before in enumerate(befores):
                match = next((i for i, (p, _s, _c) in enumerate(payloads) if i not in used
                              and (p.get("self") or {}).get("name") == before["name"]), None)
                reply = next((r for r in replies if r["name"] == before["name"]
                              and r.get("given") == ((payloads[match][0].get("self") or {}).get("feelings")
                                                     if match is not None else None)), None)
                if match is None or reply is None:
                    print(f"  {story} turn {n}: no capture for {before['name']}")
                    continue
                used.add(match)
                payload, system_hash, chat = payloads[match]
                items.append({"id": f"{story}:{n}:{k}", "story": story, "turn": n, "name": before["name"],
                              "system": _blob(con, system_hash), "payload": payload,
                              "sheet": _sheet(con, chat, (payload.get("self") or {}).get("entity_id")),
                              "block": (payload.get("self") or {}).get("feelings") or {},
                              "strengths": _strengths(before), "reply_A": reply.get("sequence") or []})
    Path(args.out).write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    print(f"{len(items)} calls")


def _request(item, arm):
    payload, system = copy.deepcopy(item["payload"]), item["system"]
    if arm in ("B", "C"):
        payload["self"]["feelings"] = with_strength(item["block"], item["strengths"])
    if arm == "C":
        system = with_clause(system)
    return system, payload


def run(args):
    from agents.common import _agent_json

    items = _load(args.items)
    path = Path(args.out)
    done = _load(path) if path.exists() else {}
    jobs = [(it, arm) for it in items for arm in ("A2", "B", "C")
            if not (done.get(it["id"]) or {}).get(arm, {}).get("out")]
    print(f"{len(jobs)} character calls to make")

    def call(job):
        item, arm = job
        system, payload = _request(item, arm)
        start = time.time()
        try:
            out, error = _agent_json("character_major", "character_kernel", system, payload), ""
        except Exception as exc:  # noqa: BLE001 -- recorded; the run goes on
            out, error = None, f"{type(exc).__name__}: {str(exc)[:200]}"
        return item["id"], arm, {"out": out, "error": error, "seconds": round(time.time() - start, 1)}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (iid, arm, res) in enumerate(pool.map(call, jobs), 1):
            done.setdefault(iid, {})[arm] = res
            path.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
            print(f"{n} of {len(jobs)}: {iid} {arm} {res['seconds']}s {res['error'] or 'ok'}", flush=True)


def _sequence(item, replies, arm):
    if arm == "A":
        return item["reply_A"]
    return ((replies.get(item["id"]) or {}).get(arm) or {}).get("out", {}).get("sequence") or []


def _conduct(sequence):
    from feelings_ab import conduct

    return conduct({"sequence": sequence})


def _scene(item):
    from mind import affect_pass as ap

    events = ap.events_from((item["payload"].get("perception") or {}).get("events"))
    felt = with_strength(item["block"], item["strengths"])
    parts = [f"THE CHARACTER: {item['name']}.\n{ap.psychology_text(item['sheet'])}"]
    if events:
        parts.append("WHAT JUST REACHED THEM:\n" + "\n".join(f"- {e['text']}" for e in events))
    parts.append("WHAT THEY FEEL, AND HOW STRONGLY:\n- now: " + "; ".join(felt.get("now") or ["-"])
                 + "\n- beneath: " + "; ".join(felt.get("beneath") or ["-"])
                 + "\n- mood: " + ", ".join(felt.get("mood") or ["-"]))
    return "\n\n".join(parts)


def _order(item_id, pair):
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
    for iid, item in items.items():
        for pair in PAIRS:
            key = f"{iid}|{pair[0]}|{pair[1]}"
            if key not in done and all(_sequence(item, replies, a) for a in pair):
                jobs.append((key, item, pair))

    def ask(job):
        key, item, pair = job
        a, b = _order(item["id"], pair)
        drafts = "\n\n".join(f"DRAFT {label}:\n{_conduct(_sequence(item, replies, arm))}"
                             for label, arm in (("A", a), ("B", b)))
        reply = jparse(chat_complete("utility", JUDGE_SYSTEM, _scene(item) + "\n\n" + drafts, json_mode=True,
                                     temperature=0.0, max_tokens=600, reasoning_effort="off")) or {}

        def num(v):
            try:
                return max(0.0, min(3.0, float(v)))
            except (TypeError, ValueError):
                return None

        pick = {"A": a, "B": b}
        return key, {"shown": [a, b], "better": pick.get(str(reply.get("better") or "").strip().upper(), "same"),
                     "open": {a: num(reply.get("open_a")), b: num(reply.get("open_b"))},
                     "why": str(reply.get("why") or "")}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for key, verdict in pool.map(ask, jobs):
            done[key] = verdict
    path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(done)} verdicts")


def _pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 4:
        return None
    x, y = zip(*pairs)
    sx, sy = statistics.pstdev(x), statistics.pstdev(y)
    if sx < 1e-9 or sy < 1e-9:
        return None
    mx, my = statistics.fmean(x), statistics.fmean(y)
    return sum((a - mx) * (b - my) for a, b in pairs) / (len(pairs) * sx * sy)


def report(args):
    items = _load(args.items)
    replies = _load(args.replies)
    judges = [(s.split(":", 1)[0], _load(s.split(":", 1)[1])) for s in args.verdicts]
    print(f"{len(items)} calls\n\nregister of the spoken lines, per arm:")
    for arm in ARMS:
        lines = [s for it in items for s in _sequence(it, replies, arm)
                 if isinstance(s, dict) and s.get("type") == "speech" and str(s.get("text") or "").strip()]
        tones = [set(re.findall(r"[a-z]+", str(s.get("tone") or "").lower())) for s in lines]
        restrained = sum(1 for t in tones if t & RESTRAINED)
        firsts = Counter(re.split(r"[,;(—–-]", str(s.get("tone") or "").lower())[0].strip() for s in lines)
        words = sorted(len(str(s["text"]).split()) for s in lines) or [0]
        print(f"  {arm:3} {len(lines):3} lines, restrained {restrained} ({restrained / max(1, len(lines)):.0%}), "
              f"{len(firsts)} distinct tones, median {words[len(words) // 2]} words   "
              + ", ".join(f"{t} {n}" for t, n in firsts.most_common(4)))
    for first, second in PAIRS:
        print(f"\n{first} against {second}:")
        for name, verdicts in judges:
            tally = Counter(v["better"] for k, v in verdicts.items() if k.endswith(f"|{first}|{second}"))
            print(f"  {name:8} better: {first} {tally[first]}, {second} {tally[second]}, same {tally['same']}")
    print("\nhow openly the feelings show (judges' mean, 0-3), and its correlation with the strongest feeling's intensity:")
    for arm in ARMS:
        opens, tops = [], []
        for it in items:
            vals = [v["open"].get(arm) for _n, verdicts in judges for k, v in verdicts.items()
                    if k.startswith(it["id"] + "|") and v["open"].get(arm) is not None]
            if vals:
                opens.append(statistics.fmean(vals))
                tops.append(max((it["strengths"].get(label, 0.0) for label in it["block"].get("now") or []),
                                default=0.0))
        r = _pearson(tops, opens)
        print(f"  {arm:3} open {statistics.fmean(opens) if opens else float('nan'):.2f}   r with strength "
              + ("--" if r is None else f"{r:+.2f}") + f"   ({len(opens)} calls)")
    if args.pairs:
        out = ["# Feelings shown as strongly as felt: the replies side by side", ""]
        for it in items:
            out += [f"## {it['id']} -- {it['name']}", "", "```", _scene(it), "```", ""]
            for arm in ARMS:
                out += [f"**{arm}**", "", "```", _conduct(_sequence(it, replies, arm)), "```", ""]
            for first, second in PAIRS:
                for name, verdicts in judges:
                    v = verdicts.get(f"{it['id']}|{first}|{second}") or {}
                    out.append(f"- {name}, {first} v {second}: better {v.get('better')}, open "
                               f"{v.get('open')} -- {v.get('why', '')}")
            out.append("")
        Path(args.pairs).write_text("\n".join(out), encoding="utf-8")
        print(f"\npairs written to {args.pairs}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--story", nargs="+", required=True, help="name:trace.jsonl:replay.db")
    p.add_argument("--out", required=True)
    p = sub.add_parser("run")
    p.add_argument("--items", required=True)
    p.add_argument("--out", required=True)
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
