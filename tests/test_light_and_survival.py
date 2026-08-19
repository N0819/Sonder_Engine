"""Light, material-borne sound, enforced restraint, and bodily condition.

Four gaps found by auditing what the engine tracks against what it enforces.
The pattern behind all of them: state is real only where a CHOKE POINT reads
it. Awareness has four and is genuinely enforced; restraint had a detector and
no reader, so a character bound hand and foot could walk out of the room.

* LIGHT did not exist. Sight was decided entirely by barriers -- whether
  something stood between two rooms -- and never by whether there was anything
  to see BY. A pitch-black cellar and a sunlit hall were identical.
* SOUND was well modelled by hear_level, but `window` and `bars` were added in
  4.5 without cases there, so a shout through prison bars was inaudible. And
  every closed door in every setting attenuated identically, which makes a
  paper shoji screen sound like an oak door.
* RESTRAINT was detected and never read.
* BODILY CONDITION did not exist, and containers-as-places made that pointed:
  sealing someone in an opaque jar was survivable indefinitely.

Survival is off by default and off means ABSENT -- no table, no ticking, no
tokens. That is asserted here, because a story that never asked for a hunger
clock must not pay for one.
"""

from __future__ import annotations

import pytest

from world.spatial import (
    effective_light,
    has_visual,
    hear_level,
    merge_scene_with_diff,
    normalize_light,
    room_light,
    spatial_rel,
)


# --------------------------------------------------------------------- light

def _rooms(light_a="lit", light_b="lit", barrier="open"):
    return {
        "rooms": {
            "a": {"name": "A", "desc": "Room A.", "light": light_a,
                  "adjacent": [{"to": "b", "barrier": barrier,
                                "distance": "near"}]},
            "b": {"name": "B", "desc": "Room B.", "light": light_b,
                  "adjacent": []},
        },
        "positions": {"Watcher": "a", "Watched": "b"},
        "entities": {},
    }


class TestLight:
    @pytest.mark.parametrize("raw,expected", [
        (None, "lit"), ("", "lit"), ("nonsense", "lit"),
        ("dark", "dark"), ("pitch black", "dark"), ("unlit", "dark"),
        ("gloom", "dim"), ("candlelit", "dim"), ("twilight", "dim"),
        ("bright", "bright"), ("blinding", "bright"),
    ])
    def test_normalization(self, raw, expected):
        assert normalize_light(raw) == expected

    def test_absent_means_lit_so_old_scenes_are_unchanged(self):
        scene = {"rooms": {"a": {"name": "A"}}}
        assert room_light(scene, "a") == "lit"
        assert effective_light(scene, "a") == "lit"

    def test_you_cannot_see_into_a_dark_room(self):
        scene = _rooms(light_b="dark", barrier="open")
        assert has_visual(spatial_rel(scene, "a", "b")) is False

    def test_you_cannot_see_inside_your_own_dark_room(self):
        """The half that matters most: darkness hides the person beside you,
        not just the room next door."""
        scene = _rooms(light_a="dark")
        scene["rooms"]["a"]["adjacent"] = []
        assert has_visual(spatial_rel(scene, "a", "a")) is False

    def test_a_lit_room_is_seen_normally(self):
        scene = _rooms()
        assert has_visual(spatial_rel(scene, "a", "b")) is True

    def test_dim_is_still_sight(self):
        scene = _rooms(light_b="dim")
        assert has_visual(spatial_rel(scene, "a", "b")) is True

    def test_light_spills_through_an_open_door(self):
        """A cellar with the door open is not pitch black."""
        scene = _rooms(light_a="lit", light_b="dark", barrier="open")
        scene["rooms"]["b"]["adjacent"] = [
            {"to": "a", "barrier": "open", "distance": "near"}]
        assert effective_light(scene, "b") == "dim"

    def test_spill_never_makes_a_room_fully_lit(self):
        scene = _rooms(light_a="bright", light_b="dark")
        scene["rooms"]["b"]["adjacent"] = [
            {"to": "a", "barrier": "open", "distance": "near"}]
        assert effective_light(scene, "b") == "dim"      # not "lit"

    def test_no_spill_through_a_closed_door(self):
        scene = _rooms(light_a="lit", light_b="dark", barrier="closed_door")
        scene["rooms"]["b"]["adjacent"] = [
            {"to": "a", "barrier": "closed_door", "distance": "near"}]
        assert effective_light(scene, "b") == "dark"

    def test_spill_through_a_window(self):
        scene = _rooms(light_a="lit", light_b="dark", barrier="window")
        scene["rooms"]["b"]["adjacent"] = [
            {"to": "a", "barrier": "window", "distance": "near"}]
        assert effective_light(scene, "b") == "dim"

    def test_darkness_is_stated_as_ground_truth(self):
        from world.spatial import spatial_facts

        # Sealed: an open edge to a lit room would (correctly) spill enough
        # light to make this dim rather than pitch black.
        scene = _rooms(light_a="dark", barrier="closed_door")
        facts = spatial_facts(scene, "Watcher", [])
        assert any("pitch dark" in f for f in facts)

    def test_a_dim_room_is_stated_differently(self):
        from world.spatial import spatial_facts

        scene = _rooms(light_a="dim", barrier="closed_door")
        assert any("dim" in f for f in spatial_facts(scene, "Watcher", []))

    def test_light_survives_schema_validation(self):
        from llm.schemas import StateDiff

        diff = StateDiff(rooms={"cellar": {"name": "Cellar", "light": "dark"}})
        assert diff.dict()["rooms"]["cellar"]["light"] == "dark"


