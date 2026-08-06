"""A mind that walked out of the room did not fall asleep in it.

`director_resolve` may assert an `awareness` condition, and a gated level
(asleep / sedated / unconscious) removes the subject from perception entirely
and stops their character step running.

Live failure, chat 63 turn 165. The player typed:

    "Doctor. I'm going to rest for today..." You slowly stand. "You could
    probably bring your box closer and show mom while I sleep?" You give
    another yawn. "Anyways... good night." You walk towards the shoji leading
    to the upstairs opening it.

Three lines of SPEECH about a plan, and three narrated acts: stand, yawn, walk.
`director_interpret` read it correctly and extracted only the acts. Resolve then
minted `{"level": "asleep", "cause": "natural fatigue after meal, declared
intent to rest and sleep"}` -- its own cause naming the speech it inferred from
-- with no expiry. The player was gated out of their own story while their
character was mid-stride, and eight subsequent turns produced no view for them
at all.

A stated plan is dialogue. Going under is an act. The prompt already says so in
those words, which is the point: instruction where structure was wanted.
"""

from __future__ import annotations

import commit


def _cond(level="asleep", subject="Hinami", active=True):
    return {"subject_id": subject, "kind": "awareness", "active": active,
            "state": {"level": level, "cause": "declared intent to rest"}}


class _Ctx:
    """The two fields the guard reads, and a warnings list."""

    def __init__(self, actions=None, chat_id=1):
        self.director_interpret = {"actions": actions or []}
        self.warnings = []
        self.chat = type("C", (), {"id": chat_id})()



def test_only_levels_that_remove_a_mind_from_play_are_gated():
    """`dazed` is deliberately present-but-degraded, so it is not caught. An
    over-broad guard would drop legitimate states and be switched off.
    """
    assert commit._is_gated_awareness(_cond("asleep"))
    assert commit._is_gated_awareness(_cond("unconscious"))
    assert commit._is_gated_awareness(_cond("sedated"))
    assert not commit._is_gated_awareness(_cond("dazed"))
    assert not commit._is_gated_awareness(_cond("awake"))
    assert not commit._is_gated_awareness(_cond(active=False))
    assert not commit._is_gated_awareness({"kind": "injury", "active": True,
                                           "state": {"level": "asleep"}})


def test_a_position_reasserted_unchanged_is_not_a_move(temp_db, monkeypatch):
    """§1.14 records that resolve asserts `state_diff.positions` with no
    declared movement. Treating those as movement would fire this guard on
    people standing still -- so the diff is compared against the scene, not
    merely read.
    """
    monkeypatch.setattr(commit, "get_scene",
                        lambda cid: {"positions": {"Hinami": "hall"}},
                        raising=False)
    ctx = _Ctx()
    assert commit._subjects_that_moved(ctx, {"positions": {"Hinami": "hall"}}) \
        == set()
    assert commit._subjects_that_moved(ctx, {"positions": {"Hinami": "upstairs"}}) \
        == {"Hinami"}


def test_an_action_naming_someone_as_its_target_exempts_them():
    """The exemption that keeps the guard honest. Being drugged, clubbed or
    carried to a bed is somebody ELSE's act naming you as its target, and it
    legitimately produces a gated state on a subject who was moving moments
    earlier.
    """
    ctx = _Ctx(actions=[{"attempt": "presses the cloth over her face",
                         "targets": ["Hinami"]}])
    assert commit._subjects_targeted_by_an_action(ctx) == {"Hinami"}
    assert commit._subjects_targeted_by_an_action(_Ctx()) == set()


def test_a_target_given_as_an_object_is_still_a_target():
    """Targets arrive as bare strings and as dicts across live data. Reading
    only one shape would silently drop the exemption for the other, and the
    failure would look like the guard being over-eager.
    """
    ctx = _Ctx(actions=[{"targets": [{"name": "Hinami"}]}])
    assert commit._subjects_targeted_by_an_action(ctx) == {"Hinami"}


