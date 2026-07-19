"""Regression tests for paradox.py: fixed-point detection, escalation,
resolution, and the pluggable consequence modes (dread/hazard/toll/
warden/bureau) built on top of frames.py. Ordinary changes to the past
that touch no declared fixed point must never trigger any of this --
that's the default, safe, non-paradox path (see test_frames.py)."""

from __future__ import annotations

import contextlib
import time

import pytest

import db as db_module
import paradox
from db import q, qi, wget, wset
from pipeline_context import ChatData, PipelineContext, TurnData


@contextlib.contextmanager
def _in_frame(frame_id):
    """Simulates a pipeline run executing in `frame_id`, exactly like
    agents/runtime.py._run_pipeline sets active_frame_id from the turn
    row -- needed here because these tests call paradox.py functions
    directly, bypassing the real pipeline."""
    token = db_module.active_frame_id.set(frame_id)
    try:
        yield
    finally:
        db_module.active_frame_id.reset(token)


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


_ctx_idx_counter = [0]


def _make_ctx(chat_id, frame_id=None):
    _ctx_idx_counter[0] += 1
    idx = _ctx_idx_counter[0]
    turn_id = qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
        (chat_id, idx, "test", time.time(), frame_id),
    )
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx, player_input="test",
                      created=time.time(), frame_id=frame_id),
        cast=[], input="test",
    )


def _make_entity(chat_id, entity_id, kind="person"):
    qi(
        "INSERT INTO world_entities(entity_id,chat_id,kind,payload) VALUES(?,?,?,?)",
        (entity_id, chat_id, kind, "{}"),
    )


class TestPolicy:
    def test_default_policy_is_hazard(self, temp_db):
        chat_id = _make_chat(temp_db)
        assert paradox.get_policy(chat_id)["mode"] == "hazard"

    def test_set_policy_rejects_unknown_mode(self, temp_db):
        chat_id = _make_chat(temp_db)
        with pytest.raises(ValueError):
            paradox.set_policy(chat_id, mode="cataclysm")

    def test_set_policy_persists(self, temp_db):
        chat_id = _make_chat(temp_db)
        paradox.set_policy(chat_id, mode="dread")
        assert paradox.get_policy(chat_id)["mode"] == "dread"


class TestFixedPoints:
    def test_add_and_list_fixed_point(self, temp_db):
        chat_id = _make_chat(temp_db)
        anchor_id = paradox.add_fixed_point(
            chat_id, entity_id="pete", frame_id=None,
            required_exists=False, label="Pete must die in the crash",
        )
        points = paradox.fixed_points(chat_id)
        assert len(points) == 1
        assert points[0]["anchor_id"] == anchor_id
        assert points[0]["required_exists"] is False

    def test_remove_fixed_point(self, temp_db):
        chat_id = _make_chat(temp_db)
        anchor_id = paradox.add_fixed_point(
            chat_id, entity_id="pete", frame_id=None, required_exists=False, label="x",
        )
        paradox.remove_fixed_point(chat_id, anchor_id)
        assert paradox.fixed_points(chat_id) == []

    def test_add_fixed_point_rejects_unknown_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        with pytest.raises(ValueError):
            paradox.add_fixed_point(
                chat_id, entity_id="pete", frame_id=999999,
                required_exists=False, label="x",
            )

    def test_add_fixed_point_rejects_unknown_mode(self, temp_db):
        chat_id = _make_chat(temp_db)
        with pytest.raises(ValueError):
            paradox.add_fixed_point(
                chat_id, entity_id="pete", frame_id=None,
                required_exists=False, label="x", mode="cataclysm",
            )


class TestOrdinaryChangesAreSafe:
    """The overwhelming default path: a chat with no fixed points, or a
    change that doesn't touch one, must never trigger anything."""

    def test_no_fixed_points_never_triggers(self, temp_db):
        chat_id = _make_chat(temp_db)
        _make_entity(chat_id, "some_npc")
        ctx = _make_ctx(chat_id)
        result = paradox.check_and_apply_paradox(ctx, 0)
        assert result == {"active": False}
        assert paradox.get_paradox(chat_id, None) is None

    def test_unrelated_entity_change_does_not_violate_an_anchor(self, temp_db):
        chat_id = _make_chat(temp_db)
        paradox.add_fixed_point(
            chat_id, entity_id="pete", frame_id=None, required_exists=False, label="x",
        )
        _make_entity(chat_id, "some_other_npc")
        ctx = _make_ctx(chat_id)
        result = paradox.check_and_apply_paradox(ctx, 0)
        assert result == {"active": False}


