"""The Story Planner: the Writers' Room's author, seated on the panel's seam.

NOT A PIPELINE STAGE. Nothing here runs inside a turn: the Planner answers
the player's line in the room panel (`story/room_conversation.PLANNER`) and
runs the out-of-band jobs the commit tail schedules -- the fill (planting
ahead asked first as one compact call, `story/room_sketch.py`), the
Dramaturge pass, the direction follow-up that judges its suggestions when
the story nears them, the bible fold. At rest it costs nothing (v2 § 10).

WHAT IT IS. A tool-using loop over the authoring facade
(`story/room_tools.py`): the model is handed the tool table and the
conversation, calls tools, and drafts, validates and publishes plot
packages (`story/plot_packages.py`). It is a coding agent over the world's
own readers and one write seam -- it judges whether a thing is natural,
plots how it lands so it reads as something that happened in the world,
and critiques rather than implements. It reads OBJECTIVE truth (it is an
author, v2 § 2.1) and addresses no mind: nothing it says reaches a
character except by what a published package places in the world, which a
mind meets by seeing, hearing or being told (B1's author-layer invariant,
kept whole here because the Planner has no other write path).

THE GRANT IS STATE. What the player allows in words, the Planner writes as
a typed mandate (`story/mandates.py`); a package it authored publishes only
under standing mandates that cover it, and it cites the mandate when it
declines. A story starts with none (the zero-harm floor): the Planner asks.

THE DELIBERATION (v2 § 6; plan § 5 Phase C). The Dramaturge
(`agents/dramaturge.py`) proposes direction as typed proposals
(`story/room_proposals.py`); the Planner JUDGES each for naturalness --
would this read as something that happened in this world -- and answers
with geography, identity, causal history and cost. It refuses with the
contradiction named, sends back for revision, or accepts and implements
through a package in the same reply. Bounded in rounds; a disagreement
that outlives them is returned to the player, never forced. It runs when
the story nears a suggestion, or once the suggestion has waited its bound,
and at once for one the player asked for (`run_direction_follow_up`).

TWO REGIMES, AND SPEND IS THE STOP (owner, 2026-09-03: "the bounds may
potentially be too strict"). The step and call counts below are SAFETY
ceilings an order of magnitude above the work. What actually stops a reply
is the wall clock of its regime and the SPEND the player granted
(`mandates.spend_limits`: calls per reply, calls per story hour): an
interactive reply has a long wall and rewrites the status row every step so
the panel shows progress; a background task (a fill, a Dramaturge pass) has
no wall at all, only a per-pass one, after which it RESUMES in the next
pass under the same mandate until spend stops it. The Planner cites the
limit when spend stops it.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time

from core.db import data_version
from core.logging_utils import logger
from story.room_calls import room_max_tokens

#: The model role (`providers.ROLES`). ONE role for the Planner and its
#: Charter Planner delegation: the delegation is a scoped call of the same
#: author, and a second settings row would be a choice that rarely differs.
PLANNER_ROLE = "story_planner"
#: The actor name a package records when the Planner drafts it
#: (`plot_packages.AGENT_AUTHORS`).
PLANNER_ACTOR = "story_planner"

#: SAFETY CEILINGS, not budgets. Steps (model calls) per reply and tool
#: calls per step and per reply, an order of magnitude above what a reply
#: needs (measured 2026-09-03: five to nine steps, eleven to nineteen calls
#: to plan a tenement). The real stop is spend (`mandates.spend_limits`) and
#: the regime's wall clock.
PLANNER_STEPS_PER_REPLY = 40
PLANNER_TOOL_CALLS_PER_STEP = 8
PLANNER_TOOL_CALLS_PER_REPLY = 200
#: THE TWO REGIMES. An interactive reply -- the player is waiting in the
#: panel -- gets this long, with the status row rewritten every step so the
#: wait is visible. A background task gets this long PER PASS and resumes.
REPLY_WALL_SECONDS = 600.0
TASK_PASS_SECONDS = 600.0
#: The old name, kept for readers: the interactive wall.
PLANNER_WALL_SECONDS = REPLY_WALL_SECONDS
#: Passes one background task may take before it is left for the next job
#: -- a safety ceiling under the spend that really bounds it.
TASK_PASSES_CAP = 12
#: THE OPENING REGIME (`docs/design/DESIGN_OPENING_PLAN.md`): one pass,
#: bounded, before the first turn row exists. Owner ruling 2026-09-16: a
#: hard budget with a silent fallback -- a plan that does not land in time
#: costs nothing but the plan, and the opening runs as it did.
#:
#: RAISED from 10 steps / 150s on the first three live openings, because the
#: budget was cutting the plan off one call from the end. Chat 127 spent 17
#: calls over the full 10 steps, drafted all four operations (`plan_rooms`,
#: `director_note` and a `place_at_opening` per present body), validated
#: clean, wrote the status line "the opening package is drafted and ready;
#: validation is the last check before it lands" -- and stopped on `steps`
#: without ever calling `publish_package`. Nothing landed, from a package
#: that was finished. The shape of the work is read, open, draft once per
#: operation, validate, publish, and one operation per draft call is what
#: the model actually does, so the floor is the number of operations plus
#: four and the ceiling wants room above it.
OPENING_STEPS = 24
OPENING_WALL_SECONDS = 360.0
#: THE PRELUDE AND THE GROUND (`docs/design/DESIGN_ROOM_PRELUDE.md`), the
#: two passes that run BEFORE the opening plan and, unlike it, before there
#: is a story at all.
#:
#: The prelude is one short exchange: the Room reads the passage and the
#: cast and asks the player what they want from this story. It is a
#: QUESTION, not a plan -- nothing is drafted, nothing is published, no
#: mandate is minted -- so its budget is the smallest of the three. Six
#: steps is read-once, ask-once with room for a second read.
PRELUDE_STEPS = 6
PRELUDE_WALL_SECONDS = 120.0
#: THE LOCATION PASS (`story/location_design.py`): the Room designs the
#: inhabited place itself -- map, institutions, posts, upkeeps, economies, a
#: naming law and a look law -- in place of the single `utility` JSON call
#: that used to be asked for all of it at once. The budget is the largest of
#: the four launch regimes because the work is: reading the lore, laying out
#: a map a handful of rooms at a time, one institution per call, and a
#: review after each. A one-shot had one attempt and no way to be told it
#: was wrong; this has as many as the budget buys, and every one of them is
#: cheaper than the blob it replaces.
LOCATION_STEPS = 40
LOCATION_WALL_SECONDS = 900.0
#: How much of the selected lore rides in the task. The Room can read more
#: with `search_lore`/`read_lore`/`scan_lore` -- which is the point -- so
#: this is a starting slice, not the budget for what it may know.
LOCATION_LORE_CHARS = 24_000
#: Output budget per model call -- the FALLBACK, when the host's own ceiling
#: cannot be read. `story.room_calls.room_max_tokens()` is what callers
#: use, and it asks the host for its whole ceiling.
#:
#: Raised to 20k on the owner's ruling (2026-09-04): every response cap the
#: room owns is the same number, so a step that needs room has it and no
#: single call is the one that truncates. Measured on GLM 5.2 (chat 111,
#: 2026-09-03): one step drafting a whole package ran past 4000 tokens and
#: its truncated JSON parsed as nothing -- which is what a cap costs when it
#: binds, and why the loop reports a cut-off rather than reading it as "done"
#: (CUT_OFF_NOTE).
PLANNER_MAX_TOKENS = 40_000
#: Conversation lines the Planner is shown, newest last -- the WINDOW. A
#: line older than the window stays shown until the bible has folded it
#: (`story/room_bible.py`), up to the hard cap.
PLANNER_HISTORY_MESSAGES = 30
PLANNER_HISTORY_HARD_CAP = 60
#: LIMITS THE OWNER SHOULD KNOW ABOUT (2026-09-04). The conversation key's
#: ceiling in characters, beside the line window: past it the OLDEST lines
#: fall off whole, never cut. Measured on chat 114 with an empty transcript,
#: the thread was 22.2k of a 28.9k first-step payload and 20.2k of that was
#: the Planner's own prior replies, shown whole on every step of every
#: reply. The bible is the memory that folds them (`story/room_bible.py`),
#: so an older room line rides as its first sentence plus a `folded_chars`
#: count; the player's lines and the newest line in each of the room's
#: voices stay whole (a follow-up question needs its referent).
PLANNER_HISTORY_CHARS = 12_000
#: A folded line's head: its first sentence, held to this many characters
#: so a sentence-less paragraph is a head and not the paragraph.
PLANNER_FOLDED_LINE_CHARS = 240
#: The reply stored in the thread. Raised with the response cap on 2026-09-04:
#: a 20k-token budget the reply was then cut to 2,400 characters is a cap that
#: hides its own effect, which is the class this codebase keeps finding. Held
#: to the thread's own room-reply ceiling so neither is the silent one.
PLANNER_REPLY_CHARS = 80_000
#: Tool results shown back to the model. Past it, the largest result the
#: model has ALREADY READ is cut to `PLANNER_TRIM_HEAD_CHARS` of head plus a
#: `trimmed` count, then the newest step's largest, and only when every
#: result is a head are whole entries evicted, oldest first. Measured on
#: chat 114 (2026-09-04): a 13k `inspect_rooms` echo at step 4 evicted seven
#: smaller results at step 5 -- the packages and plans the Planner had just
#: read -- under the old rule of whole entries newest-first.
PLANNER_TRANSCRIPT_CHARS = 24_000
PLANNER_TRIM_HEAD_CHARS = 1_500
#: A read tool result's RECEIPT: what was called and the shape of what came
#: back. The tools are pure reads of a database that is still there, so a
#: result the Room has already acted on is re-fetchable and does not need to
#: ride as a truncated copy of itself -- which is what a 1,500-character head
#: of a JSON dump was. Small on purpose: a receipt is a note, not an answer.
PLANNER_RECEIPT_CHARS = 200
#: Charter Planner delegations per reply and their output budget.
CHARTER_PLANNER_CALLS_PER_REPLY = 1
CHARTER_PLANNER_MAX_TOKENS = 40_000
#: The pseudo-tool the model names to delegate; not in the facade table.
CHARTER_PLANNER_TOOL = "charter_planner"
#: Open needs one pass of a fill job hands the Planner; each pass reads the
#: open needs afresh (`run_fill`).
FILL_NEEDS_PER_JOB = 3
#: The job keys (`core/jobs.py`), deduped per chat.
FILL_JOB_KEY = "story_planner_fill"
DRAMATURGE_JOB_KEY = "dramaturge_pass"
#: THE LAZY DIRECTION FOLLOW-UP (owner, 2026-10-08: "save heavy plans for
#: when the actors near them"): the job that asks whether a beat brought the
#: story to a pending suggestion and deliberates the ones that are due
#: (`run_direction_follow_up`). Every deliberation runs here, one at a time.
DIRECTION_JOB_KEY = "direction_follow_up"
#: The Room's jobs that read a beat, for the restore that may discard it
#: (`persist/checkpoints.restore_checkpoint`, `core.jobs.cancel_from`).
ROOM_JOB_KEYS = (DRAMATURGE_JOB_KEY, FILL_JOB_KEY, DIRECTION_JOB_KEY)
#: The yes-share at which the decision model's "does this passage bring the
#: story to what the suggestion is about?" (`jev_questions.direction_neared`)
#: makes the suggestion due its deliberation. The engine's other yes/no
#: floors are the same half (`director_prose.PRESSURE_ENDED_FLOOR`).
DIRECTION_NEAR_FLOOR = 0.5
#: Questions the status row keeps.
STATUS_QUESTIONS_CAP = 6
#: At most this many of them are the ENGINE's own asks (review E,
#: 2026-10-08), so the other half is always the Planner's: the row's cap
#: used to sort engine asks first and cut after them, so six returned
#: deliberations left no room for any question the player had been asked in
#: conversation, and a grant scoped to one lapsed with it. Each engine ask is
#: one row per kind -- the fill waiting on a grant (`WAITING_LINE` while a
#: need is open, `WAITING_TO_PLANT_LINE` while only the frontier is short,
#: never both: `_say_what_waits_on_a_grant`) and the one standing
#: returned-proposal ask (`ask_returned`) -- so this does not bind today; it
#: keeps the half however many kinds the engine grows.
ENGINE_QUESTIONS_CAP = 3
#: One question's text on the row (`room_conversation.status` reads it at
#: the same length). The returned-proposal ask keeps whole titles within it,
#: the newest kept.
QUESTION_CHARS = 600
#: Deliberation rounds between the Planner and the Dramaturge before a
#: disagreement is returned to the player (v2 § 6.3).
DELIBERATION_ROUNDS = 2

#: The keys an answer may carry. An output carrying none of them is not an
#: answer -- almost always one cut off at the token ceiling -- and is told so.
ANSWER_KEYS = ("calls", "reply", "grants", "questions", "status_line",
               "verdicts", "to_dramaturge", "claims")
CUT_OFF_NOTE = ("your last output was not one JSON object with the known keys "
                "-- most likely cut off at the token ceiling; nothing in it "
                "ran. Take smaller steps: one operation per call, a few calls "
                "per step.")

#: Fixed lines. English is the message id: the panel renders through the
#: UI catalog, so each is in both `ui.json` packs and in
#: `static/js/writers_room.js` for the harvester.
BOUNDED_LINE = ("The room stopped at its budget for this reply; what it "
                "settled stands, and it can go on when asked.")
SPENT_LINE = ("The room reached the spend you allowed for this reply; what it "
              "settled stands, and it goes on under your next word.")
HOUR_SPENT_LINE = ("The room has spent this story hour's allowance; its "
                   "background work resumes with the next hour.")
DISAGREEMENT_LINE = ("The room could not agree on a direction; the proposal "
                     "and the objection are yours to settle.")
NO_STATUS_LINE = "The room has nothing in motion."
#: The row's line while something is in motion and nothing has said what
#: (review R3-8, 2026-10-08): a pacing pass files a suggestion and writes no
#: line, and judging is lazy now, so "nothing in motion" stood beside a
#: pending suggestion for up to two pacing intervals.
IN_MOTION_LINE = "The room has something in motion."
SILENT_LINE = ("The room finished without a word; what it settled stands, and "
               "its status line says what is in motion.")
WAITING_LINE = ("The room has open planning needs and no grant to answer "
                "them. Tell the Story Planner what it may prepare.")
#: The same ask when no need is open and what waits on the grant is the
#: frontier the room would plant ahead (`_say_what_waits_on_a_grant`).
WAITING_TO_PLANT_LINE = ("The room would plan what lies ahead of the story "
                         "and has no grant to. Tell the Story Planner it may "
                         "prepare ahead between beats.")
REWOUND_LINE = "The story rewound under the room's work; nothing landed."
#: The question the engine asks when a deliberation could not settle a
#: proposal (v2 § 6.3): the proposal and the objection are the player's.
#: ONE standing ask lists every returned proposal the player has not
#: answered, each once (`ask_returned`, review E 2026-10-08): a new text per
#: deliberation piled up past the row's cap.
RETURNED_QUESTION = "Settle the returned proposal: %s"
#: The `asker` that marks that one ask on the row.
RETURNED_ASKER = "returned"
LOST_ANSWER_LINE = ("The room lost its last answer to the model; what it had "
                    "already settled stands, and its notes say what that was.")
#: What the reply says when a stop is a spend stop, keyed by stop reason.
STOP_LINES = {"steps": BOUNDED_LINE, "calls": BOUNDED_LINE, "wall": BOUNDED_LINE,
              "spend_reply": SPENT_LINE, "spend_hour": HOUR_SPENT_LINE,
              "rewound": REWOUND_LINE, "model": LOST_ANSWER_LINE}
#: Stops after which a background task resumes in its next pass.
RESUMABLE_STOPS = ("steps", "calls", "wall")


# ---------------------------------------------------------------------------
# The model call
# ---------------------------------------------------------------------------

def _call(system, payload, *, max_tokens):
    """One JSON-shaped call on the Planner's role.

    Through `story.room_calls.room_call` rather than `chat_complete`
    directly: same provider, same arguments, same return, same exceptions,
    and the exchange is recorded when the host has capture on. Every
    pipeline stage and every Director specialist was already readable that
    way; the Planner was the one agent in the engine whose payload was not,
    which all five play runs of 2026-09-05 named as the thing they most
    wanted and could not have. `room_call` reads the provider module at
    call time too, so a test still seals or stubs one name."""
    from agents.common import jparse
    from story.room_calls import room_call
    raw = room_call(PLANNER_ROLE, system, payload,
                    max_tokens=max_tokens, phase="planner")
    out = jparse(raw)
    return out if isinstance(out, dict) else {}


# ---------------------------------------------------------------------------
# What the Planner is shown
# ---------------------------------------------------------------------------

def _story(cid):
    from core.db import q
    row = q("SELECT name, scenario FROM chats WHERE id=?", (cid,), one=True)
    return {"name": row["name"], "scenario": row["scenario"]} if row else {}


_SENTENCE_END = re.compile(r"[.!?](?=[\"'”’)]*(?:\s|$))")


def _first_sentence(text, limit=PLANNER_FOLDED_LINE_CHARS):
    """The head of a line: through its first sentence end, within `limit`."""
    text = str(text or "").strip()
    match = _SENTENCE_END.search(text)
    head = text[:match.end()] if match else text
    return head if len(head) <= limit else head[:limit - 1] + "…"


def _conversation(cid, frame_id):
    """The window, plus every older line the bible has not folded yet, up
    to the hard cap: a line leaves the Planner's context only after the
    fold has read it. The PLAYER's lines ride whole -- they are the brief.
    The room's own prior lines ride as their first sentence with the count
    of characters folded, because the bible is the memory designated to
    hold what they settled; the newest line in each of the room's voices
    stays whole so a follow-up has its referent. Past
    `PLANNER_HISTORY_CHARS` the oldest lines fall off whole."""
    from story import room_conversation as room
    from story.room_bible import bible
    folded_through = bible(cid, frame_id)["folded_through"]
    rows = room.messages(cid, frame_id, limit=PLANNER_HISTORY_HARD_CAP)
    window = rows[-PLANNER_HISTORY_MESSAGES:]
    older = [m for m in rows[:-PLANNER_HISTORY_MESSAGES] if m["id"] > folded_through]
    lines = older + window
    newest_in_voice = {m["role"]: m["id"] for m in lines if m["role"] != "player"}
    out = []
    for m in lines:
        text = str(m["text"] or "").strip()
        entry = {"id": m["id"], "role": m["role"], "text": text}
        if m["role"] != "player" and newest_in_voice.get(m["role"]) != m["id"]:
            head = _first_sentence(text)
            if len(head) < len(text):
                entry["text"] = head
                entry["folded_chars"] = len(text) - len(head)
        out.append(entry)
    size = len(json.dumps(out, ensure_ascii=False))
    while len(out) > 1 and size > PLANNER_HISTORY_CHARS:
        size -= len(json.dumps(out.pop(0), ensure_ascii=False)) + 2
    return out


def _manifest():
    from story.room_tools import tool_manifest
    tools = tool_manifest()
    tools.append({
        "name": CHARTER_PLANNER_TOOL,
        "description": (
            "Delegate one populated-location brief to the Charter Planner: "
            "purpose, required connections, required institutions and "
            "figures, population and simulation budget, historical horizon, "
            "constraints. Returns a generation request to draft as a "
            "request_location operation, or the conflicts that make the brief "
            "impossible. Once per reply."),
        "args": {"type": "object", "properties": {"brief": {"type": "object"}},
                 "required": ["brief"], "additionalProperties": False},
        "long": True,
    })
    return tools


def _tools_block():
    """The tool table as a system-block suffix. It is the largest and the
    most stable thing the Planner reads (measured 2026-09-04 on chat 114:
    15.6k characters, beside an 8.6k prompt and a bible of at most
    `BIBLE_CHARS_SHOWN` = 6k, identical on every step -- it was 10.3k of a
    13k per-step payload on the first live run, before the research tools
    and the operation shapes joined the table), so it rides the system
    block, which `providers.chat_complete` marks cacheable, and not the
    per-step user message."""
    return ("\n\nTOOLS. The room's table; the player never hears these "
            "names:\n" + json.dumps(_manifest(), ensure_ascii=False))


def _bible_block(cid, frame_id):
    """The story bible rides the system block too: stable within a reply,
    beside the tool table (plan § 6 item 7)."""
    from story.room_bible import render_block
    try:
        return render_block(cid, frame_id)
    except Exception as exc:
        logger.info("story bible unavailable: %s", exc)
        return ""


def _contract_block():
    """The citation contract, in the words the check holds the room to.

    It rides here rather than in the prompt card DELIBERATELY: the sentence
    the room is given and the test that enforces it are one string
    (`story.room_citations.CONTRACT_TEXT`), so neither can be edited into
    disagreement with the other. Static, so it stays inside the cacheable
    prefix beside the tool table.
    """
    from story.room_citations import CONTRACT_TEXT
    return "\n\nWHAT YOU STATE AS FACT.\n" + CONTRACT_TEXT


def system_block(cid, frame_id):
    from llm.prompts import get_prompt
    return (get_prompt("story_planner") + _tools_block() + _contract_block()
            + _bible_block(cid, frame_id))


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def _receipt(entry):
    """What a tool call did, small enough to carry and enough to act on.

    A RESULT THE ROOM HAS READ IS RE-FETCHABLE. The tools are pure reads of
    a database that is still there, so the honest compaction is not a
    truncated copy of the answer but a record that the question was asked
    and can be asked again. This is the lineage the Room is built from --
    an agent reads a thing, acts, and does not carry the thing.

    The shape is what a reader can act on: a count for a list, the keys for
    an object, the value itself when it is already short enough to be its
    own summary."""
    result = entry.get("result")
    if isinstance(result, dict):
        if len(result) == 1 and "error" in result:
            return result
        shape = ", ".join(
            "%s: %d" % (k, len(v)) if isinstance(v, (list, dict, str))
            else str(k)
            for k, v in list(result.items())[:6])
    elif isinstance(result, list):
        shape = "%d entries" % len(result)
    else:
        shape = str(result)[:120]
    encoded = _encoded(result)
    if len(encoded) <= PLANNER_RECEIPT_CHARS:
        return result
    return {"read": shape[:PLANNER_RECEIPT_CHARS],
            "recall": "call %s again for the detail"
                      % (entry.get("tool") or "the tool")}


def _shown_transcript(transcript, cap=None):
    """What the model is shown of its own tool results, within ``cap``
    characters. Returns ``(shown, whole)``: the entries in order, and the
    set of indices INTO ``shown`` whose result is untrimmed.

    THE ORDER OF SACRIFICE. A result the model has already read is worth
    less than one it has not, and a RECEIPT is worth more than an absence,
    so: (1) the largest result from a step the model has read becomes a
    receipt -- what it called, and the shape of what came back; (2) then the
    receipts it has already read go, oldest first (measured on chat 114
    after the first cut: seven read heads still crowded out the dump the
    model had just asked for); (3) then the largest of the newest step,
    which the model has not read yet -- only when that step alone outgrows
    the cap; (4) only then are whole entries evicted, oldest first. Under
    the old rule (whole entries, newest first) one dump evicted every
    neighbour it had just read (chat 114 step 5, 2026-09-04).

    A TOOL RESULT IS SCRATCH, NOT MEMORY, and this used to keep it as
    memory: an already-read result was cut to the first 1,500 characters of
    its own JSON, which is not what the result SAID -- it is a dump stopped
    mid-object, and it rides for the rest of the reply.

    What the Room needs to keep is what the story is and what it has set in
    motion, and neither of those is here: `story`, `packages`, `status`,
    `mandates` and `frontier` are their own payload keys, re-derived from
    the database on every step, so they are always current and they do not
    grow with the number of tools a reply happens to use. Measured on the
    descent run's first step, those cost 8,245 characters TOTAL. The
    transcript is a different thing -- the echo of tool results inside ONE
    reply -- and a tool the Room has already acted on can simply be CALLED
    AGAIN, which is what the receipt says.

    Measured, the failing step of that reply: transcript 23,567 characters
    against a 24,000 cap, 68% of the whole payload and more than every other
    key combined; the request reached ~69k characters with the system sheet,
    and the model spent 71 seconds and answered nothing where the five
    smaller steps of the same reply each took under 7."""
    cap = PLANNER_TRANSCRIPT_CHARS if cap is None else cap
    entries = [dict(e) for e in transcript]
    sizes = [len(_encoded(e)) for e in entries]
    kept = list(range(len(entries)))
    trimmed = set()
    latest = max((int(e.get("step") or 0) for e in entries), default=0)

    def _read(i):
        return int(entries[i].get("step") or 0) < latest

    def _trim(i):
        entries[i]["result"] = _receipt(entries[i])
        sizes[i] = len(_encoded(entries[i]))
        trimmed.add(i)

    while kept and sum(sizes[i] for i in kept) > cap:
        # A result is a trim candidate while a head would actually be smaller.
        candidates = [i for i in kept if i not in trimmed
                      and len(_encoded(entries[i].get("result"))) > PLANNER_TRIM_HEAD_CHARS]
        read = [i for i in candidates if _read(i)]
        read_heads = [i for i in kept if i in trimmed and _read(i)]
        if read:
            _trim(max(read, key=lambda k: sizes[k]))
        elif read_heads:
            kept.remove(read_heads[0])
        elif candidates:
            _trim(max(candidates, key=lambda k: sizes[k]))
        else:
            kept.pop(0)
    shown = [entries[i] for i in kept]
    whole = {n for n, i in enumerate(kept) if i not in trimmed}
    return shown, whole


def _payload(cid, frame_id, *, text, task, transcript, step, calls_left,
             seconds_left, turn_idx, spend=None, regime="reply", memo=None,
             shown=None, steps_cap=None):
    """The step's payload. Everything but the transcript and the budget is
    DERIVED FROM THE DATABASE, and nothing derived can move while the reply
    is only reading, so ``memo`` (`room_calls.ReplyMemo`) holds that half
    for the reply and `run_planner` drops it whenever the reply writes.
    Without a memo every part is re-derived, exactly as before.

    ``shown`` is the trimmed transcript when the caller has already made it
    -- `run_planner` needs the same cut for its echo policy, and made it
    twice per step (C21)."""
    from story import room_conversation as room
    from story.mandates import (MANDATE_CAPABILITIES, MANDATE_LIMITS,
                                active_mandates, revoked_since)
    from story.plot_packages import list_packages
    from story.room_calls import memo_part
    from story.room_frontier import frontier_report
    from story.room_proposals import pending_proposals
    from story.room_tools import cast_minds_summary, run_tool
    if shown is None:
        shown, _whole = _shown_transcript(transcript)

    def _clock():
        try:
            return run_tool(cid, "inspect_clock", frame_id=frame_id)
        except Exception:
            return {}

    def _frontier():
        try:
            report = frontier_report(cid, frame_id)
        except Exception as exc:
            return {"error": str(exc)[:200]}
        # THE PLACES WANTING A FAR LOOK, as the fill's task names them -- the
        # nearest few, ids and ground -- and only under the grant that lets
        # the room write one: the whole list rode every step of every reply.
        if report.get("looks_wanted"):
            listed = (_looks_listed(report)
                      if _looks_asked(cid, frame_id, report, turn_idx) else None)
            if listed:
                report["looks_wanted"] = listed
            else:
                report.pop("looks_wanted")
        return report

    # One line per cast member -- the drive's essence and each held project's
    # aim -- so the Planner knows what `inspect_minds` would answer before it
    # reaches (measured 2026-09-04 on chat 114: 136 characters for the one
    # cast member). Author knowledge; the seam that reads it is this loop
    # and nothing a mind is shown (`tests/test_room_minds.py`).
    def _minds():
        try:
            return cast_minds_summary(cid, frame_id)
        except Exception as exc:
            return [{"error": str(exc)[:200]}]

    payload = {
        "story": memo_part(memo, "story", lambda: _story(cid)),
        "clock": memo_part(memo, "clock", _clock),
        "minds": memo_part(memo, "minds", _minds),
        "conversation": memo_part(memo, "conversation",
                                  lambda: _conversation(cid, frame_id)),
        "mandates": memo_part(memo, "mandates",
                              lambda: active_mandates(cid, frame_id, turn_idx)),
        "withdrawn": memo_part(memo, "withdrawn", lambda: [
            {"uid": m["uid"], "text": m["text"], "status": m["status"]}
            for m in revoked_since(cid, frame_id, max(0, turn_idx - 1))]),
        "capabilities": list(MANDATE_CAPABILITIES),
        "limits": list(MANDATE_LIMITS),
        "status": memo_part(memo, "status", lambda: room.status(cid, frame_id)),
        "frontier": memo_part(memo, "frontier", _frontier),
        "packages": memo_part(memo, "packages",
                              lambda: list_packages(cid, frame_id=frame_id)),
        "pending_proposals": memo_part(memo, "pending_proposals", lambda: [
            {"uid": p["uid"], "kind": p["kind"], "title": p["title"],
             "status": p["status"]} for p in pending_proposals(cid, frame_id)]),
        "transcript": shown,
        "budget": {"regime": regime, "step": step,
                   "steps": int(steps_cap or PLANNER_STEPS_PER_REPLY),
                   "calls_left": calls_left,
                   "seconds_left": round(max(0.0, seconds_left), 1),
                   **({"spend": spend} if spend else {})},
    }
    # WORDS SAID ALOUD NEAR THE STORY WITH NO REPORT BEHIND THEM (the
    # owner's ruling on D6, 2026-10-09): a person a character invents stays
    # that character's claim, and the Room MAY make them real when it plans.
    # The Room is shown the claims -- the invented person's first
    # (`carriers.unbacked_claims`), and the player's own only where their
    # authority grants them the world; deciding is its own (the card's WHAT
    # PEOPLE CLAIM), and nothing in code plants anybody from one. Absent when
    # there is none, so an ordinary payload is unchanged.
    claims = memo_part(memo, "unbacked_claims",
                       lambda: _claims_near(cid, frame_id, payload["frontier"]))
    if claims.get("rows"):
        payload["unbacked_claims"] = claims["rows"]
        if claims.get("more"):
            payload["unbacked_claims_more"] = claims["more"]
    if text is not None:
        payload["player_says"] = text
    if task is not None:
        payload["task"] = task
    return payload


def _claims_near(cid, frame_id, frontier):
    """``{"rows", "more"}``: the unbacked claims somebody within the
    frontier's reach holds (`story.carriers.unbacked_claims`), the player's
    wherever they stand. A frontier that could not be measured still carries
    the player's own."""
    from story.carriers import unbacked_claims
    frontier = frontier if isinstance(frontier, dict) else {}
    rooms = [r for r in [frontier.get("player_room"),
                         *(frontier.get("reachable") or ())] if r]
    try:
        rows, total = unbacked_claims(cid, frame_id, rooms)
    except Exception as exc:
        logger.info("planner: the claims near the story are unavailable: %s",
                    exc)
        return {"rows": [], "more": 0}
    return {"rows": rows, "more": max(0, total - len(rows))}


