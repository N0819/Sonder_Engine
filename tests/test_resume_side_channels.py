"""What a resumed turn is told that an uninterrupted one was not.

`ctx[key] = content` restores a stage's OUTPUT. It does not restore the values
a stage left on `PipelineContext._extra` by direct assignment, because no step
content carries them: `outcome_scene` (perception_outcome -> narrator),
`interaction_views` and `reaction_views` (the loops -> character steps).

The costly one is `outcome_scene`. `narrator` reads it for the spatial frame,
the position deltas, the portal states and the sensory manifest, falling back
to `get_scene()` -- which perception_outcome's own comment says is wrong on
exactly the beats it matters: the committed scene describes the space with
LAST beat's facing, because commit runs after the narrator. So a single-step
narrator reroll on a committed turn restored the pre-turn checkpoint and then
re-rendered with the beat's own movement missing from what it was told.
"""

from __future__ import annotations

import json
import time

import agents.runtime as runtime
from agents.runtime import _run_pipeline
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Resume", "", time.time()),
    )


def _make_turn(db, chat_id, idx=1):
    return db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "step through the door", time.time()),
    )


def _make_cast(db, chat_id, names):
    ids = {}
    for name in names:
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"),
        )
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
        ids[name] = char_id
    return ids


def _scene(positions):
    return {
        "location": "Old Manor", "time": "evening",
        "rooms": {
            "kitchen": {"name": "Kitchen", "desc": "", "adjacent": ["study"]},
            "study": {"name": "Study", "desc": "", "adjacent": ["kitchen"]},
        },
        "positions": positions, "entities": {}, "overlays": {}, "attire": {},
    }


def _ctx(chat_id=1):
    return PipelineContext(
        chat=ChatData(id=chat_id, name="", persona_id=None, lorebook_id=None,
                      scenario="", created=0.0),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="",
                      created=0.0),
        cast=[], input="",
    )


# ---- outcome_scene ----

def _stub_handlers(monkeypatch, commit_scene):
    """A whole turn that MOVES the player, committed."""
    stubs = {
        "director_interpret": lambda ctx, n: {"flow": {
            "needs_mapping": False, "reactors": [],
            "resolution_flags": {"contested": False}}},
        "mapping_quick": lambda ctx, n: {"relevant_lore": []},
        "perception_act": lambda ctx, n: {"views": {}},
        "director_resolve": lambda ctx, n: {
            "dialogue_log": [],
            "state_diff": {"positions": {"Player": "study"}},
        },
        "background_react": lambda ctx, n: {"fired": False},
        "narrator": lambda ctx, n: {"prose": "ok"},
        "commit": lambda ctx, n: (
            ctx.chat and commit_scene(ctx) or {"committed": True}),
    }
    for key, fn in stubs.items():
        monkeypatch.setitem(runtime.STEP_HANDLERS, key, fn)


def test_a_narrator_reroll_is_told_this_beat_s_scene_not_last_beat_s(
        temp_db, monkeypatch):
    from core.db import wset

    chat_id = _make_chat(temp_db)
    _make_cast(temp_db, chat_id, ["Alice"])
    turn_id = _make_turn(temp_db, chat_id, idx=1)
    wset(chat_id, "scene", _scene({"Player": "kitchen", "Alice": "study"}))

    def committing(ctx):
        # Stand in for commit persisting the resolved move.
        wset(ctx.chat.id, "scene",
             _scene({"Player": "study", "Alice": "study"}))
        return {"committed": True}

    _stub_handlers(monkeypatch, committing)
    list(_run_pipeline(chat_id, turn_id))

    seen = {}

    def capturing_narrator(ctx, nonce):
        outcome = ctx.get("outcome_scene") or {}
        seen["player_room"] = (outcome.get("positions") or {}).get("Player")
        return {"prose": "ok"}

    monkeypatch.setitem(runtime.STEP_HANDLERS, "narrator", capturing_narrator)
    list(_run_pipeline(chat_id, turn_id, only_key="narrator"))

    # The reroll restores the PRE-turn checkpoint (Player in the kitchen) and
    # then re-renders. Without the rebuild the narrator was handed no
    # outcome_scene at all and fell back to that rolled-back world, so the
    # move it is supposed to be describing had not happened.
    assert seen["player_room"] == "study"