class TestLightInBackdrops:
    def test_the_prompt_says_how_to_paint_it(self):
        from dressing.backdrops import compose_prompt, room_projection

        scene = {"rooms": {"c": {"name": "Cellar", "desc": "Stone.",
                                 "light": "dark"}}}
        prompt = compose_prompt(room_projection(scene, "c"))
        assert "darkness" in prompt

    def test_a_normally_lit_room_says_nothing_extra(self):
        from dressing.backdrops import compose_prompt, room_projection

        scene = {"rooms": {"c": {"name": "Hall", "desc": "Wood.",
                                 "light": "lit"}}}
        assert "darkness" not in compose_prompt(room_projection(scene, "c"))

    def test_the_cache_key_changes_when_the_lights_go_out(self):
        """Without this a room that goes dark keeps serving its lit picture."""
        from dressing.backdrops import visual_signature

        lit = {"rooms": {"c": {"name": "Cellar", "desc": "Stone.", "light": "lit"}}}
        dark = {"rooms": {"c": {"name": "Cellar", "desc": "Stone.", "light": "dark"}}}
        assert visual_signature(lit, "c") != visual_signature(dark, "c")


# --------------------------------------------------------------------- sound

class TestSoundThroughMaterial:
    def _rel(self, barrier, material=""):
        return {"same_room": False, "barrier": barrier,
                "material": material, "distance": "near"}

    def test_bars_carry_a_voice(self):
        """A grate is an acoustic hole -- the difference between a cage and a
        cell. These fell through to 'none' when the barrier was added."""
        assert hear_level(self._rel("bars"), "normal") == "full"
        assert hear_level(self._rel("bars"), "shout") == "full"

    def test_glass_does_not(self):
        """Seen and not heard: the point of a sealed pane."""
        assert hear_level(self._rel("window"), "normal") == "none"
        assert hear_level(self._rel("window"), "shout") == "fragment"

    def test_a_paper_screen_is_easy_to_overhear_through(self):
        """A shoji and an oak door are both closed_door and stop a body
        identically. They are nothing alike to listen through."""
        oak = hear_level(self._rel("closed_door", "wood"), "normal")
        paper = hear_level(self._rel("closed_door", "paper"), "normal")

        assert oak == "fragment"
        assert paper == "full"

    def test_a_stone_wall_muffles_further_than_a_wooden_one(self):
        assert hear_level(self._rel("closed_door", "stone"), "normal") == "none"
        assert hear_level(self._rel("closed_door", "wood"), "normal") == "fragment"

    def test_soundproofing_is_the_most_attenuating_material(self):
        """A shout still carries as a fragment -- an engine-wide invariant that
        predates materials (a wall does the same). Soundproofing takes an
        ordinary voice from a fragment to nothing, which is the real effect."""
        assert hear_level(self._rel("closed_door", "soundproof"), "normal") == "none"
        assert hear_level(self._rel("closed_door", "soundproof"), "shout") == "fragment"

    def test_material_does_not_touch_sight_or_passage(self):
        """Only the acoustic question shifts. A paper screen you cannot see
        through is still one you cannot see through."""
        scene = _rooms(barrier="closed_door")
        scene["rooms"]["a"]["adjacent"][0]["material"] = "paper"
        rel = spatial_rel(scene, "a", "b")

        assert rel["barrier"] == "closed_door"
        assert has_visual(rel) is False
        assert hear_level(rel, "normal") == "full"

    def test_an_unknown_material_behaves_as_before(self):
        assert hear_level(self._rel("closed_door", "unobtainium"), "normal") \
            == hear_level(self._rel("closed_door"), "normal")


