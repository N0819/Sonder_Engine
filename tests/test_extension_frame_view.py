"""The frame-bound extension facade: one projection, one era.

The defect this file exists against was found by an external integrator and
is a COMPOSITION defect, which is why the central test here is route-level
rather than a unit test of any helper: `api.player_view` resolved the latest
committed turn's frame while `api.frame_state(...).get()` and
`api.char_state(...).get()` followed the ambient `active_frame_id` -- unset
on an extension HTTP route, so answering for the present. Each call was
correct alone; a real route composing them built a DTO with scene and
identity from one era and mission, clock and crew state from another --
structurally valid, semantically impossible, and worse than a hard failure
because the consumer receives plausible data.

`api.at_frame(chat_id)` resolves the frame ONCE and binds every
frame-sensitive read and write to it. These tests drive the real route
dispatch path, then pin the contract's edges: the omitted/None/integer
selection vocabulary, refusal of foreign and unknown frames, a frame with no
turns, a bound read surviving an ambient frame change without leaking the
contextvar, and writes landing only in the bound era under the unchanged
commit gate.
"""

from __future__ import annotations

import json
import time

import pytest

import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _chat, _character, _enable, _write_extension, ext_root,
)

EXT = "coherence"

#: A real extension whose route builds one projection from four public
#: reads through one bound facade -- the exact composition that mixed
#: frames when the reads each chose their own.
ENTRY = """
def register(api):
    def projection(request):
        chat_id = request.chat_id
        raw = request.query.get("frame")
        if raw is None:
            host = api.at_frame(chat_id)
        elif raw == "present":
            host = api.at_frame(chat_id, None)
        else:
            host = api.at_frame(chat_id, int(raw))
        person_id = int(request.query["person_id"])
        return {
            "frame_id": host.frame_id,
            "player": host.player_view("player"),
            "story": host.story_view(),
            "frame_state": host.frame_state().get() or {},
            "char_state": host.char_state(person_id).get() or {},
            "story_state": api.state(chat_id).get() or {},
        }

    api.add_route("/projection", projection, methods=("GET",))
"""


@pytest.fixture
def campaign(temp_db, ext_root):
    """Present and future eras that cannot be confused: distinct location,
    clock, mission revision and per-character duty, with the story's LATEST
    turn in the future frame."""
    from core.db import wset, wset_for_frame
    from story.scene import set_char_state
    from web import app

    _write_extension(ext_root, EXT, {
        "id": EXT, "version": "1.0.0", "ext_api": 1, "name": "Coherence",
        "capabilities": {"python": "extension.py", "chat_state": True},
    }, {"extension.py": ENTRY})
    _enable(EXT)

    chat_id = _chat(temp_db, "Two eras")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Sam", json.dumps({"name": "Sam"})))
    temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?",
               (persona_id, chat_id))
    char_id = _character(temp_db, chat_id, "Ilse", "uid-ilse",
                         state=json.dumps(
                             {"ext:coherence": {"duty": "present"}}))

    # The present era.
    wset(chat_id, "scene", {
        "location": "the observatory", "time": "late",
        "rooms": {"dome": {"name": "The Dome"}},
        "positions": {"Sam": "dome", "Ilse": "dome"}, "entities": {}})
    wset(chat_id, "simulation_clock",
         {"elapsed_seconds": 60.0, "display": "now", "time_scale": "scene"})
    wset(chat_id, "extf:coherence", {"mission": {"revision": 1}})
    wset(chat_id, "ext:coherence", {"campaign": "ashes"})
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "look", time.time()))

    # The future era, holding the latest turn.
    future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10,
                                         "kind": "future"})
    wset_for_frame(chat_id, "scene", {
        "location": "future-bridge", "time": "after",
        "rooms": {"bridge": {"name": "Future Bridge"}},
        "positions": {"Sam": "bridge", "Ilse": "bridge"}, "entities": {}},
        future["id"])
    wset_for_frame(chat_id, "simulation_clock",
                   {"elapsed_seconds": 9000.0, "display": "after",
                    "time_scale": "scene"}, future["id"])
    wset_for_frame(chat_id, "extf:coherence",
                   {"mission": {"revision": 77}}, future["id"])
    set_char_state(chat_id, char_id,
                   json.dumps({"ext:coherence": {"duty": "future"}}),
                   frame_id=future["id"])
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)",
        (chat_id, 9, "look", time.time(), future["id"]))

    return {"chat_id": chat_id, "char_id": char_id, "future": future}


def _api():
    return extension_runtime._apis[EXT]


