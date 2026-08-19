#!/usr/bin/env python3
"""What `remember_lines` is actually keeping, and whether any of it comes back.

Durable dialogue used to be a fixed phrase list -- promises, "my name is", a
handful of confessions -- which is why the corpus holds 149 dialogue rows
against thousands of episodes. A warning, an instruction, a code, an indirect
threat, a newly established fact all failed it. Rather than lengthening the
list, the character says: one mind keeps an insult another shrugs off.

That makes memory formation psychology-dependent, which is the point, and it
also makes it unmeasured. Nothing in the schema separates a line the model
chose to keep from one the phrase list would have kept anyway, so "the
character decides" and "the list decided and the character agreed" look
identical in the bank.

They are separable without a migration, because the phrase list is a pure
function of the quote: a kept line the list would have REJECTED is one only
this character's judgement preserved. That is the population worth measuring,
and this tool measures it:

  * marks emitted, per character and per 100 turns
  * marks that became a row at all
  * marks the fixed list would have caught anyway (the redundant share)
  * how often kept lines are later RETRIEVED, against every other dialogue row
  * whether giving a `why` predicts a line later coming back

The last one is the question a budget or a novelty gate would depend on, and
the plan is deliberately not to build either until these numbers exist.

    python3 tools/remember_lines.py
    python3 tools/remember_lines.py --json

Read-only, same as tools/fire_rates.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _phrase_list_would_keep(text):
    """`persist/commit_memory.py`'s `_durable_dialogue_category` (re-exported
    by the `commit` facade), inlined rather than imported so this tool never
    pulls the engine -- and its database configuration -- in behind it. Kept in
    sync by test_remember_lines_telemetry.py, which asserts the two agree on
    every phrase."""
    lowered = (text or "").lower()

    def _spoken(marker):
        # Word boundary at the marker's start, inflection allowed at its end
        # -- "I promised" matches, "compromised" does not. Mirrors
        # commit_memory.
        return re.search(r"\b" + re.escape(marker), lowered) is not None

    if any(_spoken(w) for w in ("promise", "i swear", "i vow",
                                "you have my word", "i'll return",
                                "i will return")):
        return "promise"
    if any(_spoken(w) for w in ("my name is", "call me", "i confess",
                                "the truth is", "i killed", "i betrayed",
                                "i love you", "i hate you", "i'll kill",
                                "i will kill")):
        return "dialogue"
    return None


def _norm(text):
    return " ".join(str(text or "").split()).casefold()


def _quote_body(text):
    """The words inside the quotation marks, or the whole string."""
    match = re.search(r'["“‘\'](.+?)["”’\']', str(text or ""),
                      re.S)
    return (match.group(1) if match else str(text or "")).strip()


def collect(con):
    turns = {r["id"]: (r["chat_id"], r["idx"]) for r in
             con.execute("SELECT id, chat_id, idx FROM turns")}
    turns_per_chat = {}
    for chat_id, _idx in turns.values():
        turns_per_chat[chat_id] = turns_per_chat.get(chat_id, 0) + 1

    marks = []          # every remember_lines entry the corpus ever emitted
    chances = 0         # results that carried the field at all
    for row in con.execute(
            "SELECT s.turn_id, v.content FROM variants v "
            "JOIN steps s ON s.id = v.step_id "
            "WHERE v.active=1 AND s.key IN ('interaction_loop','reaction_loop')"):
        try:
            blob = json.loads(row["content"])
        except (TypeError, ValueError):
            continue
        results = (blob or {}).get("character_results")
        if isinstance(results, dict):
            results = list(results.values())
        for result in results or []:
            if not isinstance(result, dict) or "remember_lines" not in result:
                continue
            chances += 1
            for mark in result.get("remember_lines") or []:
                if not isinstance(mark, dict):
                    continue
                marks.append({
                    "turn_id": row["turn_id"],
                    "chat_id": turns.get(row["turn_id"], (None, None))[0],
                    "name": str(result.get("name") or ""),
                    "char_id": result.get("char_id"),
                    "quote": _quote_body(mark.get("quote")),
                    "why": str(mark.get("why") or "").strip(),
                })

    # Every dialogue row in the bank, so a mark can be matched to what it made.
    rows = list(con.execute(
        "SELECT id, chat_id, char_id, turn_id, gist, content, category, "
        "access_count, salience, importance FROM memories "
        "WHERE kind='dialogue'"))
    by_chat_char = {}
    for row in rows:
        by_chat_char.setdefault((row["chat_id"], row["char_id"]), []).append(row)

    landed = redundant = only_judgement = 0
    retrieved_kept = retrieved_listed = 0
    with_why = with_why_retrieved = 0
    per_character = {}
    for mark in marks:
        body = _norm(mark["quote"])
        hit = None
        for row in by_chat_char.get((mark["chat_id"], mark["char_id"]), ()):
            gist = _norm(row["gist"])
            if body and (body in gist or gist.endswith(body)):
                hit = row
                break
        slot = per_character.setdefault(
            mark["name"] or str(mark["char_id"]),
            {"marks": 0, "landed": 0, "redundant": 0, "retrieved": 0,
             "with_why": 0})
        slot["marks"] += 1
        if mark["why"]:
            with_why += 1
            slot["with_why"] += 1
        if hit is None:
            continue
        landed += 1
        slot["landed"] += 1
        was_listed = _phrase_list_would_keep(mark["quote"]) is not None
        if was_listed:
            redundant += 1
            slot["redundant"] += 1
        else:
            only_judgement += 1
        came_back = (hit["access_count"] or 0) > 0
        if came_back:
            slot["retrieved"] += 1
            if was_listed:
                retrieved_listed += 1
            else:
                retrieved_kept += 1
            if mark["why"]:
                with_why_retrieved += 1

    # The baseline every "did it come back" number has to be read against.
    all_dialogue = len(rows)
    all_retrieved = sum(1 for r in rows if (r["access_count"] or 0) > 0)
    other = list(con.execute(
        "SELECT access_count FROM memories WHERE kind!='dialogue'"))
    other_retrieved = sum(1 for r in other if (r["access_count"] or 0) > 0)

    total_turns = sum(turns_per_chat.values()) or 1
    return {
        "chances": chances,
        "marks": len(marks),
        "marks_per_100_turns": len(marks) / total_turns * 100,
        "turns": total_turns,
        "landed": landed,
        "unmatched": len(marks) - landed,
        "redundant_with_phrase_list": redundant,
        "only_this_character_kept_it": only_judgement,
        "with_why": with_why,
        "retrieval": {
            "kept_by_judgement_retrieved": retrieved_kept,
            "kept_by_judgement": only_judgement,
            "phrase_listed_retrieved": retrieved_listed,
            "phrase_listed": redundant,
            "with_why_retrieved": with_why_retrieved,
            "with_why": with_why,
            "all_dialogue_retrieved": all_retrieved,
            "all_dialogue": all_dialogue,
            "non_dialogue_retrieved": other_retrieved,
            "non_dialogue": len(other),
        },
        "per_character": per_character,
    }


def _pct(part, whole):
    return f"{part/whole*100:5.1f}%" if whole else "  n/a "


def render(report):
    r = report["retrieval"]
    lines = [
        f"{report['marks']} marked lines over {report['turns']} turns "
        f"({report['marks_per_100_turns']:.1f} per 100 turns), "
        f"from {report['chances']} beats that could carry one",
        "",
        "  WHAT BECAME OF THEM",
        f"    landed as a memory row      {report['landed']:>5}"
        f"  {_pct(report['landed'], report['marks'])}",
        f"    no matching row             {report['unmatched']:>5}"
        f"  {_pct(report['unmatched'], report['marks'])}",
        f"    the fixed list had it too   "
        f"{report['redundant_with_phrase_list']:>5}"
        f"  {_pct(report['redundant_with_phrase_list'], report['landed'])}"
        "   of landed -- these needed no character judgement",
        f"    only this mind kept it      "
        f"{report['only_this_character_kept_it']:>5}"
        f"  {_pct(report['only_this_character_kept_it'], report['landed'])}"
        "   of landed -- the population the feature exists for",
        f"    gave a reason (`why`)       {report['with_why']:>5}"
        f"  {_pct(report['with_why'], report['marks'])}",
        "",
        "  DID IT COME BACK (access_count > 0)",
        f"    kept by judgement           "
        f"{r['kept_by_judgement_retrieved']:>5}/{r['kept_by_judgement']:<5}"
        f"  {_pct(r['kept_by_judgement_retrieved'], r['kept_by_judgement'])}",
        f"    kept by the phrase list     "
        f"{r['phrase_listed_retrieved']:>5}/{r['phrase_listed']:<5}"
        f"  {_pct(r['phrase_listed_retrieved'], r['phrase_listed'])}",
        f"    marked with a reason        "
        f"{r['with_why_retrieved']:>5}/{r['with_why']:<5}"
        f"  {_pct(r['with_why_retrieved'], r['with_why'])}",
        f"    every dialogue row          "
        f"{r['all_dialogue_retrieved']:>5}/{r['all_dialogue']:<5}"
        f"  {_pct(r['all_dialogue_retrieved'], r['all_dialogue'])}",
        f"    every non-dialogue row      "
        f"{r['non_dialogue_retrieved']:>5}/{r['non_dialogue']:<5}"
        f"  {_pct(r['non_dialogue_retrieved'], r['non_dialogue'])}",
        "",
        "  BY CHARACTER (one mind keeps what another shrugs off)",
    ]
    width = max((len(k) for k in report["per_character"]), default=10)
    for name, slot in sorted(report["per_character"].items(),
                             key=lambda kv: -kv[1]["marks"]):
        lines.append(
            f"    {name:<{width}}  marks {slot['marks']:>3}  "
            f"landed {slot['landed']:>3}  redundant {slot['redundant']:>3}  "
            f"retrieved {slot['retrieved']:>3}  why {slot['with_why']:>3}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=os.environ.get("ENGINE_DB", "engine.db"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.exists(args.db):
        sys.exit(f"no database at {args.db}")
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        report = collect(con)
    finally:
        con.close()
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
