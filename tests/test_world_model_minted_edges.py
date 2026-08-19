"""MASTER-024 / docs/UNBUILT.md 1.2: minting an edge deserves the care that
merging one already gets.

`_merge_room`'s upsert doctrine is scrupulous about never erasing an edge
field through silence, and a previously unseen edge was accepted verbatim
with no check at all -- measured as `r0204 <-> r0303`, a geometrically
impossible diagonal in a grid maze, standing in the world model for hundreds
of turns and walked as a real doorway. The check decidable everywhere lands
here: a new passable edge cannot one-sidedly unseal a standing wall -- the
exact reverse of `_shield_standing_passage`'s "sealing takes a two-sided
declaration", through the hole that shield could not see (the fresh reverse
direction).

Deliberately NOT here: geometry (no coordinates exist in the model to check
against); a required BASIS for a brand-new adjacency between known rooms (a
schema-and-prompt change across the mapping and spatial specialists); and
target-room EXISTENCE -- a dangling edge is a tolerated forward reference
(the west-wing mapping flow pinned at tests/test_spatial.py's redeclaration
test mints the corridor's edge before the room exists). All three remain in
docs/UNBUILT.md 1.2.
"""

from __future__ import annotations

from world.spatial import merge_scene_with_diff


def _scene():
    return {
        "rooms": {
            "cell": {"name": "Cell", "adjacent": [
                {"to": "lobby", "barrier": "wall"}]},
            "lobby": {"name": "Lobby", "adjacent": [
                {"to": "hall", "barrier": "open"}]},
            "hall": {"name": "Hall", "adjacent": [
                {"to": "lobby", "barrier": "open"}]},
        },
        "positions": {}, "entities": {}, "attire": {}, "overlays": {},
    }


def _edges(merged, room):
    return {str(e["to"]): e for e in merged["rooms"][room]["adjacent"]
            if isinstance(e, dict) and e.get("to")}


class TestWhatStillLands:
    def test_an_edge_to_a_room_minted_by_the_same_diff_lands(self):
        merged = merge_scene_with_diff(_scene(), {"rooms": {
            "hall": {"adjacent": [{"to": "annex", "barrier": "open"}]},
            "annex": {"name": "Annex", "adjacent": [
                {"to": "hall", "barrier": "open"}]},
        }})
        assert "annex" in _edges(merged, "hall")
        assert "hall" in _edges(merged, "annex")

    def test_a_new_edge_between_standing_rooms_still_lands(self):
        """No basis requirement yet (scoped out, docs/UNBUILT.md 1.2): a new
        adjacency between two real rooms with no standing contradiction is
        accepted as before."""
        merged = merge_scene_with_diff(_scene(), {"rooms": {
            "hall": {"adjacent": [
                {"to": "cell", "barrier": "closed_door"}]}}})
        assert "cell" in _edges(merged, "hall")


class TestUnsealingIsTwoSided:
    def test_a_fresh_reverse_edge_cannot_open_a_standing_wall(self):
        """`cell -> lobby` stands as wall and `lobby` declares nothing back;
        a minted `lobby -> cell: open` would create passage through the wall
        one-sidedly, because every walk crosses an edge either side
        declares."""
        merged = merge_scene_with_diff(_scene(), {"rooms": {
            "lobby": {"adjacent": [{"to": "cell", "barrier": "open"}]}}})
        assert "cell" not in _edges(merged, "lobby")
        # The standing seal is untouched.
        assert _edges(merged, "cell")["lobby"]["barrier"] == "wall"

    def test_a_two_sided_declaration_does_open_it(self):
        merged = merge_scene_with_diff(_scene(), {"rooms": {
            "cell": {"adjacent": [{"to": "lobby", "barrier": "open_door"}]},
            "lobby": {"adjacent": [{"to": "cell", "barrier": "open_door"}]},
        }})
        assert _edges(merged, "lobby")["cell"]["barrier"] == "open_door"
        assert _edges(merged, "cell")["lobby"]["barrier"] == "open_door"

    def test_a_new_impassable_reverse_edge_is_not_passage(self):
        """A minted `lobby -> cell: window` grants no passage, so it is not
        an unsealing and may land -- the pair stays visible-but-sealed."""
        merged = merge_scene_with_diff(_scene(), {"rooms": {
            "lobby": {"adjacent": [{"to": "cell", "barrier": "window"}]}}})
        assert _edges(merged, "lobby")["cell"]["barrier"] == "window"

    def test_a_standing_closed_door_is_still_openable_from_either_side(self):
        """Scoped to `wall` exactly as the sealing shield is: opening a door
        is an ordinary act, declared from whichever side the actor stands."""
        scene = _scene()
        scene["rooms"]["cell"]["adjacent"] = [
            {"to": "lobby", "barrier": "closed_door"}]
        merged = merge_scene_with_diff(scene, {"rooms": {
            "lobby": {"adjacent": [{"to": "cell", "barrier": "open_door"}]}}})
        assert _edges(merged, "lobby")["cell"]["barrier"] == "open_door"


class TestUpsertTerritoryIsUntouched:
    def test_redeclaring_a_known_edge_still_merges_fields(self):
        merged = merge_scene_with_diff(_scene(), {"rooms": {
            "lobby": {"adjacent": [
                {"to": "hall", "barrier": "closed_door"}]}}})
        assert _edges(merged, "lobby")["hall"]["barrier"] == "closed_door"

    def test_a_barrier_change_on_an_existing_wall_edge_is_not_minting(self):
        """Changing `cell -> lobby` ITSELF (the side that holds the wall) is
        an ordinary upsert on a standing edge, not a mint, and lands."""
        merged = merge_scene_with_diff(_scene(), {"rooms": {
            "cell": {"adjacent": [
                {"to": "lobby", "barrier": "open_door"}]}}})
        assert _edges(merged, "cell")["lobby"]["barrier"] == "open_door"
