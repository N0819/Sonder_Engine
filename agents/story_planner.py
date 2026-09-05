"""The Story Planner: the Writers' Room's author, seated on the panel's seam.

NOT A PIPELINE STAGE. Nothing here runs inside a turn: the Planner answers
the player's line in the room panel (`story/room_conversation.PLANNER`) and
runs the out-of-band jobs the commit tail schedules -- the fill, the
Dramaturge pass, the bible fold. At rest it costs nothing (v2 § 10).

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
that outlives them is returned to the player, never forced.

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

import hashlib
import json
import re
import time

from core.logging_utils import logger

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
#: Output budget per model call. Raised to 20k on the owner's ruling
#: (2026-09-04): every response cap the room owns is the same number, so a
#: step that needs room has it and no single call is the one that truncates.
#: Measured on GLM 5.2 (chat 111, 2026-09-03): one step drafting a whole
#: package ran past 4000 tokens and its truncated JSON parsed as nothing --
#: which is what a cap costs when it binds, and why the loop reports a cut-off
#: rather than reading it as "done" (CUT_OFF_NOTE).
PLANNER_MAX_TOKENS = 20_000
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
#: Charter Planner delegations per reply and their output budget.
CHARTER_PLANNER_CALLS_PER_REPLY = 1
CHARTER_PLANNER_MAX_TOKENS = 20_000
#: The pseudo-tool the model names to delegate; not in the facade table.
CHARTER_PLANNER_TOOL = "charter_planner"
#: Open needs one fill job hands the Planner.
FILL_NEEDS_PER_JOB = 3
#: The job keys (`core/jobs.py`), deduped per chat.
FILL_JOB_KEY = "story_planner_fill"
DRAMATURGE_JOB_KEY = "dramaturge_pass"
#: Questions the status row keeps.
STATUS_QUESTIONS_CAP = 6
#: Deliberation rounds between the Planner and the Dramaturge before a
#: disagreement is returned to the player (v2 § 6.3).
DELIBERATION_ROUNDS = 2

#: The keys an answer may carry. An output carrying none of them is not an
#: answer -- almost always one cut off at the token ceiling -- and is told so.
ANSWER_KEYS = ("calls", "reply", "grants", "questions", "status_line",
               "verdicts", "to_dramaturge")
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
SILENT_LINE = ("The room finished without a word; what it settled stands, and "
               "its status line says what is in motion.")
WAITING_LINE = ("The room has open planning needs and no grant to answer "
                "them. Tell the Story Planner what it may prepare.")
REWOUND_LINE = "The story rewound under the room's work; nothing landed."
#: What the reply says when a stop is a spend stop, keyed by stop reason.
STOP_LINES = {"steps": BOUNDED_LINE, "calls": BOUNDED_LINE, "wall": BOUNDED_LINE,
              "spend_reply": SPENT_LINE, "spend_hour": HOUR_SPENT_LINE,
              "rewound": REWOUND_LINE}
#: Stops after which a background task resumes in its next pass.
RESUMABLE_STOPS = ("steps", "calls", "wall")


# ---------------------------------------------------------------------------
# The model call
# ---------------------------------------------------------------------------

def _call(system, payload, *, max_tokens):
    """One JSON-shaped call on the Planner's role. Read through the
    provider module at call time so a test seals or stubs one name."""
    from agents.common import jparse
    from llm import providers
    raw = providers.chat_complete(
        PLANNER_ROLE, system, json.dumps(payload, ensure_ascii=False),
        json_mode=True, max_tokens=max_tokens)
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


def system_block(cid, frame_id):
    from llm.prompts import get_prompt
    return get_prompt("story_planner") + _tools_block() + _bible_block(cid, frame_id)


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def _shown_transcript(transcript, cap=None):
    """What the model is shown of its own tool results, within ``cap``
    characters. Returns ``(shown, whole)``: the entries in order, and the
    set of indices INTO ``shown`` whose result is untrimmed.

    THE ORDER OF SACRIFICE. A result the model has already read is worth
    less than one it has not, and a head is worth more than an absence, so:
    (1) the largest result from a step the model has read is cut to a head
    of `PLANNER_TRIM_HEAD_CHARS` plus a `trimmed` count; (2) then the
    heads it has already read go, oldest first (measured on chat 114 after
    the first cut: seven read heads still crowded out the dump the model
    had just asked for); (3) then the largest of the newest step, which the
    model has not read yet -- only when that step alone outgrows the cap;
    (4) only then are whole entries evicted, oldest first. Under the old
    rule (whole entries, newest first) one dump evicted every neighbour it
    had just read (chat 114 step 5, 2026-09-04)."""
    cap = PLANNER_TRANSCRIPT_CHARS if cap is None else cap
    entries = [dict(e) for e in transcript]
    sizes = [len(_encoded(e)) for e in entries]
    kept = list(range(len(entries)))
    trimmed = set()
    latest = max((int(e.get("step") or 0) for e in entries), default=0)

    def _read(i):
        return int(entries[i].get("step") or 0) < latest

    def _trim(i):
        encoded = _encoded(entries[i].get("result"))
        entries[i]["result"] = {"head": encoded[:PLANNER_TRIM_HEAD_CHARS],
                                "trimmed": len(encoded) - PLANNER_TRIM_HEAD_CHARS}
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
             seconds_left, turn_idx, spend=None, regime="reply"):
    from story import room_conversation as room
    from story.mandates import (MANDATE_CAPABILITIES, MANDATE_LIMITS,
                                active_mandates, revoked_since)
    from story.plot_packages import list_packages
    from story.room_frontier import frontier_report
    from story.room_proposals import pending_proposals
    from story.room_tools import cast_minds_summary, run_tool
    shown, _whole = _shown_transcript(transcript)
    try:
        clock = run_tool(cid, "inspect_clock", frame_id=frame_id)
    except Exception:
        clock = {}
    try:
        frontier = frontier_report(cid, frame_id)
    except Exception as exc:
        frontier = {"error": str(exc)[:200]}
    # One line per cast member -- the drive's essence and each held project's
    # aim -- so the Planner knows what `inspect_minds` would answer before it
    # reaches (measured 2026-09-04 on chat 114: 136 characters for the one
    # cast member). Author knowledge; the seam that reads it is this loop
    # and nothing a mind is shown (`tests/test_room_minds.py`).
    try:
        minds = cast_minds_summary(cid, frame_id)
    except Exception as exc:
        minds = [{"error": str(exc)[:200]}]
    payload = {
        "story": _story(cid),
        "clock": clock,
        "minds": minds,
        "conversation": _conversation(cid, frame_id),
        "mandates": active_mandates(cid, frame_id, turn_idx),
        "withdrawn": [{"uid": m["uid"], "text": m["text"], "status": m["status"]}
                      for m in revoked_since(cid, frame_id, max(0, turn_idx - 1))],
        "capabilities": list(MANDATE_CAPABILITIES),
        "limits": list(MANDATE_LIMITS),
        "status": room.status(cid, frame_id),
        "frontier": frontier,
        "packages": list_packages(cid, frame_id=frame_id),
        "pending_proposals": [
            {"uid": p["uid"], "kind": p["kind"], "title": p["title"],
             "status": p["status"]} for p in pending_proposals(cid, frame_id)],
        "transcript": shown,
        "budget": {"regime": regime, "step": step,
                   "steps": PLANNER_STEPS_PER_REPLY,
                   "calls_left": calls_left,
                   "seconds_left": round(max(0.0, seconds_left), 1),
                   **({"spend": spend} if spend else {})},
    }
    if text is not None:
        payload["player_says"] = text
    if task is not None:
        payload["task"] = task
    return payload


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
                expires_turn=raw.get("expires_turn"), turn_idx=turn_idx))
        except (ValueError, TypeError) as exc:
            notes.append("grant not recorded: %s" % str(exc)[:200])
    return rows, notes


def _question_rows(questions):
    out = []
    for text in questions if isinstance(questions, list) else []:
        text = " ".join(str(text or "").split())[:600]
        if not text:
            continue
        out.append({"uid": "q_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8],
                    "text": text})
    return out[:STATUS_QUESTIONS_CAP]


def write_status(cid, frame_id, *, line=None, questions=None, turn_idx=None):
    """The spoiler-safe projection the panel shows: what is in motion,
    never what it is. Built from package PROJECTIONS -- a title, a status --
    the pending proposals' kind and title, and the questions the room is
    asking. A sealed package's title is the Planner's to keep spoiler-safe;
    nothing else of it is read here."""
    from core.db import wset_for_frame
    from story import room_conversation as room
    from story.plot_packages import list_packages
    from story.room_proposals import pending_proposals, projection
    in_motion = []
    for proj in list_packages(cid, frame_id=frame_id):
        if proj["status"] in ("draft", "validating", "published", "active"):
            in_motion.append({"uid": proj["uid"], "kind": "package",
                              "label": proj["title"], "state": proj["status"]})
    for prop in pending_proposals(cid, frame_id):
        in_motion.append(projection(prop))
    line = " ".join(str(line or "").split())
    if not line:
        line = room.status(cid, frame_id).get("line") if in_motion else ""
        line = line or NO_STATUS_LINE
    row = {"line": line[:400], "in_motion": in_motion,
           "questions": _question_rows(questions),
           "updated_turn": int(turn_idx or room.current_turn_idx(cid))}
    wset_for_frame(cid, room.ROOM_STATUS_KEY, row, frame_id)
    return room.status(cid, frame_id)


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
                max_tokens=CHARTER_PLANNER_MAX_TOKENS)
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


def run_planner(cid, frame_id, *, text=None, task=None, base_turn=None,
                regime=None, on_event=None):
    """One bounded reply. ``text`` is the player's line (the interactive
    regime); ``task`` a brief from a job (the background regime; no grants
    are read from a task). Returns ``{"reply", "dramaturge": None,
    "mandates", "status", "published": [uids], "verdicts": [...],
    "ask_dramaturge": str|None, "calls": n, "steps": n, "notes": [...],
    "stopped": why|None, "regime"}``.

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
    from core.jobs import story_rewound_past
    from story import room_conversation as room
    from story.mandates import expire_mandates, spend_citation, spend_limits
    from story.room_frontier import record_spend, spend_this_hour
    from story.room_tools import TOOL_INDEX, ToolError, run_tool

    def _call_key(name, args):
        return name + "\x00" + json.dumps(args, sort_keys=True, ensure_ascii=False,
                                          default=str)

    regime = regime or ("task" if task is not None and text is None else "reply")
    wall = REPLY_WALL_SECONDS if regime == "reply" else TASK_PASS_SECONDS
    system = system_block(cid, frame_id)
    turn_idx = room.current_turn_idx(cid)
    expire_mandates(cid, frame_id, turn_idx)
    spend = spend_limits(cid, frame_id, turn_idx)
    reply_cap = min(PLANNER_TOOL_CALLS_PER_REPLY, int(spend["calls_per_reply"]))
    hour_left = max(0, int(spend["calls_per_hour"])
                    - spend_this_hour(cid, frame_id, turn_idx))
    started = time.time()
    transcript, notes, published, verdicts = [], [], [], []
    calls_made, delegations, steps = 0, 0, 0
    reply, status_line, questions, ask_dramaturge = "", "", [], None
    stopped = None
    # THE ECHO POLICY. `answered` maps a call (tool + arguments) to the index
    # of the transcript entry that last showed its result in full; a repeat
    # whose answer is unchanged and still in the model's view is echoed as
    # the step to look at, never a second copy. `in_view` is what the model
    # saw whole in the payload it just read, plus what this step appended.
    answered, in_view = {}, set()
    if hour_left <= 0:
        stopped = "spend_hour"
    for step in range(1, PLANNER_STEPS_PER_REPLY + 1):
        if stopped:
            break
        _emit({"type": "room_step", "step": step,
               "calls_made": calls_made, "seconds": round(time.time() - started, 1)})
        seconds_left = wall - (time.time() - started)
        if seconds_left <= 0:
            stopped = "wall"
            break
        steps = step
        calls_left = max(0, min(reply_cap - calls_made, hour_left - calls_made))
        out = _call(system, _payload(
            cid, frame_id, text=text, task=task, transcript=transcript,
            step=step, calls_left=calls_left, seconds_left=seconds_left,
            turn_idx=turn_idx, regime=regime,
            spend={"calls_per_reply": reply_cap, "calls_per_hour_left": hour_left}),
            max_tokens=PLANNER_MAX_TOKENS)
        shown, whole = _shown_transcript(transcript)
        first_shown = len(transcript) - len(shown)
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
        if out.get("status_line"):
            status_line = str(out["status_line"])
        if isinstance(out.get("questions"), list):
            questions = out["questions"]
        if out.get("reply"):
            reply = str(out["reply"])
        if isinstance(out.get("verdicts"), list):
            verdicts = [v for v in out["verdicts"] if isinstance(v, dict)]
        if text is not None and out.get("to_dramaturge"):
            ask_dramaturge = " ".join(str(out["to_dramaturge"]).split())[:1200]
        # PROGRESS IS VISIBLE: the status row is rewritten every step, so
        # the panel's one-second watch shows a long reply working.
        if regime == "reply" and status_line:
            write_status(cid, frame_id, line=status_line, questions=questions,
                         turn_idx=turn_idx)
        calls = out.get("calls") if isinstance(out.get("calls"), list) else []
        if not calls:
            break
        for call in calls[:PLANNER_TOOL_CALLS_PER_STEP]:
            if calls_made >= PLANNER_TOOL_CALLS_PER_REPLY:
                stopped = "calls"
                break
            if calls_made >= reply_cap:
                stopped = "spend_reply"
                break
            if calls_made >= hour_left:
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
                if name in ("publish_package", "resolve_package"):
                    _note_bible(cid, frame_id, name, args, result, turn_idx)
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
    status = write_status(cid, frame_id, line=status_line, questions=questions,
                          turn_idx=turn_idx)
    return {"reply": reply, "dramaturge": None,
            "mandates": room.mandates(cid, frame_id), "status": status,
            "published": published, "verdicts": verdicts,
            "ask_dramaturge": ask_dramaturge, "calls": calls_made,
            "steps": steps, "notes": notes, "stopped": stopped, "regime": regime}