def test_no_scene_is_not_a_movement_claim(temp_db, monkeypatch):
    """If the scene cannot be read, nobody is known to have moved. Guessing
    the other way would drop legitimate conditions on a fetch error.
    """
    def boom(cid):
        raise RuntimeError("no scene")
    monkeypatch.setattr(commit, "get_scene", boom, raising=False)
    assert commit._subjects_that_moved(_Ctx(), {"positions": {"H": "x"}}) == set()


# --- through the real commit path, not a copy of its logic -----------------

def _chat_with_scene(db, positions):
    import json, time
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("A story", "", time.time()))
    db.qi("INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
          (cid, "scene", json.dumps({"positions": positions, "rooms": {}})))
    return cid


def _ctx_for(cid, actions=None):
    ctx = _Ctx(actions=actions, chat_id=cid)
    ctx.turn = type("T", (), {"id": 1, "idx": 1, "frame_id": None})()
    ctx.cast = []
    ctx.director_resolve = {"resolved_event": ""}
    ctx.director_establish = None
    ctx.mapping_quick = None
    ctx.mapping_stage = None
    return ctx


def test_the_live_case_is_dropped_end_to_end(temp_db):
    """THE REPRODUCTION. Hinami speaks about resting, stands, yawns and walks
    upstairs; resolve asserts `asleep` on her. She moved and nothing targeted
    her, so the condition rests on what she SAID.
    """
    cid = _chat_with_scene(temp_db, {"Hinami": "shrine_interior_first_floor"})
    ctx = _ctx_for(cid, actions=[{"attempt": "walks to the shoji",
                                  "targets": []}])
    diff = {"positions": {"Hinami": "shrine_interior_upstairs"},
            "conditions": {"awareness_hinami_sleep_1930": [_cond("asleep")]}}

    commit.commit_world_entities(ctx, "n1", prepared={"diff": diff})

    rows = temp_db.q("SELECT * FROM world_conditions WHERE chat_id=?", (cid,))
    assert rows == [] or all(r["kind"] != "awareness" for r in rows), \
        "the condition landed despite resting on speech"
    assert any("rests on what they SAID" in w for w in ctx.warnings), ctx.warnings


def test_being_put_under_by_someone_else_still_lands(temp_db):
    """The exemption, through the same path. An action naming her as its
    target is somebody else's act, and a subject who was walking a moment ago
    can legitimately be carried out of the room unconscious.
    """
    cid = _chat_with_scene(temp_db, {"Hinami": "hall"})
    ctx = _ctx_for(cid, actions=[{"attempt": "presses a cloth over her face",
                                  "targets": ["Hinami"]}])
    diff = {"positions": {"Hinami": "cellar"},
            "conditions": {"c1": [_cond("unconscious")]}}

    commit.commit_world_entities(ctx, "n2", prepared={"diff": diff})

    rows = temp_db.q("SELECT kind FROM world_conditions WHERE chat_id=?", (cid,))
    assert any(r["kind"] == "awareness" for r in rows), \
        "a targeted subject was wrongly exempted from being put under"
    assert not any("rests on what they SAID" in w for w in ctx.warnings)


def test_going_under_where_you_stand_still_lands(temp_db):
    """The case the player named as legitimate: "you close your eyes and slip
    into rest". No movement, so no contradiction, so no guard.
    """
    cid = _chat_with_scene(temp_db, {"Hinami": "bedroom"})
    ctx = _ctx_for(cid, actions=[{"attempt": "closes her eyes", "targets": []}])
    diff = {"positions": {"Hinami": "bedroom"},
            "conditions": {"c2": [_cond("asleep")]}}

    commit.commit_world_entities(ctx, "n3", prepared={"diff": diff})

    rows = temp_db.q("SELECT kind FROM world_conditions WHERE chat_id=?", (cid,))
    assert any(r["kind"] == "awareness" for r in rows)
    assert ctx.warnings == []
