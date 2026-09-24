"""A body inside another is in reach of it, at every site.

The place form gives an interior a room of its own, so a body swallowed into
a throat stands in one room and the body whose throat it is stands in
another. `normalize_scene_contacts` has kept that pair's contact since the
enclosure landing (`enclosure_joins_rooms`); two sites still read "same room"
and treated the two closest bodies in the world as strangers across a wall.
Measured on the chat 137 replay (2026-09-23), a player inside Mirelle's
throat for seven beats:

  * `director_contact._validated_player_contact_assertions` discarded every
    interior contact the encoder wrote -- her hands on the walls -- "between
    non-co-located bodies", so the body she was inside never felt her;
  * no reactor rule reached the holder: the Director paces the player's room
    and the hearing widening asks what carries across a wall, so Mirelle was
    asked what she did on one beat of seven -- the one a line targeted.

Strictly the pair, in both directions: a third body standing in the holder's
room is not joined to the occupant.
"""

from __future__ import annotations

import inspect
import json
import time

from agents.director import _validated_player_contact_assertions
from story.character_schema import default_character_data, default_persona_data


def _swallowed():
    return {
        "location": "a spa", "time_of_day": "night",
        "rooms": {
            "treatment_room": {"name": "Treatment Room", "adjacent": []},
            "mirelle_throat": {"name": "throat", "parent_entity": "char_mirelle",
                               "adjacent": []},
        },
        "entities": {"char_mirelle": {"name": "Mirelle", "kind": "person"}},
        "positions": {"Hinami": "mirelle_throat", "Mirelle": "treatment_room",
                      "Bram": "treatment_room"},
        "contacts": [], "attire": {}, "overlays": {},
    }


def _hands_on(target):
    return {"actor": "Hinami", "actor_part": "hands", "target": target,
            "target_part": "throat wall", "manner": "press",
            "relation": "interior"}


class TestTheContactGuard:
    def test_the_occupant_touching_its_holder_is_kept(self):
        reports = []
        kept = _validated_player_contact_assertions(
            _swallowed(), [_hands_on("Mirelle")], "Hinami", reports.append)
        assert [c["target"] for c in kept] == ["Mirelle"]
        assert reports == []

    def test_a_third_body_in_the_holders_room_is_still_out_of_reach(self):
        reports = []
        kept = _validated_player_contact_assertions(
            _swallowed(), [_hands_on("Bram")], "Hinami", reports.append)
        assert kept == []
        assert reports == [
            "discarded a contact assertion between non-co-located bodies"]

    def test_a_hand_on_the_inside_is_a_hand_on_its_holder(self):
        """Chat 137 idx 47 (round 9, 2026-09-23): every contact named the
        stomach ROOM as its target -- a room is where a body is, never a
        body -- and all four were discarded. The room's own record says
        whose inside it is, and its name is the inside's prose label."""
        reports = []
        kept = _validated_player_contact_assertions(
            _swallowed(), [_hands_on("mirelle_throat")], "Hinami", reports.append)
        assert [(c["target"], c.get("target_interior")) for c in kept] == [
            ("Mirelle", "throat")]
        assert reports == []

    def test_an_ordinary_room_is_still_nobody(self):
        """Only an inside names a holder; a room with no `parent_entity` is
        a place, and a contact naming it is still refused."""
        reports = []
        kept = _validated_player_contact_assertions(
            _swallowed(), [_hands_on("treatment_room")], "Hinami", reports.append)
        assert kept == []

    def test_the_commit_keeps_it_under_the_holders_name(self):
        from world.spatial import normalize_scene_contacts
        scene = _swallowed()
        scene["contacts"] = [dict(_hands_on("mirelle_throat"), relation="surface")]
        normalize_scene_contacts(scene)
        assert [(c["target"], c.get("target_interior")) for c in scene["contacts"]] == [
            ("Mirelle", "throat")]


def _chat(temp_db, scene):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(default_persona_data("Hinami")), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Swallowed", "", time.time(), persona_id))
    ids = {}
    for name in ("Mirelle", "Bram"):
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    return chat_id, cast, ids


