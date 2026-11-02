"""A mind's own card reaches it before its moment does, and the pool its
recall waits on is a named number.

E3 (review 2026-11-01, agents_character_background): inside `self`, the
volatile `active_state` (rewritten every commit) and `stance` (a running
log) sat AHEAD of the static card block -- `voice`, `senses`,
`sense_profile`, `interoception`, `abilities`, `embodiment_capabilities`,
`body_parts` -- so no per-character prefix of the payload could repeat from
one beat to the next for a provider to cache. Order only: the same keys,
the same values.

E2: `_MEMORY_CONTEXT_POOL` had `max_workers=4` inline while the skip stage
fans eight minds out at once (`skip_stage.SKIP_ASK_WORKERS`); the four is
the owner's cap to rule on, and is now named.
"""

from __future__ import annotations

from copy import deepcopy

from tests.test_character_continuity import story  # noqa: F401 -- the fixture

STATIC = ("voice", "senses", "sense_profile", "interoception", "abilities",
          "embodiment_capabilities")


def test_the_static_card_block_precedes_what_moves(temp_db, story, monkeypatch):
    import agents.character as character
    from llm import decisions
    from tests.test_character_bare import _answer
    char_id, context, _commit = story
    sent = []

    def model(role, step_key, system, payload, **kwargs):
        sent.append(deepcopy(payload))
        return {"want": "listen", "held_back": "", "hinge": "", "unsure": "",
                "sequence": [{"do": "listens"}], "demeanor": "", "tells": [],
                "notebook": [], "changes": [], "note": ""}

    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: _answer([])(questions))
    monkeypatch.setattr(character, "_agent_json", model)
    character.character_step(context(None, 1), char_id, 1)
    keys = list(sent[0]["self"])
    first_moving = min(keys.index(k) for k in ("active_state", "stance") if k in keys)
    for key in STATIC:
        if key in keys:
            assert keys.index(key) < first_moving, (key, keys)


def test_the_recall_pool_is_a_named_number():
    import agents.character as character
    assert character.MEMORY_CONTEXT_WORKERS == 4
    assert character._MEMORY_CONTEXT_POOL._max_workers == character.MEMORY_CONTEXT_WORKERS
