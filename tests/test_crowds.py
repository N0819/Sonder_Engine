"""A crowd is one object with many people in it.

A market square with forty people cannot be represented today: `max_managed`
defaults to 6 and is hard-capped at 8, so a populous place either eats the
whole manager budget or is silently absent. Chat 57 spent three of those six
slots on ONE Dalek, split three ways by its article. `scene.py` has said the
answer in prose since before this module existed — "past that, a crowd is
better represented as one chorus presence than as several individually-voiced
extras" — and never had an object.

These pin the three decisions everything else rests on: the count is a band,
the density is derived, and the id is not a name.
"""

from __future__ import annotations

import pytest

import crowds


class TestTheCountIsABand:
    def test_an_unknown_band_reads_as_fewer_people_not_more(self):
        """Over-claiming a throng puts bodies in a room nothing authored. The
        engine should under-populate when it cannot tell."""
        assert crowds.normalize_band("forty-ish") == crowds.BANDS[0]
        assert crowds.normalize_band(None) == crowds.BANDS[0]

    def test_splitting_is_band_preserving_not_count_preserving(self):
        """"A few dozen" toward two exits gives "a dozen or so" twice. No
        arithmetic, so no conservation bookkeeping and no drift — the moment
        two sources disagree about whether 37 became 34 there is a
        contradiction with no resolution."""
        assert crowds.split_band("a few dozen") == "a dozen or so"
        assert crowds.split_band("a throng") == "a few dozen"

    def test_the_smallest_band_does_not_divide(self):
        """A handful that splits is two things the story has no word for."""
        assert crowds.split_band("a handful") is None


class TestDensityIsDerivedFromTheRoom:
    def test_the_room_releases_you_not_the_crowd(self):
        """The property worth having. The same crowd is a crush in a gate
        passage and loose in the square beyond — the escape that was
        impossible becomes available because the geometry changed and nothing
        else did."""
        assert crowds.density("a few dozen", "small") == crowds.CRUSH
        assert crowds.density("a few dozen", "large") == crowds.LOOSE

    def test_equal_ranks_are_packed(self):
        assert crowds.density("a few dozen", "medium") == crowds.PACKED

    def test_an_unsized_room_is_medium_not_missing(self):
        """66 of the live corpus's rooms leave `size` unset, and an unsized
        room is the commonest room. A crowd that vanished in one would be a
        worse answer than a crowd of ordinary density."""
        assert crowds.density("a few dozen", None) == \
            crowds.density("a few dozen", "medium")

    def test_density_is_never_stored_on_the_object(self):
        """A stored density is a second source of truth that drifts the moment
        the crowd moves — the `wearing`/`state`/`regions` scar, which this
        module is written after rather than before."""
        crowd = crowds.new_crowd(1, "square", band="a throng",
                                 composition="dockworkers", since_turn=3)
        assert "density" not in crowd

    def test_the_travel_cost_table_is_not_a_size_rank(self):
        """`spatial._ROOM_COST` looks like this rank and is not: it collapses
        tiny, small, "" and medium all to 1 because it prices WALKING. Reusing
        it would make a crush in a broom cupboard read like one in a hall."""
        from spatial import _ROOM_COST
        assert _ROOM_COST["tiny"] == _ROOM_COST["medium"]
        assert crowds.room_size_rank("tiny") != crowds.room_size_rank("medium")


class TestIdentity:
    def test_the_id_is_not_a_display_name(self):
        """Five ledgers already key beings by display name and it is one
        defect, not five. A new writer into the wrong key space is exactly
        what subject identity exists to stop."""
        crowd = crowds.new_crowd(1, "square", band="a throng",
                                 composition="dockworkers", since_turn=3)
        assert crowd["uid"].startswith("crowd:")
        assert "dockworkers" not in crowd["uid"]

    def test_the_same_crowd_mints_the_same_id(self):
        args = dict(band="a throng", composition="dockworkers", since_turn=3)
        assert crowds.new_crowd(1, "square", **args)["uid"] == \
            crowds.new_crowd(1, "square", **args)["uid"]

    def test_a_different_room_is_a_different_crowd(self):
        args = dict(band="a throng", composition="dockworkers", since_turn=3)
        assert crowds.new_crowd(1, "square", **args)["uid"] != \
            crowds.new_crowd(1, "gate", **args)["uid"]


def test_a_crowd_murmurs_and_does_not_speak():
    """Anyone who speaks has emerged and is no longer part of the crowd, so
    the description is a phrase an observer registers — never a line."""
    crowd = crowds.new_crowd(1, "gate", band="a few dozen",
                             composition="dockworkers and ferry passengers",
                             since_turn=3, mood="restless")
    text = crowds.describe(crowd, "small")
    assert "a few dozen dockworkers" in text
    assert "shoulder to shoulder" in text  # small room -> crush
    assert "restless" in text
    assert '"' not in text


