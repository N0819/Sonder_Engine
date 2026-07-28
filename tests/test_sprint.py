"""Running: more than one room in a beat, bounded by DECISION, not sight.

A character could only ever move one room per beat, which makes a courier
whose whole craft is speed indistinguishable from someone strolling and turns
distance into a queue of identical beats.

The rule here CHANGED, and these tests record why. The first version bounded
a run by sight -- it stopped at every bend, on the reasoning that you cannot
see round a corner. Measured against the live 7x7 maze that reasoning was
worth almost nothing: 39 of 49 rooms are two-exit corridor cells and a
corridor cell is usually a bend, so 72 of 96 runnable passages offered
exactly one room (mean 1.3) and SPRINT_BUDGET never once bound. Winding is
what makes a maze a maze; a sight-bounded run cannot exist in one. The thing
sight was standing in for was never the corner -- a body enters an unseen
room every time it walks through a doorway -- it was not CHOOSING blind, and
a bend offers no choice. Decision-bounded (follow while there is exactly one
passable way onward, bends allowed; stop at a junction, a dead end, darkness,
a shut door, or the budget) the same maze offers a mean of 2.48 rooms and
the budget binds 64 times.

The firewall moved with the rule instead of dissolving: the RUN may cross
ground the runner has not seen (they perceive it by being in it), but the
OFFER may not describe such ground. `known_rooms` gates the character-facing
view to the straight sightline plus rooms they have themselves been in;
objective callers (the Director's resolve ceiling) pass nothing and see the
scene as it is.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spatial import SPRINT_BUDGET, sprint_reach


def _room(name, adjacent, **kw):
    return {"name": name, "desc": name, "adjacent": adjacent, **kw}


def _e(to, direction, barrier="open"):
    return {"to": to, "dir": direction, "barrier": barrier}


def _scene(rooms):
    return {"rooms": rooms, "positions": {}, "entities": {}, "attire": {},
            "overlays": {}}


def _corridor(n=6, **room_kw):
    """A straight run of n rooms east from `start`."""
    rooms = {"start": _room("Start", [_e("c1", "e")])}
    for i in range(1, n + 1):
        adj = [_e("start" if i == 1 else f"c{i-1}", "w")]
        if i < n:
            adj.append(_e(f"c{i+1}", "e"))
        rooms[f"c{i}"] = _room(f"C{i}", adj, **room_kw)
    return _scene(rooms)


def _one(reach, bearing="e"):
    return next((r for r in reach if r["bearing"] == bearing), None)


def test_a_run_covers_several_rooms():
    run = _one(sprint_reach(_corridor(), "start"))
    assert run and run["rooms"] == SPRINT_BUDGET
    assert run["path"] == ["c1", "c2", "c3"]
    assert run["stops"] == "full_reach"


def test_the_budget_stop_names_distance_not_physiology():
    """The stop value was `winded` first, and the word beat its own
    documentation -- the third label in this engine to do so (`closed` read
    as "no way through", `spent` read as "do not go"). Observed verbatim in
    A12: "he would be winded? But he might not want to be winded if he
    needs to assess contents" -- the best offer a run can get, the passage
    outlasting the beat, read as a penalty for taking it. A marginal
    deterrent, not an absolute one -- the same arm took one such run in
    full and reasoned against later ones -- which is how a mislabel does
    its damage: it tips close decisions. And the penalty
    reading was false as a distinguishing fact: EVERY hard run arrives
    winded (the Director applies that cost whatever ends the run), so the
    label implied a consequence specific to maximal runs that is not.
    The stop reason names why the run ENDED; what running COSTS belongs to
    the Director, and the two must not share a word. A footnote cannot
    beat a word's plain meaning; the fix that works is changing the word."""
    run = _one(sprint_reach(_corridor(), "start"))
    assert run["stops"] == "full_reach"
    assert "winded" not in str(run)


def test_the_path_is_every_room_crossed_not_just_the_destination():
    """A body that runs through three chambers has been in three chambers.
    Recording only where they stopped would leave holes in their map exactly
    where their feet went -- and the place graph builds walked edges from
    this, so the holes would be permanent."""
    run = _one(sprint_reach(_corridor(), "start"))
    assert run["path"][-1] == "c3", "path must END at the room they stop in"
    assert len(run["path"]) == run["rooms"]
    assert len(set(run["path"])) == len(run["path"]), "no room twice"


def test_a_big_room_eats_more_of_the_run():
    """Distance, not room count. Crossing a hall is not one stride."""
    small = _one(sprint_reach(_corridor(), "start"))
    large = _one(sprint_reach(_corridor(size="large"), "start"))
    assert large["rooms"] < small["rooms"]
    vast = _one(sprint_reach(_corridor(size="vast"), "start"))
    assert vast["rooms"] == 1, "a vast hall is the whole beat"


