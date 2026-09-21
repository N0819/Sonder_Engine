#!/usr/bin/env python3
"""Each life, rendered as its own story from only what that life holds.

The companion to `tools/two_lives_drive.py`. After thirty rounds in two
causality bubbles, this turns each character's own ledger into prose --
separately, and with no access to the other's.

WHAT EACH GENERATOR IS HANDED, and the list is the whole point:

  * that character's memory rows, through `mind.memory.visible_memory_rows`
    under their OWN frame -- the one seam a mind's rows come out of, which
    has already applied the frame gate and the char_id filter;
  * their interior state (`chat_chars.state` under their frame): drive,
    goal, mood, intentions, what they are carrying;
  * their own place graph -- the rooms they walked, as they recorded them.

WHAT IT IS NOT HANDED: the scene, the other character's anything, the run's
log, the town's registry, or the narrator's view of any beat (there was no
narrator -- a bubble's beat has none). If the two stories agree about
something, both of them were there for it.

THE POINT OF WRITING IT THIS WAY is that it is a firewall test wearing a
deliverable's clothes. A story that knows something its character could not
have known is a leak, and it is legible as one -- prose is much easier to
audit than a payload.

    ENGINE_DB=lives.db python3 tools/two_lives_stories.py --out DIR
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.bubble_drive import MODEL, _require_scratch  # noqa: E402
from tools.character_wire_ab import _post  # noqa: E402

SYSTEM = """You are given one person's own record of a stretch of their life:
what they remember, what they were trying to do, how they felt, and the places
they walked. Write their story.

Write it as THEIRS. Past tense, close third person, from inside their head --
what they noticed, what they thought it meant, what they decided. You have no
access to anyone else's knowledge and must not invent any: if they never
learned a name, they do not know it; if they were never told why something
happened, the story does not explain it. An absence in the record is an
absence in the life, not a gap for you to fill.

Do not summarise the record back. Write the prose a reader would read: scenes
where the record has them, connective narration where it does not, and their
own judgement of what was happening. Where the record is repetitive, say what
the repetition was like to live through rather than repeating it.

Length: 600-900 words. No headings, no preamble, no notes about the record."""


def life(cid, char_id, name, frame_id):
    """One character's own slice. Nothing here reads another's anything."""
    from core.db import q
    from mind.memory import visible_memory_rows
    from story.scene import char_state

    rows = visible_memory_rows(cid, char_id, before_turn_idx=None,
                               viewer_frame_id=frame_id, include_archived=False)
    memories = [{"turn": r["turn_idx"], "kind": r["kind"],
                 "provenance": r["provenance"], "content": r["content"]}
                for r in rows]
    raw = char_state(cid, char_id, frame_id=frame_id) or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            raw = {}
    sheet = q("SELECT sheet FROM characters WHERE id=?", (char_id,), one=True)
    card = json.loads(sheet["sheet"]) if sheet else {}
    return {
        "name": name,
        "who_they_are": {
            "drive": (card.get("psychology") or {}).get("drive"),
            "values": (card.get("psychology") or {}).get("values"),
            "traits": (card.get("psychology") or {}).get("traits"),
        },
        "where_they_started": (card.get("initial_state") or {}).get("goals"),
        "state": {k: raw.get(k) for k in
                  ("active_state", "interior", "place_graph") if raw.get(k)},
        "memories": memories,
    }


def _story_from(text):
    """``(story, truncated)`` out of one generator reply.

    The envelope is `{"story": "..."}`, and a reply the token budget cut ends
    inside that string -- so `json.loads` raises and the old `except` wrote the
    RAW JSON into the .md file, braces and literal \\n and all (v7's
    sal_weatherby.md). Salvage the prose that did arrive and SAY it was cut,
    because a story that stops mid-sentence is a failed render either way and
    the one thing worse than a short story is a short story nobody noticed.
    """
    text = text or ""
    if not text.strip().startswith("{"):
        return text, False
    try:
        body = json.loads(text)
        if isinstance(body, dict):
            return str(body.get("story") or ""), False
    except Exception:
        pass
    # Unterminated envelope: take everything after the opening quote of
    # "story" and read the escapes the JSON decoder would have.
    marker = '"story"'
    at = text.find(marker)
    if at < 0:
        return text, True
    at = text.find('"', at + len(marker) + 1)
    if at < 0:
        return text, True
    salvaged = text[at + 1:]
    try:
        salvaged = json.loads('"%s"' % salvaged.replace('"', '\\"'))
    except Exception:
        salvaged = salvaged.replace("\\n", "\n").replace('\\"', '"')
    return salvaged, True


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chat", type=int, default=1)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--timeout", type=float, default=300.0)
    # REASONING SPENDS THIS BUDGET TOO, and on these models it spends most of
    # it (90-97% of a Director specialist's output is reasoning trace). At
    # 6000 the v7 render came back with 19 words for a life of 61 memories and
    # 193 for one of 44, both cut mid-sentence: the prose was what was left.
    ap.add_argument("--max-tokens", type=int, default=24000)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    _require_scratch(os.environ.get("ENGINE_DB", ""))
    from core import db
    from core.frames import get_frame
    from story.character_schema import character_name, normalized_character_from_text
    from story.scene import active_cast

    prov = dict(db.q("SELECT * FROM providers WHERE kind='openrouter' "
                     "ORDER BY id LIMIT 1", one=True))
    cid = args.chat

    # One live bubble per life; each frame answers for exactly one body.
    frames = {}
    for row in db.q("SELECT id FROM frames WHERE chat_id=? AND kind='spatial' "
                    "AND merged_turn_idx IS NULL ORDER BY id", (cid,)):
        for cast_row in active_cast(cid, row["id"]):
            nm = character_name(normalized_character_from_text(cast_row["sheet"]))
            frames[nm] = (row["id"], cast_row["id"])

    out = {}
    for name in sorted(frames):
        frame_id, char_id = frames[name]
        payload = life(cid, char_id, name, frame_id)
        print("%-16s frame %-3s %3d memories" % (
            name, frame_id, len(payload["memories"])), flush=True)
        text, elapsed, usage, error = _post(
            prov, args.model, "narrator", SYSTEM, payload, None,
            args.timeout, args.max_tokens)
        story, cut = "", False
        if not error:
            story, cut = _story_from(text)
        out[name] = {"frame": frame_id, "char_id": char_id,
                     "memories": len(payload["memories"]),
                     "seconds": round(elapsed, 1), "error": error or "",
                     "record": payload, "story": story or ""}
        out[name]["truncated"] = cut
        print("   %.0fs %s%s" % (elapsed, error[:80] if error else "ok",
                                 "  TRUNCATED (raise --max-tokens)" if cut
                                 else ""), flush=True)

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "two_stories.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
        for name, row in out.items():
            slug = name.lower().replace(" ", "_") + ".md"
            with open(os.path.join(args.out, slug), "w", encoding="utf-8") as fh:
                fh.write("# %s\n\n%s\n" % (name, row["story"]))
        print("wrote", args.out, flush=True)
    return out


if __name__ == "__main__":
    main()
