"""What the HOST of a swallowed body is told, across the whole sequence.

`test_body_enclosure_channels.py` covers the occupant's side well -- twelve
tests on what a body inside another perceives. Almost nothing covered the
host's side, and every perception defect measured on 2026-08-29 landed
there: a body rendered in a phantom room, fifteen hundred characters of that
body's anatomy delivered through a closed throat, one smell said twice, an
enclosure named "your Mirelle's Mouth", a pose detail still holding somebody
two rooms after they left it, and a view that changed by one clause across
five turns of being swallowed.

TWO THINGS MAKE THIS TESTABLE CHEAPLY. Perception is deterministic -- there
is no model in it -- so a view composes straight from a stored scene. And
the defects were all DRIFT: state that stayed true after it stopped being
true. Each was individually plausible on the beat it was written, which is
why single-beat tests never caught one. So the fixture is a real sequence,
nine committed scenes from one swallow, and the assertions run across it.

The fixture is scene state only. It carries no prose the engine wrote, so a
change to how a view READS cannot make these pass or fail -- only a change
to which facts reach a mind can.
"""
import json
import os
import re

import pytest

from agents import composer
from agents import perception

FIXTURE = os.path.join(os.path.dirname(__file__),
                       "fixtures", "swallow_sequence.json")
HOST = "Mirelle Sulmirath"
OCCUPANT = "Hinami"
HER = {"subject": "she", "object": "her", "possessive": "her"}


def _sequence():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def _percepts(scene):
    """The host's own IR for one committed scene. No model, no database."""
    positions = scene.get("positions") or {}
    perceiver = {"room": positions.get(HOST), "pronouns": HER}
    others = [{"name": OCCUPANT, "room": positions.get(OCCUPANT)}]
    return perception._composer_standing_percepts(
        scene, perceiver, HOST, others, {OCCUPANT: OCCUPANT},
        {HOST: {OCCUPANT}}, prev_seen=set(),
        self_forms=(HOST,), self_pronouns=HER)


def _view(scene):
    rendered = composer.render_view(
        _percepts(scene), mode="character", full_render=True)
    return getattr(rendered, "text", rendered)


def _beats():
    return [(entry["turn"], entry["scene"]) for entry in _sequence()]


@pytest.fixture(scope="module")
def beats():
    return _beats()


def test_the_fixture_is_the_sequence_it_claims_to_be(beats):
    """Guards the guard: if the fixture stops containing a swallow, every
    assertion below still passes and none of them mean anything."""
    rooms = [(scene.get("positions") or {}).get(OCCUPANT) for _t, scene in beats]
    assert len(beats) >= 8
    assert rooms[0] == "private_session_room"
    assert any("mouth" in str(r) for r in rooms)
    assert any("throat" in str(r) for r in rooms)
    assert "stomach" in str(rooms[-1])


class TestSheIsNotToldWhereNobodyIs:
    def test_every_body_her_view_places_is_somewhere_real(self, beats):
        """A posture written into `positions` once minted a room and exiled a
        body into it, and her view then named that phrase as a place."""
        for turn, scene in beats:
            rooms = set(scene.get("rooms") or {})
            for name, room in (scene.get("positions") or {}).items():
                if name in (scene.get("attire") or {}):
                    assert room in rooms, (
                        f"t{turn}: {name} stands in {room!r}, which is not a "
                        "room -- a relation to a body is `contained`, "
                        "`contacts`, `stations` or a pose")


class TestSheCannotSeeIntoHerself:
    def test_no_visual_anatomy_of_a_body_inside_her(self, beats):
        """The occupant's exposed regions reached her view in full -- torso,
        arms, waist, groin, legs, feet -- while the occupant was inside a
        closed throat. Her OWN body is exempt: a body always has a channel
        to itself."""
        for turn, scene in beats:
            room = (scene.get("positions") or {}).get(OCCUPANT) or ""
            if HOST not in str(room):
                continue                    # not inside her yet
            for percept in _percepts(scene):
                if percept.channel != "sight":
                    continue
                label = str(getattr(percept, "source_label", "") or "")
                assert OCCUPANT not in label, (
                    f"t{turn}: a sight percept of {OCCUPANT} reached the host "
                    f"while they were in {room!r}")

    def test_she_still_perceives_her_own_body(self, beats):
        """The inverse, so the test above cannot be satisfied by delivering
        nothing at all."""
        _turn, scene = beats[-1]
        assert "your" in _view(scene).casefold()


class TestOneFactIsSaidOnce:
    def test_no_sentence_is_repeated_within_a_view(self, beats):
        for turn, scene in beats:
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", _view(scene))
                         if len(s.strip()) > 25]
            seen = set()
            for sentence in sentences:
                assert sentence not in seen, (
                    f"t{turn}: her view says this twice: {sentence[:70]!r}")
                seen.add(sentence)


