"""The Dramaturge: the Writers' Room's other author, and it only proposes.

PURE PLANNING (owner, 2026-09-03; plan § 5 Phase C). Its input is the
PLAYER-VISIBLE STREAM -- the player's inputs and the narration outputs of
recent beats, spoiler-safe by construction and cheap -- plus its own
standing proposals, the story bible, the genre as the scenario and the
bible's `voice` state it, and the CREATIVITY DIAL (`mandates.surprise_dial`:
0 holds to the target the player stated, 4 is wildly inventive; the number
the player set in words when a grant names one, `SURPRISE_DEFAULT` until
then). It thinks: what would be a good progression of this story, from
what I know of fiction, the chosen genre, and how far I am licensed to
surprise? It proposes DIRECTION -- pressure, reversal, revelation,
arrival, opportunity, or that nothing is needed -- as typed proposals
(`story/room_proposals.py`): what it wants to be true, why now, what it
must not contradict. Never a package, never a scene list (v2 § 4.2),
never a conclusion for a live mind (v2 § 4.3).

ONE TOOL, AND IT READS. Lore search and lookup, bounded per pass, because
the setting bible is the one thing it cannot propose without -- a heresy
trial needs a faith to exist. It never inspects the live world (rooms,
bodies, events, packages' truths) and never writes it; the Story Planner
fetches everything else it asks for and cites it back
(`agents/story_planner.deliberate`).

WHEN IT RUNS. IN EVERY STORY, ON PACING ALONE (owner, 2026-10-08: "It was
never meant to be surprise only, it was meant to suggest story
directions"). Out of band after a beat commits, once the frame has played
`mandates.beats_per_proposal` beats of its own since the last pass -- or,
before the first, since its opening (`room_proposals.pass_due`) -- while
the story hour's spend is open (`story_planner.schedule_room_work`); never
from a live causality bubble's commit, whose stream is empty; and when the
player asks the Planner for direction in the panel, at once -- the ask
waits on the room's row until a pass takes it (`room_proposals.ask_brief`),
so one made while a pass runs is answered when that pass is done. It needs
no grant: the dial a grant names only tunes how inventive it is, and a
grant naming a pacing of 0 stops its own passes while the player's ask
still runs. Until 2026-10-08 it ran only under a grant whose limits carried
a numeric `surprise`, which no grant in the owner's database ever did, so it
had never run. ITS SUGGESTIONS ARE JUDGED LAZILY (owner, 2026-10-08: "save
heavy plans for when the actors near them"): the Planner's deliberation runs
when a beat brings the story near one, or once it has waited its bound, and
at once for what the player asked (`story_planner.run_direction_follow_up`).

SUGGESTING IS NOT ACTING. Nothing it proposes reaches the world except as
a package the Planner drafts for it, and a package the Planner drafted
publishes only under mandates covering every operation in it
(`plot_packages.authority_errors`). A story with no grants still gets the
suggestions -- as the Dramaturge's line and the Planner's judgement in the
thread, and the pending proposals' kinds and titles on the status row --
and the Planner asks for whatever acting on one would need.
"""

from __future__ import annotations

import time

from core.db import data_version
from core.logging_utils import logger
from story.room_proposals import BRIEF_CHARS

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
DRAMATURGE_MAX_TOKENS = 40_000
#: Wall clock per pass.
DRAMATURGE_WALL_SECONDS = 120.0
#: Proposals one pass may file.
DRAMATURGE_PROPOSALS_PER_PASS = 3
#: The Planner's brief the payload carries as `player_asks` -- what one
#: waiting brief may hold (`room_proposals.BRIEF_CHARS`, one number), and
#: what one pass reads when several asks waited for it
#: (`story_planner._joined_briefs` keeps the newest whole).
DRAMATURGE_BRIEF_CHARS = BRIEF_CHARS
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

