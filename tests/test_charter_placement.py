"""A charter body has a room and, now, a place IN it -- derived, laid on a
view, never stored (`world/charter_place.py`,
`docs/design/DESIGN_CHARTER_PLACEMENT.md`).

The gap this closes, measured in the code before the module existed: a
charter body's location was `place` alone, and it never entered
`scene.positions`, so perception placed it by ROOM (`_presence_bodies` wrote a
bare positions row), `charter_observe._observer_scene` stood the observing
body in its room with no cell, the movement floor never route-checked a
Director move of one (no origin on the scene), and such a move committed as a
SECOND positions row disagreeing with the registry's `place`.

The owner's ruling (2026-09-05): the UNOBSERVED body's dealt cell is stable
per (body, room) across beats; a body PRESENT in a scene has a stateful
position -- what the pipeline writes lands and is read back -- and navigates
under the same floor a cast member does.
"""

from __future__ import annotations

import copy
import json
import time

from world.charter import normalize_charter
from world.charter_observe import (body_receives_evidence,
                                   plan_public_evidence)
from world.charter_place import (charter_placements, placement_uid,
                                 resolve_scene_placements, rooms_in_frame,
                                 scene_with_charter_bodies)
from world.spatial import (body_cell, body_visibility, observer_field, room_of,
                           visual_level_between)

DOOR = "open_door"


def _scene():
    """A dim hall with a head-high screen along its east wall, a hearth on
    the west wall and an open door north to the yard; the yard opens east
    onto a road; the cellar is walled off from everything."""
    return {
        "rooms": {
            "hall": {"name": "Hall", "size": "large", "light": "dim",
                     "anchors": {
                         "screen": {"desc": "a folding screen", "dir": "e",
                                    "footprint": "run", "height": "head",
                                    "opacity": "opaque"},
                         "counter": {"desc": "the long counter", "dir": "s",
                                     "footprint": "run", "height": "waist"},
                         "hearth": {"desc": "the hearth", "dir": "w"}},
                     "adjacent": [{"to": "yard", "barrier": DOOR, "dir": "n"},
                                  {"to": "cellar", "barrier": "wall",
                                   "dir": "e"}]},
            "yard": {"name": "Yard", "adjacent": [
                {"to": "hall", "barrier": DOOR, "dir": "s"},
                {"to": "road", "barrier": DOOR, "dir": "e"}]},
            "road": {"name": "Road", "adjacent": [
                {"to": "yard", "barrier": DOOR, "dir": "w"}]},
            "cellar": {"name": "Cellar", "adjacent": [
                {"to": "hall", "barrier": "wall", "dir": "w"}]},
        },
        "positions": {"Rowan": "hall"},
        "stations": {"Rowan": {"at": "hearth"}},
    }


def _charter(**bodies):
    base = {
        "clerk": {"name": "Ysra", "place": "hall"},
        "porter": {"name": "Oren", "place": "hall"},
        "guest": {"name": "Tam", "place": "hall"},
    }
    base.update(bodies)
    return normalize_charter({
        "key": "inn",
        "posts": {"desk": {"place": "hall", "anchor": "counter"},
                  "ghost": {"place": "hall", "anchor": "no_such_fixture"}},
        "watch": {"desk": "clerk", "ghost": "porter"},
        "bodies": base,
    })


def _registry(charter):
    return {"items": {charter["key"]: {"state": charter}}}


def _placed(charter, scene=None, rooms=("hall",)):
    scene = scene or _scene()
    return charter_placements(
        _registry(charter), scene, frame_rooms=rooms_in_frame(scene, rooms))


class TestTheTwoNewFields:
    def test_a_post_keeps_its_anchor_and_a_body_its_station(self):
        charter = _charter(guest={"name": "Tam", "place": "hall",
                                  "station": {"cell": [3, 3], "facing": "e",
                                              "near": ["Rowan"]}})
        assert charter["posts"]["desk"]["anchor"] == "counter"
        assert charter["bodies"]["guest"]["station"] == {
            "cell": [3, 3], "near": ["Rowan"], "facing": "e"}

    def test_the_fields_are_absent_unless_authored(self):
        """A registry from before either field existed is byte-identical."""
        charter = normalize_charter({
            "key": "inn", "posts": {"desk": {"place": "hall"}},
            "bodies": {"clerk": {"name": "Ysra", "place": "hall"}}})
        assert "anchor" not in charter["posts"]["desk"]
        assert "station" not in charter["bodies"]["clerk"]

    def test_junk_is_no_station_and_a_body_nowhere_carries_none(self):
        charter = _charter(
            guest={"name": "Tam", "place": "hall", "station": {"cell": "3,3"}},
            gone={"name": "Wil", "place": "", "station": {"at": "counter"}})
        assert "station" not in charter["bodies"]["guest"]
        assert "station" not in charter["bodies"]["gone"]


