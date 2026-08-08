"""The provisional canon provenance tier (0a).

Each test names the defect it exists to refuse. Two of them exist purely to
stop a later tidy-up closing something that was left open on purpose.
"""

import pytest

from canon_provenance import (
    ADJUDICATED_DISPOSITIONS,
    KNOWN_SUBJECT_KINDS,
    PROVISIONAL,
    Subject,
    is_canon,
    may_assert_consequence,
    outranks,
    promote,
    unavailable,
    validate_provisional,
)


def record(**over):
    """A well-formed provisional record, overridable field by field."""

    base = {
        "disposition": PROVISIONAL,
        "subject": {"kind": "character", "id": "guinan_7f3a"},
        "base_turn": 12,
        "basis": "deterministic",
        "summary": "She was in the east wing.",
    }
    base.update(over)
    return base


def test_a_well_formed_provisional_record_validates():
    """The floor. Without this every other test could pass by refusing everything."""

    result = validate_provisional(record())
    assert result.ok, result.errors
    assert result.errors == []
    assert result.unknown_subject_kind is None


def test_the_subject_kind_vocabulary_is_open():
    """Without this, `kind` closes into a two-value enum and a crowd needs a migration.

    An unrecognised kind is ACCEPTED and reported. That is the contract.
    """

    result = validate_provisional(record(subject={"kind": "swarm", "id": "hive_04"}))
    assert result.ok, result.errors
    assert result.unknown_subject_kind == "swarm"
    assert result.warnings


def test_crowd_faction_room_and_place_are_all_spellable_today():
    """Without this, the four kinds the design already needs are only a comment."""

    for kind in ("crowd", "faction", "room", "place"):
        assert kind in KNOWN_SUBJECT_KINDS
        result = validate_provisional(record(subject={"kind": kind, "id": "east_wing"}))
        assert result.ok, (kind, result.errors)
        assert result.unknown_subject_kind is None
        assert result.warnings == []


def test_the_low_tier_does_not_assume_its_subject_is_a_person():
    """A room subject and a crowd subject validate exactly as a character does.

    Without this the tier can quietly acquire a person-shaped assumption and
    nothing catches it until a crowd is minted.
    """

    person = validate_provisional(record(subject={"kind": "character", "id": "guinan_7f3a"}))
    room = validate_provisional(record(subject={"kind": "room", "id": "east_wing"}))
    crowd = validate_provisional(record(subject={"kind": "crowd", "id": "market_throng"}))
    assert person.ok and room.ok and crowd.ok
    assert person.errors == room.errors == crowd.errors == []


def test_a_display_name_may_not_be_used_as_the_subject_id():
    """'A Dalek', 'Dalek' and 'The Dalek' were three presences and one being.

    Without this the tier inherits the key space that produced them.
    """

    result = validate_provisional(record(subject={"kind": "character", "id": "The Dalek"}))
    assert not result.ok
    assert any("not an id" in e for e in result.errors)


def test_an_id_that_is_just_the_display_name_again_is_refused():
    """A lowercased display name passes the slug shape; this is the second gate."""

    result = validate_provisional(
        record(subject={"kind": "character", "id": "guinan", "display": "Guinan"})
    )
    assert not result.ok
    assert any("display" in e for e in result.errors)


def test_a_room_named_in_prose_is_refused_on_the_write_path():
    """The one offscreen_log row ever written places its actor in 'a quiet office'.

    Without this the tier stores rooms the scene graph does not contain, and no
    read-path filter can undo that afterwards.
    """

    result = validate_provisional(record(about={"room": "a quiet office"}))
    assert not result.ok
    assert any("quiet office" in e for e in result.errors)

    moved = validate_provisional(
        record(moves=[{"turn": 4, "from_room": "east_wing", "to_room": "the long gallery"}])
    )
    assert not moved.ok


def test_base_turn_is_required():
    """Without the stamp there is no way to tell a stale tick from a current one,
    which is the guard 0b exists to make possible."""

    missing = dict(record())
    missing.pop("base_turn")
    assert not validate_provisional(missing).ok
    assert not validate_provisional(record(base_turn=-1)).ok
    assert not validate_provisional(record(base_turn="12")).ok


def test_the_provisional_tier_may_describe_but_may_not_commit():
    """Without this the cheap rung becomes an unadjudicated authoring channel --
    the same failure as a villain declaring victory offscreen, through the back
    door and harder to see."""

    assert not validate_provisional(record(deltas={"trust": -0.2})).ok
    assert not validate_provisional(record(standing_intentions=[{"who": "x"}])).ok
    assert not validate_provisional(record(ratified_claims=["the east wing burned"])).ok
    assert not may_assert_consequence(PROVISIONAL)
    assert may_assert_consequence("resolved_fact")


def test_an_event_with_an_id_is_a_consequence_and_is_refused():
    """Describing an event is allowed; minting one that downstream code can cite
    is not. Without this the shape difference between rungs is only a comment."""

    ok = validate_provisional(record(events=[{"turn": 3, "summary": "the market closed"}]))
    assert ok.ok, ok.errors
    bad = validate_provisional(
        record(events=[{"turn": 3, "event_id": "ev_9", "summary": "the market closed"}])
    )
    assert not bad.ok


def test_unavailable_must_say_why():
    """Silence is how the abort path made a crash and a closed tab
    indistinguishable. Without this the tier repeats it."""

    with pytest.raises(ValueError):
        unavailable(Subject("room", "east_wing"), 3, "   ")

    rec = unavailable(Subject("room", "east_wing"), 3, "no positions recorded since turn 3")
    assert validate_provisional(rec).ok

    assert not validate_provisional(record(basis="unavailable")).ok


def test_provisional_is_below_everything_and_the_seven_are_not_ranked():
    """Without the second half, a ranking nobody decided gets invented by the
    first caller who needs one and is then depended upon."""

    for other in ADJUDICATED_DISPOSITIONS:
        assert outranks(other, PROVISIONAL) is True
        assert outranks(PROVISIONAL, other) is False
        assert is_canon(other)
    assert not is_canon(PROVISIONAL)
    assert outranks("resolved_fact", "character_belief") is None
    assert outranks(PROVISIONAL, PROVISIONAL) is False
    assert outranks("nonsense", PROVISIONAL) is None


def test_promotion_is_a_named_seam_and_is_not_implemented_here():
    """Without this the seam can be quietly filled in by whatever needs it first,
    which is how the Director boundary gets touched without anyone deciding to."""

    with pytest.raises(NotImplementedError) as excinfo:
        promote(record(), "resolved_fact", adjudicator="director")
    assert "settle_claims" in str(excinfo.value)
