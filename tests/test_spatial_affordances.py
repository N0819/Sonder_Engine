"""What a character needs in order not to backtrack.

Measured against a live model in tools/maze_experiment.py: standing in a room,
the character's entire spatial payload was

    {"unclassified": [{"room": "Chamber 01", "barrier": "open"},
                      {"room": "Chamber 21", "barrier": "open"}]}

-- exits with no marker separating the one just arrived through from one never
taken, and no name for the room being stood in. Preferring the unexplored exit
was not a choice the payload made available. Both are the character's OWN
history and position, so neither crosses an information boundary.
"""

from __future__ import annotations

import json
import time

from agents.character import _annotate_known_exits


def _scene():
    return {
        "rooms": {
            "r00": {"name": "Chamber 00", "adjacent": []},
            "r01": {"name": "Chamber 01", "adjacent": []},
            "r21": {"name": "Chamber 21", "adjacent": []},
        },
        "positions": {}, "entities": {}, "attire": {}, "overlays": {},
    }


DIGEST = {"unclassified": [{"room": "Chamber 01", "barrier": "open"},
                           {"room": "Chamber 21", "barrier": "open"}]}


class TestKnownExits:
    def test_an_unvisited_exit_is_distinguishable_from_a_visited_one(self):
        out = _annotate_known_exits(DIGEST, _scene(), ["r00", "r01"])
        by_room = {e["room"]: e for e in out["unclassified"]}
        assert by_room["Chamber 01"]["been_there"] is True
        assert by_room["Chamber 21"]["been_there"] is False

    def test_recency_is_ordinal_in_the_characters_own_route(self):
        """'How far back in my own route' is the form a person actually has --
        not a turn index."""
        out = _annotate_known_exits(DIGEST, _scene(), ["r01", "r21", "r00"])
        by_room = {e["room"]: e for e in out["unclassified"]}
        assert by_room["Chamber 21"]["last_seen_beats_ago"] == 2
        assert by_room["Chamber 01"]["last_seen_beats_ago"] == 3

    def test_repeat_entries_are_counted(self):
        out = _annotate_known_exits(DIGEST, _scene(), ["r01", "r00", "r01"])
        by_room = {e["room"]: e for e in out["unclassified"]}
        assert by_room["Chamber 01"]["times_entered"] == 2

    def test_no_route_means_nothing_is_marked_visited(self):
        out = _annotate_known_exits(DIGEST, _scene(), [])
        assert all(not e["been_there"] for e in out["unclassified"])

    def test_it_survives_junk(self):
        assert _annotate_known_exits(None, _scene(), ["r00"]) is None
        out = _annotate_known_exits({"unclassified": ["oops", None]}, _scene(),
                                    ["r00"])
        assert out["unclassified"] == ["oops", None]
        assert _annotate_known_exits({"x": "notalist"}, _scene(), [])["x"] == "notalist"


class TestRouteRecording:
    """commit records the route from the character's committed position."""

    def test_the_cap_is_bounded(self):
        import commit
        assert 0 < commit.VISITED_ROOMS_CAP <= 200


