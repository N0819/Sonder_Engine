"""A mind is never a stranger to itself, under either of its names.

`_delivery_ok` is the unified delivery gate, and its first substantive line
is the self-exemption: an observer always receives its own conduct. That line
asked `observer_name == source_name`, a bare string comparison, in the file
whose own `region_visibility` sits 1,800 lines above it using `same_subject`
for exactly this question and saying why: "a being routinely carries a display
name and an entity id at once".

The miss direction is closed rather than open -- a body whose two spellings do
not match `==` is denied its OWN percept, not handed someone else's -- so this
is the `_self_cannot_see_own_surface` class rather than a leak. It bites the
moment either side of the call resolves the other spelling, and it bites
hardest exactly where the self-exemption matters most: a body sealed inside
something is concealed from every subject in the scene, itself included, once
the `==` has failed to recognise it.
"""

from __future__ import annotations

from agents.common import _delivery_ok


HOLDER = "Satchel"


def _scene():
    """One body, two live spellings: entity id `ada_01`, display name `Ada`.

    `spatial_identity.canonical_subject_map` deliberately declines to fold a
    lone entity-id key, so a scene carrying the pair is the ordinary case, not
    a malformed one.
    """
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {"ada_01": "hall", HOLDER: "hall"},
        "contained": {"ada_01": {"in": HOLDER, "mode": "container"}},
        "entities": {
            "ada_01": {"name": "Ada", "kind": "person"},
            HOLDER: {"name": HOLDER, "kind": "object"},
        },
    }


def _rel():
    return {"same_room": True, "barrier": "open", "distance": "same",
            "light": "lit"}


def test_a_body_receives_its_own_conduct_across_its_two_spellings():
    assert _delivery_ok(_rel(), _scene(), "Ada", "ada_01", "sight")
    assert _delivery_ok(_rel(), _scene(), "ada_01", "Ada", "hearing")


def test_the_self_exemption_still_holds_for_one_spelling():
    assert _delivery_ok(_rel(), _scene(), "Ada", "Ada", "sight")
    assert _delivery_ok(_rel(), _scene(), "ada_01", "ada_01", "hearing")


def test_two_different_beings_are_still_two_beings():
    """The negative control: the wider identity test must not merge anyone."""
    sc = _scene()
    sc["entities"]["cass_01"] = {"name": "Cass", "kind": "person"}
    sc["positions"]["cass_01"] = "hall"
    assert not _delivery_ok(_rel(), sc, "Cass", "ada_01", "sight")


def test_a_non_awake_mind_still_receives_nothing_from_itself():
    """Awareness outranks the self-exemption and must keep doing so."""
    assert not _delivery_ok(_rel(), _scene(), "Ada", "ada_01", "sight",
                            awareness="asleep")