class TestTheRule:
    def test_the_post_anchor_places_the_watch_holder_at_the_fixture(self):
        placed = _placed(_charter())
        clerk = placed[placement_uid("inn", "clerk")]
        assert clerk["station"] == {"at": "counter"}
        assert clerk["source"] == "post"
        assert clerk["facing"] == "s"          # toward the counter's wall

    def test_an_anchor_the_room_lacks_is_ignored_fail_open(self):
        placed = _placed(_charter())
        porter = placed[placement_uid("inn", "porter")]
        assert porter["source"] == "dealt"
        assert "cell" in porter["station"]

    def test_an_authored_station_outranks_the_post(self):
        charter = _charter(clerk={"name": "Ysra", "place": "hall",
                                  "station": {"at": "hearth"}})
        clerk = _placed(charter)[placement_uid("inn", "clerk")]
        assert clerk["station"] == {"at": "hearth"}
        assert clerk["source"] == "authored"
        assert clerk["facing"] == "w"

    def test_an_authored_cell_is_snapped_to_the_room(self):
        charter = _charter(guest={"name": "Tam", "place": "hall",
                                  "station": {"cell": [40, 40]}})
        guest = _placed(charter)[placement_uid("inn", "guest")]
        x, y = guest["station"]["cell"]
        assert 0 <= x < 8 and 0 <= y < 8

    def test_an_en_route_body_stands_at_the_doorway(self):
        charter = _charter(guest={
            "name": "Tam", "place": "hall",
            "walk": {"target": "road", "route": ["hall", "yard", "road"],
                     "leg": 0, "credit": 0.0}})
        guest = _placed(charter)[placement_uid("inn", "guest")]
        assert guest["station"] == {"at": "door:yard"}
        assert guest["source"] == "walk"
        assert guest["facing"] == "n"          # toward the doorway

    def test_the_dealt_cell_is_byte_stable_across_two_registry_loads(self):
        """Seeded from (identity seed, room) and nothing else: two loads,
        two beats, the same cell -- a body nobody touched does not wander."""
        first = _placed(_charter())
        second = _placed(normalize_charter(json.loads(json.dumps(_charter()))))
        assert {k: (v["station"], v["facing"]) for k, v in first.items()} == \
            {k: (v["station"], v["facing"]) for k, v in second.items()}

    def test_the_dealt_cell_avoids_the_furniture(self):
        from world.spatial import anchor_cells
        scene = _scene()
        taken = {tuple(c) for rec in anchor_cells(scene, "hall").values()
                 for c in rec["cells"]}
        for placed in _placed(_charter(), scene).values():
            if placed["source"] == "dealt":
                assert tuple(placed["station"]["cell"]) not in taken

    def test_only_the_frame_is_laid(self):
        charter = _charter(far={"name": "Far", "place": "road"})
        placed = _placed(charter, rooms=("hall",))
        assert placement_uid("inn", "far") not in placed
        assert rooms_in_frame(_scene(), ["hall"]) == ["hall", "yard"]

    def test_bound_and_departed_bodies_are_not_placed(self):
        charter = _charter(gone={"name": "Wil", "place": "hall",
                                 "departed": True})
        charter["bindings"] = {"clerk": {"char_id": 1}}
        placed = _placed(charter)
        assert placement_uid("inn", "gone") not in placed
        assert placement_uid("inn", "clerk") not in placed


class TestTheView:
    def test_the_stored_scene_is_never_mutated(self):
        scene = _scene()
        before = copy.deepcopy(scene)
        placed = _placed(_charter(), scene)
        view = scene_with_charter_bodies(scene, placed)
        assert scene == before
        assert set(view["positions"]) == {"Rowan", "Ysra", "Oren", "Tam"}
        assert view["stations"]["Ysra"] == {"at": "counter"}
        assert view["orientation"]["Ysra"] == {"facing": "s"}

    def test_a_body_the_scene_already_stands_is_left_alone(self):
        scene = _scene()
        scene["positions"]["Ysra"] = "yard"
        view = scene_with_charter_bodies(scene, _placed(_charter(), scene))
        assert view["positions"]["Ysra"] == "yard"
        assert "Ysra" not in view["stations"]

    def test_a_withheld_ambiguous_name_is_keyed_by_its_uid(self):
        """Two people named Ash: neither may stand under the name (a shared
        name is withheld from every view), so both stand under the permanent
        uid -- a key no stranger label is ever cut from."""
        charter = _charter(twin_a={"name": "Ash", "place": "hall"},
                           twin_b={"name": "Ash", "place": "yard"})
        placed = _placed(charter, rooms=("hall", "yard"))
        assert placed[placement_uid("inn", "twin_a")]["key"] == \
            "charter:inn:twin_a"
        assert placed[placement_uid("inn", "twin_a")]["ambiguous"] is True
        view = scene_with_charter_bodies(_scene(), placed)
        assert "Ash" not in view["positions"]
        assert view["positions"]["charter:inn:twin_a"] == "hall"