class TestLocationCuedRecall:
    """`location` was stored on every memory row and never read for ranking, so
    'what happened in this room' had no index behind it."""

    def _seed(self, db):
        chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                        ("T", "", time.time()))
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        for turn, loc, text in (
            (1, "Chamber 01", "a hinge shrieked as it swung"),
            (2, "Chamber 21", "a hinge shrieked as it swung"),
        ):
            db.qi(
                "INSERT INTO memories(chat_id,char_id,turn_idx,kind,category,"
                "provenance,salience,content,gist,location) "
                "VALUES(?,?,?,'episodic','episode','witnessed',0.5,?,?,?)",
                (chat_id, char_id, turn, text, text, loc))
        return chat_id, char_id

    def test_being_here_lifts_what_happened_here(self, temp_db):
        from memory import search_memories
        chat_id, char_id = self._seed(temp_db)
        got = search_memories(chat_id, char_id, "a hinge shrieked", k=8,
                              chronological=False, here="Chamber 21")
        top = got[0]
        assert top["location"] == "Chamber 21"
        assert "happened here" in top["retrieval_reasons"]

    def test_it_is_additive_not_a_filter(self, temp_db):
        """Being somewhere makes a memory easier to reach; it must not make
        everything elsewhere unreachable."""
        from memory import search_memories
        chat_id, char_id = self._seed(temp_db)
        got = search_memories(chat_id, char_id, "a hinge shrieked", k=8,
                              chronological=False, here="Chamber 21")
        assert {m["location"] for m in got} == {"Chamber 01", "Chamber 21"}

    def test_no_location_cue_changes_nothing(self, temp_db):
        from memory import search_memories
        chat_id, char_id = self._seed(temp_db)
        got = search_memories(chat_id, char_id, "a hinge shrieked", k=8,
                              chronological=False)
        assert len(got) == 2
        assert all("happened here" not in m["retrieval_reasons"] for m in got)


class TestDestinationIsNotADeadEnd:
    """A tavern is a room you enter and leave by the same door.

    `no_route_onward` is a fact about DOORWAYS -- not a way through -- and must
    never read as a verdict on the place. An earlier name, `led_nowhere`, did:
    it would have told a character the tavern they were heading for was a dead
    end. Somewhere they chose to REMAIN is never marked, because dwelling is
    what going somewhere on purpose looks like, as against passing through and
    finding a wall.
    """

    SCENE = {
        "rooms": {"r1": {"name": "Dead End"}, "r2": {"name": "The Tavern"},
                  "r3": {"name": "Hall"}},
        "positions": {"V": "r3"}, "entities": {},
    }
    DIGEST = {"ahead": [{"room": "Dead End", "barrier": "open"},
                        {"room": "The Tavern", "barrier": "open"}]}

    def _exits(self, route):
        out = _annotate_known_exits(self.DIGEST, self.SCENE, route)
        return {e["room"]: e for e in out["ahead"]}

    def test_a_dead_end_walked_into_twice_is_marked(self):
        got = self._exits(["r3", "r1", "r3", "r1", "r3"])
        assert got["Dead End"]["no_route_onward"] is True

    def test_a_place_he_lingered_in_is_never_marked(self):
        """Entered four times, reversed out every time -- but he STAYED."""
        got = self._exits(["r3", "r2", "r2", "r3", "r2", "r2", "r3"])
        assert "no_route_onward" not in got["The Tavern"]
        assert got["The Tavern"]["been_there"] is True

    def test_one_reversal_is_not_enough(self):
        """Turning back once is as easily a change of mind as a wall, and a
        wrong marker steers him off the real route."""
        got = self._exits(["r3", "r1", "r3"])
        assert "no_route_onward" not in got["Dead End"]
        assert got["Dead End"]["turned_back_here"] == 1

    def test_lingering_is_not_even_a_turn_back(self):
        """Dwelling breaks the A-B-A pattern outright: he did not turn STRAIGHT
        back, he stayed and then left. So a place he settles in registers
        neither the fact nor the inference -- which is the right answer twice
        over."""
        got = self._exits(["r3", "r2", "r2", "r3", "r2", "r2", "r3"])
        assert "turned_back_here" not in got["The Tavern"]
        assert "no_route_onward" not in got["The Tavern"]

    def test_the_fact_is_reported_when_he_really_did_turn_straight_back(self):
        got = self._exits(["r3", "r1", "r3"])
        assert got["Dead End"]["turned_back_here"] == 1

    def test_an_exit_he_passed_through_is_not_marked(self):
        """Onward movement disqualifies it however often he also came back."""
        got = self._exits(["r3", "r1", "r2", "r1", "r3", "r1", "r3"])
        assert "no_route_onward" not in got["Dead End"]
