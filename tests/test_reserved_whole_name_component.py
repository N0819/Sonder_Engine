"""A component that IS somebody's whole name is refused whatever the law
addresses people by.

`address_components` asks "would people call these two the same word", which is
the right question for a shared surname and the wrong one for a registered mind
whose entire name turns up as somebody else's given name.

Measured after the surname half of this guard landed and was working: a law of
`{rank} {family}` reports only `family` as an address component, so a generated
roster came back carrying five registered identities in the half nobody was
checking. The surnames were clean. The collision had moved to the other axis.
"""
from world.charter_identity import identity_reservation, name_is_reserved

CAST = ["Jean-Luc Picard", "Worf", "Data", "Beverly Crusher", "Geordi La Forge"]
FAMILY_LAW = {"formal_format": "{rank} {family}"}


def _res():
    return identity_reservation(CAST)


def test_a_one_word_identity_is_refused_as_a_given_name():
    """The measured case: a law that addresses by family only, and a body
    minted with a registered mind's whole name as its given half."""
    assert name_is_reserved("Worf Yar", FAMILY_LAW, _res(), "Worf", "Yar")
    assert name_is_reserved("Data O'Brien", FAMILY_LAW, _res(), "Data", "O'Brien")


def test_a_one_word_identity_is_refused_as_a_family_name_too():
    """Either half. Which end an identity lands on is the culture's business."""
    assert name_is_reserved("Miles Picard", FAMILY_LAW, _res(), "Miles", "Picard")


def test_a_shared_given_name_is_still_allowed():
    """The subtraction stays narrow. A registered `Beverly Crusher` does not
    reserve every Beverly in the story -- that would be an expansion, and two
    people sharing a given name is ordinary. What is reserved is a component
    that is the WHOLE identity somebody already answers to."""
    assert not name_is_reserved(
        "Beverly Pulaski", FAMILY_LAW, _res(), "Beverly", "Pulaski")


def test_an_unrelated_name_passes():
    assert not name_is_reserved("Sonya Ogawa", FAMILY_LAW, _res(), "Sonya", "Ogawa")
    assert not name_is_reserved("Tasha Yar", FAMILY_LAW, _res(), "Tasha", "Yar")


def test_the_whole_name_refusal_still_holds():
    """Unchanged: the entire name matching a registered one is refused
    regardless of components or law."""
    assert name_is_reserved("Worf", FAMILY_LAW, _res(), "Worf", "")
    assert name_is_reserved("Beverly Crusher", FAMILY_LAW, _res(),
                            "Beverly", "Crusher")


def test_the_address_component_refusal_still_holds():
    """The surname half that was already working must not regress: under a
    law that addresses by family, sharing a registered family is refused."""
    assert name_is_reserved(
        "Katherine Crusher", FAMILY_LAW, _res(), "Katherine", "Crusher")


def test_a_paired_address_law_still_permits_a_shared_family():
    """Under `{given} {family}` the PAIR is the address and neither half is,
    so two people may share a family exactly as two people do."""
    paired = {"name_format": "{given} {family}", "formal_format": "{title} {name}"}
    assert not name_is_reserved(
        "Katherine Crusher", paired, _res(), "Katherine", "Crusher")
