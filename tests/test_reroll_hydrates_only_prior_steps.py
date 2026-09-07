"""A single-step reroll hydrates only the steps BEFORE the rerolled one.

Review 2026-09-07 A1: the `only_key` branch loaded every step on the turn
and rehydrated each, so the old `perception_outcome` ran against the old
`director_resolve` and wrote `_player_room` from the ruling being
discarded; a rerolled resolve then graded the player from the room the
discarded ruling had moved her to. No stage may read a later stage's
output.
"""
import time

from agents.runtime import _hydrate_steps_before
from agents.storage import save_step


def test_steps_at_or_after_the_rerolled_ord_are_not_loaded(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Reroll", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "step through", time.time()))
    for ordn, key in enumerate(("director_interpret", "compile_world_context",
                                "perception_act", "director_resolve",
                                "perception_outcome", "narrator", "commit")):
        save_step(turn_id, key, key, ordn, {"ord": ordn})

    ctx = {}
    hydrated = _hydrate_steps_before(ctx, turn_id, 3)   # rerolling director_resolve

    assert [k for k, _ in hydrated] == ["director_interpret",
                                        "compile_world_context",
                                        "perception_act"]
    assert "director_resolve" not in ctx
    assert "perception_outcome" not in ctx, "the discarded outcome must not be on ctx"
    assert "commit" not in ctx
