"""MASTER-022 / docs/UNBUILT.md 1.6: sight is not a route.

A remembering mind records an edge when it is a way THROUGH -- passable now,
or passable by opening (`closed_door`; a locked door normalizes there, and a
remembered route past a locked door is still a route if you expect the key).
The place-graph writers used to read "doorway" as merely `!= "wall"`, so a
`window`, `bars`, a `one_way_window` and even a `separated` non-adjacency all
minted walkable remembered edges -- and `_frontier_hops` then rendered the
false edge to its owner as a specific distance through glass they could act
on with no retraction path. The legacy `known_exits` writer was worse (no
barrier filter at all), and `_annotate_known_exits` merges it back into the
same BFS adjacency, so both writers must agree or wall edges re-enter.
"""

from __future__ import annotations

from persist.commit import record_spatial_experience, update_place_graph
from world.spatial import visible_adjacent_rooms


def _edge(to, dir=None, barrier="open"):
    e = {"to": to, "barrier": barrier}
    if dir:
        e["dir"] = dir
    return e


def _room(name, adjacent=()):
    return {"name": name, "light": "lit", "desc": f"{name}.",
            "adjacent": [dict(e) for e in adjacent]}


def _scene(rooms):
    return {"rooms": rooms, "positions": {}, "entities": {}, "attire": {},
            "overlays": {}}


def _gallery():
    """One standing room ringed by every barrier family."""
    return _scene({
        "cell": _room("Cell", [
            _edge("yard", "e", barrier="window"),
            _edge("corridor", "n", barrier="bars"),
            _edge("obs", "w", barrier="one_way_window"),
            _edge("vault", "s", barrier="wall"),
            _edge("hall", None, barrier="closed_door"),
            _edge("store", None, barrier="locked_door"),
            _edge("foyer", None, barrier="open"),
            _edge("tent", None, barrier="membrane"),
            _edge("far_tower", None, barrier="separated"),
        ]),
        "yard": _room("Yard"), "corridor": _room("Corridor"),
        "obs": _room("Obs"), "vault": _room("Vault"), "hall": _room("Hall"),
        "store": _room("Store"), "foyer": _room("Foyer"),
        "tent": _room("Tent"), "far_tower": _room("Far Tower"),
    })


class TestWhatMintsARememberedRoute:
    def test_see_through_barriers_mint_no_edge(self):
        sc = _gallery()
        graph = update_place_graph(
            None, sc, "cell", 1, visible=visible_adjacent_rooms(sc, "cell"))
        minted = set(graph["edges"].get("cell") or {})
        assert not minted & {"yard", "corridor", "obs", "vault", "far_tower"}

    def test_ways_through_now_or_by_opening_do(self):
        sc = _gallery()
        graph = update_place_graph(
            None, sc, "cell", 1, visible=visible_adjacent_rooms(sc, "cell"))
        minted = set(graph["edges"].get("cell") or {})
        assert {"foyer", "tent", "hall", "store"} <= minted, (
            "open, membrane, closed_door and locked_door (which normalizes "
            "to closed_door) are all routes a mind should record")

    def test_a_room_seen_through_glass_is_still_a_known_place(self):
        """Sight's legitimate earnings survive the narrowing: the NODE (the
        place exists, its name) is knowledge sight gives; only the walkable
        EDGE is not."""
        sc = _gallery()
        graph = update_place_graph(
            None, sc, "cell", 1, visible=visible_adjacent_rooms(sc, "cell"))
        assert graph["nodes"].get("yard", {}).get("basis") == "seen"

    def test_a_glass_edge_remembered_from_before_is_disproven_on_standing(self):
        """The retraction path the old filter lacked: an edge minted through
        a window before this rule gets stamped `disproven` -- both ways --
        the next time its owner stands at the pane."""
        sc = _gallery()
        stale = {
            "nodes": {"cell": {"basis": "walked", "visits": 1},
                      "yard": {"basis": "seen"}},
            "edges": {
                "cell": {"yard": {"last_confirmed": 1, "basis": "seen"}},
                "yard": {"cell": {"last_confirmed": 1, "basis": "seen"}},
            },
        }
        graph = update_place_graph(
            stale, sc, "cell", 9, visible=visible_adjacent_rooms(sc, "cell"))
        assert graph["edges"]["cell"]["yard"].get("disproven") == 9
        assert graph["edges"]["yard"]["cell"].get("disproven") == 9


class TestTheLegacyWriterAgrees:
    """`known_exits` merges into the same BFS adjacency the graph feeds; a
    laxer filter here would let wall and glass edges re-enter through the
    older door."""

    def test_known_exits_records_only_route_memory_edges(self):
        st = record_spatial_experience({}, _gallery(), "cell", 1)
        assert st["known_exits"]["cell"] == sorted(
            ["hall", "store", "foyer", "tent"])


def test_the_local_set_is_the_canonical_set():
    """Drift guard. `persist/commit_place_graph.py` spells the set from the
    facade's `_PASSABLE_BARRIERS` because `world/spatial.py` does not yet
    re-export the canonical predicate; the two spellings must stay
    byte-identical until that facade line lands and the local one collapses
    into an import."""
    import persist.commit_place_graph as commit_place_graph
    import world.spatial_barriers as spatial_barriers

    assert getattr(commit_place_graph, "_ROUTE_MEMORY_BARRIERS") == \
        getattr(spatial_barriers, "_ROUTE_MEMORY_BARRIERS")
    # And the predicate answers exactly membership in that set.
    for barrier in getattr(spatial_barriers, "_VALID_BARRIERS"):
        assert spatial_barriers.route_memory_barrier(barrier) == (
            barrier in spatial_barriers._ROUTE_MEMORY_BARRIERS)
