"""The resolve labels a player's contestable events with the CHAT'S dial.

`_causal_event_inputs` handed each player group
`interp.get("authority_mode") or "world_author"`, and the interpret stamps
`authority_mode` only on a beat that had a downgrade. So on a chat at
`actor_only` every beat without one told the resolve's author and encoder
that the player's contestable events were `world_author`'s -- the input
`commitment` is judged WITH (`director_evidence.authority_by_entity`) -- and
an extra player was `world_author` always: one fact, read two ways (review
2026-11-01, director core F10).

And a beat that DID have a downgrade carries the refused assertions to the
resolve's author, as the code always said it did ("so the Director can
answer it in THIS beat"): they rode only the staging payload, which no model
call receives.
"""

from __future__ import annotations

from types import SimpleNamespace

import agents.director as director
from story.scene import set_player_authority

from tests.director_fakes import _make_ctx, _speech_interp, prose_resolve_agent


def _contestable_interp():
    interp = _speech_interp()
    interp["sequence"] = [{"type": "action", "attempt": "force the hatch",
                           "commitment": "contestable", "targets": [],
                           "visibility": "overt", "conceal_from": []}]
    return interp


def test_a_restricted_dial_reaches_the_resolve_on_a_beat_without_a_downgrade(temp_db):
    ctx = _make_ctx(temp_db, interp=_contestable_interp())
    set_player_authority(ctx.chat.id, "actor_only")
    ctx.extra_players = [{"persona_id": 9, "name": "Bob", "input": "I wait.",
                          "idle": False}]
    groups = director._causal_event_inputs(ctx, _contestable_interp(), [], [], [])
    assert [(g["entity_id"], g["authority_mode"]) for g in groups] \
        == [("persona:primary", "actor_only")], groups


def test_a_downgrade_the_dial_made_reaches_the_resolves_author(
        temp_db, monkeypatch, prose_director):
    interp = _contestable_interp()
    interp["authority_mode"] = "actor_only"
    interp["authority_downgrades"] = [{"claim_id": "claim:0:effect",
                                       "assertion": "the hatch flies open"}]
    ctx = _make_ctx(temp_db, interp=interp)
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "The hatch holds."}, calls=calls))

    director.director_resolve(ctx, nonce=0)

    author = [p for key, p in calls if key == "director_prose"][0]
    declared = author.get("player_declaration") or {}
    assert declared.get("downgraded_assertions") == interp["authority_downgrades"], \
        author.keys()
    assert declared.get("authority_mode") == "actor_only"
