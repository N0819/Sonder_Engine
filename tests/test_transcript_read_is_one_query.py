"""Reading a transcript costs the same whether it is three beats or three
hundred, and a page that already holds the story is not sent it again
(review 2026-09-07, C22).

Two costs, both linear in the length of a story, both on paths a reader hits
constantly:

  * `chat_get` walked the chat's turns and asked the steps/variants table for
    the narrator's prose ONE TURN AT A TIME, and `guest_state` did the same
    for `narrator_extra` plus one `turn_player_inputs` read per turn -- on a
    payload a guest's page polls every ten seconds. Measured on the review's
    bench copy of chat 117 (124 turns): `GET /api/chats/117` issued 148
    queries, 124 of them that one read repeated.
  * every finished beat made the page re-read the WHOLE story to learn about
    the one turn that was just appended -- 266,689 bytes on that same chat,
    against 32,209 for the slice.

The first is `persist.steps.active_mappings`, which asks once. The second is
`?since_turn_id=`, which is sound only because a transcript GROWS AT THE END:
`stale` is only ever set within one turn's own steps, and prose, player input
and `dialogue_log` are each written once, for the turn they belong to. An
EDIT to an existing turn is not an append, which is why the client asks for a
slice only after a new beat and reads the story whole after everything else.

The query-count tests compare two chats of different lengths rather than
asserting a number: the property is that the cost does not grow with the
story, and a number would need editing every time an unrelated read is added
to the route.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from core import db
from persist import steps as step_store
from web import app as app_module
from web import guest_access as guest


# --------------------------------------------------------------------------
# Fixtures: stories of two different lengths
# --------------------------------------------------------------------------

def _chat(temp_db, name="Story"):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      (name, "", time.time()))


def _turn(temp_db, chat_id, idx, player_input=""):
    return temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, player_input, time.time()))


def _step(temp_db, turn_id, key, content, *, ordn=0, stale=0, active=1):
    sid = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,?)",
        (turn_id, key, key, ordn, stale))
    temp_db.qi("INSERT INTO variants(step_id,content,created,active) "
               "VALUES(?,?,?,?)",
               (sid, json.dumps(content), time.time(), active))
    return sid


def _event(temp_db, chat_id, turn_id, speaker, quote):
    temp_db.qi("INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
               (chat_id, turn_id, json.dumps(
                   {"turn": 0, "summary": "s", "event": "e",
                    "dialogue_log": [{"speaker": speaker,
                                      "exact_quote": quote}]})))


def _story(temp_db, beats, name="Story"):
    """A chat of `beats` turns, each with narrated prose and a spoken line."""
    cid = _chat(temp_db, name)
    tids = []
    for idx in range(beats):
        tid = _turn(temp_db, cid, idx, f"beat {idx}")
        _step(temp_db, tid, "narrator", {"prose": f"prose {idx}"}, ordn=7)
        _event(temp_db, cid, tid, "Mara", f"line {idx}")
        tids.append(tid)
    return cid, tids


def _statements(fn):
    """Every SQL statement one call executes, via SQLite's own trace hook --
    no monkeypatch, so it counts what the connection really ran rather than
    what one module's imported name happened to be."""
    seen = []
    conn = db.conn()
    conn.set_trace_callback(seen.append)
    try:
        result = fn()
    finally:
        conn.set_trace_callback(None)
    return result, seen


# --------------------------------------------------------------------------
# One query, not one per turn
# --------------------------------------------------------------------------

