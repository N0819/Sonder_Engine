"""Dramaturge proposals: intent as state, and the deliberation's ledger.

The Dramaturge (`agents/dramaturge.py`) proposes DIRECTION -- a pressure, a
reversal, a revelation, an arrival, an opportunity, or that nothing is
needed -- and never a package. A proposal is typed state (v2 § 4.2, § 6.1:
"conversation is presentation; proposals are state"): what it wants to be
true, why now, what it must not contradict, at what scale. The Story
Planner judges it (`agents/story_planner.deliberate`), and the verdict is
recorded here beside it, so the exchange the panel shows or summarises has
a ledger behind it and the room never re-proposes what it has refused.

Statuses: `open` (awaiting the Planner), `revised` (sent back and revised
by the Dramaturge, awaiting the Planner again), `accepted` (the Planner
found it natural and is implementing), `implemented` (a package landed for
it), `refused` (with the contradiction named), `withdrawn` (the Dramaturge
gave it up after a critique), `returned` (rounds exhausted; the
disagreement is the player's to settle).

The row rides the frame-scoped `room_proposals` world key. It is author
state: served to the room's agents and the panel, to no mind.

THE PLAYER'S ASKS WAIT HERE TOO (review F1, 2026-10-08). When the Planner
hands the Dramaturge a brief, the brief is kept on this row until a pass
takes it (`ask_brief`, `take_briefs`). The pass and the ask share one job
key, so an ask made while a pacing pass ran joined that pass and was never
read; kept here, the running pass answers it when it finishes, and a commit
queues a pass while one waits. A brief is the CONVERSATION's, not the
beat's: a restore leaves the waiting ones as they stand
(`persist/checkpoints.restore_checkpoint`, `held_briefs`/`keep_briefs`),
as it leaves the thread they were asked in. Every read-modify-write of the
row is one transaction, because a pass writes proposals while a reply asks.

AND THE LAZY FOLLOW-UP'S MARKS (owner, 2026-10-08: "save heavy plans for
when the actors near them"). A pending proposal is judged when the story
nears it, not when it is filed (`story_planner.run_direction_follow_up`):
`due` says why it is due now (`DUE_REASONS`) and `taken_turn` the beat a
deliberation last took it up; the row's `follow_up_turn` is the newest beat
the decision model has read. The bound is `DIRECTION_WAIT_INTERVALS`.
"""

from __future__ import annotations

import hashlib
import json
import time

from core.db import q, transaction, wget_for_frame, wset_for_frame

PROPOSALS_KEY = "room_proposals"

#: The closed set of things a proposal can be. A schema the engine owns:
#: the Planner's judgement and the panel's label read it. `quiet` is the
#: Dramaturge saying the story needs nothing from it now, which is a
#: proposal too (v2 § 4.1) and is recorded so the pass counts.
PROPOSAL_KINDS = ("pressure", "reversal", "revelation", "arrival",
                  "opportunity", "quiet")
PROPOSAL_STATUSES = ("open", "revised", "accepted", "implemented", "refused",
                     "withdrawn", "returned")
#: Statuses that still await the Planner. A `quiet` proposal never does: it
#: is the record that a pass found nothing needed (`awaits_planner`).
PENDING_STATUSES = ("open", "revised")
#: Statuses after which nothing more is asked about a proposal: it landed,
#: was refused or withdrawn, or went back to the player. `accepted` is not
#: among them -- an accepted proposal with no package is still being worked
#: and may still be waiting on a grant (`story_planner.write_status` keeps a
#: deliberation's question while any proposal it judged is unsettled).
SETTLED_STATUSES = ("implemented", "refused", "withdrawn", "returned")
#: WHY A PENDING PROPOSAL IS DUE ITS DELIBERATION NOW (the lazy follow-up,
#: owner 2026-10-08: "save heavy plans for when the actors near them").
#: `asked`: the player asked for direction and this answers it -- judged at
#: once, never lazily. `touched`: the decision model read a beat as bringing
#: the story to what it is about. `waited`: the story did not come to it
#: within the bound (`DIRECTION_WAIT_INTERVALS`), and it is judged anyway, so
#: no suggestion is ever dropped. A closed set the engine owns.
DUE_REASONS = ("asked", "touched", "waited")
#: THE BOUND ON THE LAZY FOLLOW-UP, in pacing intervals of the story's own
#: pace (`mandates.beats_per_proposal`; the default pace when the player has
#: turned the passes off): a pending proposal no deliberation has taken
#: within this many intervals since it was filed -- or since a deliberation
#: last took it up and was cut short -- is deliberated anyway. Two intervals
#: (12 beats at the default pace of 6): by then the pass after next has run,
#: so a suggestion is judged before the one after it is filed on top of it,
#: and at most two passes' proposals wait at once. Owner's to rule on.
DIRECTION_WAIT_INTERVALS = 2
#: Rows kept per frame, pending and settled together; past it the oldest
#: SETTLED rows fall off -- a `quiet` one counts as settled. A proposal
#: awaiting the Planner is never dropped by the cap.
PROPOSALS_CAP = 24
#: Each prose field of a proposal.
PROPOSAL_TEXT_CHARS = 600
#: How many times one proposal may be revised before it is returned.
PROPOSAL_REVISIONS_CAP = 2
#: One brief the Planner handed on, as `story_planner.run_planner` caps the
#: `to_dramaturge` it reads, and as the Dramaturge's payload carries
#: `player_asks`.
BRIEF_CHARS = 1200
#: The asks one proposal remembers answering (`asks`), as its pass took them.
PROPOSAL_ASKS_CAP = 8
#: The passes a row remembers (`pass_log`), newest last: enough that a
#: restore which takes the newest back finds the ones before it standing.
PASS_LOG_CAP = 8