def _projection(campaign, frame=None):
    query = {"chat_id": str(campaign["chat_id"]),
             "person_id": str(campaign["char_id"])}
    if frame is not None:
        query["frame"] = frame
    return extension_runtime.dispatch_route(EXT, "GET", "/projection",
                                            query=query)


# ---------------------------------------------------------------- the route


class TestRouteLevelProjection:
    """The reviewer's acceptance test, run through the real dispatch path:
    every projected field from one selected frame, then the inverse."""

    def test_every_field_comes_from_the_latest_turns_frame(self, campaign):
        out = _projection(campaign)

        future_id = campaign["future"]["id"]
        assert out["frame_id"] == future_id
        assert out["player"]["frame"]["id"] == future_id
        assert out["player"]["location"] == {"room_id": "bridge",
                                             "name": "Future Bridge"}
        assert out["player"]["clock"]["display"] == "after"
        assert out["story"]["frame"]["id"] == future_id
        assert out["story"]["scene"]["location"] == "future-bridge"
        assert out["frame_state"]["mission"]["revision"] == 77
        assert out["char_state"]["duty"] == "future"

    def test_selecting_the_present_inverts_every_field(self, campaign):
        out = _projection(campaign, frame="present")

        assert out["frame_id"] is None
        assert out["player"]["frame"] is None
        assert out["player"]["location"] == {"room_id": "dome",
                                             "name": "The Dome"}
        assert out["player"]["clock"]["display"] == "now"
        assert out["story"]["frame"] is None
        assert out["story"]["scene"]["location"] == "the observatory"
        assert out["story"]["turn"]["idx"] == 1, \
            "the present's own latest turn, not the story-wide one"
        assert out["frame_state"]["mission"]["revision"] == 1
        assert out["char_state"]["duty"] == "present"

    def test_chat_global_state_is_untouched_by_the_binding(self, campaign):
        """`api.state` stays off the facade because it is chat-global by
        design -- the same answer in every era is the feature."""
        latest = _projection(campaign)
        present = _projection(campaign, frame="present")

        assert latest["story_state"] == present["story_state"] \
            == {"campaign": "ashes"}


# ---------------------------------------------------------------- selection


class TestAtFrameSelection:
    def test_a_frame_of_another_chat_is_refused(self, temp_db, campaign):
        from web import app

        other = _chat(temp_db, "Elsewhere")
        foreign = app.frames_create(other, {"label": "Theirs", "ordinal": 2})

        with pytest.raises(ExtensionError, match="no frame"):
            _api().at_frame(campaign["chat_id"], foreign["id"])

    def test_an_unknown_frame_is_refused_with_the_same_text_shape(
            self, campaign):
        """The refusal must not disclose whether the id exists somewhere: an
        extension holding chat A cannot probe chat B's frame ids."""
        with pytest.raises(ExtensionError, match="no frame"):
            _api().at_frame(campaign["chat_id"], 987654)

    def test_an_unknown_chat_is_refused(self, temp_db, campaign):
        with pytest.raises(ExtensionError, match="no chat"):
            _api().at_frame(987654)

    def test_a_story_with_no_turns_stands_in_the_present(self, temp_db,
                                                         campaign):
        empty = _chat(temp_db, "Unstarted")

        bound = _api().at_frame(empty)

        assert bound.frame_id is None

    def test_a_frame_with_no_turns_is_honoured_not_fallen_back_from(
            self, temp_db, campaign):
        from core.db import wset_for_frame
        from web import app

        quiet = app.frames_create(campaign["chat_id"],
                                  {"label": "Quiet", "ordinal": 20,
                                   "kind": "future"})
        wset_for_frame(campaign["chat_id"], "extf:coherence",
                       {"mission": {"revision": 5}}, quiet["id"])

        bound = _api().at_frame(campaign["chat_id"], quiet["id"])
        view = bound.story_view()

        assert bound.frame_id == quiet["id"]
        assert view["turn"] is None
        assert view["frame"]["id"] == quiet["id"]
        assert bound.frame_state().get()["mission"]["revision"] == 5, \
            "provisioned state exists before any turn runs in the era"

    def test_explicit_frame_ids_work_on_the_flat_view_methods_too(
            self, campaign):
        api = _api()

        seen = api.player_view(campaign["chat_id"], "player", frame_id=None)
        assert seen["frame"] is None

        with pytest.raises(ExtensionError, match="no frame"):
            api.player_view(campaign["chat_id"], "player", frame_id=987654)
        with pytest.raises(ExtensionError, match="no frame"):
            api.story_view(campaign["chat_id"], frame_id=987654)

    def test_the_view_is_immutable(self, campaign):
        bound = _api().at_frame(campaign["chat_id"])

        with pytest.raises(ExtensionError, match="immutable"):
            bound.frame_id = None


