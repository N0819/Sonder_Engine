"""Artifacts: a claim nailed to a wall, read rather than heard.

The carrier network's fourth body, and the first one that does not move. A
notice, a proclamation, a wanted bill is information made THING: it stands in
one room, it informs only whoever comes and reads it, and tearing it down
stops it informing anyone further -- which is the artifact equivalent of
silencing a courier, and what makes it part of the world rather than a
message box the engine whispers through.

Three rules carry the module, each the same physics the rest of the network
already obeys:

**Posting is publication of what the POSTER holds, where the poster stands.**
The poster must be registered and must hold the report (or be inventing a
claim, which lands on their own row as `invented` exactly as a spoken lie
does -- a wanted bill naming the player for something they never did enters
through the same door as a true one, and nothing a reader can reach marks it
false). The bill goes up in the room the poster's body is in: posting across
a distance is a courier carrying a letter, not a new power.

**Reading is a COPY, not a mouth.** A posted notice does not degrade by
retelling -- every reader takes in the same words -- so a read copy carries
the claim VERBATIM at the retelling count it was posted with, provenance
`read`, attributed to the thing itself ("a wanted bill nailed to the post"),
never to a person. A copy of a copy still degrades where it always did: a
bill posted from a rumor carries the rumor's already-faded wording, and a
mouth repeating what the bill said costs a retelling like any other mouth.
The counts never move at the wall.

**Torn down is silenced.** A removed artifact refuses every later read, drops
off every perception surface, and teaches a passing caravan nothing. The
record of it is kept (capped) the way a finished courier route is: a road,
not an archive.

THE CEILING IS PRESENTATION, NEVER INFORMATION. `schedule_artifact_wording`
mints the bill's actual wording -- the proclamation's formality, the woodcut
caption -- with one small out-of-band call, off the player's critical path,
landed onto the artifact only if it still stands when the job returns (the
`land_profile_ticks` rollback discipline). What a reader ACQUIRES is always
the claim envelope; the authored `text` is what the narrator may quote. With
no model configured the floor is whole: the artifact posts, reads, and tears
down exactly the same, and the text stays empty.

Persistence is a frame-scoped world key like the couriers': checkpoints
snapshot the world table verbatim, so a rewind takes the bill off the wall
and a branch that never posted it has a bare post.
"""

from __future__ import annotations

import hashlib
import json
from llm.prompts import get_prompt

#: The world-KV key artifacts live under, spelled once, frame-scoped in
#: `db.FRAME_SCOPED_WORLD_KEYS`.
ARTIFACTS_WORLD_KEY = "artifacts"

#: How many artifacts may stand at once. A coherence limit like MAX_CROWDS:
#: past this the Director is papering rooms nobody reads.
MAX_ARTIFACTS = 8

#: How many removed artifacts to keep as a record beside the standing ones.
_REMOVED_KEPT = 6

#: The authored wording's bound, enforced on the write path. Long enough for
#: a proclamation, short enough that the mint cannot smuggle a scene in.
TEXT_MAX_WORDS = 80

#: How many times the wording mint may fail before the artifact is left
#: plain forever. Fail toward not spending: a provider that is down or
#: absent costs two cheap failures, never a retry per beat for the rest of
#: the story.
_WORDING_ATTEMPT_CAP = 2

POSTED = "posted"
REMOVED = "removed"

OP_POST = "post"
OP_READ = "read"
OP_REMOVE = "remove"
_OPS = (OP_POST, OP_READ, OP_REMOVE)


def artifact_uid(chat_id, room, turn, description):
    """A stable id minted once, from what the artifact IS. Never a name."""
    material = "|".join([
        str(int(chat_id)), str(room or ""), str(int(turn)),
        " ".join(str(description or "").split()).casefold(),
    ])
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return "artifact:%s" % digest


def artifact_voice(artifact):
    """How a read copy is attributed. The THING, never a person.

    "a wanted bill nailed to the post" is a source a mind can weigh -- it is
    obviously paper, obviously put up by somebody who is not standing there
    to be questioned. The same rule as `crowd_voice` and `courier_voice`,
    for the same reason.
    """
    if not isinstance(artifact, dict):
        return "a posted notice"
    return str(artifact.get("description") or "").strip() or "a posted notice"