def _text(value, limit=PROPOSAL_TEXT_CHARS):
    return " ".join(str(value or "").split())[:limit]


def _identity(kind, title):
    return "%s:%s" % (kind, _text(title, 200).casefold())


def _uid(identity, frame_id):
    material = "%s|%s" % (identity, frame_id if frame_id is not None else "")
    return "prop_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]


def normalize_proposal(entry, frame_id=None):
    entry = entry if isinstance(entry, dict) else {}
    kind = str(entry.get("kind") or "").strip().casefold()
    if kind not in PROPOSAL_KINDS:
        kind = "pressure"
    status = str(entry.get("status") or "open")
    if status not in PROPOSAL_STATUSES:
        status = "open"
    title = _text(entry.get("title"), 200)
    identity = str(entry.get("identity") or "") or _identity(kind, title)
    out = {
        "uid": str(entry.get("uid") or "") or _uid(identity, frame_id),
        "identity": identity,
        "kind": kind,
        "title": title,
        "wants_true": _text(entry.get("wants_true")),
        "why_now": _text(entry.get("why_now")),
        "must_not_contradict": _text(entry.get("must_not_contradict")),
        "scale": _text(entry.get("scale"), 60),
        "dial": int(entry.get("dial") or 0),
        "status": status,
        "revision": int(entry.get("revision") or 0),
        "filed_turn": int(entry.get("filed_turn") or 0),
        "judgements": [dict(j) for j in (entry.get("judgements") or [])
                       if isinstance(j, dict)][-6:],
        "package_uid": str(entry.get("package_uid") or ""),
        "sources": [str(s) for s in (entry.get("sources") or []) if str(s)][:8],
        # The lazy follow-up's two marks: why it is due a deliberation now
        # (`DUE_REASONS`, "" while it waits), and the beat a deliberation
        # last took it up (None: never deliberated).
        "due": (str(entry.get("due") or "")
                if str(entry.get("due") or "") in DUE_REASONS else ""),
        "taken_turn": _turn_or_none(entry.get("taken_turn")),
    }
    if entry.get("brief"):
        out["brief"] = _text(entry.get("brief"))
    asks = _asks(entry.get("asks"))
    if asks:
        out["asks"] = asks
    return out


def _asks(raw):
    """The player's asks, each once, as a pass took them (`take_briefs`)."""
    out = []
    for text in raw if isinstance(raw, list) else []:
        text = _text(text, BRIEF_CHARS)
        if text and text not in out:
            out.append(text)
    return out[-PROPOSAL_ASKS_CAP:]


def answered_asks(proposal):
    """The player's asks ``proposal`` answers: the ones its pass took
    (`asks`) -- or, on a row filed before the asks were kept, its brief as
    one ask. One text is one ask, as it is while it waits (`ask_brief`)."""
    asks = list(proposal.get("asks") or ())
    if not asks and proposal.get("brief"):
        asks = [proposal["brief"]]
    return asks


def _pass_log(stored):
    """The row's passes, newest last (`PASS_LOG_CAP`): each its number, the
    beat it was recorded at (`record_pass`), and the newest beat it had read
    when its answer landed (`land_pass`; None while it runs, and for good
    once it failed). A row written before the log was kept reads as its one
    recorded pass."""
    stored = stored if isinstance(stored, dict) else {}
    out = []
    for entry in stored.get("pass_log") or []:
        if not isinstance(entry, dict):
            continue
        number, turn = _turn_or_none(entry.get("pass")), _turn_or_none(entry.get("turn"))
        if number is None or turn is None:
            continue
        out.append({"pass": number, "turn": turn,
                    "read": _turn_or_none(entry.get("read"))})
    if not out:
        last = _turn_or_none(stored.get("last_pass_turn"))
        if last is not None:
            out.append({"pass": int(stored.get("passes") or 0), "turn": last,
                        "read": None})
    return out[-PASS_LOG_CAP:]


