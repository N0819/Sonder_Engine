"""The prelude: the Writers' Room is asked before the story starts
(`docs/design/DESIGN_ROOM_PRELUDE.md`).

Two launches open a story, and until now neither asked. The player picked a
persona, a greeting, a lorebook and a horizon, pressed start, and the next
thing that happened was a story -- with the inhabited place around it
designed by one `utility` model call from a sentence typed into a text box.
Who designs that place is `story/location_design.py`'s subject; this module
is the PAUSE that lets the player say what they want from the story before
any of it is built.

The prelude is the pause that fixes both. A launch that takes it CREATES THE
STORY AND STOPS: the chat row, the cast, the language and the lorebook are
seeded, the pending launch is kept whole in `story_setup`, the Room reads the
passage and asks one question, and nothing else happens until the player says
begin. What they say back is ordinary room conversation -- the same thread,
the same routes, the same planner -- so nothing here re-implements a chat.

This module holds the STATE: the pending launch, the record, and the reader
that hands what the player said to the two passes that use it -- the location
design and the opening plan, both in `agents/story_planner.py`. The launches
themselves stay where they are, in `story/greetings.py` and `web/app.py`.

WHY A SETUP IS KEPT WHOLE RATHER THAN RE-SENT. The browser could post the
same arguments again at `begin`, and then a story's ground would depend on a
form still being open in a tab. The launch is a decision the player already
made; it is recorded once, at the moment they made it, and `begin` is a
button that says go -- which is also what makes the failed-setup path
(2026-09-08) able to pick a prelude up, because everything its retry needs is
already on the chat.
"""

from __future__ import annotations

import copy
import time

from core.db import q, wget, wset

#: The launch this chat is holding open, as the launch screen sent it:
#: `{"kind": "greeting"|"scenario", "args": {...}, "at": float}`. Present
#: means the story has been created and not yet begun; `begin` clears it.
#: Unframed deliberately -- a prelude happens before there is a frame to
#: scope anything to.
SETUP_KEY = "story_setup"

#: What the prelude did: `{"asked": str, "at": float, "began": float}`.
#: Kept after the story begins, because the question the Room asked is part
#: of how the ground came to be what it is.
PRELUDE_KEY = "prelude"

#: What the Room says when it could not write its own line -- the model was
#: down, the budget ran out, the pass raised. It is the question the prelude
#: exists to ask, so a launch that loses the Room still gets the pause.
#: English is the message id, as everywhere else the engine speaks in the
#: panel's voice; the UI catalog carries the translation.
PRELUDE_FALLBACK_LINE = (
    "Before we open this one: is there anything in particular you want from "
    "this story -- a place, a mood, something you want waiting there? Say so, "
    "or just begin and I will work from the page.")


def pending_setup(cid):
    """The launch this chat is holding open, or {}."""
    row = wget(int(cid), SETUP_KEY, {}) or {}
    return copy.deepcopy(row) if isinstance(row, dict) else {}


def record_setup(cid, kind, args):
    """Keep the launch whole so `begin` needs nothing from the browser."""
    row = {"kind": str(kind), "args": copy.deepcopy(args or {}),
           "at": time.time()}
    wset(int(cid), SETUP_KEY, row)
    return row


def clear_setup(cid):
    """The story began: the pending launch is spent."""
    wset(int(cid), SETUP_KEY, {})


def awaiting_begin(cid):
    """True while the Room has the floor: a setup is pending and no turn has
    been written. The turn test is the one that cannot lie -- a setup row
    left behind by a launch that went on to run turn 0 anyway would
    otherwise hold a live story at the door forever."""
    if not pending_setup(cid):
        return False
    return not q("SELECT id FROM turns WHERE chat_id=? LIMIT 1",
                 (int(cid),), one=True)


def record_prelude(cid, **fields):
    row = {**(wget(int(cid), PRELUDE_KEY, {}) or {}), **fields}
    wset(int(cid), PRELUDE_KEY, row)
    return row


def prelude_record(cid):
    return wget(int(cid), PRELUDE_KEY, {}) or {}


def player_wants(cid, frame_id=None):
    """WHAT THE PLAYER SAID BEFORE THE STORY STARTED, in their own words.

    The location design and the opening plan both read this: it is the
    whole point of the pause. Only the player's own lines, because the Room's are
    its own and would come back to it as if the player had said them; and
    only lines from before the first beat, because a prelude ends when the
    story begins and everything after it is ordinary room conversation about
    a story that is already running."""
    from story import room_conversation as room

    began = float(prelude_record(cid).get("began") or 0.0)
    out = []
    for row in room.messages(int(cid), frame_id, limit=room.ROOM_PAGE):
        if row.get("role") != "player":
            continue
        if began and float(row.get("created") or 0.0) > began:
            continue
        text = str(row.get("text") or "").strip()
        if text:
            out.append(text)
    return out


def begin_story(cid):
    """The player said go: run the launch the prelude was holding open.

    ONE finisher for both launches, because "begin" means the same thing on
    each -- everything the launch screen decided, plus everything the player
    said to the Room since. A greeting resumes the quick start it stopped in
    the middle of (`start_story` asks the CHAT what is already there, so the
    seeding above the cut is not repeated); a scenario chat has no turn to
    run yet, so its ground is built and the first beat waits for the player,
    exactly as a scenario chat always has.

    The pending setup is cleared only on success: a begin that fails leaves
    the story where the failed-setup path can pick it up, which is the whole
    reason it is stored on the chat rather than re-sent by the browser.
    """
    setup = pending_setup(cid)
    if not setup:
        raise ValueError("this story has no launch waiting")
    # THE PRELUDE ENDS HERE, AND IT ENDS BEFORE THE WORK. `player_wants`
    # cuts the thread at this timestamp, so the lines the two passes below
    # read are exactly the ones said while the Room had the floor -- and a
    # line typed into the panel while the launch runs belongs to the story,
    # not to its prelude.
    record_prelude(cid, began=time.time())
    kind = str(setup.get("kind") or "")
    args = setup.get("args") if isinstance(setup.get("args"), dict) else {}
    if kind == "greeting":
        from story.greetings import start_story
        chat_id, turn_id = start_story(
            int(args.get("char_id")), int(args.get("persona_id")),
            int(args.get("greeting_index") or 0),
            lorebook_id=args.get("lorebook_id"),
            already_known=bool(args.get("already_known", True)),
            language=args.get("language"),
            lived_location=args.get("lived_location"),
            resume_chat_id=int(cid))
        clear_setup(cid)
        return {"chat_id": int(chat_id), "turn_id": turn_id,
                "began": True}
    # A scenario chat: building the place is the whole of what begin does.
    # Turn 0 runs when the player writes their first line, and the opening
    # plan runs with it (`web/app.turn_new`), by then over a planted town.
    request = args.get("lived_location")
    built = None
    if isinstance(request, dict) and request.get("enabled", True):
        from world.charter_runtime import generate_lived_location
        from world.structure import registry_rows
        request = copy.deepcopy(request)
        chat = q("SELECT scenario FROM chats WHERE id=?", (int(cid),), one=True)
        passage = str((chat or {})["scenario"] if chat else "") or ""
        if not registry_rows(int(cid)):
            # In the story's own language, the same as every other path
            # into the generator (`web.app.charters_generate`).
            from agents.story_planner import room_town_planner
            from language_runtime import story_language_scope
            with story_language_scope(int(cid)):
                built = generate_lived_location(
                    int(cid), request,
                    town_planner=room_town_planner(int(cid)))
    clear_setup(cid)
    return {"chat_id": int(cid), "turn_id": None, "began": True,
            "location": bool(built)}