# ---------------------------------------------------------------------------
# Grants, questions, status
# ---------------------------------------------------------------------------

def _apply_grants(cid, frame_id, grants, turn_idx):
    """The player's words became rows. Returns (rows, notes)."""
    from story.mandates import grant_mandate
    rows, notes = [], []
    for raw in grants if isinstance(grants, list) else []:
        if not isinstance(raw, dict):
            continue
        try:
            rows.append(grant_mandate(
                cid, frame_id, text=raw.get("text"),
                scope=raw.get("scope") or "this story",
                capabilities=raw.get("capabilities") or (),
                limits=raw.get("limits"),
                # THE ASK THE GRANT ANSWERS. `mandates` has stated since
                # 2026-09-04 that a grant may name the request it was earned
                # by and lapse with it -- and nothing passed one, so every
                # grant the room ever minted was standing. Asked to build two
                # rooms and a person, the room minted five capabilities with
                # `limits: {}` and `expires_turn: null`: the player granted,
                # without knowing it, the right to file lore and close needs
                # forever (PX24, masque run, 2026-09-05).
                request=raw.get("request"),
                expires_turn=raw.get("expires_turn"), turn_idx=turn_idx))
        except (ValueError, TypeError) as exc:
            notes.append("grant not recorded: %s" % str(exc)[:200])
    return rows, notes


def _question_text(text):
    return " ".join(str(text or "").split())[:QUESTION_CHARS]


def _asker_fields(entry):
    """A question's `asker` and `proposals` -- which task or engine ask it
    is, and what it was about -- when it carries them."""
    out = {}
    if not isinstance(entry, dict):
        return out
    asker = " ".join(str(entry.get("asker") or "").split())[:60]
    if asker:
        out["asker"] = asker
    proposals = entry.get("proposals")
    if isinstance(proposals, (list, tuple)):
        uids = list(dict.fromkeys(str(u) for u in proposals if str(u or "").strip()))
        if uids:
            out["proposals"] = uids[:24]
    return out


def _question_rows(questions, source="reply"):
    """The status row's questions: a uid, the text and who asked it
    (`room_conversation.QUESTION_SOURCES`) -- a plain string is asked by
    ``source`` -- with the task or engine ask it came from when it has one
    (`asker`, `proposals`); one row per text, the first statement of a text
    keeping its asker; the engine's own asks first, then the Planner's in
    replies, then the background tasks', at most `ENGINE_QUESTIONS_CAP` of
    the engine's and `STATUS_QUESTIONS_CAP` in all, so the cap cuts a
    task's question before anything the player was asked in conversation,
    and the engine's asks can never fill the row."""
    from story.room_conversation import QUESTION_SOURCES
    out, seen = [], set()
    for entry in questions if isinstance(questions, list) else []:
        asker, fields = source, _asker_fields(entry)
        if isinstance(entry, dict):
            asker = entry.get("source") or source
            entry = entry.get("text")
        text = _question_text(entry)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append({"uid": "q_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8],
                    "text": text,
                    "source": asker if asker in QUESTION_SOURCES else "reply",
                    **fields})
    out.sort(key=lambda row: QUESTION_SOURCES.index(row["source"]))
    engine = [row for row in out if row["source"] == "engine"]
    out = engine[:ENGINE_QUESTIONS_CAP] + [row for row in out
                                           if row["source"] != "engine"]
    return out[:STATUS_QUESTIONS_CAP]


def _unsettled(cid, frame_id, questions):
    """``questions`` less a deliberation's whose every proposal has settled
    (`room_proposals.SETTLED_STATUSES`): it was asked about those
    proposals, and nothing about them is left to answer -- the package
    landed, or it was refused, withdrawn or returned to the player. An
    `accepted` proposal is not settled: a grant asked for to carry it out
    stands until the player answers it (review D, 2026-10-08)."""
    from story.room_proposals import SETTLED_STATUSES, proposals
    rows = [q for q in questions if isinstance(q, dict) and q.get("source") == "task"
            and q.get("proposals")]
    if not rows:
        return questions
    status = {p["uid"]: p["status"] for p in proposals(cid, frame_id)}

    def settled(q):
        return all(status.get(uid, SETTLED_STATUSES[0]) in SETTLED_STATUSES
                   for uid in q["proposals"])
    return [q for q in questions
            if not (isinstance(q, dict) and q.get("source") == "task"
                    and q.get("proposals") and settled(q))]


def write_status(cid, frame_id, *, line=None, questions=None, turn_idx=None,
                 source="reply"):
    """The spoiler-safe projection the panel shows: what is in motion,
    never what it is. Built from package PROJECTIONS -- a title, a status --
    the pending proposals' kind and title, and the questions the room is
    asking. A sealed package's title is the Planner's to keep spoiler-safe;
    nothing else of it is read here.

    ``line`` None keeps the standing line while something is in motion and
    says nothing is when nothing is. The row never says "nothing in motion"
    beside something in motion, nor the reverse (`IN_MOTION_LINE`, review
    R3-8). ``questions`` None keeps the standing
    questions as they are; a list is the row's questions from now on, a
    plain string in it asked by ``source`` (`_question_rows`) -- a writer
    that answers only for its own uses `_restated` to build that list.
    Either way a deliberation's questions leave once every proposal they
    were about has settled (`_unsettled`). One transaction: a pass, a fill
    and a deliberation can all write the row at once."""
    from core.db import transaction, wset_for_frame
    from story import room_conversation as room
    from story.plot_packages import list_packages
    from story.room_proposals import pending_proposals, projection
    with transaction():
        in_motion = []
        for proj in list_packages(cid, frame_id=frame_id):
            if proj["status"] in ("draft", "validating", "published", "active"):
                in_motion.append({"uid": proj["uid"], "kind": "package",
                                  "label": proj["title"], "state": proj["status"]})
        for prop in pending_proposals(cid, frame_id):
            in_motion.append(projection(prop))
        current = room.status(cid, frame_id)
        line = " ".join(str(line or "").split())
        if not line:
            line = current.get("line") if in_motion else ""
        if in_motion and line in ("", NO_STATUS_LINE):
            line = IN_MOTION_LINE
        elif not in_motion and line in ("", IN_MOTION_LINE):
            line = NO_STATUS_LINE
        if questions is None:
            questions = current.get("questions") or []
        row = {"line": line[:400], "in_motion": in_motion,
               "questions": _question_rows(_unsettled(cid, frame_id, list(questions)),
                                           source),
               "updated_turn": int(turn_idx or room.current_turn_idx(cid))}
        wset_for_frame(cid, room.ROOM_STATUS_KEY, row, frame_id)
    return room.status(cid, frame_id)