def _turn_or_none(value):
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _briefs(raw):
    """Waiting briefs, oldest first: each a text, the beat it was asked at
    and when -- and, for one a pass took and failed on, the beat it failed
    at (`failed_turn`, `briefs_due`). One text is one ask, however often it
    was handed on."""
    out, seen = [], set()
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        text = _text(entry.get("text"), BRIEF_CHARS)
        if not text or text in seen:
            continue
        seen.add(text)
        brief = {"text": text, "turn_idx": int(entry.get("turn_idx") or 0),
                 "at": float(entry.get("at") or 0.0)}
        failed = _turn_or_none(entry.get("failed_turn"))
        if failed is not None:
            brief["failed_turn"] = failed
        out.append(brief)
    return out


def _row(cid, frame_id):
    stored = wget_for_frame(cid, PROPOSALS_KEY, frame_id, {}) or {}
    if not isinstance(stored, dict):
        stored = {}
    rows = [normalize_proposal(p, frame_id) for p in (stored.get("proposals") or [])
            if isinstance(p, dict)]
    log = _pass_log(stored)
    return {"proposals": rows,
            "last_pass_turn": log[-1]["turn"] if log else None,
            "pass_log": log,
            "passes": int(stored.get("passes") or 0),
            "briefs": _briefs(stored.get("briefs")),
            "follow_up_turn": _turn_or_none(stored.get("follow_up_turn"))}


def awaits_planner(proposal):
    """Whether a proposal is waiting on the Planner's judgement: open or
    revised, and not `quiet`. A quiet proposal is the Dramaturge saying the
    story needs nothing from it now; the deliberation never judges one
    (`story_planner.deliberate`), so it sat `open` for good -- shown on the
    player's status row as something in motion, handed to the Planner as a
    pending proposal, and never dropped by the cap. Harmless while the
    Dramaturge never ran; on its pacing (owner, 2026-10-08) every pass that
    found nothing would have added one."""
    return proposal["status"] in PENDING_STATUSES and proposal["kind"] != "quiet"


def _save(cid, frame_id, row):
    rows = [normalize_proposal(p, frame_id) for p in row.get("proposals") or []]
    settled = [p for p in rows if not awaits_planner(p)]
    while len(rows) > PROPOSALS_CAP and settled:
        oldest = settled.pop(0)
        rows = [p for p in rows if p is not oldest]
    row["proposals"] = rows
    row["briefs"] = _briefs(row.get("briefs"))
    wset_for_frame(cid, PROPOSALS_KEY, row, frame_id)
    return row


def proposals(cid, frame_id=None):
    return _row(cid, frame_id)["proposals"]


def pending_proposals(cid, frame_id=None):
    return [p for p in proposals(cid, frame_id) if awaits_planner(p)]


def get_proposal(cid, frame_id, uid):
    for p in proposals(cid, frame_id):
        if p["uid"] == str(uid):
            return p
    return None


def file_proposal(cid, frame_id, *, kind, title, wants_true, why_now,
                  must_not_contradict="", scale="", dial=0, turn_idx=0,
                  brief=None, sources=(), asks=()):
    """The Dramaturge's intent, as a row. Refuses an unknown kind, no
    title, or (for anything but `quiet`) nothing it wants true. The same
    kind and title while pending or accepted is the same proposal, returned
    as it stands -- a model re-emits a proposal on every step of a pass it
    is still working -- answering, from now on, the ``asks`` (the player's,
    as its pass took them) it did not answer already."""
    kind = str(kind or "").strip().casefold()
    if kind not in PROPOSAL_KINDS:
        raise ValueError("no such proposal kind %r; the kinds are %s"
                         % (kind, ", ".join(PROPOSAL_KINDS)))
    title = _text(title, 200)
    if not title:
        raise ValueError("a proposal has a title the panel can show")
    wants = _text(wants_true)
    if kind != "quiet" and not wants:
        raise ValueError("a proposal says what it wants to be true")
    with transaction():
        row = _row(cid, frame_id)
        identity = _identity(kind, title)
        asks = _asks(list(asks or ()))
        for existing in row["proposals"]:
            if existing["identity"] == identity and existing["status"] in (
                    "open", "revised", "accepted"):
                merged = _asks(existing.get("asks", []) + asks)
                if merged != existing.get("asks", []):
                    existing["asks"] = merged
                    _save(cid, frame_id, row)
                return dict(existing)
        record = normalize_proposal({
            "kind": kind, "title": title, "wants_true": wants,
            "why_now": why_now, "must_not_contradict": must_not_contradict,
            "scale": scale, "dial": dial, "status": "open",
            "filed_turn": int(turn_idx or 0), "brief": brief, "asks": asks,
            "sources": list(sources or ()), "filed_at": time.time(),
        }, frame_id)
        row["proposals"].append(record)
        _save(cid, frame_id, row)
    return record


