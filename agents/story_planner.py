"""The Story Planner: the Writers' Room's author, seated on the panel's seam.

NOT A PIPELINE STAGE. Nothing here runs inside a turn: the Planner answers
the player's line in the room panel (`story/room_conversation.PLANNER`) and
runs the out-of-band fill job the commit tail schedules. At rest it costs
nothing (v2 § 10).

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

BOUNDED. Model calls per reply, tool calls per reply and per step, wall
clock, and the transcript it is shown back are all capped below; the
Charter Planner delegation is one scoped call per reply; the fill job is
budgeted per story hour by the identity-fill mandate.
"""

from __future__ import annotations

import hashlib
import json
import time

from core.logging_utils import logger

#: The model role (`providers.ROLES`). ONE role for the Planner and its
#: Charter Planner delegation: the delegation is a scoped call of the same
#: author, and a second settings row would be a choice that rarely differs.
PLANNER_ROLE = "story_planner"
#: The actor name a package records when the Planner drafts it
#: (`plot_packages.AGENT_AUTHORS`).
PLANNER_ACTOR = "story_planner"

#: Model calls per reply. Each step may call tools and be asked again.
PLANNER_STEPS_PER_REPLY = 6
#: Tool calls one step may make, and the ceiling across a whole reply.
PLANNER_TOOL_CALLS_PER_STEP = 6
PLANNER_TOOL_CALLS_PER_REPLY = 24
#: Wall clock for one reply, the fill job included; past it the loop ends
#: with what it has.
PLANNER_WALL_SECONDS = 180.0
#: Output budget per model call.
PLANNER_MAX_TOKENS = 4000
#: Conversation lines shown to the model, newest last.
PLANNER_HISTORY_MESSAGES = 30
#: The reply stored in the thread (the thread's own cap is larger).
PLANNER_REPLY_CHARS = 2400
#: Tool results shown back to the model; oldest fall off past it.
PLANNER_TRANSCRIPT_CHARS = 24_000
#: Charter Planner delegations per reply and their output budget.
CHARTER_PLANNER_CALLS_PER_REPLY = 1
CHARTER_PLANNER_MAX_TOKENS = 3000
#: The pseudo-tool the model names to delegate; not in the facade table.
CHARTER_PLANNER_TOOL = "charter_planner"
#: Open needs one fill job hands the Planner.
FILL_NEEDS_PER_JOB = 3
#: The job key (`core/jobs.py`), deduped per chat.
FILL_JOB_KEY = "story_planner_fill"
#: Questions the status row keeps.
STATUS_QUESTIONS_CAP = 6

#: Fixed lines. English is the message id: the panel renders through the
#: UI catalog, so each is in both `ui.json` packs.
BOUNDED_LINE = ("The room stopped at its budget for this reply; what it "
                "settled stands, and it can go on when asked.")
NO_STATUS_LINE = "The room has nothing in motion."
WAITING_LINE = ("The room has open planning needs and no grant to answer "
                "them. Tell the Story Planner what it may prepare.")
REWOUND_LINE = "The story rewound under the room's work; nothing landed."


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