def _call(system, payload, *, max_tokens=None):
    """One Room call on the dramaturge's role. `max_tokens=None` means the
    Room's one number (`room_calls.room_max_tokens`), which is the host's own
    output ceiling."""
    # Through `story.room_calls.room_call` rather than `chat_complete`
    # directly, so a pass is as readable as a beat's stages are when the
    # host has capture on (`persist/llm_capture.py`). Same provider, same
    # arguments, same return.
    from agents.common import jparse
    from story.room_calls import room_call, room_max_tokens
    raw = room_call(DRAMATURGE_ROLE, system, payload,
                    max_tokens=(max_tokens if max_tokens is not None
                                else room_max_tokens(DRAMATURGE_MAX_TOKENS)),
                    phase="dramaturge")
    out = jparse(raw)
    return out if isinstance(out, dict) else {}


# ---------------------------------------------------------------------------
# What it is shown
# ---------------------------------------------------------------------------

#: Rows a reader looks past for the newest beat something has answered: the
#: beat in play is one, and a second covers a line sent while the first was
#: still being answered.
IN_PLAY_ROWS = 2


def _frame_turns(cid, frame_id, limit):
    """The frame's newest turn rows, newest first."""
    from core.db import q
    if frame_id is None:
        return list(q("SELECT id, idx, player_input FROM turns WHERE chat_id=? "
                      "AND frame_id IS NULL ORDER BY idx DESC LIMIT ?",
                      (int(cid), int(limit))))
    return list(q("SELECT id, idx, player_input FROM turns WHERE chat_id=? "
                  "AND frame_id=? ORDER BY idx DESC LIMIT ?",
                  (int(cid), int(frame_id), int(limit))))


def _answered(turns):
    """``turns`` (newest first) less the newest ones still IN PLAY: the
    player's line is sent and the turn row stands, but no narration has
    answered it yet (no active `narrator` step -- a hand-edited one of any
    shape still counts). Only the newest rows can be in play; one with no
    narration further down is a beat that ended without it, and is kept."""
    from persist.steps import active_content
    turns = list(turns)
    while turns and active_content(turns[0]["id"], "narrator") is None:
        turns = turns[1:]
    return turns


def newest_answered_beat(cid, frame_id=None):
    """The newest beat of the frame that something has answered -- the beat
    in play above it left out (`player_visible_stream`) -- or None when it
    has none. A pass is recorded at it (`story_planner._dramaturge_pass`):
    the pacing counts from the beats a pass reads, not from a line still
    being answered."""
    turns = _answered(_frame_turns(cid, frame_id, IN_PLAY_ROWS + 1))
    return int(turns[0]["idx"]) if turns else None