def judge_proposal(cid, frame_id, uid, *, verdict, reason, contradiction="",
                   round_no=1, turn_idx=0, package_uid=""):
    """The Planner's verdict: `accept` (natural; being implemented),
    `refuse` (with the contradiction named), or `revise` (sent back to the
    Dramaturge). Returns the row, or None for an unknown uid."""
    verdict = str(verdict or "").strip().casefold()
    if verdict not in ("accept", "refuse", "revise"):
        raise ValueError("a verdict is accept, refuse or revise")
    with transaction():
        row = _row(cid, frame_id)
        for p in row["proposals"]:
            if p["uid"] != str(uid):
                continue
            p["judgements"].append({
                "round": int(round_no), "verdict": verdict,
                "reason": _text(reason), "contradiction": _text(contradiction),
                "turn": int(turn_idx or 0)})
            p["judgements"] = p["judgements"][-6:]
            if verdict == "accept":
                p["status"] = "accepted"
                if package_uid:
                    p["status"] = "implemented"
                    p["package_uid"] = str(package_uid)
            elif verdict == "refuse":
                p["status"] = "refused"
            else:
                p["status"] = "revised" if p["revision"] < PROPOSAL_REVISIONS_CAP \
                    else "returned"
            _save(cid, frame_id, row)
            return dict(p)
    return None


def revise_proposal(cid, frame_id, uid, *, wants_true, why_now,
                    must_not_contradict=None, turn_idx=0):
    """The Dramaturge answers a critique: the proposal, re-stated, goes back
    to the Planner as `open` with its revision counted. Past
    `PROPOSAL_REVISIONS_CAP` it is `returned` instead."""
    with transaction():
        row = _row(cid, frame_id)
        for p in row["proposals"]:
            if p["uid"] != str(uid):
                continue
            if p["revision"] >= PROPOSAL_REVISIONS_CAP:
                p["status"] = "returned"
            else:
                p["revision"] += 1
                p["wants_true"] = _text(wants_true) or p["wants_true"]
                p["why_now"] = _text(why_now) or p["why_now"]
                if must_not_contradict is not None:
                    p["must_not_contradict"] = _text(must_not_contradict)
                p["status"] = "open"
            _save(cid, frame_id, row)
            return dict(p)
    return None


def settle_proposal(cid, frame_id, uid, status, *, package_uid="", turn_idx=0):
    """Move a proposal to a terminal status: `implemented` (with its
    package), `withdrawn` or `returned`."""
    if status not in ("implemented", "withdrawn", "returned"):
        raise ValueError("a proposal settles as implemented, withdrawn or returned")
    with transaction():
        row = _row(cid, frame_id)
        for p in row["proposals"]:
            if p["uid"] != str(uid):
                continue
            p["status"] = status
            if package_uid:
                p["package_uid"] = str(package_uid)
            p["judgements"].append({"round": 0, "verdict": status, "reason": "",
                                    "contradiction": "",
                                    "turn": int(turn_idx or 0)})
            _save(cid, frame_id, row)
            return dict(p)
    return None


def record_pass(cid, frame_id, turn_idx):
    """One Dramaturge pass was asked at this beat (whatever it proposed,
    and whether or not its model answered -- `story_planner.
    run_dramaturge_pass` records it before the call, so a dead provider is
    asked again at the pacing, never at every commit). Returns the pass's
    entry in the row's log (`pass_log`): its number, by which `land_pass`
    and `give_back_pass` name it, and the beat."""
    with transaction():
        row = _row(cid, frame_id)
        number = int(row.get("passes") or 0) + 1
        entry = {"pass": number, "turn": int(turn_idx or 0), "read": None}
        row["passes"] = number
        row["pass_log"] = (row["pass_log"] + [entry])[-PASS_LOG_CAP:]
        row["last_pass_turn"] = entry["turn"]
        _save(cid, frame_id, row)
    return dict(entry)


def land_pass(cid, frame_id, number, read_turn):
    """Pass ``number``'s answer landed -- its suggestions on the row, its
    note in the thread -- written from the beats through ``read_turn`` (its
    job's read horizon). A restore that discards one of those beats takes
    the pass's turn back with its answer (`keep_spared`). Returns the entry,
    or None when the log no longer holds it."""
    with transaction():
        row = _row(cid, frame_id)
        for entry in row["pass_log"]:
            if entry["pass"] == int(number):
                entry["read"] = int(read_turn or 0)
                _save(cid, frame_id, row)
                return dict(entry)
    return None


def give_back_pass(cid, frame_id, number):
    """A PASS CANCELLED BEFORE IT ANSWERED HAS NOT HAD ITS TURN (review
    R4-1, 2026-10-08): its entry leaves the log, and the pacing counts from
    the pass before it (`pass_due`). A restore cancels a pass that read a
    beat it discards (`core.jobs.cancel_from`), and the pass gives itself
    back the way it hands back the asks it took -- which may land before the
    restore's transaction or after it. Either way holds: the restore keeps
    the log as it stood (`keep_spared`), so a give-back made first is
    kept, and one made after takes the entry off the restored row. Returns
    whether an entry was given back."""
    with transaction():
        row = _row(cid, frame_id)
        log = [e for e in row["pass_log"] if e["pass"] != int(number)]
        if len(log) == len(row["pass_log"]):
            return False
        row["pass_log"] = log
        row["last_pass_turn"] = log[-1]["turn"] if log else None
        _save(cid, frame_id, row)
    return True


