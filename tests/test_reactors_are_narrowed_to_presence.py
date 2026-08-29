"""A model's PACING list is not a PRESENCE list.

`flow.reactors` is the Director's judgement about who should speak this beat.
The engine narrowed it by exactly two tests -- valid cast id, and awareness --
and never asked the scene whether it places those bodies anywhere at all.

Measured, chat 95 (a Star Trek story, 2026-08-28). `scene.positions` held no
entry for Worf (76) or Geordi (77) at any point, so
`_present_cast_bodies(scene, cast)` returned `{74, 75}` all run. The Director
nevertheless named them: `flow.reactors` was `[75, 76, 77]` on turns 4 and 5,
`[74, 75, 76]` on turns 8 and 14. `build_plan` and both loops kept every one.

The turn's own deterministic stage disagreed in the same beat -- `perception_
act.views` had observers `['75']` on turns 4/5/8 and `['74','75']` on turn 14
-- because perception ALREADY gates on presence (`agents/perception.py`,
"Presence is the scene's answer, not the Director's"). That fix widened
perception to match presence; the complementary NARROWING of the reactor list
was never made. The cost was 6 `character_major` calls at 13-22s each, each
one asking a mind with an empty perception base to declare conduct from a
place the world does not put it in.

Presence is "the scene places them SOMEWHERE", never "the same room as the
player": a character answering over a comm channel from another room is
present and must survive the narrowing.
"""

from __future__ import annotations

import inspect
import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data


def _bridge(temp_db, positions):
    """A chat with three cast members and an author-chosen position ledger."""
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Player", json.dumps(default_persona_data("Player")), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Presence", "", time.time(), persona_id))

    ids = {}
    for name in ("Here", "Elsewhere", "Nowhere"):
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid

    temp_db.wset(chat_id, "scene", {
        "location": "a ship", "time_of_day": "night",
        "rooms": {"bridge": {"name": "Bridge", "adjacent": ["annex"]},
                  "annex": {"name": "Annex", "adjacent": ["bridge"]}},
        "positions": dict(positions, Player="bridge"),
        "entities": {}, "attire": {}, "overlays": {}})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Presence", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    return ctx, chat_id, ids


def _positions():
    """"Here" stands with the player; "Elsewhere" stands in another room;
    "Nowhere" is the chat-95 shape -- registered, awake, and placed by the
    scene nowhere at all."""
    return {"Here": "bridge", "Elsewhere": "annex"}


def test_a_reactor_the_scene_places_nowhere_is_not_planned(temp_db):
    """chat 95 turn 4: `flow.reactors=[75,76,77]` while `scene.positions`
    had no entry for 76 or 77 and `perception_act.views` had observers
    `['75']`."""
    from agents.runtime import build_plan
    ctx, chat_id, ids = _bridge(temp_db, _positions())
    # autonomy 0 makes the planner name each reactor as its own step, which
    # is what lets this read the narrowed set off the plan itself.
    temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
    interp = {"flow": {"reactors": [ids["Here"], ids["Nowhere"]],
                       "resolution_flags": {}}}

    keys = [key for key, _ in build_plan(interp, ctx.cast, chat_id=chat_id)]

    assert f"character:{ids['Nowhere']}" not in keys
    assert f"character:{ids['Here']}" in keys, (
        "the present reactor must still be planned")


def test_a_reactor_in_another_room_is_still_planned(temp_db):
    """Presence is "the scene places them SOMEWHERE", not "in the player's
    room" -- a mind answering over a comm channel from another room has a
    position and must survive the narrowing."""
    from agents.runtime import build_plan
    ctx, chat_id, ids = _bridge(temp_db, _positions())
    temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
    interp = {"flow": {"reactors": [ids["Elsewhere"]],
                       "resolution_flags": {}}}

    keys = [key for key, _ in build_plan(interp, ctx.cast, chat_id=chat_id)]

    assert f"character:{ids['Elsewhere']}" in keys


def test_every_reactor_reader_narrows_to_presence(temp_db):
    """Three readers take `flow.reactors` off the Director independently --
    `build_plan` and both loops -- so all three must gate, for the same
    reason `_drop_non_awake` is called in all three."""
    from agents import loops, runtime

    assert "_present_cast_bodies" in inspect.getsource(runtime.build_plan)
    for loop in (loops.interaction_loop, loops.reaction_loop):
        assert "_drop_absent" in inspect.getsource(loop), (
            f"{loop.__name__} still hands the Director's pacing list on "
            "without asking the scene")


def test_the_loops_drop_an_unplaced_reactor_and_say_so(temp_db):
    """A silently dropped reactor reads as a quiet character, which is how
    the chat-95 shape stayed invisible for sixteen turns."""
    from agents import loops
    ctx, chat_id, ids = _bridge(temp_db, _positions())

    kept = loops._drop_absent(ctx, [ids["Here"], ids["Elsewhere"],
                                    ids["Nowhere"]])

    assert kept == [ids["Here"], ids["Elsewhere"]]
    assert any("Nowhere" in w for w in ctx.warnings), ctx.warnings
    assert not any("Elsewhere" in w for w in ctx.warnings)


def test_character_step_refuses_a_mind_the_scene_places_nowhere(temp_db):
    """The choke point, for stale and rerun plans: it already holds the
    scene and already carries the parallel awareness guard, so no reader of
    `flow.reactors` can route around presence. No LLM call, no manifest."""
    from agents.character import character_step
    ctx, chat_id, ids = _bridge(temp_db, _positions())
    ctx.director_interpret = {"sequence": [], "flow": {}}

    out = character_step(ctx, ids["Nowhere"], nonce=0)

    assert out["speech"] is None and out["action"] is None
    assert out["sequence"] == [] and out["manifest"] == {}
    assert out.get("_absent_gated") is True
    assert any("Nowhere" in w for w in ctx.warnings), ctx.warnings