def test_crowds_in_room_is_stable_and_scoped():
    a = crowds.new_crowd(1, "square", band="a throng", composition="x", since_turn=1)
    b = crowds.new_crowd(1, "gate", band="a handful", composition="y", since_turn=1)
    assert [c["uid"] for c in crowds.crowds_in_room([a, b], "square")] == [a["uid"]]
    assert crowds.crowds_in_room([a, b], "") == []


# --- the perception surface --------------------------------------------------

class TestACrowdIsVisibleWithoutCostingASlot:
    """The whole reason the object exists. `max_managed` defaults to 6 and is
    hard-capped at 8; a crowd that consumed one of those slots would have
    solved nothing.
    """

    def _story(self, temp_db):
        import time
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Crowd", "", time.time()))
        scene = {
            "location": "Priestella",
            "rooms": {"gate": {"name": "Watergate", "size": "small"},
                      "square": {"name": "Square", "size": "large"},
                      "office": {"name": "Back Office", "size": "small"}},
            "positions": {},
        }
        crowd = crowds.new_crowd(cid, "gate", band="a few dozen",
                                 composition="dockworkers", since_turn=1,
                                 mood="restless")
        temp_db.wset(cid, "crowds", [crowd])
        return cid, scene

    def test_an_observer_in_the_room_registers_it(self, temp_db):
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        seen = crowds_for_room(cid, scene, "gate")
        assert len(seen) == 1
        assert "dockworkers" in seen[0]["what"]

    def test_someone_in_a_back_office_learns_nothing_of_the_square(self, temp_db):
        """Per observer and room-scoped. A scene-wide list would hand someone
        behind a closed door the state of the crowd outside."""
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        assert crowds_for_room(cid, scene, "office") == []

    def test_density_follows_the_room_the_crowd_is_in_now(self, temp_db):
        """Recomputed at read, never read back from the object — the crowd may
        have walked into a different room since it was minted."""
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        assert crowds_for_room(cid, scene, "gate")[0]["density"] == crowds.CRUSH
        stored = temp_db.wget(cid, "crowds", [])
        stored[0]["room_uid"] = "square"
        temp_db.wset(cid, "crowds", stored)
        assert crowds_for_room(cid, scene, "square")[0]["density"] == crowds.LOOSE

    def test_the_ledger_is_frame_scoped(self):
        """A branch that never went to the market must not inherit its throng."""
        from db import FRAME_SCOPED_WORLD_KEYS
        assert "crowds" in FRAME_SCOPED_WORLD_KEYS

    def test_a_crowd_is_not_a_managed_presence(self, temp_db):
        """It must not appear in the presence ledger the manager budget counts."""
        cid, _scene = self._story(temp_db)
        assert not (temp_db.wget(cid, "background_presences", {}) or {})


# --- fixtures: the rule that separates them from emergences ------------------

class TestAFixtureMayBeReMet:
    """PROPOSAL_CROWDS.md §3a: "a fixture may be re-met; an emergence may not."

    `station_room` already existed and was used only to gate what a presence
    PERCEIVES. Nothing re-offered one when the player walked back into their
    room, so a tavern whose barkeep is only voiced when the Director happens to
    mention him is a tavern with nobody behind the bar on every quiet visit.
    Measured: 8 of 52 live presences carry a station_room and nothing re-met
    any of them.

    Being at your post is the WEAKEST qualifying signal — far weaker than being
    addressed — and `cap` still bounds the picks, so a busy room does not
    become a chorus.
    """

    def test_the_at_post_signal_exists_and_is_room_scoped(self):
        import inspect

        import commit
        body = inspect.getsource(commit.pick_background_reactors)
        assert "at_post" in body
        assert "station_room) == str(player_room" in body

    def test_it_qualifies_a_presence_that_nothing_else_would(self):
        """The whole point: no address, no mention, no owed reply, no history
        — just standing where they work."""
        import inspect

        import commit
        body = inspect.getsource(commit.pick_background_reactors)
        gate = body[body.index("if not (flow_addressed"):]
        assert "or at_post)" in gate.split("continue")[0]

    def test_standing_at_your_post_ranks_below_being_addressed(self):
        """A fixture must not outrank someone the player just spoke to."""
        import inspect

        import commit
        body = inspect.getsource(commit.pick_background_reactors)
        priority = body[body.index("priority = ("):body.index("candidates.append")]
        assert "at_post" not in priority.split("bool(addressed)")[0]