def ask_brief(cid, frame_id, text, *, turn_idx=0):
    """Keep a brief the Planner handed the Dramaturge for the player until a
    pass takes it (`take_briefs`). The same text asked again is one ask.
    Returns the briefs now waiting."""
    text = _text(text, BRIEF_CHARS)
    if not text:
        return waiting_briefs(cid, frame_id)
    with transaction():
        row = _row(cid, frame_id)
        row["briefs"] = [b for b in row["briefs"] if b["text"] != text] + [
            {"text": text, "turn_idx": int(turn_idx or 0), "at": time.time()}]
        _save(cid, frame_id, row)
    return list(row["briefs"])


def waiting_briefs(cid, frame_id=None):
    """The briefs no pass has taken yet, oldest first."""
    return list(_row(cid, frame_id)["briefs"])


def take_briefs(cid, frame_id):
    """The waiting briefs' texts, oldest first, and none left waiting: the
    pass that takes them answers them."""
    with transaction():
        row = _row(cid, frame_id)
        taken = row["briefs"]
        if taken:
            row["briefs"] = []
            _save(cid, frame_id, row)
    return [b["text"] for b in taken]


def hand_back_briefs(cid, frame_id, texts, *, failed_turn=None):
    """Briefs a pass took and did not answer -- it was cancelled, or its
    provider failed (``failed_turn``, the beat it failed at: `briefs_due`) --
    wait again, ahead of any asked since.

    NEVER ANSWERED TWICE (review of 2026-10-08, round 4). An ask a
    suggestion still waiting on the Planner already answers -- the pass
    filed it before the cancel or the failure cut it short -- is not handed
    back: that suggestion is marked due as asked instead, so the ask is
    judged at once and answered once. A suggestion already judged answers
    nothing here: the same words asked again later are a new ask. And an ask the
    player has made again since, in the same words, keeps waiting as the
    fresh ask it is: the failed copy put in front of it carried the failed
    beat, and the player's new ask waited a pacing interval behind it."""
    texts = [_text(t, BRIEF_CHARS) for t in texts or () if _text(t, BRIEF_CHARS)]
    if not texts:
        return []
    failed = {} if failed_turn is None else {"failed_turn": int(failed_turn)}
    with transaction():
        row = _row(cid, frame_id)
        waiting = {b["text"] for b in row["briefs"]}
        answering = {}
        for p in row["proposals"]:
            if awaits_planner(p):
                for ask in answered_asks(p):
                    answering.setdefault(ask, p)
        back, dirty = [], False
        for text in dict.fromkeys(texts):
            p = answering.get(text)
            if p is not None:
                if not p["due"]:
                    p["due"] = "asked"
                    dirty = True
                continue
            if text not in waiting:
                back.append(text)
        if back:
            now = time.time()
            row["briefs"] = [{"text": t, "turn_idx": 0, "at": now, **failed}
                             for t in back] + row["briefs"]
            dirty = True
        if dirty:
            _save(cid, frame_id, row)
    return list(_briefs(row["briefs"]))


def briefs_due(cid, frame_id, turn_idx, pace):
    """Whether a waiting ask makes a Dramaturge pass due at beat
    ``turn_idx`` whatever the pacing: one no pass has failed on, at once; one
    a pass took and failed on -- its provider refused or was unreachable --
    once the frame has played ``pace`` of its own beats since (the default
    pace when the passes are off), so a dead provider is not asked again at
    every commit (review R3-7, 2026-10-08). The player asking again is a
    fresh ask, due at once (`ask_brief`)."""
    from core.jobs import story_rewound_past
    from story.mandates import BEATS_PER_PROPOSAL
    from story.room_frontier import _other_frames_beats
    try:
        wait = int(pace)
    except (TypeError, ValueError):
        wait = 0
    wait = wait if wait > 0 else BEATS_PER_PROPOSAL
    for brief in waiting_briefs(cid, frame_id):
        since = brief.get("failed_turn")
        if since is None or turn_idx is None or story_rewound_past(since, turn_idx):
            return True
        played = int(turn_idx) - int(since) - _other_frames_beats(
            cid, frame_id, since, turn_idx)
        if played >= wait:
            return True
    return False