def _run_task(cid, frame_id, task, *, base_turn, job=None):
    """A background task: passes of `run_planner` in the task regime until
    the reply is done, a pass ends on a non-resumable stop, the passes cap
    is reached, or the job is cancelled. Spend per hour is checked by each
    pass; the wall is per pass. The passes so far ride the task so the
    model knows it is continuing."""
    passes, out = 0, None
    while passes < TASK_PASSES_CAP:
        cancelled = getattr(job, "cancelled", None)
        if cancelled is not None and getattr(cancelled, "is_set", lambda: False)():
            break
        passes += 1
        carried = dict(task)
        if passes > 1:
            carried["resumed"] = {"pass": passes,
                                  "last_stopped": out["stopped"] if out else None,
                                  "published_so_far": list(out["published"]) if out else []}
        this = run_planner(cid, frame_id, task=carried, base_turn=base_turn,
                           regime="task")
        if out is None:
            out = this
        else:
            out = {**this,
                   "published": out["published"] + this["published"],
                   "calls": out["calls"] + this["calls"],
                   "steps": out["steps"] + this["steps"],
                   "notes": out["notes"] + this["notes"],
                   "verdicts": this["verdicts"] or out["verdicts"]}
        if this["stopped"] not in RESUMABLE_STOPS:
            break
    out["passes"] = passes
    return out