# ----------------------------------------------------------------- restraint

class TestRestraint:
    def test_the_readers_exist_and_fail_open(self, temp_db):
        from story.scene import restraint_map, restraint_of

        assert restraint_map(1) == {}
        assert restraint_of({}, "Anyone") is None

    def test_a_binding_this_beat_is_in_force_this_beat(self):
        from story.scene import apply_restraint_records_diff, restraint_of

        diff = {"conditions": {"c1": [{
            "condition_id": "c1", "subject_id": "Hinami", "kind": "restraint",
            "state": {"level": "bound", "by": "Tamamo", "means": "rope"}}]}}
        records = apply_restraint_records_diff([], diff)

        assert restraint_of(records, "Hinami")["level"] == "bound"
        assert restraint_of(records, "Hinami")["by"] == "Tamamo"

    def test_releasing_frees_them(self):
        from story.scene import apply_restraint_records_diff, restraint_of

        held = apply_restraint_records_diff([], {"conditions": {"c1": [{
            "subject_id": "Hinami", "kind": "restraint",
            "state": {"level": "bound"}}]}})
        freed = apply_restraint_records_diff(held, {"conditions": {"c1": [{
            "subject_id": "Hinami", "kind": "restraint", "active": 0,
            "state": {"level": "bound"}}]}})

        assert restraint_of(freed, "Hinami") is None

    def test_an_unknown_level_degrades_to_the_mildest(self):
        from story.scene import apply_restraint_records_diff, restraint_of

        records = apply_restraint_records_diff([], {"conditions": {"c1": [{
            "subject_id": "X", "kind": "restraint",
            "state": {"level": "hogtied_with_ribbon"}}]}})
        assert restraint_of(records, "X")["level"] == "held"

    def test_an_awareness_condition_is_not_a_restraint(self):
        from story.scene import apply_restraint_records_diff

        records = apply_restraint_records_diff([], {"conditions": {"c1": [{
            "subject_id": "X", "kind": "awareness",
            "state": {"level": "asleep"}}]}})
        assert records == []


# ------------------------------------------------------------------ survival

class TestSurvivalIsOffByDefault:
    def test_the_setting_defaults_off(self, temp_db):
        import time

        from world.survival import survival_enabled

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Fresh", "", time.time()))
        assert survival_enabled(cid) is False

    def test_off_means_absent_not_zeroed(self):
        """The whole bargain: a story that never asked for a hunger clock must
        not carry one in its state or its prompts."""
        scene = merge_scene_with_diff(
            {"rooms": {"a": {"name": "A"}}, "positions": {"P": "a"},
             "entities": {}}, {"time": {"duration_seconds": 86400}})
        assert "vitals" not in scene

    def test_nothing_ticks_without_a_table(self):
        from world.survival import tick_vitals

        scene = {"rooms": {}, "positions": {}}
        assert tick_vitals(scene, 86400) is scene
        assert "vitals" not in scene

    def test_no_facts_without_a_table(self):
        from world.survival import vitals_facts
        assert vitals_facts({"positions": {}}, "P") == []

    def test_the_toggle_round_trips(self, temp_db):
        import time

        from world.survival import set_survival_enabled, survival_enabled

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Story", "", time.time()))
        set_survival_enabled(cid, True)
        assert survival_enabled(cid) is True
        set_survival_enabled(cid, False)
        assert survival_enabled(cid) is False


