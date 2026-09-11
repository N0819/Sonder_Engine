"""One composition per beat, read by perception_outcome and by the commit.

Review 2026-09-07 A26/B1/C6. `perception_outcome` used to compose its own
post-beat scene -- `merge_scene_with_diff(sc, diff, clock_seconds=)`, attire,
and the three orientation inferences -- beside the commit's composition. The
two drifted three separate times; the drift the finding was written for is
that the mirror never ran `_refuse_unheld_transfers`, so the narrator and
every memory episode built from that stage could read a handover as done that
the commit was about to refuse.

`persist.commit_scene_state.compose_beat_scene` is now the one composition.
Perception calls it and stashes the result on the context; the commit reads
that back when it was composed from the same stored scene and the same stored
answer, and composes afresh when it was not. These tests hold the three
things that can go wrong with that: the mirror coming back, the stash being
served when it is stale, and the composed scene disagreeing with the
committed one.

Measured on the bench copies while landing this (chats 114 and 117, every
turn with a resolve step, the composition run against the chat's stored
scene): the second composition cost 55.6 ms/beat on the 307-body charter town
and 47.9 ms/beat on the 123-beat descent, and both chats' prepared commit
answers -- scene, diff, clock, destruction, regions, charter routing, room
registry, warnings and Director notes -- are byte-identical through the reuse
path.
"""

from __future__ import annotations

import ast
import inspect
import time

import pytest

from core.db import wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import compose_beat_scene, prepare_scene_commit


def _scene():
    """Two rooms a floor apart, a box in one and its claimed holder in the
    other -- the shape of the Vaunt's Yard turn 13 refusal."""
    return {
        "location": "A stairwell", "time_of_day": "",
        "rooms": {
            "third_landing": {"name": "Third Landing", "desc": "A landing.",
                              "adjacent": [{"to": "second_landing",
                                            "barrier": "open"}]},
            "second_landing": {"name": "Second Landing", "desc": "Below it.",
                               "adjacent": [{"to": "third_landing",
                                             "barrier": "open"}]},
        },
        "entities": {"mirela_box": {"name": "a tin box", "kind": "object"}},
        "positions": {"mirela_box": "third_landing",
                      "Mirela Andelic": "second_landing",
                      "Vesna Kolar": "second_landing"},
        "attire": {}, "overlays": {}, "contained": {},
    }


def _make_ctx(temp_db, scene=None, state_diff=None, *, with_step=True):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Compose", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 4, "hand it over", time.time()))
    wset(chat_id, "scene", scene if scene is not None else _scene())
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Compose", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=4,
                      player_input="hand it over", created=time.time(),
                      frame_id=None),
        cast=[], input="hand it over")
    ctx.director_resolve = {
        "resolved_event": "The box changes hands.", "dialogue_log": [],
        "state_diff": state_diff or {},
    }
    if with_step:
        step_id = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
            (turn_id, "director_resolve", "Resolve", 5))
        temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) "
            "VALUES(?,?,?,1)", (step_id, "{}", time.time()))
    return ctx


_UNHELD_HANDOVER = {"inventory_ops": [
    {"op": "transfer", "object_id": "mirela_box",
     "from_id": "Mirela Andelic", "to_id": "Vesna Kolar"}]}


def test_the_composed_scene_refuses_a_handover_from_someone_not_holding_it(
        temp_db):
    """The finding's own case: the composed scene the narrator reads must
    show the refusal, not only the committed one."""
    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    composed = compose_beat_scene(ctx)
    # The op was struck off the diff the merge saw...
    assert composed.diff.get("inventory_ops") == []
    # ...so nothing put the box in the claimed recipient's hands, and it is
    # still standing where the scene had it.
    assert (composed.scene.get("contained") or {}).get("mirela_box") is None
    assert composed.scene["positions"]["mirela_box"] == "third_landing"
    # And the Director is told, once, by whichever side publishes.
    assert any("was not" in note and "hand over" in note
               for note in composed.director_notes)
    assert not ctx.engine_feedback   # composing publishes nothing


def test_the_committed_scene_agrees_with_the_composed_one(temp_db):
    """Same inputs, same answer: the reason there is one function."""
    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    composed = compose_beat_scene(ctx)
    ctx["_composed_beat"] = composed
    committed = prepare_scene_commit(ctx)["scene"]
    for key in ("positions", "contained", "entities"):
        assert committed.get(key) == composed.scene.get(key), key