def planner_reply(cid, frame_id, text, *, on_event=None):
    """The seam's shape: what `room_conversation.PLANNER` returns. When the
    Planner hands a brief to the Dramaturge, the pass runs OUT OF BAND (a
    background task has no wall) and its lines land in the thread; the
    envelope's `dramaturge` stays None and the panel's watch shows them."""
    from core import jobs
    from story.mandates import surprise_dial
    from story.room_bible import schedule_fold
    out = run_planner(cid, frame_id, text=text, regime="reply",
                      on_event=on_event)
    if out.get("ask_dramaturge"):
        dial = surprise_dial(cid, frame_id)
        if dial is not None:
            brief = out["ask_dramaturge"]
            base = None

            def _run(job):
                return run_dramaturge_pass(cid, frame_id, base_turn=base,
                                           brief=brief, job=job)

            jobs.submit(cid, DRAMATURGE_JOB_KEY, _run, base_turn=base)
    try:
        schedule_fold(cid, frame_id, window=PLANNER_HISTORY_MESSAGES)
    except Exception as exc:
        logger.info("bible fold not scheduled: %s", exc)
    return {"reply": out["reply"], "dramaturge": None,
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
    Returns a report; every line of the exchange is stored in the thread."""
    from agents import dramaturge
    from story import room_conversation as room
    from story.room_proposals import (PENDING_STATUSES, get_proposal,
                                      judge_proposal, settle_proposal)
    turn_idx = room.current_turn_idx(cid) if turn_idx is None else int(turn_idx)
    uids = [p["uid"] for p in proposals if p.get("kind") != "quiet"]
    report = {"rounds": 0, "implemented": [], "refused": [], "withdrawn": [],
              "returned": [], "published": [], "calls": 0}
    for round_no in range(1, DELIBERATION_ROUNDS + 1):
        pending = [get_proposal(cid, frame_id, u) for u in uids]
        pending = [p for p in pending if p and p["status"] in PENDING_STATUSES]
        if not pending:
            break
        report["rounds"] = round_no
        task = {"kind": "deliberate", "round": round_no,
                "rounds": DELIBERATION_ROUNDS, "dial": int(dial),
                "proposals": [_proposal_brief(p) for p in pending]}
        out = _run_task(cid, frame_id, task, base_turn=base_turn, job=job)
        report["calls"] += out["calls"]
        report["published"].extend(out["published"])
        if out["reply"]:
            try:
                room.add_message(cid, frame_id, "planner", out["reply"],
                                 turn_idx=turn_idx)
            except ValueError:
                pass
        judged = set()
        for v in out["verdicts"]:
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
            judged.add(uid)
            if row["status"] == "implemented":
                report["implemented"].append(uid)
            elif row["status"] == "refused":
                report["refused"].append(uid)
            elif row["status"] == "revised":
                revised, note = dramaturge.revise(
                    cid, frame_id, row, row["judgements"][-1], dial=dial,
                    turn_idx=turn_idx)
                if note:
                    try:
                        room.add_message(cid, frame_id, "dramaturge", note,
                                         turn_idx=turn_idx)
                    except ValueError:
                        pass
                if revised and revised["status"] == "withdrawn":
                    report["withdrawn"].append(uid)
        # An accepted proposal with no package yet stays accepted: the
        # Planner said it is natural and is working it; nothing more to
        # deliberate. A pending proposal the Planner did not judge stays
        # pending for the next round.
    for uid in uids:
        p = get_proposal(cid, frame_id, uid)
        if p and p["status"] in PENDING_STATUSES:
            settle_proposal(cid, frame_id, uid, "returned", turn_idx=turn_idx)
            report["returned"].append(uid)
    if report["returned"]:
        try:
            room.add_message(cid, frame_id, "room", DISAGREEMENT_LINE,
                             turn_idx=turn_idx)
        except ValueError:
            pass
        titles = [get_proposal(cid, frame_id, u)["title"] for u in report["returned"]]
        current = room.status(cid, frame_id)
        questions = [q["text"] for q in current.get("questions") or []]
        questions.append("Settle the returned proposal: %s" % "; ".join(titles))
        write_status(cid, frame_id, line=current.get("line"), questions=questions,
                     turn_idx=turn_idx)
    return report


def run_dramaturge_pass(cid, frame_id, *, base_turn=None, brief=None, job=None):
    """One Dramaturge pass and the deliberation it leads to, out of band.
    Refuses when no grant carries the dial (the Dramaturge proposes nothing
    until the player has said how much they want to be surprised) or the
    story rewound under the job. Every line lands in the thread."""
    from agents import dramaturge
    from core.jobs import story_rewound_past
    from story import room_conversation as room
    from story.mandates import spend_limits, surprise_dial
    from story.room_frontier import record_spend, spend_this_hour
    from story.room_proposals import record_pass
    now = room.current_turn_idx(cid)
    if base_turn is not None and story_rewound_past(base_turn, now):
        return {"skipped": "rewound", "base_turn": base_turn, "turn": now}
    dial = surprise_dial(cid, frame_id, now)
    if dial is None:
        return {"skipped": "no dial"}
    spend = spend_limits(cid, frame_id, now)
    if spend_this_hour(cid, frame_id, now) >= spend["calls_per_hour"]:
        return {"skipped": "spend_hour"}
    out = dramaturge.propose(cid, frame_id, dial=dial, brief=brief, turn_idx=now)
    record_pass(cid, frame_id, now)
    if out["calls"]:
        record_spend(cid, frame_id, turn_idx=now, calls=out["calls"],
                     who="dramaturge")
    if out["note"]:
        try:
            room.add_message(cid, frame_id, "dramaturge", out["note"], turn_idx=now)
        except ValueError:
            pass
    report = {"dial": dial, "proposals": [p["uid"] for p in out["proposals"]],
              "none_needed": out["none_needed"], "refused": out["refused"],
              "dramaturge_calls": out["calls"], "deliberation": None}
    live = [p for p in out["proposals"] if p["kind"] != "quiet"]
    if live:
        report["deliberation"] = deliberate(cid, frame_id, live, base_turn=base_turn,
                                            dial=dial, turn_idx=now, job=job)
    else:
        write_status(cid, frame_id, turn_idx=now)
    return report


# ---------------------------------------------------------------------------
# The fill job, the frontier, and the commit tail
# ---------------------------------------------------------------------------

def _fill_task(cid, frame_id, report):
    from world.planning_needs import open_planning_needs
    needs = open_planning_needs(cid, frame_id)[:FILL_NEEDS_PER_JOB]
    return {
        "kind": "fill",
        "needs": needs,
        "frontier": {"player_room": report.get("player_room"),
                     "rooms_short": report.get("rooms_short"),
                     "identities_short": report.get("identities_short"),
                     "rooms_ahead": report.get("rooms_ahead"),
                     "identities_ahead": report.get("identities_ahead")},
    }


def run_fill(cid, frame_id, *, base_turn, job=None):
    """Answer what the deterministic fill could not, through a package,
    under the identity-fill mandate. Refuses when the story rewound under
    the job. Runs in passes (`_run_task`) and keeps its reply in the
    thread as the Planner's own line."""
    from core.jobs import story_rewound_past
    from story import room_conversation as room
    from story.room_frontier import frontier_report, record_fill
    now = room.current_turn_idx(cid)
    if story_rewound_past(base_turn, now):
        return {"skipped": "rewound", "base_turn": base_turn, "turn": now}
    report = frontier_report(cid, frame_id)
    task = _fill_task(cid, frame_id, report)
    if not task["needs"] and not report.get("rooms_short") \
            and not report.get("identities_short"):
        return {"skipped": "nothing short"}
    out = _run_task(cid, frame_id, task, base_turn=base_turn, job=job)
    if out["published"]:
        record_fill(cid, frame_id, turn_idx=now, package_uid=out["published"][0],
                    needs=[n["uid"] for n in task["needs"]])
    try:
        room.add_message(cid, frame_id, "planner", out["reply"], turn_idx=now)
    except ValueError:
        pass
    return {"published": out["published"], "calls": out["calls"],
            "steps": out["steps"], "stopped": out["stopped"],
            "passes": out.get("passes", 1)}


def schedule_room_work(ctx):
    """From the commit tail: measure the frontier and queue what is due --
    a fill when something is short or a need is open, under an
    identity-fill grant with room in the hour; a Dramaturge pass when a
    grant carries the dial and the pacing budget says the story is due a
    turn; a bible fold when a batch of thread lines has aged past the
    window. With no grant the status row asks. Never raises; returns the
    first job queued, or None."""
    from core import jobs
    from story import room_conversation as room
    from story.mandates import (beats_per_proposal, fill_limit, spend_limits,
                                surprise_dial)
    from story.room_bible import schedule_fold
    from story.room_frontier import (fills_this_hour, frontier_report,
                                     record_measure, spend_this_hour)
    from story.room_proposals import last_pass_turn
    cid = ctx.chat.id
    frame_id = getattr(ctx.turn, "frame_id", None)
    turn_idx = getattr(ctx.turn, "idx", None)
    report = frontier_report(cid, frame_id)
    record_measure(cid, frame_id, report, turn_idx=turn_idx)
    queued = []
    spend = spend_limits(cid, frame_id, turn_idx)
    hour_open = spend_this_hour(cid, frame_id, turn_idx) < spend["calls_per_hour"]

    wanting = bool(report.get("open_need_uids")) or report.get("rooms_short") \
        or report.get("identities_short")
    if wanting:
        limit = fill_limit(cid, frame_id, turn_idx)
        if limit is None:
            current = room.status(cid, frame_id)
            texts = [q["text"] for q in current.get("questions") or []]
            if WAITING_LINE not in texts:
                write_status(cid, frame_id, line=current.get("line"),
                             questions=texts + [WAITING_LINE], turn_idx=turn_idx)
        elif hour_open and fills_this_hour(cid, frame_id, turn_idx) < limit:
            def _fill(job):
                return run_fill(cid, frame_id, base_turn=turn_idx, job=job)
            queued.append(jobs.submit(cid, FILL_JOB_KEY, _fill, base_turn=turn_idx))

    dial = surprise_dial(cid, frame_id, turn_idx)
    if dial is not None and hour_open and turn_idx is not None:
        beats = beats_per_proposal(cid, frame_id, turn_idx)
        last = last_pass_turn(cid, frame_id)
        if last is None or int(turn_idx) - last >= int(beats):
            def _pass(job):
                return run_dramaturge_pass(cid, frame_id, base_turn=turn_idx, job=job)
            queued.append(jobs.submit(cid, DRAMATURGE_JOB_KEY, _pass,
                                      base_turn=turn_idx))

    fold = schedule_fold(cid, frame_id, window=PLANNER_HISTORY_MESSAGES,
                         base_turn=turn_idx)
    if fold is not None:
        queued.append(fold)
    return queued[0] if queued else None