class TestPerceptionGradesTheCell:
    """The payoff: a townsperson is graded by light and line at its cell,
    as cast are, instead of being seen because it shares a room."""

    def test_behind_the_screen_is_none_and_in_the_open_is_shapes(self):
        charter = _charter(
            guest={"name": "Tam", "place": "hall", "station": {"cell": [7, 3]}},
            porter={"name": "Oren", "place": "hall", "station": {"cell": [3, 3]}})
        scene = _scene()
        view = scene_with_charter_bodies(scene, _placed(charter, scene))
        assert body_visibility(view, "Rowan", "Tam")["occluded_by"] \
            == "a folding screen"
        assert visual_level_between(view, "Rowan", "Tam") == "none"
        assert visual_level_between(view, "Rowan", "Oren") == "shapes"

    def test_before_the_view_both_were_seen_alike(self):
        """The room-only placement `_presence_bodies` used to write."""
        scene = _scene()
        scene["positions"].update({"Tam": "hall", "Oren": "hall"})
        assert visual_level_between(scene, "Rowan", "Tam") == \
            visual_level_between(scene, "Rowan", "Oren") == "shapes"

    def test_the_charter_observers_own_eye_is_graded_by_line(self):
        """The observing body stands at its cell: behind the screen it does
        not see the player's act; in the open it does."""
        scene = _scene()
        scene["rooms"]["hall"]["light"] = "lit"
        charter = _charter(
            guest={"name": "Tam", "place": "hall", "station": {"cell": [7, 3]}},
            porter={"name": "Oren", "place": "hall", "station": {"cell": [3, 3]}})
        act = {"source_id": "act:0", "kind": "action", "actor": "Rowan",
               "surface": "draws a knife", "visibility": "overt",
               "conceal_from": []}
        plan = plan_public_evidence(charter, [act], scene, turn_id=3)
        assert "porter" in plan["receiving"]
        assert "guest" not in plan["receiving"]
        assert scene["positions"] == {"Rowan": "hall"}   # the store, untouched


class TestNothingChangesWithoutACharter:
    def test_observer_field_and_the_evidence_fallback_are_as_they_were(self):
        scene = _scene()
        before = copy.deepcopy(scene)
        field = observer_field(scene, "Rowan")
        assert set(field.offsets) == {"hall", "yard"}
        # `body_receives_evidence` without a placement is the old room-only
        # reading: the same hall hears, the walled-off cellar does not.
        speech = {"source_id": "speech:0", "kind": "speech", "actor": "Rowan",
                  "exact_quote": '"Ale."', "volume": "normal",
                  "visibility": "overt", "conceal_from": []}
        assert body_receives_evidence(
            scene, "clerk", {"place": "hall"}, (), None, speech) is True
        assert body_receives_evidence(
            scene, "cook", {"place": "cellar"}, (), None, speech) is False
        assert scene == before

    def test_a_flat_scene_plans_exactly_what_it_planned(self):
        """No geometry authored, no station on the actor: the view deals a
        cell per body and `body_visibility` still answers open, so the plan
        is byte-identical to the room-only one."""
        scene = {"rooms": {"hall": {"name": "Hall", "adjacent": [
            {"to": "yard", "barrier": "closed_door"}]},
            "yard": {"name": "Yard", "adjacent": [
                {"to": "hall", "barrier": "closed_door"}]}},
            "positions": {"Rowan": "hall"}}
        charter = normalize_charter({"key": "town", "bodies": {
            "reeve": {"name": "Ysra", "place": "hall"},
            "porter": {"name": "Oren", "place": "yard"}}})
        speech = {"source_id": "speech:0", "kind": "speech", "actor": "Rowan",
                  "exact_quote": '"Ale."', "volume": "normal",
                  "visibility": "overt", "conceal_from": []}
        plan = plan_public_evidence(charter, [speech], scene, turn_id=1)
        assert plan["receiving"] == ["reeve"]
        assert plan["acquired"] == 1


