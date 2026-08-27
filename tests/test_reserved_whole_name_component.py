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


# --- a rank is how a story addresses somebody, not part of who they are ------

RANKED_CAST = ["Jean-Luc Picard", "Worf", "Lieutenant Commander Data",
               "Beverly Crusher", "Geordi La Forge"]
RANKED_LAW = {
    "name_format": "{given} {family}", "formal_format": "{title} {name}",
    "titles": {"ranks": {"lieutenant_commander": "Lieutenant Commander"},
               "posts": {}},
}


def _ranked():
    return identity_reservation(RANKED_CAST, RANKED_LAW)


def test_a_registered_name_carrying_a_rank_still_reserves_the_bare_identity():
    """A cast member registered as "Lieutenant Commander Data" holds the bare
    identity `data`; the rank is how the story addresses him, not who he is.

    Measured: comparing components against the STORED whole names alone let
    `Data Picard`, `Data Soong`, `Data Ogawa` through in one generation,
    because "data" is not "lieutenant commander data" as a string.
    """
    assert name_is_reserved("Data Picard", RANKED_LAW, _ranked(), "Data", "Picard")
    assert name_is_reserved("Data Soong", RANKED_LAW, _ranked(), "Data", "Soong")


def test_a_one_word_registered_name_needs_no_stripping_and_still_holds():
    assert name_is_reserved("Worf Yar", RANKED_LAW, _ranked(), "Worf", "Yar")


def test_a_half_of_a_multi_word_identity_is_still_not_reserved():
    """The subtraction stays narrow. `Geordi` is not the whole of
    `Geordi La Forge`, so it is a shared given name like any other -- refusing
    it would be an expansion, and two people sharing a given name is ordinary.
    """
    assert not name_is_reserved(
        "Geordi Picard", RANKED_LAW, _ranked(), "Geordi", "Picard")
    assert not name_is_reserved(
        "Beverly Pulaski", RANKED_LAW, _ranked(), "Beverly", "Pulaski")


def test_an_unrelated_name_still_passes_under_a_ranked_cast():
    assert not name_is_reserved("Sonya Ogawa", RANKED_LAW, _ranked(), "Sonya", "Ogawa")
