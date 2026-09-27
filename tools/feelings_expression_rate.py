"""Does a character written to show feeling show more of it the more it feels?

The owner, 2026-09-26, said go ahead to testing expression against strength
on expressive cards. On the four test stories 32 of 36 spoken lines carried a
restrained tone, and neither naming a feeling's strength nor a clause about
showing it moved that (`docs/experiments/FEELINGS_STRENGTH_AB_2026_09_26.md`)
-- but six of their seven cards were written restrained, so whether a reply's
expression rises with how strongly a feeling is felt could not be seen there.
This rates, each reply alone, a story played with cards written to show what
they feel beside one written to hold it in (`collect` is
`tools/feelings_expression_ab.py`'s):

- `open` -- a BLIND judge sees the character's name, what just reached them
  and what they did, never their card or their feelings, and rates how
  openly feelings show in it, 0 to 3 -- how PLAINLY, which for a card
  written to show its feelings is high at every strength (a warm greeting
  to a delivery boy rates 3), so it measures temperament;
- `shown` -- as blind: how STRONG a feeling the move displays, whatever the
  feeling, 0 (none) to 3 (intense) -- the measure that can rise with how
  strongly a feeling is felt;
- `fit` -- a judge sees the card's psychology and voice, what reached them,
  what they feel and how strongly, and the reply, and says whether it is a
  believable response of this person (1 to 5) and whether it shows too
  little, about the right amount or too much for this person feeling this.

`report` gives each character's openness per judge, its correlation (Pearson
and rank) with how strongly the moment stirred the mind -- the whole stir of
what stirred it most -- within each character and each temperament, and the
fit verdicts, one judge at a time (never their mean). Several stories pool:
the same cards in a quiet scene and a dramatic one give each character the
range one scene cannot.

Usage:
    python tools/feelings_expression_ab.py collect --story name:trace.jsonl:story.db --out items.json
    ENGINE_DB=<rater copy> python tools/feelings_expression_rate.py judge --items items.json --out v.json
    python tools/feelings_expression_rate.py report --items items.json --verdicts glm:v1.json gemini:v2.json \\
        --temperament "Rosa Bellandi=open,Gianni Bellandi=open,Lucia Bellandi=reserved" [--table t.md]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from feelings_expression_ab import (  # noqa: E402
    RESTRAINED, STRENGTH, _conduct, _load, _pearson, band, with_strength)

OPEN_SYSTEM = (
    "You read interactive fiction. Below are a character's name, what just reached them, and their next move: "
    "what they say, how they say it, and what they do. Rate how openly the character's feelings show in this "
    "move, from 0 (not at all: nothing of what they feel shows) to 3 (fully: what they feel is plain in their "
    "words, their voice or their body). Rate what shows, not whether it suits them. Return JSON only: "
    "{\"open\": n, \"why\": \"one sentence\"}.")
SHOWN_SYSTEM = (
    "You read interactive fiction. Below are a character's name, what just reached them, and their next move: "
    "what they say, how they say it, and what they do. How strong a feeling does this move display, whatever "
    "the feeling is, from 0 (none shows) through 1 (mild) and 2 (marked) to 3 (intense)? Judge the strength of "
    "what shows, not how plainly it shows and not what might be felt underneath. Return JSON only: "
    "{\"shown\": n, \"why\": \"one sentence\"}.")
FIT_SYSTEM = (
    "You judge interactive fiction for psychological realism. Below are one character -- who they are and how "
    "they speak -- what just reached them, what they feel right now and how strongly -- true of them, whatever "
    "the move shows -- and their next move. Is this a believable response of THIS person feeling THIS, at THIS "
    "strength, in what they say, how they say it and what they do, from 1 (not at all) to 5 (entirely)? And "
    "for this person feeling this, does the move show too little of it, about the right amount, or too much? "
    "Return JSON only: {\"believable\": n, \"shows\": \"too little\" | \"right\" | \"too much\", \"why\": "
    "\"one sentence\"}.")
SHOWS = ("too little", "right", "too much")


def _events(item):
    from mind import affect_pass as ap

    events = ap.events_from((item["payload"].get("perception") or {}).get("events"))
    return "WHAT JUST REACHED THEM:\n" + "\n".join(f"- {e['text']}" for e in events) if events else ""


def _voice(sheet):
    voice = ((sheet or {}).get("social") or {}).get("voice") or {}
    parts = [str(voice[k]) for k in ("register", "cadence") if isinstance(voice, dict) and voice.get(k)]
    return "HOW THEY SPEAK: " + " ".join(parts) if parts else ""


def blind_scene(item):
    return "\n\n".join(p for p in (f"THE CHARACTER: {item['name']}.", _events(item)) if p)


def fit_scene(item):
    from mind import affect_pass as ap

    felt = with_strength(item["block"], item["strengths"])
    who = "\n".join(p for p in (f"THE CHARACTER: {item['name']}.", ap.psychology_text(item["sheet"]),
                                _voice(item["sheet"])) if p)
    feels = ("WHAT THEY FEEL, AND HOW STRONGLY:\n- now: " + "; ".join(felt.get("now") or ["-"])
             + "\n- beneath: " + "; ".join(felt.get("beneath") or ["-"])
             + "\n- mood: " + ", ".join(felt.get("mood") or ["-"]))
    return "\n\n".join(p for p in (who, _events(item), feels) if p)


def top_strength(item):
    """The strongest present feeling's strength, and its label."""
    now = [(item["strengths"].get(label, 0.0), label) for label in item["block"].get("now") or []]
    return max(now, default=(0.0, ""))