def standing_artifacts(cid):
    """Every artifact row this era holds, straight off the world key."""
    from core.db import wget

    return [a for a in wget(cid, ARTIFACTS_WORLD_KEY, []) or []
            if isinstance(a, dict)]


def posted_in_room(artifacts, room_uid):
    """Artifacts still standing in one room, in a stable order."""
    room = str(room_uid or "")
    if not room:
        return []
    return sorted(
        (a for a in (artifacts or [])
         if isinstance(a, dict) and a.get("status") == POSTED
         and str(a.get("room") or "") == room),
        key=lambda a: str(a.get("uid") or ""))


def new_artifact(chat_id, *, room, turn, description, report, posted_by):
    """One artifact, standing where it was nailed up."""
    return {
        "uid": artifact_uid(chat_id, room, turn, description),
        "room": str(room),
        "description": " ".join(str(description or "").split())[:80]
                       or "a posted notice",
        "status": POSTED,
        "posted_turn": int(turn),
        # Who nailed it up -- provenance for the record and the rewind, never
        # shown to a reader: a bill does not sign itself, and a mind that
        # knew the poster's name without a signature would know more than
        # reading can deliver.
        "posted_by": str(posted_by or ""),
        "report": dict(report or {}),
        # The authored wording, minted out of band by the ceiling; empty is
        # the floor and the floor is complete.
        "text": "",
        "wording_failures": 0,
    }


def reading_copy(artifact, reader_room, turn):
    """The reader's copy of what this artifact says. Pure.

    Verbatim, at the posted retelling count, provenance `read`: a copy is
    not a mouth. Returns ``None`` for a bill with nothing legible on it.
    """
    held = (artifact or {}).get("report") or {}
    claim = " ".join(str(held.get("claim") or "").split())
    if not claim:
        return None
    return {
        "world_event_id": str(held.get("world_event_id") or ""),
        "source_event_id": str(held.get("source_event_id") or ""),
        "claim": claim,
        "kind": str(held.get("kind") or ""),
        "occurred_at": float(held.get("occurred_at") or 0.0),
        "acquired_turn": int(turn),
        "acquired_location": str(reader_room or ""),
        "current_location": str(reader_room or ""),
        "route": [str(reader_room or "")],
        "hops": 0,
        "retellings": max(0, int(held.get("retellings") or 0)),
        "told_by": artifact_voice(artifact),
        "provenance": "read",
    }


# --------------------------------------------------------------------------
# The impure half: reads the cast, writes state. Mirrors couriers.py and
# runs inside the same `information_carriers` commit domain and transaction.
# --------------------------------------------------------------------------