def _task_identity(entry):
    """Which task a question, or an asker, is: its kind and the proposals
    it was about. Two runs of one fill are the same task; a deliberation is
    the proposals it was handed, whichever round asked."""
    entry = entry if isinstance(entry, dict) else {}
    return (str(entry.get("asker") or ""),
            tuple(sorted(str(u) for u in entry.get("proposals") or ())))


def _asker_for(task):
    """A background task's asker when its caller named none: the task's own
    kind, about no proposal, with nothing asked yet."""
    kind = str((task or {}).get("kind") or "task") if isinstance(task, dict) else "task"
    return {"asker": kind, "proposals": [], "asked": []}


def _with_earlier(earlier, stated):
    """What one task has asked across its rounds and passes: the earlier
    questions first, then any new one, each text once."""
    out, seen = [], set()
    for text in list(earlier or ()) + list(stated or ()):
        text = _question_text(text)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _restated(cid, frame_id, stated, source, *, engine=(), asker=None):
    """The status row's questions once ``source`` has stated its own list.

    WHO ASKED DECIDES WHO MAY TAKE IT OFF (review, 2026-10-08). A
    BACKGROUND TASK answers nobody: its list replaces only the questions
    THAT SAME TASK asked before (``asker``: a fill, or a deliberation of
    the same proposals) and keeps the rest -- what the Planner asked the
    player in a reply, the engine's own asks, and every other task's.
    Keyed by the last task alone, a deliberation's second round wiped the
    grant its first round asked for, and so did the next fill, and a grant
    the player had scoped to that question lapsed with it
    (`mandates.request_open`); before that every task replaced the whole
    row. Rounds and passes of one task add to its list (`_with_earlier`).
    A REPLY restates the row, as it always has: the player has just spoken
    and the Planner was shown every question standing, so one it does not
    restate was answered or dropped. An engine ask it restates stays the
    engine's -- ``engine`` names the ones that stood when the reply began --
    which is what lets the engine take it off again when its reason is gone
    (`withdraw_question`)."""
    from story import room_conversation as room
    standing = room.status(cid, frame_id).get("questions") or []
    stated = [t for t in (stated or ()) if _question_text(t)]
    if source == "reply":
        engine_rows = {q["text"]: q for q in standing if q["source"] == "engine"}
        asked = set(engine) | set(engine_rows)
        kept = [{**_asker_fields(engine_rows.get(_question_text(t))),
                 "text": _question_text(t), "source": "engine"}
                for t in stated if _question_text(t) in asked]
        return kept + [{"text": t, "source": source} for t in stated]
    identity = _task_identity(asker)
    kept = [q for q in standing
            if not (q["source"] == "task" and _task_identity(q) == identity)]
    fields = {"asker": identity[0], "proposals": list(identity[1])}
    return kept + [{"text": t, "source": "task", **fields} for t in stated]


def ask_question(cid, frame_id, text, *, turn_idx=None):
    """The engine asks the player something by its own reading of the story:
    on the status row ahead of every question a model asked, until the
    engine withdraws it or a reply restates the row without it. Idempotent:
    an ask already standing is not written again. Returns the status row, or
    None when nothing was written."""
    from core.db import transaction
    from story import room_conversation as room
    text = _question_text(text)
    with transaction():
        standing = room.status(cid, frame_id).get("questions") or []
        if not text or any(q["text"] == text and q["source"] == "engine"
                           for q in standing):
            return None
        questions = [q for q in standing if q["text"] != text]
        questions.append({"text": text, "source": "engine"})
        return write_status(cid, frame_id, questions=questions, turn_idx=turn_idx)


def withdraw_question(cid, frame_id, text, *, turn_idx=None):
    """The engine takes back an ask whose reason is gone. Only its own: the
    same words asked by the Planner are the Planner's to drop. Returns the
    status row, or None when nothing was written."""
    from core.db import transaction
    from story import room_conversation as room
    text = _question_text(text)
    with transaction():
        standing = room.status(cid, frame_id).get("questions") or []
        kept = [q for q in standing
                if not (q["text"] == text and q["source"] == "engine")]
        if len(kept) == len(standing):
            return None
        return write_status(cid, frame_id, questions=kept, turn_idx=turn_idx)


def ask_returned(cid, frame_id, uids, *, turn_idx=None):
    """The engine's ONE standing ask about the proposals the room could not
    settle (review E, 2026-10-08). Each deliberation that returned one asked
    a new question naming its titles, so the asks piled up past the row's
    cap and pushed out the questions the player had been asked in
    conversation. Now the ask names every returned proposal the player has
    not yet answered -- those the standing ask already named, then ``uids``
    -- each once, as one row, keeping whole titles within
    `QUESTION_CHARS`, the newest kept. A reply that does not restate it has
    answered it, and the next return starts a fresh list. Returns the status
    row, or None when there was nothing to ask."""
    from core.db import transaction
    from story import room_conversation as room
    from story.room_proposals import get_proposal
    with transaction():
        standing = room.status(cid, frame_id).get("questions") or []
        prior = [q for q in standing if q["source"] == "engine"
                 and q.get("asker") == RETURNED_ASKER]
        listed = list(dict.fromkeys(
            [u for q in prior for u in q.get("proposals") or ()]
            + [str(u) for u in uids or ()]))
        titled = [(u, (get_proposal(cid, frame_id, u) or {}).get("title"))
                  for u in listed]
        titled = [(u, t) for u, t in titled if t]
        while len(titled) > 1 and len(
                RETURNED_QUESTION % "; ".join(t for _u, t in titled)) > QUESTION_CHARS:
            titled.pop(0)
        if not titled:
            return None
        rest = [q for q in standing if q not in prior]
        return write_status(cid, frame_id, questions=rest + [{
            "text": RETURNED_QUESTION % "; ".join(t for _u, t in titled),
            "source": "engine", "asker": RETURNED_ASKER,
            "proposals": [u for u, _t in titled]}], turn_idx=turn_idx)


# ---------------------------------------------------------------------------
# The Charter Planner delegation
# ---------------------------------------------------------------------------

#: The request keys `charter_runtime.generate_lived_location` reads.
REQUEST_KEYS = ("name", "brief", "scale", "topology", "required_rooms",
                "featured_residents", "population", "horizon_hours")


def charter_planner(cid, frame_id, brief):
    """One scoped call: a bounded brief in, a generation request out. It
    never changes the plan, never negotiates, and returns a conflict rather
    than forcing an impossible requirement (v2 § 3.6). Its work lands only
    through `request_location` -> `generate_lived_location`."""
    from story.room_tools import run_tool
    brief = dict(brief) if isinstance(brief, dict) else {}
    purpose = " ".join(str(brief.get("purpose") or brief.get("name") or "").split())
    if not purpose:
        return {"error": "a charter brief names the location's purpose"}
    payload = {"brief": brief}
    for tool, args in (("search_lore", {"query": purpose[:200]}),
                       ("inspect_structures", {}),
                       ("inspect_reserved_identities", {}),
                       ("inspect_clock", {})):
        try:
            payload[tool] = run_tool(cid, tool, args, frame_id=frame_id)
        except Exception as exc:
            payload[tool] = {"error": str(exc)[:200]}
    from llm.prompts import get_prompt
    out = _call(get_prompt("charter_planner"), payload,
                max_tokens=room_max_tokens())
    request = out.get("request") if isinstance(out.get("request"), dict) else {}
    request = {k: request[k] for k in REQUEST_KEYS if request.get(k) not in (None, "", [])}
    if request and not request.get("name") and not request.get("brief"):
        request["brief"] = purpose
    conflicts = [str(c)[:400] for c in (out.get("conflicts") or [])
                 if str(c or "").strip()] if isinstance(out.get("conflicts"), list) else []
    return {"request": request, "conflicts": conflicts,
            "report": " ".join(str(out.get("report") or "").split())[:1200]}


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------

def _is_write(name):
    from story.room_tools import TOOL_INDEX
    tool = TOOL_INDEX.get(name)
    return bool(tool) and name in ("publish_package", "prepare_package")


def _note_bible(cid, frame_id, name, args, result, turn_idx):
    """Deterministic bible lines for a publish or a resolve, no call."""
    from story.room_bible import note_publish, note_resolve
    if not isinstance(result, dict):
        return
    uid = str(result.get("uid") or args.get("uid") or "")
    title = str(result.get("title") or "")
    if not title:
        try:
            from story.plot_packages import get_package
            pkg = get_package(cid, uid, frame_id=frame_id)
            title = str((pkg or {}).get("title") or uid)
        except Exception:
            title = uid
    try:
        if name == "publish_package" and result.get("published_turn") is not None:
            note_publish(cid, frame_id, package_uid=uid, title=title,
                         turn_idx=turn_idx)
        elif name == "resolve_package":
            note_resolve(cid, frame_id, package_uid=uid, title=title,
                         turn_idx=turn_idx)
    except Exception as exc:
        logger.info("bible note skipped: %s", exc)


def _session_account(transcript):
    """What a reply DID, as notes: the packages it touched and the tools it
    ran. Read off the transcript rather than tracked alongside it, so it
    cannot drift from what actually happened.

    This exists for the reply that ends without one -- see the model-failure
    branch in `run_planner`. A package the room drafted and validated is real
    the moment the tool returns; the only thing a lost answer costs is the
    sentence naming it, and this is that sentence.
    """
    uids, tools = [], []
    for entry in transcript or ():
        if not isinstance(entry, dict):
            continue
        args = entry.get("args")
        uid = str((args or {}).get("uid") or "") if isinstance(args, dict) else ""
        if uid and uid not in uids:
            uids.append(uid)
        name = str(entry.get("tool") or "")
        if name and name not in tools:
            tools.append(name)
    notes = []
    if uids:
        notes.append("packages this reply touched: " + ", ".join(uids[:8]))
    if tools:
        notes.append("tools this reply ran: " + ", ".join(tools[:16]))
    return notes