def _conversation(cid, frame_id):
    from story import room_conversation as room
    return [{"role": m["role"], "text": m["text"]}
            for m in room.messages(cid, frame_id, limit=PLANNER_HISTORY_MESSAGES)]


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
    most stable thing the Planner reads (10.3k of a 13k-character payload
    on the first live run, identical on every step), so it rides the system
    block, which `providers.chat_complete` marks cacheable, and not the
    per-step user message."""
    return ("\n\nTOOLS. The room's table; the player never hears these "
            "names:\n" + json.dumps(_manifest(), ensure_ascii=False))


def _payload(cid, frame_id, *, text, task, transcript, step, calls_left,
             seconds_left, turn_idx):
    from story import room_conversation as room
    from story.mandates import (MANDATE_CAPABILITIES, MANDATE_LIMITS,
                                active_mandates, revoked_since)
    from story.plot_packages import list_packages
    from story.room_frontier import frontier_report
    from story.room_tools import run_tool
    shown, size = [], 0
    for entry in reversed(transcript):
        encoded = json.dumps(entry, ensure_ascii=False, default=str)
        if size + len(encoded) > PLANNER_TRANSCRIPT_CHARS and shown:
            break
        shown.append(entry)
        size += len(encoded)
    shown.reverse()
    try:
        clock = run_tool(cid, "inspect_clock", frame_id=frame_id)
    except Exception:
        clock = {}
    try:
        frontier = frontier_report(cid, frame_id)
    except Exception as exc:
        frontier = {"error": str(exc)[:200]}
    payload = {
        "story": _story(cid),
        "clock": clock,
        "conversation": _conversation(cid, frame_id),
        "mandates": active_mandates(cid, frame_id, turn_idx),
        "withdrawn": [{"uid": m["uid"], "text": m["text"], "status": m["status"]}
                      for m in revoked_since(cid, frame_id, max(0, turn_idx - 1))],
        "capabilities": list(MANDATE_CAPABILITIES),
        "limits": list(MANDATE_LIMITS),
        "status": room.status(cid, frame_id),
        "frontier": frontier,
        "packages": list_packages(cid, frame_id=frame_id),
        "transcript": shown,
        "budget": {"step": step, "steps": PLANNER_STEPS_PER_REPLY,
                   "calls_left": calls_left,
                   "seconds_left": round(max(0.0, seconds_left), 1)},
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
    and the questions the room is asking. A sealed package's title is the
    Planner's to keep spoiler-safe; nothing else of it is read here."""
    from core.db import wset_for_frame
    from story import room_conversation as room
    from story.plot_packages import list_packages
    in_motion = []
    for proj in list_packages(cid, frame_id=frame_id):
        if proj["status"] in ("draft", "validating", "published", "active"):
            in_motion.append({"uid": proj["uid"], "kind": "package",
                              "label": proj["title"], "state": proj["status"]})
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


def run_planner(cid, frame_id, *, text=None, task=None, base_turn=None):
    """One bounded reply. ``text`` is the player's line; ``task`` a fill
    brief from the job (no grants are read from a task). Returns
    ``{"reply", "dramaturge": None, "mandates", "status", "published":
    [uids], "calls": n, "steps": n, "notes": [...]}``."""
    from core.jobs import story_rewound_past
    from llm.prompts import get_prompt
    from story import room_conversation as room
    from story.mandates import expire_mandates
    from story.room_tools import ToolError, run_tool

    system = get_prompt("story_planner") + _tools_block()
    turn_idx = room.current_turn_idx(cid)
    expire_mandates(cid, frame_id, turn_idx)
    started = time.time()
    transcript, notes, published = [], [], []
    calls_made, delegations, steps = 0, 0, 0
    reply, status_line, questions = "", "", []
    stopped = None
    for step in range(1, PLANNER_STEPS_PER_REPLY + 1):
        seconds_left = PLANNER_WALL_SECONDS - (time.time() - started)
        if seconds_left <= 0:
            stopped = "wall"
            break
        steps = step
        out = _call(system, _payload(
            cid, frame_id, text=text, task=task, transcript=transcript,
            step=step, calls_left=PLANNER_TOOL_CALLS_PER_REPLY - calls_made,
            seconds_left=seconds_left, turn_idx=turn_idx),
            max_tokens=PLANNER_MAX_TOKENS)
        if text is not None and out.get("grants"):
            _rows, grant_notes = _apply_grants(cid, frame_id, out["grants"], turn_idx)
            notes.extend(grant_notes)
        if out.get("status_line"):
            status_line = str(out["status_line"])
        if isinstance(out.get("questions"), list):
            questions = out["questions"]
        if out.get("reply"):
            reply = str(out["reply"])
        calls = out.get("calls") if isinstance(out.get("calls"), list) else []
        if not calls:
            break
        for call in calls[:PLANNER_TOOL_CALLS_PER_STEP]:
            if calls_made >= PLANNER_TOOL_CALLS_PER_REPLY:
                stopped = "calls"
                break
            # A call the loop cannot run is REPORTED, never dropped: measured
            # live (chat 111, 2026-09-03), a model spelled the tool key
            # `name` for three steps running, each silently skipped, and
            # repeated itself into an empty transcript for 27 seconds.
            if not isinstance(call, dict):
                transcript.append({"tool": None, "args": call, "result": {
                    "error": "a call is an object with `tool` and `args`"}})
                continue
            name = str(call.get("tool") or call.get("name") or "")
            if not name:
                transcript.append({"tool": None, "args": call, "result": {
                    "error": "a call names its tool under `tool`"}})
                continue
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            calls_made += 1
            if base_turn is not None and _is_write(name) \
                    and story_rewound_past(base_turn, room.current_turn_idx(cid)):
                transcript.append({"tool": name, "args": args,
                                   "result": {"refused": REWOUND_LINE}})
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
            transcript.append({"tool": name, "args": args, "result": result})
        if stopped:
            break
    else:
        stopped = "steps"
    if stopped and not reply:
        reply = BOUNDED_LINE if stopped != "rewound" else REWOUND_LINE
    reply = str(reply or BOUNDED_LINE).strip()[:PLANNER_REPLY_CHARS]
    status = write_status(cid, frame_id, line=status_line, questions=questions,
                          turn_idx=turn_idx)
    return {"reply": reply, "dramaturge": None,
            "mandates": room.mandates(cid, frame_id), "status": status,
            "published": published, "calls": calls_made, "steps": steps,
            "notes": notes, "stopped": stopped}