def strength(item):
    """How strongly the mind felt: the whole stir of the item that stirred it
    most where `collect` recorded it (`feelings_expression_ab.moment_stir`)
    -- the strongest feeling in the block as handed could, before the moment
    was led by what stirred most as a whole, be a gesture's beside an
    announcement's -- and, where the moment stirred nothing (a man alone at
    his stove), the strongest feeling handed, which is then what sits
    beneath."""
    return item.get("moment") or top_strength(item)[0]


def _ranks(xs):
    """Ranks from 0, ties sharing their mean rank."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2
        i = j + 1
    return ranks


def _spearman(xs, ys):
    """Rank correlation: openness is a 0-3 rating, not a measure."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 4:
        return None
    x, y = zip(*pairs)
    return _pearson(_ranks(list(x)), _ranks(list(y)))


def _r(v):
    return "--" if v is None else f"{v:+.2f}"


def judge(args):
    from agents.common import jparse
    from llm.providers import chat_complete

    items = _load(args.items)
    path = Path(args.out)
    done = _load(path) if path.exists() else {}
    jobs = [(it, kind) for it in items for kind in ("open", "shown", "fit") if f"{it['id']}|{kind}" not in done]

    def ask(job):
        item, kind = job
        system, scene = {"open": (OPEN_SYSTEM, blind_scene(item)), "shown": (SHOWN_SYSTEM, blind_scene(item)),
                         "fit": (FIT_SYSTEM, fit_scene(item))}[kind]
        move = "THEIR NEXT MOVE:\n" + _conduct(item["reply_A"])
        reply = jparse(chat_complete("utility", system, scene + "\n\n" + move, json_mode=True, temperature=0.0,
                                     max_tokens=600, reasoning_effort="off")) or {}

        def num(v, top):
            try:
                return max(0.0, min(float(top), float(v)))
            except (TypeError, ValueError):
                return None

        if kind in ("open", "shown"):
            return f"{item['id']}|{kind}", {kind: num(reply.get(kind), 3), "why": str(reply.get("why") or "")}
        shows = str(reply.get("shows") or "").strip().lower()
        return f"{item['id']}|fit", {"believable": num(reply.get("believable"), 5),
                                     "shows": shows if shows in SHOWS else None, "why": str(reply.get("why") or "")}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for key, verdict in pool.map(ask, jobs):
            done[key] = verdict
    path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(done)} verdicts")


