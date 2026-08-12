"""What the player says happened has happened, before pass 1 fires.

THE GAP. A player's declaration reached `director_interpret` as prose and
reached the SCENE only through `director_resolve` -- which runs after every
character has already declared. So everything a player narrated was invisible
for the beat in which they narrated it: "I pull my top off" was perceived as
still wearing it, "I kneel" as still standing, "I duck into the alcove" as
standing in the open with no alcove. Each reactor decided against a world one
beat stale, and the change surfaced the turn AFTER it happened.

Contact, movement and following were each fixed one at a time, with their own
field, their own guard and their own preview -- a hand-picked list of the
channels lucky enough to have been noticed, each re-deciding what the player
was allowed to say.

THE RULE THESE TESTS PIN: interpret is not a lesser authority than resolve.
It is the same authority scoped to player input. So `state_assertions` is a
full `StateDiff` -- the same schema, the same channels, applied through the
same `merge_scene_with_diff` commit uses. What bounds it is its SOURCE (it
reads the player's declaration and nothing else) and the Director's existing
`asserted` vs `contestable` classification, not a whitelist.

And it writes nothing. The preview is a copy; commit stays the only writer.
"""

from __future__ import annotations

import json
import time

import pytest

import attire
from agents.common import (merge_player_state_assertions,
                           preview_player_state_assertions,
                           validated_player_state_assertions)


def _scene():
    return {
        "positions": {"Hinami": "room_a", "Elyra": "room_a"},
        "rooms": {"room_a": {"name": "Treatment Room", "adjacent": []}},
        "entities": {},
        "poses": {"Hinami": {"posture": "standing", "support": "floor"}},
        "attire": {
            "Hinami": attire.authored_entry(
                [], [], {"torso": {"garments": [{"name": "fitted tank top"}]},
                         "groin": {"garments": [{"name": "travel shorts"}]}}),
            "Elyra": attire.authored_entry(
                [], [], {"torso": {"garments": [{"name": "silk robe"}]}}),
        },
    }


def _said(raw, sc=None, who="Hinami"):
    notes = []
    got = validated_player_state_assertions(sc or _scene(), raw, who,
                                            notes.append)
    return got, notes


class TestTheSameAuthorityAsResolve:
    """No channel is off-limits: equal authority means the same vocabulary."""

    @pytest.mark.parametrize("channel,payload", [
        ("poses", {"Hinami": {"posture": "kneeling"}}),
        ("attire", {"Hinami": {"remove": ["fitted tank top"]}}),
        ("rooms", {"alcove": {"name": "Alcove", "desc": "A shallow recess."}}),
        ("entities", {"crate": {"name": "crate", "room": "room_a"}}),
        ("positions", {"Hinami": "alcove"}),
        ("stations", {"Hinami": {"at": "treatment_platform"}}),
        ("conditions", {"Hinami": [{"name": "winded"}]}),
        ("world_facts", ["The lamp is lit."]),
        ("inventory_ops", [{"op": "add", "owner": "Hinami", "item": "torch"}]),
    ])
    def test_every_state_diff_channel_is_assertable(self, channel, payload):
        got, notes = _said({channel: payload})
        assert channel in got, f"{channel} was refused"
        assert notes == []

    def test_the_shape_is_the_directors_own(self):
        """Not "a subset of StateDiff" -- StateDiff. If resolve grows a
        channel, interpret has it the same day, with no list to update."""
        from schemas import DirectorInterpret, StateDiff
        assert "state_assertions" in DirectorInterpret.__fields__
        for channel in ("rooms", "entities", "poses", "attire", "destruction",
                        "world_facts", "containment", "overlays"):
            assert channel in StateDiff.__fields__

    def test_several_channels_travel_as_one_payload(self):
        """One declaration, one assertion -- not one field per thing somebody
        happened to notice."""
        got, _ = _said({
            "rooms": {"alcove": {"name": "Alcove"}},
            "positions": {"Hinami": "alcove"},
            "attire": {"Hinami": {"remove": ["fitted tank top"]}},
            "poses": {"Hinami": {"posture": "crouching"}},
        })
        assert set(got) >= {"rooms", "positions", "attire", "poses"}


class TestItValidatesShapeAndNothingElse:
    def test_junk_is_survived(self):
        for raw in (None, "off", [], 7, 0, ""):
            assert validated_player_state_assertions(
                _scene(), raw, "Hinami") == {}

    def test_a_malformed_payload_is_reported_not_raised(self):
        got, notes = _said({"positions": ["not", "a", "mapping"]})
        assert got == {}
        assert any("malformed" in n for n in notes)

    def test_empty_channels_are_dropped(self):
        """An empty dict is the model saying nothing, and saying nothing must
        not cost a scene merge."""
        got, _ = _said({"poses": {}, "rooms": {}, "world_facts": []})
        assert got == {}

    def test_validating_does_not_touch_the_scene(self):
        sc = _scene()
        before = json.dumps(sc, sort_keys=True)
        validated_player_state_assertions(
            sc, {"attire": {"Hinami": {"remove": ["fitted tank top"]}},
                 "poses": {"Hinami": {"posture": "kneeling"}}}, "Hinami")
        assert json.dumps(sc, sort_keys=True) == before


