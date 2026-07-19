"""Tests for spatial_frames.py: proximity-driven (zone-based, not
distance-based) automatic split/merge of a chat's cast into a spatial
sibling frame, and the corresponding incomparability rule in
frames.is_memory_visible plus the paradox exemption for spatial frames.

Design recap (see spatial_frames.py's module docstring): a room may
carry an explicit `zone` field; a split fires only when two human
parties are standing in rooms with two DIFFERENT non-empty zones. This
is deliberately NOT triggered by spatial.py's `distance:"far"` (that
just means "no adjacency edge happens to connect these rooms", true of
any unmapped hallway) -- only an explicitly authored zone difference.
"""

from __future__ import annotations

import json
import time

import pytest

import app
import memory
import paradox
import spatial_frames
from character_schema import default_character_data
from db import active_frame_id, wget, wget_for_frame, wset, wset_for_frame
from frames import create_frame, get_frame, is_memory_visible
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_persona(db, name):
    return db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        (name, json.dumps({"identity": {"name": name}})),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


def _split_scene():
    return {
        "rooms": {
            "bridge": {"name": "Bridge", "adjacent": [], "zone": "ship_alpha"},
            "shuttle": {"name": "Shuttle", "adjacent": [], "zone": "ship_beta"},
        },
        "positions": {"The Stranger": "bridge", "Bob": "shuttle"},
        "entities": {}, "attire": {}, "overlays": {},
    }


class TestZoneGroups:
    def test_groups_members_by_room_zone(self, temp_db):
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": bob})
        wset(chat_id, "scene", _split_scene())

        groups = spatial_frames.zone_groups(chat_id, None, _split_scene())
        assert groups == {"ship_alpha": ["The Stranger"], "ship_beta": ["Bob"]}

    def test_unzoned_rooms_are_excluded(self, temp_db):
        chat_id = _make_chat(temp_db)
        scene = {
            "rooms": {"hallway": {"name": "Hallway", "adjacent": []}},
            "positions": {"The Stranger": "hallway"},
            "entities": {}, "attire": {}, "overlays": {},
        }
        groups = spatial_frames.zone_groups(chat_id, None, scene)
        assert groups == {}


class TestDetectSplit:
    def test_fires_when_two_zones_are_occupied(self, temp_db):
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": bob})
        wset(chat_id, "scene", _split_scene())

        assert spatial_frames.detect_split(chat_id, None, turn_idx=5) == "ship_beta"

    def test_does_not_fire_with_only_one_zone(self, temp_db):
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": bob})
        scene = _split_scene()
        scene["positions"]["Bob"] = "bridge"
        wset(chat_id, "scene", scene)

        assert spatial_frames.detect_split(chat_id, None, turn_idx=5) is None

    def test_does_not_fire_without_any_extra_personas(self, temp_db):
        chat_id = _make_chat(temp_db)
        wset(chat_id, "scene", _split_scene())
        assert spatial_frames.detect_split(chat_id, None, turn_idx=5) is None

    def test_does_not_fire_on_unzoned_rooms_even_if_far(self, temp_db):
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": bob})
        scene = {
            "rooms": {
                "attic": {"name": "Attic", "adjacent": []},
                "basement": {"name": "Basement", "adjacent": []},
            },
            "positions": {"The Stranger": "attic", "Bob": "basement"},
            "entities": {}, "attire": {}, "overlays": {},
        }
        wset(chat_id, "scene", scene)
        assert spatial_frames.detect_split(chat_id, None, turn_idx=5) is None

    def test_does_not_fire_while_a_paradox_is_active_in_this_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": bob})
        wset(chat_id, "scene", _split_scene())
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                required_exists=True, label="x")
        # Directly seed an active paradox record for the present frame.
        wset(chat_id, "paradoxes", {"present": {
            "anchor_id": 1, "label": "x", "frame_id": None, "epicenter_room": "bridge",
            "started_clock_seconds": 0, "severity": 0.0, "stage": 0, "mode": "hazard",
            "consumed": {"rooms": [], "entities": []},
        }})
        assert spatial_frames.detect_split(chat_id, None, turn_idx=5) is None

    def test_does_not_fire_for_an_already_spatial_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        spatial = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                               split_turn_idx=1)
        bob = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": bob})
        wset_for_frame(chat_id, "scene", _split_scene(), spatial)
        assert spatial_frames.detect_split(chat_id, spatial, turn_idx=5) is None