class TestVitals:
    def _scene(self, **over):
        scene = {
            "rooms": {"hall": {"name": "Hall"}},
            "positions": {"P": "hall"}, "entities": {},
            "contacts": [], "scales": {}, "contained": {},
        }
        scene.update(over)
        return scene

    def test_declaring_vitals_creates_the_table(self):
        scene = merge_scene_with_diff(
            self._scene(), {"vitals": {"P": {"stamina": 0.5}}})
        assert scene["vitals"]["P"]["stamina"] == 0.5

    def test_time_moves_them_not_turns(self):
        scene = merge_scene_with_diff(
            self._scene(), {"vitals": {"P": {}},
                            "time": {"duration_seconds": 3600}})
        one_hour = scene["vitals"]["P"]["stamina"]

        scene2 = merge_scene_with_diff(
            self._scene(), {"vitals": {"P": {}},
                            "time": {"duration_seconds": 36000}})
        assert scene2["vitals"]["P"]["stamina"] < one_hour

    def test_values_are_clamped(self):
        scene = merge_scene_with_diff(
            self._scene(), {"vitals": {"P": {"stamina": 99, "injury": -4}}})
        assert scene["vitals"]["P"]["stamina"] == 1.0
        assert scene["vitals"]["P"]["injury"] == 0.0

    def test_a_body_can_be_dropped_from_tracking(self):
        scene = merge_scene_with_diff(
            self._scene(), {"vitals": {"P": {"stamina": 0.5}}})
        scene = merge_scene_with_diff(scene, {"vitals": {"P": None}})
        assert "P" not in scene["vitals"]

    @pytest.mark.parametrize("vital,value,expected", [
        ("stamina", 1.0, ""), ("stamina", 0.6, "tired"),
        ("stamina", 0.05, "exhausted"), ("stamina", 0.0, "spent"),
        ("nourishment", 0.3, "very hungry"), ("nourishment", 0.0, "starving"),
        ("air", 0.5, "breathing hard"), ("air", 0.3, "short of breath"),
        ("air", 0.0, "suffocating"), ("air", 1.0, ""),
        ("injury", 0.0, ""), ("injury", 0.5, "hurt"),
        ("injury", 0.9, "critically injured"),
    ])
    def test_labels(self, vital, value, expected):
        from world.survival import vital_label
        assert vital_label(vital, value) == expected

    def test_a_healthy_body_says_nothing(self):
        from world.survival import vitals_facts

        scene = merge_scene_with_diff(self._scene(), {"vitals": {"P": {}}})
        assert vitals_facts(scene, "P") == []

    def test_a_failing_body_is_ground_truth(self):
        from world.spatial import spatial_facts

        scene = merge_scene_with_diff(
            self._scene(), {"vitals": {"P": {"stamina": 0.05}}})
        assert any("exhausted" in f for f in spatial_facts(scene, "P", []))


class TestAirAndSealedContainers:
    """The direct consequence of containers-as-places: sealing someone in was
    previously survivable indefinitely."""

    def _jar(self, enclosure="opaque", hatch="closed"):
        return {
            "rooms": {
                "hall": {"name": "Hall", "adjacent": []},
                "jar_in": {"name": "Inside", "adjacent": [],
                           "parent_entity": "jar"},
            },
            "positions": {"P": "jar_in", "jar": "hall"},
            "entities": {"jar": {
                "name": "Jar", "kind": "object", "enclosure": enclosure,
                "interior_rooms": ["jar_in"], "state": {"hatch": hatch}}},
            "contacts": [], "scales": {}, "contained": {},
            "vitals": {"P": {"air": 1.0, "stamina": 1.0,
                             "nourishment": 1.0, "injury": 0.0}},
        }

    def test_a_sealed_body_runs_out_of_air(self):
        scene = merge_scene_with_diff(
            self._jar(), {"time": {"duration_seconds": 600}})
        assert scene["vitals"]["P"]["air"] < 1.0

    def test_glass_is_no_help(self):
        """Being seen through something is not breathing through it."""
        scene = merge_scene_with_diff(
            self._jar("transparent"), {"time": {"duration_seconds": 600}})
        assert scene["vitals"]["P"]["air"] < 1.0

    def test_an_open_container_does_not_suffocate_anyone(self):
        scene = merge_scene_with_diff(
            self._jar(hatch="open"), {"time": {"duration_seconds": 3600}})
        assert scene["vitals"]["P"]["air"] == 1.0

    def test_an_ordinary_room_does_not_suffocate_anyone(self):
        scene = merge_scene_with_diff({
            "rooms": {"hall": {"name": "Hall"}},
            "positions": {"P": "hall"}, "entities": {},
            "vitals": {"P": {"air": 1.0}},
        }, {"time": {"duration_seconds": 86400}})
        assert scene["vitals"]["P"]["air"] == 1.0

    def test_air_returns_once_out(self):
        scene = merge_scene_with_diff(
            self._jar(), {"time": {"duration_seconds": 600}})
        assert scene["vitals"]["P"]["air"] < 1.0

        scene["positions"]["P"] = "hall"
        scene = merge_scene_with_diff(scene, {"time": {"duration_seconds": 120}})
        assert scene["vitals"]["P"]["air"] == 1.0


