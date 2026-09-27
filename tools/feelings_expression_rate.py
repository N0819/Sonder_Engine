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
  openly feelings show in it, 0 to 3;
- `fit` -- a judge sees the card's psychology and voice, what reached them,
  what they feel and how strongly, and the reply, and says whether it is a
  believable response of this person (1 to 5) and whether it shows too
  little, about the right amount or too much for this person feeling this.

`report` gives each character's openness per judge, its correlation with the
strongest present feeling's strength within each temperament, and the fit
verdicts, one judge at a time (never their mean).

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

from feelings_expression_ab import RESTRAINED, _conduct, _load, _pearson, band, with_strength  # noqa: E402

OPEN_SYSTEM = (
    "You read interactive fiction. Below are a character's name, what just reached them, and their next move: "
    "what they say, how they say it, and what they do. Rate how openly the character's feelings show in this "
    "move, from 0 (not at all: nothing of what they feel shows) to 3 (fully: what they feel is plain in their "
    "words, their voice or their body). Rate what shows, not whether it suits them. Return JSON only: "
    "{\"open\": n, \"why\": \"one sentence\"}.")
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


def judge(args):
    from agents.common import jparse
    from llm.providers import chat_complete

    items = _load(args.items)
    path = Path(args.out)
    done = _load(path) if path.exists() else {}
    jobs = [(it, kind) for it in items for kind in ("open", "fit") if f"{it['id']}|{kind}" not in done]

    def ask(job):
        item, kind = job
        system, scene = (OPEN_SYSTEM, blind_scene(item)) if kind == "open" else (FIT_SYSTEM, fit_scene(item))
        move = "THEIR NEXT MOVE:\n" + _conduct(item["reply_A"])
        reply = jparse(chat_complete("utility", system, scene + "\n\n" + move, json_mode=True, temperature=0.0,
                                     max_tokens=600, reasoning_effort="off")) or {}

        def num(v, top):
            try:
                return max(0.0, min(float(top), float(v)))
            except (TypeError, ValueError):
                return None

        if kind == "open":
            return f"{item['id']}|open", {"open": num(reply.get("open"), 3), "why": str(reply.get("why") or "")}
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
    print(f"{len(items)} replies: " + ", ".join(f"{n} {sum(1 for it in items if it['name'] == n)}" for n in names))
    print("\nregister of the spoken lines (the tone the character gave each), as the four test stories were counted:")
    for name in names:
        lines = [s for it in items if it["name"] == name for s in it["reply_A"]
                 if isinstance(s, dict) and s.get("type") == "speech" and str(s.get("text") or "").strip()]
        tones = [str(s.get("tone") or "").lower() for s in lines]
        restrained = sum(1 for t in tones if set(re.findall(r"[a-z]+", t)) & RESTRAINED)
        words = sorted(len(str(s["text"]).split()) for s in lines) or [0]
        print(f"  {name:16} {len(lines):2} lines, restrained {restrained}, median {words[len(words) // 2]} words; "
              "tones: " + "; ".join(tones))
    for jname, verdicts in judges:
        print(f"\n{jname}:")
        for name in names:
            mine = [it for it in items if it["name"] == name]
            opens = [(verdicts.get(f"{it['id']}|open") or {}).get("open") for it in mine]
            believ = [(verdicts.get(f"{it['id']}|fit") or {}).get("believable") for it in mine]
            shows = Counter((verdicts.get(f"{it['id']}|fit") or {}).get("shows") for it in mine)
            r = _pearson([top_strength(it)[0] for it in mine], opens)
            o = [v for v in opens if v is not None]
            b = [v for v in believ if v is not None]
            print(f"  {name:16} ({temper.get(name, '?'):8}) open {statistics.fmean(o) if o else float('nan'):.2f}"
                  f"   r(open, strength) " + ("--" if r is None else f"{r:+.2f}")
                  + f"   believable {statistics.fmean(b) if b else float('nan'):.2f}   shows "
                  + ", ".join(f"{k} {shows[k]}" for k in SHOWS if shows[k]))
        for group in sorted(set(temper.values())):
            mine = [it for it in items if temper.get(it["name"]) == group]
            r = _pearson([top_strength(it)[0] for it in mine],
                         [(verdicts.get(f"{it['id']}|open") or {}).get("open") for it in mine])
            by_band = {}
            for it in mine:
                v = (verdicts.get(f"{it['id']}|open") or {}).get("open")
                if v is not None:
                    by_band.setdefault(band(top_strength(it)[0]), []).append(v)
            print(f"  {group} pooled: r(open, strength) " + ("--" if r is None else f"{r:+.2f}") + "   by strength: "
                  + ", ".join(f"{b} {statistics.fmean(v):.2f} (n={len(v)})" for b, v in by_band.items()))
    if args.table:
        out = ["| call | character | strongest feeling now | strength | "
               + " | ".join(f"open ({j})" for j, _ in judges) + " | "
               + " | ".join(f"fit ({j})" for j, _ in judges) + " |",
               "|" + "---|" * (4 + 2 * len(judges))]
        for it in items:
            s, label = top_strength(it)
            cells = [it["id"], it["name"], label or "-", f"{s:.2f}"]
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
