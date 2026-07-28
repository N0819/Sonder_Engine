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


class TestCorridorSight:
    """A character could see one room and no further, so a corridor ending
    three rooms north was indistinguishable from one running on -- he had to
    walk it. You can see down a straight passage; that you cannot see round the
    corner is what makes it sight rather than a map."""

    def _scene(self, rooms):
        return {"rooms": rooms, "positions": {}, "entities": {},
                "attire": {}, "overlays": {}}

    def _corridor(self, n, terminal_adjacent):
        """A straight north-running passage of `n` rooms from r0."""
        rooms = {}
        for i in range(n):
            adj = []
            if i:
                adj.append({"to": f"r{i-1}", "barrier": "open", "dir": "s"})
            if i + 1 < n:
                adj.append({"to": f"r{i+1}", "barrier": "open", "dir": "n"})
            rooms[f"r{i}"] = {"name": f"Room {i}", "light": "lit", "adjacent": adj}
        rooms[f"r{n-1}"]["adjacent"].extend(terminal_adjacent)
        return rooms

    def test_a_dead_end_is_seen_from_down_the_corridor(self):
        from spatial import corridor_sightlines
        sc = self._scene(self._corridor(4, []))
        line = corridor_sightlines(sc, "r0")[0]
        assert line["terminus"] == "dead_end"
        assert line["distance"] == 3

    def test_distance_is_reported_vaguely(self):
        """'some way north the passage ends', not 'three rooms north'."""
        from spatial import corridor_sightlines
        near = corridor_sightlines(self._scene(self._corridor(2, [])), "r0")[0]
        far = corridor_sightlines(self._scene(self._corridor(5, [])), "r0")[0]
        assert near["vagueness"] == "just ahead"
        assert far["vagueness"] in ("some way", "far")
        assert near["vagueness"] != far["vagueness"]

    def test_sight_stops_at_a_bend(self):
        """The passage turns; what is round the corner is not seen."""
        from spatial import corridor_sightlines
        rooms = self._corridor(3, [{"to": "east1", "barrier": "open", "dir": "e"}])
        rooms["east1"] = {"name": "East", "light": "lit",
                          "adjacent": [{"to": "r2", "barrier": "open", "dir": "w"}]}
        line = corridor_sightlines(self._scene(rooms), "r0")[0]
        assert line["terminus"] == "turn"
        assert line["distance"] < 3

    def test_sight_stops_at_darkness(self):
        from spatial import corridor_sightlines
        rooms = self._corridor(4, [])
        rooms["r2"]["light"] = "dark"
        assert corridor_sightlines(self._scene(rooms), "r0")[0]["terminus"] == "darkness"

    def test_a_junction_reads_as_an_opening_not_an_end(self):
        from spatial import corridor_sightlines
        rooms = self._corridor(3, [
            {"to": "w1", "barrier": "open", "dir": "w"},
            {"to": "e1", "barrier": "open", "dir": "e"}])
        rooms["w1"] = {"name": "W", "light": "lit", "adjacent": []}
        rooms["e1"] = {"name": "E", "light": "lit", "adjacent": []}
        assert corridor_sightlines(self._scene(rooms), "r0")[0]["terminus"] == "opening"

    def test_no_direction_means_no_sightline(self):
        """Without `dir` there is no line to follow, and guessing one would
        invent a sense the character does not have."""
        from spatial import corridor_sightlines
        rooms = self._corridor(3, [])
        for r in rooms.values():
            for e in r["adjacent"]:
                e.pop("dir")
        assert corridor_sightlines(self._scene(rooms), "r0") == []

    def test_detail_decays_with_distance(self):
        """The near chamber is read plainly, the next by its one memorable
        feature, past that only that the passage runs on. Both what sight does
        and what keeps this from being a page of prose every beat."""
        from spatial import corridor_sightlines, _CORRIDOR_NAMED
        line = corridor_sightlines(self._scene(self._corridor(5, [])), "r0")[0]
        along = line["along"]
        assert len(along) == _CORRIDOR_NAMED, "far rooms must not be named"
        assert along[0]["detail"] == "clear"
        assert along[1]["detail"] == "landmark"

    def test_the_payload_stays_small(self):
        """Four directions of graded sight must not rival the view itself."""
        import json
        from spatial import corridor_sightlines
        rooms = self._corridor(6, [])
        blob = json.dumps(corridor_sightlines(self._scene(rooms), "r0"))
        assert len(blob) < 600, f"sightline payload grew to {len(blob)} chars"

    def test_a_distant_room_is_named_so_it_can_be_recognised(self):
        """The real payoff: matching a landmark two rooms off against memory,
        without walking there."""
        from spatial import corridor_sightlines
        line = corridor_sightlines(self._scene(self._corridor(4, [])), "r0")[0]
        assert [a["room"] for a in line["along"]] == ["Room 1", "Room 2"]