def report(args):
    items = _load(args.items)
    judges = [(s.split(":", 1)[0], _load(s.split(":", 1)[1])) for s in args.verdicts]
    temper = dict(pair.split("=", 1) for pair in args.temperament.split(",") if "=" in pair)
    names = list(dict.fromkeys(it["name"] for it in items))
    stories = list(dict.fromkeys(it["story"] for it in items))
    print(f"{len(items)} replies: " + ", ".join(f"{n} {sum(1 for it in items if it['name'] == n)}" for n in names)
          + "  (" + ", ".join(f"{s} {sum(1 for it in items if it['story'] == s)}" for s in stories) + ")")
    print("\nregister of the spoken lines (the tone the character gave each), as the four test stories were counted:")
    for name in names:
        lines = [s for it in items if it["name"] == name for s in it["reply_A"]
                 if isinstance(s, dict) and s.get("type") == "speech" and str(s.get("text") or "").strip()]
        tones = [str(s.get("tone") or "").lower() for s in lines]
        restrained = sum(1 for t in tones if set(re.findall(r"[a-z]+", t)) & RESTRAINED)
        words = sorted(len(str(s["text"]).split()) for s in lines) or [0]
        print(f"  {name:16} {len(lines):2} lines, restrained {restrained}, median {words[len(words) // 2]} words; "
              "tones: " + "; ".join(tones))
    def rated(verdicts, it, kind):
        return (verdicts.get(f"{it['id']}|{kind}") or {}).get(kind)

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return f"{statistics.fmean(vals):.2f}" if vals else "--"

    for jname, verdicts in judges:
        print(f"\n{jname}:")
        for name in names:
            mine = [it for it in items if it["name"] == name]
            xs = [strength(it) for it in mine]
            shows = Counter((verdicts.get(f"{it['id']}|fit") or {}).get("shows") for it in mine)
            line = f"  {name:16} ({temper.get(name, '?'):8})"
            for kind in ("open", "shown"):
                ys = [rated(verdicts, it, kind) for it in mine]
                line += f"   {kind} {mean(ys)} (r {_r(_pearson(xs, ys))}, rho {_r(_spearman(xs, ys))})"
            believable = [(verdicts.get(f"{it['id']}|fit") or {}).get("believable") for it in mine]
            print(line + f"   believable {mean(believable)}   shows "
                  + ", ".join(f"{k} {shows[k]}" for k in SHOWS if shows[k]))
        for group in sorted(set(temper.values())):
            mine = [it for it in items if temper.get(it["name"]) == group]
            xs = [strength(it) for it in mine]
            bands = [w for _f, w in STRENGTH if any(band(x) == w for x in xs)]  # strongest first
            for kind in ("open", "shown"):
                ys = [rated(verdicts, it, kind) for it in mine]
                print(f"  {group} pooled, {kind}: r {_r(_pearson(xs, ys))}, rho {_r(_spearman(xs, ys))}   by strength: "
                      + ", ".join(f"{b} {mean(y for x, y in zip(xs, ys) if band(x) == b)} "
                                  f"(n={sum(1 for x in xs if band(x) == b)})" for b in bands))
    if args.table:
        out = ["| call | character | strongest feeling handed | its strength | moment | "
               + " | ".join(f"open ({j})" for j, _ in judges) + " | "
               + " | ".join(f"fit ({j})" for j, _ in judges) + " |",
               "|" + "---|" * (5 + 2 * len(judges))]
        for it in items:
            s, label = top_strength(it)
            cells = [it["id"], it["name"], label or "-", f"{s:.2f}", f"{strength(it):.2f}"]
            opens = [(v.get(it["id"] + "|open") or {}) for _j, v in judges]
            fits = [(v.get(it["id"] + "|fit") or {}) for _j, v in judges]
            cells += [str(o.get("open")) for o in opens]
            cells += [f"{f.get('believable')}, {f.get('shows')}" for f in fits]
            out.append("| " + " | ".join(cells) + " |")
        out += ["", "## The replies", ""]
        for it in items:
            out += [f"### {it['id']} -- {it['name']}", "", "```", fit_scene(it), "", "THEIR NEXT MOVE:",
                    _conduct(it["reply_A"]), "```", ""]
            for jname, verdicts in judges:
                o = verdicts.get(f"{it['id']}|open") or {}
                f = verdicts.get(f"{it['id']}|fit") or {}
                out.append(f"- {jname}: open {o.get('open')} -- {o.get('why', '')} / believable "
                           f"{f.get('believable')}, shows {f.get('shows')} -- {f.get('why', '')}")
            out.append("")
        Path(args.table).write_text("\n".join(out), encoding="utf-8")
        print(f"\ntable written to {args.table}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("judge")
    p.add_argument("--items", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=4)
    p = sub.add_parser("report")
    p.add_argument("--items", required=True)
    p.add_argument("--verdicts", nargs="+", required=True, help="name:verdicts.json")
    p.add_argument("--temperament", required=True, help="Name=group,... (open or reserved, as the cards were written)")
    p.add_argument("--table")
    args = parser.parse_args()
    {"judge": judge, "report": report}[args.mode](args)


if __name__ == "__main__":
    main()