class TestCarriedLight:
    """A room-level model is wrong in one obvious way: a character standing in
    a lightless cellar holding a lit lamp still saw nothing."""

    def _cellar(self, lit=True, present=True, emits="dim"):
        return {
            "rooms": {"cellar": {"name": "Cellar", "desc": "Stone.",
                                 "light": "dark", "adjacent": []},
                      "hall": {"name": "Hall", "desc": "Hall.", "light": "lit",
                               "adjacent": []}},
            "positions": {"P": "cellar",
                          **({"torch": "cellar"} if present else {"torch": "hall"})},
            "entities": {"torch": {"name": "Torch", "light_source": emits,
                                   "state": {"lit": lit}}},
        }

    def test_a_lit_torch_lights_the_room(self):
        assert effective_light(self._cellar(), "cellar") == "dim"

    def test_and_lets_you_see(self):
        scene = self._cellar()
        assert has_visual(spatial_rel(scene, "cellar", "cellar")) is True

    def test_a_doused_torch_does_not(self):
        scene = self._cellar(lit=False)
        assert effective_light(scene, "cellar") == "dark"
        assert has_visual(spatial_rel(scene, "cellar", "cellar")) is False

    def test_a_torch_in_another_room_does_not_light_this_one(self):
        assert effective_light(self._cellar(present=False), "cellar") == "dark"

    def test_a_brighter_source_wins(self):
        assert effective_light(self._cellar(emits="bright"), "cellar") == "bright"

    def test_it_travels_with_whoever_carries_it(self):
        """Carried entities already have their holder's position derived, so
        the lamp is wherever its bearer is with nothing extra to track."""
        scene = self._cellar(present=False)
        scene["contained"] = {"torch": {"in": "P", "mode": "held"}}
        scene["contacts"], scene["scales"] = [], {}
        scene = merge_scene_with_diff(scene, {})

        assert scene["positions"]["torch"] == "cellar"
        assert effective_light(scene, "cellar") == "dim"

    def test_an_ordinary_object_is_not_a_light(self):
        scene = self._cellar()
        scene["entities"]["torch"].pop("light_source")
        assert effective_light(scene, "cellar") == "dark"

    def test_light_source_survives_schema_validation(self):
        from llm.schemas import StateDiff

        diff = StateDiff(entities={"t": {"name": "Lantern",
                                         "light_source": "lit"}})
        assert diff.dict()["entities"]["t"]["light_source"] == "lit"


class TestLightIsGradedNotBinary:
    """A boolean cannot express the state most scenes want: a shape moving in
    the gloom that you cannot identify."""

    def _rooms_at(self, light):
        return {
            "rooms": {"a": {"name": "A", "desc": "A.", "light": light,
                            "adjacent": []}},
            "positions": {"P": "a", "Q": "a"}, "entities": {},
        }

    @pytest.mark.parametrize("light,level", [
        ("dark", "none"), ("dim", "shapes"), ("lit", "full"), ("bright", "full"),
    ])
    def test_sight_levels(self, light, level):
        from world.spatial import sight_level

        scene = self._rooms_at(light)
        assert sight_level(spatial_rel(scene, "a", "a")) == level

    def test_a_blocked_line_is_none_whatever_the_light(self):
        from world.spatial import sight_level

        scene = {"rooms": {
            "a": {"name": "A", "light": "bright",
                  "adjacent": [{"to": "b", "barrier": "wall"}]},
            "b": {"name": "B", "light": "bright", "adjacent": []}}}
        assert sight_level(spatial_rel(scene, "a", "b")) == "none"

    def test_has_visual_still_answers_the_boolean(self):
        assert has_visual(spatial_rel(self._rooms_at("dim"), "a", "a")) is True
        assert has_visual(spatial_rel(self._rooms_at("dark"), "a", "a")) is False