class TestPerformSplit:
    def test_creates_a_spatial_frame_and_partitions_cast_and_personas(self, temp_db):
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": bob})

        nova = _make_char(temp_db, "Nova")  # stays behind
        astra = _make_char(temp_db, "Astra")  # goes with Bob
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,'active','{}')",
                   (chat_id, nova))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,'active','{}')",
                   (chat_id, astra))

        scene = _split_scene()
        scene["positions"]["Nova"] = "bridge"
        scene["positions"]["Astra"] = "shuttle"
        wset(chat_id, "scene", scene)
        wset(chat_id, "known", {"The Stranger": ["Nova", "Astra", "Bob"]})

        new_frame_id = spatial_frames.perform_split(chat_id, None, turn_idx=7, away_zone="ship_beta")

        frame = get_frame(new_frame_id)
        assert frame["kind"] == "spatial"
        assert frame["parent_frame_id"] is None
        assert frame["split_turn_idx"] == 7
        assert frame["ordinal"] == 0

        persona_row = temp_db.q(
            "SELECT frame_id FROM chat_personas WHERE chat_id=? AND persona_id=?",
            (chat_id, bob), one=True,
        )
        assert persona_row["frame_id"] == new_frame_id

        from scene import active_cast
        parent_cast_ids = {r["id"] for r in active_cast(chat_id, None)}
        child_cast_ids = {r["id"] for r in active_cast(chat_id, new_frame_id)}
        assert nova in parent_cast_ids and nova not in child_cast_ids
        assert astra in child_cast_ids and astra not in parent_cast_ids

        parent_scene = wget(chat_id, "scene")
        assert "Bob" not in parent_scene["positions"]
        assert "Nova" in parent_scene["positions"]
        child_scene = wget_for_frame(chat_id, "scene", new_frame_id)
        assert "Bob" in child_scene["positions"]

        child_known = wget_for_frame(chat_id, "known", new_frame_id)
        assert child_known == {"The Stranger": ["Nova", "Astra", "Bob"]}


class TestMemoryVisibilityIncomparability:
    def test_pre_split_history_is_visible_from_the_child(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=10)

        assert is_memory_visible(alice, None, child, memory_turn_idx=5) is True

    def test_post_split_parent_memories_are_invisible_to_the_child(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=10)

        assert is_memory_visible(alice, None, child, memory_turn_idx=15) is False

    def test_child_memories_are_invisible_to_the_parent(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=10)

        assert is_memory_visible(alice, child, None, memory_turn_idx=15) is False

    def test_a_traveler_of_the_child_still_sees_its_memories_from_the_parent(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=10, travelers=[alice])

        assert is_memory_visible(alice, child, None, memory_turn_idx=15) is True

    def test_after_merge_full_bidirectional_visibility_resumes(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=10)
        temp_db.qi("UPDATE frames SET merged_turn_idx=20 WHERE id=?", (child,))

        assert is_memory_visible(alice, child, None, memory_turn_idx=15) is True
        assert is_memory_visible(alice, None, child, memory_turn_idx=15) is True