def test_a_bend_does_not_stop_the_run():
    """The rule this file exists to pin, in the direction it broke.

    The first rule stopped every run at a bend ('you cannot see round a
    corner'), and in the live 7x7 maze that reduced the feature to noise: 72
    of 96 passages offered exactly one room, a courier read offer after offer
    as 'only 1 room, walking is fine', and in 152 turns not one multi-room
    move happened. Following a corridor round a bend is not a CHOICE -- there
    is one way on and you take it -- so the run carries through and `stops`
    is reserved for things that genuinely end one: a decision, the world, or
    the body."""
    sc = _scene({
        "start": _room("Start", [_e("c1", "e")]),
        "c1": _room("C1", [_e("start", "w"), _e("c2", "n")]),
        "c2": _room("C2", [_e("c1", "s")]),
    })
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1", "c2"], "the run must carry round the bend"
    assert run["stops"] == "dead_end"


def test_it_stops_at_a_junction():
    """A junction is a decision and a decision is a beat. Running blind
    through one would be choosing without looking -- this is the bound that
    SURVIVED the sight-to-decision rewrite, and the reason it survived is
    that it was the thing sight was standing in for all along."""
    sc = _scene({
        "start": _room("Start", [_e("c1", "e")]),
        "c1": _room("C1", [_e("start", "w"), _e("c2", "e"), _e("c3", "n")]),
        "c2": _room("C2", [_e("c1", "w")]),
        "c3": _room("C3", [_e("c1", "s")]),
    })
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1"] and run["stops"] == "junction"


def test_a_see_through_side_opening_is_not_a_junction():
    """A junction is a choice of ROUTE. A barred side opening offers no
    route, so it forces no decision and must not end the run -- counting it
    would resurrect the old sight-bound rule one window at a time."""
    sc = _scene({
        "start": _room("Start", [_e("c1", "e")]),
        "c1": _room("C1", [_e("start", "w"), _e("c2", "e"),
                           _e("c3", "n", barrier="bars")]),
        "c2": _room("C2", [_e("c1", "w")]),
        "c3": _room("C3", [_e("c1", "s", barrier="bars")]),
    })
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1", "c2"], "bars are not a fork in the road"
    assert run["stops"] == "dead_end"


def test_it_stops_at_the_dark():
    """Running into a room you cannot see into is how a body breaks an ankle,
    and it is also how a character would learn a room they never saw."""
    sc = _corridor(4)
    sc["rooms"]["c2"]["light"] = "dark"
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1"]
    assert run["stops"] == "darkness"


def test_you_cannot_run_through_glass():
    """The sightline follows any see-through barrier; a run follows only
    passable ones. You can see through bars and you cannot run through them."""
    sc = _scene({
        "start": _room("Start", [_e("c1", "e", barrier="bars")]),
        "c1": _room("C1", [_e("start", "w")]),
    })
    assert sprint_reach(sc, "start") == []

    sc2 = _corridor(4)
    sc2["rooms"]["c1"]["adjacent"][1]["barrier"] = "window"
    run = _one(sprint_reach(sc2, "start"))
    assert run["path"] == ["c1"] and run["stops"] == "door"


def test_a_closed_door_ends_the_run_rather_than_opening_itself():
    sc = _corridor(4)
    sc["rooms"]["c1"]["adjacent"][1]["barrier"] = "closed_door"
    run = _one(sprint_reach(sc, "start"))
    assert run["path"] == ["c1"] and run["stops"] == "door"


def test_a_dead_end_is_reported_as_one():
    run = _one(sprint_reach(_corridor(2), "start"))
    assert run["path"] == ["c1", "c2"] and run["stops"] == "dead_end"


def test_a_scene_without_directions_offers_no_runs():
    """No `dir` means no line to follow, and inventing one would invent a
    sense -- the same rule corridor_sightlines keeps."""
    sc = _scene({
        "start": _room("Start", [{"to": "c1", "barrier": "open"}]),
        "c1": _room("C1", [{"to": "start", "barrier": "open"}]),
    })
    assert sprint_reach(sc, "start") == []


def test_junk_does_not_crash_it():
    assert sprint_reach({}, "nowhere") == []
    assert sprint_reach(None, "start") == []
    assert sprint_reach(_scene({"start": _room("S", ["junk", None])}),
                        "start") == []
    # An edge naming a room that is not in the scene stops the run, and does
    # not put a phantom room in the path.
    sc = _scene({"start": _room("Start", [_e("gone", "e")])})
    assert sprint_reach(sc, "start") == []