class TestLightIsLocalNotRoomWide:
    """A hand torch makes a pool. Standing next to the bearer you are lit;
    across the room you are a shape."""

    def _hall(self):
        return {
            "rooms": {"hall": {"name": "Hall", "desc": "Long.", "light": "dark",
                               "size": "large", "adjacent": [],
                               "anchors": {"door": {}, "far": {}}}},
            "positions": {"Bearer": "hall", "Far": "hall", "torch": "hall"},
            "stations": {"Bearer": {"at": "door", "near": []},
                         "Far": {"at": "far", "near": []},
                         "torch": {"at": "door", "near": []}},
            "entities": {"torch": {"name": "torch", "light_source": "lit",
                                   "portable": True, "state": {}}},
        }

    def test_the_bearer_is_lit(self):
        from world.spatial import light_at
        assert light_at(self._hall(), "Bearer") == "lit"

    def test_someone_across_the_room_is_only_a_shape(self):
        from world.spatial import light_at
        assert light_at(self._hall(), "Far") == "dim"

    def test_the_room_itself_is_not_declared_lit(self):
        """A pool of light must not silently illuminate the far corner."""
        assert effective_light(self._hall(), "hall") == "dark"

    def test_a_room_filling_source_does_light_everyone(self):
        from world.spatial import light_at

        scene = self._hall()
        scene["entities"]["torch"]["light_radius"] = "room"
        assert light_at(scene, "Far") == "lit"
        assert effective_light(scene, "hall") == "lit"

    def test_a_hearth_defaults_to_filling_the_room(self):
        from world.spatial import light_at

        scene = self._hall()
        scene["entities"]["torch"].pop("portable")       # fixed, not carried
        assert light_at(scene, "Far") == "lit"

    def test_graded_sight_between_bodies_uses_local_light(self):
        from world.spatial import visual_level_between

        scene = self._hall()
        # The bearer is in their own light; the far figure is only a shape.
        assert visual_level_between(scene, "Far", "Bearer") == "full"
        assert visual_level_between(scene, "Bearer", "Far") == "shapes"


class TestAnyWayOfMakingLight:
    """There is no separate mechanism for a campfire: building one is creating
    an entity with light_source and a position."""

    @pytest.mark.parametrize("name,emits,radius", [
        ("Campfire", "lit", "room"),
        ("Brazier", "dim", "room"),
        ("Hearth", "lit", "room"),
        ("Glowing rune", "dim", "room"),
    ])
    def test_a_built_or_kindled_source_lights_the_room(self, name, emits, radius):
        scene = {
            "rooms": {"cave": {"name": "Cave", "desc": "Stone.",
                               "light": "dark", "adjacent": []}},
            "positions": {"fire": "cave", "P": "cave"},
            "entities": {"fire": {"name": name, "light_source": emits,
                                  "light_radius": radius, "state": {}}},
        }
        assert effective_light(scene, "cave") != "dark"
        assert has_visual(spatial_rel(scene, "cave", "cave")) is True

    def test_dousing_it_brings_the_dark_back(self):
        scene = {
            "rooms": {"cave": {"name": "Cave", "light": "dark", "adjacent": []}},
            "positions": {"fire": "cave"},
            "entities": {"fire": {"name": "Campfire", "light_source": "lit",
                                  "light_radius": "room",
                                  "state": {"lit": False}}},
        }
        assert effective_light(scene, "cave") == "dark"


class TestLightSourcesInBackdrops:
    def test_a_fire_lights_the_picture_and_is_named(self):
        from dressing.backdrops import compose_prompt, room_projection

        scene = {"rooms": {"cave": {"name": "Cave", "desc": "Wet stone.",
                                    "light": "dark", "adjacent": []}},
                 "positions": {"fire": "cave"},
                 "entities": {"fire": {"name": "Campfire", "light_source": "lit",
                                       "light_radius": "room", "state": {}}}}
        prompt = compose_prompt(room_projection(scene, "cave"))

        assert "lit by Campfire" in prompt
        assert "darkness" not in prompt      # it is not a dark room any more

    def test_the_cache_key_follows_the_fire(self):
        from dressing.backdrops import visual_signature

        dark = {"rooms": {"cave": {"name": "Cave", "desc": "S.", "light": "dark"}},
                "positions": {}, "entities": {}}
        lit = {"rooms": {"cave": {"name": "Cave", "desc": "S.", "light": "dark"}},
               "positions": {"fire": "cave"},
               "entities": {"fire": {"name": "Campfire", "light_source": "lit",
                                     "light_radius": "room", "state": {}}}}
        assert visual_signature(dark, "cave") != visual_signature(lit, "cave")


