"""A planned thing standing where a body stands becomes a real entity.

THE OWNER'S REPORT (chat 151, "The Doctor — Hinami ⎇3", 2026-09-20): "the
tardis only exists as a planned object no beat has minted it."

Everything upstream was right. The mandate was granted and active -- "Can you
place the tardis down on the beach somewhere?", capabilities `plan_entity` --
and the Room filed a complete plan: `where: moonlit_beach`, a `look` ("A tall
blue box, absurdly out of place on an Okinawan beach, its roof lantern
unlit."), `sources: {light_source: dark}`, and three truths including "It
stands a few paces up the dry sand from where the Doctor and Hinami fell."
`room_status` even said so in as many words: "the TARDIS plan waits on the
beach for its first glance." Both bodies stood in `moonlit_beach`, the room id
matched, nothing was frame-scoped, and `plans_in_view` therefore offered the
plan to the Director on every beat with its look and brief attached.

`scene` never held it, through four beats. Only `interaction_loop` ever
mentioned a TARDIS -- the Doctor knowing from his own card that he has one.

WHY THE DIRECTOR COULD NOT DO IT. "The Director RENDERS a plan when it comes
into view" was the handoff, and the causal Director's sheet forbids that row in
so many words: "Initial standing descriptions and unchanged background facts
are context." Its contract is to convert event_inputs into ordered event
ledgers, and a police box standing on sand is not an event. So a plan was
rendered only when somebody TOUCHED the thing -- which nobody does to a thing
they cannot see, and nobody can see it because perception reads
`scene.entities`. Chat 114's identical plan was rendered at beat 9, when a body
finally reached the spot.

Planned ROOMS have had a deterministic materializer all along
(`structure.materialize_planned_fringe`). Planned THINGS did not. Per the
owner's ruling the same day: a model declares, and everything after that is
arithmetic.
"""

import time

import pytest

from world.planned_entities import (add_planned_entity, materialize_plans_in_sight,
                                    planned_entities)

LOOK = ("A tall blue box, absurdly out of place on an Okinawan beach, its "
        "roof lantern unlit.")


def _beach():
    return {
        "rooms": {"moonlit_beach": {"name": "Moonlit Beach", "adjacent": []},
                  "utaki_shrine": {"name": "Utaki Shrine", "adjacent": []}},
        "positions": {"Hinami": "moonlit_beach", "The Doctor": "moonlit_beach"},
        "entities": {}, "stations": {}, "contained": {}, "contacts": [],
    }


@pytest.fixture
def cid(temp_db):
    """A real chat row: `world` carries a chat foreign key."""
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("The Doctor — Hinami", "", time.time()))


def _plan(cid, **over):
    entry = {"kind": "thing", "name": "The TARDIS",
             "role": "the Doctor's stranded time machine",
             "look": LOOK,
             "brief": {"where": "moonlit_beach",
                       "purpose": "The way home, standing unattended."}}
    entry.update(over)
    return add_planned_entity(cid, entry, turn_idx=0)


class TestTheTardisOnTheBeach:
    def test_a_plan_where_a_body_stands_is_stood_up(self, cid):
        plan = _plan(cid)
        scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        assert [m["name"] for m in minted] == ["The TARDIS"]
        key = minted[0]["entity_id"]
        assert scene["entities"][key]["name"] == "The TARDIS"
        assert scene["positions"][key] == "moonlit_beach"

    def test_it_mints_the_bare_fact_and_the_plan_s_own_look(self, cid):
        """What the thing IS stays the plan's and what it DOES stays the
        Director's; this only ensures there is something to write about."""
        _plan(cid)
        scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        record = scene["entities"][minted[0]["entity_id"]]
        assert record["description"] == LOOK
        assert record["plan_ref"]["uid"] == minted[0]["plan"]
        # No state, no posture, no invented anatomy of a time machine.
        assert set(record) <= {"name", "kind", "description", "aliases",
                               "plan_ref"}

    def test_the_plan_is_settled_so_nothing_mints_it_twice(self, cid):
        """`plans_in_view` must stop offering it, or the next beat is invited
        to stand a second police box beside the first -- the defect
        `commit_background` records for chat 114."""
        _plan(cid)
        scene, first = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        assert first
        stored = list(planned_entities(cid).values())[0]
        assert stored["rendered"]["by"] == "engine"
        scene, again = materialize_plans_in_sight(
            cid, scene, occupied={"moonlit_beach"})
        assert again == []

    def test_a_reroll_of_the_same_beat_stands_up_one(self, cid):
        """Idempotence is what makes this safe under reroll, rerun-from-stage,
        branch and replay."""
        _plan(cid)
        scene = _beach()
        for _ in range(3):
            scene, _m = materialize_plans_in_sight(
            cid, scene, occupied={"moonlit_beach"})
        names = [e["name"] for e in scene["entities"].values()]
        assert names == ["The TARDIS"]


