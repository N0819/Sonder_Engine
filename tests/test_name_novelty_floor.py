"""A name assembled out of somebody is still that somebody's name.

Every other guard in `charter_identity` refuses a name the mint RECOGNISES --
the whole name, a component, an address form. This one refuses a name it BUILT
from recognisable pieces, which is the failure no reservation can reach:
measured 2026-08-28, 78.5% of the surnames this engine's extension lane could
reach shared a run of four or more characters in order with a real person's
surname, and the lane regenerated one canon surname verbatim.

The floors are the owner's, ruled 2026-08-28: longest common substring 4,
shared-prefix veto 4.
"""
from __future__ import annotations

from world.charter_identity import (NAME_PREFIX_FLOOR, NAME_RUN_FLOOR,
                                    identity_reservation,
                                    reconstructs_a_reserved_name)

CAST = ["Jean-Luc Picard", "Beverly Crusher", "Reginald Barclay",
        "Katherine Pulaski"]


def _reservation():
    return identity_reservation(CAST)


def test_a_name_rebuilt_from_two_people_is_refused():
    """THE CASE A DISTANCE METRIC CANNOT SEE. Edit distance measures closeness
    to the nearest SINGLE name, and a mashup is recognisable precisely because
    it is close to two at once -- `Crulaski` is far enough from `Pulaski` to
    pass any published threshold while being unmistakably made of it."""
    assert reconstructs_a_reserved_name("Crulaski", _reservation())


def test_an_exact_share_is_left_to_the_guards_that_own_it():
    """DIVISION OF LABOUR, and it is deliberate. A verbatim `Barclay` is the
    SHARING case, which this repo permits on purpose -- "a registered `Beverly
    Crusher` does not reserve every `Beverly` in the story; that would be an
    expansion, and shared given names are ordinary" -- and which the
    reservation and the pool subtraction decide under their own rules.

    This floor answers the opposite case: nobody SHARES `Crushen` with anybody,
    it was assembled out of somebody. Refusing exact matches here turned that
    documented permission off and failed five tests that exist to pin it.
    """
    assert not reconstructs_a_reserved_name("Barclay", _reservation())
    assert reconstructs_a_reserved_name("Barclayne", _reservation())


def test_a_shared_opening_is_refused_even_when_the_tail_diverges():
    """The front of a name is where recognisability lives."""
    assert reconstructs_a_reserved_name("Picarde", _reservation())
    assert reconstructs_a_reserved_name("Crushen", _reservation())


def test_an_ordinary_novel_name_passes():
    """The guard must not empty the world. These share nothing four characters
    long with anybody reserved."""
    for name in ("Kestrel", "Ondaatje", "Vasquez", "Okonkwo", "Lindqvist"):
        assert not reconstructs_a_reserved_name(name, _reservation()), name


def test_a_short_shared_cluster_is_phonology_and_passes():
    """`Piccolo` opens on three of `Picard`'s characters, which is a cluster
    rather than a name. Refusing at three would take out the phonology this
    design depends on."""
    assert not reconstructs_a_reserved_name("Piccolo", _reservation())


def test_a_fragment_shorter_than_the_floor_is_never_judged():
    assert not reconstructs_a_reserved_name("Ka", _reservation())
    assert NAME_RUN_FLOOR == 4 and NAME_PREFIX_FLOOR == 4


def test_an_empty_reservation_refuses_nothing():
    assert not reconstructs_a_reserved_name("Barclay", {})
    assert not reconstructs_a_reserved_name("Barclay", {"runs": set()})