def run_planner(cid, frame_id, *, text=None, task=None, base_turn=None,
                regime=None, on_event=None, job=None, asker=None):
    """One bounded reply. ``text`` is the player's line (the interactive
    regime); ``task`` a brief from a job (the background regime; no grants
    are read from a task). Returns ``{"reply", "dramaturge": None,
    "mandates", "status", "published": [uids], "opened": [uids],
    "verdicts": [...], "ask_dramaturge": str|None, "calls": n, "steps": n,
    "notes": [...], "stopped": why|None, "regime"}`` -- ``opened`` being
    the packages THIS reply's own `new_package` calls opened.

    ``asker`` is which background task this is, for its questions
    (`_restated`): ``{"asker": kind, "proposals": [uids], "asked":
    [texts]}``, ``asked`` holding what the task's earlier rounds and passes
    asked and updated in place. None: the task's own kind, asked afresh.

    ``job`` is the out-of-band job a task runs in. Once it is cancelled
    (`core.jobs.cancel` -- a restore, above all) the loop runs no further
    step and no further tool, and writes nothing more: no status row, no
    spend, and an empty reply for its caller to post (stopped
    "cancelled").

    ``on_event`` is an optional callable taking one dict, for a caller
    watching the loop rather than waiting on it. It is told when a step
    begins and what each tool call was and returned, so a panel can show the
    room working instead of a spinner over a reply that takes half a minute.
    Advisory by construction: a raising or slow callback must not be able to
    change what the room does, so every call is swallowed, and a caller that
    passes nothing runs exactly the code that ran before this existed."""

    def _emit(event):
        if on_event is None:
            return
        try:
            on_event(event)
        except Exception:  # a watcher is never allowed to break the work
            pass
    from core.jobs import is_cancelled, story_rewound_past
    from story import room_conversation as room
    from story.mandates import expire_mandates, spend_citation, spend_limits
    from story.room_calls import ReplyMemo
    from story.room_citations import normalize_claim
    from story.room_frontier import record_spend, spend_this_hour
    from story.room_tools import (TOOL_INDEX, ToolError, run_tool,
                                  tool_only_reads)

    def _call_key(name, args):
        return name + "\x00" + json.dumps(args, sort_keys=True, ensure_ascii=False,
                                          default=str)

    regime = regime or ("task" if task is not None and text is None else "reply")
    wall = (REPLY_WALL_SECONDS if regime == "reply"
            else OPENING_WALL_SECONDS if regime == "opening"
            else PRELUDE_WALL_SECONDS if regime == "prelude"
            else LOCATION_WALL_SECONDS if regime == "location"
            else TASK_PASS_SECONDS)
    steps_cap = (OPENING_STEPS if regime == "opening"
                 else PRELUDE_STEPS if regime == "prelude"
                 else LOCATION_STEPS if regime == "location"
                 else PLANNER_STEPS_PER_REPLY)
    system = system_block(cid, frame_id)
    turn_idx = room.current_turn_idx(cid)
    expire_mandates(cid, frame_id, turn_idx)
    spend = spend_limits(cid, frame_id, turn_idx)
    # None: no per-reply allowance (`mandates.CALLS_PER_REPLY`); the loop's
    # own ceiling still bounds the reply.
    reply_cap = (PLANNER_TOOL_CALLS_PER_REPLY if spend["calls_per_reply"] is None
                 else min(PLANNER_TOOL_CALLS_PER_REPLY, int(spend["calls_per_reply"])))
    # None: no hourly allowance (`mandates.CALLS_PER_STORY_HOUR`).
    hour_left = (None if spend["calls_per_hour"] is None else
                 max(0, int(spend["calls_per_hour"]) - spend_this_hour(cid, frame_id, turn_idx)))
    started = time.time()
    transcript, notes, published, verdicts, claims = [], [], [], [], []
    # THE DRAFTS THIS REPLY OPENED, recorded where its own `new_package`
    # call returns them (review A, 2026-10-08): the only drafts a task's end
    # may retire (`_retire_stranded`).
    opened = []
    calls_made, delegations, steps = 0, 0, 0
    # `questions` stays None until the model states a list: saying nothing
    # about the questions standing is not an answer to them.
    reply, status_line, questions, ask_dramaturge = "", "", None, None
    # The engine's asks as the reply found them, so one the model restates
    # stays the engine's even after a progress write (`_restated`).
    engine_asks = {q["text"] for q in room.status(cid, frame_id).get("questions") or []
                   if q.get("source") == "engine"}
    stopped = None
    # THE ECHO POLICY. `answered` maps a call (tool + arguments) to the index
    # of the transcript entry that last showed its result in full; a repeat
    # whose answer is unchanged and still in the model's view is echoed as
    # the step to look at, never a second copy. `in_view` is what the model
    # saw whole in the payload it just read, plus what this step appended.
    answered, in_view = {}, set()
    # THE STATIC HALF OF THE PAYLOAD, ONCE PER WRITE (review 2026-09-07,
    # C21). Every step rebuilt the frontier, the cast's minds, the clock,
    # the packages, the mandates and the status row. Measured on the bench
    # copy of chat 114 (`tools/bench/room_payload.py`): 17.3 ms a step,
    # 0.69 s over a forty-step reply, against 0.02 s held. The memo is
    # dropped by what the reply WRITES -- a tool that is not a pure read, an
    # applied grant, a rewritten status row -- and by a BEAT LANDING UNDER
    # IT: this loop runs in `converse_stream`'s daemon thread against no
    # lock, which is why `story_rewound_past` is checked below, so each step
    # hands the memo the database's own `data_version` (0.013 ms median), the
    # counter that moves on ANOTHER connection's commit -- the turn index
    # moves when a beat starts, not when it commits (C21, second skeptic).
    memo = ReplyMemo()
    if hour_left is not None and hour_left <= 0:
        stopped = "spend_hour"
    for step in range(1, steps_cap + 1):
        if stopped:
            break
        if is_cancelled(job):
            stopped = "cancelled"
            break
        _emit({"type": "room_step", "step": step,
               "calls_made": calls_made, "seconds": round(time.time() - started, 1)})
        seconds_left = wall - (time.time() - started)
        if seconds_left <= 0:
            stopped = "wall"
            break
        steps = step
        memo.at_version(data_version())
        calls_left = max(0, (reply_cap - calls_made) if hour_left is None
                         else min(reply_cap - calls_made, hour_left - calls_made))
        # ONE CUT PER STEP. The trim the model is shown and the `in_view`
        # set the echo policy holds it to are the same cut of the same
        # unchanged transcript; it was made twice, once inside `_payload`
        # and once after the call (C21).
        shown, whole = _shown_transcript(transcript)
        first_shown = len(transcript) - len(shown)
        try:
            out = _call(system, _payload(
                cid, frame_id, text=text, task=task, transcript=transcript,
                step=step, calls_left=calls_left, seconds_left=seconds_left,
                turn_idx=turn_idx, regime=regime, memo=memo, shown=shown,
                steps_cap=steps_cap,
                spend={"calls_per_reply": reply_cap,
                       "calls_per_hour_left": hour_left}),
                max_tokens=room_max_tokens())
        except Exception as exc:
            # THE WORK IS NOT LOST, ONLY THE REPORT OF IT. A reply that has
            # already run tools has already changed the database -- a package
            # drafted, edited, validated -- and letting the exception out of
            # here threw away the account of what that was. Measured (masque,
            # 2026-09-05, PX22): 287 seconds, 14 model calls, 36 tool calls,
            # a package sitting at revision 7 with `validation: {ok: true}`
            # holding a `plan_rooms` and a `director_note`, and the caller was
            # handed `reply: None, published: None`. The host found it by
            # running `inspect_packages` by hand.
            #
            # A step-one failure with nothing done is a different event: there
            # is no account to give, and swallowing it would hide the outage
            # from a caller whose retry is the right answer. So the raise is
            # kept for exactly that case.
            if not calls_made and not transcript:
                raise
            logger.info("story planner call failed at step %s: %s", step, exc)
            notes.append("the model call failed at step %d (%s: %s); the "
                         "work before it stands"
                         % (step, type(exc).__name__, str(exc)[:200]))
            notes.extend(_session_account(transcript))
            stopped = "model"
            break
        if is_cancelled(job):
            # Cancelled while the model answered: nothing it said is acted
            # on -- it read a story the player may since have rerolled.
            stopped = "cancelled"
            break
        in_view = {first_shown + n for n in whole}
        if not any(k in out for k in ANSWER_KEYS):
            # A truncated or shapeless output is reported, not read as "done":
            # the loop used to fall through to BOUNDED_LINE, telling the
            # player the room had stopped at its budget when the model had
            # stopped mid-sentence.
            transcript.append({"tool": None, "args": None,
                               "result": {"error": CUT_OFF_NOTE}, "step": step})
            continue
        if text is not None and out.get("grants"):
            _rows, grant_notes = _apply_grants(cid, frame_id, out["grants"], turn_idx)
            notes.extend(grant_notes)
            memo.wrote()  # the mandates the next payload states
        if out.get("status_line"):
            status_line = str(out["status_line"])
        if isinstance(out.get("questions"), list):
            # THE OPENING CANNOT ASK (owner, 2026-09-16): nobody is there to
            # answer before the first beat, and chat 126's plan waited on
            # one question for the whole story. A question in that regime
            # is kept as a note, never written to the status row.
            # The GROUND pass is the same case: it runs inside a launch,
            # after the prelude has closed and while the player is watching
            # a progress line, so a question there is a stall too. The
            # PRELUDE is the regime that exists to ask one, and it asks it
            # in its reply.
            if regime in ("opening", "location"):
                for q_text in out["questions"]:
                    notes.append("question not asked before the story: %s"
                                 % str(q_text)[:200])
            else:
                questions = out["questions"]
        if out.get("reply"):
            reply = str(out["reply"])
        if isinstance(out.get("verdicts"), list):
            verdicts = [v for v in out["verdicts"] if isinstance(v, dict)]
        if isinstance(out.get("claims"), list):
            # The step that wrote the reply is the step that enumerates what
            # the reply states, so the last list wins, exactly as the reply
            # itself does. Nothing is checked here: `room_citations` holds
            # the claims to the rows `run_tool` recorded, and does it in the
            # context that owns the ledger.
            claims = [normalize_claim(c) for c in out["claims"]
                      if isinstance(c, (dict, str))]
        if text is not None and out.get("to_dramaturge"):
            ask_dramaturge = " ".join(str(out["to_dramaturge"]).split())[:1200]
        # PROGRESS IS VISIBLE: the status row is rewritten every step, so
        # the panel's one-second watch shows a long reply working.
        if regime == "reply" and status_line:
            from core.db import transaction
            with transaction():
                write_status(cid, frame_id, line=status_line,
                             questions=(None if questions is None else _restated(
                                 cid, frame_id, questions, "reply",
                                 engine=engine_asks)),
                             turn_idx=turn_idx)
            memo.wrote()  # the status row the next payload states
        calls = out.get("calls") if isinstance(out.get("calls"), list) else []
        if not calls:
            break
        for call in calls[:PLANNER_TOOL_CALLS_PER_STEP]:
            if is_cancelled(job):
                stopped = "cancelled"
                break
            if calls_made >= PLANNER_TOOL_CALLS_PER_REPLY:
                stopped = "calls"
                break
            if calls_made >= reply_cap:
                stopped = "spend_reply"
                break
            if hour_left is not None and calls_made >= hour_left:
                stopped = "spend_hour"
                break
            # A call the loop cannot run is REPORTED, never dropped: measured
            # live (chat 111, 2026-09-03), a model spelled the tool key
            # `name` for three steps running, each silently skipped, and
            # repeated itself into an empty transcript for 27 seconds.
            if not isinstance(call, dict):
                transcript.append({"tool": None, "args": call, "result": {
                    "error": "a call is an object with `tool` and `args`"},
                    "step": step})
                continue
            name = str(call.get("tool") or call.get("name") or "")
            if not name:
                transcript.append({"tool": None, "args": call, "result": {
                    "error": "a call names its tool under `tool`"}, "step": step})
                continue
            if isinstance(call.get("args"), dict):
                args = call["args"]
            else:
                # Arguments written beside the tool name instead of under
                # `args` (GLM 5.2, live) are the arguments.
                args = {k: v for k, v in call.items() if k not in ("tool", "name", "args")}
            calls_made += 1
            if base_turn is not None and _is_write(name) \
                    and story_rewound_past(base_turn, room.current_turn_idx(cid)):
                transcript.append({"tool": name, "args": args,
                                   "result": {"refused": REWOUND_LINE}, "step": step})
                stopped = "rewound"
                break
            if name == CHARTER_PLANNER_TOOL:
                if delegations >= CHARTER_PLANNER_CALLS_PER_REPLY:
                    result = {"refused": "the Charter Planner is delegated to "
                                         "once per reply"}
                else:
                    delegations += 1
                    try:
                        result = charter_planner(cid, frame_id, args.get("brief"))
                    except Exception as exc:
                        result = {"error": str(exc)[:400]}
            else:
                try:
                    result = run_tool(cid, name, args, frame_id=frame_id,
                                      actor=PLANNER_ACTOR)
                except ToolError as exc:
                    result = {"error": str(exc)[:400]}
                except Exception as exc:
                    logger.info("story planner tool %s failed: %s", name, exc)
                    result = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])}
                if name == "publish_package" and isinstance(result, dict) \
                        and result.get("published_turn") is not None:
                    published.append(str(result.get("uid") or args.get("uid") or ""))
                if name == "new_package" and isinstance(result, dict) \
                        and result.get("uid") and not (
                            "error" in result or "refused" in result):
                    opened.append(str(result["uid"]))
                if name in ("publish_package", "resolve_package"):
                    _note_bible(cid, frame_id, name, args, result, turn_idx)
            # A CALL THE TABLE DOES NOT MARK AS A PURE READ MAY HAVE MOVED
            # ANYTHING (`room_tools.tool_only_reads`), and so may the
            # Charter Planner's delegation, so the next step re-derives.
            if name == CHARTER_PLANNER_TOOL or not tool_only_reads(name):
                memo.wrote()
            echo = result
            answered_ok = isinstance(result, dict) and not (
                "error" in result or "refused" in result)
            payload_key = (TOOL_INDEX.get(name) or {}).get("payload_key")
            if payload_key and answered_ok:
                # The payload already carries this, rebuilt every step: the
                # echo is the key to read (chat 114 called `inspect_clock`
                # five times per reply, each a full copy).
                echo = {"in_payload": payload_key}
            elif answered_ok:
                key = _call_key(name, args)
                earlier = answered.get(key)
                if earlier is not None and earlier in in_view \
                        and transcript[earlier]["result"] == result:
                    echo = {"see_step": transcript[earlier]["step"]}
                else:
                    answered[key] = len(transcript)
                    in_view.add(len(transcript))
            transcript.append({"tool": name, "args": args, "result": echo, "step": step})
            # What the room DID, not what it meant to do: a refusal and an
            # error are the two the watcher most needs, and they are exactly
            # what a spinner hides (see REPORT WHAT LANDED on the card).
            _emit({"type": "room_tool", "step": step, "tool": name,
                   "refused": (result or {}).get("refused")
                   if isinstance(result, dict) else None,
                   "error": (result or {}).get("error")
                   if isinstance(result, dict) else None})
        if stopped:
            break
    else:
        stopped = "steps"
    if stopped == "cancelled":
        # A CANCELLED JOB WRITES NOTHING MORE -- not the status row, not the
        # spend, and no line for its caller to post. What its tools already
        # wrote before the cancel landed is what the restore that cancelled
        # it rolls back (`persist/checkpoints.restore_checkpoint`).
        return {"reply": "", "dramaturge": None,
                "mandates": room.mandates(cid, frame_id),
                "status": room.status(cid, frame_id),
                "published": published, "opened": opened, "verdicts": [],
                "claims": claims, "ask_dramaturge": None, "calls": calls_made,
                "steps": steps, "notes": notes, "stopped": stopped,
                "regime": regime}
    if stopped and not reply:
        reply = STOP_LINES.get(stopped, BOUNDED_LINE)
        if stopped in ("spend_reply", "spend_hour"):
            key = "calls_per_reply" if stopped == "spend_reply" else "calls_per_hour"
            cited = spend_citation(cid, frame_id, key, turn_idx)
            if cited:
                notes.append("spend stop under %s" % cited)
    if not reply and not stopped:
        # THE LINE SAYS WHAT HAPPENED. A model that judged or built and said
        # nothing did not stop at a budget (bench, chat 114: a deliberation
        # round with verdicts and no reply told the player the room had run
        # out). A task posts no line; a reply owes the player one.
        reply = "" if regime == "task" else SILENT_LINE
    reply = str(reply or "").strip()[:PLANNER_REPLY_CHARS]
    if calls_made:
        record_spend(cid, frame_id, turn_idx=turn_idx, calls=calls_made,
                     who="planner")
    from core.db import transaction
    with transaction():
        if regime == "task":
            # A BACKGROUND TASK ANSWERS NO QUESTION: what it has asked over
            # all its rounds and passes -- none stated adds none -- replaces
            # only what THIS task asked before, and what the player was asked
            # in a reply, the engine's own asks and every other task's stand
            # (`_restated`, review D 2026-10-08).
            asker = asker if asker is not None else _asker_for(task)
            asker["asked"] = _with_earlier(asker.get("asked"), questions or [])
            questions = _restated(cid, frame_id, asker["asked"], "task",
                                  asker=asker)
        elif regime in ("opening", "location"):
            # NOBODY IS THERE TO ANSWER, so the questions the Room asked
            # before the story -- the prelude's, above all -- are cleared
            # here as they always were, and the engine's own asks stand
            # (review G, 2026-10-08). The prelude expects the player may
            # simply begin; left standing, its question rode every task
            # payload for the whole story (the class chat 126 found).
            questions = [q for q in room.status(cid, frame_id).get("questions") or []
                         if q.get("source") == "engine"]
        elif questions is not None:
            questions = _restated(cid, frame_id, questions, "reply",
                                  engine=engine_asks)
        status = write_status(cid, frame_id, line=status_line,
                              questions=questions, turn_idx=turn_idx)
    return {"reply": reply, "dramaturge": None,
            "mandates": room.mandates(cid, frame_id), "status": status,
            "published": published, "opened": opened, "verdicts": verdicts,
            "claims": claims, "ask_dramaturge": ask_dramaturge,
            "calls": calls_made, "steps": steps, "notes": notes,
            "stopped": stopped, "regime": regime}


def _run_task(cid, frame_id, task, *, base_turn, job=None, before_pass=None,
              asker=None):
    """A background task: passes of `run_planner` in the task regime until
    the reply is done, a pass ends on a non-resumable stop, the passes cap
    is reached, or the job is cancelled. Spend per hour is checked by each
    pass; the wall is per pass. The passes so far ride the task so the
    model knows it is continuing, and what each asked carries into the next
    (``asker``, `_restated`; None: the task's own kind).
    ``before_pass(carried)``, when given, is handed each pass's copy of the
    task before that pass runs and may change it: a task whose question can
    move while it runs reads the question afresh there (the fill's open
    needs, `run_fill`). A task the job was cancelled under ends "cancelled"
    whichever pass the cancel reached, so its caller writes nothing on its
    account. A task that ends otherwise retires the drafts its own passes
    opened that the standing grants cannot carry (`_retire_stranded`)."""
    from core.jobs import is_cancelled
    asker = asker if asker is not None else _asker_for(task)
    passes, out = 0, None
    while passes < TASK_PASSES_CAP:
        if is_cancelled(job):
            break
        passes += 1
        carried = dict(task)
        if passes > 1:
            carried["resumed"] = {"pass": passes,
                                  "last_stopped": out["stopped"] if out else None,
                                  "published_so_far": list(out["published"]) if out else []}
        if before_pass is not None:
            before_pass(carried)
        this = run_planner(cid, frame_id, task=carried, base_turn=base_turn,
                           regime="task", job=job, asker=asker)
        if out is None:
            out = this
        else:
            out = {**this,
                   "published": out["published"] + this["published"],
                   "opened": out["opened"] + this["opened"],
                   "calls": out["calls"] + this["calls"],
                   "steps": out["steps"] + this["steps"],
                   "notes": out["notes"] + this["notes"],
                   # Each pass states its own facts, so they add up; a pass
                   # that stated none does not erase the one before it.
                   "claims": out["claims"] + this["claims"],
                   "verdicts": this["verdicts"] or out["verdicts"]}
        if this["stopped"] not in RESUMABLE_STOPS:
            break
    if out is None:
        # CANCELLED BEFORE ITS FIRST PASS: nothing ran, so nothing was
        # answered. The loop used to fall out holding None and fail the job
        # on `out["passes"]` -- a TypeError filed as the job's error where
        # the truth was a cancellation, and one the fill's back-off would now
        # read as an empty answer.
        out = {"reply": "", "published": [], "opened": [], "verdicts": [],
               "claims": [], "calls": 0, "steps": 0, "notes": [],
               "stopped": "cancelled", "regime": "task", "ask_dramaturge": None}
    if is_cancelled(job):
        out = {**out, "stopped": "cancelled", "reply": "", "verdicts": []}
    else:
        out["retired"] = _retire_stranded(cid, frame_id, out["opened"])
    out["passes"] = passes
    return out


def _retire_stranded(cid, frame_id, opened):
    """THE FLOOR UNDER "OPEN NO PACKAGE THAT CANNOT VALIDATE" (review F3,
    2026-10-08). A draft the Planner opens needs no grant; validating and
    publishing it do (`plot_packages.authority_errors`), and only the host
    may retire one. So in a story with no grant every accepted proposal the
    Planner tried to carry out left a draft that could never publish --
    measured by the review: three passes, three drafts -- each shown on the
    status row as in motion and each counted against `PACKAGES_CAP`, past
    which `new_package` refuses everything, the player's own asks included,
    until the host retires drafts by hand. At the end of a background task,
    every draft in ``opened`` -- the drafts THAT TASK's own `new_package`
    calls opened (`run_planner`'s ``opened``) -- authored by the room, that
    the standing grants do not cover is retired with the refusal as its
    note: a draft placed nothing, so nothing in the world changes. A draft
    the grants do cover is left for the work to go on.

    ONLY ITS OWN (review A, 2026-10-08). The floor first diffed the package
    ledger against the task's start, and every Planner draft carries the
    same author, so a draft a panel reply opened WHILE the task ran -- the
    player asking for a storm and the reply asking, package-scoped, for the
    grant -- was retired at the task's end, and the grant the player then
    gave lapsed on arrival (`mandates.request_open`). The status line is
    restated too: it stands only while something is in motion
    (`write_status`, review H), so a fill whose one draft is retired no
    longer leaves its "drafting ..." line behind. Returns the uids
    retired."""
    from story.plot_packages import (AGENT_AUTHORS, authority_errors, packages,
                                     retire_package)
    retired = []
    stored = packages(cid, frame_id)
    for uid in dict.fromkeys(str(u) for u in opened or ()):
        pkg = stored.get(uid)
        if pkg is None or pkg["status"] != "draft":
            continue
        if pkg["provenance"].get("created_by") not in AGENT_AUTHORS:
            continue
        errors = authority_errors(cid, frame_id, pkg)
        if not errors:
            continue
        retire_package(cid, uid, frame_id=frame_id, note=(
            "retired at the end of the background task that opened it, which "
            "the standing grants do not cover: %s" % errors[0])[:400])
        retired.append(uid)
    if retired:
        write_status(cid, frame_id)
    return retired


def _opening_task(cid, frame_id, passage, first_beat=""):
    """What the opening regime is handed: the passage the story opens on,
    who is present, what the launch already planted, and -- since the
    prelude (`docs/design/DESIGN_ROOM_PRELUDE.md`) -- whatever the player
    asked for before the story started."""
    from story.opening_plan import present_bodies
    from story.scene import persona_name, persona_of
    from core.db import q, wget_for_frame
    from world.structure import STRUCTURES_KEY, normalize_structures
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    try:
        player = persona_name(persona_of(dict(chat))) if chat else ""
    except Exception:
        player = ""
    present = present_bodies(cid)
    planted = sorted(normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, frame_id, {}) or {})["items"])
    task = {"kind": "opening",
            "passage": str(passage or "")[:PLANNER_TRANSCRIPT_CHARS],
            "player": player,
            "present": present,
            "planted_structures": planted}
    # The player's first line when it is PLAYED after the opening rather than
    # being part of it (`web.app._first_line_is_a_beat`): read for where each
    # body stands before it, never as something that has already happened.
    if str(first_beat or "").strip():
        task["first_beat"] = str(first_beat).strip()[:PLANNER_TRANSCRIPT_CHARS]
    # WHAT THE PLAYER ASKED FOR IS READ HERE, NOT PASSED IN
    # (`docs/design/DESIGN_ROOM_PRELUDE.md`). Both launches reach the
    # opening plan by their own route -- the greeting quick start calls it
    # directly, a scenario chat through `web.app._plan_opening` on turn 0 --
    # and a parameter would have had to be threaded through both and
    # remembered by the next one. The prelude is on the chat; the task reads
    # the chat.
    try:
        from story.prelude import player_wants
        said = [str(w)[:2000] for w in player_wants(cid, frame_id)][:20]
    except Exception:
        said = []
    if said:
        task["player_said"] = said
    return task