def test_every_passage_out_gets_its_own_answer():
    sc = _scene({
        "start": _room("Start", [_e("e1", "e"), _e("w1", "w")]),
        "e1": _room("E1", [_e("start", "w")]),
        "w1": _room("W1", [_e("start", "e")]),
    })
    reach = sprint_reach(sc, "start")
    assert {r["bearing"] for r in reach} == {"e", "w"}


def _bent_corridor():
    """start -e-> c1 -n-> c2 -n-> c3, one bend, then straight, then a dead
    end. From `start` the sightline covers c1 only; c2 and c3 lie round the
    bend."""
    return _scene({
        "start": _room("Start", [_e("c1", "e")]),
        "c1": _room("C1", [_e("start", "w"), _e("c2", "n")]),
        "c2": _room("C2", [_e("c1", "s"), _e("c3", "n")]),
        "c3": _room("C3", [_e("c2", "s")]),
    })


class TestTheOfferIsGatedByKnowledge:
    """The run may cross unseen ground; the OFFER may not describe it.

    Decision-bounded reach handed raw to a character reports the winding
    geometry of passages they never walked -- a mind standing still would
    learn that the corridor bends, runs two more rooms, and ends at a
    junction. That is unearned map smuggled in as an affordance: exactly the
    structured-representation leak the perception layer exists to prevent
    (a second representation must never expand the information budget). So
    the character-facing view extends only through the straight sightline
    plus rooms the character has been in, and truncates with `unknown`
    where its warrant runs out.
    """

    def test_unwalked_ground_past_a_bend_is_not_reported(self):
        run = _one(sprint_reach(_bent_corridor(), "start", known_rooms=()))
        assert run["path"] == ["c1"], (
            "the offer described rooms round a bend the character has "
            "never walked -- that is map they did not earn")
        assert run["stops"] == "unknown"

    def test_remembered_ground_extends_the_offer(self):
        """Having walked the corridor IS the warrant. The same body's reach
        grows as it learns the ground, which is what is true of runners."""
        run = _one(sprint_reach(_bent_corridor(), "start",
                                known_rooms={"c2", "c3"}))
        assert run["path"] == ["c1", "c2", "c3"]
        assert run["stops"] == "dead_end"

    def test_the_straight_sightline_needs_no_memory(self):
        """Looking down a straight passage is ordinary sight -- the same
        warrant corridor_sightlines runs on -- so a never-walked straight
        corridor is still runnable to the budget."""
        run = _one(sprint_reach(_corridor(), "start", known_rooms=()))
        assert run["rooms"] == SPRINT_BUDGET
        assert run["stops"] == "full_reach"

    def test_the_warrant_must_cover_every_room_past_the_bend(self):
        """Memory of the room round the bend does not vouch for the one
        after it: each beyond-sight room needs its own warrant, or one
        remembered room becomes a periscope."""
        run = _one(sprint_reach(_bent_corridor(), "start",
                                known_rooms={"c2"}))
        assert run["path"] == ["c1", "c2"]
        assert run["stops"] == "unknown"

    def test_a_resumed_heading_is_still_past_the_bend(self):
        """Sight ends at the FIRST bend for good. A passage that bends and
        then resumes the original heading is not thereby visible again, and
        treating it so would leak the room beyond a dogleg."""
        sc = _scene({
            "start": _room("Start", [_e("c1", "e")]),
            "c1": _room("C1", [_e("start", "w"), _e("c2", "n")]),
            "c2": _room("C2", [_e("c1", "s"), _e("c3", "e")]),
            "c3": _room("C3", [_e("c2", "w")]),
        })
        run = _one(sprint_reach(sc, "start", known_rooms={"c2"}))
        assert run["path"] == ["c1", "c2"]
        assert run["stops"] == "unknown"

    def test_the_objective_view_is_ungated(self):
        """known_rooms=None is the Director's resolve ceiling: it owns
        objective causality and must see the scene as it is, or a declared
        open-ended run could not resolve past the runner's own knowledge."""
        run = _one(sprint_reach(_bent_corridor(), "start"))
        assert run["path"] == ["c1", "c2", "c3"]
        assert run["stops"] == "dead_end"