class TestEveryGateSubtracts:
    def test_a_room_nobody_is_standing_in_stands_nothing_up(self, cid):
        """The first glance the plan waits for, and never a sweep that stands
        things up across a map nobody has walked. `project_planned_emissions`
        is what reaches past the room, and it deliberately mints nothing."""
        _plan(cid, brief={"where": "utaki_shrine"})
        scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        assert minted == [] and scene["entities"] == {}

    def test_a_plan_the_director_already_rendered_is_left_alone(self, cid):
        _plan(cid, rendered={"entity_id": "tardis", "render": LOOK})
        _scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        assert minted == []

    @pytest.mark.parametrize("kind", ["person", "creature"])
    def test_only_a_thing(self, cid, kind):
        """A person is the identity floor's and a promotion's business; a
        creature carries a stance and a hunger a bare mint would lie about."""
        _plan(cid, kind=kind, name="Someone")
        _scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        assert minted == []

    def test_a_name_the_scene_already_holds_mints_nothing(self, cid):
        """A second copy of a thing is worse than one nobody found -- the
        duplicate this engine minted as `copper_coin_2` days earlier."""
        _plan(cid)
        for already in ({"entities": {"blue_box": {"name": "The TARDIS"}}},
                        {"entities": {"b": {"aliases": ["the tardis"]}}},
                        {"entities": {"The TARDIS": {"kind": "object"}}},
                        {"positions": {"The TARDIS": "moonlit_beach"}}):
            scene = _beach()
            for key, val in already.items():
                scene[key].update(val)
            _scene, minted = materialize_plans_in_sight(
            cid, scene, occupied={"moonlit_beach"})
            assert minted == [], already

    def test_a_room_the_scene_does_not_hold_stands_nothing_up(self, cid):
        _plan(cid, brief={"where": "hibiscus_garden"})
        _scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"hibiscus_garden", "moonlit_beach"})
        assert minted == []

    def test_a_nameless_plan_says_nothing(self, cid):
        _plan(cid, name="")
        _scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        assert minted == []

    def test_an_empty_world_is_a_no_op(self, cid):
        for scene in ({}, {"rooms": {}}, _beach()):
            out, minted = materialize_plans_in_sight(
            cid, scene, occupied={"moonlit_beach"})
            assert minted == []
        assert materialize_plans_in_sight(
            cid, _beach(), occupied=())[1] == []


class TestTheMindCanThenSeeIt:
    def test_a_stood_up_thing_reaches_the_eyes_in_the_room(self, cid):
        """The whole point, and it only works because a thing in a room became
        visible at all on the same day
        (`tests/test_a_thing_someone_set_down_can_be_seen.py`). Before that,
        minting it would have changed nothing anyone could perceive."""
        from agents import perception
        _plan(cid)
        scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        assert minted
        rows = perception._visible_things(
            scene, "The Doctor", "moonlit_beach", bodies=["The Doctor", "Hinami"])
        assert any("tardis" in row["what"].lower() for row in rows), rows