def _proposal_rows_raw(cid):
    """Every era's row of this chat, by its stored key -- read raw, as a
    restore reads, so it answers the same whichever frame is active."""
    from core.db import parse_scoped_world_key
    out = {}
    for r in q("SELECT key, value FROM world WHERE chat_id=? AND key LIKE ?",
               (int(cid), PROPOSALS_KEY + "%")):
        if parse_scoped_world_key(r["key"])[0] != PROPOSALS_KEY:
            continue
        try:
            stored = json.loads(r["value"])
        except (TypeError, ValueError):
            stored = {}
        out[r["key"]] = stored if isinstance(stored, dict) else {}
    return out


def held_briefs(cid):
    """``{stored key: briefs}`` for every era's row with briefs waiting,
    for a restore to read before it rolls the rows back (`keep_briefs`)."""
    out = {}
    for key, stored in _proposal_rows_raw(cid).items():
        briefs = _briefs(stored.get("briefs"))
        if briefs:
            out[key] = briefs
    return out


def keep_briefs(cid, held):
    """After a restore: every era's row waits on exactly the briefs it
    waited on before it (``held``, from `held_briefs`) -- not the ones the
    snapshot happened to hold, which a pass may since have answered. A brief
    is the conversation's, and a restore does not unsay the conversation. An
    era the restore took away takes its briefs with it. Writes raw keys, so
    the caller holds the restore's unscoped view (`active_frame_id` None)."""
    from core.db import parse_scoped_world_key, wset
    rows = _proposal_rows_raw(cid)
    for key in sorted(set(rows) | set(held or {})):
        _base, frame_id = parse_scoped_world_key(key)
        if frame_id is not None and not q(
                "SELECT 1 FROM frames WHERE id=? AND chat_id=?",
                (int(frame_id), int(cid)), one=True):
            continue
        stored = dict(rows.get(key) or {})
        want = _briefs((held or {}).get(key))
        if _briefs(stored.get("briefs")) == want:
            continue
        stored["briefs"] = want
        wset(int(cid), key, stored)


def held_rows(cid):
    """Every era's row as it stands, by stored key, for a restore to read
    before it rolls them back (`keep_spared`)."""
    return _proposal_rows_raw(cid)


def keep_spared(cid, held, turn_idx):
    """After a restore to beat ``turn_idx``: what the Room wrote to these
    rows after the snapshot from beats the restore KEEPS, put back (review
    R3-2, 2026-10-08), and what it built on a beat the restore discards,
    given back. Returns the frame ids whose rows changed.

    The snapshot of beat N is taken as beat N starts, and work from beat N-1
    can still be landing then: a pacing pass's suggestions filed during the
    next beat, or a verdict reached on an earlier beat. A restore spares the
    job that did it (`core.jobs.cancel_from`) and then rolled its writes
    back: rerolling the beat after a pacing beat took that pass's
    suggestions while its note stood in the thread, and the pacing it had
    spent was not re-armed. ``held`` is every era's row before the restore
    (`held_rows`). Kept, each by its own stamp below ``turn_idx``:

    * a proposal the restored row lacks, filed from kept beats (`filed_turn`,
      the newest beat its pass read), as its pass filed it -- open,
      undeliberated, and due at once when it answers the player's ask, which
      then no longer waits as well (a cancelled pass may have handed it back
      before the restore began). A deliberation of one filed after the
      snapshot began while the discarded beat was in play, so what it wrote
      goes;
    * a refusal of a proposal both rows hold, reached by a deliberation
      that began at a kept beat (its judgements' `turn`). A verdict that
      acted -- a package, a grant asked for, a return to the player -- is
      not kept: what it did rolled back with the world and the status row,
      and the proposal is judged again at its bound;
    * THE PASSES THAT HAD THEIR TURN (review R4-1, 2026-10-08): the row's
      pass log as it stood, less every pass recorded at a discarded beat and
      every pass whose answer was read from one (`land_pass`). The pacing
      counts from the newest pass left (`pass_due`), so a pass whose
      suggestions the restore drops has not spent it, nor has one the
      restore cancelled before it answered, which gives its own entry back
      (`give_back_pass`) before the restore or after it. Kept whole, the
      record of a pass that read the next beat's narration stood while
      everything it wrote was dropped, and the story waited a full interval
      for its next suggestion.

    An ask whose ANSWER the restore drops -- a proposal filed from a
    discarded beat, answering the player -- waits again (review R4-1): it is
    the conversation's, and its answer is gone. Not when a proposal still
    waiting on the Planner answers it.

    NOT KEPT: the follow-up's reading (review of 2026-10-08, round 4).
    What a reading concluded -- the proposals it marked due, and the ones
    its deliberation took up -- rolls back with the row, so the reading
    does too, and the replayed commit reads those beats again; kept alone,
    a beat that did bring the story near a suggestion was never asked about
    again, and the suggestion waited its bound.

    Writes raw keys, so the caller holds the restore's unscoped view."""
    from core.db import parse_scoped_world_key, wset
    changed = []
    limit = int(turn_idx)
    rows = _proposal_rows_raw(cid)
    for key, before in sorted((held or {}).items()):
        if not isinstance(before, dict):
            continue
        _base, frame_id = parse_scoped_world_key(key)
        if key not in rows and frame_id is not None and not q(
                "SELECT 1 FROM frames WHERE id=? AND chat_id=?",
                (int(frame_id), int(cid)), one=True):
            continue          # an era the restore took away takes its work
        stored = dict(rows.get(key) or {})
        now = [normalize_proposal(p, frame_id)
               for p in stored.get("proposals") or [] if isinstance(p, dict)]
        by_uid = {p["uid"]: p for p in now}
        dirty, dropped_asks, readded_asks = False, [], []
        for raw in before.get("proposals") or []:
            if not isinstance(raw, dict):
                continue
            p = normalize_proposal(raw, frame_id)
            mine = by_uid.get(p["uid"])
            if mine is None:
                if p["kind"] == "quiet":
                    continue
                if p["filed_turn"] >= limit:
                    dropped_asks.extend(answered_asks(p))
                    continue
                asks = answered_asks(p)
                p.update(status="open", judgements=[], package_uid="",
                         taken_turn=None, due="asked" if asks else "")
                readded_asks.extend(asks)
                now.append(p)
                dirty = True
                continue
            if not awaits_planner(mine):
                continue
            added = [j for j in p["judgements"] if j not in mine["judgements"]]
            if p["status"] == "refused" and added \
                    and all(int(j.get("turn") or 0) < limit for j in added):
                mine.update(status="refused", judgements=p["judgements"], due="")
                dirty = True
        in_play = {ask for p in now if awaits_planner(p) for ask in answered_asks(p)}
        briefs = _briefs(stored.get("briefs"))
        waiting = [b for b in briefs if b["text"] not in set(readded_asks)]
        texts = {b["text"] for b in waiting}
        again = [ask for ask in dict.fromkeys(dropped_asks)
                 if ask not in in_play and ask not in texts]
        if again or len(waiting) != len(briefs):
            stamp = time.time()
            stored["briefs"] = [{"text": ask, "turn_idx": 0, "at": stamp}
                                for ask in again] + waiting
            dirty = True
        log = [e for e in _pass_log(before)
               if e["turn"] < limit and (e["read"] is None or e["read"] < limit)]
        if log != _pass_log(stored):
            stored["pass_log"] = log
            stored["last_pass_turn"] = log[-1]["turn"] if log else None
            dirty = True
        passes = max(int(stored.get("passes") or 0), int(before.get("passes") or 0))
        if passes != int(stored.get("passes") or 0):
            stored["passes"] = passes
            dirty = True
        if dirty:
            stored["proposals"] = now
            wset(int(cid), key, stored)
            changed.append(frame_id)
    return changed


