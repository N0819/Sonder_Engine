"""Replay a chat's recorded speech decisions through today's hearing model.

Every `speech_percept` decision perception records (`_engine_notes.decisions`,
"<level> via <how>; volume <v>, barrier <b>, tier <t>") is graded again by the
engine's own `composer.line_hear_level`, on the scene of its turn as the
checkpoints hold it. CHECKPOINT N IS THE WORLD BEFORE TURN N (written with the
turn row, `web/app.py:_insert_turn_row`; settled 2026-10-11), so the onset pass
(`perception_act`) is graded on checkpoint idx and the outcome pass on idx+1 --
the chat's live world for its last turn. Until 2026-10-20 this read idx-1 and
idx, one beat early. What comes back:

  * how often the replay reproduces the recorded grade (not always: a scene
    moves inside a beat, and the act pass's reach tier is the pass's own);
  * the grades the current code gives;
  * the REASON for every grade short of `full`, in the hearing rule's own
    words (`spatial.hearing_reason`: breath beyond reach, a shut door from
    farther off, a heavy door or glass, a wall, rooms away, a deafening
    source, no air between the two) -- the question a hearing complaint
    needs answered first.

Built for the owner's "Sound gatings is entirely overzealous" (2026-09-26,
`docs/UNBUILT_PERCEPTION.md` § 1.167), where it measured 508 decisions in four
test stories before and after the change; used again for the hearing rule's
restatement (2026-10-20, § 1.159). Read-only: the database is opened
`mode=ro` and nothing is written.

Run from the repository root:
    python tools/speech_replay.py --db story.db [--db other.db] [--chat 1] [--show]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.common import CROWDS_KEY  # noqa: E402
from agents.composer import line_hear_level  # noqa: E402
from world.spatial import (hearing_reason, room_of, sound_field,  # noqa: E402
                           spatial_rel_between)

#: The frame separator world rows are keyed with (`key` + SEP + "fr<id>").
SEP = "\x1e"
REASON = re.compile(r"^(\w+) via ([^;]+); volume (\w+), barrier ([\w-]+), tier ([\w-]+)")
TIERS = ("within_reach", "near", "across")


def _world_at(con, chat, idx):
    """The world BEFORE turn `idx` (its checkpoint), or the chat's live world
    when no such checkpoint exists -- the world after its last turn."""
    row = con.execute("SELECT blob FROM checkpoints WHERE chat_id = ? AND turn_idx = ?",
                      (chat, idx)).fetchone()
    if row:
        return (json.loads(row[0]) or {}).get("world") or {}
    return {key: json.loads(value) for key, value in
            con.execute("SELECT key, value FROM world WHERE chat_id = ?", (chat,))}


def _key(name, frame):
    return name if not frame else f"{name}{SEP}fr{frame}"


def grade(scene, listener, speaker, volume, tier, idx, crowds):
    """(word, relation) for one line, the way perception builds them."""
    field = sound_field(scene, listener, room=room_of(scene, listener), turn_idx=idx, crowds=crowds)
    rel = spatial_rel_between(scene, listener, speaker, sound=field)
    word = line_hear_level({"volume": volume, "text": "x", "speaker": speaker}, rel, listener,
                           proximity=tier if tier in TIERS else None)
    return word, rel


def cause(volume, tier, word, rel):
    """Why a line is short of `full`, in the hearing rule's own words."""
    if word == "full":
        return ""
    return hearing_reason(rel, volume, proximity=tier if tier in TIERS else None) \
        or "other"


def replay(db, chat=1, show=False):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT t.idx, t.frame_id, s.key, v.content FROM turns t JOIN steps s ON s.turn_id = t.id "
        "JOIN variants v ON v.step_id = s.id AND v.active = 1 WHERE t.chat_id = ? AND "
        "s.key IN ('perception_act', 'perception_outcome') ORDER BY t.idx", (chat,)).fetchall()
    agree, now, causes, lines = Counter(), Counter(), Counter(), []
    # Only the two blobs a step reads are kept, never every checkpoint: a
    # world holds the story's charters, which run to megabytes.
    parsed = {}
    for idx, frame, step, content in rows:
        notes = (json.loads(content) or {}).get("_engine_notes") or {}
        decisions = [d for d in notes.get("decisions") or [] if d.get("kind") == "speech_percept"]
        if not decisions:
            continue
        at = idx if step == "perception_act" else idx + 1
        if (at, frame) not in parsed:
            world = _world_at(con, chat, at)
            parsed = {(at, frame): (world.get(_key("scene", frame)) or {},
                                    world.get(_key(CROWDS_KEY, frame)) or [])}
        scene, crowds = parsed[(at, frame)]
        if isinstance(scene, str):
            scene = json.loads(scene)
        if isinstance(crowds, str):
            crowds = json.loads(crowds)
        if not scene:
            continue
        for d in decisions:
            m = REASON.match(str(d.get("reason") or ""))
            if not m:
                continue
            level, _how, volume, barrier, tier = m.groups()
            speaker, _, listener = str(d.get("subject") or "").partition(" -> ")
            word, rel = grade(scene, listener, speaker, volume, tier, idx, crowds)
            agree[word == level] += 1
            now[word] += 1
            why = cause(volume, tier, word, rel)
            if why:
                causes[(word, why)] += 1
            if show and word != "full":
                lines.append(f"   t{idx} {step[11:]:7s} {speaker} -> {listener} ({volume}, {barrier}, "
                             f"{tier}): recorded {level}, now {word}: {why}")
    total = sum(agree.values())
    print(f"== {db}: {total} decisions; the replay reproduces the recorded grade on "
          f"{agree[True]} ({100 * agree[True] / max(1, total):.0f}%); grades now "
          f"{dict(sorted(now.items()))}")
    for (word, why), n in sorted(causes.items(), key=lambda kv: -kv[1]):
        print(f"   {n:3d} {word:8s} {why}")
    for line in lines:
        print(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", action="append", required=True, help="a database to read (repeatable)")
    parser.add_argument("--chat", type=int, default=1)
    parser.add_argument("--show", action="store_true", help="list every line short of full")
    args = parser.parse_args(argv)
    for db in args.db:
        replay(db, chat=args.chat, show=args.show)


if __name__ == "__main__":
    main()