def test_the_commit_reads_back_the_composition_perception_stashed(
        temp_db, monkeypatch):
    """A composition stashed under the current key is REUSED, not repeated."""
    import persist.commit_scene_state as css

    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    ctx["_composed_beat"] = compose_beat_scene(ctx)

    def _refuse(_ctx):
        raise AssertionError("the commit composed the beat a second time")

    # The module that DEFINES it, never the facade.
    monkeypatch.setattr(css, "compose_beat_scene", _refuse)
    prepared = prepare_scene_commit(ctx)
    assert prepared["scene"]["positions"]["mirela_box"] == "third_landing"
    # The reports the composition held back are published exactly once, by
    # the side entitled to speak.
    assert sum(1 for n in ctx.engine_feedback if "was not" in n) == 1


def test_a_stash_from_a_different_scene_is_refused(temp_db, monkeypatch):
    """The world moved under the stash, so it is composed again.

    The key's first half is the scene row's own read token: any tracked write
    to it between the two stages invalidates the composition, because the
    composition is a merge ONTO that row.
    """
    import persist.commit_scene_state as css

    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    ctx["_composed_beat"] = compose_beat_scene(ctx)
    moved = _scene()
    moved["positions"]["mirela_box"] = "second_landing"
    wset(ctx.chat.id, "scene", moved)

    calls = []
    real = css.compose_beat_scene

    def _counted(_ctx):
        calls.append(1)
        return real(_ctx)

    monkeypatch.setattr(css, "compose_beat_scene", _counted)
    prepared = prepare_scene_commit(ctx)
    assert calls, "a stash built on a superseded scene must not be served"
    assert prepared["scene"]["positions"]["mirela_box"] == "second_landing"


def test_a_stash_from_a_superseded_answer_is_refused(temp_db, monkeypatch):
    """The beat was rerolled or hand-edited, so it is composed again.

    The key's second half is the id of the ACTIVE resolve variant, which is
    what moves when the stored answer does.
    """
    import persist.commit_scene_state as css

    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    ctx["_composed_beat"] = compose_beat_scene(ctx)
    step = temp_db.q("SELECT id FROM steps WHERE turn_id=? AND key=?",
                     (ctx.turn.id, "director_resolve"), one=True)
    temp_db.qi("UPDATE variants SET active=0 WHERE step_id=?", (step["id"],))
    temp_db.qi("INSERT INTO variants(step_id,content,created,active) "
               "VALUES(?,?,?,1)", (step["id"], "{}", time.time()))

    calls = []
    real = css.compose_beat_scene

    def _counted(_ctx):
        calls.append(1)
        return real(_ctx)

    monkeypatch.setattr(css, "compose_beat_scene", _counted)
    prepare_scene_commit(ctx)
    assert calls, "a stash built on a superseded answer must not be served"


def test_a_commit_with_no_stash_composes_for_itself(temp_db):
    """A rerun from the commit stage alone never saw perception_outcome."""
    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    assert ctx.get("_composed_beat") is None
    prepared = prepare_scene_commit(ctx)
    assert prepared["scene"]["positions"]["mirela_box"] == "third_landing"
    assert any("was not" in n for n in ctx.engine_feedback)


def test_perception_outcome_no_longer_composes_a_scene_of_its_own():
    """The mirror is GONE, by AST rather than by grep.

    Named calls, not a text search: a comment naming `merge_scene_with_diff`
    is fine and a call to it is the defect. `perception_establish` still
    composes the opening for itself -- a separate mirror, out of A26's scope
    and left deliberately, because the opening's base scene differs between
    the two sides (`get_scene` seeds a new scene's initial attire and the
    commit does not).
    """
    from agents import perception

    src = inspect.getsource(perception.perception_outcome)
    tree = ast.parse(inspect.cleandoc("\n" + src))
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                called.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                called.add(fn.attr)
    for name in ("merge_scene_with_diff", "apply_attire_diff",
                 "infer_came_from", "infer_focus", "infer_facing",
                 "dedup_minted_rooms", "stamp_authored_interiors"):
        assert name not in called, (
            f"perception_outcome calls {name} again -- the composition it "
            "must read is compose_beat_scene's")
    assert "compose_beat_scene" in called


def test_compose_writes_nothing_to_the_scene_row(temp_db):
    """Composing is a derivation; only `commit_scene` persists."""
    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    before = temp_db.wget(ctx.chat.id, "scene", {})
    compose_beat_scene(ctx)
    assert temp_db.wget(ctx.chat.id, "scene", {}) == before