class TestDetectAndPerformMerge:
    def test_merges_when_both_parties_report_the_same_zone(self, temp_db):
        chat_id = _make_chat(temp_db)
        bob = _make_persona(temp_db, "Bob")
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=5)
        temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) VALUES(?,?,'active',?)",
                   (chat_id, bob, child))

        rendezvous_room = {"name": "Docking Bay", "adjacent": [], "zone": "rendezvous"}
        wset(chat_id, "scene", {
            "rooms": {"docking_bay": rendezvous_room},
            "positions": {"The Stranger": "docking_bay"},
            "entities": {}, "attire": {}, "overlays": {},
        })
        wset_for_frame(chat_id, "scene", {
            "rooms": {"docking_bay": rendezvous_room},
            "positions": {"Bob": "docking_bay"},
            "entities": {}, "attire": {}, "overlays": {},
        }, child)
        wset_for_frame(chat_id, "simulation_clock", {"elapsed_seconds": 500.0}, child)
        wset(chat_id, "simulation_clock", {"elapsed_seconds": 300.0})
        wset_for_frame(chat_id, "known", {"Bob": ["A stowaway"]}, child)
        wset(chat_id, "known", {"The Stranger": ["Bob"]})

        merge = spatial_frames.detect_merge(chat_id, None)
        assert merge == (None, child)

        warnings = spatial_frames.perform_merge(chat_id, None, child, turn_idx=30)
        assert any("skew" in w.lower() for w in warnings)

        merged_frame = get_frame(child)
        assert merged_frame["merged_turn_idx"] == 30

        parent_clock = wget(chat_id, "simulation_clock")
        assert parent_clock["elapsed_seconds"] == 500.0  # max of the two

        parent_known = wget(chat_id, "known")
        assert "A stowaway" in parent_known["Bob"]
        assert parent_known["The Stranger"] == ["Bob"]

        persona_row = temp_db.q(
            "SELECT frame_id FROM chat_personas WHERE chat_id=? AND persona_id=?",
            (chat_id, bob), one=True,
        )
        assert persona_row["frame_id"] is None

    def test_does_not_merge_when_zones_still_differ(self, temp_db):
        chat_id = _make_chat(temp_db)
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=5)
        wset(chat_id, "scene", _split_scene())
        wset_for_frame(chat_id, "scene", {
            "rooms": {"shuttle": {"name": "Shuttle", "adjacent": [], "zone": "ship_beta"}},
            "positions": {"Bob": "shuttle"},
            "entities": {}, "attire": {}, "overlays": {},
        }, child)
        temp_db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) VALUES(?,?,'active',?)",
                   (chat_id, _make_persona(temp_db, "Bob"), child))

        assert spatial_frames.detect_merge(chat_id, None) is None


class TestParadoxIsExemptDuringSpatialSplit:
    def test_check_and_apply_paradox_skips_an_unmerged_spatial_frame(self, temp_db):
        chat_id = _make_chat(temp_db)
        child = create_frame(chat_id, label="Away", ordinal=0, kind="spatial",
                             parent_frame_id=None, split_turn_idx=5)
        wset_for_frame(chat_id, "scene", {
            "rooms": {"shuttle": {"name": "Shuttle", "adjacent": []}},
            "positions": {"pete": "shuttle"},
            "entities": {}, "attire": {}, "overlays": {},
        }, child)
        wset_for_frame(chat_id, "simulation_clock", {"elapsed_seconds": 0.0}, child)
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=child,
                                required_exists=False, label="pete must not exist")
        temp_db.qi(
            "INSERT INTO world_entities(entity_id,chat_id,kind,payload) VALUES(?,?,?,?)",
            ("pete", chat_id, "person", "{}"),
        )

        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "test", time.time(), child),
        )
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="test",
                          created=time.time(), frame_id=child),
            cast=[], input="test",
        )

        token = active_frame_id.set(child)
        try:
            result = paradox.check_and_apply_paradox(ctx, 0)
        finally:
            active_frame_id.reset(token)

        assert result == {"active": False, "skipped": "spatial"}
        assert paradox.get_paradox(chat_id, child) is None


class TestZoneFieldSurvivesSchemaValidation:
    """Fable's plan assumed rooms carry arbitrary extra keys through
    validate_llm_output untouched -- true for merge_scene_with_diff
    itself, but state_diff.rooms (director_resolve's output) is
    validated against the strict RoomDef Pydantic model first, whose
    default model_dump() silently drops any field it doesn't declare.
    Without zone being an actual RoomDef field, the model could author
    it all day and it would never survive to reach the scene blob."""

    def test_director_resolves_room_zone_is_not_stripped(self):
        from schemas import validate_llm_output

        raw = {
            "resolved_event": "x", "summary": "x",
            "state_diff": {
                "rooms": {
                    "shuttle": {"name": "Shuttle", "adjacent": [], "zone": "ship_beta"},
                },
            },
        }
        out, warnings = validate_llm_output("director_resolve", raw)
        assert out["state_diff"]["rooms"]["shuttle"]["zone"] == "ship_beta"


