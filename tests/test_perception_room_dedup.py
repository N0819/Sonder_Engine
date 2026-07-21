"""perception_outcome canonicalizes colliding room keys BEFORE its merge
(movement/space Phase 2, item 6): commit's dedup_minted_rooms is a pure
function of the stored scene + registry + diff, all unchanged between the
outcome stage and commit, so running it here on a COPY of the diff shows
this beat's rendering the same canonical key the committed world will
carry -- removing the Phase-1 one-beat cosmetic skew where perception
described 'deck_3' aboard the wrong ship for exactly one beat.
"""

from __future__ import annotations

import json
import time

from pipeline_context import ChatData, PipelineContext, TurnData


def _make_ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "Harbor",
        "rooms": {
            "harbor": {"name": "Harbor", "adjacent": []},
            "deck_3": {"name": "Deck 3", "parent_entity": "ship_a",
                       "adjacent": []},
        },
        "positions": {"ship_a": "harbor", "ship_b": "harbor",
                      "The Stranger": "harbor"},
        "entities": {
            "ship_a": {"name": "The Aurora", "kind": "vehicle",
                       "interior_rooms": ["deck_3"], "state": {}},
            "ship_b": {"name": "The Boreas", "kind": "vehicle",
                       "interior_rooms": [], "state": {}},
        },
        "attire": {}, "overlays": {},
    })
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "board", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="board", created=time.time()),
        cast=[], input="board",
    )
    ctx.director_interpret = {"movement": None}
    # Ship B mints a colliding 'deck_3' and the player boards it -- the
    # same two-ship collision commit's dedup rekeys.
    ctx.director_resolve = {
        "resolved_event": "The Stranger boards the Boreas.",
        "dialogue_log": [],
        "state_diff": {
            "rooms": {"deck_3": {"name": "Deck 3", "parent_entity": "ship_b",
                                 "adjacent": []}},
            "positions": {"The Stranger": "deck_3"},
        },
    }
    return ctx


def test_outcome_scene_uses_the_canonical_rekeyed_room(temp_db, monkeypatch):
    import agents.perception as perception
    import commit

    ctx = _make_ctx(temp_db)
    captured = {}

    def fake_agent_json(*args, **kwargs):
        return {"views": {}}

    monkeypatch.setattr(perception, "_agent_json", fake_agent_json)
    perception.perception_outcome(ctx, nonce=0)

    # The player's resolved room is the REKEYED key, exactly what commit's
    # own dedup will produce for the same diff -- not the colliding one.
    prepared = commit.prepare_scene_commit(ctx)
    committed_room = prepared["scene"]["positions"]["The Stranger"]
    assert committed_room != "deck_3"
    assert ctx["_player_room"] == committed_room

    # And the persisted resolve diff was never mutated by either pass.
    assert ctx.director_resolve["state_diff"]["positions"]["The Stranger"] \
        == "deck_3"