class TestOnwardBearings:
    """A count is read as a promise to carry on the way you face.

    Observed live in the 12x12 maze harness: given `onward_exits: 1` for the
    chamber to his west, the runner formed the belief "further WESTWARD exit
    that can now be taken as continuation" at 0.78 confidence and walked west
    into it on four separate beats. The chamber's one other way out went
    north. He was not reasoning badly -- he was handed a number where the
    thing he needed was a bearing.
    """

    def _scene(self, rooms):
        return {"rooms": rooms, "positions": {}, "entities": {},
                "attire": {}, "overlays": {}}

    def _elbow(self):
        """here --east--> corner, whose only other way out runs north."""
        return self._scene({
            "here": {"name": "Here", "light": "lit", "desc": "Here.",
                     "adjacent": [
                {"to": "corner", "barrier": "open", "dir": "e"}]},
            "corner": {"name": "Corner", "light": "lit", "desc": "A corner.",
                       "adjacent": [
                {"to": "here", "barrier": "open", "dir": "w"},
                {"to": "north", "barrier": "open", "dir": "n"}]},
            "north": {"name": "North", "light": "lit", "desc": "North.",
                      "adjacent": [
                {"to": "corner", "barrier": "open", "dir": "s"}]},
        })

    def test_the_way_on_is_named_not_merely_counted(self):
        from spatial import visible_adjacent_rooms
        seen = {r["room_id"]: r for r in visible_adjacent_rooms(
            self._elbow(), "here")}
        assert seen["corner"]["onward_exits"] == 1
        assert seen["corner"]["onward_bearings"] == ["n"], (
            "one way on, and it is north -- not a continuation eastward")

    def test_the_way_back_is_never_offered_as_a_way_on(self):
        from spatial import visible_adjacent_rooms
        seen = {r["room_id"]: r for r in visible_adjacent_rooms(
            self._elbow(), "here")}
        assert "w" not in seen["corner"]["onward_bearings"]

    def test_a_visible_dead_end_names_no_bearing_at_all(self):
        from spatial import visible_adjacent_rooms
        sc = self._scene({
            "here": {"name": "Here", "light": "lit", "desc": "Here.",
                     "adjacent": [
                {"to": "pocket", "barrier": "open", "dir": "e"}]},
            "pocket": {"name": "Pocket", "light": "lit", "desc": "A pocket.",
                       "adjacent": [
                {"to": "here", "barrier": "open", "dir": "w"}]},
        })
        seen = {r["room_id"]: r for r in visible_adjacent_rooms(sc, "here")}
        assert seen["pocket"]["onward_exits"] == 0
        assert "onward_bearings" not in seen["pocket"]

    def test_a_scene_without_directions_invents_none(self):
        """No `dir` on the edges means no bearings to give. Guessing one
        would be inventing a sense the character does not have."""
        from spatial import visible_adjacent_rooms
        sc = self._scene({
            "here": {"name": "Here", "light": "lit", "desc": "Here.",
                     "adjacent": [{"to": "corner", "barrier": "open"}]},
            "corner": {"name": "Corner", "light": "lit", "desc": "A corner.",
                       "adjacent": [
                {"to": "here", "barrier": "open"},
                {"to": "far", "barrier": "open"}]},
            "far": {"name": "Far", "light": "lit", "desc": "Far.",
                    "adjacent": [{"to": "corner", "barrier": "open"}]},
        })
        seen = {r["room_id"]: r for r in visible_adjacent_rooms(sc, "here")}
        assert seen["corner"]["onward_exits"] == 1
        assert "onward_bearings" not in seen["corner"]

    def test_gloom_reports_nothing_not_even_a_count(self):
        """Bearings must not become a back door round the light gate -- and
        the gate is FULL sight, not merely some sight. Light spilling through
        the doorway makes a dark chamber read `dim`, which carries bulk and
        movement and cannot possibly carry which wall a doorway is in.
        `corridor_sightlines` already refuses to read a terminus through
        gloom; these two must not disagree."""
        from spatial import effective_light, visible_adjacent_rooms
        sc = self._elbow()
        sc["rooms"]["corner"]["light"] = "dark"
        assert effective_light(sc, "corner") == "dim", "spill, not blackness"
        seen = {r["room_id"]: r for r in visible_adjacent_rooms(sc, "here")}
        assert "onward_exits" not in seen["corner"]
        assert "onward_bearings" not in seen["corner"]

    def test_a_reverse_declared_neighbour_is_not_permanently_opaque(self):
        """Sight does not care which room declared the edge. While it did,
        a visibly closed chamber reachable only by a reverse-declared edge
        reported nothing -- and absent reads as 'cannot tell', so it had to
        be walked into to be ruled out."""
        from spatial import visible_adjacent_rooms
        sc = self._scene({
            "here": {"name": "Here", "light": "lit", "desc": "Here.",
                     "adjacent": []},
            "pocket": {"name": "Pocket", "light": "lit", "desc": "A pocket.",
                       "adjacent": [
                {"to": "here", "barrier": "open", "dir": "w"}]},
        })
        seen = {r["room_id"]: r for r in visible_adjacent_rooms(sc, "here")}
        assert seen["pocket"]["onward_exits"] == 0
        assert "onward_bearings" not in seen["pocket"]

    def test_the_bearing_reaches_the_characters_exit_marker(self):
        """The datum is useless if it stops at spatial.py."""
        from agents.character import _annotate_known_exits
        marked = _annotate_known_exits(
            {"ahead": [{"room": "Corner", "barrier": "open"}]},
            self._elbow(), [], known_exits={}, here_rid="here")
        entry = marked["ahead"][0]
        assert entry["onward_exits_visible"] == 1
        assert entry["onward_bearings"] == ["n"]