class TestBackdropFollowsTheLightYouCarry:
    """A backdrop is the room as the PLAYER sees it. A hand light does not
    raise the room's ambient -- correctly, for who can see whom -- so asking
    the room alone would render a cave the player is lighting as pitch black."""

    def _cave(self, lit=True, emits="dim", portable=True):
        return {
            "rooms": {"cave": {"name": "Cave", "desc": "Wet stone.",
                               "light": "dark", "adjacent": []}},
            "positions": {"P": "cave", "torch": "cave"},
            "entities": {"torch": {"name": "Torch", "light_source": emits,
                                   "portable": portable,
                                   "state": {"lit": lit}}},
        }

    def test_a_carried_light_lights_the_picture(self):
        from dressing.backdrops import compose_prompt, room_projection

        prompt = compose_prompt(room_projection(self._cave(), "cave", viewer="P"))
        assert "lit by Torch" in prompt
        assert "darkness" not in prompt

    def test_turning_it_off_returns_to_dark(self):
        from dressing.backdrops import compose_prompt, room_projection

        prompt = compose_prompt(
            room_projection(self._cave(lit=False), "cave", viewer="P"))
        assert "darkness" in prompt
        assert "lit by" not in prompt

    def test_that_counts_as_a_room_change_for_the_cache(self):
        """Or the dark cave keeps serving the torchlit picture."""
        from dressing.backdrops import visual_signature

        on = visual_signature(self._cave(), "cave", viewer="P")
        off = visual_signature(self._cave(lit=False), "cave", viewer="P")
        assert on != off

    def test_intensity_changes_the_picture(self):
        from dressing.backdrops import compose_prompt, room_projection

        candle = compose_prompt(room_projection(
            self._cave(emits="dim"), "cave", viewer="P"))
        flood = compose_prompt(room_projection(
            self._cave(emits="bright", portable=False), "cave", viewer="P"))

        assert "small pool of warm light" in candle
        assert "harsh light" in flood
        assert candle != flood

    def test_a_hand_light_says_the_rest_of_the_room_is_dark(self):
        from dressing.backdrops import compose_prompt, room_projection

        prompt = compose_prompt(room_projection(self._cave(), "cave", viewer="P"))
        assert "only illumination" in prompt

    def test_a_room_filling_source_does_not(self):
        from dressing.backdrops import compose_prompt, room_projection

        prompt = compose_prompt(room_projection(
            self._cave(emits="lit", portable=False), "cave", viewer="P"))
        assert "only illumination" not in prompt

    def test_without_a_viewer_it_falls_back_to_room_ambient(self):
        from dressing.backdrops import room_projection

        assert room_projection(self._cave(), "cave")["light"] == "dark"

    def test_a_torch_in_another_room_does_not_light_the_picture(self):
        from dressing.backdrops import room_projection

        scene = self._cave()
        scene["rooms"]["hall"] = {"name": "Hall", "adjacent": []}
        scene["positions"]["torch"] = "hall"
        assert room_projection(scene, "cave", viewer="P")["light"] == "dark"


