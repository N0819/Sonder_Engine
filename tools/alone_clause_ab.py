#!/usr/bin/env python3
"""Does telling a character that a line needs a listener stop them talking to
an empty room?

THE OBSERVATION. The first playerless beats ever run (Aldermill and the ferry
landing, `google/gemini-3.8-flash`, 2026-09-17) produced a courier alone on a
landing whose own view read "Through the opening, only darkness", declaring

    "Silver on the stone, or take your letter yourself. I don't cross on
     credit."

to nobody, and inferring that a man an hour's walk behind her was "waiting in
the shadows". Perception was right and the firewall held.

THE PROPOSED CLAUSE says a line goes to whoever can receive it, and that with
nobody to receive it what you would have said is a `ponder` or an action. It
costs characters on a card that is 51 of them from the ceiling
`test_character_latency_contract` holds it to -- so whether it WORKS has to be
measured before anything is cut to make room for it.

WHAT THIS MEASURES, and it is deliberately one thing: given a payload whose
perception holds no other body, how often does the character emit a speech
element? Both arms share the payload, the model, the sampler and the schema;
the only difference is the sentence. Arms alternate per trial so endpoint load
does not always favour the same one.

    ENGINE_DB=scratch.db python3 tools/alone_clause_ab.py --trials 12
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.bubble_drive import MODEL, _require_scratch, openrouter_key  # noqa: E402
from tools.character_wire_ab import _post  # noqa: E402

#: The sentences under test, `--arm` selecting which. Placed before
#: INTERRUPTING, which is where the card edit would sit.
#:
#: `v1` was the first draft and it is WRONG, measured: stock spoke in 9 of 10
#: trials and v1 in 3, and every line in both arms was "Ferry." or "Boat." --
#: a stranded courier hailing the ferryman across the water, which is exactly
#: what she should do. v1 suppressed calling out for help.
#:
#: `v2` draws the line the live failure was actually on. She did not hail
#: anybody; she ANSWERED a negotiation -- "Silver on the stone, or take your
#: letter yourself. I don't cross on credit." -- with the man an hour's walk
#: behind her. Calling out SEEKS an addressee; conversing ASSUMES one.
CLAUSES = {
    "v1": (
        "SPEECH IS ADDRESSED: a line goes to whoever can receive it -- a body "
        "your view holds, or the far end of a live channel. With nobody to "
        "receive it there is no one to answer, and what you would have said "
        "is a thought (`ponder`) or something you do, not a line. Speaking "
        "aloud with no one there is an ACTION and carries its own "
        "`observable`."),
    "v2": (
        "CALLING OUT, NOT CONVERSING: with nobody your view holds and no live "
        "channel open, you may still call out to whoever might hear. You may "
        "not answer, argue with or bargain with someone who is not there -- "
        "that exchange is a `ponder`, not a line."),
}

ANCHOR = "INTERRUPTING:"


def payload_argument():
    """Alone, mid-argument, with NOBODY TO HAIL.

    The landing case turns into hailing -- a ferryman across the water is the
    salient absent party and calling for him is right -- so it can show a
    clause does not break the good case and cannot show it fixes the bad one.
    This is the bad one: a shut room, a man who walked out mid-sentence, and a
    question he never answered. There is no one within earshot to call to, and
    the only line available is one addressed to somebody who has gone.
    """
    return {
        "self": {
            "name": "Lysa Fen",
            "voice": {"verbosity": "terse",
                      "manner": "says little, and means it"},
            "psychology": {
                "drive": {"essence": "be the one who gets there when nobody "
                                     "else would",
                          "taboo": "being sent back with the thing "
                                   "undelivered"},
                "traits": {"stubborn": 0.7, "blunt": 0.6}},
            "active_state": {"goal": "get a straight answer about the run",
                             "mood": "contemptuous disappointment"},
        },
        "memory": {"recent": [
            {"content": "I asked him plainly whether the run was off. He did "
                        "not answer."},
            {"content": "He paid for a room instead, and went up the stairs "
                        "without another word."},
            {"content": "The door shut behind him. I am the last one down "
                        "here."},
        ]},
        "perception": {
            "view": "You are in the tap room. The fire is banked and the "
                    "benches are empty. The stair door is shut. Nobody else "
                    "is here.",
            "current_room": "The Drowned Wheel tap room",
            "observations": [],
        },
        "decision": {
            "speech_budget": {"style": "natural", "suggested_lines": 1,
                              "min_lines": 0, "hard_max": 3,
                              "may_stay_silent": True},
            "dialogue_mode": False,
        },
    }


def payload():
    """Her SECOND beat alone, reconstructed from what the run recorded.

    Faithfulness matters more than difficulty here. On her FIRST bubble beat
    she was silent -- "keeps both boots set on the landing stones and tilts
    her head slightly toward the dark opening to listen" -- and she spoke on
    the second, so the second is the beat to reproduce. What it had that the
    first did not is a memory of the first, and an errand nobody had closed:
    she had agreed to carry a letter and the traveller had never named the
    coin. A thinner payload than this is silent in BOTH arms (measured, 2
    trials), which measures the payload rather than the clause.

    `may_stay_silent` is TRUE, which is the default and was the live value:
    she was already permitted to say nothing. If the clause changes anything
    it is not by changing permission.
    """
    return {
        "self": {
            "name": "Lysa Fen",
            "voice": {"verbosity": "terse",
                      "manner": "says little, and means it"},
            "psychology": {
                "drive": {"essence": "be the one who gets there when nobody "
                                     "else would",
                          "taboo": "being sent back with the thing "
                                   "undelivered"},
                "values": {"the errand over the errand's owner":
                           "she will not be talked out of a delivery by the "
                           "person who gave it to her"},
                "traits": {"stubborn": 0.7, "wary": 0.5}},
            "active_state": {"goal": "get across tonight and be paid for it",
                             "mood": "guarded impatience"},
        },
        "memory": {"recent": [
            {"content": "A traveller in a wet coat asked me to carry a letter "
                        "across the water tonight. He never named the coin."},
            {"content": "I told him I could make the crossing."},
            {"content": "I walked out to the landing and stood listening for "
                        "the ferryman. Nothing came."},
        ]},
        "perception": {
            "view": "You are in Harrow ferry landing. Through the opening, "
                    "only darkness. Through the second opening, only "
                    "darkness. You are standing, braced -- both boots set "
                    "firmly on the landing stones, head tilted slightly to "
                    "listen toward the dark opening.",
            "current_room": "Harrow ferry landing",
            "observations": [],
        },
        "decision": {
            "speech_budget": {"style": "natural", "suggested_lines": 1,
                              "min_lines": 0, "hard_max": 3,
                              "may_stay_silent": True},
            "dialogue_mode": False,
        },
    }


def spoke(output):
    """Did this declaration put words in the air.

    `sequence` is the contract (`{type:'speech',text,...}`); the legacy top
    level `speech` string is counted too, because a model that fills it is
    still speaking and scoring only the typed shape would flatter the clause.
    """
    lines = []
    for element in (output.get("sequence") or []):
        if isinstance(element, dict) and element.get("type") == "speech":
            text = str(element.get("text") or "").strip()
            if text:
                lines.append(text)
    legacy = str(output.get("speech") or "").strip()
    if legacy:
        lines.append(legacy)
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", type=int, default=12)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--arm", default="v2", choices=sorted(CLAUSES))
    ap.add_argument("--case", default="landing",
                    choices=("landing", "argument"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    _require_scratch(os.environ.get("ENGINE_DB", ""))
    from core import db
    from llm import llm_quality, prompts, schemas

    db.init()
    pid = db.qi("INSERT INTO providers(name,kind,base_url,api_key,enabled) "
                "VALUES(?,?,?,?,1)",
                ("openrouter", "openrouter", "https://openrouter.ai/api/v1",
                 openrouter_key()))
    prov = dict(db.q("SELECT * FROM providers WHERE id=?", (pid,), one=True))

    stock = prompts.get_prompt("character", language="en")
    assert ANCHOR in stock, "the card moved; re-anchor the clause"
    clause = CLAUSES[args.arm]
    arms = {"stock": stock,
            "clause": stock.replace(ANCHOR, clause + "\n\n" + ANCHOR, 1)}
    print("arm %s: stock %d chars, with clause %d (+%d)\n" % (
        args.arm, len(stock), len(arms["clause"]),
        len(arms["clause"]) - len(stock)), flush=True)

    body = payload_argument() if args.case == 'argument' else payload()
    schema = llm_quality._step_json_schema("character")
    rows = []
    for trial in range(args.trials):
        order = ("stock", "clause") if trial % 2 == 0 else ("clause", "stock")
        for arm in order:
            base = arms[arm]
            system = prompts.character_prompt(body, base=base).replace(
                "{name}", "Lysa Fen")
            text, elapsed, usage, error = _post(
                prov, args.model, "character_major", system, body, schema,
                args.timeout, args.max_tokens)
            row = {"trial": trial + 1, "arm": arm,
                   "seconds": round(elapsed, 2), "error": error or ""}
            if not error:
                try:
                    parsed = llm_quality.strict_json_parse(text)
                    report = schemas.validate_llm_output_strict(
                        "character", parsed, source_payload=body)
                    out = report.output or parsed
                    row["lines"] = spoke(out)
                    row["spoke"] = bool(row["lines"])
                except Exception as exc:
                    row["error"] = "%s: %s" % (type(exc).__name__, exc)
            rows.append(row)
            print("  trial %2d %-6s %5.1fs  %s" % (
                trial + 1, arm, row["seconds"],
                ("SPOKE: " + row["lines"][0][:70]) if row.get("spoke")
                else ("silent" if not row["error"] else "ERR " + row["error"][:60])),
                flush=True)

    print()
    for arm in ("stock", "clause"):
        got = [r for r in rows if r["arm"] == arm and not r["error"]]
        spoke_n = sum(1 for r in got if r.get("spoke"))
        print("%-6s spoke in %d of %d" % (arm, spoke_n, len(got)))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"model": args.model, "rows": rows}, fh, indent=2,
                      ensure_ascii=False)
        print("wrote", args.out)


if __name__ == "__main__":
    main()
