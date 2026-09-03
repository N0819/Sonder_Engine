"""The Dramaturge: the Writers' Room's other author, and it only proposes.

PURE PLANNING (owner, 2026-09-03; plan § 5 Phase C). Its input is the
PLAYER-VISIBLE STREAM -- the player's inputs and the narration outputs of
recent beats, spoiler-safe by construction and cheap -- plus its own
standing proposals, the story bible, the genre as the scenario and the
bible's `voice` state it, and the CREATIVITY DIAL the player set in words
(`mandates.surprise_dial`: 0 holds to the target the player stated, 4 is
wildly inventive). It thinks: what would be a good progression of this
story, from what I know of fiction, the chosen genre, and how far I am
licensed to surprise? It proposes DIRECTION -- pressure, reversal,
revelation, arrival, opportunity, or that nothing is needed -- as typed
proposals (`story/room_proposals.py`): what it wants to be true, why now,
what it must not contradict. Never a package, never a scene list (v2
§ 4.2), never a conclusion for a live mind (v2 § 4.3).

ONE TOOL, AND IT READS. Lore search and lookup, bounded per pass, because
the setting bible is the one thing it cannot propose without -- a heresy
trial needs a faith to exist. It never inspects the live world (rooms,
bodies, events, packages' truths) and never writes it; the Story Planner
fetches everything else it asks for and cites it back
(`agents/story_planner.deliberate`).

WHEN IT RUNS. Out of band after a beat commits, when a grant carries the
dial and the pacing budget says the story is due a turn
(`story_planner.schedule_room_work`); and when the player addresses it in
the panel, through the Planner. A story begins with no dial set, and it
proposes nothing.
"""

from __future__ import annotations

import json
import time

from core.logging_utils import logger

#: The model role (`providers.ROLES`). Its own row: the owner may want a
#: more inventive model here than the Planner's coding-agent temperament.
DRAMATURGE_ROLE = "dramaturge"
#: Beats of the player-visible stream shown, newest last.
DRAMATURGE_BEATS = 12
#: Characters of one beat's input plus narration shown.
DRAMATURGE_BEAT_CHARS = 1600
#: Room-thread lines shown (what the player and the Planner have been
#: saying), newest last.
DRAMATURGE_THREAD_LINES = 8
#: Model calls per pass: a lore step or two, then the proposal.
DRAMATURGE_STEPS = 3
#: Lore calls per pass, across its steps.
DRAMATURGE_LORE_CALLS = 4
#: Output budget per call. One number across the room (2026-09-04).
DRAMATURGE_MAX_TOKENS = 20_000
#: Wall clock per pass.
DRAMATURGE_WALL_SECONDS = 120.0
#: Proposals one pass may file.
DRAMATURGE_PROPOSALS_PER_PASS = 3
#: The one tool, both spellings of it.
LORE_TOOLS = ("search_lore", "read_lore")

#: The keys an answer may carry; an output carrying none is a cut-off.
ANSWER_KEYS = ("calls", "proposals", "note", "none_needed", "revision",
               "withdraw")
CUT_OFF_NOTE = ("your last output was not one JSON object with the known "
                "keys -- most likely cut off; nothing in it was read. Say "
                "less per step.")
#: The dial's ends, said once to the model as a scale, never as a list of
#: moves.
DIAL_SCALE = ("0 holds to the target the player stated and proposes only what "
              "serves it; 4 is wildly inventive, a turn nobody asked for; "
              "between them, the further from 0 the bolder.")


# ---------------------------------------------------------------------------
# The model call
# ---------------------------------------------------------------------------

def _call(system, payload, *, max_tokens=DRAMATURGE_MAX_TOKENS):
    from agents.common import jparse
    from llm import providers
    raw = providers.chat_complete(
        DRAMATURGE_ROLE, system, json.dumps(payload, ensure_ascii=False),
        json_mode=True, max_tokens=max_tokens)
    out = jparse(raw)
    return out if isinstance(out, dict) else {}


# ---------------------------------------------------------------------------
# What it is shown
# ---------------------------------------------------------------------------