def run_artifacts(ctx, scene, ops):
    """Apply this beat's artifact ops. Returns ``(metrics, rejected)``.

    Every refusal is deterministic and mirrors the courier physics: the
    poster must be registered and must HOLD what the bill asserts (or be
    inventing a claim, which lands on their own row as `invented`); the bill
    goes up where the poster's body is; and nobody reads or tears down a
    bill from a room it is not in.
    """
    from core.db import wget, wset
    from world.spatial import room_of

    from story.carriers import REPORT_CAP, STATE_KEY, _cast_index, save_state
    from story.couriers import _give_report, _hold_report, _player_name

    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    turn = int(ctx.turn.idx)

    artifacts = [dict(a) for a in wget(cid, ARTIFACTS_WORLD_KEY, []) or []
                 if isinstance(a, dict)]
    before = json.dumps(artifacts, sort_keys=True, ensure_ascii=False)
    index = _cast_index(cid, frame_id, scene, chat=getattr(ctx, "chat", None))
    by_uid = {str(a.get("uid") or ""): a for a in artifacts}
    rejected = []
    metrics = {"artifact_ops_offered": 0, "artifacts_posted": 0,
               "artifacts_read": 0, "artifacts_removed": 0,
               "artifacts_standing": 0}

    player = _player_name(ctx)

    def body_room(name):
        """Where the named body is, or "" for nobody the story can place."""
        key = str(name or "").strip().casefold()
        if not key:
            return ""
        entry = index.get(key)
        if entry is not None:
            return str(entry.get("room") or "")
        if player and key == player.casefold():
            return str(room_of(scene, player) or "")
        return ""

    ops = [op.dict() if hasattr(op, "dict") else op for op in (ops or [])]
    for raw in ops:
        if not isinstance(raw, dict):
            rejected.append("artifact op was not an object")
            continue
        metrics["artifact_ops_offered"] += 1
        op = " ".join(str(raw.get("op") or OP_POST).split()).casefold()
        if op not in _OPS:
            rejected.append("unknown artifact op %r" % (raw.get("op"),))
            continue

        if op == OP_POST:
            poster_key = str(raw.get("poster") or "").strip().casefold()
            poster = index.get(poster_key)
            if poster is None:
                rejected.append(
                    "artifact poster %r is not a registered character; a "
                    "bill is nailed up by somebody's hands"
                    % (raw.get("poster"),))
                continue
            room = str(poster.get("room") or "")
            if not room:
                rejected.append("%s is nowhere the scene can place; no bill "
                                "goes up in an unknown room" % poster["name"])
                continue
            asked_room = str(raw.get("room") or "").strip()
            if asked_room and asked_room != room:
                rejected.append(
                    "%s is in %s, not %s; a notice is posted where the "
                    "poster stands -- send a courier with a letter to post "
                    "it further away" % (poster["name"], room, asked_room))
                continue
            if sum(1 for a in artifacts if a.get("status") == POSTED) \
                    >= MAX_ARTIFACTS:
                rejected.append("%d notices already stand; no more until "
                                "one comes down" % MAX_ARTIFACTS)
                continue
            event_id = str(raw.get("world_event_id") or "").strip()
            held = _hold_report(poster, event_id) if event_id else None
            if held is None and not event_id \
                    and str(raw.get("claim") or "").strip():
                from story.carriers import _invented_claim

                invented = _invented_claim(raw.get("claim"), ctx, poster)
                state = poster.get("state") or {}
                state[STATE_KEY] = (
                    [dict(r) for r in state.get(STATE_KEY) or []
                     if isinstance(r, dict)] + [invented])[-REPORT_CAP:]
                save_state(cid, poster, state, frame_id=frame_id)
                poster["state"] = state
                held = invented
            if held is None:
                rejected.append(
                    "%s does not carry %r and cannot post it on a wall"
                    % (poster["name"], event_id or "that report"))
                continue
            envelope = {
                "world_event_id": str(held.get("world_event_id") or ""),
                "source_event_id": str(held.get("source_event_id") or ""),
                # What the poster HOLDS, written down: writing is not a
                # retelling (the letter precedent), so a bill posted from a
                # rumor is a verbatim copy of the rumor at the rumor's own
                # faded count -- the copy-of-a-copy that already degraded at
                # every mouth it crossed.
                "claim": " ".join(str(held.get("claim") or "").split()),
                "kind": str(held.get("kind") or ""),
                "occurred_at": float(held.get("occurred_at") or 0.0),
                "retellings": max(0, int(held.get("retellings") or 0)),
            }
            artifact = new_artifact(
                cid, room=room, turn=turn,
                description=raw.get("description"), report=envelope,
                posted_by=poster["name"])
            if artifact["uid"] in by_uid:
                rejected.append("that notice is already on the wall")
                continue
            artifacts.append(artifact)
            by_uid[artifact["uid"]] = artifact
            metrics["artifacts_posted"] += 1
            continue

        uid = str(raw.get("artifact_id") or "").strip()
        artifact = by_uid.get(uid)
        if artifact is None:
            rejected.append("no artifact %r on any wall; the engine mints "
                            "these ids and perception shows them" % uid)
            continue
        if artifact.get("status") != POSTED:
            # THE point of destructibility: a bill that came down informs
            # nobody further, however many beats later somebody looks for it.
            rejected.append("the %s is no longer standing; it can inform "
                            "nobody" % artifact_voice(artifact))
            continue

        if op == OP_READ:
            reader_key = str(raw.get("reader") or "").strip().casefold()
            reader = index.get(reader_key)
            reader_room = body_room(raw.get("reader"))
            if not reader_room:
                rejected.append("artifact read by %r, whom the story does "
                                "not know" % (raw.get("reader"),))
                continue
            if reader_room != str(artifact.get("room") or ""):
                rejected.append(
                    "%s is not where the %s hangs; a notice is read in "
                    "front of it" % (raw.get("reader"),
                                     artifact_voice(artifact)))
                continue
            copy = reading_copy(artifact, reader_room, turn)
            if copy is None:
                rejected.append("the %s has nothing legible on it"
                                % artifact_voice(artifact))
                continue
            if reader is not None:
                if _give_report(cid, frame_id, reader, copy):
                    metrics["artifacts_read"] += 1
                else:
                    rejected.append("%s already knows what the %s says"
                                    % (reader["name"],
                                       artifact_voice(artifact)))
            elif player and reader_key == player.casefold():
                # The player's own knowledge is the transcript; the resolve
                # narrates the wording. The read is still real: the count
                # records that the wall informed somebody.
                metrics["artifacts_read"] += 1
            continue

        if op == OP_REMOVE:
            by = raw.get("by")
            by_room = body_room(by)
            if not by_room:
                rejected.append(
                    "an artifact is torn down by somebody, somewhere; %r "
                    "is not a body the story can place" % (by,))
                continue
            if by_room != str(artifact.get("room") or ""):
                rejected.append(
                    "%s is not where the %s hangs; a bill is torn down off "
                    "its own wall" % (by, artifact_voice(artifact)))
                continue
            removed = dict(artifact)
            removed["status"] = REMOVED
            removed["removed_turn"] = turn
            removed["removed_manner"] = " ".join(
                str(raw.get("manner") or "").split())[:40]
            artifacts[artifacts.index(artifact)] = removed
            by_uid[uid] = removed
            metrics["artifacts_removed"] += 1
            continue

    standing = [a for a in artifacts if a.get("status") == POSTED]
    done = [a for a in artifacts if a.get("status") != POSTED]
    artifacts = done[-_REMOVED_KEPT:] + standing

    if json.dumps(artifacts, sort_keys=True, ensure_ascii=False) != before:
        wset(cid, ARTIFACTS_WORLD_KEY, artifacts)
    metrics["artifacts_standing"] = len(standing)
    metrics["artifact_rejected"] = len(rejected)
    return metrics, rejected