def run_opening_plan(cid, frame_id=None, *, passage, first_beat=""):
    """Plan the ground the story opens on, before the first turn row exists
    (`docs/design/DESIGN_OPENING_PLAN.md`). Mints the opening mandate, runs
    ONE pass of the planner in the `opening` regime, records the outcome in
    the `opening_plan` world row and the room thread, and NEVER RAISES: a
    launch is not failed by its plan. Returns the row written."""
    from story import room_conversation as room
    from story.opening_plan import (mint_opening_mandate, opening_placements,
                                    record_opening_plan)
    fields = {"published": [], "calls": 0, "steps": 0, "stopped": None,
              "notes": [], "error": "", "trace": []}
    # WHAT THE ROOM ACTUALLY DID, because nothing else records it. A
    # planner exchange is captured against a TURN (`persist/llm_capture`,
    # keyed on `turn_id`), and this runs before turn 0 exists, so the
    # opening plan's calls leave no trace anywhere -- the owner's question
    # on chat 131, after seventeen calls produced no package: "what is the
    # writers room actually doing in those calls, I have no idea." The
    # loop's own `on_event` seam is advisory by construction (a raising or
    # slow callback cannot change what the room does), so the trace costs
    # the plan nothing and rides the row the launch already writes.
    trace = []

    def _watch(event):
        if event.get("type") != "room_tool":
            return
        row = {"step": event.get("step"), "tool": event.get("tool")}
        if event.get("refused"):
            row["refused"] = str(event["refused"])[:200]
        if event.get("error"):
            row["error"] = str(event["error"])[:200]
        trace.append(row)

    try:
        mint_opening_mandate(cid, frame_id)
        task = _opening_task(cid, frame_id, passage, first_beat)
        out = run_planner(cid, frame_id, task=task, regime="opening",
                          base_turn=None, on_event=_watch)
        fields.update({
            "published": list(out.get("published") or []),
            "calls": int(out.get("calls") or 0),
            "steps": int(out.get("steps") or 0),
            "stopped": out.get("stopped"),
            "notes": list(out.get("notes") or []),
        })
        reply = str(out.get("reply") or "").strip()
        if reply:
            try:
                room.add_message(cid, frame_id, "planner", reply, turn_idx=0)
            except ValueError:
                pass
    except Exception as exc:
        logger.info("opening plan failed for chat %s: %s", cid, exc)
        fields["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:300])
    fields["trace"] = trace
    row = record_opening_plan(cid, frame_id, **fields)
    tools = ", ".join(
        "%s%s" % (t["tool"], "!" if t.get("refused") or t.get("error") else "")
        for t in trace) or "none"
    logger.info("opening plan for chat %s: %d published, %d calls, %d "
                "placement(s)%s; tools: %s", cid, len(row["published"]),
                row["calls"], len(opening_placements(cid, frame_id)),
                (", stopped: %s" % row["stopped"]) if row["stopped"] else "",
                tools)
    return row


def _cast_brief(cid):
    """Who the story is about, for a pass that runs before any of them has
    acted: the name and the one line a card leads with."""
    from story.room_tools import cast_minds_summary
    try:
        rows = cast_minds_summary(cid, None)
    except Exception:
        return []
    out = []
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict):
            continue
        out.append({"name": str(row.get("name") or "")[:120]})
    return [r for r in out if r["name"]][:12]


def _prelude_task(cid, frame_id, passage, location_requested):
    """What the prelude regime is handed. Deliberately the SAME shape the
    opening gets, minus the plan: the passage, who is present, and what the
    launch screen already decided about the place -- whether the player
    asked for one lived in before the story opens and, when they did, what
    they asked for, under the location regime's own keys (`_location_task`):
    `author_brief`, the months it has behind it, the people they named.

    It used to be the bool alone, so the Room asked about what the player
    had already written: a location note giving "a few hundred people" and a
    chandlery was answered with "a hamlet of forty souls ... or a working fen
    port of a few hundred?" (scratch story 164, 2026-10-06). Both launches
    record the request before the prelude runs."""
    task = _opening_task(cid, frame_id, passage)
    task["kind"] = "prelude"
    task["cast"] = _cast_brief(cid)
    task["location_requested"] = bool(location_requested)
    if location_requested:
        from story.prelude import pending_setup
        args = pending_setup(cid).get("args")
        lived = args.get("lived_location") if isinstance(args, dict) else None
        lived = lived if isinstance(lived, dict) else {}
        brief = str(lived.get("brief") or "").strip()
        if brief:
            task["author_brief"] = brief[:4000]
        hours = lived.get("horizon_hours")
        if isinstance(hours, (int, float)) and not isinstance(hours, bool) and hours > 0:
            task["horizon_hours"] = hours
        residents = lived.get("featured_residents")
        if isinstance(residents, list) and residents:
            task["featured_residents"] = copy.deepcopy(residents)
    return task


def run_prelude(cid, frame_id=None, *, passage, location_requested=False):
    """Ask the player what they want, before the story starts
    (`docs/design/DESIGN_ROOM_PRELUDE.md`).

    ONE pass of the planner in the `prelude` regime, over a task carrying
    the passage the story would open on. It publishes nothing and mints no
    mandate -- it only reads and asks -- and its reply is written to the
    room thread as the Room's first line. NEVER RAISES: a launch that the
    Room could not greet still opens, with the standing question in place
    of the one it would have written. Returns the line that was posted."""
    from story import room_conversation as room
    from story.prelude import PRELUDE_FALLBACK_LINE

    line = ""
    try:
        task = _prelude_task(cid, frame_id, passage, location_requested)
        out = run_planner(cid, frame_id, task=task, regime="prelude",
                          base_turn=None)
        line = " ".join(str(out.get("reply") or "").split())
    except Exception as exc:
        logger.info("prelude failed for chat %s: %s", cid, exc)
    line = line or PRELUDE_FALLBACK_LINE
    try:
        room.add_message(cid, frame_id, "planner", line, turn_idx=0)
    except ValueError:
        pass
    logger.info("prelude for chat %s: %d characters", cid, len(line))
    return line


def _location_task(cid, frame_id, payload, spec, closure=None):
    """What the location regime is handed: the ask, the lore that was
    selected for it, the constraints the launch is holding the plan to, and
    the SHAPE the plan must take -- `charter_generate._PLAN_SYSTEM`, the
    same specification the one-shot call was given, because there must be
    exactly one statement of what a location plan is."""
    payload = payload if isinstance(payload, dict) else {}
    lore = payload.get("lore")
    lore_text = (lore if isinstance(lore, str)
                 else json.dumps(lore, ensure_ascii=False, default=str))
    task = {"kind": "location",
            "author_brief": str(payload.get("author_brief") or "")[:4000],
            "lore": lore_text[:LOCATION_LORE_CHARS],
            "lore_truncated": len(lore_text) > LOCATION_LORE_CHARS,
            "shape": spec}
    for key in ("scale", "topology", "required_rooms", "featured_residents",
                "candidate_residents", "population", "naming_register"):
        if payload.get(key) not in (None, "", []):
            task[key] = payload[key]
    # WHETHER THIS PLACE HAS MONTHS BEHIND IT. The closure carries it
    # because it is the launch's decision, not the payload's: a horizon of
    # zero means the place exists and has not been lived through yet, and
    # the Room must not draft a prehistory nobody asked to simulate.
    closure = closure if isinstance(closure, dict) else {}
    task["wants_history"] = bool(closure.get("wants_history"))
    if task["wants_history"]:
        task["horizon_hours"] = float(closure.get("horizon_hours") or 0.0)
    try:
        from story.prelude import player_wants
        said = [str(w)[:2000] for w in player_wants(cid, frame_id)][:20]
    except Exception:
        said = []
    if said:
        task["player_said"] = said
    return task


