#!/usr/bin/env python3
"""Raise a crowd through the real commit path, then walk into it.

`crowds.py` shipped pure and correct and could not occur: perception read
`wget(cid, "crowds")` faithfully and nothing in the engine ever wrote that key.
Unit tests can assert that each link exists. Only a drive can show the chain
carrying a crowd from a Director's declaration, through validation, into world
state, and back out of the perception surface as terrain -- which is the exact
sequence where every off-screen bug of the previous drive actually lived.

WHAT THIS CAN AND CANNOT PROVE. It exercises machinery: crowd_ops -> commit ->
world key -> per-observer payload -> density derived against the room -> drift
offered -> movement on the spatial graph -> split. It CANNOT tell you whether a
model will ever WRITE a crowd_op, because the harness supplies the payload a
Director would have produced. Asking it how often crowds appear would be asking
whether the author of the harness typed one. That number only moves in a real
playthrough, and `tools/fire_rates.py` is where it should be read.

Writes only to its own scratch database, and refuses to start against anything
that looks like the author's.

    ENGINE_DB=/path/to/scratch.db python3 tools/crowd_drive.py
    ENGINE_DB=/path/to/scratch.db python3 tools/crowd_drive.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.offscreen_drive import _Chat, _Ctx, _require_scratch  # noqa: E402

#: A gate passage and the square beyond it, one open doorway apart. The sizes
#: are the whole point: the SAME crowd is a crush in one and loose in the
#: other, so the escape that was impossible in the gateway is simply available
#: because the geometry changed and nothing else did.
GATE, SQUARE = "gate_passage", "market_square"


def scene():
    return {
        "location": "Lugunica",
        "rooms": {
            GATE: {"name": "Gate Passage", "size": "small",
                   "adjacent": [{"to": SQUARE, "barrier": "open"}]},
            SQUARE: {"name": "Market Square", "size": "huge",
                     "adjacent": [{"to": GATE, "barrier": "open"}]},
        },
        "positions": {"Mora": GATE},
        "entities": {},
    }


def build_story(db):
    """A story with nothing switched on, and one registered character.

    Deliberately bare otherwise. Crowds are on-screen atmosphere rather than
    off-screen simulation, so they are NOT gated behind a living-world setting,
    and a harness that quietly configured one would hide it if they were.

    Mora is a REAL cast row rather than a name passed to the harness, because
    `_registered_name_roster` reads `extant_cast` out of the database and
    parses the sheet. A hand-built cast list produces an empty roster, the
    named-character guard then refuses nobody, and the drive reports a rule
    holding that is not running -- which is the failure mode every tool in
    this directory exists to catch.
    """
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Crowd drive", "", time.time()))
    sheet = json.dumps({"identity": {"name": "Mora", "uid": "mora_uid"}})
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mora", sheet, "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
          "VALUES(?,?,'active','{}',NULL)", (cid, char_id))
    return cid


def make_ctx(db, cid, turn_idx, ops, cast=(), dialogue=()):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, turn_idx, "", time.time()))
    return _Ctx(
        chat=_Chat(id=cid, name="Crowd drive"),
        turn=types.SimpleNamespace(id=turn_id, idx=turn_idx, frame_id=None),
        cast=list(cast),
        character_results={}, warnings=[], extra_players=[],
        director_resolve={"state_diff": {"crowd_ops": ops},
                          "dialogue_log": list(dialogue)},
    )


def beat(db, cid, turn_idx, ops, cast=(), dialogue=()):
    """One Director declaration through the real commit domain."""
    from persist.commit import commit_crowds

    ctx = make_ctx(db, cid, turn_idx, ops, cast=cast, dialogue=dialogue)
    with db.transaction():
        result = commit_crowds(ctx, {"scene": scene()}) or {}
    return result, list(ctx.warnings)


def observed(cid, room):
    """What a body standing in `room` actually receives."""
    from agents.common import crowds_for_room

    return crowds_for_room(cid, scene(), room)


def drive(report):
    from core import db

    cid = build_story(db)
    report["chat_id"] = cid
    steps = []

    # 1. A Director raises a crowd. No crowd_id: the engine mints it.
    result, warnings = beat(db, cid, 1, [{
        "op": "set", "room": GATE, "band": "a few dozen",
        "composition": "pilgrims and gate traffic", "mood": "impatient",
    }])
    here = observed(cid, GATE)
    steps.append({
        "step": "a crowd is raised in the gate passage",
        "commit": result, "warnings": warnings,
        "minted_uid_is_not_a_name": bool(here) and
        here[0]["uid"].startswith("crowd:") and
        "pilgrim" not in here[0]["uid"],
        "observer_sees": here,
    })
    if not here:
        report["steps"] = steps
        report["verdict"] = "the crowd never reached the perception surface"
        return report
    uid = here[0]["uid"]

    # 2. The same crowd, seen from the square it is NOT standing in. Perception
    #    is room-scoped, so somebody in a back office must not receive the
    #    state of the square outside.
    steps.append({
        "step": "an observer in the next room over",
        "observer_sees": observed(cid, SQUARE),
    })

    # 3. Two ops the engine must refuse, offered together with a good one so
    #    the harness also shows a rejection does not poison the beat.
    result, warnings = beat(db, cid, 2, [
        {"op": "set", "crowd_id": "the pilgrims", "room": GATE,
         "composition": "pilgrims"},
        {"op": "set", "room": "the harbour", "composition": "dockworkers"},
        {"op": "set", "crowd_id": uid, "heading": SQUARE},
    ])
    steps.append({
        "step": "an invented id and an unauthored room, beside a good op",
        "commit": result, "warnings": warnings,
        "still_standing": len(observed(cid, GATE)),
    })

    # 4. THE OBSERVATION THE WHOLE FEATURE RESTS ON. The crowd is still here,
    #    and it is going somewhere -- so the press has a current the Director
    #    can be shown and asked to resolve. Spending the heading in the commit
    #    that declared it made this `drift: null` forever, which is the defect
    #    this drive found on its first run.
    caught = observed(cid, GATE)
    steps.append({
        "step": "caught in it: a crush in a small gate passage, going somewhere",
        "observer_sees": caught,
        "drift_is_offered": bool(caught) and bool(caught[0]["drift"]),
    })

    # 5. An ordinary beat, no ops at all. Last beat's flow is spent now, so the
    #    crowd is watched leaving rather than teleporting on declaration.
    result, warnings = beat(db, cid, 3, [])
    steps.append({
        "step": "an ordinary beat: the press moves through the gate",
        "commit": result, "warnings": warnings,
        "left_in_gate": len(observed(cid, GATE)),
    })

    # 6. The same crowd in a huge square. Nothing about it changed.
    moved = observed(cid, SQUARE)
    steps.append({
        "step": "the room releases you, the crowd does not decide to",
        "gate_passage": {"density": caught[0]["density"],
                         "terrain": caught[0]["terrain"],
                         "drift": caught[0]["drift"]},
        "market_square": {"density": moved[0]["density"],
                          "terrain": moved[0]["terrain"],
                          "drift": moved[0]["drift"]} if moved else None,
        "same_crowd": bool(moved) and moved[0]["uid"] == uid,
    })

    # 7. A knot peels off toward the gate. Band-preserving: both halves are one
    #    band down, and there are two rows where there was one.
    result, warnings = beat(db, cid, 4, [
        {"op": "split", "crowd_id": uid, "heading": GATE}])
    steps.append({
        "step": "a knot peels off toward the shouting",
        "commit": result, "warnings": warnings,
        "square": [c["what"] for c in observed(cid, SQUARE)],
        "gate": [c["what"] for c in observed(cid, GATE)],
    })

    # 8. Someone steps out. Two of them, and one is a cast member the crowd
    #    must refuse to produce.
    #    The uid is read AFTER the peeled half has spent its heading and gone,
    #    or the emergence lands on a crowd that is no longer in this room --
    #    which is what the first run of this step actually did.
    beat(db, cid, 5, [])
    square_uid = observed(cid, SQUARE)[0]["uid"]
    result, warnings = beat(db, cid, 6, [
        {"op": "emerge", "crowd_id": square_uid, "who": "a rope-seller"},
        {"op": "emerge", "crowd_id": square_uid, "who": "Mora"},
    ])
    steps.append({
        "step": "a stranger steps out, and a cast member may not",
        "commit": result, "warnings": warnings,
        "standing_out_of_it": observed(cid, SQUARE)[0]["emerged"],
        "band_unchanged": observed(cid, SQUARE)[0]["what"],
    })

    # 9. The one-way rule, adjudicated against what the beat actually recorded
    #    rather than against what the Director says about it.
    result, warnings = beat(
        db, cid, 7,
        [{"op": "absorb", "who": "a rope-seller"}],
        dialogue=[{"speaker": "a rope-seller",
                                  "text": "Two coppers the fathom."}])
    steps.append({
        "step": "someone who spoke tries to go back into the crowd",
        "commit": result, "warnings": warnings,
        "still_standing_out": observed(cid, SQUARE)[0]["emerged"],
    })

    # 10. And someone who only moved.
    beat(db, cid, 8, [
        {"op": "emerge", "crowd_id": square_uid, "who": "a man with a basket"},
    ])
    result, warnings = beat(
        db, cid, 9, [{"op": "absorb", "who": "a man with a basket"}],
        dialogue=[{"speaker": "Mora", "text": "Let me past."}])
    steps.append({
        "step": "someone who only stepped aside goes back",
        "commit": result, "warnings": warnings,
        "still_standing_out": observed(cid, SQUARE)[0]["emerged"],
    })

    report["steps"] = steps
    return report


def summarize(report):
    lines = []
    for step in report.get("steps", []):
        lines.append("- %s" % step["step"])
        for key, value in step.items():
            if key == "step":
                continue
            lines.append("    %-26s %s" % (key, json.dumps(value)))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = _require_scratch()
    from core import db

    db.init()
    report = {"database": path}
    drive(report)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(summarize(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