# --------------------------------------------------------------------------
# The ceiling: authored wording, one small call, off the critical path.
# --------------------------------------------------------------------------


def schedule_artifact_wording(ctx):
    """Queue the wording mint for freshly posted artifacts. Returns Job or
    None.

    Called from the commit tail, AFTER the turn's facts are durable, on the
    `schedule_profile_ticks` terms: a failure is a warning, never a
    rollback, and a turn starting never cancels the job. Gated on the
    rumor ledger's CEILING -- the floor never spends -- and on the artifact
    still lacking text with attempts left, so a dead provider costs a
    bounded number of cheap failures rather than a retry per beat forever.
    """
    from core import jobs
    from core.db import wget
    from world.living_world import living_world_allows, living_world_config

    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    turn_idx = int(ctx.turn.idx)
    if not living_world_allows(
            living_world_config(cid), "rumor_ledger", "ceiling"):
        return None
    pending = [
        dict(a) for a in wget(cid, ARTIFACTS_WORLD_KEY, []) or []
        if isinstance(a, dict) and a.get("status") == POSTED
        and not str(a.get("text") or "").strip()
        and int(a.get("wording_failures") or 0) < _WORDING_ATTEMPT_CAP]
    if not pending:
        return None

    # The deterministic invention guard's roster: a minted wording may name
    # only people the CLAIM already names, and the roster is how the guard
    # knows which words are people. Gathered at schedule time, on the turn
    # thread, where the cast is already loaded. An unreadable roster (bare
    # test doubles) degrades to no name guard rather than no wording -- the
    # word cap still bounds the mint, and failing the whole ceiling over a
    # diagnostic roster would be the guard outranking the feature.
    try:
        from persist.commit import _registered_name_roster

        roster = [str(n) for n in
                  _registered_name_roster(ctx.chat, getattr(ctx, "cast", []))]
    except Exception:  # noqa: BLE001 - scheduling never raises
        roster = []

    def _produce(job):
        from core.db import active_frame_id

        token = active_frame_id.set(frame_id)
        try:
            landed = []
            for artifact in pending:
                if job.cancelled.is_set():
                    break
                text, error = mint_wording(artifact, roster)
                landed.append(land_artifact_wording(
                    cid, artifact.get("uid"), text, error,
                    base_turn=turn_idx))
            return {"artifacts": landed}
        finally:
            active_frame_id.reset(token)

    return jobs.submit(
        cid, "artifact_wording:t%d:%s" % (
            turn_idx, ",".join(sorted(str(a.get("uid")) for a in pending))),
        _produce, base_turn=turn_idx)


