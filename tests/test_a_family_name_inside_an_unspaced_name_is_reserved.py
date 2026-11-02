"""A registered name written without spaces still reserves its parts.

`charter_identity._tokens` split on whitespace, so a cast member 佐藤ヒナミ was
one run and no component of a candidate could match its start or its end:
a minted 佐藤タロウ passed beside her -- two people the story addresses as 佐藤
-- although the same name written 佐藤 ヒナミ reserved 佐藤 (audit
story_scene_schema F9, reproduced). The name is read in the parts its script
writes it in (`language_runtime.fold_words`); a Latin name is read exactly
as before. The novelty floors' per-script numbers are the owner's and are not
moved here."""
from world.charter_identity import (_reserves_component, address_components,
                                    identity_reservation, name_is_reserved)


def test_the_family_name_at_the_front_of_an_unspaced_name_is_reserved():
    reservation = identity_reservation(["佐藤ヒナミ"])
    assert _reserves_component(reservation, "佐藤")
    assert _reserves_component(reservation, "ヒナミ")
    assert not _reserves_component(reservation, "田中")


def test_spaced_and_unspaced_spellings_reserve_alike():
    spaced = identity_reservation(["佐藤 ヒナミ"])
    unspaced = identity_reservation(["佐藤ヒナミ"])
    for part in ("佐藤", "ヒナミ", "田中"):
        assert _reserves_component(spaced, part) \
            == _reserves_component(unspaced, part), part


def test_a_latin_name_reserves_exactly_as_before():
    reservation = identity_reservation(["Jean-Luc Picard"])
    assert _reserves_component(reservation, "Picard")
    assert _reserves_component(reservation, "Jean-Luc")
    assert not _reserves_component(reservation, "Jean")


def test_a_mint_addressed_by_family_cannot_take_her_family_name():
    profile = {"given": ["タロウ"], "family": ["佐藤"],
               "name_format": "{family}{given}",
               "formal_format": "{family}さん"}
    reservation = identity_reservation(["佐藤ヒナミ"], profile)
    assert "family" in address_components(profile)
    assert name_is_reserved("佐藤タロウ", profile, reservation,
                            given="タロウ", family="佐藤")