class TestSurvivalSurvivesBranchingAndRerolls:
    """Whether a story tracks condition is an authoring decision, not a fact
    about turn 40 — so it must ride through a restore the same way genre and
    NPC autonomy already do. The VITALS are diegetic and must NOT: rewind to
    before you were starving and you are not starving."""

    def test_it_uses_the_same_mechanism_as_genre_and_dialogue(self):
        from persist.checkpoints import PRESERVED_SETTING_KEYS

        assert "survival_enabled" in PRESERVED_SETTING_KEYS
        # The company it keeps is the argument for it being there.
        assert "style_guide" in PRESERVED_SETTING_KEYS
        assert "dialogue_config" in PRESERVED_SETTING_KEYS

    def test_a_restore_carries_the_setting_across(self, temp_db):
        import time

        from persist.checkpoints import _preserved_settings
        from world.survival import set_survival_enabled

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Ordeal", "", time.time()))
        set_survival_enabled(cid, True)

        assert _preserved_settings(cid).get("survival_enabled") is True

    def test_it_is_per_story_not_per_install(self, temp_db):
        import time

        from world.survival import set_survival_enabled, survival_enabled

        a = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                       ("Ordeal", "", time.time()))
        b = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                       ("Tavern", "", time.time()))
        set_survival_enabled(a, True)

        assert survival_enabled(a) is True
        assert survival_enabled(b) is False      # a tavern needs no hunger clock

    def test_the_default_is_off_for_a_fresh_story(self, temp_db):
        import time

        from world.survival import survival_enabled

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Fresh", "", time.time()))
        assert survival_enabled(cid) is False

    def test_a_reroll_does_not_double_tick(self):
        """The pipeline restores the checkpoint before re-committing, so a
        rerun merges from the SAME pre-turn scene rather than from an already
        advanced one."""
        base = {"rooms": {"a": {"name": "A"}}, "positions": {"P": "a"},
                "entities": {}, "contacts": [], "scales": {}, "contained": {},
                "vitals": {"P": {"air": 1.0, "stamina": 1.0,
                                 "nourishment": 1.0, "injury": 0.0}}}
        diff = {"time": {"duration_seconds": 3600}}

        import copy
        once = merge_scene_with_diff(copy.deepcopy(base), diff)
        twice = merge_scene_with_diff(copy.deepcopy(base), diff)

        assert once["vitals"]["P"]["stamina"] == twice["vitals"]["P"]["stamina"]

    def test_a_stored_vital_that_is_not_a_number_does_not_take_the_turn_down(
            self):
        """The stored table is the same JSON blob a checkpoint restore, an
        archive import, an extension and the GM's own scene editor all write,
        so a value read back OUT of it is untrusted exactly as a value read
        out of a diff is. Both seeding sites trusted it: `tick_vitals` did
        arithmetic on it and `apply_vitals_diff` rounded it, and either raises
        TypeError out of `merge_scene_with_diff` -- which fails the whole
        turn, not the vital."""
        base = {"rooms": {"a": {"name": "A"}}, "positions": {"P": "a"},
                "entities": {}, "contacts": [], "scales": {}, "contained": {},
                "vitals": {"P": {"air": 0.9, "stamina": "low",
                                 "nourishment": 0.5, "injury": 0.0}}}
        merged = merge_scene_with_diff(base, {"time": {"duration_seconds": 60},
                                              "vitals": {"P": {"air": 0.8}}})
        stamina = merged["vitals"]["P"]["stamina"]
        assert isinstance(stamina, float)
        # The unreadable one falls to its default; the readable ones are
        # untouched by their neighbour's damage.
        assert merged["vitals"]["P"]["nourishment"] < 0.5
        assert merged["vitals"]["P"]["air"] > 0.8


class TestAuthoringSettingsSurviveARestore:
    """A rewind rolls back the STORY, not the author's standing decisions about
    it. Every key here is edited through the interface and belongs to the
    reader; the story state they shape is diegetic and correctly reverts."""

    @pytest.mark.parametrize("key", [
        "style_guide",                # genre and tone
        "dialogue_config",            # NPC autonomy
        "background_config",
        "paradox_policy",
        "fixed_points",               # the author's constraints, not the
                                      # paradoxes they detect
        "persona_private_history",    # edited behind the persona lock
        "survival_enabled",
    ])
    def test_it_is_preserved(self, key):
        from persist.checkpoints import PRESERVED_SETTING_KEYS
        assert key in PRESERVED_SETTING_KEYS

    @pytest.mark.parametrize("key", [
        "scene",                # where everyone is, and what they are doing
        "known",                # who recognises whom
        "simulation_clock",
        "pending",
        "standing_intentions",
        "paradoxes",            # what the fixed points caught, not the points
        "lore_cache",
        # Was on the preserved list, and this class's own docstring is why it
        # should not have been: "every key here is EDITED THROUGH THE
        # INTERFACE". Narration person is not — it is detected from how the
        # player writes, and has no endpoint and no control anywhere in the UI.
        # Preserving it meant one misdetection outlived the turn that caused
        # it, the restore meant to undo it, and every reroll after. Observed
        # live: a checkpoint holding "second" restored into a world still
        # holding "first", and the story stayed in the wrong person.
        "narration_person",
    ])
    def test_story_state_is_not(self, key):
        """The other half of the contract: rewinding must actually rewind."""
        from persist.checkpoints import PRESERVED_SETTING_KEYS
        assert key not in PRESERVED_SETTING_KEYS

    def test_a_persona_history_edit_survives_a_rewind(self, temp_db):
        import time

        from persist.checkpoints import _preserved_settings
        from core.db import wset

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Story", "", time.time()))
        wset(cid, "persona_private_history", ["I have never told anyone."])

        assert _preserved_settings(cid)["persona_private_history"] == [
            "I have never told anyone."]

    def test_a_declared_fixed_point_survives_a_rewind(self, temp_db):
        import time

        from persist.checkpoints import _preserved_settings
        from world.paradox import add_fixed_point

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Story", "", time.time()))
        add_fixed_point(cid, entity_id="lighthouse", frame_id=None,
                        label="must stand", required_exists=True)

        preserved = _preserved_settings(cid)["fixed_points"]
        assert preserved and preserved[0]["entity_id"] == "lighthouse"