# ---------------------------------------------------------------- binding


class TestBoundReadsArePinned:
    def test_a_bound_read_survives_an_ambient_frame_change(self, campaign):
        """The reviewer's fifth requirement: `.get()` called AFTER something
        else moved `active_frame_id` still answers for the captured frame --
        and does so by resolving the frame into the query, never by leaving
        the contextvar set across extension code."""
        from core.db import active_frame_id

        bound = _api().at_frame(campaign["chat_id"],
                                campaign["future"]["id"])
        mission = bound.frame_state()
        duty = bound.char_state(campaign["char_id"])

        token = active_frame_id.set(None)   # somebody else's present
        try:
            assert mission.get()["mission"]["revision"] == 77
            assert duty.get()["duty"] == "future"
            assert active_frame_id.get() is None, \
                "a bound read must not leave the ambient frame changed"
        finally:
            active_frame_id.reset(token)

    def test_the_unbound_accessors_keep_their_ambient_behaviour(
            self, campaign):
        """Byte-identical compatibility: `api.frame_state` and
        `api.char_state` still follow whatever frame is active at call time,
        which is what state read inside a pipeline run wants."""
        from core.db import active_frame_id

        api = _api()
        ambient_mission = api.frame_state(campaign["chat_id"])
        ambient_duty = api.char_state(campaign["chat_id"],
                                      campaign["char_id"])

        assert ambient_mission.get()["mission"]["revision"] == 1
        assert ambient_duty.get()["duty"] == "present"
        token = active_frame_id.set(campaign["future"]["id"])
        try:
            assert ambient_mission.get()["mission"]["revision"] == 77
            assert ambient_duty.get()["duty"] == "future"
        finally:
            active_frame_id.reset(token)


class TestBoundWrites:
    def test_a_bound_write_lands_only_in_the_selected_frame(self, campaign):
        from core.db import wget, wget_for_frame

        bound = _api().at_frame(campaign["chat_id"],
                                campaign["future"]["id"])
        bound.frame_state().set_now({"mission": {"revision": 78}})

        assert wget_for_frame(campaign["chat_id"], "extf:coherence",
                              campaign["future"]["id"]) \
            == {"mission": {"revision": 78}}
        assert wget(campaign["chat_id"], "extf:coherence") \
            == {"mission": {"revision": 1}}, "the present must not move"

    def test_a_present_bound_write_reaches_the_base_rows(self, campaign):
        from core.db import wget_for_frame

        bound = _api().at_frame(campaign["chat_id"], None)
        bound.frame_state().set_now({"mission": {"revision": 2}})
        bound.char_state(campaign["char_id"]).set_now({"duty": "revised"})

        assert wget_for_frame(campaign["chat_id"], "extf:coherence", None) \
            == {"mission": {"revision": 2}}
        assert _api().at_frame(campaign["chat_id"],
                               campaign["future"]["id"]) \
            .char_state(campaign["char_id"]).get()["duty"] == "future", \
            "the future overlay must not move"

    def test_a_bound_char_write_lands_in_the_overlay_not_the_base_row(
            self, temp_db, campaign):
        bound = _api().at_frame(campaign["chat_id"],
                                campaign["future"]["id"])
        bound.char_state(campaign["char_id"]).set_now({"duty": "promoted"})

        base = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (campaign["chat_id"], campaign["char_id"]), one=True)["state"])
        overlay = json.loads(temp_db.q(
            "SELECT state FROM chat_char_frames "
            "WHERE chat_id=? AND char_id=? AND frame_id=?",
            (campaign["chat_id"], campaign["char_id"],
             campaign["future"]["id"]), one=True)["state"])

        assert base["ext:coherence"] == {"duty": "present"}
        assert overlay["ext:coherence"] == {"duty": "promoted"}

    def test_the_commit_gate_is_unchanged_by_the_binding(self, campaign):
        """The binding decides WHERE a write lands; the gate still decides
        WHEN it may. A bound facade is not a new bypass."""
        bound = _api().at_frame(campaign["chat_id"],
                                campaign["future"]["id"])

        with pytest.raises(ExtensionError, match="on_turn_committed"):
            bound.frame_state().set({"mission": {"revision": 99}})
        with pytest.raises(ExtensionError, match="on_turn_committed"):
            bound.char_state(campaign["char_id"]).set({"duty": "never"})