class TestTriggering:
    def test_violated_anchor_triggers_a_paradox(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                  "positions": {"pete": "road"}, "entities": {}})
        paradox.add_fixed_point(
            chat_id, entity_id="pete", frame_id=None,
            required_exists=False, label="Pete must die in the crash",
        )
        _make_entity(chat_id, "pete")  # Rose saved him -- he now exists when he shouldn't.

        ctx = _make_ctx(chat_id)
        result = paradox.check_and_apply_paradox(ctx, 0)

        assert result["label"] == "Pete must die in the crash"
        assert result["severity"] == 0.0
        state = paradox.get_paradox(chat_id, None)
        assert state is not None
        assert state["epicenter_room"] == "road"

    def test_second_commit_while_active_advances_not_retriggers(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                  "positions": {"pete": "road"}, "entities": {}})
        wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
        paradox.add_fixed_point(
            chat_id, entity_id="pete", frame_id=None, required_exists=False, label="x",
        )
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id)
        paradox.check_and_apply_paradox(ctx, 0)

        wset(chat_id, "simulation_clock", {"elapsed_seconds": 100.0})
        result = paradox.check_and_apply_paradox(ctx, 0)
        assert result["started_clock_seconds"] == 0.0  # same episode, not re-triggered
        assert result["severity"] > 0.0


