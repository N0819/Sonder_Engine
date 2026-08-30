"""A `positions` value must name a ROOM, and the mint never asked whether it did.

Putting a body somewhere is the strongest possible assertion that the
somewhere exists, so an asserted room that does not exist is MINTED rather
than refused -- refusing it would leave the body standing nowhere, which is
the corrupt scene the whole block exists to prevent. What it never asked is
whether the string is a place at all.

Measured live (chat 95 t55). The Director wrote
`positions: {"Hinami": "prone on Mirelle Sulmirath's palm"}` -- a posture --
and the engine minted a room of that name "with a way back to
private_session_room". From that beat Hinami stood alone in it while Mirelle
stood in the session room. Contacts between bodies in different rooms are
pruned, so every contact between them was dropped for four turns, including
the interior contact of a swallow -- which is what `place_enclosed_bodies`
needs to put a body inside another at all. The `mirelle_mouth` and
`mirelle_esophagus` rooms the Director correctly declared were never
occupied, and both minds were told about two people in two different places.

The test is structural: a real new place is named for itself, and a place
named for somebody is a relation to them. Relations have their own ledgers.
"""
from agents.common import validated_player_state_assertions as _assert_state


def _scene():
    return {
        "rooms": {"private_session_room": {}},
        "positions": {"Hinami": "private_session_room",
                      "Mirelle Sulmirath": "private_session_room"},
        "attire": {"Mirelle Sulmirath": {"wearing": []}},
        "entities": {"wide_bed": {"name": "wide bed", "kind": "object"}},
    }


class TestAPlaceNamedForSomebodyIsNotAPlace:
    def test_a_posture_against_a_body_is_refused(self):
        report = []
        out = _assert_state(
            _scene(), {"positions": {"Hinami": "prone on Mirelle Sulmirath's palm"}},
            "Hinami", report=report.append)
        assert "positions" not in out
        assert "rooms" not in out
        assert any("rather than a place" in line for line in report), report

    def test_the_body_is_left_where_it_was(self):
        """Dropping the position and keeping the mint would point a body at a
        room that was refused, which is worse than either."""
        out = _assert_state(
            _scene(), {"positions": {"Hinami": "held against Mirelle Sulmirath"}},
            "Hinami", report=[].append)
        assert out.get("positions", {}).get("Hinami") is None

    def test_an_object_counts_as_much_as_a_person(self):
        out = _assert_state(
            _scene(), {"positions": {"Hinami": "sprawled across the wide bed"}},
            "Hinami", report=[].append)
        assert "positions" not in out

    def test_one_refusal_does_not_take_the_others_with_it(self):
        out = _assert_state(
            _scene(),
            {"positions": {"Hinami": "on Mirelle Sulmirath's palm",
                           "Mirelle Sulmirath": "balcony"}},
            "Hinami", report=[].append)
        assert out["positions"] == {"Mirelle Sulmirath": "balcony"}
        assert "balcony" in out["rooms"]


class TestARealNewPlaceStillMints:
    def test_an_undeclared_room_is_minted_with_a_way_back(self):
        report = []
        out = _assert_state(
            _scene(), {"positions": {"Hinami": "balcony"}},
            "Hinami", report=report.append)
        assert out["positions"]["Hinami"] == "balcony"
        assert out["rooms"]["balcony"]["adjacent"][0]["to"] == \
            "private_session_room"
        assert any("minted it" in line for line in report)

    def test_a_room_the_beat_declares_is_untouched(self):
        """An interior enters the world through `rooms` with a
        `parent_entity`, which is how `mirelle_esophagus` arrived -- and it is
        named after a body on purpose. Declared rooms never reach the test."""
        out = _assert_state(
            _scene(),
            {"positions": {"Hinami": "mirelle_esophagus"},
             "rooms": {"mirelle_esophagus": {
                 "name": "Mirelle's Esophagus",
                 "parent_entity": "Mirelle Sulmirath"}}},
            "Hinami", report=[].append)
        assert out["positions"]["Hinami"] == "mirelle_esophagus"
        assert out["rooms"]["mirelle_esophagus"]["parent_entity"] == \
            "Mirelle Sulmirath"

    def test_an_existing_room_is_untouched(self):
        out = _assert_state(
            _scene(), {"positions": {"Hinami": "private_session_room"}},
            "Hinami", report=[].append)
        assert out["positions"]["Hinami"] == "private_session_room"
        assert "rooms" not in out