def test_the_stage_that_renders_the_beat_may_not_write_the_world(temp_db):
    """The composed scene is the object the commit persists, and the stage
    that renders the beat writes on the scene it holds -- `lay_charter_bodies`
    lays unregistered presence bodies onto "the stage's own fresh copy, never
    the store". The first A26 patch handed the stage the store-bound object,
    and the skeptic's replay of the descent found a charter creature's
    position, station and facing committed on 7 of 124 beats with no entity
    row to match. So whatever the stage lays -- this test lays the same three
    rows under a name the scene does not stand -- must not reach the commit.
    """
    from agents.perception import perception_outcome

    ctx = _make_ctx(temp_db, state_diff=dict(_UNHELD_HANDOVER))
    perception_outcome(ctx, 0)
    staged = ctx._extra["outcome_scene"]
    assert staged is not ctx["_composed_beat"].scene
    staged.setdefault("positions", {})["Carbonic_stalker_0"] = "second_landing"
    staged.setdefault("stations", {})["Carbonic_stalker_0"] = {"cell": [3, 0]}
    staged.setdefault("orientation", {})["Carbonic_stalker_0"] = {"facing": "w"}

    committed = prepare_scene_commit(ctx)["scene"]
    for ledger in ("positions", "stations", "orientation"):
        assert "Carbonic_stalker_0" not in (committed.get(ledger) or {}), ledger


def test_the_composed_scene_carries_the_beats_events(temp_db):
    """THE ARROW INTO THE WORLD: character -> director -> recompiler -> WORLD
    -> perception. The composition is where the beat stops being something
    perception re-derives out of everybody's declarations and becomes a thing
    it READS, and it is written HERE rather than at the commit because the
    commit runs after the narrator (`_record_sensory_events` is the record
    that does, which is why it reads empty during its own beat)."""
    from world.beat_ledger import beat_events
    ctx = _make_ctx(temp_db)
    ctx.director_resolve["beat_events"] = [
        {"order": 0, "actor": "Mirela Andelic", "surface": "holds out the box",
         "declared": "turn:4:character:1:0:action"},
        {"order": 1, "actor": "Vesna Kolar", "surface": "does not take it"},
    ]
    composed = compose_beat_scene(ctx)
    rows = beat_events(composed.scene, 4)
    assert [r["actor"] for r in rows] == ["Mirela Andelic", "Vesna Kolar"]
    assert rows[0]["declared"] == "turn:4:character:1:0:action"


def test_another_beat_inherits_no_events_and_nothing_swept_them(temp_db):
    """The beat number IS the lifetime. A sweep is a second thing that has to
    run on every path forever, and the path it misses renders a stale event as
    though it had just happened; a reader that must prove the beat matches
    cannot be wrong that way."""
    from world.beat_ledger import beat_events
    ctx = _make_ctx(temp_db)
    ctx.director_resolve["beat_events"] = [
        {"order": 0, "actor": "Mirela Andelic", "surface": "holds out the box"}]
    composed = compose_beat_scene(ctx)
    assert beat_events(composed.scene, 4)
    assert beat_events(composed.scene, 5) == []


def test_a_beat_with_no_events_clears_the_one_before_it(temp_db):
    """"This beat had no events" and "no beat has spoken" are different
    answers; an establish turn, or any beat whose resolve wrote none, must not
    leave the previous beat's list standing where the first could be read as
    the second."""
    from world.beat_ledger import BEAT_EVENTS_KEY, beat_events
    scene = _scene()
    scene[BEAT_EVENTS_KEY] = {"beat": 3, "events": [
        {"order": 0, "actor": "Vesna Kolar", "surface": "a beat ago"}]}
    ctx = _make_ctx(temp_db, scene=scene)
    composed = compose_beat_scene(ctx)
    assert composed.scene[BEAT_EVENTS_KEY]["beat"] == 4
    assert beat_events(composed.scene, 3) == []
    assert beat_events(composed.scene, 4) == []


def test_the_actors_own_words_never_reach_the_scene(temp_db):
    """A strict projection, not a passthrough. `attempt` is the actor's own
    intent-bearing words and `surface` the intent-free outward form; writing
    the element wholesale would put the first into the world for every
    observer to read, which is the leak the perception filter exists for."""
    ctx = _make_ctx(temp_db)
    ctx.director_resolve["beat_events"] = [{
        "order": 0, "actor": "Mirela Andelic",
        "surface": "holds out the box",
        "attempt": "get her fingerprints onto it before the constable comes"}]
    composed = compose_beat_scene(ctx)
    row, = composed.scene["beat_events"]["events"]
    assert "attempt" not in row
    assert "fingerprints" not in str(row)