class TestNavigationMarkersAreDocumented:
    """Every marker the character is handed must be explained to it.

    `spatial_frame` shipped SEVEN markers -- onward_exits_visible,
    visibly_no_way_through, been_there, times_entered, no_route_onward,
    no_new_ground_that_way, worked_before -- with not one of them mentioned
    anywhere in the character prompt. Their meanings were being inferred from
    their key names, which is how a bare count sitting on an egocentric
    bucket became a compass heading and sent a maze runner west into a wall
    on four separate beats.

    The character payload is 21 top-level keys deep, so adding a field to it
    has no natural back-pressure: it feels free, and the cost surfaces
    hundreds of beats later as a character confabulating what it meant. This
    test is that back-pressure.
    """

    def test_every_marker_is_explained_in_the_character_prompt(self):
        import re
        from prompts import DEFAULT_PROMPTS
        src = open("agents/character.py", encoding="utf-8").read()
        # The keys _annotate_known_exits actually writes onto an exit.
        emitted = set(re.findall(r'entry\["([a-z_]+)"\]', src))
        assert emitted, "found no markers -- has the annotator been renamed?"
        prompt = DEFAULT_PROMPTS["character"]
        missing = sorted(k for k in emitted if k not in prompt)
        assert not missing, (
            "spatial_frame markers handed to the character with no "
            f"explanation in its prompt: {missing}. A marker whose meaning "
            "has to be guessed from its key name is worse than no marker, "
            "because the guess is confident. Document it in the SPATIAL "
            "FRAME section of DEFAULT_PROMPTS['character'].")

    def test_absent_means_cannot_tell_is_stated(self):
        """The single most dangerous misreading: absent as 'none'. Every
        one of these keys is omitted when it cannot be determined, and a
        character that reads omission as a clear way will walk into things."""
        from prompts import DEFAULT_PROMPTS
        prompt = DEFAULT_PROMPTS["character"].upper()
        assert "CANNOT TELL" in prompt or "COULD NOT TELL" in prompt