def test_the_rebuild_reads_the_restored_world_not_the_committed_one(
        temp_db, monkeypatch):
    """The rebuild must run AFTER the checkpoint restore.

    Rebuilding from the live world would re-derive the outcome from the
    OUTCOME -- the exact leak the restore exists to prevent -- and would hide
    a resolve stage that had been rerolled to a different answer.
    """
    from core.db import wset

    chat_id = _make_chat(temp_db)
    _make_cast(temp_db, chat_id, ["Alice"])
    turn_id = _make_turn(temp_db, chat_id, idx=1)
    wset(chat_id, "scene", _scene({"Player": "kitchen", "Alice": "kitchen"}))

    def committing(ctx):
        wset(ctx.chat.id, "scene",
             _scene({"Player": "study", "Alice": "study"}))
        return {"committed": True}

    _stub_handlers(monkeypatch, committing)
    list(_run_pipeline(chat_id, turn_id))

    seen = {}

    def capturing_narrator(ctx, nonce):
        outcome = ctx.get("outcome_scene") or {}
        seen["alice"] = (outcome.get("positions") or {}).get("Alice")
        return {"prose": "ok"}

    monkeypatch.setitem(runtime.STEP_HANDLERS, "narrator", capturing_narrator)
    list(_run_pipeline(chat_id, turn_id, only_key="narrator"))

    # Alice's move to the study was never in this turn's state_diff -- it only
    # exists in the committed blob the restore rolls back. Seeing her there
    # would mean the rebuild ran against post-commit state.
    assert seen["alice"] == "kitchen"


# ---- the two loop view maps ----

def test_reaction_views_come_back_from_the_stored_rounds():
    from agents.loops import rehydrate_loop_views

    ctx = _ctx()
    ctx["perception_act"] = {"views": {"7": "You are grabbed.",
                                       "9": "Someone is grabbed."}}
    rehydrate_loop_views(ctx, "reaction_loop", {
        "rounds": [{"round": 0, "reactor_id": 7, "result": {}}],
        "reaction_results": {"7": {}},
    })
    # Only the reactor who actually took a reaction phase, and exactly the
    # onset view they were handed then.
    assert ctx.get("reaction_views") == {7: "You are grabbed."}


def test_interaction_views_replay_the_persisted_micro_rounds():
    from agents.loops import rehydrate_loop_views

    ctx = _ctx()
    ctx["perception_act"] = {"views": {"7": "Base view.", "9": "Other base."}}
    rehydrate_loop_views(ctx, "interaction_loop", {
        "rounds": [
            {"round": 0, "speaker_id": 9,
             "delivered_views": {"7": ['Nine says: "Hello."']}},
            {"round": 1, "speaker_id": 7,
             "delivered_views": {"9": ['Seven says: "Hello back."']}},
        ],
    })
    views = ctx.get("interaction_views")
    # Each mind gets its own base view plus only what was delivered TO it --
    # never the other's, and never the speaker's own line back.
    assert "Base view." in views[7]
    assert 'Nine says: "Hello."' in views[7]
    assert 'Hello back.' not in views[7]
    assert 'Seven says: "Hello back."' in views[9]
    assert 'Nine says: "Hello."' not in views[9]


def test_a_loop_with_no_rounds_leaves_the_base_views_alone():
    from agents.loops import rehydrate_loop_views

    ctx = _ctx()
    ctx["perception_act"] = {"views": {"7": "Base view."}}
    rehydrate_loop_views(ctx, "reaction_loop", {"rounds": []})
    assert ctx.get("reaction_views", {}) == {}
    rehydrate_loop_views(ctx, "interaction_loop", {"rounds": []})
    assert ctx.get("interaction_views") == {7: "Base view."}