class TestAnEnclosureIsNamedOnce:
    def test_no_doubled_possessive_on_an_interior(self, beats):
        """`target_interior` carries whatever the fiction called the place,
        and a Director that minted a room writes the ROOM'S NAME -- owner
        included. Wrapping the standard possessive round that says it twice."""
        for turn, scene in beats:
            view = _view(scene)
            assert f"your {HOST}" not in view, f"t{turn}: {view[:120]!r}"
            assert f"{HOST}'s {HOST}" not in view, f"t{turn}: {view[:120]!r}"
            for owned in re.findall(r"your ([A-Z][a-z]+(?:'s)?)", view):
                assert not owned.endswith("'s"), (
                    f"t{turn}: doubled possessive {owned!r}")


class TestProseDoesNotOutliveTheFactItStates:
    """A `detail` is the one scene field nothing re-derives. Saying a body is
    HELD is a claim about where that body is, and where a body is belongs to
    `positions` -- so `invalidate_moved_body_pose_details` retires the clause
    when the body moves."""

    @staticmethod
    def _carriage(detail):
        from world.spatial import _CONTACT_BOUND_POSE_WORDS
        words = set(re.findall(r"[a-z']+", str(detail or "").casefold()))
        return bool(words & _CONTACT_BOUND_POSE_WORDS)

    def test_a_named_body_that_moves_loses_its_carriage_clause(self, beats):
        """Asked with the production predicate rather than a lookalike, so
        this measures the shipped rule and not a second implementation."""
        from world.spatial import _detail_names_subject
        previous = None
        for turn, scene in beats:
            positions = scene.get("positions") or {}
            if previous is not None:
                was, now = previous.get(OCCUPANT), positions.get(OCCUPANT)
                detail = ((scene.get("poses") or {}).get(HOST)
                          or {}).get("detail") or ""
                if (was and now and was != now and self._carriage(detail)
                        and _detail_names_subject(scene, detail, OCCUPANT)):
                    pytest.fail(
                        f"t{turn}: {OCCUPANT} moved {was} -> {now} and the "
                        f"host's pose still holds them: {detail[:80]!r}")
            previous = positions

    def test_the_descriptor_case_is_a_known_hole(self, beats):
        """PINNED, NOT PASSED. On this real sequence the host's pose says
        "tongue curled around the little fox, holding her at the back of the
        mouth" -- and "the little fox" is the host's own coinage, in no name
        map and no alias list. So the rule above never fires on it, and the
        clause outlived two room changes in the live story.

        The naming is what the engine cannot do without either a vocabulary
        of descriptors or a model call, and this asserts the CURRENT limit so
        that closing it is a visible change rather than a silent one. If this
        test starts failing, the hole has been closed and it should be
        deleted along with this docstring."""
        previous, unnamed = None, 0
        for _turn, scene in beats:
            positions = scene.get("positions") or {}
            if previous is not None:
                was, now = previous.get(OCCUPANT), positions.get(OCCUPANT)
                detail = ((scene.get("poses") or {}).get(HOST)
                          or {}).get("detail") or ""
                if (was and now and was != now and self._carriage(detail)
                        and OCCUPANT.casefold() not in detail.casefold()):
                    unnamed += 1
            previous = positions
        assert unnamed >= 1, (
            "the fixture no longer contains a carriage clause that refers to "
            "the moved body by descriptor -- if the data changed, this test "
            "is measuring nothing")


class TestTheFirewallFromTheHostsSide:
    def test_no_interoception_of_another_body_reaches_her(self, beats):
        """The one that must never fail. Interoception is a body's own
        channel; a percept on it whose source is somebody else is a leak, and
        a leak is an engine failure rather than a model's."""
        for turn, scene in beats:
            for percept in _percepts(scene):
                if percept.channel != "interoception":
                    continue
                label = str(getattr(percept, "source_label", "") or "")
                assert OCCUPANT not in label, (
                    f"t{turn}: {OCCUPANT}'s interoception reached the host")

    # A SECOND TEST STOOD HERE and asserted the occupant's pose `detail`
    # never reached the host. It was wrong about the boundary, not about the
    # code: a pose detail is OBSERVABLE ARRANGEMENT -- how a body lies, that
    # it is coated in saliva, that its tails are fluffed -- and delivering it
    # to anyone who can see the body is what `pose_percepts` is for. It fired
    # on the one beat where the occupant was lying in plain sight on the
    # host's palm, which is exactly when the host should have it.
    #
    # WHAT IS ACTUALLY PRIVATE -- hedonic state, wants, the undercurrent, a
    # suppressed want, mind models -- is not in a scene blob at all. It lives
    # in `chat_chars.state`, so a scene fixture cannot test that leak and
    # should not pretend to. The interoception-channel test above is the part
    # of the firewall this fixture can genuinely hold; the rest belongs with
    # the adversarial perception and self-knowledge suites, which own it.