def mint_wording(artifact, roster):
    """One small call for one artifact's wording. Returns ``(text, error)``.

    The claim is the information; the wording is dress. Validation is
    deterministic and fails toward the plain floor: a wording over the word
    cap, or one that names a registered character the claim itself does not
    name, is refused -- an authored bill must not put a name into a room
    that the carrier network never delivered there.
    """
    from llm.providers import chat_complete

    held = (artifact or {}).get("report") or {}
    claim = " ".join(str(held.get("claim") or "").split())
    if not claim:
        return "", "nothing legible to word"
    sys = get_prompt("artifact_wording")
    user = json.dumps({
        "artifact": artifact_voice(artifact),
        "claim": claim,
    }, ensure_ascii=False)
    last_error = "no attempt"
    for _attempt in range(2):
        try:
            out = json.loads(chat_complete(
                "utility", sys, user, temperature=0.7, max_tokens=400))
        except Exception as exc:  # noqa: BLE001 - recorded, never raised
            last_error = "%s: %s" % (type(exc).__name__, str(exc)[:200])
            continue
        if not isinstance(out, dict):
            last_error = "output was not an object"
            continue
        text = " ".join(str(out.get("text") or "").split())
        if not text:
            last_error = "text missing or empty"
            continue
        # split() counts one "word" for a whole Japanese notice, so the cap
        # never fired. Characters are the language-neutral measure; the
        # multiplier is the rough words-to-characters ratio for English prose
        # so the English bound is unchanged in practice.
        if (len(text.split()) > TEXT_MAX_WORDS
                or len(text) > TEXT_MAX_WORDS * 6):
            last_error = ("text runs past %d words: a bill is not a scene"
                          % TEXT_MAX_WORDS)
            continue
        lowered = text.casefold()
        claim_lowered = claim.casefold()
        invented = [n for n in roster
                    if n and n.casefold() in lowered
                    and n.casefold() not in claim_lowered]
        if invented:
            last_error = ("wording names %r, whom the claim does not"
                          % invented[0])
            continue
        return text, ""
    return "", last_error


def land_artifact_wording(cid, uid, text, error, *, base_turn):
    """Write a minted wording, unless the wall changed underneath it.

    The `land_profile_ticks` discipline: the job ran against turn N, and by
    the time it lands the player may have rewound past the posting, torn
    the bill down, or branched into an era that never had it. The artifact
    must still EXIST, still STAND, and still be blank -- anything else
    discards the wording, loudly in the returned record, and never raises.
    A failure lands as a counted failure so the scheduler stops paying
    after `_WORDING_ATTEMPT_CAP`.
    """
    from core.db import wget, wset

    uid = str(uid or "")
    record = {"uid": uid, "landed": False, "error": str(error or "")}
    try:
        artifacts = [dict(a) for a in wget(cid, ARTIFACTS_WORLD_KEY, []) or []
                     if isinstance(a, dict)]
        target = None
        for artifact in artifacts:
            if str(artifact.get("uid") or "") == uid:
                target = artifact
                break
        if target is None:
            record["error"] = record["error"] or \
                "artifact gone before wording landed (rewind or branch)"
            return record
        if target.get("status") != POSTED:
            record["error"] = record["error"] or \
                "artifact came down before wording landed"
            return record
        if str(target.get("text") or "").strip():
            record["error"] = record["error"] or "artifact already worded"
            return record
        if int(target.get("posted_turn") or 0) > int(base_turn):
            # A same-uid artifact posted AFTER the job's base turn is a
            # different bill wearing a recycled id; its wording was not
            # minted from this claim's era.
            record["error"] = "artifact re-posted after the job's base turn"
            return record
        if text:
            target["text"] = str(text)
            record["landed"] = True
        else:
            target["wording_failures"] = \
                int(target.get("wording_failures") or 0) + 1
        wset(cid, ARTIFACTS_WORLD_KEY, artifacts)
    except Exception as exc:  # noqa: BLE001 - a landing never raises
        record["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:200])
    return record
