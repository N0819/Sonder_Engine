"""The room answers the way an assistant does: as it writes, with its working.

The panel posted a line, waited on a reply that can legitimately take half a
minute of tool calls, and showed a spinner over all of it. What the engine
already had was the whole seam -- `token_sink`, an ndjson stream, a browser
decoder -- armed by `agents/runtime.py` for pipeline steps and by nothing else.
So this is a wiring job, not a mechanism: the room arms the same sinks in a
worker thread and yields what they carry.

The invariant that matters is that streaming changed no WRITE. The same rows
land in the same order as the non-streaming route, so a client that cannot
stream loses only the watching.
"""
import json
import time

import pytest

from story import room_conversation as room


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Room stream", "A cold harbour.", time.time()))


def _events(cid, text, frame_id=None):
    return list(room.converse_stream(cid, frame_id, text))


def _seat(monkeypatch, fn):
    monkeypatch.setattr(room, "PLANNER", fn)


class TestTheShapeOfTheStream:
    def test_the_players_line_is_stored_and_announced_first(self, temp_db,
                                                            monkeypatch):
        cid = _chat(temp_db)
        _seat(monkeypatch, lambda c, f, t, **kw: {"reply": "Noted."})

        events = _events(cid, "Plan a town up the coast.")

        assert events[0]["type"] == "room_message"
        assert events[0]["message"]["role"] == "player"
        assert events[0]["message"]["text"] == "Plan a town up the coast."

    def test_it_ends_with_the_stored_rows_and_the_status(self, temp_db,
                                                        monkeypatch):
        cid = _chat(temp_db)
        _seat(monkeypatch, lambda c, f, t, **kw: {"reply": "A town, then."})

        done = _events(cid, "Plan a town.")[-1]

        assert done["type"] == "room_done"
        assert [r["text"] for r in done["replies"]] == ["A town, then."]
        assert done["seated"] is True
        assert "mandates" in done and "status" in done

    def test_the_loops_own_events_ride_through(self, temp_db, monkeypatch):
        """A step and a tool call are what the panel shows instead of a
        spinner, and they are what the card calls reporting what landed."""
        def planner(c, f, t, *, on_event=None):
            on_event({"type": "room_step", "step": 1})
            on_event({"type": "room_tool", "tool": "search_lore",
                      "refused": None, "error": None})
            return {"reply": "Read the lore first."}

        cid = _chat(temp_db)
        _seat(monkeypatch, planner)

        kinds = [e["type"] for e in _events(cid, "What is up the coast?")]

        assert kinds == ["room_message", "room_step", "room_tool", "room_done"]

    def test_prose_and_trace_arrive_on_separate_channels(self, temp_db,
                                                         monkeypatch):
        from llm.providers import reasoning_sink, token_sink

        def planner(c, f, t, *, on_event=None):
            token_sink.get()("A town")
            reasoning_sink.get()("weighing the coast road")
            token_sink.get()(", then.")
            return {"reply": "A town, then."}

        cid = _chat(temp_db)
        _seat(monkeypatch, planner)

        events = _events(cid, "Plan a town.")
        prose = "".join(e["delta"] for e in events if e["type"] == "token")
        trace = "".join(e["delta"] for e in events if e["type"] == "reasoning")

        assert prose == "A town, then."
        assert trace == "weighing the coast road"


class TestItChangedNoWrite:
    def test_the_same_rows_land_as_the_unstreamed_route(self, temp_db,
                                                        monkeypatch):
        _seat(monkeypatch, lambda c, f, t, **kw: {"reply": "Noted."})
        a, b = _chat(temp_db), _chat(temp_db)

        room.converse(a, None, "Plan a town.")
        _events(b, "Plan a town.")

        def rows(cid):
            return [(r["role"], r["text"]) for r in room.messages(cid, None)]
        assert rows(a) == rows(b)

    def test_a_raising_planner_keeps_the_players_line_and_reports(
            self, temp_db, monkeypatch):
        def boom(c, f, t, **kw):
            raise RuntimeError("the provider fell over")

        cid = _chat(temp_db)
        _seat(monkeypatch, boom)

        done = _events(cid, "Plan a town.")[-1]

        assert "the provider fell over" in done["error"]
        assert done["replies"] == []
        assert [r["role"] for r in room.messages(cid, None)] == ["player"]

    def test_a_seam_that_cannot_take_a_watcher_still_runs(self, temp_db,
                                                          monkeypatch):
        """The watcher is advisory. A seam seated before it existed -- or any
        test double with the old signature -- must not be broken by it."""
        _seat(monkeypatch, lambda c, f, t: {"reply": "Old signature."})

        cid = _chat(temp_db)
        done = _events(cid, "Plan a town.")[-1]

        assert [r["text"] for r in done["replies"]] == ["Old signature."]
        assert done["error"] is None

    def test_an_empty_line_is_refused_before_anything_is_stored(self, temp_db):
        cid = _chat(temp_db)
        with pytest.raises(ValueError):
            _events(cid, "   ")
        assert room.messages(cid, None) == []


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient

    from web import app as app_module
    from web import guest_access as guest
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


class TestTheRoute:
    def test_it_streams_ndjson_and_the_client_gets_the_same_end(
            self, temp_db, client, monkeypatch):
        _seat(monkeypatch, lambda c, f, t, **kw: {"reply": "Noted."})
        cid = _chat(temp_db)

        r = client.post("/api/chats/%d/room/messages/stream" % cid,
                        json={"text": "Plan a town."})
        assert r.status_code == 200, r.text
        assert "ndjson" in r.headers["content-type"]
        events = [json.loads(line) for line in r.text.splitlines() if line]

        assert events[0]["type"] == "room_message"
        assert events[-1]["type"] == "room_done"
        assert [x["text"] for x in events[-1]["replies"]] == ["Noted."]

    def test_a_refusal_is_an_http_error_not_an_event(self, temp_db, client):
        """A 400 delivered inside a 200 is a refusal the client has to be
        taught to look for."""
        cid = _chat(temp_db)

        r = client.post("/api/chats/%d/room/messages/stream" % cid,
                        json={"text": "   "})
        assert r.status_code == 400
