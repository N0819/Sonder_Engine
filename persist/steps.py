"""The steps/variants read: one step's active content, in one place.

A step's output lives in `variants.content` as opaque JSON, one active row
per step, and reading it back is the same question wherever it is asked --
the pipeline rehydrating a rerun, an extension asking what a stage produced,
a projection asking what a viewer was shown, a debug panel quoting a beat.

It lives HERE, next to the table's other readers (`persist/checkpoints.py`,
`persist/pipeline_trace.py`), rather than in `agents/storage.py`, for one
reason: importing `agents.storage` runs `agents/__init__.py`, which pulls the
whole pipeline in. A read-only projection that must answer a panel refresh
without the agent runtime could not use it, so `web/story_view.py` wrote the
query out a second time -- and the copy kept the engine's own repair log that
this one strips (review 2026-09-07, B23). This module imports `core.db` and
nothing else, so there is no version of that question left to answer.
"""

from __future__ import annotations

import json

from core.db import q

# Reserved key on a step's saved content carrying what the DETERMINISTIC layer
# did to that step's output: repairs it made, and which steps it ran beside.
# Written by `agents.runtime._with_engine_notes`, read by the pipeline UI.
#
# It lives in the content rather than in a column on purpose. It is
# per-variant by nature (a reroll repairs differently), it rides every
# archive, branch, checkpoint and trace for free because those all carry step
# content as opaque JSON, and it needs no migration.
ENGINE_NOTES_KEY = "_engine_notes"


def _parsed(raw):
    """One stored variant body, parsed and stripped of the engine's notes.

    The parse is deliberately NOT guarded: every writer goes through
    `json.dumps` (`agents.storage.save_step` and the manual edit route alike),
    so unparseable content is a broken database rather than an expected
    answer, and swallowing it would hide that.

    The engine notes are ABOUT this content, not part of it. This is the read
    path a rerun rehydrates through -- ctx[key] = active_content(...) -- and
    several stages hand a prior step's dict to a model wholesale, so leaving
    them in would put the engine's own repair log into a prompt on every rerun
    and nowhere else, which is the worst kind of difference between a fresh
    run and a resumed one. The pipeline UI reads the variants table directly
    and still sees them.
    """
    content = json.loads(raw)
    if isinstance(content, dict) and ENGINE_NOTES_KEY in content:
        content = {k: v for k, v in content.items() if k != ENGINE_NOTES_KEY}
    return content


def active_content(turn_id, key):
    """The active variant's parsed content for one step of one turn.

    `None` when the step never ran.
    """
    r = q("SELECT v.content FROM steps s JOIN variants v "
          "ON v.step_id=s.id AND v.active=1 "
          "WHERE s.turn_id=? AND s.key=?", (turn_id, key), one=True)
    if not r:
        return None
    return _parsed(r["content"])


def active_mapping(turn_id, key):
    """The same read, narrowed to a mapping: `{}` when the content is not one.

    A step's content is any JSON. `/api/steps/{sid}/edit` stores whatever the
    request body holds, with no shape check, so a hand-edited step
    legitimately holds a list, a string or null -- which means a consumer
    that reads NAMED KEYS off a step (`.get("prose")`, `content["prose"] =
    ...`) is asking a question a non-mapping cannot answer, and asking it
    anyway raises inside whatever route was reading: `AttributeError` on the
    read, `TypeError` on the assignment. So the rule is stated once here --
    narrow first, and a step that answers none of the named keys answers
    nothing (review 2026-09-07, B23).

    A step that never ran answers `{}` too. The callers reading named keys
    have the same nothing to say either way, and the ones that need to tell
    an absent step from an unreadable one ask `active_content`, which still
    distinguishes them.
    """
    content = active_content(turn_id, key)
    return content if isinstance(content, dict) else {}


def active_mappings(chat_id, key, *, after_turn_id=None):
    """`active_mapping` for EVERY turn of one chat, in ONE query.

    Keyed by turn id; a turn whose step never ran is simply absent, which the
    callers read as the same `{}` the single-turn form answers.

    THE RULE THIS STATES: a reader rendering a whole transcript asks the
    steps/variants table once, not once per turn. Asking per turn is what a
    route does when it walks `turns` and calls `active_mapping` inside the
    loop -- correct, and linear in the length of the story, on a table every
    open and every poll reads. Measured 2026-09-07 on the review's bench copy
    of chat 117 (124 turns, C22): `GET /api/chats/117` issued 148 queries, 124
    of them this one read repeated; with this it issues 25, and the transcript
    read itself falls from 17.3 ms to 7.4 ms.

    It is deliberately chat-wide rather than taking a turn-id list. A story
    reaches thousands of turns -- the owner's own chats are the finding's
    ~2,500 -- and an `IN (?)` list of that size is a silent cap waiting on
    SQLite's parameter limit. `after_turn_id` is the incremental form the
    route's `?since_turn_id=` uses; it is a filter on the same JOIN, not a
    page size.

    NOT for a reader that wants a BOUNDED window (`agents.dramaturge`'s last
    few beats, `agents.narration`'s history depth): reading a whole chat to
    answer a question about six turns is the same defect with its sign
    reversed. Those keep their own LIMITed queries.
    """
    # CROSS JOIN, which in SQLite pins the join ORDER rather than changing the
    # result: this chat's turns first, then that turn's step, then that step's
    # active variant. Written as a plain JOIN the planner drove it from
    # `idx_steps_key` instead -- every `narrator` step in the FILE, 3,925 of
    # them on the review's bench copy, scanned to answer a 14-turn story --
    # and a short chat's open got SLOWER than the per-turn loop it replaced
    # (measured 2026-09-07: chat 114, 1.6 ms to 5.8 ms; pinned, 0.2 ms). A
    # long story hid it, because there the two costs are the same rows.
    sql = ("SELECT s.turn_id AS turn_id, v.content AS content "
           "FROM turns t "
           "CROSS JOIN steps s ON s.turn_id=t.id AND s.key=? "
           "CROSS JOIN variants v ON v.step_id=s.id AND v.active=1 "
           "WHERE t.chat_id=?")
    args = [key, chat_id]
    if after_turn_id is not None:
        sql += " AND s.turn_id>?"
        args.append(after_turn_id)
    # ORDER BY and `setdefault`, so that a turn carrying the key TWICE answers
    # with the same row the single-turn read answers with. `save_step` upserts
    # on (turn_id, key) and there is no unique index behind it, so a second
    # row is a shape a hand-built or repaired database can hold -- and there,
    # last-one-wins and first-one-wins are different prose on the page.
    sql += " ORDER BY s.turn_id, s.ord, s.id"
    first = {}
    for row in q(sql, tuple(args)):
        first.setdefault(row["turn_id"], row["content"])
    out = {}
    for turn_id, raw in first.items():
        content = _parsed(raw)
        if isinstance(content, dict):
            out[turn_id] = content
    return out