def last_pass_turn(cid, frame_id):
    value = _row(cid, frame_id).get("last_pass_turn")
    return int(value) if value is not None else None


def frame_opening_idx(cid, frame_id):
    """The first beat THIS frame played, or None when it has played none --
    where the Dramaturge's pacing counts from before its first pass."""
    row = q("SELECT MIN(idx) AS m FROM turns WHERE chat_id=? AND frame_id IS ?",
            (int(cid), frame_id), one=True)
    return int(row["m"]) if row and row["m"] is not None else None


def pass_due(cid, frame_id, turn_idx, beats):
    """Whether the Dramaturge's turn has come at beat ``turn_idx``: the
    frame has played ``beats`` beats of its OWN since the last pass -- or,
    before the first pass, since its opening beat -- or the last pass was
    made in a timeline the story has since rewound out of. Returns ``(due,
    why)``; ``why`` says where the count started and how far into the
    interval the frame is, for a reader asking why a commit queued nothing.

    THE FRAME'S OWN BEATS, counted exactly as the fill's back-off counts
    them (`room_frontier.fill_due`, the same helper): turn rows are numbered
    across the whole chat, and a live causality bubble inserts its beats
    into that numbering, so a difference of indices alone would run the
    pacing down early -- two bubbles each playing a beat per player beat
    would bring a pass every two of the player's beats instead of six.

    FROM THE OPENING, NOT AT IT. The opening beat is the Room's own plan
    landing, and a direction read off it alone is read off the scenario; a
    story that has never had a pass is due once it has played one pacing
    interval past its opening. A story already past that -- every story
    written before the pass ran by default -- is due at its next commit.

    ``beats`` 0 IS OFF (`mandates.beats_per_proposal`): the player has said
    they want no suggestions on the Dramaturge's own initiative, and nothing
    here is ever due. Their own ask still runs (`story_planner.planner_reply`).

    A REROLL RE-ARMS THE PACING. The record of the last pass rides this row,
    which a restore rolls back, and the restore cancels a pass still running
    that read the beat it discards (`persist/checkpoints.restore_checkpoint`,
    `core.jobs.cancel_from`): the rerolled beat is asked
    again, as the beat it now is, rather than inheriting a pass that read the
    beat the player threw away. Each reroll of a pacing beat therefore costs
    one more pass (owner question, 2026-10-08). A pass that read only beats
    the restore keeps keeps its record and its suggestions (`keep_spared`)."""
    from core.jobs import story_rewound_past
    from story.room_frontier import _other_frames_beats
    if turn_idx is None:
        return False, "no beat to count from"
    if int(beats) <= 0:
        return False, "the pacing is off: a standing grant names 0 beats"
    beats = max(1, int(beats))
    last = last_pass_turn(cid, frame_id)
    if last is not None and story_rewound_past(last, turn_idx):
        return True, ""
    since = last if last is not None else frame_opening_idx(cid, frame_id)
    if since is None:
        return False, "the frame has played no beat"
    played = int(turn_idx) - since - _other_frames_beats(
        cid, frame_id, since, turn_idx)
    if played >= beats:
        return True, ""
    return False, ("%s at beat %d; %d of %d beats played"
                   % ("last pass" if last is not None else "opened",
                      since, max(0, played), beats))


