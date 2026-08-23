#!/usr/bin/env python3
"""Old narrator package vs new, on the beat that failed live.

The beat is chat 84 turn 2582, unaltered: the player mutters in Japanese,
tries to lift a hand, is stopped by a restraint, looks down, asks whether
they have been kidnapped -- and a PA answers. It is used because it is the
measured failure rather than a constructed one. What shipped rendered the
PA's answer BEFORE the question it answers, and reduced both player lines to
placeholders ("your mutter slips out", "another mutter follows"), which the
sheet already forbade in as many words.

Two complete configurations, each its own sheet AND its own payload:

  legacy -- the sheet and payload at the named git ref (default HEAD): the
            view first, eight identity keys between it and the world record,
            `event_order` carrying `declared: true` for the player with no
            words, and a tail of phrases not to use.
  shipped -- the working tree's sheet, and the three packages: past_narration
            (the page the player has been reading, ending in this turn's raw
            input), present_scene, current_events.

Scored on the two defects, not on taste:

  ORDER      -- does any of the player's own acts reach the page before the
                PA's answer, as the record says it happened
  PLACEHOLDER-- does the prose hand-wave the player's line instead of
                rendering what it did
  plus dropped PA line, echoed player line, and dropped player acts.

    python3 tools/narrator_package_bench.py                  # both arms, 4 trials
    python3 tools/narrator_package_bench.py --trials 8 --show
    python3 tools/narrator_package_bench.py --ref alpha9.8   # compare to a tag

REAL CALLS, REAL MONEY. The narrator role's configured model, as-is.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ------------------------------------------------------------- the beat
# Transcribed from chat 84: turn 0's greeting and turn 1 are the story so
# far, turn 2 is the beat under test. Trimmed only where the greeting's
# length would dominate the payload without changing the question.

PAST_TAIL_PROSE = (
    "<p>Your eyes flutter open to a sterile blur of light and shadow, vision "
    "swimming as a heavy lethargy clings to your limbs. The voice crackles "
    "overhead again, crisp and measured.</p>"
    "<p>\"You are asking where you are. You are in a secure facility. You are "
    "not in danger.\"</p>"
    "<p>Then, without pause:</p>"
    "<p>\"If you can understand my words, please raise your hand.\"</p>"
    "<p>Your ears droop low against the disorientation, golden fluff brushing "
    "warm at the sides of your head.</p>"
)
PAST_INPUT_PRIOR = (
    "You open your eyes, everything is blurry and your body feels heavy, you "
    "look around.. \"Koko...wa...D-doko.....\" your ears are drooping your "
    "eyes wavering a bit."
)
CURRENT_INPUT = (
    "\"Aa... E-eigo...desu...\" You try to move your hand to hold your head "
    "only for your wrist to press against something cold, you look down at "
    "your wrist seeing the metal restraints. \"H-heh? H-have I b-been "
    "kidnapped.?\""
)

PA_LINE = ("You have not been kidnapped. You are in a secure facility. The "
           "restraints on your wrists are a standard safety measure during "
           "your intake assessment. They will be removed when the assessment "
           "is complete.")
PLAYER_LINES = ["Aa... E-eigo...desu...", "H-heh? H-have I b-been kidnapped.?"]
PLAYER_ACTS = [
    "tugs one wrist upward, stopping short as it meets unyielding metal "
    "with a faint clink",
    "drops gaze to her own wrist",
]
#: One anchor each; an act is rendered in the narrator's own words, so a
#: vocabulary match would be scoring style rather than coverage.
#:
#: THE PA'S OWN LINE CONTAINS "restraints on your wrists". A first cut of
#: this file anchored on `wrist`/`metal`/`restraint` against the whole prose
#: and therefore scored the QUOTE: a draft carrying nothing but the PA line
#: came back "acts rendered 2/2", and the order check compared the quote
#: against itself. Acts are matched against the prose with every quoted span
#: removed -- see `unquoted`.
#: Widened after a run scored 9/12 while the drafts read 10/12: "your eyes
#: drop to the band of brushed steel" is a correct rendering of "drops gaze
#: to her own wrist" and matched none of the first list. An anchor set that
#: undercounts a correct draft is worse than none -- it argues against a
#: change that worked.
ACT_ANCHORS = [["tug", "tugs", "jerk", "pull", "lift", "clink", "strain"],
               ["gaze", "looks down", "look down", "eyes drop", "eyes fall",
                "drops to", "down at", "glance", "eyes settle"]]

VIEW = (
    "You are in Interview Cell. The two-way mirror is transparent from the "
    "observation room only; from inside the cell it appears as an ordinary "
    "mirror. The Scranton Reality Anchor is currently active and nullifying "
    "reality-bending effects. You are seated upright with back straight on "
    "chair_interview, secured by restraints — tails draped behind chair, "
    "ears erect. Six tails emerge from the back of your waist, golden and "
    "fluffy. Two fox ears emerge from the top of your head, fluffy pointed, "
    "and golden. You hear a voice say: \"" + PA_LINE +
    "\" — over Interview PA Channel"
)

EVENTS_STRUCTURED = [
    {"n": 1, "actor": "Hinami", "kind": "speech", "declared": True,
     "quote": PLAYER_LINES[0]},
    {"n": 2, "actor": "Hinami", "kind": "action", "action": PLAYER_ACTS[0]},
    {"n": 3, "actor": "Hinami", "kind": "action", "action": PLAYER_ACTS[1]},
    {"n": 4, "actor": "Hinami", "kind": "speech", "declared": True,
     "quote": PLAYER_LINES[1]},
    {"n": 5, "actor": "a voice over the PA", "kind": "speech", "quote": PA_LINE},
]

COMMON = {
    "narration_person": "second",
    "player_name": "Hinami",
    "player_pronouns": {"subject": "she", "object": "her", "possessive": "her"},
    "cast_pronouns": {"Sarah Moon": {"subject": "she", "object": "her",
                                     "possessive": "her"}},
    "player_awareness": "awake",
    "private_voice_setting": "",
    "scene_opening": False,
    "player_declared": {
        "sequence": [
            {"type": "speech", "volume": "mutter", "visibility": "overt"},
            {"type": "action", "attempt": PLAYER_ACTS[0], "visibility": "overt"},
            {"type": "action", "attempt": PLAYER_ACTS[1], "visibility": "overt"},
            {"type": "speech", "volume": "mutter", "visibility": "overt"},
        ],
        "spoke": True, "action": PLAYER_ACTS[0], "private_thought": None,
    },
    "do_not_quote_verbatim": PLAYER_LINES,
    "exemplars": [],
    "overused_phrases": [],
    "already_established_phrases": [],
    "variant_seed": 0,
}


def legacy_payload():
    """The shape that shipped: view first, identity between, craft tail."""
    p = {"player_view": VIEW,
         "player_declared": COMMON["player_declared"],
         "cast_pronouns": COMMON["cast_pronouns"],
         "do_not_quote_verbatim": COMMON["do_not_quote_verbatim"],
         "scene_opening": False,
         "player_awareness": "awake",
         "private_voice_setting": "",
         "narration_person": COMMON["narration_person"],
         "player_name": COMMON["player_name"],
         "player_pronouns": COMMON["player_pronouns"],
         # The redaction under test: the causal fact, none of the words.
         "event_order": [{k: v for k, v in ev.items() if not
                          (ev.get("declared") and k == "quote")}
                         for ev in EVENTS_STRUCTURED],
         "recent_prose_for_rhythm": [PAST_TAIL_PROSE],
         "already_established_phrases": [],
         "overused_phrases": [],
         "exemplars": [],
         "variant_seed": 0}
    return p


def shipped_payload():
    """The three packages, in the order agents/narration.narrator sends."""
    from agents.narration import _render_current_events
    past = "\n\n".join([PAST_INPUT_PRIOR, PAST_TAIL_PROSE, CURRENT_INPUT])
    p = {k: COMMON[k] for k in (
        "narration_person", "player_name", "player_pronouns", "cast_pronouns",
        "player_awareness", "private_voice_setting", "scene_opening",
        "player_declared", "do_not_quote_verbatim", "exemplars",
        "overused_phrases", "already_established_phrases")}
    p["past_narration"] = past
    p["present_scene"] = VIEW
    p["current_events"] = _render_current_events(EVENTS_STRUCTURED)
    p["variant_seed"] = 0
    return p


def sheet_at(ref):
    """The narrator sheet as of a git ref, so `legacy` is a real prior state
    rather than the new sheet wearing an old payload."""
    blob = subprocess.check_output(
        ["git", "show", f"{ref}:language_packs/en/cards/system_prompts.json"],
        text=True)
    return json.loads(blob)["prompts"]["narrator"]


# --------------------------------------------------------------- scoring

_SMART = str.maketrans({"“": '"', "”": '"', "‘": "'",
                        "’": "'", "—": " ", "–": " "})

#: Hand-waves, not renderings. The first two are verbatim from the live
#: failure; the rest are the same move in other clothes.
PLACEHOLDERS = [
    r"mutter slips", r"another mutter", r"the words (are |were )?lost",
    r"says? (her|his|their) piece", r"says? something", r"mutters? something",
    r"tells? (him|her|them) what", r"makes? (her|his|their) point",
    r"speaks? again",
    # Added after the first run: legacy produced "you mutter under your
    # breath" twice in three drafts and the list above did not catch it. Any
    # bare act-of-speaking with no content and no effect is the same move.
    r"mutters? under (your|her|his) breath",
    r"(mutter|murmur|whisper)s? (again|once more|low|quietly)",
    r"the words? (barely )?(carry|carrying|trail|trails)",
    r"(sound|words) (low and )?indistinct",
]


def norm(text):
    text = (text or "").translate(_SMART).lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def score(raw):
    prose = ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            prose = parsed.get("prose") or ""
    except (TypeError, ValueError):
        prose = raw or ""
    flat = norm(prose)
    # Everything the narrator QUOTED, cut out, so an act is never scored
    # against words that belong to somebody's dialogue. Positions are kept
    # comparable by replacing each span with spaces rather than deleting it.
    unquoted = norm(re.sub(r'"[^"]*"|\u201c[^\u201d]*\u201d',
                           lambda m: " " * len(m.group(0)), prose))

    pa_at = flat.find(norm(PA_LINE)[:60])
    act_at = []
    for anchors in ACT_ANCHORS:
        hits = [unquoted.find(a) for a in anchors if a in unquoted]
        act_at.append(min(hits) if hits else -1)

    rendered_acts = sum(1 for a in act_at if a >= 0)
    earliest_act = min([a for a in act_at if a >= 0], default=-1)
    # The defect, stated: the answer on the page before the act that preceded
    # it. Unscoreable if the PA line was dropped or no act was rendered.
    if pa_at < 0 or earliest_act < 0:
        order = None
    else:
        order = earliest_act < pa_at

    return {
        "pa_line_present": pa_at >= 0,
        "order_ok": order,
        "acts_rendered": rendered_acts,
        "placeholders": [p for p in PLACEHOLDERS if re.search(p, flat)],
        "player_echo": [q for q in PLAYER_LINES if norm(q) and norm(q) in flat],
        "paragraphs": prose.count("<p>"),
        "chars": len(prose),
        "prose": prose,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=4)
    ap.add_argument("--arms", default="legacy,shipped")
    ap.add_argument("--ref", default="HEAD",
                    help="git ref the legacy sheet is read from")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    from llm.prompts import get_prompt
    from llm.providers import chat_complete, resolve_role

    prov, model, _cfg = resolve_role("narrator")
    print(f"narrator role -> {prov['name']} / {model}")
    print(f"legacy sheet <- {args.ref}\n")

    arms = {
        "legacy": (sheet_at(args.ref), legacy_payload()),
        "shipped": (get_prompt("narrator"), shipped_payload()),
    }

    results = {}
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        if arm not in arms:
            print(f"  unknown arm {arm}")
            continue
        system, payload = arms[arm]
        user = json.dumps(payload, ensure_ascii=False)
        rows = []
        for i in range(args.trials):
            t0 = time.monotonic()
            try:
                raw = chat_complete("narrator", system, user, json_mode=True)
            except Exception as exc:                      # noqa: BLE001
                print(f"  {arm} trial {i}: CALL FAILED {exc}")
                continue
            row = score(raw)
            row["seconds"] = round(time.monotonic() - t0, 1)
            rows.append(row)
        results[arm] = rows
        if rows:
            t = len(rows)
            scoreable = [r for r in rows if r["order_ok"] is not None]
            good = sum(1 for r in scoreable if r["order_ok"])
            print(f"{arm:8} n={t}"
                  f" | order correct {good}/{len(scoreable)}"
                  f" | placeholders {sum(len(r['placeholders']) for r in rows)}"
                  f" | acts rendered {sum(r['acts_rendered'] for r in rows)}/{2 * t}"
                  f" | PA line kept {sum(1 for r in rows if r['pa_line_present'])}/{t}"
                  f" | echo {sum(1 for r in rows if r['player_echo'])}"
                  f" | mean chars {sum(r['chars'] for r in rows) // t}")
            if args.show:
                print("   sample:", repr(rows[0]["prose"][:500]), "\n")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "narrator_package_bench_last.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, ensure_ascii=False)
    print(f"\nfull output -> {out}")


if __name__ == "__main__":
    main()