class TestTheManyTurnReadAsksOnce:
    def test_it_answers_exactly_what_the_per_turn_read_answers(self, temp_db):
        cid, tids = _story(temp_db, 3)
        # ...plus the shapes a real database holds: a step that never ran, a
        # step whose content is not a mapping, one carrying the engine's own
        # repair log, and a superseded variant that is no longer active.
        bare = _turn(temp_db, cid, 3)
        listy = _turn(temp_db, cid, 4)
        _step(temp_db, listy, "narrator", ["bare prose"])
        noted = _turn(temp_db, cid, 5)
        _step(temp_db, noted, "narrator",
              {"prose": "kept", step_store.ENGINE_NOTES_KEY: {"warnings": []}})
        superseded = _turn(temp_db, cid, 6)
        _step(temp_db, superseded, "narrator", {"prose": "old"}, active=0)
        _step(temp_db, superseded, "narrator", {"prose": "new"}, ordn=1)

        many = step_store.active_mappings(cid, "narrator")
        every = tids + [bare, listy, noted, superseded]
        assert {t: many.get(t, {}) for t in every} == {
            t: step_store.active_mapping(t, "narrator") for t in every}
        assert many[noted] == {"prose": "kept"}
        assert many[superseded] == {"prose": "new"}

    def test_a_turn_holding_the_key_twice_answers_with_the_same_one(
            self, temp_db):
        """`save_step` upserts on (turn_id, key) and no index enforces it, so
        a repaired or hand-built database can hold two. Last-one-wins and
        first-one-wins are different prose on the page, so the many-turn read
        answers with the row the single-turn read answers with."""
        cid = _chat(temp_db)
        tid = _turn(temp_db, cid, 0)
        _step(temp_db, tid, "narrator", {"prose": "first"}, ordn=7)
        _step(temp_db, tid, "narrator", {"prose": "second"}, ordn=8)

        assert step_store.active_mappings(cid, "narrator")[tid] == (
            step_store.active_mapping(tid, "narrator"))
        assert app_module.chat_get(cid)["turns"][0]["prose"] == "first"

    def test_it_stops_at_the_chat_it_was_asked_about(self, temp_db):
        mine, _ = _story(temp_db, 2, "mine")
        theirs, other_tids = _story(temp_db, 2, "theirs")
        assert set(step_store.active_mappings(mine, "narrator")).isdisjoint(
            other_tids)
        assert len(step_store.active_mappings(theirs, "narrator")) == 2

    def test_after_turn_id_answers_only_what_follows_it(self, temp_db):
        cid, tids = _story(temp_db, 4)
        assert sorted(step_store.active_mappings(
            cid, "narrator", after_turn_id=tids[1])) == tids[2:]
        assert step_store.active_mappings(
            cid, "narrator", after_turn_id=tids[-1]) == {}

    def test_the_chat_payload_costs_the_same_at_any_length(self, temp_db):
        short_id, _ = _story(temp_db, 3, "short")
        long_id, _ = _story(temp_db, 30, "long")

        short, short_sql = _statements(lambda: app_module.chat_get(short_id))
        long, long_sql = _statements(lambda: app_module.chat_get(long_id))

        assert len(short["turns"]) == 3 and len(long["turns"]) == 30
        assert len(long_sql) == len(short_sql), (
            "the transcript read must not grow with the story: "
            f"{len(short_sql)} statements for 3 turns, "
            f"{len(long_sql)} for 30")

    def test_the_prose_is_still_each_turns_own(self, temp_db):
        cid, _ = _story(temp_db, 5)
        payload = app_module.chat_get(cid)
        assert [t["prose"] for t in payload["turns"]] == [
            f"prose {i}" for i in range(5)]
        assert [t["speech"] for t in payload["turns"]] == [
            [{"speaker": "Mara", "quote": f"line {i}"}] for i in range(5)]


# --------------------------------------------------------------------------
# The slice
# --------------------------------------------------------------------------

class TestTheSliceSaysWhatTheWholeStorySays:
    def test_the_new_turns_are_the_tail_of_the_whole_payload(self, temp_db):
        cid, tids = _story(temp_db, 6)
        whole = app_module.chat_get(cid)
        sliced = app_module.chat_get(cid, tids[3])

        assert sliced["turns"] == whole["turns"][4:]
        assert sliced["turns_since"] == tids[3]
        # Everything that is not the transcript is not append-only, so it
        # still arrives whole and unchanged.
        assert {k: v for k, v in sliced.items()
                if k not in ("turns", "turns_since")} == {
            k: v for k, v in whole.items() if k != "turns"}

    def test_a_whole_read_never_looks_like_a_slice(self, temp_db):
        cid, _ = _story(temp_db, 2)
        assert "turns_since" not in app_module.chat_get(cid)

    def test_nothing_new_answers_nothing(self, temp_db):
        cid, tids = _story(temp_db, 3)
        sliced = app_module.chat_get(cid, tids[-1])
        assert sliced["turns"] == []
        assert sliced["turns_since"] == tids[-1]

    def test_the_new_turn_brings_its_own_speech_and_staleness(self, temp_db):
        """The three per-turn indexes are filtered by the same boundary, so a
        spliced turn arrives coloured and flagged exactly as a whole read
        would have delivered it."""
        cid, tids = _story(temp_db, 2)
        fresh = _turn(temp_db, cid, 2, "beat 2")
        _step(temp_db, fresh, "director_resolve", {}, ordn=4, stale=1)
        _step(temp_db, fresh, "narrator", {"prose": "prose 2"}, ordn=7)
        _event(temp_db, cid, fresh, "Mara", "line 2")

        whole = app_module.chat_get(cid)["turns"][-1]
        sliced = app_module.chat_get(cid, tids[-1])["turns"]
        assert sliced == [whole]
        assert whole["speech"] == [{"speaker": "Mara", "quote": "line 2"}]
        assert whole["prose_stale"] is False and whole["stale"] is True
        assert whole["stale_from"]["key"] == "director_resolve"

    def test_the_route_takes_it_as_a_query_parameter(self, temp_db):
        cid, tids = _story(temp_db, 3)
        guest.reset_host_account()
        with TestClient(app_module.app) as c:
            r = c.post("/api/auth/setup",
                       json={"username": "host", "password": "pw12345"})
            assert r.status_code == 200, r.text
            body = c.get(f"/api/chats/{cid}?since_turn_id={tids[0]}").json()
        guest.reset_host_account()
        assert [t["id"] for t in body["turns"]] == tids[1:]
        assert body["turns_since"] == tids[0]


