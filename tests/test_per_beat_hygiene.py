"""Per-beat hygiene: the shared fetches and the write-on-change guard.

Review 2026-09-07 C20. Every mechanism here makes a beat pay once for
something it was paying for per body, per observer or per mind; each test
holds the half that could go wrong -- that the shared answer is still the
private answer, and that the memo is invalidated by what changes it.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager

from agents import character as ch
from agents import common
from core import db


@contextmanager
def _statements():
    """Every SQL statement this connection runs while the block is open."""
    seen = []
    connection = db.conn()
    connection.set_trace_callback(lambda sql: seen.append(" ".join(sql.split())))
    try:
        yield seen
    finally:
        connection.set_trace_callback(None)


def _chat(temp_db, name="Hygiene"):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      (name, "", time.time()))


# ---------------------------------------------------------------------------
# A byte-identical write is not a write
# ---------------------------------------------------------------------------

def test_an_unchanged_world_row_is_not_rewritten(temp_db):
    cid = _chat(temp_db)
    assert db.wset_if_changed(cid, "known", {"Ada": ["Bo"]}) is True
    token_after_write = db.world_read_token(cid, "known")

    with _statements() as seen:
        assert db.wset_if_changed(cid, "known", {"Ada": ["Bo"]}) is False
    assert not [s for s in seen if s.startswith("INSERT")]
    # The row's read token is what a cached parse is validated against: an
    # identical rewrite would have thrown every one of them away.
    assert db.world_read_token(cid, "known") == token_after_write
    assert db.wget(cid, "known", {}) == {"Ada": ["Bo"]}


def test_a_changed_world_row_is_written_and_moves_its_token(temp_db):
    cid = _chat(temp_db)
    db.wset_if_changed(cid, "known", {"Ada": ["Bo"]})
    before = db.world_read_token(cid, "known")
    assert db.wset_if_changed(cid, "known", {"Ada": ["Bo", "Cyd"]}) is True
    assert db.wget(cid, "known", {}) == {"Ada": ["Bo", "Cyd"]}
    assert db.world_read_token(cid, "known") != before


def test_a_row_that_does_not_exist_yet_is_always_written(temp_db):
    cid = _chat(temp_db)
    assert db.wset_if_changed(cid, "active_books", []) is True
    assert db.wget(cid, "active_books", None) == []
    assert db.wset_if_changed(cid, "active_books", []) is False


# ---------------------------------------------------------------------------
# The stage's standing ledgers: one fetch, sliced per room
# ---------------------------------------------------------------------------

def _scene():
    return {"rooms": {"square": {"name": "Square", "size": "large",
                                 "adjacent": []},
                      "keep": {"name": "Keep", "adjacent": []}},
            "positions": {}}


def test_the_shared_fetch_answers_what_each_reader_would_have_read(temp_db):
    from story import artifacts as artifacts_model
    from story import couriers as couriers_model
    from world import crowds as crowds_model

    cid = _chat(temp_db)
    scene = _scene()
    db.wset(cid, crowds_model.CROWDS_WORLD_KEY, [{
        "uid": "crowd_1", "room_uid": "square", "band": "a throng",
        "composition": "dockworkers", "since_turn": 0}])
    db.wset(cid, couriers_model.COURIERS_WORLD_KEY, [{
        "uid": "c1", "at": "keep", "route": ["keep", "square"], "leg": 0,
        "status": couriers_model.EN_ROUTE,
        "description": "a rider in a mud-spattered cloak"}])
    db.wset(cid, artifacts_model.ARTIFACTS_WORLD_KEY, [{
        "uid": "a1", "room": "square", "status": artifacts_model.POSTED,
        "description": "a hand-lettered bill"}])

    inputs = common.chatter_inputs(cid, scene)
    for room in ("square", "keep"):
        assert common.crowds_for_room(cid, scene, room, inputs) \
            == common.crowds_for_room(cid, scene, room)
        assert common.couriers_for_room(cid, scene, room, inputs) \
            == common.couriers_for_room(cid, scene, room)
        assert common.artifacts_for_room(cid, scene, room, inputs) \
            == common.artifacts_for_room(cid, scene, room)
    assert common.crowds_for_room(cid, scene, "square", inputs)
    assert common.couriers_for_room(cid, scene, "keep", inputs)
    assert common.artifacts_for_room(cid, scene, "square", inputs)


def test_the_stage_reads_each_standing_ledger_once_however_many_perceivers(
        temp_db):
    cid = _chat(temp_db)
    scene = _scene()
    inputs = common.chatter_inputs(cid, scene)
    with _statements() as seen:
        for _observer in range(6):
            for room in ("square", "keep"):
                common.crowds_for_room(cid, scene, room, inputs)
                common.couriers_for_room(cid, scene, room, inputs)
                common.artifacts_for_room(cid, scene, room, inputs)
    # Twelve deliveries, three reads: one per ledger for the whole stage.
    reads = [s for s in seen if "FROM world" in s]
    assert len(reads) == 3, reads
    for key in ("crowds", "couriers", "artifacts"):
        assert len([s for s in reads if "'%s'" % key in s]) == 1


def test_a_reader_with_no_shared_fetch_still_reads_for_itself(temp_db):
    cid = _chat(temp_db)
    scene = _scene()
    with _statements() as seen:
        common.crowds_for_room(cid, scene, "square")
        common.couriers_for_room(cid, scene, "square")
        common.artifacts_for_room(cid, scene, "square")
    for key in ("crowds", "couriers", "artifacts"):
        assert len([s for s in seen
                    if "FROM world" in s and "'%s'" % key in s]) == 1


def test_a_fresh_fetch_sees_a_ledger_the_beat_changed(temp_db):
    """The shared fetch is the STAGE's, not the turn's: a later stage builds
    its own, and must see what commit wrote in between."""
    from world import crowds as crowds_model

    cid = _chat(temp_db)
    scene = _scene()
    assert common.crowds_for_room(cid, scene, "square",
                                  common.chatter_inputs(cid, scene)) == []
    db.wset(cid, crowds_model.CROWDS_WORLD_KEY, [{
        "uid": "crowd_1", "room_uid": "square", "band": "a throng",
        "composition": "dockworkers", "since_turn": 0}])
    assert common.crowds_for_room(cid, scene, "square",
                                  common.chatter_inputs(cid, scene))


# ---------------------------------------------------------------------------
# One host answer per composed view
# ---------------------------------------------------------------------------

def test_the_beneath_setting_is_asked_once_for_a_scene_of_bodies(temp_db):
    scene = {"attire": {
        "Ada": {"wearing": ["a coat"], "state": []},
        "Bo": {"wearing": ["a shirt"], "state": []},
        "Cyd": {"wearing": ["a robe"], "state": []},
    }}
    with _statements() as seen:
        compact = common.scene_compact_attire(scene)
    assert len([s for s in seen if "FROM settings" in s]) == 1
    # Same answer as asking body by body.
    assert compact == {name: common.compact_attire(entry)
                       for name, entry in scene["attire"].items()}


def test_a_caller_that_passes_the_answer_overrides_the_lookup(temp_db):
    entry = {"regions": {"torso": {"garments": [], "state": "bare",
                                   "beneath": "an old scar"}}}
    db.set_setting("attire_beneath", "0")
    assert "scar" not in json.dumps(common.attire_view(entry))
    assert "scar" in json.dumps(common.attire_view(entry, beneath=True))
    assert "scar" not in json.dumps(common.attire_view(entry, beneath=False))


# ---------------------------------------------------------------------------
# The turn's prior-variant window
# ---------------------------------------------------------------------------

def _beat(temp_db, cid, idx, steps):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, idx, "", time.time()))
    for ord_, (key, content) in enumerate(steps.items()):
        step_id = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
            (turn_id, key, key, ord_))
        temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) "
            "VALUES(?,?,?,1)", (step_id, json.dumps(content), time.time()))
    return turn_id


def _two_minds(temp_db):
    """Two beats in which two minds each declared through their OWN
    `character:<id>` step -- the shape `build_plan` uses at autonomy 0, and
    the one a per-character query used to isolate with its WHERE clause."""
    cid = _chat(temp_db)
    for idx in (0, 1):
        _beat(temp_db, cid, idx, {
            "director_interpret": {"speech": ""},
            "character:7": {"name": "Ada", "char_id": 7,
                            "interaction": {"selected_response":
                                            "ask about the ferry %d" % idx}},
            "character:8": {"name": "Bo", "char_id": 8,
                            "interaction": {"selected_response":
                                            "refuse to answer %d" % idx}},
            "director_resolve": {"dialogue_log": [
                {"speaker": "Ada", "exact_quote": "When does it sail? (%d)" % idx},
                {"speaker": "Bo", "exact_quote": "It does not. (%d)" % idx}]},
        })
    return cid


def test_one_window_serves_every_mind_and_each_reads_only_its_own(temp_db):
    cid = _two_minds(temp_db)
    private = {
        char_id: (ch._recent_self_lines(cid, name, 2),
                  ch._recent_self_moves(cid, char_id, 2))
        for char_id, name in ((7, "Ada"), (8, "Bo"))}

    shared = {}
    for char_id, name in ((7, "Ada"), (8, "Bo")):
        assert ch._recent_self_lines(cid, name, 2, cache=shared) \
            == private[char_id][0]
        assert ch._recent_self_moves(cid, char_id, 2, cache=shared) \
            == private[char_id][1]
    # Each mind's ledger holds its own lines and moves, and no other's.
    assert [row["said"] for row in private[7][0]] \
        == ["When does it sail? (0)", "When does it sail? (1)"]
    assert all("ferry" in json.dumps(row) for row in private[7][1])
    assert all("refuse" in json.dumps(row) for row in private[8][1])


def test_the_window_is_read_once_for_the_turn_not_once_per_mind(temp_db):
    cid = _two_minds(temp_db)
    shared = {}
    with _statements() as seen:
        for char_id, name in ((7, "Ada"), (8, "Bo"), (9, "Cyd")):
            ch._recent_self_lines(cid, name, 2, cache=shared)
            ch._recent_self_moves(cid, char_id, 2, cache=shared)
            ch._player_quiet_beats(cid, 2, None, cache=shared)
            ch._unanswered_question_note(cid, name, char_id, 2, None,
                                         cache={}, rows_cache=shared)
    windows = [s for s in seen if "JOIN variants" in s]
    assert len(windows) == 4, windows


def test_the_window_is_keyed_by_the_beat_it_looks_back_from(temp_db):
    """The memo must not answer beat 2's question with beat 1's rows."""
    cid = _two_minds(temp_db)
    shared = {}
    at_one = ch._recent_self_lines(cid, "Ada", 1, cache=shared)
    at_two = ch._recent_self_lines(cid, "Ada", 2, cache=shared)
    assert at_one == ch._recent_self_lines(cid, "Ada", 1)
    assert at_two == ch._recent_self_lines(cid, "Ada", 2)
    assert len(at_one) == 1 and len(at_two) == 2


def test_a_mind_with_no_shared_cache_reads_for_itself(temp_db):
    cid = _two_minds(temp_db)
    assert ch._recent_self_moves(cid, 7, 2, cache=None) \
        == ch._recent_self_moves(cid, 7, 2, cache={})
