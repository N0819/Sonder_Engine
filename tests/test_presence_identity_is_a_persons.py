"""An object's name is not an identity, and the noun cannot settle which is which.

Live, chat 82 t1. The player's own view of her own cell read:

    You are in Intake Interview Cell — Subject Side. the unfamiliar person
    powered on and functional. Reality-bending ability is suppressed...

The room note says "Scranton Reality Anchors powered on and functional". The
array is a wall-mounted suppression fixture; it was tracked as a background
presence, entered the identity space as a body whose name must be withheld,
and — having no appearance to build a descriptor from — fell to the same
fallback label as the security guard who actually spoke that beat. One label,
two subjects, one of them a machine bolted to the wall of the room she is
restrained in.

`background_presences` answers "might this thing act?", and its kind filter is
generous both ways ON PURPOSE, so a sentient robot tagged `device` is never
dropped. The identity floor asks a different question — whose name is theirs to
give — and the generous answer is wrong for it.

THE NOUN CANNOT SEPARATE THEM. Measured across the corpus, 16 presences resolve
`undecided`: 14 machines (`device`, `transit_car`, `body_interior`) and 2
Daleks (`dalek war machine`). `commit_background`'s own docstring says so in as
many words. What separates them is CONDUCT, which is this engine's standard of
proof everywhere else: the two Daleks are the only ones that have ever spoken
(2 and 10 dialogue turns, against 0 for every machine).
"""

from __future__ import annotations

from persist.commit import presence_has_an_identity, presence_personhood

CELL = {
    "entities": {
        "Scranton Reality Anchors": {"name": "Scranton Reality Anchors",
                                     "kind": "device"},
        "Site Security Guard 2": {"name": "Site Security Guard 2",
                                  "kind": "character"},
        "Interview Chair": {"name": "Interview Chair", "kind": "fixture"},
        "dalek_1": {"name": "A Dalek", "kind": "dalek war machine"},
    },
}


def _rec(spoke=0):
    return {"dialogue_turns": list(range(spoke)), "mention_turns": [1]}


def test_a_person_keeps_their_name_protected():
    assert presence_has_an_identity(CELL, "Site Security Guard 2", _rec())


def test_a_declared_thing_has_no_identity_to_protect():
    assert not presence_has_an_identity(CELL, "Interview Chair", _rec())


def test_an_undecided_machine_that_never_spoke_has_no_identity():
    """The live case. `device` is deliberately absent from both kind lists so
    a sentient robot is never dropped from the SPEECH gate; that generosity
    put a wall array into the identity space."""
    assert presence_personhood(CELL, "Scranton Reality Anchors", _rec()) \
        == "undecided"
    assert not presence_has_an_identity(CELL, "Scranton Reality Anchors", _rec())


def test_an_undecided_body_that_has_spoken_keeps_its_identity():
    """Both live examples land in `undecided` together and only one of them is
    a person. Conduct is what tells them apart: a thing that has taken a turn
    at speech is acting as a person, whatever noun the model reached for."""
    assert presence_personhood(CELL, "A Dalek", _rec(spoke=2)) == "undecided"
    assert presence_has_an_identity(CELL, "A Dalek", _rec(spoke=2))


def test_a_presence_with_no_entity_record_is_a_person():
    """An unregistered body named in prose has no entity to judge, and the
    provenance is already person-shaped -- a speaker, or a placed body."""
    assert presence_has_an_identity(CELL, "the night clerk", _rec())


def test_the_two_gates_read_the_verdict_differently_on_purpose():
    """May this act (silence is cheap) is not is this name protected (a
    wrongly-protected name renders a machine as a person in the room's own
    description). Same verdict, opposite conservatism."""
    rec = _rec()
    assert presence_personhood(CELL, "Scranton Reality Anchors", rec) \
        == "undecided"
    assert not presence_has_an_identity(CELL, "Scranton Reality Anchors", rec)