class TestEscalation:
    def _setup_active_paradox(self, temp_db, mode="hazard"):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {
            "rooms": {
                "road": {"name": "Road", "adjacent": [{"to": "church"}]},
                "church": {"name": "Church", "adjacent": [{"to": "road"}]},
            },
            "positions": {"pete": "road"}, "entities": {},
        })
        wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
        paradox.set_policy(chat_id, mode=mode)
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id)
        paradox.check_and_apply_paradox(ctx, 0)
        return chat_id, ctx

    def test_severity_climbs_with_diegetic_time_not_wall_clock(self, temp_db):
        chat_id, ctx = self._setup_active_paradox(temp_db)
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS / 2})
        result = paradox.check_and_apply_paradox(ctx, 0)
        assert 0.3 < result["severity"] < 0.7

    def test_hazard_mode_consumes_the_epicenter_room_at_stage_2(self, temp_db):
        chat_id, ctx = self._setup_active_paradox(temp_db, mode="hazard")
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.5})
        paradox.check_and_apply_paradox(ctx, 0)
        sc = wget(chat_id, "scene")
        assert sc["rooms"]["road"].get("paradox_consumed") is True

    def test_hazard_mode_spreads_outward_at_stage_3(self, temp_db):
        chat_id, ctx = self._setup_active_paradox(temp_db, mode="hazard")
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.75})
        paradox.check_and_apply_paradox(ctx, 0)
        sc = wget(chat_id, "scene")
        assert sc["rooms"]["road"].get("paradox_consumed") is True
        assert sc["rooms"]["church"].get("paradox_consumed") is True

    def test_hazard_mode_room_consumption_is_narratively_visible(self, temp_db):
        """A consumed room's `notes` field must carry something a
        perceiver would actually notice -- perception_act/perception_
        outcome already read room.notes verbatim into room_notes, so this
        is the cheap way to make the paradox_consumed flag (previously
        write-only: nothing in perception.py/narration.py/director.py
        ever read it) actually reach the player, without a new payload
        field anywhere."""
        chat_id, ctx = self._setup_active_paradox(temp_db, mode="hazard")
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.5})
        paradox.check_and_apply_paradox(ctx, 0)
        sc = wget(chat_id, "scene")
        assert paradox._HAZARD_WOUND_NOTE in sc["rooms"]["road"]["notes"]

    def test_warden_mode_spawns_a_hunting_entity(self, temp_db):
        chat_id, ctx = self._setup_active_paradox(temp_db, mode="warden")
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.3})
        paradox.check_and_apply_paradox(ctx, 0)
        sc = wget(chat_id, "scene")
        warden_name = paradox.get_paradox(chat_id, None)["warden_entity_name"]
        assert sc["positions"][warden_name] == "road"
        assert sc["entities"][warden_name]["hostile"] is True

    def test_dread_mode_never_touches_the_scene(self, temp_db):
        chat_id, ctx = self._setup_active_paradox(temp_db, mode="dread")
        before = wget(chat_id, "scene")
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS})
        paradox.check_and_apply_paradox(ctx, 0)
        after = wget(chat_id, "scene")
        assert before == after

    def test_toll_mode_decays_a_traveler_memory_confidence_in_radius(self, temp_db):
        import memory
        from character_schema import default_character_data
        import json as _json

        chat_id = _make_chat(temp_db)
        hinami = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Hinami", _json.dumps(default_character_data("Hinami")), "{}", time.time()),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, hinami, "active", "{}"),
        )
        from frames import create_frame
        past_frame = create_frame(chat_id, label="Past", ordinal=-1, kind="past", travelers=[hinami])

        paradox.set_policy(chat_id, mode="toll")
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past_frame,
                                 required_exists=False, label="x")
        memory.add_memory(chat_id, hinami, None, "episode", "witnessed", 0.5, "A memory.", turn_idx=1)
        before = memory.dump_character_memories(chat_id, hinami)[0]["confidence"]

        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id, frame_id=past_frame)
        with _in_frame(past_frame):
            wset(chat_id, "scene", {
                "rooms": {"road": {"name": "Road", "adjacent": []}},
                "positions": {"pete": "road", "Hinami": "road"}, "entities": {},
            })
            wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
            paradox.check_and_apply_paradox(ctx, 0)
            wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.5})
            paradox.check_and_apply_paradox(ctx, 0)

        after = memory.dump_character_memories(chat_id, hinami)[0]["confidence"]
        assert after < before

    def test_toll_mode_spares_memories_formed_in_the_wound_frame_itself(self, temp_db):
        """Fable's audit (B9): toll's docstring says it decays a
        traveler's memories "from their origin frame", but the query had
        no frame filter at all -- it hit EVERY memory the character had,
        including ones formed while standing in the wound room right now
        (which should still be freshly perceived, not fading). Only
        memories from OTHER frames -- the timeline being destabilized --
        should decay."""
        import memory
        from character_schema import default_character_data
        import json as _json

        chat_id = _make_chat(temp_db)
        hinami = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Hinami", _json.dumps(default_character_data("Hinami")), "{}", time.time()),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, hinami, "active", "{}"),
        )
        from frames import create_frame
        past_frame = create_frame(chat_id, label="Past", ordinal=-1, kind="past", travelers=[hinami])

        paradox.set_policy(chat_id, mode="toll")
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past_frame,
                                 required_exists=False, label="x")
        memory.add_memory(chat_id, hinami, None, "episode", "witnessed", 0.5,
                          "From back home.", turn_idx=1, frame_id=None)
        memory.add_memory(chat_id, hinami, None, "episode", "witnessed", 0.5,
                          "Right here in the wound room, just now.", turn_idx=2,
                          frame_id=past_frame)

        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id, frame_id=past_frame)
        with _in_frame(past_frame):
            wset(chat_id, "scene", {
                "rooms": {"road": {"name": "Road", "adjacent": []}},
                "positions": {"pete": "road", "Hinami": "road"}, "entities": {},
            })
            wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
            paradox.check_and_apply_paradox(ctx, 0)
            wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.5})
            paradox.check_and_apply_paradox(ctx, 0)

        rows = {
            m["content"]: m["confidence"]
            for m in memory.dump_character_memories(chat_id, hinami)
        }
        assert rows["From back home."] < 1.0
        assert rows["Right here in the wound room, just now."] == 1.0