class TestInferVehicleZones:
    """Found live during the Doctor Who playtest (chat 10, Aran's Reach):
    the model reliably marks a ship kind="vehicle" with parent_entity
    interior rooms and moves its exterior position on every flight, but
    never spontaneously tagged room.zone even with maximally explicit
    narration ("nothing connecting it to the colony but empty vacuum").
    Worse, ROOM CREATION forces a same-turn adjacency edge back to the
    departure room, directly undermining any prompt-based zone
    criterion. infer_vehicle_zones detects the same event
    deterministically from data the model already reliably produces."""

    def _base_scene(self):
        return {
            "rooms": {
                "market_dome": {"name": "Market Dome", "adjacent": [
                    {"to": "bay_nine", "barrier": "open", "distance": "near"},
                ]},
                "bay_nine": {"name": "Bay Nine", "adjacent": [
                    {"to": "market_dome", "barrier": "open", "distance": "near"},
                ]},
                "long_odds_cockpit": {"name": "Cockpit", "adjacent": [], "parent_entity": "long_odds"},
            },
            "positions": {"The Stranger": "long_odds_cockpit", "long_odds": "bay_nine"},
            "entities": {"long_odds": {"kind": "vehicle", "name": "Long Odds"}},
            "attire": {}, "overlays": {},
        }

    def test_a_genuine_gap_crossing_stamps_two_distinct_zones(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = self._base_scene()

        # Simulate what actually happened live: the model moves the
        # vehicle and creates a new room with a forced adjacency edge
        # back to the departure room (ROOM CREATION's instruction).
        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["rooms"]["halyards_rest_approach"] = {
            "name": "Halyard's Rest — Approach",
            "adjacent": [{"to": "bay_nine", "barrier": "open", "distance": "near"}],
        }
        new_scene["positions"]["long_odds"] = "halyards_rest_approach"

        changed = spatial_frames.infer_vehicle_zones(chat_id, None, prev_scene, new_scene)
        assert changed is True

        zone_bay_nine = new_scene["rooms"]["bay_nine"]["zone"]
        zone_approach = new_scene["rooms"]["halyards_rest_approach"]["zone"]
        zone_dome = new_scene["rooms"]["market_dome"]["zone"]
        assert zone_bay_nine and zone_approach
        assert zone_bay_nine != zone_approach
        assert zone_dome == zone_bay_nine  # same pre-diff component as bay_nine

        # Vehicle interiors travel with the vehicle -- never zoned.
        assert "zone" not in new_scene["rooms"]["long_odds_cockpit"]

    def test_ordinary_movement_through_an_already_connected_room_does_not_trigger(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = self._base_scene()
        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["positions"]["long_odds"] = "market_dome"  # already reachable pre-diff

        changed = spatial_frames.infer_vehicle_zones(chat_id, None, prev_scene, new_scene)
        assert changed is False
        assert "zone" not in new_scene["rooms"]["market_dome"]
        assert "zone" not in new_scene["rooms"]["bay_nine"]

    def test_no_party_member_aboard_does_not_trigger(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        prev_scene = self._base_scene()
        prev_scene["positions"]["The Stranger"] = "market_dome"  # not aboard the vehicle

        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["rooms"]["somewhere_else"] = {"name": "Somewhere Else", "adjacent": []}
        new_scene["positions"]["long_odds"] = "somewhere_else"

        changed = spatial_frames.infer_vehicle_zones(chat_id, None, prev_scene, new_scene)
        assert changed is False

    def test_split_actually_fires_after_zone_inference(self, temp_db):
        """End-to-end: infer_vehicle_zones's output is exactly what
        detect_split needs -- no model cooperation required."""
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        bob = temp_db.qi(
            "INSERT INTO personas(name,sheet) VALUES(?,?)",
            ("Bob", json.dumps({"identity": {"name": "Bob"}})),
        )
        app.chat_add_persona(chat_id, {"persona_id": bob})

        prev_scene = self._base_scene()
        prev_scene["positions"]["The Stranger"] = "market_dome"
        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["rooms"]["halyards_rest_approach"] = {
            "name": "Halyard's Rest — Approach",
            "adjacent": [{"to": "bay_nine", "barrier": "open", "distance": "near"}],
        }
        new_scene["positions"]["long_odds"] = "halyards_rest_approach"
        new_scene["positions"]["Bob"] = "long_odds_cockpit"
        wset(chat_id, "scene", new_scene)

        spatial_frames.infer_vehicle_zones(chat_id, None, prev_scene, new_scene)
        wset(chat_id, "scene", new_scene)

        away_zone = spatial_frames.detect_split(chat_id, None, turn_idx=5)
        assert away_zone == new_scene["rooms"]["halyards_rest_approach"]["zone"]