def planner_reply(cid, frame_id, text):
    """The seam's shape: what `room_conversation.PLANNER` returns."""
    out = run_planner(cid, frame_id, text=text)
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
# The fill job and the frontier
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


def run_fill(cid, frame_id, *, base_turn):
    """Answer what the deterministic fill could not, through a package,
    under the identity-fill mandate. Refuses when the story rewound under
    the job. The reply is kept in the thread as the Planner's own line."""
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
    out = run_planner(cid, frame_id, task=task, base_turn=base_turn)
    if out["published"]:
        record_fill(cid, frame_id, turn_idx=now, package_uid=out["published"][0],
                    needs=[n["uid"] for n in task["needs"]])
    try:
        room.add_message(cid, frame_id, "planner", out["reply"], turn_idx=now)
    except ValueError:
        pass
    return {"published": out["published"], "calls": out["calls"],
            "steps": out["steps"], "stopped": out["stopped"]}


def schedule_room_work(ctx):
    """From the commit tail: measure the frontier; when something is short
    or a need is open, and a grant permits fills, and the hour's budget has
    room, queue one fill job. With no grant the status row asks. Never
    raises; returns the job, or None."""
    from core import jobs
    from story import room_conversation as room
    from story.mandates import fill_limit
    from story.room_frontier import (fills_this_hour, frontier_report,
                                     record_measure)
    cid = ctx.chat.id
    frame_id = getattr(ctx.turn, "frame_id", None)
    turn_idx = getattr(ctx.turn, "idx", None)
    report = frontier_report(cid, frame_id)
    record_measure(cid, frame_id, report, turn_idx=turn_idx)
    wanting = bool(report.get("open_need_uids")) or report.get("rooms_short") \
        or report.get("identities_short")
    if not wanting:
        return None
    limit = fill_limit(cid, frame_id, turn_idx)
    if limit is None:
        current = room.status(cid, frame_id)
        texts = [q["text"] for q in current.get("questions") or []]
        if WAITING_LINE not in texts:
            write_status(cid, frame_id, line=current.get("line"),
                         questions=texts + [WAITING_LINE], turn_idx=turn_idx)
        return None
    if fills_this_hour(cid, frame_id, turn_idx) >= limit:
        return None

    def _run(job):
        return run_fill(cid, frame_id, base_turn=turn_idx)

    return jobs.submit(cid, FILL_JOB_KEY, _run, base_turn=turn_idx)