def _location_digest(payload):
    """What this design is an answer TO. The same fingerprint idea
    `charter_runtime._request_digest` uses for the generation job, over the
    fields that decide what the place IS -- so a retry of the same ask
    adopts the plan and a retry of a changed one does not."""
    payload = payload if isinstance(payload, dict) else {}
    keys = ("author_brief", "lore", "scale", "topology", "required_rooms",
            "featured_residents", "population", "naming_register")
    asked = {k: payload.get(k) for k in keys}
    # Who MAY live here is part of the question, but only where there is
    # anyone to ask about: a payload without candidates digests as it always
    # did, so no design already submitted is orphaned by the new key.
    if payload.get("candidate_residents"):
        asked["candidate_residents"] = payload["candidate_residents"]
    body = json.dumps(asked, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def run_location_plan(cid, frame_id=None, *, payload, closure=None):
    """The Writers' Room designs the inhabited location
    (`docs/design/DESIGN_ROOM_PRELUDE.md` § 4, `story/location_design.py`).

    Replaces `charter_generate.propose_town`'s single `utility` call. The
    Room reads the lore with its own tools, drafts the map and the
    institutions a piece at a time, asks the engine to close what it has,
    fixes what comes back, and submits. Returns the plan in the shape
    `propose_town` returned one, so everything downstream is untouched.

    `payload` is what `propose_town` would have been sent. `closure` carries
    what `close_plan` needs when the draft is reviewed -- the featured
    residents, the reservation, the naming law, the population -- so that the
    check the Room runs IS the check the launch will run.

    Raises `ValueError` when the Room produced no usable plan. Deliberately:
    the caller is a location generation, which already has a failure path
    that keeps the story and offers a retry, and falling back to the
    one-shot would be keeping alive the thing this replaces."""
    from story import location_design
    from llm import providers
    from world.charter_generate import plan_specification

    closure = dict(closure or {})
    task = _location_task(cid, frame_id, payload, plan_specification(), closure)
    closure.setdefault("featured_residents",
                       (payload or {}).get("featured_residents") or [])
    closure.setdefault("population", (payload or {}).get("population"))
    # ALREADY DESIGNED IS ALREADY DONE (owner, chat 150, 2026-09-17: "you've
    # made it so i have to rerun every single step instead of recovering from
    # what the writers room sucesfully planned"). A design is 227-250 seconds
    # and six to nine model calls -- by far the most expensive thing a launch
    # does -- and every stage after it can raise. A plan submitted for THIS
    # request is adopted whole; one submitted for a different one is not,
    # because an author who changed the brief asked a different question.
    digest = _location_digest(payload)
    kept = location_design.submitted_for(cid, digest)
    if kept is not None:
        logger.info("location plan for chat %s: adopting the plan a previous "
                    "pass submitted (%d rooms, %d charters)", cid,
                    len(kept.get("rooms") or {}),
                    len(kept.get("charters") or []))
        return kept
    resumed = location_design.resumable_draft(cid, digest, closure)
    if resumed is not None:
        held = resumed.get("plan") or {}
        task["resumed_draft"] = {
            "rooms": sorted(str(r) for r in (held.get("rooms") or {})),
            "institutions": [str((c or {}).get("key") or "")
                             for c in held.get("charters") or []
                             if isinstance(c, dict)],
            "history": bool(resumed.get("history"))}
        logger.info("location plan for chat %s: resuming an unsubmitted "
                    "draft (%d rooms, %d charters)", cid,
                    len(held.get("rooms") or {}),
                    len(held.get("charters") or []))
    else:
        location_design.open_draft(cid, closure, digest)
    calls = steps = 0
    stopped = None
    started = time.time()
    try:
        # A DESIGN IS ALLOWED TO THINK. The stream watchdog
        # (`PROVIDER_SILENCE_SECONDS`, 10s) was measured against pipeline
        # SPECIALISTS, "where the role's usual cost is 3-7 s" -- the right
        # threshold for a stage a player is waiting on, and the wrong one for
        # the most expensive call this engine makes. A location pass is
        # 227-250 seconds over six to nine calls, planning a whole inhabited
        # place, and a reasoning model pauses longer than ten seconds inside
        # one. Measured 2026-09-19/20: four consecutive town designs died on
        # that watchdog, the last after 2,032 characters of reasoning and no
        # content -- a model that was working, killed for not being finished.
        # Raised HERE, by the caller that knows what it is doing, exactly as
        # `request_timeout` is raised for a long authoring read; every
        # pipeline stage keeps the 10s it was tuned for.
        with providers.patient_stream(180):
            out = run_planner(cid, frame_id, task=task, regime="location",
                              base_turn=None)
        calls = int(out.get("calls") or 0)
        steps = int(out.get("steps") or 0)
        stopped = out.get("stopped")
        plan = location_design.submitted_plan(cid)
        if plan is None:
            # WHAT IT HAD, said plainly. A pass that ran out one call from
            # `submit_location` is the failure the opening plan already had
            # once (chat 127, 2026-09-16), and the only way to know which
            # one this is, is to say what was on the table when it stopped.
            row = location_design.draft(cid)
            drafted = row.get("plan") or {}
            raise ValueError(
                "the Writers' Room did not submit a location plan "
                "(%d calls, %d steps%s); it had %d room(s) and %d "
                "institution(s) drafted"
                % (calls, steps, (", stopped: %s" % stopped) if stopped else "",
                   len(drafted.get("rooms") or {}),
                   len(drafted.get("charters") or [])))
        location_design.keep_submitted(cid, digest, plan)
        logger.info("location plan for chat %s: %d rooms, %d charters, "
                    "%d calls, %d steps, %.1fs", cid,
                    len(plan.get("rooms") or {}),
                    len(plan.get("charters") or []), calls, steps,
                    time.time() - started)
        location_design.record_pass(
            cid, calls=calls, steps=steps, stopped=stopped,
            seconds=round(time.time() - started, 1),
            rooms=len(plan.get("rooms") or {}),
            charters=[str(c.get("key") or "") for c in
                      (plan.get("charters") or [])][:40],
            error="")
        return plan
    except Exception as exc:
        # WHAT THE ROOM WAS DOING, because nothing else records it and the
        # owner has asked that question of a planner pass before (chat 131,
        # `DESIGN_OPENING_PLAN.md` § 4a). A generation that failed here
        # leaves a story in the library with a retry; this is what the
        # retry's author needs to decide whether to ask for less.
        row = location_design.draft(cid)
        drafted = row.get("plan") or {}
        location_design.record_pass(
            cid, calls=calls, steps=steps, stopped=stopped,
            seconds=round(time.time() - started, 1),
            rooms=len(drafted.get("rooms") or {}),
            charters=[str(c.get("key") or "") for c in
                      (drafted.get("charters") or [])][:40],
            error="%s: %s" % (type(exc).__name__, str(exc)[:400]))
        # PAUSED, NOT CLEARED: what the pass drafted is kept for a retry of
        # THIS request (`location_design.resumable_draft`), and closed to the
        # draft tools meanwhile. A different request still starts fresh.
        location_design.pause_draft(cid)
        raise
    finally:
        # Cleared on success: the plan it produced is the job's artifact now,
        # and a draft left open would be offered to the next pass as work in
        # progress. A failed pass paused its draft above.
        if not location_design.draft(cid).get("paused"):
            location_design.close_draft(cid)


def room_town_planner(cid, frame_id=None):
    """The town planner `generate_lived_location` takes: the Writers' Room.

    ONE contract, `(payload, closure) -> plan`, and it takes BOTH of its
    arguments at the call rather than one of them at construction. It was a
    factory over `closure` for a few hours on 2026-09-17 and the caller
    invoked it with the closure to obtain the model call, so the Room ran
    with `closure_inputs` as its payload -- no brief, no lore, no
    constraints -- designed fourteen rooms out of nothing over 249 seconds,
    and handed back a plan that `propose_town` then tried to CALL
    (`TypeError: 'dict' object is not callable`, chat 149). Two curried
    arguments of different meanings is what made that mistake available;
    one call with both is what closes it."""

    def _plan(payload, closure=None):
        return run_location_plan(cid, frame_id, payload=payload,
                                 closure=closure)

    return _plan


def planner_reply(cid, frame_id, text, *, on_event=None):
    """The seam's shape: what `room_conversation.PLANNER` returns. When the
    Planner hands a brief to the Dramaturge, the pass runs OUT OF BAND (a
    background task has no wall) and its lines land in the thread; the
    envelope's `dramaturge` stays None and the panel's watch shows them.
    The brief is handed whatever the grants say: asking the Dramaturge for
    direction needs no grant (owner, 2026-10-08), and acting on what it
    suggests still does (`run_dramaturge_pass`).

    THE ASK IS KEPT BEFORE ANYTHING IS QUEUED (review F1, 2026-10-08). The
    pacing pass and the asked one share `DRAMATURGE_JOB_KEY`, and
    `core.jobs.submit` joins a job already in flight: an ask made while a
    pacing pass ran -- minutes, with its deliberation -- joined it and was
    never read, and the pass's own note looked like the answer. The brief
    waits on the room's row (`room_proposals.ask_brief`) for whichever pass
    takes it: this one, the one it joined (at its end), or, when that one was
    cancelled, the next commit's (`schedule_room_work`)."""
    from core import jobs
    from persist.llm_capture import room_capture
    from story import room_conversation as room
    from story.room_bible import schedule_fold
    from story.room_proposals import ask_brief
    out = run_planner(cid, frame_id, text=text, regime="reply",
                      on_event=on_event)
    if out.get("ask_dramaturge"):
        brief = out["ask_dramaturge"]
        # EVERY JOB CARRIES ITS BASE TURN (review 2026-09-07 A33). Both
        # rewind guards -- `run_planner`'s per-write check and
        # `run_dramaturge_pass`'s own -- open with `if base_turn is not
        # None`, so a None here is not a missing number, it is the guard
        # switched off: a pass launched from the panel could land its
        # proposals, judgements and revisions onto a story the player had
        # meanwhile rewound underneath it. The commit tail already passes
        # `turn_idx` for exactly this reason; the panel is the same act
        # from the other door, and reads the number the same way
        # `run_planner` does.
        base = room.current_turn_idx(cid)
        ask_brief(cid, _player_frame(cid, frame_id), brief, turn_idx=base)

        def _run(job):
            # The reply's own scope does not reach here: the pass runs out
            # of band, in a job, and `core/jobs.py` clears turn-scoped
            # contextvars. A brief handed to the Dramaturge is the most
            # readable thing the room does and would otherwise be the
            # least readable. The brief itself is not passed: the pass
            # takes it, and any other waiting, from the room's row.
            with room_capture(cid, "dramaturge"):
                return run_dramaturge_pass(cid, frame_id, base_turn=base,
                                           job=job)

        jobs.submit(cid, DRAMATURGE_JOB_KEY, _run, base_turn=base)
    try:
        schedule_fold(cid, frame_id, window=PLANNER_HISTORY_MESSAGES)
    except Exception as exc:
        logger.info("bible fold not scheduled: %s", exc)
    return {"reply": out["reply"], "dramaturge": None,
            # What the reply STATED, for `room_citations.check_claims` to
            # hold against the rows this reply actually read. The seam
            # returns them rather than checking them: the ledger lives in
            # the context that made the calls, which for a streamed reply
            # is a worker thread.
            "claims": out["claims"],
            "mandates": out["mandates"], "status": out["status"]}


def seat():
    """Seat the Planner on the room's seam. Called once at app startup."""
    from story import room_conversation as room
    return room.seat_planner(planner_reply)


def unseat():
    from story import room_conversation as room
    return room.seat_planner(None)


# ---------------------------------------------------------------------------
# The deliberation
# ---------------------------------------------------------------------------

def _proposal_brief(p):
    return {k: p.get(k) for k in ("uid", "kind", "title", "wants_true", "why_now",
                                  "must_not_contradict", "scale", "revision",
                                  "judgements")}


def deliberate(cid, frame_id, proposals, *, base_turn=None, dial=0,
               turn_idx=None, job=None):
    """The Planner judges the Dramaturge's proposals and implements what
    survives. Each round: the Planner is handed the pending proposals as a
    task and answers `verdicts` (accept / refuse / revise, each with its
    reason and the contradiction it names) beside whatever package it
    drafts; a `revise` goes back to the Dramaturge, whose revision is judged
    in the next round. After `DELIBERATION_ROUNDS` a proposal still pending
    is RETURNED to the player as a disagreement, never forced (v2 § 6.3).
    Returns a report; every line of the exchange is stored in the thread.
    A cancelled ``job`` stops the deliberation where it stands: nothing is
    judged, said, returned or asked after the cancel (`report["cancelled"]`),
    because what it would write was weighed against a beat the player may
    have rerolled (`persist/checkpoints.restore_checkpoint`).

    The proposals are TAKEN first (`room_proposals.take_proposals`): no
    longer due, and stamped with the beat, so one this deliberation leaves
    pending -- a failed call, a cancel -- waits its bound again from here
    rather than being judged twice at once (`run_direction_follow_up`). The
    questions every round asks are ONE task's, keyed by the proposals it was
    handed (`_restated`): a later round, a fill or another deliberation does
    not take them off, and they leave once all those proposals settle.

    WHAT IT READS, IT READS BEFORE IT TAKES ANYTHING (review R3-1,
    2026-10-08): its proposals were written from the beats through their
    `filed_turn`, and its Planner reads the world the newest beat left, so
    ``job``'s read horizon is raised there first (`core.jobs.read_through`)
    and a restore that discards one of those beats stops it. A job a restore
    has spared starts nothing it could only build on a beat being played
    again (`report["spared"]`). A verdict on a proposal that is gone -- a
    restore rolled it back under a deliberation -- is skipped (review R3-5).

    ONLY WHAT IT LEFT PENDING IS RETURNED (review R4-2, 2026-10-08). A
    proposal this deliberation accepted, refused, or saw withdrawn, and that
    is pending again at the end, had that verdict rolled back by a restore
    that spared the job -- a verdict that acted is not kept across one
    (`room_proposals.keep_spared`). It is judged again at its bound, as the
    restore leaves it; returned, the Planner's acceptance was thrown away
    and the player was asked to settle a disagreement the room never had.
    """
    from agents import dramaturge
    from core.jobs import is_cancelled, read_through
    from story import room_conversation as room
    from story.room_frontier import frame_turn_idx
    from story.room_proposals import (PENDING_STATUSES, get_proposal,
                                      judge_proposal, settle_proposal,
                                      take_proposals)
    turn_idx = room.current_turn_idx(cid) if turn_idx is None else int(turn_idx)
    uids = [p["uid"] for p in proposals if p.get("kind") != "quiet"]
    report = {"rounds": 0, "implemented": [], "refused": [], "withdrawn": [],
              "returned": [], "published": [], "calls": 0}
    if uids and job is not None:
        newest = max([frame_turn_idx(cid, frame_id)]
                     + [int(p.get("filed_turn") or 0) for p in proposals])
        if read_through(job, newest) < newest:
            report["spared"] = True
            return report
    if uids and not is_cancelled(job):
        take_proposals(cid, frame_id, uids, turn_idx)
    asker = {"asker": "deliberate", "proposals": sorted(uids), "asked": []}
    concluded = set()        # the uids a round of this one judged to an end
    for round_no in range(1, DELIBERATION_ROUNDS + 1):
        if is_cancelled(job):
            break
        pending = [get_proposal(cid, frame_id, u) for u in uids]
        pending = [p for p in pending if p and p["status"] in PENDING_STATUSES]
        if not pending:
            break
        report["rounds"] = round_no
        task = {"kind": "deliberate", "round": round_no,
                "rounds": DELIBERATION_ROUNDS, "dial": int(dial),
                "proposals": [_proposal_brief(p) for p in pending]}
        out = _run_task(cid, frame_id, task, base_turn=base_turn, job=job,
                        asker=asker)
        report["calls"] += out["calls"]
        report["published"].extend(out["published"])
        if is_cancelled(job):
            break
        if out["reply"]:
            try:
                room.add_message(cid, frame_id, "planner", out["reply"],
                                 turn_idx=turn_idx)
            except ValueError:
                pass
        judged = set()
        for v in out["verdicts"]:
            if is_cancelled(job):
                break
            uid = str(v.get("proposal_uid") or v.get("uid") or "")
            if uid not in {p["uid"] for p in pending}:
                continue
            verdict = str(v.get("verdict") or "").casefold()
            package_uid = str(v.get("package_uid") or "")
            if verdict == "accept" and not package_uid and out["published"]:
                package_uid = out["published"][0]
            try:
                row = judge_proposal(
                    cid, frame_id, uid, verdict=verdict, reason=v.get("reason"),
                    contradiction=v.get("contradiction") or "", round_no=round_no,
                    turn_idx=turn_idx, package_uid=package_uid)
            except ValueError:
                continue
            if row is None:
                # Gone from the row while the Planner judged it: a restore
                # rolled it back (review R3-5). Nothing to judge or revise.
                report.setdefault("vanished", []).append(uid)
                continue
            judged.add(uid)
            if row["status"] not in PENDING_STATUSES:
                concluded.add(uid)
            if row["status"] == "implemented":
                report["implemented"].append(uid)
            elif row["status"] == "refused":
                report["refused"].append(uid)
            elif row["status"] == "revised":
                revised, note = dramaturge.revise(
                    cid, frame_id, row, row["judgements"][-1], dial=dial,
                    turn_idx=turn_idx, job=job)
                if note and not is_cancelled(job):
                    try:
                        room.add_message(cid, frame_id, "dramaturge", note,
                                         turn_idx=turn_idx)
                    except ValueError:
                        pass
                if revised and revised["status"] == "withdrawn":
                    report["withdrawn"].append(uid)
                if revised and revised["status"] not in PENDING_STATUSES:
                    concluded.add(uid)
        # An accepted proposal with no package yet stays accepted: the
        # Planner said it is natural and is working it; nothing more to
        # deliberate. A pending proposal the Planner did not judge stays
        # pending for the next round.
    if is_cancelled(job):
        report["cancelled"] = True
        return report
    for uid in uids:
        p = get_proposal(cid, frame_id, uid)
        if p and p["status"] in PENDING_STATUSES:
            if uid in concluded:
                report.setdefault("rolled_back", []).append(uid)
                continue
            settle_proposal(cid, frame_id, uid, "returned", turn_idx=turn_idx)
            report["returned"].append(uid)
    if report["returned"]:
        try:
            room.add_message(cid, frame_id, "room", DISAGREEMENT_LINE,
                             turn_idx=turn_idx)
        except ValueError:
            pass
        # THE ENGINE'S OWN ASK, ahead of every model question (review,
        # 2026-10-08), and ONE of it: the standing returned-proposal ask
        # names these beside the ones the player has not answered yet, each
        # once (`ask_returned`, review E). The player settles it in
        # conversation, and a reply that does not restate it drops it.
        ask_returned(cid, frame_id, report["returned"], turn_idx=turn_idx)
    # THE ROW SAYS WHAT IS IN MOTION AFTER THE JUDGEMENT, not before it. The
    # task wrote it while the proposals still waited on the Planner, so an
    # accepted, refused or returned proposal stood on the row as open until
    # some later write; the line is kept only while something is in motion
    # (`write_status`).
    write_status(cid, frame_id, turn_idx=turn_idx)
    return report


def _player_frame(cid, frame_id):
    """The frame a Dramaturge pass reads, paces and speaks in: ``frame_id``
    itself, or -- for a live causality bubble, a frame nobody plays -- its
    era's. A bubble's beats carry no player line and no narration
    (`agents/offscreen_beat.py`), so a pass read there reads an empty
    stream, and the pacing row it would stamp is the era's shared one. The
    commit tail never queues a pass from a bubble; this is the panel's
    door, which a viewer reaches by switching to a bubble's frame pill."""
    if frame_id is None:
        return None
    from core.db import era_of_frame
    from world.spatial_frames import is_bubble_frame
    try:
        if is_bubble_frame(cid, frame_id):
            return era_of_frame(frame_id)
    except Exception:
        pass
    return frame_id


def run_dramaturge_pass(cid, frame_id, *, base_turn=None, brief=None, job=None):
    """One Dramaturge pass, out of band: it suggests, and leaves the
    judging to the follow-up -- at once when the player asked, and when the
    story comes near the suggestion otherwise (`run_direction_follow_up`).

    SUGGESTING NEEDS NO GRANT (owner, 2026-10-08: "It was never meant to be
    surprise only, it was meant to suggest story directions"). The pass
    runs at the dial a standing grant names, else at
    `mandates.SURPRISE_DEFAULT`; it is never refused for want of one.
    ACTING ON A SUGGESTION STILL NEEDS THE PLAYER'S GRANTS: the Planner
    implements an accepted proposal only through a package, a package the
    Planner drafted validates and publishes only under mandates covering
    every operation in it (`plot_packages.authority_errors`, read at both),
    and a task reads no grants (`run_planner`), so the deliberation cannot
    license itself. With none, the Planner says what it would need -- the
    card's "ask for it plainly".

    Refuses when the story rewound under the job or the story hour's spend
    is gone (`mandates.spend_limits`). A live bubble's pass is its era's
    (`_player_frame`). The pass is RECORDED before the Dramaturge is
    called, at the frame's own newest beat (`room_frontier.frame_turn_idx`,
    never a bubble's row above it), so a pass whose provider failed has had
    its turn and is asked again at the pacing, not at every commit. Every
    line lands in the thread.

    THE PLAYER'S ASKS ARE ANSWERED HERE, WHENEVER THEY CAME (review F1,
    2026-10-08). The Planner keeps the brief it hands on
    (`room_proposals.ask_brief`) before it queues a pass, and the pacing
    pass and the asked one share one job key, so an ask made while a pass
    ran used to join it and go unread. A pass takes every brief waiting at
    its start (``brief``, when a caller hands one directly, goes first), and
    when it is done it answers, with one more pass, whatever was asked while
    it ran -- until nothing waits. One pass answers every ask that waited
    for it.

    A CANCELLED PASS WRITES NOTHING (review F2, 2026-10-08): a restore that
    discards the beat it read cancels it (`persist/checkpoints.
    restore_checkpoint`) and every write below asks `core.jobs.is_cancelled`
    first. Its one write is to hand back the briefs it took AND HAD NOT YET
    ANSWERED (review C): they are the conversation's, not the rerolled
    beat's, but once the Dramaturge's answer is in the thread -- which no
    restore takes back -- handing the ask back had it answered twice, at the
    cost of two passes. A REROLL RE-ARMS THE PACING: a cancelled pass that
    had not answered gives its turn back (`room_proposals.give_back_pass`),
    and one whose answer was read from the rerolled beat loses it with that
    answer (`room_proposals.keep_spared`), so the rerolled beat is asked
    again, as itself (`room_proposals.pass_due`).

    BY WHAT IT READ (review R3-1): every round of the loop reads the beats
    played since, and the stream raises the job's read horizon before it
    reads them (`dramaturge.player_visible_stream`), so a restore that
    discards a beat any round read cancels the pass. A pass the restore
    spared -- it read only beats the restore keeps -- finishes the round it
    is in and starts no other (`core.jobs.spared`) -- the next would read the
    beat being played again -- unless the replayed beat's own commit joins
    it, which hands it that beat (`core.jobs.submit`).

    A PASS THAT FAILS HANDS BACK THE ASKS IT TOOK AND HAD NOT ANSWERED
    (review R3-7): they are the conversation's, and the provider's refusal
    is not an answer. Handed back with the beat it failed at, so the next
    pass that takes them comes at the pacing -- or, with the passes off, at
    the default pace -- rather than at every commit, which a dead provider
    makes expensive (`room_proposals.briefs_due`)."""
    from core.jobs import is_cancelled, spared, story_rewound_past
    from story import room_conversation as room
    from story.mandates import spend_limits
    from story.room_frontier import spend_this_hour
    from story.room_proposals import give_back_pass, hand_back_briefs, take_briefs
    now = room.current_turn_idx(cid)
    if base_turn is not None and story_rewound_past(base_turn, now):
        return {"skipped": "rewound", "base_turn": base_turn, "turn": now}
    frame_id = _player_frame(cid, frame_id)

    def _spent():
        spend = spend_limits(cid, frame_id, now)
        return (spend["calls_per_hour"] is not None
                and spend_this_hour(cid, frame_id, now) >= spend["calls_per_hour"])

    report, given = None, [brief] if brief else []
    while not is_cancelled(job) and not spared(job) and not _spent():
        asks = given + take_briefs(cid, frame_id)
        given = []
        if report is not None and not asks:
            break
        progress, failed = {}, False
        try:
            one = _dramaturge_pass(cid, frame_id, now=now, brief=_joined_briefs(asks),
                                   asks=asks, base_turn=base_turn, job=job,
                                   progress=progress)
        except BaseException:
            failed = True
            raise
        finally:
            if asks and not progress.get("answered") \
                    and (failed or is_cancelled(job)):
                hand_back_briefs(cid, frame_id, asks,
                                 failed_turn=None if is_cancelled(job) else now)
            if progress.get("pass") is not None and is_cancelled(job) \
                    and not progress.get("answered") and not progress.get("landed"):
                give_back_pass(cid, frame_id, progress["pass"])
        if report is None:
            report = one
        else:
            report.setdefault("asked_after", []).append(one)
    if report is None:
        return {"skipped": "cancelled" if is_cancelled(job)
                else "spared" if spared(job) else "spend_hour"}
    if is_cancelled(job):
        report["cancelled"] = True
    elif spared(job):
        report["spared"] = True
    return report


def _joined_briefs(asks):
    """The asks one pass answers, as the one `player_asks` the Dramaturge
    reads: oldest first, and within its cap the newest kept whole."""
    from agents.dramaturge import DRAMATURGE_BRIEF_CHARS
    asks = [str(a).strip() for a in asks or () if str(a or "").strip()]
    if not asks:
        return None
    text = "\n".join(asks)
    return text[-DRAMATURGE_BRIEF_CHARS:]


def _dramaturge_pass(cid, frame_id, *, now, brief, base_turn, job, progress=None,
                     asks=()):
    """One Dramaturge pass in the frame the caller resolved. See
    `run_dramaturge_pass`. ``progress["answered"]`` is set once the pass's
    answer lands -- its note in the thread, its proposals on the row -- so
    a cancel after that point is not handed the ask back (review C);
    ``progress["pass"]`` names the pass's entry in the row's log, which a
    cancel before that point gives back (`room_proposals.give_back_pass`).
    ``asks`` are the player's asks the pass took, which ``brief`` joins.

    RECORDED AT THE NEWEST BEAT SOMETHING HAS ANSWERED
    (`dramaturge.newest_answered_beat`, review R4-1): the beats a pass reads
    (`dramaturge.player_visible_stream`), never a line still being answered
    above them -- recorded there, a pass that read through the beat before
    stood on the beat in play, and a reroll of it took the pass's turn.
    LANDED with the newest beat its job had read (`room_proposals.land_pass`),
    so a restore that discards one of them gives the turn back with the
    answer (`room_proposals.keep_spared`).

    THE DELIBERATION IS NOT THIS PASS'S (owner, 2026-10-08: "save heavy
    plans for when the actors near them"). The Planner's judgement is six
    or more calls; on the pacing it ran in the same job, every six beats,
    over directions the story might never come near. A PACING pass now
    files its suggestions and leaves them pending: the follow-up at each
    commit asks whether the beat brought the story to one, and judges it
    then -- or once it has waited its bound, so nothing is dropped
    (`run_direction_follow_up`). A pass THE PLAYER ASKED FOR marks what it
    filed due at once and queues the follow-up: an answer the player is
    waiting on is never left to wait on the story."""
    from agents import dramaturge
    from core.jobs import is_cancelled, spared
    from story import room_conversation as room
    from story.mandates import surprise_dial
    from story.room_frontier import frame_turn_idx, record_spend
    from story.room_proposals import (awaits_planner, land_pass, mark_due,
                                      record_pass)
    dial = surprise_dial(cid, frame_id, now)
    answered = dramaturge.newest_answered_beat(cid, frame_id)
    entry = record_pass(cid, frame_id, answered if answered is not None
                        else frame_turn_idx(cid, frame_id))
    if progress is not None:
        progress["pass"] = entry["pass"]
    out = dramaturge.propose(cid, frame_id, dial=dial, brief=brief, turn_idx=now,
                             job=job, asks=asks)
    report = {"dial": dial, "proposals": [p["uid"] for p in out["proposals"]],
              "none_needed": out["none_needed"], "refused": out["refused"],
              "dramaturge_calls": out["calls"], "deliberation": None}
    if brief:
        report["asked"] = brief
    if is_cancelled(job):
        report["cancelled"] = True
        # WHAT IT FILED BEFORE THE CANCEL STANDS OR FALLS BY ITS OWN BEAT
        # (`room_proposals.keep_spared`): a suggestion from a beat the
        # restore keeps is the pass's turn, had, and the pass lands with it;
        # one with nothing standing gives its turn back
        # (`run_dramaturge_pass`). By the beat the restore took the story
        # back to (`core.jobs.cancel_from`), so the answer is the same
        # whether this runs before the restore's transaction or after it.
        back_to = getattr(job, "cancelled_from", None)
        stands = [p["filed_turn"] for p in out["proposals"]
                  if back_to is None or p["filed_turn"] < back_to]
        if stands:
            land_pass(cid, frame_id, entry["pass"], max(stands))
            if progress is not None:
                progress["landed"] = True
        return report
    if progress is not None:
        progress["answered"] = True
    read = getattr(job, "read_turn", None)
    land_pass(cid, frame_id, entry["pass"],
              read if read is not None else entry["turn"])
    if out["calls"]:
        record_spend(cid, frame_id, turn_idx=now, calls=out["calls"],
                     who="dramaturge")
    if out["note"]:
        try:
            room.add_message(cid, frame_id, "dramaturge", out["note"], turn_idx=now)
        except ValueError:
            pass
    filed = [p["uid"] for p in out["proposals"] if awaits_planner(p)]
    if brief and filed and not is_cancelled(job):
        mark_due(cid, frame_id, {uid: "asked" for uid in filed})
        if spared(job):
            # A PASS A RESTORE SPARED QUEUES NO FOLLOW-UP (review of
            # 2026-10-08, round 4): a fresh job carries no read limit and
            # would read the beat being played again, its old narration
            # still standing. What it filed waits due as asked, and the
            # replayed beat's commit -- or the next, when the pass files
            # after it -- has it judged (`follow_up_wanted`).
            report["deliberation"] = "due"
        else:
            report["deliberation"] = "queued"
            _queue_follow_up(cid, frame_id, base_turn)
    elif filed:
        report["awaiting"] = filed
    if not is_cancelled(job):
        # THE ROW SHOWS WHAT THE PASS FILED and keeps the questions the room
        # is waiting on: written bare, the row lost them -- and a grant
        # scoped to a question lapses when the question leaves the row
        # (`mandates.request_open`) -- which, on the pacing, would have been
        # every sixth beat. The LINE is not kept for its own sake: it says
        # what is in motion, so it stands while something is and gives way
        # to "nothing in motion" when nothing is (`write_status`); kept
        # whole, a deliberation's "building the bill" outlived the package
        # it described and was read back as the next pass's `status_line`
        # (review, 2026-10-08).
        write_status(cid, frame_id, turn_idx=now)
    return report


# ---------------------------------------------------------------------------
# The direction follow-up: the deliberation waits for the story to near it
# ---------------------------------------------------------------------------

def _queue_follow_up(cid, frame_id, base_turn):
    """Queue the direction follow-up (`run_direction_follow_up`) under
    `DIRECTION_JOB_KEY`: one at a time per chat, so two deliberations never
    judge one proposal at once. One already running takes up whatever is due
    when it finishes what it holds. Never raises; returns the job."""
    from core import jobs
    from persist.llm_capture import room_capture

    def _follow(job):
        # Armed inside the job: `core/jobs.py` clears turn-scoped contextvars
        # (`persist/llm_capture.room_capture`).
        with room_capture(cid, "dramaturge"):
            return run_direction_follow_up(cid, frame_id, base_turn=base_turn,
                                           job=job)
    return jobs.submit(cid, DIRECTION_JOB_KEY, _follow, base_turn=base_turn)


def follow_up_wanted(cid, frame_id, turn_idx):
    """Whether a commit at beat ``turn_idx`` has anything for the follow-up:
    a proposal already due (a player's ask a running follow-up has not
    taken), one that has waited its bound, or -- when the decision model
    can be asked at all -- one no deliberation has taken yet, whose beat
    this may be. Pure reads; never raises."""
    try:
        from story.mandates import beats_per_proposal
        from story.room_proposals import (direction_wait_beats, pending_proposals,
                                          waited_beats)
        pending = pending_proposals(cid, frame_id)
        if not pending:
            return False
        if any(p["due"] for p in pending):
            return True
        wait = direction_wait_beats(beats_per_proposal(cid, frame_id, turn_idx))
        if any(waited_beats(cid, frame_id, p, turn_idx) >= wait for p in pending):
            return True
        if any(p["taken_turn"] is None for p in pending):
            from llm import decisions
            return bool(decisions.configured())
    except Exception as exc:
        logger.info("direction follow-up not weighed for chat %s: %s", cid, exc)
    return False


def _unread_stream(cid, frame_id, beat, job=None):
    """The beats of this frame the follow-up's decision has not read yet, as
    the player saw them: every beat after the last one it read (the beats
    that passed while a deliberation held the job included), at most
    `dramaturge.DRAMATURGE_BEATS`, through ``job``'s read horizon -- which
    the read raises (`core.jobs.read_through`). Each suggestion is asked
    only about those of them played after the beats it was written from
    (`_mark_due_now`).

    ONLY A NARRATED BEAT IS READ (review R3-6, 2026-10-08). The turn row
    exists from the moment the player sends their line, so a follow-up that
    came round while the beat ran read the line alone, marked the beat read,
    and the narration that answered it was never asked about."""
    from agents.dramaturge import DRAMATURGE_BEATS, player_visible_stream
    from core.jobs import story_rewound_past
    from story.room_proposals import follow_up_turn
    stream = [b for b in player_visible_stream(cid, frame_id, beats=DRAMATURGE_BEATS,
                                               job=job)
              if b["narration"]]
    last = follow_up_turn(cid, frame_id)
    if last is None or story_rewound_past(last, beat):
        return stream
    return [b for b in stream if b["beat"] > last]


def _passage(stream):
    """The decision model's state: the beats as the player read them, their
    own line and the narration that answered it."""
    parts = []
    for b in stream or ():
        said = " ".join(str(b.get("player") or "").split())
        prose = str(b.get("narration") or "").strip()
        parts.append("\n".join(x for x in (("> " + said) if said else "", prose) if x))
    return "\n\n".join(p for p in parts if p)


def directions_neared(cid, proposals, stream):
    """``{uid: yes-share}`` -- whether ``stream`` brings the story to what
    each proposal is about (`jev_questions.direction_neared`, asked of the
    passage alone, one question per proposal: its title, what it wants true
    and why now). None when the decision model cannot answer -- unconfigured,
    refused, unreachable -- so the caller falls back on the bound alone;
    nothing waits on it."""
    from language_runtime import story_language
    from llm import decisions
    from llm.prompts import jev_question
    passage = _passage(stream)
    if not passage or not proposals:
        return {}
    try:
        if not decisions.configured():
            return None
        language = story_language(cid)
    except Exception:
        return None
    battery = {}
    for p in proposals:
        text = jev_question("direction_neared", language, title=p["title"],
                            wants_true=p["wants_true"],
                            why_now=p.get("why_now") or "")
        if text:
            battery["near:" + p["uid"]] = {"type": "noul", "instructions": text}
    if not battery:
        return {}
    try:
        answers = decisions.decide("PASSAGE:\n" + passage, battery)
    except Exception as exc:  # noqa: BLE001 -- the bound still holds
        logger.info("direction follow-up: the decision model did not answer "
                    "for chat %s: %s", cid, exc)
        return None
    return {key[len("near:"):]: round(decisions.probability(answers.get(key)), 4)
            for key in battery}


def _mark_due_now(cid, frame_id, beat, report, job):
    """Read the beats since the last reading and mark what is due: every
    pending proposal that has waited its bound (`DIRECTION_WAIT_INTERVALS`
    of the story's pace), and every one no deliberation has taken yet that
    the decision model reads the unread beats as nearing. A proposal a cut-
    short deliberation left pending waits its bound again (`taken_turn`).
    The decision model unavailable, the bound alone decides.

    A SUGGESTION IS ASKED ONLY ABOUT THE BEATS AFTER THE ONES IT WAS WRITTEN
    FROM (review R3-4, 2026-10-08): those through its `filed_turn`, the
    newest beat its pass read. Asked of the beats its own `why_now`
    describes, the answer confirmed itself, and the suggestion was judged a
    beat after it was filed. Suggestions with the same unread beats share one
    request. The beats count as read only once every request about them was
    answered (review R3-6): one the decision model could not answer is asked
    again with the next."""
    from core.jobs import is_cancelled
    from story.mandates import beats_per_proposal
    from story.room_proposals import (awaits_planner, direction_wait_beats,
                                      mark_due, proposals, record_follow_up,
                                      waited_beats)
    waiting = [p for p in proposals(cid, frame_id)
               if awaits_planner(p) and not p["due"]]
    reasons = {}
    if waiting:
        wait = direction_wait_beats(beats_per_proposal(cid, frame_id, beat))
        fresh = []
        for p in waiting:
            if waited_beats(cid, frame_id, p, beat) >= wait:
                reasons[p["uid"]] = "waited"
            elif p["taken_turn"] is None:
                fresh.append(p)
        stream = _unread_stream(cid, frame_id, beat, job) if fresh else []
        passages = {}
        for p in fresh:
            after = tuple(b["beat"] for b in stream if b["beat"] > p["filed_turn"])
            if after:
                passages.setdefault(after, []).append(p)
        answered = bool(passages)
        for after, asked in passages.items():
            neared = directions_neared(cid, asked,
                                       [b for b in stream if b["beat"] in after])
            if neared is None:
                answered = False
                continue
            report.setdefault("neared", {}).update(neared)
            for uid, share in neared.items():
                if share >= DIRECTION_NEAR_FLOOR:
                    reasons[uid] = "touched"
        if passages:
            report["decision"] = "asked" if answered else "unavailable"
        if answered and not is_cancelled(job):
            record_follow_up(cid, frame_id, stream[-1]["beat"])
    if is_cancelled(job):
        return
    if reasons:
        marked = set(mark_due(cid, frame_id, reasons))
        report.setdefault("due", {}).update(
            {uid: why for uid, why in reasons.items() if uid in marked})


def run_direction_follow_up(cid, frame_id, *, base_turn=None, job=None):
    """THE LAZY DIRECTION FOLLOW-UP (owner, 2026-10-08: "Can we do lighter
    weight planning potentially? And save heavy plans for when the actors
    near them?"). The Dramaturge suggests on its pacing; the Planner's
    deliberation -- six calls and more -- waits until the story nears what
    a suggestion is about. Queued at each commit of the player's frame
    while a suggestion is pending (`follow_up_wanted`), it asks the decision
    model, of the beats it has not read yet, whether they bring the story
    to each suggestion not yet deliberated (`directions_neared`), and judges
    the ones they do. NOTHING IS DROPPED: a suggestion that has waited
    `DIRECTION_WAIT_INTERVALS` pacing intervals is judged anyway, and so is
    every one the decision model could not be asked about by then. A
    player's ask is never lazy: its pass marks what it filed due, and this
    judges it at once (`_dramaturge_pass`).

    Every deliberation runs here, one at a time, until nothing is due --
    whatever a commit or a player's ask made due while one ran is taken up
    when it finishes, and the beats that passed meanwhile are read then.
    Refuses when the story rewound under the job; stops at the story hour's
    spend (`mandates.spend_limits`), the due proposals waiting for the next
    commit. A cancelled job writes nothing more (`core.jobs.is_cancelled`).
    Returns a report: what was read and found due, and each deliberation's.

    BY WHAT IT READ (review R3-1): each round reads later beats than the one
    the job was queued from, and raises the job's read horizon before it
    does (`_unread_stream`, `deliberate`), so a restore that discards any
    beat a round read cancels it. One the restore spared finishes the
    deliberation it is in and starts no other (`core.jobs.spared`) unless the
    replayed beat's own commit joins it, which hands it that beat to read
    (`core.jobs.submit`); otherwise the next commit's follow-up reads it."""
    from core.jobs import is_cancelled, spared, story_rewound_past
    from story import room_conversation as room
    from story.mandates import spend_limits, surprise_dial
    from story.room_frontier import frame_turn_idx, spend_this_hour
    from story.room_proposals import due_proposals
    now = room.current_turn_idx(cid)
    if base_turn is not None and story_rewound_past(base_turn, now):
        return {"skipped": "rewound", "base_turn": base_turn, "turn": now}
    frame_id = _player_frame(cid, frame_id)
    report = {"deliberations": []}
    while not is_cancelled(job) and not spared(job):
        _mark_due_now(cid, frame_id, frame_turn_idx(cid, frame_id), report, job)
        due = due_proposals(cid, frame_id)
        if not due or is_cancelled(job) or spared(job):
            break
        # Read here, at the deliberation's door: its verdicts carry this beat,
        # and a restore keeps a refusal only when it was reached from beats
        # the restore keeps (`room_proposals.keep_spared`).
        now = room.current_turn_idx(cid)
        spend = spend_limits(cid, frame_id, now)
        if spend["calls_per_hour"] is not None \
                and spend_this_hour(cid, frame_id, now) >= spend["calls_per_hour"]:
            report["stopped"] = "spend_hour"
            break
        report["deliberations"].append(deliberate(
            cid, frame_id, due, base_turn=base_turn,
            dial=surprise_dial(cid, frame_id, now), turn_idx=now, job=job))
    if is_cancelled(job):
        report["cancelled"] = True
    elif spared(job):
        report["spared"] = True
    return report


# ---------------------------------------------------------------------------
# The fill job, the frontier, and the commit tail
# ---------------------------------------------------------------------------

def _fill_task(cid, frame_id, report):
    from world.planning_needs import open_planning_needs
    needs = open_planning_needs(cid, frame_id)[:FILL_NEEDS_PER_JOB]
    frontier = {"player_room": report.get("player_room"),
                "rooms_short": report.get("rooms_short"),
                "identities_short": report.get("identities_short"),
                "rooms_ahead": report.get("rooms_ahead"),
                # The furnished ground within reach: what a fill short of
                # rooms plans beyond (the card's THE FILL names it).
                "rooms_developed": report.get("rooms_developed") or [],
                "identities_ahead": report.get("identities_ahead"),
                "bodies_ahead": report.get("bodies_ahead") or {}}
    # Only when they say something: an exit into nothing is a room missing
    # now, and a room with no way out is why no room is short.
    for key in ("rooms_unheld", "rooms_unmeasured"):
        if report.get(key):
            frontier[key] = report[key]
    # THE STANDING PLACES THAT WANT A FAR LOOK, when the grants let the Room
    # write one: the nearest `room_sketch.SKETCH_LOOKS_CAP` of them, ids only
    # -- the loop reads any of them with its tools, and the sketch is handed
    # the same few (`room_sketch.looks_offered`).
    looks = _looks_listed(report) if _looks_asked(cid, frame_id, report) else None
    if looks:
        frontier["looks_wanted"] = looks
    return {"kind": "fill", "needs": needs, "frontier": frontier}


def _looks_asked(cid, frame_id, report, turn_idx=None):
    """Whether the fill gives places near the story their far looks: the
    frontier wants some (`room_frontier.looks_wanted`) and a standing grant
    lets the Room write one (`set_far_looks`). Without the grant they are
    nobody's question: the fill neither runs for them nor asks for a grant
    on their account -- the status row's ask stays the planting one."""
    if not report.get("looks_wanted"):
        return False
    try:
        from story.mandates import coverage
        return bool(coverage(cid, frame_id, ["set_far_looks"], turn_idx=turn_idx)["ok"])
    except Exception:
        return False


def _looks_listed(report):
    """The nearest places and parts of the map wanting a far look, as ids
    (a place's with its ground), at most `room_sketch.SKETCH_LOOKS_CAP` in
    all, parts of the map first."""
    from story.room_sketch import looks_offered
    offered = looks_offered(report.get("looks_wanted"))
    return ({"regions": [r["region"] for r in offered["regions"]],
             "places": [{"room": p["room"], "ground": p["ground"]}
                        for p in offered["places"]]}
            if offered["places"] or offered["regions"] else None)


def _fill_wanted(report, looks=False):
    """Whether the frontier report leaves a fill anything to answer: an open
    need, or a shortfall -- fewer planned rooms or people ahead than the
    frontier wants, or an exit into nothing (`room_frontier.frontier_report`)
    -- or, with ``looks`` (`_looks_asked`), standing places near the story
    that far eyes read by their ground alone (2026-10-09). A developed area
    with nothing open still wants one: planting ahead is the fill's standing
    work (owner ruling, 2026-10-08), and `room_frontier.fill_due` is what
    keeps an unchanged question from being asked every beat."""
    return bool(report.get("open_need_uids") or report.get("rooms_short")
                or report.get("identities_short") or looks)


def _signature(cid, frame_id, report, mandate_uids, turn_idx=None):
    """The fill's question for this report (`room_frontier.fill_signature`),
    with whether it gives far looks -- read the same way wherever a question
    is asked or filed, so the memo matches what was asked."""
    from story.room_frontier import fill_signature
    return fill_signature(report, mandate_uids,
                          looks=_looks_asked(cid, frame_id, report, turn_idx))


def _mandate_uids(cid, frame_id, turn_idx):
    from story.mandates import active_mandates
    return [m["uid"] for m in active_mandates(cid, frame_id, turn_idx)]


def _player_line_waiting(cid, frame_id):
    """Whether the newest line in the room's thread is the player's: an ask
    nobody has answered yet, which only the full loop -- the one that reads
    the thread -- can answer. A thread that cannot be read is no ask."""
    from story import room_conversation as room
    try:
        rows = room.messages(cid, frame_id, limit=1)
    except Exception:
        return False
    return bool(rows) and rows[-1]["role"] == "player"


def _planting_only(cid, frame_id, report):
    """THE SKETCH'S QUESTION: planting ahead and nothing else -- no need
    open and no player's line waiting. Everything else is the full loop's
    (owner, 2026-10-08: the full loop is kept for open needs, the player's
    asks and accepted directions; a Dramaturge direction is its own job)."""
    return (not report.get("open_need_uids")
            and not _player_line_waiting(cid, frame_id))


def _needs_answered(cid, frame_id, package_uids):
    """The planning needs the packages a fill published answered or closed
    (`plot_packages.operation_needs`) -- what the hour's needs line counts,
    never what a fill merely carried (review 2026-10-08, R2-2)."""
    from story.plot_packages import get_package, operation_needs
    out = []
    for uid in package_uids or ():
        try:
            pkg = get_package(cid, uid, frame_id=frame_id) or {}
        except Exception:
            continue
        for op in pkg.get("operations") or ():
            for need in sorted(operation_needs(op)):
                if need not in out:
                    out.append(need)
    return out


def _only_looks(cid, frame_id, package_uids):
    """Whether every package a fill published only gave standing places
    their far looks (`plot_packages.set_far_looks`): planted nothing and
    answered no need. Read off the packages as filed, whichever tier filed
    them -- the sketch's or the full loop's -- so the hour's rule is one rule
    (review 2026-10-09, F2: the loop's looks-only pass was counted against
    planting's hour and the sketch's was not). False for no package, or for
    one that cannot be read."""
    from story.plot_packages import get_package
    if not package_uids:
        return False
    for uid in package_uids:
        try:
            ops = (get_package(cid, uid, frame_id=frame_id) or {}).get("operations") or ()
        except Exception:
            return False
        if not ops or any(not isinstance(op, dict) or op.get("op") != "set_far_looks"
                          for op in ops):
            return False
    return True


def _record_landed_fill(cid, frame_id, turn_idx, published, needs):
    """Count one fill that landed against the hour's line (`room_frontier.
    record_fill`) -- except a pass that only described what stands
    (`_only_looks`, 2026-10-09). It planted nothing, so counted it would
    spend the hour the world's growth runs on, and on a slow clock that is
    every planting the story gets. A number the player STATED is the total
    of every fill (owner, 2026-10-08), so under one it counts too."""
    from story.mandates import fill_limit_stated
    from story.room_frontier import record_fill
    if _only_looks(cid, frame_id, published) \
            and not fill_limit_stated(cid, frame_id, turn_idx):
        return False
    record_fill(cid, frame_id, turn_idx=turn_idx, package_uid=published[0],
                needs=needs)
    return True


def _restate_status(cid, frame_id, turn_idx):
    """Rewrite the status row as it stands, so what is in motion counts a
    package the room just filed outside a reply. The line and the questions
    are kept as they are; never raises."""
    from story import room_conversation as room
    try:
        current = room.status(cid, frame_id)
        write_status(cid, frame_id, line=current.get("line"),
                     questions=[qn["text"] for qn in current.get("questions") or []],
                     turn_idx=turn_idx)
    except Exception as exc:
        logger.info("room status not restated for chat %s: %s", cid, exc)


def run_fill(cid, frame_id, *, base_turn, job=None):
    """Answer what the deterministic fill could not, through a package,
    under the identity-fill mandate. Refuses when the story rewound under
    the job.

    TWO TIERS (owner, 2026-10-08). A planting-only question -- no need open,
    no player's line waiting (`_planting_only`) -- is asked as ONE compact
    call, the sketch (`story/room_sketch.run_sketch`), which files light
    plans through one package. Everything else, and every question the
    sketch hands on -- it said so, its answer could not be read, code
    refused what it planned, its package did not validate, or the frontier
    is short of something the grants keep from a sketch -- runs the full
    loop in passes (`_run_task`) exactly as before, its task carrying the
    reason under "escalated". Each pass reads the frontier and the open
    needs afresh, and the reply is kept in the thread as the Planner's own
    line.
    A cancelled ``job`` -- a restore cancels the fill as it cancels a
    Dramaturge pass (review F2, 2026-10-08) -- writes nothing: no answer for
    the back-off, no fill record, no line."""
    from core.jobs import is_cancelled, story_rewound_past
    from story import room_conversation as room
    from story.room_frontier import (frame_turn_idx, frontier_report,
                                     record_fill_asked, record_spend)
    now = room.current_turn_idx(cid)
    if story_rewound_past(base_turn, now):
        return {"skipped": "rewound", "base_turn": base_turn, "turn": now}
    report = frontier_report(cid, frame_id)
    if not _fill_wanted(report, _looks_asked(cid, frame_id, report, now)):
        return {"skipped": "nothing short"}
    mandate_uids = _mandate_uids(cid, frame_id, now)
    # THE QUESTION THIS FILL WAS ASKED, read where the task was built, so the
    # memo files the answer against exactly what the Room was shown.
    signature = _signature(cid, frame_id, report, mandate_uids, now)
    # A NEED FILED WHILE THE FILL RUNS JOINS ITS NEXT PASS. The fill holds
    # the chat's one fill slot (`FILL_JOB_KEY`, deduped per chat), so a
    # commit that files a need while a planting fill runs JOINS that fill
    # rather than queueing the need's own -- and every pass used to carry
    # the task as the fill began, with no needs: the review's probe
    # (2026-10-08) saw the tasks [[], [need]] across two jobs and the need
    # first asked a beat late, and a fill as long as the Brackwater run's
    # longest (29 minutes) holds one about three beats. So each pass reads
    # the open needs afresh, and every question a pass was asked goes into
    # the memo with the answer, so the next commit does not ask it again at
    # once. A pass is walled at `TASK_PASS_SECONDS`, so a fill longer than
    # one pass reaches its next pass within that; a fill that ends in its
    # first pass -- a sketch has no second -- has no next one, and a need
    # filed under it is asked at the first commit after it ends.
    #
    # EACH PASS RE-MEASURES THE FRONTIER TOO (review 2026-10-08, R2-3). Its
    # question was built with the frontier the fill BEGAN with, so a pass-1
    # publication that moved the shortfall left the memo holding a question
    # the next commit no longer asked: the need a later pass had just
    # declined was asked again at once, about seventeen calls for nothing.
    # And the question the next commit WILL ask -- the frontier as the fill
    # left it -- is filed with the answer as well, when every need open then
    # is one a pass carried, so a need filed in the last moments is still
    # asked at once.
    asked, carried_needs = [], []

    def _ask(question):
        if question not in asked:
            asked.append(question)

    def _each_pass(carried):
        fresh = frontier_report(cid, frame_id)
        carried.update(_fill_task(cid, frame_id, fresh))
        _ask(_signature(cid, frame_id, fresh, mandate_uids, now))
        for need in carried["needs"]:
            if need["uid"] not in carried_needs:
                carried_needs.append(need["uid"])

    def _asked(published):
        # Filed at the beat the answer CAME, not the beat that queued it: a
        # fill runs for several beats, and the back-off counts from the
        # answer. A story that rewound under the job answered nothing the
        # timeline it is now in asked. THIS frame's newest beat, never a
        # live bubble's row above it (`room_frontier.frame_turn_idx`).
        end = frame_turn_idx(cid, frame_id)
        if story_rewound_past(base_turn, end):
            return
        try:
            left = frontier_report(cid, frame_id)
            if set(left.get("open_need_uids") or ()) <= set(carried_needs):
                _ask(_signature(cid, frame_id, left, mandate_uids, now))
        except Exception as exc:
            logger.info("room fill: the frontier it left was not measured: %s", exc)
        for question in asked or [signature]:
            record_fill_asked(cid, frame_id, question, turn_idx=end,
                              published=published)

    escalated = ""
    if _planting_only(cid, frame_id, report):
        from story.room_sketch import SKETCH_ESCALATE_CHARS, run_sketch
        _ask(signature)
        try:
            sketch = run_sketch(cid, frame_id, report, role=PLANNER_ROLE,
                                actor=PLANNER_ACTOR, base_turn=base_turn,
                                job=job, turn_idx=now)
        except Exception:
            if not is_cancelled(job):
                _asked(False)
            raise
        if sketch["calls"]:
            record_spend(cid, frame_id, turn_idx=now, calls=sketch["calls"],
                         who="sketch")
        if sketch["stopped"] in ("rewound", "cancelled") or is_cancelled(job):
            # A CANCEL THAT LANDS AFTER THE SKETCH'S LAST LOOK is the full
            # loop's case below, met the same way: nothing filed for the
            # back-off, no fill record, no line.
            return {"tier": "sketch", "published": [], "calls": sketch["calls"],
                    "steps": sketch["calls"],
                    "stopped": sketch["stopped"] or "cancelled", "passes": 0}
        if not sketch["escalate"]:
            published = sketch["published"]
            _asked(bool(published))
            if published:
                # A sketch answers no need -- it runs only when none is open
                # -- so its fill counts on the planting line alone, and a
                # pass that only gave standing places their far looks not at
                # all unless the player stated a number (`_record_landed_fill`).
                _record_landed_fill(cid, frame_id, now, published, ())
                _restate_status(cid, frame_id, now)
            try:
                room.add_message(cid, frame_id, "planner", sketch["reply"],
                                 turn_idx=now)
            except ValueError:
                pass
            return {"tier": "sketch", "published": published,
                    "calls": sketch["calls"], "steps": sketch["calls"],
                    "stopped": None, "passes": 0, "event": sketch["event"],
                    "notes": sketch["notes"]}
        escalated = sketch["escalate"][:SKETCH_ESCALATE_CHARS]
        logger.info("room fill for chat %s: the sketch handed the question "
                    "to the full planner: %s", cid, escalated)
    task = _fill_task(cid, frame_id, report)
    if escalated:
        task["escalated"] = escalated
    try:
        out = _run_task(cid, frame_id, task, base_turn=base_turn, job=job,
                        before_pass=_each_pass)
    except Exception:
        # A fill that failed (the provider refused, the credit ran out) is an
        # empty answer for the back-off: re-asking on the very next commit is
        # what a dead provider makes expensive.
        if not is_cancelled(job):
            _asked(False)
        raise
    if is_cancelled(job) or out["stopped"] == "cancelled":
        return {"published": out["published"], "calls": out["calls"],
                "steps": out["steps"], "stopped": "cancelled",
                "passes": out.get("passes", 1)}
    if out["stopped"] != "rewound":
        _asked(bool(out["published"]))
    if out["published"]:
        # The same rule as the sketch's: a pass whose every package only gave
        # far looks is not counted against planting's hour (`_record_landed_fill`).
        _record_landed_fill(cid, frame_id, now, out["published"],
                            _needs_answered(cid, frame_id, out["published"]))
    try:
        room.add_message(cid, frame_id, "planner", out["reply"], turn_idx=now)
    except ValueError:
        pass
    return {"tier": "escalated" if escalated else "loop",
            **({"escalated": escalated} if escalated else {}),
            "published": out["published"], "calls": out["calls"],
            "steps": out["steps"], "stopped": out["stopped"],
            "passes": out.get("passes", 1)}


#: The lines the commit tail asks for a fill grant with; the status row
#: carries at most the one that is true (`_say_what_waits_on_a_grant`).
GRANT_WAITING_LINES = (WAITING_LINE, WAITING_TO_PLANT_LINE)


def _say_what_waits_on_a_grant(cid, frame_id, turn_idx, line):
    """THE STATUS ROW SAYS WHAT WAITS ON A FILL GRANT, AND ONLY WHILE IT DOES.
    ``line`` is the one true at this commit -- `WAITING_LINE` while a need
    is open, `WAITING_TO_PLANT_LINE` while only the frontier is short, None
    while a grant is held or nothing is wanted -- and the row is made to
    carry exactly it: the other is withdrawn, the true one is said once,
    AHEAD of every question the Room asked itself, and those stay in their
    order behind it. Said last, it was cut by the row's own cap
    (`STATUS_QUESTIONS_CAP`) whenever the Room already had that many
    questions standing, and with them standing it was never said at all
    (probe 2026-10-08; the Dramaturge lane's review found the same of
    `WAITING_LINE`).

    The row used to be given `WAITING_LINE` whenever a fill was wanted with
    no grant, so once planting ahead was restored it told the player -- and
    the Room, which reads the row back as its own `status` -- that planning
    needs were open in every developed area and chartered town that had
    none (review, 2026-10-08: chat 114 beats 0-4, no need open), and a line
    once written stood until the Planner next wrote the row, whatever had
    become true since. Written only when the row changes. Never raises: the
    row is what the room SAYS, and the commit tail settles it before it
    queues the fill, which a failed read here must not cost.

    THE LINE IS THE ENGINE'S ASK (`ask_question`'s terms, the Dramaturge
    lane's review E): it stands as ``source`` "engine", so the row's own
    sort keeps it ahead of the Room's questions and a reply that restates it
    leaves it the engine's to withdraw. A copy under any other source is
    taken off with it -- these words are the engine's alone, and a row
    written before the asks carried a source holds them as a plain
    question."""
    from core.db import transaction
    from story import room_conversation as room
    try:
        with transaction():
            current = room.status(cid, frame_id)
            standing = current.get("questions") or []
            kept = [q for q in standing
                    if q["text"] not in GRANT_WAITING_LINES
                    or (q["text"] == line and q["source"] == "engine")]
            if line and not any(q["text"] == line for q in kept):
                kept.insert(0, {"text": line, "source": "engine"})
            if [(row["text"], row["source"]) for row in _question_rows(kept)] \
                    != [(q["text"], q["source"]) for q in standing]:
                write_status(cid, frame_id, line=current.get("line"),
                             questions=kept, turn_idx=turn_idx)
    except Exception as exc:
        logger.info("room status not settled for chat %s: %s", cid, exc)


def schedule_room_work(ctx):
    """From the commit tail: measure the frontier and queue what is due --
    a fill when something is short or a need is open, under an
    identity-fill grant with room in the hour, and only when what it would
    answer has changed since a fill last answered it or the back-off has run
    (`room_frontier.fill_due`) -- the fill itself picks its tier, a sketch
    for planting ahead and the full loop for the rest (`run_fill`); a
    Dramaturge pass whenever the frame has played `beats_per_proposal` of
    its own beats since the last one (`room_proposals.pass_due`; a pacing of
    0 is off) or a player's ask is waiting, while the hour's spend is open --
    no grant needed to suggest, never from a live bubble; the direction
    follow-up while a suggestion is pending (`follow_up_wanted`), which
    judges the ones the story has come near; a bible fold when a batch of
    thread lines has aged past the window. With no fill grant the engine
    asks for one on the status row, naming what waits on it, ahead of every
    model question, and withdraws the ask once a grant arrives or nothing is
    wanted (`_say_what_waits_on_a_grant`). Never raises; returns the first
    job queued, or None."""
    from core import jobs
    from persist.llm_capture import room_capture
    from story.mandates import (beats_per_proposal, fill_limit,
                                fill_limit_stated, spend_limits)
    from story.room_bible import schedule_fold
    from story.room_frontier import (fill_due, fills_this_hour,
                                     frontier_report, record_measure,
                                     spend_this_hour)
    from story.room_proposals import briefs_due, pass_due
    from world.spatial_frames import is_bubble_frame
    cid = ctx.chat.id
    frame_id = getattr(ctx.turn, "frame_id", None)
    turn_idx = getattr(ctx.turn, "idx", None)
    # A LIVE BUBBLE'S COMMIT NEITHER MEASURES NOR FILLS. Its scene is cut down
    # to its own subjects, so the frontier read "the player stands in no
    # room", filed that measure over the era's shared row, and asked the
    # era's open needs under a second signature with a back-off of its own
    # (review, 2026-10-08). The player frame's next commit reads the same
    # needs and grants. Nor does it queue a Dramaturge pass (below); the
    # fold is unchanged.
    try:
        bubble = bool(frame_id) and is_bubble_frame(cid, frame_id)
    except Exception:
        bubble = False
    report = {} if bubble else frontier_report(cid, frame_id)
    if not bubble:
        record_measure(cid, frame_id, report, turn_idx=turn_idx)
    queued = []
    spend = spend_limits(cid, frame_id, turn_idx)
    hour_open = (spend["calls_per_hour"] is None
                 or spend_this_hour(cid, frame_id, turn_idx) < spend["calls_per_hour"])

    # FAR LOOKS ARE ASKED FOR ONLY UNDER THEIR GRANT, and never asked about:
    # the status row's ask for a fill grant stays planting's and the needs'
    # (`planting`), and looks only add to what a granted fill answers.
    planting = not bubble and _fill_wanted(report)
    looks = not bubble and _looks_asked(cid, frame_id, report, turn_idx)
    wanted = planting or looks
    limit = fill_limit(cid, frame_id, turn_idx) if wanted else None
    if not bubble:
        # THE ENGINE'S OWN ASK FOR A FILL GRANT, read again at every commit
        # of the player's frame: the line true now -- an open need, or the
        # frontier the room would plant -- asked ahead of every model
        # question so a full row cannot cut it, and withdrawn once a grant
        # arrives or nothing is wanted (`_say_what_waits_on_a_grant`).
        _say_what_waits_on_a_grant(
            cid, frame_id, turn_idx,
            None if not planting or limit is not None
            else WAITING_LINE if report.get("open_need_uids")
            else WAITING_TO_PLANT_LINE)
    if wanted and limit is not None:
        # A NUMBER THE PLAYER STATES IS THE TOTAL (owner, 2026-10-08):
        # planting ahead and open needs are held together to it, every
        # landed fill counted. With the engine's default the hour is held
        # per kind of question: a question carrying an open need counts
        # only the fills that answered needs, planting every fill that
        # landed, so planting never starves a need of the default hour
        # (`mandates.FILLS_PER_STORY_HOUR`, `room_frontier.fills_this_hour`).
        per_kind = not fill_limit_stated(cid, frame_id, turn_idx)
        if hour_open and fills_this_hour(
                cid, frame_id, turn_idx,
                needs_only=per_kind and bool(report.get("open_need_uids"))) < limit:
            # ASKED ONCE, THEN BACKED OFF. Measured on the Brackwater run
            # (chat 166): a fill was in flight at every kept commit from turn
            # 6 to 30 and the Room answered the same unchanged question with
            # "nothing to build" again and again. A changed question -- a new
            # need, a moved shortfall, a new grant, or a new room while a
            # need is open -- is asked at once; an unchanged one waits out
            # `fill_wait_beats`.
            due, why = fill_due(cid, frame_id, _signature(
                cid, frame_id, report, _mandate_uids(cid, frame_id, turn_idx),
                turn_idx), turn_idx)
            if not due:
                logger.info("room fill not queued for chat %s: the question "
                            "is unchanged (%s)", cid, why)
            else:
                def _fill(job):
                    # ARMED INSIDE THE JOB, not around the submit.
                    # `core/jobs.py` clears turn-scoped contextvars by design
                    # and this body runs outside any reply, so a scope set
                    # here is the only one the calls below can see
                    # (`persist/llm_capture.room_capture`).
                    with room_capture(cid, "fill"):
                        return run_fill(cid, frame_id, base_turn=turn_idx,
                                        job=job)
                queued.append(jobs.submit(cid, FILL_JOB_KEY, _fill,
                                          base_turn=turn_idx))

    # THE DRAMATURGE'S TURN COMES ON PACING ALONE (owner, 2026-10-08): every
    # `beats_per_proposal` beats of this frame's own play, with no grant --
    # the dial a grant names only tunes how inventive it is -- and under the
    # same spend stop as the fill. Never from a live bubble's commit: its
    # stream is empty (no player line, no narration) and the pacing row it
    # would stamp is the era's (review, 2026-10-08). A pacing of 0 is off
    # (`room_proposals.pass_due`). AN ASK STILL WAITING IS DUE AT ONCE,
    # pacing or none: the pass it joined was cancelled before it answered
    # (`planner_reply`, review F1) -- unless a pass took it and its provider
    # failed, when it waits a pacing interval (`briefs_due`, review R3-7).
    if not bubble and hour_open and turn_idx is not None:
        pace = beats_per_proposal(cid, frame_id, turn_idx)
        due, _why = pass_due(cid, frame_id, turn_idx, pace)
        if not due and briefs_due(cid, frame_id, turn_idx, pace):
            due = True
        if due:
            def _pass(job):
                with room_capture(cid, "dramaturge"):
                    return run_dramaturge_pass(cid, frame_id,
                                               base_turn=turn_idx, job=job)
            queued.append(jobs.submit(cid, DRAMATURGE_JOB_KEY, _pass,
                                      base_turn=turn_idx))

    # THE DIRECTION FOLLOW-UP, at every commit of the player's frame while a
    # suggestion is pending (owner, 2026-10-08: "save heavy plans for when
    # the actors near them"): one decision-model question per suggestion
    # against the beat, and the deliberation for the ones it nears, or that
    # have waited their bound (`run_direction_follow_up`). Out of band like
    # the pass, so the beat never waits on the question; under the same
    # spend stop; never from a live bubble's commit, whose stream is empty.
    if not bubble and hour_open and turn_idx is not None \
            and follow_up_wanted(cid, frame_id, turn_idx):
        queued.append(_queue_follow_up(cid, frame_id, turn_idx))

    fold = schedule_fold(cid, frame_id, window=PLANNER_HISTORY_MESSAGES,
                         base_turn=turn_idx)
    if fold is not None:
        queued.append(fold)
    return queued[0] if queued else None
