"""A room full of people presents at least one person you can speak to.

The crowd presentation is texture and should stay texture -- nobody reads six
names off a forge. What it may not do is leave an observer with nobody: a body
visibly working in front of you is a body you could address, and before this
the subtraction handed every member of a crowd to the band and stopped.

Measured, two_lives v5 (2026-09-19): Sal Weatherby spent nine beats in
Aldermill Forge holding six charter smiths, her own pose reading "watching the
strikers and tong-holder at the central anvil", and her view said "a handful of
journeymans and apprentices" with `perception_act.company` empty. Zero speech
from anyone in that town across thirty beats. The inversion is what marks it a
defect rather than a budget: the more people a room held, the fewer of them
could answer.
"""

from __future__ import annotations

from world import charter_crowd, crowds


def _forge(**over):
    """Six smiths of one institution in one room -- v5's forge, in
    `agents.common.chatter_inputs`' slice shape."""
    base = {
        "key": "smithy",
        "bodies": {
            "b%d" % n: {"key": "b%d" % n, "name": "Smith%d" % n,
                        "place": "forge", "home_post": "journeyman"}
            for n in range(1, 7)
        },
        "watch": {"master": "b1"},
        "posts": {"master": {"place": "forge", "serves": []},
                  "journeyman": {"place": "forge", "serves": []}},
        "naming": None,
        "figures": {},
        "known_bodies": frozenset(),
        "bindings": frozenset(),
        "feel": {},
    }
    base.update(over)
    return base


class TestTheFaceIsOneMemberAndAlwaysTheSameOne:
    def test_a_crowd_fronts_somebody(self):
        members = charter_crowd.members_of(_forge(), "forge")
        assert len(members) == 6
        assert charter_crowd.crowd_face(_forge(), members) in members

    def test_the_face_is_whoever_has_attention_to_spare(self):
        """Strain is the engine's own quantity for how loaded a body is; the
        one not swinging a hammer is the one who looks up."""
        feel = {"b1": {"stress": {"strain": 0.9}},
                "b2": {"stress": {"strain": 0.8}},
                "b4": {"stress": {"strain": 0.1}}}
        held = _forge(feel=feel)
        members = charter_crowd.members_of(held, "forge")
        # b3, b5, b6 carry no strain at all -- less loaded than b4's 0.1.
        assert charter_crowd.crowd_face(held, members, feel) == "b3"
        # And with everyone equally loaded it is still ONE stable answer.
        assert charter_crowd.crowd_face(
            _forge(), members, {}) == charter_crowd.crowd_face(
                _forge(), list(reversed(members)), {})

    def test_an_empty_membership_fronts_nobody(self):
        assert charter_crowd.crowd_face(_forge(), []) == ""
        assert charter_crowd.crowd_face(_forge(), None) == ""


class TestTheBandDescribesWhatItStillCarries:
    def test_the_floor_is_the_rooms_headcount_not_the_carried_count(self):
        """A room of exactly `CHARTER_CROWD_FLOOR` people is still a crowd
        with one of them turned around -- the face must not flip the whole
        institution out of its band at the boundary."""
        held = _forge(bindings=frozenset({"b4", "b5", "b6"}))
        members = charter_crowd.members_of(held, "forge")
        assert len(members) == crowds.CHARTER_CROWD_FLOOR
        crowd = charter_crowd.crowd_for(
            1, held, "forge", members,
            fronted=charter_crowd.crowd_face(held, members))
        assert crowd is not None

    def test_nobody_is_presented_twice(self):
        """The band counts the bodies it carries, not the fronted one."""
        held = _forge()
        members = charter_crowd.members_of(held, "forge")
        face = charter_crowd.crowd_face(held, members)
        crowd = charter_crowd.crowd_for(1, held, "forge", members,
                                        fronted=face)
        alone = charter_crowd.crowd_for(
            1, held, "forge", [m for m in members if m != face])
        assert crowd["band"] == alone["band"]

    def test_fronting_the_only_member_is_not_a_crowd(self):
        crowd = charter_crowd.crowd_for(1, _forge(), "forge", ["b1"],
                                        fronted="b1")
        assert crowd is None


class TestTheBandSaysItInEnglish:
    def test_a_post_ending_in_man_pluralises(self):
        """"journeymans and masters" was a forge describing itself (v5).
        A suffix inflection, so it needs no vocabulary of nouns."""
        held = _forge()
        members = charter_crowd.members_of(held, "forge")
        assert "journeymen" in charter_crowd.composition_of(members, held)
        assert "journeymans" not in charter_crowd.composition_of(members, held)


def test_a_body_the_scene_stands_is_never_ground():
    """Playerless Aldermill round 6 (2026-09-23): three peace duties leased
    and named on screen were folded into "a handful of manor peace duties",
    which hid two of their acts."""
    forge = _forge()
    body_key = sorted(forge["bodies"])[0]
    forge["bodies"][body_key] = dict(forge["bodies"][body_key], leased="frame:2")
    assert body_key not in charter_crowd.members_of(forge, "forge")


def test_a_regular_plural_is_spelled_right():
    assert charter_crowd._plural("peace duty") == "peace duties"
    assert charter_crowd._plural("journeyman") == "journeymen"
    assert charter_crowd._plural("watch") == "watches"
    assert charter_crowd._plural("key") == "keys"
    assert charter_crowd._plural("clerks") == "clerks"
