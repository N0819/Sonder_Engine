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


def active_content(turn_id, key):
    """The active variant's parsed content for one step of one turn.

    `None` when the step never ran. The parse is deliberately NOT guarded:
    every writer goes through `json.dumps` (`agents.storage.save_step` and the
    manual edit route alike), so unparseable content is a broken database
    rather than an expected answer, and swallowing it would hide that.
    """
    r = q("SELECT v.content FROM steps s JOIN variants v "
          "ON v.step_id=s.id AND v.active=1 "
          "WHERE s.turn_id=? AND s.key=?", (turn_id, key), one=True)
    if not r:
        return None
    content = json.loads(r["content"])
    # The engine notes are ABOUT this content, not part of it. This is the
    # read path a rerun rehydrates through -- ctx[key] = active_content(...) --
    # and several stages hand a prior step's dict to a model wholesale, so
    # leaving them in would put the engine's own repair log into a prompt on
    # every rerun and nowhere else, which is the worst kind of difference
    # between a fresh run and a resumed one. The pipeline UI reads the
    # variants table directly and still sees them.
    if isinstance(content, dict) and ENGINE_NOTES_KEY in content:
        content = {k: v for k, v in content.items() if k != ENGINE_NOTES_KEY}
    return content


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