class TestTheRouting:
    """A Director move of a townsperson is the registry's to land."""

    def test_a_move_and_a_station_are_resolved_by_every_spelling(self):
        charter = _charter()
        diff = {"positions": {"Ysra": "yard", "Rowan": "yard",
                              "charter:inn:porter": "yard"},
                "stations": {"Tam": {"at": "counter"}, "Rowan": {"at": "hearth"}}}
        out = resolve_scene_placements(_registry(charter), diff, _scene())
        assert sorted((m["body"], m["room"]) for m in out["moves"]) == [
            ("clerk", "yard"), ("porter", "yard")]
        assert out["stations"] == [{"charter": "inn", "body": "guest",
                                    "name": "Tam", "station": {"at": "counter"}}]
        assert sorted(out["names"]) == ["Tam", "Ysra", "charter:inn:porter"]

    def test_a_name_the_scene_stands_and_a_shared_name_are_left_alone(self):
        charter = _charter(twin_a={"name": "Ash", "place": "hall"},
                           twin_b={"name": "Ash", "place": "yard"})
        scene = _scene()
        scene["positions"]["Ysra"] = "hall"       # a minted entity's row
        out = resolve_scene_placements(
            _registry(charter), {"positions": {"Ysra": "yard", "Ash": "road"}},
            scene)
        assert out["moves"] == [] and out["names"] == []

    def test_a_destination_that_is_no_room_is_not_routed(self):
        out = resolve_scene_placements(
            _registry(_charter()), {"positions": {"Ysra": "the moon"}}, _scene())
        assert out["moves"] == []

    def test_the_commit_routes_before_the_merge_and_lands_in_the_domain(self):
        import inspect
        from persist import commit as facade
        m = inspect.getmodule(facade.commit_scene)   # the defining sibling
        prepare = inspect.getsource(m.prepare_scene_commit)
        assert prepare.index("route_scene_placements(") \
            < prepare.index("sc = merge_scene_with_diff(")
        assert '"charter_placements": _charter_placements' in prepare
        commit = inspect.getsource(m.commit_scene)
        assert "_apply_charter_placements(ctx, prepared.get(\"charter_placements\"))" \
            in commit
        assert "apply_scene_placements" in inspect.getsource(
            m._apply_charter_placements)


def _chat(db):
    from world.charter_runtime import save_registry
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Charter placement", "", time.time()))
    # Two in the hall, not three: at `CHARTER_CROWD_FLOOR` the crowd IS the
    # presentation and no body is a figure of its own.
    save_registry(cid, {"inn": _charter(porter={"name": "Oren", "place": "road"})})
    return cid