class TestFrameScopedVisibilityAndLockouts:
    """A paradox unfolding in one frame must not leak into, or block
    jumps for, a chat currently occupied with an unrelated frame -- see
    the live conversation that surfaced this: a player in the future
    should experience their own frame normally while a paradox plays out
    back in the past."""

    def test_paradox_visible_only_in_its_own_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        from frames import create_frame

        past = create_frame(chat_id, label="Past", ordinal=-1, kind="past")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        _make_entity(chat_id, "pete")
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past,
                                 required_exists=False, label="x")
        ctx = _make_ctx(chat_id, frame_id=past)
        with _in_frame(past):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"pete": "road"}, "entities": {}})
            paradox.check_and_apply_paradox(ctx, 0)

        assert paradox.paradox_visible_to(chat_id, past) is not None
        assert paradox.paradox_visible_to(chat_id, future) is None
        assert paradox.paradox_visible_to(chat_id, None) is None

    def test_director_payload_omits_paradox_for_an_unrelated_frame(self, temp_db, monkeypatch):
        import agents.director as director_module
        from frames import create_frame

        chat_id = _make_chat(temp_db)
        past = create_frame(chat_id, label="Past", ordinal=-1, kind="past")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id, frame_id=past)
        with _in_frame(past):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"pete": "road"}, "entities": {}})
            paradox.check_and_apply_paradox(ctx, 0)

        with _in_frame(future):
            wset(chat_id, "scene", {
                "location": "Alien planet", "time": "day",
                "rooms": {"clearing": {"name": "Clearing", "adjacent": []}},
                "positions": {}, "entities": {}, "attire": {}, "overlays": {},
            })

            turn_id = temp_db.qi(
                "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                (chat_id, 5, "hello", time.time(), future),
            )
            future_ctx = PipelineContext(
                chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                              scenario="", created=time.time()),
                turn=TurnData(id=turn_id, chat_id=chat_id, idx=5, player_input="hello",
                              created=time.time(), frame_id=future),
                cast=[], input="hello",
            )

            captured = {}

            def fake_agent_json(role, step_key, system, payload, **kwargs):
                captured["payload"] = payload
                return {"flow": {}, "sequence": []}

            monkeypatch.setattr(director_module, "_agent_json", fake_agent_json)
            director_module.director_interpret(future_ctx, 0)

        assert captured["payload"]["paradox"] is None

    def test_restationing_between_unrelated_frames_is_unaffected_by_a_paradox_elsewhere(self, temp_db):
        import app
        from frames import create_frame

        chat_id = _make_chat(temp_db)
        past = create_frame(chat_id, label="Past", ordinal=-1, kind="past")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        other = create_frame(chat_id, label="Also future", ordinal=20, kind="future")
        pid = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Bob", "{}"))
        app.chat_add_persona(chat_id, {"persona_id": pid})
        app.chat_persona_station(chat_id, pid, {"frame_id": future})

        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id, frame_id=past)
        with _in_frame(past):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"pete": "road"}, "entities": {}})
            paradox.check_and_apply_paradox(ctx, 0)

        result = app.chat_persona_station(chat_id, pid, {"frame_id": other})
        assert result["frame_id"] == other

    def test_restationing_into_the_paradoxs_own_frame_is_blocked(self, temp_db):
        import app
        from frames import create_frame

        chat_id = _make_chat(temp_db)
        past = create_frame(chat_id, label="Past", ordinal=-1, kind="past")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")
        pid = temp_db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)", ("Bob", "{}"))
        app.chat_add_persona(chat_id, {"persona_id": pid})
        app.chat_persona_station(chat_id, pid, {"frame_id": future})

        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id, frame_id=past)
        with _in_frame(past):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"pete": "road"}, "entities": {}})
            paradox.check_and_apply_paradox(ctx, 0)

        with pytest.raises(Exception) as exc_info:
            app.chat_persona_station(chat_id, pid, {"frame_id": past})
        assert exc_info.value.status_code == 409

    def test_branching_an_unrelated_frames_turn_is_unaffected(self, temp_db):
        import app
        from frames import create_frame

        chat_id = _make_chat(temp_db)
        past = create_frame(chat_id, label="Past", ordinal=-1, kind="past")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id, frame_id=past)
        with _in_frame(past):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"pete": "road"}, "entities": {}})
            paradox.check_and_apply_paradox(ctx, 0)

        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 9, "hi", time.time(), future),
        )
        branched = app.turn_branch(turn_id)
        assert branched["id"] is not None