# --------------------------------------------------------------------------
# The guest poll, which asks the same question every ten seconds
# --------------------------------------------------------------------------

class TestTheGuestPollAsksOnce:
    @pytest.fixture()
    def host(self, temp_db):
        guest.reset_host_account()
        guest._join_attempts.clear()
        guest._login_attempts.clear()
        with TestClient(app_module.app) as c:
            r = c.post("/api/auth/setup",
                       json={"username": "host", "password": "pw12345"})
            assert r.status_code == 200, r.text
            yield c
        guest.reset_host_account()
        guest._join_attempts.clear()
        guest._login_attempts.clear()

    def _joined(self, host, temp_db, chat_id, name="Guest"):
        pid = temp_db.qi(
            "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
            (name, "{}", "{}"))
        temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status) "
                   "VALUES(?,?,'active')", (chat_id, pid))
        invite = host.post(f"/api/chats/{chat_id}/guest_invites",
                           json={"persona_id": pid}).json()
        gc = TestClient(app_module.app)
        assert gc.post("/api/join", json={"code": invite["code"]}).status_code == 200
        return gc, pid

    def _seat(self, temp_db, chat_id, tids, seats):
        """The real shape: ONE `narrator_extra` step per turn, holding every
        seat's own render keyed by persona id (`agents.narration` writes it
        that way), and one input row per seat per turn."""
        for idx, tid in enumerate(tids):
            _step(temp_db, tid, "narrator_extra",
                  {str(pid): {"prose": f"{name} prose {idx}"}
                   for pid, name in seats.items()}, ordn=8)
            for pid, name in seats.items():
                temp_db.qi(
                    "INSERT INTO turn_player_inputs"
                    "(chat_id,turn_idx,persona_id,input,created) "
                    "VALUES(?,?,?,?,?)",
                    (chat_id, idx, pid, f"{name} said {idx}", time.time()))

    def test_each_seat_still_reads_its_own_story(self, host, temp_db):
        """Two people at one table are shown two different stories on purpose.
        Reading both seats' inputs in one query must not hand either of them
        the other's -- so this asserts the seats, not just the count."""
        cid, tids = _story(temp_db, 3)
        gc_a, pid_a = self._joined(host, temp_db, cid, "Ana")
        gc_b, pid_b = self._joined(host, temp_db, cid, "Bo")
        self._seat(temp_db, cid, tids, {pid_a: "Ana", pid_b: "Bo"})

        for client, name in ((gc_a, "Ana"), (gc_b, "Bo")):
            turns = client.get("/api/guest/state").json()["turns"]
            assert [t["player_input"] for t in turns] == [
                f"{name} said {i}" for i in range(3)]
            assert [t["prose"] for t in turns] == [
                f"{name} prose {i}" for i in range(3)]

    def test_a_seat_with_nothing_written_reads_nothing(self, host, temp_db):
        """A turn this persona did not write in, and a turn with no per-player
        render: absent stays absent rather than borrowing the seat next door."""
        cid, tids = _story(temp_db, 2)
        gc, pid = self._joined(host, temp_db, cid, "Ana")
        self._seat(temp_db, cid, tids[:1], {pid: "Ana"})

        turns = gc.get("/api/guest/state").json()["turns"]
        assert [t["player_input"] for t in turns] == ["Ana said 0", None]
        assert [t["prose"] for t in turns] == ["Ana prose 0", ""]

    def test_the_poll_costs_the_same_at_any_length(self, host, temp_db):
        short_id, short_tids = _story(temp_db, 3, "short")
        long_id, long_tids = _story(temp_db, 30, "long")
        gc_short, pid_short = self._joined(host, temp_db, short_id, "Ana")
        gc_long, pid_long = self._joined(host, temp_db, long_id, "Bo")
        self._seat(temp_db, short_id, short_tids, {pid_short: "Ana"})
        self._seat(temp_db, long_id, long_tids, {pid_long: "Bo"})

        # The route reads the grant off the request, so it is exercised
        # through the handler with a stub request rather than over HTTP --
        # the trace hook counts this thread's connection.
        class _Req:
            def __init__(self, grant):
                self.state = type("S", (), {"guest_grant": grant})()

        short, short_sql = _statements(lambda: app_module.guest_state(
            _Req({"chat_id": short_id, "persona_id": pid_short})))
        long, long_sql = _statements(lambda: app_module.guest_state(
            _Req({"chat_id": long_id, "persona_id": pid_long})))

        assert len(short["turns"]) == 3 and len(long["turns"]) == 30
        assert len(long_sql) == len(short_sql), (
            f"{len(short_sql)} statements for 3 turns, "
            f"{len(long_sql)} for 30")