class TestOffersHandedToACharacter:
    """The payload edge: sprint_offers = knowledge gate + a worth floor.

    Measured live (A11): 72 of 96 passages offered exactly one room, the
    character read offer after offer as 'only 1 room, walking is fine', and
    never ran at all. A 1-room 'run' is a step with a different verb -- an
    adjacent visible room needs no affordance entry to be sprinted into --
    so entries below two rooms are noise that teaches runs are trivial,
    and they are dropped.
    """

    def test_one_room_offers_are_dropped(self):
        from agents.character import sprint_offers
        sc = _scene({
            "start": _room("Start", [_e("e1", "e"), _e("w1", "w")]),
            "e1": _room("E1", [_e("start", "w"), _e("e2", "e")]),
            "e2": _room("E2", [_e("e1", "w")]),
            "w1": _room("W1", [_e("start", "e")]),
        })
        offers = sprint_offers(sc, "start", {})
        assert [o["bearing"] for o in offers] == ["e"], (
            "the 1-room western 'run' is a step wearing a verb")
        assert offers[0]["rooms"] == 2

    def test_the_gate_reads_the_durable_place_graph_not_just_the_window(self):
        """visited_rooms is a bounded RECENCY window; durable been-there
        knowledge lives in place_graph nodes (the same union commit.py uses
        for remembered ground). Gating on the window alone would make a
        courier forget how to run his oldest corridors."""
        from agents.character import sprint_offers
        sc = _bent_corridor()
        walked_long_ago = {"place_graph": {"nodes": {"c2": {}, "c3": {}},
                                           "edges": {}},
                           "visited_rooms": []}
        offers = sprint_offers(sc, "start", walked_long_ago)
        assert offers and offers[0]["rooms"] == 3
        assert offers[0]["run_ends_at"] == "C3"

    def test_the_offer_is_a_whole_run_with_nothing_to_split(self):
        """Structural fix for a measured failure: the first offer shape
        listed `path`, and the smallest-plausible directive did to it what a
        minimizer does to a divisible quantity -- the character took the
        first room off the list and declared a 1-room "run" ("the smallest
        plausible next behavior might be just the first step"). Prompt text
        arguing the whole reach was one behaviour was read and lost, twice.
        So the offer names where the run ENDS and nothing along the way:
        declaring less than the reach now requires inventing a stop the
        offer never mentioned. The Director's objective sprint_reach keeps
        the full path for resolution and commit."""
        from agents.character import sprint_offers
        sc = _bent_corridor()
        offers = sprint_offers(sc, "start",
                               {"visited_rooms": ["c2", "c3"]})
        assert offers, "the gated bent corridor is runnable end to end"
        offer = offers[0]
        assert "path" not in offer, (
            "a listed path is an invitation to split the run at its first "
            "room -- the offer must present a whole run or nothing")
        assert offer["run_ends_at"] == "C3"
        assert set(offer) == {"bearing", "run_ends_at", "rooms", "stops"}

    def test_a_fresh_character_is_not_handed_the_maze(self):
        from agents.character import sprint_offers
        offers = sprint_offers(_bent_corridor(), "start", {})
        assert offers == [], (
            "an unwalked bent corridor must offer nothing: past the bend "
            "is unearned map, and the room before it is a mere step")


class TestRunningIsRemembered:
    """The rooms crossed at a run must land in memory, or the map gets holes
    exactly where the feet went -- and worse than holes: the place graph mints
    walked edges from adjacent steps, so a corridor sprinted end to end would
    keep reading as untrodden and pull him back down it."""

    def _sc(self):
        return _corridor(4)

    def test_the_rooms_run_through_are_recorded(self):
        from commit import record_spatial_experience
        sc = self._sc()
        st = {}
        record_spatial_experience(st, sc, "start", 1)
        record_spatial_experience(st, sc, "c3", 2)      # ran three rooms
        assert st["visited_rooms"] == ["start", "c1", "c2", "c3"]

    def test_the_walked_edges_span_the_whole_run(self):
        from commit import record_spatial_experience
        sc = self._sc()
        st = {}
        record_spatial_experience(st, sc, "start", 1)
        record_spatial_experience(st, sc, "c3", 2)
        edges = st["place_graph"]["edges"]
        assert edges.get("c2", {}).get("c3", {}).get("taken") is True, (
            "the last leg of the run must read as walked")

    def test_a_teleport_still_mints_nothing(self):
        """No passable route means carried, teleported, or shipped. A
        character learns a place by being carried through it about as well as
        a parcel does."""
        from commit import record_spatial_experience
        sc = _scene({
            "here": _room("Here", []),
            "far": _room("Far", []),
        })
        st = {}
        record_spatial_experience(st, sc, "here", 1)
        record_spatial_experience(st, sc, "far", 2)
        assert st["visited_rooms"] == ["here", "far"], "no invented rooms"
        assert not (st["place_graph"]["edges"].get("here") or {}).get("far")

    def test_an_ordinary_step_is_unchanged(self):
        """One room is a one-element path, so a walk needs no special case --
        and must not gain one."""
        from commit import record_spatial_experience
        sc = self._sc()
        st = {}
        record_spatial_experience(st, sc, "start", 1)
        record_spatial_experience(st, sc, "c1", 2)
        assert st["visited_rooms"] == ["start", "c1"]
        assert st["place_graph"]["edges"]["start"]["c1"]["taken"] is True
