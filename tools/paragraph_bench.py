#!/usr/bin/env python3
"""Will the narrator mark paragraphs if we ask for a DELIMITER instead of a shape?

Everything tried so far asked the model to change the SHAPE of its reply and it
declined, four times out of four, measured:

  * "separate paragraphs with a blank line -- a literal \\n\\n in the `prose`
    string": one week live, 6 of 600 stored narrations complied (1%).
  * `paragraphs: [str]`, one element per paragraph: `paragraph_count` was 0 on
    every live variant. The model never emitted the field at all.

A delimiter is a different ask. It is not a shape -- it is characters inside a
string the model is already writing, needing no JSON escape and no new key. If
compliance is about shape reluctance, delimiters should sail through; if the
model simply will not follow paragraph instructions of any kind, they will fail
too, and that is worth knowing before anyone builds schema enforcement.

    python3 tools/paragraph_bench.py                    # all arms, 5 trials
    python3 tools/paragraph_bench.py --trials 3 --arms html,exotic

REAL CALLS, REAL MONEY. The narrator role's configured model is used as-is.
At ~6k in / ~400 out per call the whole default run is well under a cent on a
10c/M model, but it is not free and it is not a mock.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# A beat that CANNOT honestly be one paragraph: three speakers, a focus shift,
# and an action between two lines from the same character. Single-paragraph
# output against this payload is unambiguously wrong rather than a judgement
# call, which is what makes the measurement mean anything.
VIEW = (
    "The customs hall is loud with people who have been waiting too long. "
    "Sera stands at the counter with your papers in her hand. "
    "Bryn is three paces behind you, watching the doors. "
    "The clerk does not look up.\n"
    "Sera says: \"These are stamped for the wrong port.\"\n"
    "Sera sets the papers down on the counter and does not let go of them.\n"
    "Sera says: \"I want the supervisor.\"\n"
    "The clerk says: \"The supervisor left at four.\"\n"
    "Bryn says: \"Then we come back at four tomorrow.\"\n"
    "Behind the counter, a shutter comes down over the second window."
)

PAYLOAD = {
    "player_view": VIEW,
    "player_declared": {"sequence": [], "speech": None, "action": None,
                        "private_thought": None, "raw_input": "I wait."},
    "cast_pronouns": {"Sera": "she/her", "Bryn": "he/him",
                      "the clerk": "they/them"},
    "do_not_quote_verbatim": [],
    "scene_opening": False,
    "narration_person": "second",
    "player_name": "you",
    "player_pronouns": {},
    "recent_prose_for_rhythm": [],
    "already_established_phrases": [],
    "overused_phrases": [],
    "exemplars": [],
    "variant_seed": 0,
    "event_order": [
        {"n": 1, "actor": "Sera", "kind": "speech",
         "quote": "\"These are stamped for the wrong port.\""},
        {"n": 2, "actor": "Sera", "kind": "action",
         "what": "sets the papers down and does not let go"},
        {"n": 3, "actor": "Sera", "kind": "speech",
         "quote": "\"I want the supervisor.\""},
        {"n": 4, "actor": "the clerk", "kind": "speech",
         "quote": "\"The supervisor left at four.\""},
        {"n": 5, "actor": "Bryn", "kind": "speech",
         "quote": "\"Then we come back at four tomorrow.\""},
    ],
}

#: The formatting blocks currently in the narrator sheet, split by what they
#: are FOR. The distinction turned out to matter: an arm that cuts everything
#: gets a compliant delimiter and badly over-fragmented prose, because the
#: rules about when NOT to break went out with the rules about how.
#:
#: MECHANISM -- how a paragraph is physically made. A delimiter replaces all
#: of this, and leaving any of it in means telling the model two different
#: things at once.
#:
#: THESE ARE ALL GONE FROM THE LIVE SHEET, deleted when the <p> contract
#: landed. They are kept here so the losing arms can be REBUILT and re-run
#: against a new model; `strip_formatting` reporting 0 found is expected now,
#: not a warning about the live prompt.
MECHANISM_MARKERS = (
    "MARK PARAGRAPHS WITH <p> AND </p>.",
)
#: JUDGEMENT -- when a break belongs. Orthogonal to how it is written, and the
#: owner's own rules: one speaker owns a paragraph across their own actions,
#: capped at two spoken lines and one action.
JUDGEMENT_MARKERS = (
    "Give a line of dialogue its own paragraph",
    "ONE SPEAKER OWNS A PARAGRAPH",
    "THE CEILING ON THAT IS TWO SPOKEN LINES",
)
CUT_MARKERS = MECHANISM_MARKERS + JUDGEMENT_MARKERS


def strip_formatting(sheet, markers=CUT_MARKERS):
    """Remove every formatting block, leaving craft and fidelity rules intact.

    Each block runs to the next blank line, which is how the sheet is written.
    Returns (stripped_sheet, how_many_blocks_were_found) so a silent miss --
    the sheet being reworded out from under this file -- is visible in the
    output rather than quietly weakening every arm.
    """
    out, found = sheet, 0
    for marker in markers:
        at = out.find(marker)
        if at < 0:
            continue
        found += 1
        end = out.find("\n\n", at)
        out = out[:at] + (out[end + 2:] if end > 0 else "")
    return out, found


def contract(open_tag, close_tag):
    return (
        f"PARAGRAPHS. Wrap every paragraph of `prose` in {open_tag} and "
        f"{close_tag}. Write {open_tag} immediately before the first character "
        f"of a paragraph and {close_tag} immediately after its last. Every "
        f"paragraph gets its own pair, including the first and the last. Do "
        f"not use line breaks; the markers are how a paragraph reaches the "
        f"reader. Start a new paragraph when the speaker changes or the focus "
        f"moves.\n\n"
    )


ARMS = {
    # THE LIVE CONTRACT, unchanged: the narrator sheet now carries the <p>
    # instruction itself. This is the arm to run after changing narrator
    # models -- compliance is model-dependent (the array contract scored 2/5
    # on grok-4.20 and 0/4 live on gpt-5.6-luna-pro), so a new model is a
    # reason to re-measure rather than assume.
    "live": {"cut": (), "extra": "", "open": "<p>", "close": "</p>"},
    # Everything cut -- compliant delimiter, but nothing left telling it when
    # NOT to break, which is how you get a paragraph per line of dialogue.
    "html": {"cut": CUT_MARKERS, "extra": contract("<p>", "</p>"),
             "open": "<p>", "close": "</p>"},
    # THE SHIPPABLE SHAPE: delimiter replaces the mechanism, the owner's
    # judgement rules stay.
    "html_owned": {"cut": MECHANISM_MARKERS, "extra": contract("<p>", "</p>"),
                   "open": "<p>", "close": "</p>"},
    "exotic": {"cut": CUT_MARKERS, "extra": contract("[[P]]", "[[/P]]"),
               "open": "[[P]]", "close": "[[/P]]"},
    # One marker instead of two: fewer tokens, and nothing to mismatch.
    "sep": {"cut": CUT_MARKERS, "open": "[[BREAK]]", "close": None, "extra": (
        "PARAGRAPHS. Write [[BREAK]] between paragraphs -- not at the start, "
        "not at the end, only between. Do not use line breaks; the marker is "
        "how a paragraph reaches the reader. Break when the speaker changes "
        "or the focus moves.\n\n")},
}


def score(arm, raw):
    """What came back, in the terms the decision needs."""
    prose = ""
    parsed = None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            prose = parsed.get("prose") or ""
            if not prose and isinstance(parsed.get("paragraphs"), list):
                prose = "\n\n".join(str(p) for p in parsed["paragraphs"])
    except (TypeError, ValueError):
        prose = raw or ""

    spec = ARMS[arm]
    o, c = spec.get("open"), spec.get("close")
    opens = prose.count(o) if o else 0
    closes = prose.count(c) if c else 0
    return {
        "used_array": isinstance(parsed, dict)
        and isinstance(parsed.get("paragraphs"), list)
        and bool(parsed["paragraphs"]),
        "opens": opens,
        "closes": closes,
        "balanced": (opens == closes) if (o and c) else None,
        # What a reader would actually get, by whichever route this arm offers.
        "paragraphs": (
            len(parsed["paragraphs"]) if (isinstance(parsed, dict)
                                          and isinstance(parsed.get("paragraphs"), list)
                                          and parsed["paragraphs"])
            else (opens if (o and c) else (opens + 1 if o else 0))
            or (prose.count("\n\n") + 1 if prose.strip() else 0)
        ),
        "chars": len(prose),
        "prose": prose,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--show", action="store_true", help="print one sample each")
    args = ap.parse_args()

    from llm.prompts import get_prompt
    from llm.providers import chat_complete, resolve_role

    prov, model, _cfg = resolve_role("narrator")
    print(f"narrator role -> {prov['name']} / {model}\n")

    sheet = get_prompt("narrator")
    _probe, found = strip_formatting(sheet)
    print(f"formatting blocks locatable in the sheet: {found} of "
          f"{len(CUT_MARKERS)} (the judgement blocks were deleted when the "
          f"<p> contract landed; 1 of {len(CUT_MARKERS)} is the healthy "
          f"reading)\n")

    user = json.dumps(PAYLOAD, ensure_ascii=False)
    results = {}
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        spec = ARMS[arm]
        cut = spec.get("cut") or ()
        system = (strip_formatting(sheet, cut)[0] if cut else sheet) + spec["extra"]
        rows = []
        for i in range(args.trials):
            t0 = time.monotonic()
            try:
                raw = chat_complete("narrator", system, user, json_mode=True)
            except Exception as exc:                      # noqa: BLE001
                print(f"  {arm} trial {i}: CALL FAILED {exc}")
                continue
            row = score(arm, raw)
            row["seconds"] = round(time.monotonic() - t0, 1)
            rows.append(row)
        results[arm] = rows
        if rows:
            got = sum(1 for r in rows if r["paragraphs"] > 1)
            mean_p = sum(r["paragraphs"] for r in rows) / len(rows)
            bal = [r["balanced"] for r in rows if r["balanced"] is not None]
            print(f"{arm:8} multi-paragraph {got}/{len(rows)}"
                  f" | mean paragraphs {mean_p:.1f}"
                  f" | balanced {sum(1 for b in bal if b)}/{len(bal)}"
                  if bal else
                  f"{arm:8} multi-paragraph {got}/{len(rows)}"
                  f" | mean paragraphs {mean_p:.1f}")
            if args.show:
                print("   sample:", repr(rows[0]["prose"][:400]), "\n")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "paragraph_bench_last.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, ensure_ascii=False)
    print(f"\nfull output -> {out}")


if __name__ == "__main__":
    main()
