"""A dead bridge is silent, so the engine says when it is certainly dead.

`agents/background.py` asks which charter bodies are near by handing the
player's ROOM id to `background_presence_records`, which filters bodies by
charter PLACE. The two are independent vocabularies and nothing establishes a
correspondence between them.

Measured on chat 84 -- the only chat in the corpus where the charter system ran
past a single turn (14 turns, 37 bodies, 36 minds, 42 practices): the scene's
four rooms and the registry's nine places shared ZERO ids. So every lookup
returned nothing, always, and 37 simulated people were unreachable by anyone
for the whole run. The subsystem read as unexercised; it was a namespace
mismatch, and the one place that could have reported it swallowed its own
failures in a bare `except`.

The diagnostic fires only on the unambiguous case -- both sides populated, no
id in common -- because there is no story in which a populated institution and
a populated scene legitimately share no ground.
"""
import pytest

from world.charter_runtime import charter_place_ids


class TestTheHelperReadsEveryPlaceTheRegistryKnows:
    """`charter_place_ids` exists so a caller can tell 'nobody is here' from
    'nobody could ever be here'."""

    def _registry(self, monkeypatch, items):
        import world.charter_runtime as cr
        monkeypatch.setattr(cr, "registry_for",
                            lambda cid, frame_id=None: {"items": items})

    def test_it_reads_active_places(self, monkeypatch):
        self._registry(monkeypatch, {"site": {"state": {
            "active_places": ["staff_canteen", "research_lab"]}}})
        assert charter_place_ids(1) == {"staff_canteen", "research_lab"}

    def test_it_also_reads_where_bodies_actually_stand(self, monkeypatch):
        """A body may stand somewhere `active_places` does not list -- chat 84
        had bodies at `security_post`, which is not among its nine places."""
        self._registry(monkeypatch, {"site": {"state": {
            "active_places": ["staff_canteen"],
            "bodies": {"k": {"place": "security_post", "berth": "bunkroom"}}}}})
        assert charter_place_ids(1) == {"staff_canteen", "security_post",
                                        "bunkroom"}

    def test_a_malformed_registry_yields_nothing_rather_than_raising(
            self, monkeypatch):
        """It backs a diagnostic. It must never be why a beat fails."""
        import world.charter_runtime as cr

        def boom(cid, frame_id=None):
            raise RuntimeError("registry unreadable")

        monkeypatch.setattr(cr, "registry_for", boom)
        assert charter_place_ids(1) == set()

    def test_an_empty_registry_is_an_empty_set_not_an_error(self, monkeypatch):
        self._registry(monkeypatch, {})
        assert charter_place_ids(1) == set()


class TestItCannotFireFalsely:
    """The entire justification for adding this. If it can cry wolf it is
    worse than the silence it replaces."""

    def _fires(self, known, places):
        """The predicate exactly as background.py applies it."""
        return bool(known) and bool(places) and not (known & set(places))

    def test_the_measured_case_fires(self):
        """chat 84: four scene rooms, nine charter places, no overlap."""
        known = {"ethics_office", "personnel_office", "psych_office",
                 "research_lab", "scp073_area", "scp105_area", "scp343_area",
                 "scp999_area", "staff_canteen"}
        rooms = {"observation_room", "interview_cell", "elevator_hall",
                 "hallway_floor1"}
        assert self._fires(known, rooms)

    def test_one_shared_id_is_enough_to_stay_quiet(self):
        """A single room named for a charter place means the bridge is alive,
        whether or not anyone is standing there this beat."""
        assert not self._fires({"staff_canteen", "research_lab"},
                               {"hallway_floor1", "staff_canteen"})

    def test_a_chat_with_no_charters_never_fires(self):
        """Most chats have no institution at all. They are not misconfigured."""
        assert not self._fires(set(), {"interview_cell"})

    def test_a_beat_with_no_room_in_scope_never_fires(self):
        """Absence of a player room is not evidence of a mismatch."""
        assert not self._fires({"staff_canteen"}, set())

    def test_both_empty_never_fires(self):
        assert not self._fires(set(), set())