class TestTheRoundTrip:
    """Beat N the Director moves the innkeeper to the door anchor; beat N+1
    the placement returns the door anchor, not the dealt cell; beat N+2 she
    is moved into the next room: the registry's `place` is that room, `walk`
    is empty, and the old room's observer no longer sees her."""

    def test_the_round_trip(self, temp_db):
        from agents.common import presence_figures_for_room
        from world.charter_runtime import (apply_scene_placements,
                                           registry_for,
                                           route_scene_placements)
        cid = _chat(temp_db)
        scene = _scene()
        # Put her mid-walk first, so the landing is seen to end the route.
        from world.charter_runtime import registry_for_update, save_registry
        reg = registry_for_update(cid)
        reg["items"]["inn"]["state"]["bodies"]["clerk"]["walk"] = {
            "target": "road", "route": ["hall", "yard", "road"], "leg": 0,
            "credit": 0.0}
        save_registry(cid, reg)

        # Beat N: to the door anchor, in her own room.
        diff = {"positions": {"Ysra": "hall"},
                "stations": {"Ysra": {"at": "door:yard"}}}
        routing = route_scene_placements(cid, diff, scene)
        assert diff == {"positions": {}, "stations": {}}   # stripped
        assert apply_scene_placements(cid, routing) == 1

        # Beat N+1: the placement reads it back.
        placed = charter_placements(registry_for(cid), scene,
                                    frame_rooms=["hall"])
        clerk = placed[placement_uid("inn", "clerk")]
        assert clerk["station"] == {"at": "door:yard"}
        assert clerk["source"] == "authored"
        body = registry_for(cid)["items"]["inn"]["state"]["bodies"]["clerk"]
        assert "walk" not in body
        names_before = [r["name"] for r in presence_figures_for_room(
            cid, scene, "hall")]
        assert "Ysra" in names_before
        row = next(r for r in presence_figures_for_room(cid, scene, "hall")
                   if r["name"] == "Ysra")
        assert row["placement"]["station"] == {"at": "door:yard"}

        # Beat N+2: into the yard.
        routing = route_scene_placements(
            cid, {"positions": {"Ysra": "yard"}}, scene)
        apply_scene_placements(cid, routing)
        body = registry_for(cid)["items"]["inn"]["state"]["bodies"]["clerk"]
        assert body["place"] == "yard"
        assert "walk" not in body and "station" not in body
        assert "Ysra" not in [r["name"] for r in presence_figures_for_room(
            cid, scene, "hall")]
        placed = charter_placements(registry_for(cid), scene,
                                    frame_rooms=["yard"])
        assert placed[placement_uid("inn", "clerk")]["source"] == "dealt"

    def test_a_walk_leg_clears_the_station(self):
        from world.charter_move import _advance
        body = {"key": "clerk", "place": "hall", "station": {"at": "counter"},
                "walk": {"target": "road", "route": ["hall", "yard", "road"],
                         "leg": 0, "credit": 2.0}}
        moved = _advance("clerk", body, None, {}, {})
        assert moved["place"] == "road" and "station" not in moved

    def test_relocate_and_station_seams(self):
        from world.charter_move import place_body, station_body
        reg = _registry(_charter())
        station_body(reg, "inn", "clerk", {"cell": [2, 2], "facing": "n"})
        assert reg["items"]["inn"]["state"]["bodies"]["clerk"]["station"] == {
            "cell": [2, 2], "facing": "n"}
        place_body(reg, "inn", "clerk", "yard")
        body = reg["items"]["inn"]["state"]["bodies"]["clerk"]
        assert body["place"] == "yard" and "station" not in body
        station_body(reg, "inn", "clerk", None)
        assert "station" not in body


class TestNavigation:
    """The movement floor judges a townsperson from the view."""

    def test_through_an_open_door_lands_and_through_a_wall_is_refused(self):
        from agents.director import _unreachable_position_writes
        scene = _scene()
        view = scene_with_charter_bodies(scene, _placed(_charter(), scene))
        bodies = ["Rowan", "Ysra"]
        assert _unreachable_position_writes(
            view, view, {"Ysra": "yard"}, bodies) == []
        assert _unreachable_position_writes(
            view, view, {"Ysra": "cellar"}, bodies) == [
            ("Ysra", "hall", "cellar")]
        # And the same refusal for the cast member beside her.
        assert _unreachable_position_writes(
            view, view, {"Rowan": "cellar"}, bodies) == [
            ("Rowan", "hall", "cellar")]

    def test_without_the_view_the_townsperson_was_never_checked(self):
        from agents.director import _unreachable_position_writes
        scene = _scene()
        assert room_of(scene, "Ysra") is None
        assert _unreachable_position_writes(
            scene, scene, {"Ysra": "cellar"}, ["Ysra"]) == []

    def test_director_resolve_builds_the_view_before_the_floor(self):
        import inspect
        from agents import director
        src = inspect.getsource(director.director_resolve)
        assert src.index("charter_view_for_rooms(") \
            < src.index("_unreachable_position_writes(")
        assert "_bodies.extend(_charter_keys)" in src


def test_the_view_exists_for_the_stage_only():
    """Perception lays the rows on its own scene copy and nothing persists
    them: the placement row travels on `presence_figures_for_room`'s row and
    is laid by `_presence_bodies`, never written by any commit domain."""
    import inspect
    from agents import perception
    src = inspect.getsource(perception._presence_bodies)
    assert "lay_charter_bodies(sc, placements, keys=keys)" in src
    from persist import commit as facade
    css = inspect.getmodule(facade.commit_scene)     # the defining sibling
    for fn in (css.prepare_scene_commit, css.commit_scene,
               css._apply_charter_placements):
        assert "lay_charter_bodies" not in inspect.getsource(fn)
        assert "scene_with_charter_bodies" not in inspect.getsource(fn)


def test_the_cell_is_read_through_the_same_functions_the_map_reads():
    scene = _scene()
    charter = _charter(guest={"name": "Tam", "place": "hall",
                              "station": {"cell": [3, 3]}})
    view = scene_with_charter_bodies(scene, _placed(charter, scene))
    assert body_cell(view, "Tam") == (3, 3)
    assert body_cell(view, "Ysra") is not None      # at the counter