def _planned(cast, chat_id):
    from agents.runtime import build_plan
    interp = {"flow": {"reactors": [], "resolution_flags": {}}}
    return [key for key, _ in build_plan(interp, cast, chat_id=chat_id)]


class TestTheHolderIsInTheBeat:
    def test_the_body_the_player_is_inside_is_asked(self, temp_db):
        """No line, nobody addressed: the chat 137 idx 47 shape ("You try to
        feel around your surroundings")."""
        chat_id, cast, ids = _chat(temp_db, _swallowed())
        keys = _planned(cast, chat_id)
        assert f"character:{ids['Mirelle']}" in keys
        assert f"character:{ids['Bram']}" not in keys

    def test_a_body_inside_the_player_is_asked(self, temp_db):
        scene = _swallowed()
        scene["rooms"] = {
            "treatment_room": {"name": "Treatment Room", "adjacent": []},
            "hinami_belly": {"name": "belly", "parent_entity": "persona_hinami",
                             "adjacent": []},
        }
        scene["entities"] = {"persona_hinami": {"name": "Hinami", "kind": "person"}}
        scene["positions"] = {"Hinami": "treatment_room",
                              "Mirelle": "hinami_belly", "Bram": "hinami_belly"}
        chat_id, cast, ids = _chat(temp_db, scene)
        keys = _planned(cast, chat_id)
        assert f"character:{ids['Mirelle']}" in keys
        assert f"character:{ids['Bram']}" in keys

    def test_the_planner_and_the_loop_widen_alike(self):
        """Two readers derive the reactor list on their own; both widen."""
        from agents import loops, runtime
        assert "widen_reactors_to_enclosure" in inspect.getsource(runtime.build_plan)
        assert "widen_reactors_to_enclosure" in inspect.getsource(
            loops.interaction_loop)


def _stomach():
    return {
        "rooms": {
            "treatment_room": {"name": "Treatment Room", "adjacent": []},
            "mirelle_mouth": {"name": "mouth", "parent_entity": "char_mirelle",
                              "adjacent": [{"to": "treatment_room", "barrier": "closed"}]},
            "mirelle_throat": {"name": "throat", "parent_entity": "char_mirelle",
                               "adjacent": [{"to": "mirelle_mouth", "barrier": "membrane"}]},
            "mirelle_stomach": {"name": "stomach", "parent_entity": "char_mirelle",
                                "adjacent": [{"to": "mirelle_throat", "barrier": "membrane"}]},
            "hall": {"name": "Hall", "adjacent": [{"to": "treatment_room", "barrier": "open"}]},
        },
        "entities": {"char_mirelle": {"name": "Mirelle", "kind": "person"}},
        "attire": {"Mirelle": {"regions": {}}},
        "positions": {"Hinami": "mirelle_stomach", "Mirelle": "treatment_room"},
    }


class TestTheHolderIsNeverAway:
    """Chat 137 replay, round 4 (2026-09-23): swallowed to the stomach, three
    adjacency steps from the room her holder stood in, the player was out of
    the beat's one-step range of it -- and Mirelle was split into a causality
    bubble of her own, while Hinami spoke to her from inside her."""

    def test_the_holders_room_is_attended_from_deep_inside(self):
        from world.spatial import attended_rooms
        reach = attended_rooms(_stomach(), {"mirelle_stomach"}, hops=1)
        assert "treatment_room" in reach and "mirelle_mouth" in reach

    def test_the_holder_is_not_split_off(self):
        from world.spatial_bubbles import bubble_split_decision
        assert bubble_split_decision(_stomach(), party_names=["Hinami"],
                                     cast_names=["Mirelle"]) is None

    def test_the_insides_of_a_body_in_the_room_are_attended(self):
        from world.spatial import attended_rooms
        reach = attended_rooms(_stomach(), {"hall"}, hops=1)
        assert "mirelle_stomach" in reach