class TestCirclingIsVisible:
    """A lifetime tally cannot tell a thoroughfare from a loop.

    Observed live on a second attempt at the same maze: the character locked
    into a period-four cycle, 0001 -> 0002 -> 0001 -> 0000, three times
    exactly. He was not blind to the way out -- he GENERATED "south into
    0100", real new ground, as a candidate and rejected it with
    `norm_conflict: conflicts with association that east from blue-tile reset
    leads toward 0507`. A route learned on the previous run outranked the
    evidence in front of him, and nothing in the payload said that route had
    just failed three times running.
    """

    SCENE = {"rooms": {"rA": {"name": "A"}, "rB": {"name": "B"},
                       "rC": {"name": "C"}, "rZ": {"name": "Z"}},
             "positions": {}, "entities": {}}
    DIGEST = {"ahead": [{"room": "A", "barrier": "open"},
                        {"room": "Z", "barrier": "open"}]}

    def _exits(self, route):
        from agents.character import _annotate_known_exits
        out = _annotate_known_exits(self.DIGEST, self.SCENE, route)
        return {e["room"]: e for e in out["ahead"]}

    def test_a_tight_cycle_is_reported_as_circling(self):
        from agents.character import LOOP_WINDOW
        route = ["rA", "rB", "rC"] * 6          # 18 beats, 3 rooms
        got = self._exits(route)
        assert got["A"]["circling_here"] is True
        assert got["A"]["entered_recently"] >= 2
        assert got["A"]["entered_recently"] < len(route), (
            "recent must be a window, not the lifetime tally")
        # `times_entered` is deliberately dropped once circling is set: it,
        # turned_back_here and last_seen_beats_ago all say the same thing as
        # the verdict, and together they outweighed the untried door beside
        # them. The verdict carries the count now.
        assert "times_entered" not in got["A"]
        assert got["A"]["verdict"].startswith("circling")
        assert len(route[-LOOP_WINDOW:]) == LOOP_WINDOW

    def test_an_untrodden_exit_is_never_marked(self):
        """The way OUT of the loop must not be tarred with it."""
        got = self._exits(["rA", "rB", "rC"] * 6)
        assert "circling_here" not in got["Z"]
        assert "entered_recently" not in got["Z"]
        assert got["Z"]["been_there"] is False

    def test_a_long_wander_is_not_circling(self):
        """A signal that fires on everything argues against the right move as
        loudly as the wrong one, which is worse than no signal."""
        route = [f"r{i:02d}" for i in range(30)] + ["rA"]
        got = self._exits(route)
        assert "circling_here" not in got["A"]

    def test_a_busy_hub_crossed_twice_is_not_a_lock(self):
        """Passing back through a junction is ordinary. Only a nearly-full
        window confined to a handful of rooms counts."""
        route = ["rA", "r1", "r2", "r3", "rA", "r4", "r5", "r6",
                 "r7", "r8", "r9", "r10"]
        got = self._exits(route)
        assert "circling_here" not in got["A"]
        assert got["A"]["entered_recently"] == 2

    def test_recent_never_exceeds_the_lifetime_count(self):
        """On an exit with no discouraging verdict both numbers survive, and
        the window can never exceed the whole route."""
        route = ["rA", "rB", "rC", "rD", "rE", "rF", "rG", "rA"]
        got = self._exits(route)
        assert got["A"]["entered_recently"] <= got["A"]["times_entered"]