def player_visible_stream(cid, frame_id=None, beats=DRAMATURGE_BEATS, *, job=None):
    """The last ``beats`` beats as the player saw them: their input and the
    narration that answered it (the active `narrator` variant's prose).
    Spoiler-safe by construction: nothing here was hidden from the player.
    Oldest first.

    A BEAT IN PLAY IS NOT READ (review R4-1, 2026-10-08): a line the player
    has sent and nothing has answered yet (`_answered`) is left out, line
    and place in the read horizon alike. Read, it carried the horizon of a
    pass that came round while the next beat ran onto that beat, so a
    reroll of it -- which keeps the line -- took everything the pass wrote:
    its suggestions dropped, its pacing spent, a player's ask answered and
    gone.

    A ``job`` reading it has its read horizon raised to the newest beat it
    returns (`core.jobs.read_through`, review R3-1), so a restore that
    discards a beat the job has read stops the job -- and a job a restore
    spared reads none of the beats being played again: the horizon is
    raised before any narration is returned, and nothing past the limit a
    restore set is."""
    from core.jobs import read_through
    from persist.steps import active_content
    turns = _answered(_frame_turns(cid, frame_id, int(beats) + IN_PLAY_ROWS))
    turns = turns[:int(beats)]
    if turns and job is not None:
        through = read_through(job, max(int(t["idx"]) for t in turns))
        turns = [t for t in turns if int(t["idx"]) <= through]
    out = []
    for t in reversed(turns):
        prose = ""
        # One reader of a step's active content (`persist/steps.py`); the
        # copy that used to stand here answered `.get("prose")` on whatever
        # the JSON parsed to, which is an AttributeError the moment a step's
        # content is not a mapping (review 2026-09-07, B23).
        content = active_content(t["id"], "narrator")
        if isinstance(content, dict):
            prose = str(content.get("prose") or "")
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
             seconds_left, turn_idx, memo=None, job=None):
    """The step's payload. Everything but the dial, the transcript and the
    budget is derived from the database, and a pass reads far more often
    than it writes, so ``memo`` (`room_calls.ReplyMemo`) holds that half
    across the pass's steps and `propose` drops it whenever the pass
    writes. Measured (review 2026-09-07, C21): the player-visible stream
    alone is one query for the beats and one per beat for their narration,
    thirteen for twelve beats, rebuilt on every one of
    `DRAMATURGE_STEPS`."""
    from story import room_conversation as room
    from story.mandates import beats_per_proposal
    from story.room_calls import memo_part
    from story.room_proposals import proposals
    from core.db import q

    def _story():
        chat = q("SELECT name, scenario FROM chats WHERE id=?", (cid,), one=True)
        return {"name": chat["name"] if chat else "",
                "scenario": chat["scenario"] if chat else ""}

    def _standing():
        return [{"uid": p["uid"], "kind": p["kind"], "title": p["title"],
                 "wants_true": p["wants_true"], "status": p["status"],
                 "judgements": [{"verdict": j["verdict"], "reason": j["reason"]}
                                for j in p["judgements"][-2:]]}
                for p in proposals(cid, frame_id)
                if p["status"] in ("open", "revised", "accepted", "implemented",
                                   "refused", "returned")][-12:]

    def _thread():
        return [{"role": m["role"], "text": m["text"][:600]}
                for m in room.messages(cid, frame_id,
                                       limit=DRAMATURGE_THREAD_LINES)]

    payload = {
        "story": memo_part(memo, "story", _story),
        "dial": int(dial), "dial_scale": DIAL_SCALE,
        "pacing_beats": memo_part(
            memo, "pacing_beats",
            lambda: beats_per_proposal(cid, frame_id, turn_idx)),
        "stream": memo_part(memo, "stream",
                            lambda: player_visible_stream(cid, frame_id, job=job)),
        "standing_proposals": memo_part(memo, "standing_proposals", _standing),
        "status_line": memo_part(memo, "status_line",
                                 lambda: room.status(cid, frame_id).get("line")),
        "thread": memo_part(memo, "thread", _thread),
        "kinds": ["pressure", "reversal", "revelation", "arrival",
                  "opportunity", "quiet"],
        "transcript": transcript,
        "budget": {"step": step, "steps": DRAMATURGE_STEPS,
                   "lore_calls_left": lore_left,
                   "seconds_left": round(max(0.0, seconds_left), 1),
                   "proposals_max": DRAMATURGE_PROPOSALS_PER_PASS},
    }
    if brief:
        payload["player_asks"] = str(brief)[-DRAMATURGE_BRIEF_CHARS:]
    return payload


# ---------------------------------------------------------------------------
# The pass
# ---------------------------------------------------------------------------

def _file(cid, frame_id, raw, *, dial, turn_idx, brief, job=None, asks=()):
    from core.jobs import is_cancelled
    from story.room_proposals import file_proposal
    if is_cancelled(job):
        # A cancelled pass files nothing: what it read may be a beat the
        # player has since rerolled (`persist/checkpoints.restore_checkpoint`).
        return None, "the pass was cancelled; nothing is filed"
    if not isinstance(raw, dict):
        return None, "a proposal is an object"
    # FILED AT THE NEWEST BEAT THE PASS READ (review R3-2/R3-4, 2026-10-08):
    # its job's read horizon, which the stream raised before the call that
    # wrote this answered. A suggestion is about the beats after the ones it
    # was written from (`story_planner._mark_due_now`), and a restore keeps
    # one written only from beats it keeps (`room_proposals.keep_spared`).
    horizon = getattr(job, "read_turn", None)
    if horizon is not None:
        turn_idx = int(horizon)
    try:
        row = file_proposal(
            cid, frame_id, kind=raw.get("kind"), title=raw.get("title"),
            wants_true=raw.get("wants_true"), why_now=raw.get("why_now"),
            must_not_contradict=raw.get("must_not_contradict") or "",
            scale=raw.get("scale") or "", dial=dial, turn_idx=turn_idx,
            brief=brief, asks=asks)
    except ValueError as exc:
        return None, str(exc)[:200]
    return row, None


