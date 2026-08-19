"""A one-way window declared from both sides is said out loud.

`one_way_window` carries its asymmetry on ONE edge -- declared in the
direction it looks, with the way back a wall. Written from both sides it says
"sight passes each way", which is a `window`, and the asymmetry the author
reached for is silently gone.

Live, chat 82 "Sarah Moon — Hinami attempt 2". The interview suite declared it
from the observation annex to the cell AND from the cell back to the annex,
while the cell's own room note read "The mirrored side of the two-way glass
offers no visibility to the annex". The engine contradicted the authored prose
and the subject watched her interviewer. Both prompts ask for `wall` on the
blind side; the model wrote two anyway.

NEITHER ROOM SEES, and the contradiction is reported. Nothing in the pair says
which direction was meant, and the two ways of guessing are not equally wrong.
Admitting keeps the leak — the subject watching her interviewer through a
mirror the fiction told her was opaque, her view asserting both things two
sentences apart. Subtracting costs the watching side a view she should have
had, and that cost is real and accepted: a gap plays wrong obviously and the
notice says exactly what to fix, where a leak is not noticed until it has been
true for fifty beats.

The right answer is neither guess. Sight through the glass belongs to the edge;
what the glass LOOKS like from each side belongs to the edge too, so the blind
side reads "a mirror" and the watching side "transparent glass"; and KNOWING
the glass is one-way is prior knowledge — an interviewer was briefed, a subject
was not — which is not a property of a room at all. Standing beside a mirror is
not a channel to how it works.
"""

from __future__ import annotations

import time as _time

from persist import commit

MIRRORED = {
    "rooms": {
        "annex": {"name": "Observation Annex",
                  "adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
        "cell": {"name": "Interview Cell",
                 "adjacent": [{"to": "annex", "barrier": "one_way_window"}]},
    },
    "positions": {"Watcher": "annex", "Subject": "cell"},
}


def _ctx(temp_db, scene, diff):
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Interview", "", _time.time()))
    temp_db.wset(chat_id, "scene", scene)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Interview", persona_id=None,
                      lorebook_id=None, scenario="", created=_time.time()),
        turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="",
                      created=_time.time()),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": diff}
    return chat_id, ctx


def _mirrored_walls():
    """The same suite written correctly: one declaration, `wall` behind it."""
    import copy
    scene = copy.deepcopy(MIRRORED)
    scene["rooms"]["cell"]["adjacent"] = [{"to": "annex", "barrier": "wall"}]
    return scene


def test_the_beat_it_appears_it_warns_and_tells_the_director(temp_db):
    chat_id, ctx = _ctx(temp_db, _mirrored_walls(), {"rooms": {
        "cell": {"adjacent": [{"to": "annex", "barrier": "one_way_window"}]}}})

    commit.prepare_scene_commit(ctx)

    assert any("one_way_window into the other" in w for w in ctx.warnings), \
        ctx.warnings
    notices = temp_db.wget(chat_id, "engine_notices", [])
    assert any("`wall` on the blind side" in n for n in notices), notices


def test_a_scene_already_contradictory_is_told_once(temp_db):
    """The appearance test compares against the previous beat -- and for a
    scene contradictory since before this check existed, the previous beat was
    contradictory too. Left at that it would sit silently walled forever, with
    nothing anywhere saying why two rooms stopped seeing each other."""
    chat_id, ctx = _ctx(temp_db, MIRRORED, {"time": "a moment later"})

    commit.prepare_scene_commit(ctx)

    assert [w for w in ctx.warnings if "one_way_window into the other" in w]
    assert temp_db.wget(chat_id, "sight_contradictions_told", False) is True


def test_it_does_not_repeat_once_the_chat_has_heard_it(temp_db):
    """A standing condition reported every beat is one the reader learns to
    skip, which is the failure the warning exists to avoid."""
    chat_id, ctx = _ctx(temp_db, MIRRORED, {"time": "a moment later"})
    commit.prepare_scene_commit(ctx)

    ctx.warnings.clear()
    commit.prepare_scene_commit(ctx)

    assert not [w for w in ctx.warnings if "one_way_window into the other" in w]
    assert chat_id


def test_a_correctly_written_mirror_says_nothing(temp_db):
    chat_id, ctx = _ctx(temp_db, _mirrored_walls(), {"time": "a moment later"})

    commit.prepare_scene_commit(ctx)

    assert not [w for w in ctx.warnings if "one_way_window" in w]
    assert temp_db.wget(chat_id, "engine_notices", []) == []