class TestLoopDensityNotRoomCount:
    """The threshold is a ratio because a fixed count missed the real thing.

    A lock observed live started as three rooms and widened to five as he
    wandered a little further each cycle -- 0001/0002/0001/0000 became
    0001/0002/0003/0102/0000. A count of four would have stopped reporting
    exactly as it got worse. Five rooms over twelve beats is every room
    walked twice over, which is no less stuck than three.
    """

    SCENE = {"rooms": {f"r{i}": {"name": f"R{i}"} for i in range(30)},
             "positions": {}, "entities": {}}

    def _exits(self, route, room="R0"):
        from agents.character import _annotate_known_exits
        out = _annotate_known_exits(
            {"ahead": [{"room": room, "barrier": "open"}]}, self.SCENE, route)
        return out["ahead"][0]

    def test_the_widened_five_room_lock_is_still_caught(self):
        """The observed A7 tail: he wandered one room further each cycle and
        came straight back, so the pocket grew while the progress did not.
        It ends on a REVISIT, which is what being in a loop looks like -- a
        route ending on new ground is a route leaving one."""
        route = (["r0", "r1", "r2", "r1"] * 2) + ["r0", "r1", "r3", "r1"]
        assert len(set(route[-12:])) == 4
        assert self._exits(route).get("circling_here") is True

    def test_covering_ground_never_trips_it(self):
        """Ratio near 1.0 -- the shape of actually going somewhere."""
        route = [f"r{i}" for i in range(20)]
        assert "circling_here" not in self._exits(route + ["r0"], "R0")

    def test_half_the_window_is_the_boundary(self):
        from agents.character import LOOP_WINDOW, LOOP_DENSITY
        # exactly half -- each room twice -- counts as stuck
        route = [f"r{i}" for i in range(LOOP_WINDOW // 2)] * 2
        assert len(set(route[-LOOP_WINDOW:])) == LOOP_DENSITY * LOOP_WINDOW
        assert self._exits(route, "R0").get("circling_here") is True


class TestCorridorPacingIsCaught:
    """Counting distinct rooms in a window measures the wrong thing.

    Twice now the detector went quiet as the loop got WORSE. A fixed
    four-room threshold missed a lock that widened to five. The ratio that
    replaced it went silent on a seven-room corridor walked end to end --
    0001/0101/0201/0202/0203/0204/0104, ten beats, not one room he had not
    already seen -- because an out-and-back fills the window with distinct
    rooms while arriving nowhere.

    What a lost person actually notices is that nothing has been new for a
    while, so that is what is measured.
    """

    SCENE = {"rooms": {f"r{i}": {"name": f"R{i}"} for i in range(40)},
             "positions": {}, "entities": {}}

    def _frame(self, route, room="R0"):
        from agents.character import _annotate_known_exits
        return _annotate_known_exits(
            {"ahead": [{"room": room, "barrier": "open"}]}, self.SCENE, route)

    def test_the_seven_room_corridor_that_defeated_the_ratio(self):
        corridor = ["r0", "r1", "r2", "r3", "r4", "r5", "r6"]
        route = corridor + (corridor[::-1] + corridor) * 2
        assert len(set(route[-12:])) == 7, "the shape that went undetected"
        f = self._frame(route)
        assert f["ahead"][0].get("circling_here") is True
        assert f["beats_since_new_ground"] >= 12

    def test_the_count_says_how_long(self):
        route = ["r0", "r1", "r2"] + ["r1", "r2"] * 5
        f = self._frame(route, "R1")
        assert f["beats_since_new_ground"] == len(route) - 3

    def test_finding_somewhere_new_resets_it(self):
        """Discovery is the thing being measured, so discovery clears it."""
        route = ["r0", "r1"] * 8 + ["r9"]
        f = self._frame(route, "R1")
        assert "beats_since_new_ground" not in f
        assert "circling_here" not in f["ahead"][0]

    def test_steady_exploration_never_reports_it(self):
        f = self._frame([f"r{i}" for i in range(25)], "R0")
        assert "beats_since_new_ground" not in f
        assert "circling_here" not in f["ahead"][0]

    def test_a_couple_of_retraced_steps_is_not_being_lost(self):
        """Ordinary movement, and a signal that fires on it is noise."""
        route = [f"r{i}" for i in range(20)] + ["r18", "r19"]
        f = self._frame(route, "R18")
        assert "beats_since_new_ground" not in f


class TestTheRightDoorIsNotTheLightestEntry:
    """We annotated the doors he should not take and left the one he should
    take nearly bare.

    Measured at the exact beat a character failed to take it: the right door
    carried 3 keys and 64 characters -- `been_there: false` among them --
    while the door he kept taking carried 8 keys and 179. Every good thing
    about the correct answer was the ABSENCE of something, making it the
    lightest item in the payload, and it was chosen against nineteen beats
    running while the payload said `circling_here` and
    `beats_since_new_ground: 19`.

    Salience follows weight. Ours pointed the wrong way.
    """

    SCENE = {"rooms": {"rHere": {"name": "Here"}, "rLoop": {"name": "Loop"},
                       "rNew": {"name": "New"}},
             "positions": {}, "entities": {}}
    DIGEST = {"ahead": [{"room": "Loop", "barrier": "open"},
                        {"room": "New", "barrier": "open"}]}

    def _frame(self):
        from agents.character import _annotate_known_exits
        route = ["rHere", "rLoop"] * 8
        return _annotate_known_exits(self.DIGEST, self.SCENE, route)

    def test_the_untried_door_comes_first(self):
        """Position is salience and it costs nothing."""
        assert [e["room"] for e in self._frame()["ahead"]] == ["New", "Loop"]

    def test_the_frontier_is_marked_positively(self):
        new = self._frame()["ahead"][0]
        assert new["untried"] is True
        assert new["verdict"].startswith("UNTRIED")

    def test_the_untried_door_is_no_longer_the_lightest_entry(self):
        import json
        by = {e["room"]: e for e in self._frame()["ahead"]}
        new, loop = json.dumps(by["New"]), json.dumps(by["Loop"])
        assert len(new) > 100, "the right answer must not be a bare negative"
        assert len(new) > len(loop) * 0.6, (
            f"untried {len(new)} chars vs looping {len(loop)} -- the gap was "
            "2.8x the wrong way when this was found")

    def test_the_redundant_counters_are_gone_from_a_looping_exit(self):
        loop = {e["room"]: e for e in self._frame()["ahead"]}["Loop"]
        for redundant in ("times_entered", "turned_back_here",
                          "last_seen_beats_ago"):
            assert redundant not in loop
        assert "entered_recently" in loop, "the informative one stays"

    def test_the_evidence_survives_under_the_verdict(self):
        """A reading, not a replacement -- a model may disagree with it, and
        needs what the reading was made from in order to."""
        loop = {e["room"]: e for e in self._frame()["ahead"]}["Loop"]
        assert loop["been_there"] is True
        assert loop["circling_here"] is True

    def test_proven_does_not_outrank_untried(self):
        """Choosing between a way that worked and a way not yet tried is what
        curiosity is FOR; ordering must not quietly settle it."""
        from agents.character import _annotate_known_exits
        got = _annotate_known_exits(
            self.DIGEST, self.SCENE, ["rHere", "rLoop"],
            routes_that_worked={"rLoop": 3})
        rooms = [e["room"] for e in got["ahead"]]
        assert rooms == ["New", "Loop"]
        assert got["ahead"][1]["verdict"].startswith("proven")
