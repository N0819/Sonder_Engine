"""Who an older memory had in it (`memories.about`), backfilled.

The tag landed in v43 (2026-09-29; `docs/guides/MEMORY.md` §1 and §3): every
memory a mind mints carries, host-only, the engine's names of the bodies that
were there, so a ponder by a name the mind has since learned reaches the rows
that never say it -- written as "the young woman" before she said who she was.
Rows minted before v43 carry no tag, and nothing gave them one
(`UNBUILT_CHARACTERS.md` §6.17). Measured 2026-10-05: 17,011 of the owner's
17,121 turn rows; and the one wrong answer of the lookups probe was exactly
such a row, which the ponder's ABOUT lane, built for it, could not reach
(`docs/experiments/CHARACTER_LOOKUPS_2026_10_05.md` §4).

THE MINT RULE, NOT A SECOND ONE. Each row is tagged by
`commit_memory._memory_about` itself, fed what it is fed at commit, read back
from what the turn left behind:

- the scene, the known-names map and the conditions (a disguise that kept the
  mind from recognising a body keeps it out of the tag, as at commit) from the
  checkpoint `turn_new` writes as turn N begins -- MEASURED, not assumed:
  against the 110 rows the mint itself tagged in the owner's db (2026-10-05),
  the people standing in the world before the turn match the mint's people
  in 106 of 106 rows, and the world after it (checkpoint N+1) in 104 of 110,
  missing exactly the bodies that moved during the beat. The checkpoint after
  is the fallback where the one before is gone, then the live world for the
  newest turn;
- the lines the mind heard, from the turn's own stored steps: the resolve's
  dialogue log and the background reactions that fired, a line heard when its
  words are in the mind's view -- the same test the mint makes, with the
  player's line under the persona's own name, a mind's own lines skipped.

A RECONCILER, NOT A MIGRATION. A checkpoint restore puts memory rows back as
they were -- untagged -- exactly as it puts back stale vectors
(`memory_vectors.start_rebuild_if_needed`'s note). So this runs in the
background at startup and synchronously after a restore (a rerun recalls the
moment the restore is done, and a background heal would land after it), over
rows whose tag is empty; a row with nobody else in it is written `[]`, which
every reader reads as empty, so it is computed once.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict

from core.db import q, qi, transaction

logger = logging.getLogger(__name__)

_LOCKS_GUARD = threading.Lock()
_CHAT_LOCKS = defaultdict(threading.Lock)

_TURN_STEPS = ("director_resolve", "director_establish", "background_react",
               "perception_outcome", "perception_establish")


def _chat_lock(chat_id):
    with _LOCKS_GUARD:
        return _CHAT_LOCKS[int(chat_id)]


def _untagged(chat_id):
    """This chat's turn rows with no tag, by turn: the rows the mint gave a
    tag to and v43 never reached (a greeting's seeds are a story's prehistory,
    minted with none, and stay so)."""
    rows = q(
        "SELECT id, char_id, turn_id, turn_idx, kind, category, content, event_key "
        "FROM memories WHERE chat_id=? AND (about IS NULL OR about='') "
        "AND turn_idx IS NOT NULL AND turn_idx>=0 "
        "AND COALESCE(event_key,'') NOT LIKE 'greeting_seed:%' ORDER BY turn_idx, id",
        (chat_id,))
    by_turn = defaultdict(list)
    for r in rows:
        by_turn[int(r["turn_idx"])].append(dict(r))
    return by_turn


def _world_key(key, frame_id):
    """The stored key a frame-scoped world value lives under in `frame_id`."""
    from core.db import _scoped_world_key, active_frame_id
    token = active_frame_id.set(frame_id)
    try:
        return _scoped_world_key(key)
    finally:
        active_frame_id.reset(token)


def _conditions(rows, kind):
    """The active `kind` rows of a snapshot's condition table, in the live
    read's order (`started_at`, then the order stored, which is rowid's)."""
    picked = [(i, r) for i, r in enumerate(rows or [])
              if isinstance(r, dict) and r.get("kind") == kind and int(r.get("active", 1) or 0) == 1]
    picked.sort(key=lambda ir: (float(ir[1].get("started_at") or 0.0), ir[0]))
    return [r for _i, r in picked]


def _from_checkpoint(chat_id, idx, scene_key, known_key):
    """`(scene, known, conditions)` from checkpoint `idx`, or None. One parse
    of the blob for all three (a checkpoint runs to megabytes)."""
    from story.scene import disguises_from_rows, transformations_from_rows
    row = q("SELECT json_extract(blob, ?, ?, '$.world_conditions') AS got "
            "FROM checkpoints WHERE chat_id=? AND turn_idx=?",
            ('$.world."%s"' % scene_key.replace('"', '\\"'),
             '$.world."%s"' % known_key.replace('"', '\\"'), chat_id, idx), one=True)
    if row is None or not row["got"]:
        return None
    try:
        scene, known, conditions = json.loads(row["got"])
    except (TypeError, ValueError):
        return None
    if not isinstance(scene, dict) or not scene:
        return None
    return (scene, known if isinstance(known, dict) else {},
            disguises_from_rows(_conditions(conditions, "physical_disguise")),
            transformations_from_rows(_conditions(conditions, "physical_transformation")))


def _world_at(chat_id, turn_idx, frame_id, newest):
    """`(scene, known, disguises, transformations)` as the mint read them for
    turn `turn_idx` -- the checkpoint written as the turn began, else the one
    after it, else the live world for the newest turn -- or None."""
    from story.scene import active_disguises, active_transformations
    scene_key, known_key = _world_key("scene", frame_id), _world_key("known", frame_id)
    for idx in (turn_idx, turn_idx + 1):
        got = _from_checkpoint(chat_id, idx, scene_key, known_key)
        if got is not None:
            return got
    if not newest:
        return None
    from core.db import wget_for_frame
    return (wget_for_frame(chat_id, "scene", frame_id, {}) or {},
            wget_for_frame(chat_id, "known", frame_id, {}) or {},
            active_disguises(chat_id), active_transformations(chat_id))


def _turn_steps(turn_id):
    out = {}
    if turn_id is None:
        return out
    for r in q("SELECT s.key, v.content FROM steps s JOIN variants v ON v.step_id=s.id "
               "AND v.active=1 WHERE s.turn_id=? AND s.key IN (%s)"
               % ",".join("?" * len(_TURN_STEPS)), (turn_id, *_TURN_STEPS)):
        try:
            content = json.loads(r["content"] or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(content, dict):
            out[r["key"]] = content
    return out


class _Speakers:
    """Who a line's speaker is, for one chat: the commit's own answer
    (`_is_player`; the persona's name for the player), asked once per speaker
    -- it normalises the persona's whole card on every call, 20 ms a line, and
    the answer cannot change within a chat."""

    def __init__(self, chat):
        self.chat = chat
        self._player = {}
        self._persona = None

    def name(self, speaker):
        from persist.commit import _is_player
        if speaker not in self._player:
            self._player[speaker] = bool(_is_player(speaker, self.chat))
        if not self._player[speaker]:
            return speaker
        if self._persona is None:
            from story.character_schema import persona_name
            from story.scene import persona_of
            self._persona = persona_name(persona_of(self.chat)) or ""
        return self._persona or speaker


def _heard(steps, speakers, observer, view):
    """`[(speaker, addressee, words)]` of the lines this mind heard this turn:
    the commit's own test (`prepare_memory_commit`), on what the turn stored."""
    from persist.commit import _background_fired_reactions, _quote_body
    res = steps.get("director_resolve") or steps.get("director_establish") or {}
    dlog = list(res.get("dialogue_log") or [])
    for fired in _background_fired_reactions(steps.get("background_react")):
        dlog.append(fired["dialogue_log_entry"])
    out = []
    for d in dlog:
        if not isinstance(d, dict):
            continue
        spk = speakers.name(str(d.get("speaker", "") or ""))
        if spk == observer:
            continue
        target = str(d.get("intended_target") or "").strip()
        quote = d.get("exact_quote", "") or ""
        words = _quote_body(quote)
        if words and view and (quote in view or words in view):
            out.append((spk, target, words))
    return out


def _observer_name(chat_id, char_id):
    from story.character_schema import character_name
    from story.scene import chat_character_sheet
    sheet = chat_character_sheet(chat_id, char_id)
    if sheet is None:
        row = q("SELECT sheet FROM characters WHERE id=?", (char_id,), one=True)
        try:
            sheet = json.loads(row["sheet"] or "{}") if row else {}
        except (TypeError, ValueError):
            sheet = {}
    return character_name(sheet or {})


def backfill_chat(chat_id):
    """Tag this chat's untagged turn rows by the mint rule; never raises.
    Returns `{"tagged", "nobody", "skipped"}`."""
    counts = {"tagged": 0, "nobody": 0, "skipped": 0}
    try:
        with _chat_lock(chat_id):
            _backfill_chat(int(chat_id), counts)
    except Exception as exc:  # noqa: BLE001 -- a maintenance pass must never fail its caller
        logger.warning("memory: about-tag backfill of chat %s stopped: %s", chat_id, exc)
    return counts


def _backfill_chat(chat_id, counts):
    from core.pipeline_context import ChatData
    from mind.memory import _storage_json
    from persist.commit import _memory_about, _room_of

    by_turn = _untagged(chat_id)
    if not by_turn:
        return
    chat_row = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    if chat_row is None:
        return
    chat = ChatData.from_row(chat_row)
    speakers = _Speakers(chat)
    newest = q("SELECT MAX(idx) AS i FROM turns WHERE chat_id=?", (chat_id,), one=True)
    newest = int(newest["i"]) if newest and newest["i"] is not None else None
    names = {}
    writes = []
    for turn_idx, rows in sorted(by_turn.items()):
        turn = None
        turn_ids = {r["turn_id"] for r in rows if r.get("turn_id") is not None}
        if len(turn_ids) == 1:
            turn = q("SELECT id, frame_id FROM turns WHERE id=?", (next(iter(turn_ids)),), one=True)
        if turn is None:
            turn = q("SELECT id, frame_id FROM turns WHERE chat_id=? AND idx=? ORDER BY id DESC",
                     (chat_id, turn_idx), one=True)
        frame_id = turn["frame_id"] if turn is not None else None
        world = _world_at(chat_id, turn_idx, frame_id, newest is not None and turn_idx == newest)
        if world is None:
            counts["skipped"] += len(rows)
            continue
        scene, known, disguises, transformations = world
        steps = _turn_steps(turn["id"]) if turn is not None else {}
        views = ((steps.get("perception_outcome") or {}).get("views")
                 or (steps.get("perception_establish") or {}).get("views") or {})
        for char_id in sorted({r["char_id"] for r in rows}):
            if char_id not in names:
                names[char_id] = _observer_name(chat_id, char_id)
            observer = names[char_id]
            room = _room_of(scene, observer)
            heard = _heard(steps, speakers, observer, str(views.get(str(char_id)) or ""))
            for row in (r for r in rows if r["char_id"] == char_id):
                if row["kind"] == "episodic":
                    extra = [n for spk, tgt, _w in heard for n in (spk, tgt) if n]
                elif row["kind"] == "dialogue":
                    extra = [n for spk, tgt, words in heard
                             if words in str(row["content"] or "") for n in (spk, tgt) if n]
                else:
                    extra = []
                about = _memory_about(scene, observer, room, known, disguises,
                                      transformations, extra=extra)
                writes.append((_storage_json(about) if about else "[]", row["id"]))
                counts["tagged" if about else "nobody"] += 1
    if writes:
        with transaction():
            for value, row_id in writes:
                qi("UPDATE memories SET about=? WHERE id=? AND (about IS NULL OR about='')",
                   (value, row_id))


def backfill_all():
    """Every chat with untagged turn rows, one at a time; never raises.
    Returns the totals and the seconds taken."""
    t0 = time.time()
    totals = {"chats": 0, "tagged": 0, "nobody": 0, "skipped": 0}
    try:
        chats = [r["chat_id"] for r in q(
            "SELECT DISTINCT chat_id FROM memories WHERE (about IS NULL OR about='') "
            "AND turn_idx IS NOT NULL AND turn_idx>=0 "
            "AND COALESCE(event_key,'') NOT LIKE 'greeting_seed:%'")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory: about-tag backfill could not list chats: %s", exc)
        return {**totals, "seconds": 0.0}
    for chat_id in chats:
        counts = backfill_chat(chat_id)
        totals["chats"] += 1
        for k in ("tagged", "nobody", "skipped"):
            totals[k] += counts[k]
    totals["seconds"] = round(time.time() - t0, 2)
    return totals