class TestTickOwnership:
    """Each frame has its OWN paradox slot (get_all_paradoxes), but
    escalating or resolving a given slot writes into "scene" and reads
    "simulation_clock" -- both frame-scoped through whichever frame is
    ACTUALLY active when check_and_apply_paradox runs. An unrelated
    frame's commit must never be allowed to tick a DIFFERENT frame's
    slot (that would write hazard-mode room consumption into the WRONG
    frame's scene, and pace escalation off the wrong frame's clock) --
    it may only ever detect and advance its OWN."""

    def test_an_unrelated_frames_commit_does_not_advance_the_other_frames_paradox(self, temp_db):
        chat_id = _make_chat(temp_db)
        from frames import create_frame

        past = create_frame(chat_id, label="Past", ordinal=-1, kind="past")
        future = create_frame(chat_id, label="Future", ordinal=10, kind="future")

        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        past_ctx = _make_ctx(chat_id, frame_id=past)
        with _in_frame(past):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"pete": "road"}, "entities": {}})
            wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
            paradox.check_and_apply_paradox(past_ctx, 0)

        before = paradox.get_paradox(chat_id, past)
        assert before["severity"] == 0.0

        # A commit in the FUTURE frame, well past the escalation window
        # if it were (wrongly) using the past frame's clock and scene.
        # The SAME anchor is violated chat-wide, so the future frame's
        # own commit legitimately triggers its OWN independent paradox
        # here (world_entities has no per-frame partitioning) -- that is
        # the correct, NEW behavior this test now covers: past's slot
        # must stay completely untouched by it.
        future_ctx = _make_ctx(chat_id, frame_id=future)
        with _in_frame(future):
            wset(chat_id, "scene", {"rooms": {"clearing": {"name": "Clearing", "adjacent": []}}})
            wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 5})
            result = paradox.check_and_apply_paradox(future_ctx, 0)

        # A brand new trigger always starts at severity 0 regardless of
        # the frame's absolute clock reading (severity is relative to
        # ITS OWN start time) -- so this assertion holds for a genuinely
        # different reason than before the fix.
        assert result["severity"] == 0.0
        assert result["frame_id"] == future

        # Past's own slot is completely untouched by the future's commit.
        after = paradox.get_paradox(chat_id, past)
        assert after == before

        # And the future frame now correctly has its OWN independent slot.
        future_paradox = paradox.get_paradox(chat_id, future)
        assert future_paradox is not None
        assert future_paradox["frame_id"] == future

    def test_a_paradox_active_in_one_frame_does_not_mask_detection_in_another(self, temp_db):
        """The actual bug Fable's audit found: a single chat-global
        paradox slot meant frame B's own anchor violation went
        completely undetected while frame A's paradox was live, because
        check_and_apply_paradox short-circuited on ANY active record
        regardless of which frame it belonged to."""
        chat_id = _make_chat(temp_db)
        from frames import create_frame

        frame_a = create_frame(chat_id, label="A", ordinal=-1, kind="past")
        frame_b = create_frame(chat_id, label="B", ordinal=10, kind="future")

        paradox.add_fixed_point(chat_id, entity_id="alpha", frame_id=frame_a,
                                 required_exists=False, label="alpha must not exist")
        paradox.add_fixed_point(chat_id, entity_id="beta", frame_id=frame_b,
                                 required_exists=False, label="beta must not exist")
        _make_entity(chat_id, "alpha")

        ctx_a = _make_ctx(chat_id, frame_id=frame_a)
        with _in_frame(frame_a):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"alpha": "road"}, "entities": {}})
            wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
            paradox.check_and_apply_paradox(ctx_a, 0)

        assert paradox.get_paradox(chat_id, frame_a) is not None
        # Before the fix: frame B's own beta-violation check never even
        # ran, because check_and_apply_paradox returned frame A's
        # unrelated active record as soon as it saw ANY active paradox.
        assert paradox.get_paradox(chat_id, frame_b) is None

        # Resolve alpha's anchor first so it's not still first-in-line
        # when frame B scans fixed_points (anchors aren't per-frame
        # scoped at the detection level -- see check_and_apply_paradox's
        # docstring -- this isolates beta's violation as the only one
        # left for frame B to notice).
        qi("DELETE FROM world_entities WHERE chat_id=? AND entity_id=?", (chat_id, "alpha"))
        _make_entity(chat_id, "beta")  # now frame B's own anchor is violated too
        ctx_b = _make_ctx(chat_id, frame_id=frame_b)
        with _in_frame(frame_b):
            wset(chat_id, "scene", {"rooms": {"clearing": {"name": "Clearing", "adjacent": []}}})
            wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
            result_b = paradox.check_and_apply_paradox(ctx_b, 0)

        assert result_b.get("label") == "beta must not exist"
        beta_paradox = paradox.get_paradox(chat_id, frame_b)
        assert beta_paradox is not None
        assert beta_paradox["frame_id"] == frame_b
        # Frame A's own paradox is completely unaffected by frame B's.
        alpha_paradox = paradox.get_paradox(chat_id, frame_a)
        assert alpha_paradox is not None
        assert alpha_paradox["frame_id"] == frame_a

    def test_the_owning_frames_commit_can_still_advance_it(self, temp_db):
        chat_id = _make_chat(temp_db)
        from frames import create_frame

        past = create_frame(chat_id, label="Past", ordinal=-1, kind="past")
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=past,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id, frame_id=past)
        with _in_frame(past):
            wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                      "positions": {"pete": "road"}, "entities": {}})
            wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
            paradox.check_and_apply_paradox(ctx, 0)
            wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.5})
            result = paradox.check_and_apply_paradox(ctx, 0)

        assert result["severity"] > 0.0