class TestAPlanCanSayWhereInTheRoom:
    """`brief.where` named a ROOM and nothing finer, so a materialized thing
    stood nowhere in particular: named without a distance, and needing light
    like anything else, because `feature_visibility`'s carve-outs -- what a body
    has its hands on, and a doorway -- cannot reach a thing that stands at
    nothing. Chat 151's plan said in PROSE that the box "stands a few paces up
    the dry sand ... above the tideline", on a beach carrying an anchor called
    `tideline_sand`, and reading the anchor out of the sentence is the word-list
    failure this repository keeps paying for. So the Room declares it.
    """

    def _beach_with_fixtures(self):
        scene = _beach()
        scene["rooms"]["moonlit_beach"]["anchors"] = {
            "tideline_sand": {"desc": "the dry sand above the tideline"},
            "waterline": {"desc": "the waterline"},
        }
        return scene

    def test_a_declared_station_is_stamped(self, cid):
        _plan(cid, brief={"where": "moonlit_beach", "station": "tideline_sand"})
        scene, minted = materialize_plans_in_sight(
            cid, self._beach_with_fixtures(), occupied={"moonlit_beach"})
        key = minted[0]["entity_id"]
        assert scene["stations"][key] == {"at": "tideline_sand", "near": []}

    def test_and_the_thing_is_then_seen_where_the_fixture_is(self, cid):
        """The point of declaring it: the thing inherits that anchor's own
        visibility, exactly as a coin on a counter does, instead of standing
        unplaced and claiming no distance."""
        from agents import perception
        _plan(cid, brief={"where": "moonlit_beach", "station": "tideline_sand"})
        scene, _m = materialize_plans_in_sight(
            cid, self._beach_with_fixtures(), occupied={"moonlit_beach"})
        rows = perception._visible_things(scene, "The Doctor", "moonlit_beach",
                                         bodies=["The Doctor", "Hinami"])
        said = " ".join(r["what"] for r in rows)
        assert "TARDIS" in said and "tideline" in said, said

    def test_a_station_the_room_does_not_have_falls_back_to_a_cell(self, cid):
        """A station naming nothing is a place nobody can see it at, so the
        named fixture is refused -- but the thing is still PUT somewhere, because
        the alternative is the defect below. The package validator refuses the
        bad name at draft time; this is the floor under that."""
        _plan(cid, brief={"where": "moonlit_beach", "station": "hibiscus_wall"})
        scene, minted = materialize_plans_in_sight(
            cid, self._beach_with_fixtures(), occupied={"moonlit_beach"})
        station = (scene.get("stations") or {})[minted[0]["entity_id"]]
        assert station["at"] == "" and station["cell"]

    def test_a_thing_with_no_declared_station_is_still_somewhere(self, cid):
        """THE DEFECT THE OWNER FOUND: "where is the tardis in my latest scene.
        It's in the things list but it shows nowhere on the map." A thing with a
        room and no station is "in here, nowhere in particular", and the map
        draws a thing by its station's anchor or its cell, so it had nothing to
        be drawn at.

        The fallback is the engine's OWN answer for a body that stands nowhere in
        particular -- `standing_cell`'s room centre, stepped off by
        `free_cell_near` to a cell no furniture and no body holds -- so it is a
        default rather than an invention, and the thing ends up somewhere a body
        could stand beside."""
        _plan(cid)
        scene, minted = materialize_plans_in_sight(
            cid, self._beach_with_fixtures(), occupied={"moonlit_beach"})
        station = (scene.get("stations") or {})[minted[0]["entity_id"]]
        assert len(station["cell"]) == 2
        assert all(isinstance(n, int) for n in station["cell"])

    def test_a_room_that_declares_no_geometry_still_places_it(self, cid):
        """There is no such thing as a room without a floor: `room_grid` answers
        a default 6x6 centred at (3, 3) for a room that declares no size and no
        cells, so a thing is placeable in any room the scene holds. Written down
        because the first version of this guarded an unplaceable case that does
        not exist."""
        _plan(cid)
        scene, minted = materialize_plans_in_sight(
            cid, _beach(), occupied={"moonlit_beach"})
        station = (scene.get("stations") or {})[minted[0]["entity_id"]]
        assert station["cell"] == [3, 3]

    def test_a_thing_stood_up_before_this_existed_is_placed_on_a_later_beat(
            self, cid):
        """Self-healing rather than a migration: the owner's TARDIS was already
        committed unplaced, and this pass runs on every commit, so the story
        repairs itself on its next beat instead of having its scene rewritten
        underneath it."""
        _plan(cid)
        scene = self._beach_with_fixtures()
        scene, first = materialize_plans_in_sight(
            cid, scene, occupied={"moonlit_beach"})
        key = first[0]["entity_id"]
        # Put it back the way it landed before the placement existed.
        scene["stations"].pop(key)
        scene, healed = materialize_plans_in_sight(
            cid, scene, occupied={"moonlit_beach"})
        assert [h["placed_late"] for h in healed] == [True]
        assert (scene.get("stations") or {})[key]["cell"]
        # ...and once placed, it is left alone.
        scene, again = materialize_plans_in_sight(
            cid, scene, occupied={"moonlit_beach"})
        assert again == []