def propose(cid, frame_id=None, *, dial, brief=None, turn_idx=None, job=None,
            asks=()):
    """One pass: read lore if it must, then propose. Returns
    ``{"proposals": [rows], "note": str, "none_needed": bool, "calls": n,
    "steps": n, "refused": [reasons], "stopped": why|None}``. Proposals are
    filed as state (`room_proposals`), each naming the player's ``asks`` it
    answers -- the ones its pass took, which ``brief`` joins -- so a restore
    that drops it gives them back (`room_proposals.keep_spared`); the note
    is the Dramaturge's line for the thread and is the caller's to store. A
    ``job`` that is cancelled stops the pass at its next step and files
    nothing more (`core.jobs.is_cancelled`); ``stopped`` is then
    "cancelled"."""
    from core.jobs import is_cancelled
    from story import room_conversation as room
    from story.room_calls import ReplyMemo
    from story.room_tools import ToolError, run_tool, tool_only_reads
    turn_idx = room.current_turn_idx(cid) if turn_idx is None else int(turn_idx)
    system = system_block(cid, frame_id)
    started = time.time()
    transcript, filed, refused = [], [], []
    calls_made, steps, stopped = 0, 0, None
    note, none_needed = "", False
    # The pass's derived half, dropped by what the pass writes -- a filed
    # proposal, a tool the table does not mark a pure read -- and by a beat
    # landing under it, which no write of the pass's own would report (C21).
    memo = ReplyMemo()
    for step in range(1, DRAMATURGE_STEPS + 1):
        if is_cancelled(job):
            stopped = "cancelled"
            break
        seconds_left = DRAMATURGE_WALL_SECONDS - (time.time() - started)
        if seconds_left <= 0:
            stopped = "wall"
            break
        steps = step
        memo.at_version(data_version())
        out = _call(system, _payload(
            cid, frame_id, dial=dial, brief=brief, transcript=transcript,
            step=step, lore_left=DRAMATURGE_LORE_CALLS - calls_made,
            seconds_left=seconds_left, turn_idx=turn_idx, memo=memo, job=job))
        if is_cancelled(job):
            # Cancelled while the model answered: what it answered is about a
            # beat the story may no longer hold.
            stopped = "cancelled"
            break
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
            if is_cancelled(job):
                stopped = "cancelled"
                break
            row, why = _file(cid, frame_id, raw, dial=dial, turn_idx=turn_idx,
                             brief=brief, job=job, asks=asks)
            if row is None:
                refused.append(why)
            else:
                memo.wrote()  # the standing proposals the next payload states
                if all(f["uid"] != row["uid"] for f in filed):
                    filed.append(row)
        if stopped:
            break
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
            if not tool_only_reads(name):
                memo.wrote()
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


def revise(cid, frame_id, proposal, judgement, *, dial, turn_idx=None, job=None):
    """The Dramaturge answers the Planner's critique: it re-states the
    proposal so the natural version is still worth encountering, or
    withdraws it. One call, no tools. Returns the proposal row as it now
    stands (revised, withdrawn or returned) and its note. A cancelled
    ``job`` writes nothing and says nothing: the proposal comes back as it
    stood."""
    from core.jobs import is_cancelled
    from story import room_conversation as room
    from story.room_proposals import revise_proposal, settle_proposal
    if is_cancelled(job):
        return proposal, ""
    turn_idx = room.current_turn_idx(cid) if turn_idx is None else int(turn_idx)
    payload = {
        "dial": int(dial), "dial_scale": DIAL_SCALE,
        "proposal": {k: proposal.get(k) for k in (
            "uid", "kind", "title", "wants_true", "why_now",
            "must_not_contradict", "revision")},
        "planner_says": {"verdict": judgement.get("verdict"),
                         "reason": judgement.get("reason"),
                         "contradiction": judgement.get("contradiction")},
        "stream": player_visible_stream(cid, frame_id, beats=6, job=job),
        "task": "revise_or_withdraw",
    }
    out = _call(system_block(cid, frame_id), payload)
    if is_cancelled(job):
        return proposal, ""
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