def direction_wait_beats(pace):
    """The lazy follow-up's bound in the frame's own beats, at a story paced
    ``pace`` (`mandates.beats_per_proposal`): `DIRECTION_WAIT_INTERVALS`
    intervals of it. A pace of 0 -- the player turned the Dramaturge's own
    passes off -- still leaves suggestions from their asks and from before,
    and those wait at the default pace (`mandates.BEATS_PER_PROPOSAL`)."""
    from story.mandates import BEATS_PER_PROPOSAL
    try:
        pace = int(pace)
    except (TypeError, ValueError):
        pace = 0
    return DIRECTION_WAIT_INTERVALS * (pace if pace > 0 else BEATS_PER_PROPOSAL)


def waited_beats(cid, frame_id, proposal, turn_idx):
    """How many of the frame's OWN beats a pending proposal has waited at
    beat ``turn_idx``: since a deliberation last took it up, else since it
    was filed. Counted as the pacing counts them (`pass_due`): a live
    bubble's rows in the chat-wide numbering are not this frame's beats."""
    from core.jobs import story_rewound_past
    from story.room_frontier import _other_frames_beats
    since = proposal.get("taken_turn")
    if since is None:
        since = proposal.get("filed_turn") or 0
    since = int(since)
    if turn_idx is None or story_rewound_past(since, turn_idx):
        return 0
    return max(0, int(turn_idx) - since
               - _other_frames_beats(cid, frame_id, since, turn_idx))


def mark_due(cid, frame_id, reasons):
    """``{uid: why}`` (`DUE_REASONS`): each proposal named that still awaits
    the Planner is due its deliberation now; one already due keeps its
    reason. Returns the uids marked."""
    marked = []
    with transaction():
        row = _row(cid, frame_id)
        for p in row["proposals"]:
            why = (reasons or {}).get(p["uid"])
            if why not in DUE_REASONS or not awaits_planner(p) or p["due"]:
                continue
            p["due"] = why
            marked.append(p["uid"])
        if marked:
            _save(cid, frame_id, row)
    return marked


def due_proposals(cid, frame_id=None):
    """The proposals due their deliberation now, oldest first."""
    return [p for p in proposals(cid, frame_id) if awaits_planner(p) and p["due"]]


def take_proposals(cid, frame_id, uids, turn_idx):
    """A deliberation takes these up at beat ``turn_idx``: no longer due,
    and stamped with the beat, so one it leaves pending (a failed call, a
    cancel) waits its bound again from here (`waited_beats`) instead of
    being taken again at once. Returns the rows taken."""
    uids = {str(u) for u in uids or ()}
    taken = []
    with transaction():
        row = _row(cid, frame_id)
        for p in row["proposals"]:
            if p["uid"] in uids and awaits_planner(p):
                p["due"] = ""
                p["taken_turn"] = int(turn_idx or 0)
                taken.append(dict(p))
        if taken:
            _save(cid, frame_id, row)
    return taken


def follow_up_turn(cid, frame_id=None):
    """The newest beat the follow-up's decision has read, or None."""
    return _row(cid, frame_id)["follow_up_turn"]


def record_follow_up(cid, frame_id, turn_idx):
    """The follow-up has read the stream through beat ``turn_idx``."""
    with transaction():
        row = _row(cid, frame_id)
        row["follow_up_turn"] = int(turn_idx or 0)
        _save(cid, frame_id, row)
    return row


def projection(proposal):
    """The spoiler-safe face of a proposal for the status row: its kind,
    its title (the Dramaturge's to keep spoiler-safe) and its state --
    never what it wants true."""
    return {"uid": proposal["uid"], "kind": "proposal",
            "label": "%s: %s" % (proposal["kind"], proposal["title"]),
            "state": proposal["status"]}