class TestResolution:
    def test_restoring_the_anchor_resolves_the_paradox(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                  "positions": {"pete": "road"}, "entities": {}})
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id)
        paradox.check_and_apply_paradox(ctx, 0)
        assert paradox.get_paradox(chat_id, None) is not None

        qi("DELETE FROM world_entities WHERE chat_id=? AND entity_id=?", (chat_id, "pete"))
        result = paradox.check_and_apply_paradox(ctx, 0)

        assert result["resolved"] is True
        assert paradox.get_paradox(chat_id, None) is None

    def test_resolution_restores_consumed_rooms(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                  "positions": {"pete": "road"}, "entities": {}})
        wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id)
        paradox.check_and_apply_paradox(ctx, 0)
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.6})
        paradox.check_and_apply_paradox(ctx, 0)
        assert wget(chat_id, "scene")["rooms"]["road"].get("paradox_consumed") is True

        qi("DELETE FROM world_entities WHERE chat_id=? AND entity_id=?", (chat_id, "pete"))
        paradox.check_and_apply_paradox(ctx, 0)

        assert "paradox_consumed" not in wget(chat_id, "scene")["rooms"]["road"]

    def test_resolution_strips_the_hazard_wound_note_and_nothing_else(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {
            "rooms": {"road": {"name": "Road", "adjacent": [],
                                "notes": "A quiet country road."}},
            "positions": {"pete": "road"}, "entities": {},
        })
        wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id)
        paradox.check_and_apply_paradox(ctx, 0)
        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 0.6})
        paradox.check_and_apply_paradox(ctx, 0)
        assert paradox._HAZARD_WOUND_NOTE in wget(chat_id, "scene")["rooms"]["road"]["notes"]

        qi("DELETE FROM world_entities WHERE chat_id=? AND entity_id=?", (chat_id, "pete"))
        paradox.check_and_apply_paradox(ctx, 0)

        assert wget(chat_id, "scene")["rooms"]["road"]["notes"] == "A quiet country road."

    def test_reaching_the_ceiling_forces_restoration(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", {"rooms": {"road": {"name": "Road", "adjacent": []}},
                                  "positions": {"pete": "road"}, "entities": {}})
        wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                 required_exists=False, label="x")
        _make_entity(chat_id, "pete")
        ctx = _make_ctx(chat_id)
        paradox.check_and_apply_paradox(ctx, 0)

        wset(chat_id, "simulation_clock", {"elapsed_seconds": paradox.ESCALATION_SECONDS * 10})
        result = paradox.check_and_apply_paradox(ctx, 0)

        assert result["resolved"] is True
        assert result["forced"] is True
        assert paradox.get_paradox(chat_id, None) is None
        # Reality won: Pete no longer exists, satisfying the anchor.
        assert not q("SELECT 1 FROM world_entities WHERE chat_id=? AND entity_id=?",
                     (chat_id, "pete"), one=True)