def player_visible_stream(cid, frame_id=None, beats=DRAMATURGE_BEATS):
    """The last ``beats`` beats as the player saw them: their input and the
    narration that answered it (the active `narrator` variant's prose).
    Spoiler-safe by construction: nothing here was hidden from the player.
    Oldest first."""
    from core.db import q
    if frame_id is None:
        turns = q("SELECT id, idx, player_input FROM turns WHERE chat_id=? "
                  "AND frame_id IS NULL ORDER BY idx DESC LIMIT ?",
                  (int(cid), int(beats)))
    else:
        turns = q("SELECT id, idx, player_input FROM turns WHERE chat_id=? "
                  "AND frame_id=? ORDER BY idx DESC LIMIT ?",
                  (int(cid), int(frame_id), int(beats)))
    out = []
    for t in reversed(list(turns)):
        prose = ""
        row = q("SELECT v.content FROM steps s JOIN variants v ON v.step_id=s.id "
                "AND v.active=1 WHERE s.turn_id=? AND s.key='narrator' "
                "ORDER BY s.ord DESC LIMIT 1", (t["id"],), one=True)
        if row:
            try:
                prose = str((json.loads(row["content"]) or {}).get("prose") or "")
            except (TypeError, ValueError):
                prose = str(row["content"] or "")
        player = str(t["player_input"] or "")
        budget = DRAMATURGE_BEAT_CHARS
        player = player[:budget // 3]
        prose = prose[:max(0, budget - len(player))]
        out.append({"beat": int(t["idx"]), "player": player, "narration": prose})
    return out


def system_block(cid, frame_id=None):
    from llm.prompts import get_prompt
    from story.room_bible import render_block
    return get_prompt("dramaturge") + render_block(cid, frame_id)


def _payload(cid, frame_id, *, dial, brief, transcript, step, lore_left,
             seconds_left, turn_idx):
    from story import room_conversation as room
    from story.mandates import beats_per_proposal
    from story.room_proposals import proposals
    from core.db import q
    chat = q("SELECT name, scenario FROM chats WHERE id=?", (cid,), one=True)
    standing = [{"uid": p["uid"], "kind": p["kind"], "title": p["title"],
                 "wants_true": p["wants_true"], "status": p["status"],
                 "judgements": [{"verdict": j["verdict"], "reason": j["reason"]}
                                for j in p["judgements"][-2:]]}
                for p in proposals(cid, frame_id)
                if p["status"] in ("open", "revised", "accepted", "implemented",
                                   "refused", "returned")][-12:]
    thread = [{"role": m["role"], "text": m["text"][:600]}
              for m in room.messages(cid, frame_id, limit=DRAMATURGE_THREAD_LINES)]
    payload = {
        "story": {"name": chat["name"] if chat else "",
                  "scenario": chat["scenario"] if chat else ""},
        "dial": int(dial), "dial_scale": DIAL_SCALE,
        "pacing_beats": beats_per_proposal(cid, frame_id, turn_idx),
        "stream": player_visible_stream(cid, frame_id),
        "standing_proposals": standing,
        "status_line": room.status(cid, frame_id).get("line"),
        "thread": thread,
        "kinds": ["pressure", "reversal", "revelation", "arrival",
                  "opportunity", "quiet"],
        "transcript": transcript,
        "budget": {"step": step, "steps": DRAMATURGE_STEPS,
                   "lore_calls_left": lore_left,
                   "seconds_left": round(max(0.0, seconds_left), 1),
                   "proposals_max": DRAMATURGE_PROPOSALS_PER_PASS},
    }
    if brief:
        payload["player_asks"] = str(brief)[:1200]
    return payload


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------

def _file(cid, frame_id, raw, *, dial, turn_idx, brief):
    from story.room_proposals import file_proposal
    if not isinstance(raw, dict):
        return None, "a proposal is an object"
    try:
        row = file_proposal(
            cid, frame_id, kind=raw.get("kind"), title=raw.get("title"),
            wants_true=raw.get("wants_true"), why_now=raw.get("why_now"),
            must_not_contradict=raw.get("must_not_contradict") or "",
            scale=raw.get("scale") or "", dial=dial, turn_idx=turn_idx,
            brief=brief)
    except ValueError as exc:
        return None, str(exc)[:200]
    return row, None


def propose(cid, frame_id=None, *, dial, brief=None, turn_idx=None):
    """One pass: read lore if it must, then propose. Returns
    ``{"proposals": [rows], "note": str, "none_needed": bool, "calls": n,
    "steps": n, "refused": [reasons], "stopped": why|None}``. Proposals are
    filed as state (`room_proposals`); the note is the Dramaturge's line
    for the thread and is the caller's to store."""
    from story import room_conversation as room
    from story.room_tools import ToolError, run_tool
    turn_idx = room.current_turn_idx(cid) if turn_idx is None else int(turn_idx)
    system = system_block(cid, frame_id)
    started = time.time()
    transcript, filed, refused = [], [], []
    calls_made, steps, stopped = 0, 0, None
    note, none_needed = "", False
    for step in range(1, DRAMATURGE_STEPS + 1):
        seconds_left = DRAMATURGE_WALL_SECONDS - (time.time() - started)
        if seconds_left <= 0:
            stopped = "wall"
            break
        steps = step
        out = _call(system, _payload(
            cid, frame_id, dial=dial, brief=brief, transcript=transcript,
            step=step, lore_left=DRAMATURGE_LORE_CALLS - calls_made,
            seconds_left=seconds_left, turn_idx=turn_idx))
        if not any(k in out for k in ANSWER_KEYS):
            transcript.append({"tool": None, "args": None,
                               "result": {"error": CUT_OFF_NOTE}})
            continue
        if out.get("note"):
            note = " ".join(str(out["note"]).split())[:1200]
        if out.get("none_needed"):
            none_needed = True
        for raw in (out.get("proposals") if isinstance(out.get("proposals"), list)
                    else [])[:DRAMATURGE_PROPOSALS_PER_PASS]:
            if len(filed) >= DRAMATURGE_PROPOSALS_PER_PASS:
                break
            row, why = _file(cid, frame_id, raw, dial=dial, turn_idx=turn_idx,
                             brief=brief)
            if row is None:
                refused.append(why)
            elif all(f["uid"] != row["uid"] for f in filed):
                filed.append(row)
        calls = out.get("calls") if isinstance(out.get("calls"), list) else []
        if not calls:
            break
        for call in calls:
            if not isinstance(call, dict):
                transcript.append({"tool": None, "args": call, "result": {
                    "error": "a call is an object with `tool` and `args`"}})
                continue
            name = str(call.get("tool") or call.get("name") or "")
            args = call.get("args") if isinstance(call.get("args"), dict) else {
                k: v for k, v in call.items() if k not in ("tool", "name", "args")}
            if name not in LORE_TOOLS:
                # THE ONE TOOL. The Dramaturge reads the setting bible and
                # nothing else; the Planner fetches the rest and cites it.
                transcript.append({"tool": name, "args": args, "result": {
                    "refused": "the Dramaturge reads lore and nothing else; "
                               "ask the Planner for the world"}})
                continue
            if calls_made >= DRAMATURGE_LORE_CALLS:
                stopped = "calls"
                break
            calls_made += 1
            try:
                result = run_tool(cid, name, args, frame_id=frame_id,
                                  actor="dramaturge")
            except ToolError as exc:
                result = {"error": str(exc)[:400]}
            except Exception as exc:
                logger.info("dramaturge tool %s failed: %s", name, exc)
                result = {"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])}
            transcript.append({"tool": name, "args": args, "result": result})
        if stopped:
            break
    else:
        stopped = "steps"
    if not filed and not none_needed and not note:
        none_needed = True
    return {"proposals": filed, "note": note, "none_needed": none_needed,
            "calls": calls_made, "steps": steps, "refused": refused,
            "stopped": stopped}


def revise(cid, frame_id, proposal, judgement, *, dial, turn_idx=None):
    """The Dramaturge answers the Planner's critique: it re-states the
    proposal so the natural version is still worth encountering, or
    withdraws it. One call, no tools. Returns the proposal row as it now
    stands (revised, withdrawn or returned) and its note."""
    from story import room_conversation as room
    from story.room_proposals import revise_proposal, settle_proposal
    turn_idx = room.current_turn_idx(cid) if turn_idx is None else int(turn_idx)
    payload = {
        "dial": int(dial), "dial_scale": DIAL_SCALE,
        "proposal": {k: proposal.get(k) for k in (
            "uid", "kind", "title", "wants_true", "why_now",
            "must_not_contradict", "revision")},
        "planner_says": {"verdict": judgement.get("verdict"),
                         "reason": judgement.get("reason"),
                         "contradiction": judgement.get("contradiction")},
        "stream": player_visible_stream(cid, frame_id, beats=6),
        "task": "revise_or_withdraw",
    }
    out = _call(system_block(cid, frame_id), payload)
    note = " ".join(str(out.get("note") or "").split())[:1200]
    if out.get("withdraw"):
        row = settle_proposal(cid, frame_id, proposal["uid"], "withdrawn",
                              turn_idx=turn_idx)
        return row, note or str(out["withdraw"])[:600]
    revision = out.get("revision") if isinstance(out.get("revision"), dict) else None
    if not revision:
        row = settle_proposal(cid, frame_id, proposal["uid"], "withdrawn",
                              turn_idx=turn_idx)
        return row, note
    row = revise_proposal(cid, frame_id, proposal["uid"],
                          wants_true=revision.get("wants_true"),
                          why_now=revision.get("why_now"),
                          must_not_contradict=revision.get("must_not_contradict"),
                          turn_idx=turn_idx)
    return row, note
