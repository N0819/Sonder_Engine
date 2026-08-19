#!/usr/bin/env python3
"""Play a story with a human-or-model author answering each stage for real.

Every other drive in this directory stubs the model with something valid and
inert, which is right for proving a MECHANISM fired and wrong for anything
about prose. `tools/quest_drive.py` returned "The hall is busy." to every
perceiver on every beat, and its narrator echoed the Director's one-line
resolution -- so its transcript reads flat, and that flatness says nothing
about the engine. It was two of my own stubs in series.

This runs in two passes over the same scripted beats:

  pass 1  play with inert defaults, writing every stage's real payload to disk
  ...     an author (a person, or a model reading those files) writes answers
  pass 2  replay the identical beats with those answers scripted in

The second pass sees near-identical payloads because the authored answers only
change PROSE fields -- views and narration -- and never state. Where an answer
is missing, the inert default is used and the beat is marked, so a partly
answered story is honest about which beats were written and which were not.

The point is to find out what the engine's perception payload actually
SUPPORTS. A view composed from `crowds[].talk`, `ambient_location`, `light`
and the contact ledger is evidence about the payload; "The hall is busy." is
evidence about the stub.

    ENGINE_DB=scratch.db python3 tools/live_drive.py --capture DIR      # pass 1
    ENGINE_DB=scratch.db python3 tools/live_drive.py --answers DIR --out DIR
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.offscreen_drive import _require_scratch  # noqa: E402
from tools.quest_drive import (KEEP, MARKET, ROAD, TOWN, WELL,  # noqa: E402
                               QuestAuthor, build_story, scene)


class AnsweredAuthor(QuestAuthor):
    """Uses a written answer where one exists; the inert default otherwise.

    Answers are keyed `"<turn>:<stage>"`. A missing answer is not an error --
    it is a beat nobody wrote yet, and it is counted so the report can say how
    much of the story is genuinely authored rather than implying all of it is.
    """

    def __init__(self, answers=None):
        super().__init__()
        self.answers = answers or {}
        self.answered = set()
        self.unanswered = set()

    def _for(self, step_key):
        turn = getattr(self, "_turn", -1)
        stage = step_key.split(":")[0]
        written = self.answers.get("%d:%s" % (turn, stage))
        if written is not None:
            self.answered.add((turn, stage))
            return written
        if stage in ("perception", "narrator"):
            self.unanswered.add((turn, stage))
        return super()._for(step_key)


#: A short story on purpose. Answering a stage honestly means READING what it
#: was handed, and a fifty-beat story answered properly is three hundred reads.
#: Eight beats answered for real say more about the payload than fifty stubbed.
def beats(author, cid):
    def R(prose, **over):
        out = author.default("director_resolve")
        diff = out["state_diff"]
        for key, value in over.pop("diff", {}).items():
            diff[key] = value
        out["resolved_event"] = prose
        out.update(over)
        return out

    return [
        ("I come up the road into the market.",
         R("Corin comes into the square.",
           diff={"positions": {"Corin": MARKET}})),
        # The crowd is declared on the SECOND beat. The first turn of a story
        # runs `director_establish`, not `director_resolve`, so crowd ops
        # written into the opening beat's `state_diff` go to a stage that
        # never runs -- they are not rejected, they are never offered, and
        # every later beat here then had no crowd to steer and no way to say
        # so. `tools/quest_drive.py` declares its crowd on beat six for the
        # same reason.
        ("I stand still and listen to them.",
         R("The talk goes on around him.",
           diff={"crowd_ops": [{"op": "set", "room": MARKET,
                                "band": "a throng",
                                "composition": "villagers with empty pails",
                                "mood": "frightened"}]})),
        ("I look at the well.",
         R("The cover is grey stone and will not shift.")),
        # The heading has to name the crowd_id the payload showed. A `set`
        # carrying only a room and a heading does not steer the crowd standing
        # there -- it tries to MINT one and is refused for having no
        # composition, so this beat used to declare a drift that never
        # happened and said nothing about it.
        ("I push through toward the far side.",
         lambda p: R("The press gives, slowly.", diff={"crowd_ops": [
             {"op": "set", "crowd_id": c["crowd_id"], "heading": ROAD}
             for c in ((p or {}).get("crowds") or [])[:1] if c.get("crowd_id")
         ]})),
        ("I ask the nearest woman what happened here.",
         R("She tells him what she saw.",
           dialogue_log=[{"speaker": "Sera",
                          "text": "It closed itself. I watched it."}])),
        ("I wait for the square to empty.",
         R("It does not empty.",
           diff={"time": {"start_seconds": 0, "duration_seconds": 5400,
                          "end_seconds": 5400, "mode": "time_skip",
                          "explicit": True,
                          "display_advance": "an hour and a half"}})),
        ("I go back to the well.",
         R("It is exactly as it was.")),
        ("I take the road east.",
         R("The road runs out between dead hedges.",
           diff={"positions": {"Corin": ROAD}})),
    ]


def play(db, cid, author, script, capture_dir=""):
    from agents.runtime import run_pipeline

    author.capture_dir = capture_dir
    played = []
    for idx, (player_input, payload) in enumerate(script):
        author.script(idx, "director_resolve", payload)
        # A beat whose payload depends on what the engine SHOWED that turn --
        # a crowd_id, a world_event_id -- has to be a callable, because those
        # ids do not exist when the script is written. Its speech and movement
        # are read off attributes instead, exactly as `tools/quest_drive.py`
        # does it.
        static = payload if isinstance(payload, dict) else {}
        for line in (static.get("dialogue_log")
                     or getattr(payload, "dialogue_log", None) or []):
            if isinstance(line, dict) and line.get("text"):
                spoken = dict(author.default("character"))
                spoken["sequence"] = [{"type": "speech", "text": line["text"]}]
                author.script(idx, "character", spoken)
                break
        moved = ((static.get("state_diff") or {}).get("positions") or {}
                 ).get("Corin") or getattr(payload, "moves_to", None)
        if moved:
            interp = author.default("director_interpret")
            if callable(interp):
                interp = interp({"player_input": player_input})
            interp["movement"] = {"to_room": moved, "manner": "walk"}
            author.script(idx, "director_interpret", interp)
        author.current_turn(idx)
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (cid, idx, player_input, time.time(), None))
        error = ""
        try:
            for _ in run_pipeline(cid, tid):
                pass
        except Exception as exc:              # noqa: BLE001 - reported
            error = "%s: %s" % (type(exc).__name__, exc)
        played.append({"turn": idx, "input": player_input, "turn_id": tid,
                       "error": error})
    return played


def transcript(played, prose, answered):
    lines = ["# The Vale, answered",
             "",
             "Eight beats. Every view and every line of narration below was",
             "written by an author READING the payload the engine actually",
             "delivered for that beat -- the crowd's band and talk, the light,",
             "the ambient location, the contact ledger -- rather than returned",
             "by a stub.",
             "",
             "Beats marked *(unanswered)* fell back to the inert default and",
             "are left in so the difference is visible.",
             "",
             "---", ""]
    for row in played:
        mark = "" if (row["turn"], "narrator") in answered else "  *(unanswered)*"
        lines.append("### %d. %s%s" % (row["turn"] + 1, row["input"], mark))
        lines.append("")
        text = prose.get(row["turn_id"]) or ""
        if text:
            lines.append(text)
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture", default="")
    ap.add_argument("--answers", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    _require_scratch()
    from core import db as db_module
    from llm import llm_quality

    db_module.init()

    answers = {}
    if args.answers:
        path = os.path.join(args.answers, "answers.json")
        if os.path.exists(path):
            answers = json.load(open(path))
    author = AnsweredAuthor(answers)
    llm_quality.complete_validated_json = author
    for mod in list(sys.modules.values()):
        if getattr(mod, "complete_validated_json", None) is not None \
                and mod is not llm_quality:
            mod.complete_validated_json = author

    cid = build_story(db_module)
    script = beats(author, cid)
    played = play(db_module, cid, author, script, capture_dir=args.capture)

    print("beats: %d | errors: %d" % (
        len(played), len([p for p in played if p["error"]])))
    print("answered stages: %d | fell back to a stub: %d"
          % (len(author.answered), len(author.unanswered)))

    if args.out:
        rows = db_module.q(
            "SELECT s.turn_id, v.content FROM variants v "
            "JOIN steps s ON s.id = v.step_id "
            "WHERE v.active=1 AND s.key='narrator' ORDER BY s.turn_id") or []
        prose = {}
        for row in rows:
            try:
                blob = json.loads(row["content"])
            except (TypeError, ValueError):
                continue
            if isinstance(blob, dict):
                prose[row["turn_id"]] = str(blob.get("prose") or "")
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "transcript.md"), "w") as fh:
            fh.write(transcript(played, prose, author.answered))
        # THE WIRED SERVICE, not the class. `export_chat` is an instance
        # method: it dereferences `self._remap` inside the frames loop, so
        # `ChatArchiveService.export_chat(None, cid)` worked only until a
        # chat had a `frames` row -- and a frame split happens on its own,
        # after the run is paid for. `web.app` owns the one wiring of the
        # remappers; borrowing it cannot drift from what the route does.
        from web.app import chat_export
        with open(os.path.join(args.out, "story.json"), "w") as fh:
            json.dump(chat_export(cid), fh, indent=1, default=str)
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