class TestResolveKeepsTheLastWord:
    def test_a_silent_resolve_does_not_lose_the_assertion(self):
        """Previewing fixes what reactors SAW and nothing else. If resolve
        never mentions the change, commit writes the turn without it and the
        ledger forks from the beat everybody just played."""
        merged = merge_player_state_assertions(
            {"attire": {"Hinami": {"remove": ["fitted tank top"]}},
             "poses": {"Hinami": {"posture": "kneeling"}}}, {})
        assert merged["attire"]["Hinami"]["remove"] == ["fitted tank top"]
        assert merged["poses"]["Hinami"]["posture"] == "kneeling"

    def test_resolve_restating_the_subject_wins(self):
        """Resolve keeps the last word but has to USE it; silence is not a
        contradiction."""
        notes = []
        merged = merge_player_state_assertions(
            {"poses": {"Hinami": {"posture": "kneeling"}}},
            {"poses": {"Hinami": {"posture": "supine"}}}, report=notes.append)
        assert merged["poses"]["Hinami"]["posture"] == "supine"
        assert any("restated" in n for n in notes)

    def test_another_subject_in_the_same_diff_is_untouched(self):
        merged = merge_player_state_assertions(
            {"poses": {"Hinami": {"posture": "kneeling"}}},
            {"poses": {"Elyra": {"posture": "standing"}}})
        assert set(merged["poses"]) == {"Hinami", "Elyra"}

    def test_ops_append_rather_than_replace(self):
        """An op is an event, not a snapshot, so both happened."""
        merged = merge_player_state_assertions(
            {"substance_ops": [{"substance": "sweat"}]},
            {"substance_ops": [{"substance": "wine"}]})
        assert len(merged["substance_ops"]) == 2

    def test_channels_resolve_never_mentioned_are_left_alone(self):
        merged = merge_player_state_assertions(
            {"poses": {"Hinami": {"posture": "kneeling"}}},
            {"positions": {"Hinami": "room_b"}})
        assert merged["positions"] == {"Hinami": "room_b"}


class TestPassOneSeesIt:
    """The end of the road: the scene pass 1 builds every view from."""

    def _ctx(self, temp_db, player_input):
        from pipeline_context import ChatData, PipelineContext, TurnData
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Assert", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 1, player_input, time.time()))
        return PipelineContext(
            chat=ChatData(id=chat_id, name="Assert", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                          player_input=player_input, created=time.time()),
            cast=[], input=player_input)

    def test_body_and_world_both_land_before_anyone_looks(self, temp_db):
        ctx = self._ctx(temp_db, "I pull my top off and drop to my knees.")
        sc = _scene()
        asserted, _ = _said({
            "attire": {"Hinami": {"remove": ["fitted tank top"]}},
            "poses": {"Hinami": {"posture": "kneeling"}},
            "rooms": {"alcove": {"name": "Alcove", "desc": "A recess."}},
        }, sc)
        seen = preview_player_state_assertions(sc, asserted, ctx, "Hinami")

        top = [g for g in
               seen["attire"]["Hinami"]["regions"]["torso"]["garments"]
               if g["name"] == "fitted tank top"]
        assert top and top[0]["state"] == "removed", "reactors still see it on"
        assert seen["poses"]["Hinami"]["posture"] == "kneeling"
        assert "alcove" in seen["rooms"]

    def test_the_scene_it_came_from_is_untouched(self, temp_db):
        """The copy is the whole safety property: commit stays the only
        writer, and pass 1 must not be able to become a second one."""
        ctx = self._ctx(temp_db, "I kneel.")
        sc = _scene()
        before = json.dumps(sc, sort_keys=True)
        preview_player_state_assertions(
            sc, {"poses": {"Hinami": {"posture": "kneeling"}},
                 "rooms": {"alcove": {"name": "Alcove"}}}, ctx, "Hinami")
        assert json.dumps(sc, sort_keys=True) == before

    def test_the_torso_stops_being_concealed(self, temp_db):
        """What a reactor actually reads: concealment, not the rung."""
        ctx = self._ctx(temp_db, "I pull my top off over my head.")
        sc = _scene()
        assert "torso" in attire.concealing_garments(
            sc["attire"]["Hinami"]["regions"])
        seen = preview_player_state_assertions(
            sc, {"attire": {"Hinami": {"remove": ["fitted tank top"]}}},
            ctx, "Hinami")
        concealed = attire.concealing_garments(
            seen["attire"]["Hinami"]["regions"])
        assert "torso" not in concealed
        assert "groin" in concealed, "the shorts were never mentioned"

    def test_nothing_asserted_is_the_same_scene_object(self, temp_db):
        """No assertion must not cost a deep copy of the scene every turn."""
        ctx = self._ctx(temp_db, "I wait.")
        sc = _scene()
        assert preview_player_state_assertions(sc, {}, ctx, "Hinami") is sc
