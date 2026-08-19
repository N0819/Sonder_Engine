"""Who each authority claim is about, asked once per CLAIM.

`targets` is a property of an action ELEMENT; the effects hanging off it are
separate claims. The self-subject fallback was scoped to the element, so an
element that both acted on somebody AND asserted something about the actor's
own body lost the subject on the body claim -- and `_named_cast_subject`, the
guard added to catch a claim plainly about someone else, was nested inside the
same condition and could not run there either.

Measured over every stored `director_interpret` active variant in the owner's
engine.db, read-only:

    effect claims                                  1673
      subject_id null                               856  (51.2%)
        ...hanging off an element that NAMED targets 703
      empty predicate                                48  (2.9%)
        ...with a non-empty value                     0

Every subject-less claim lands in `director_reconcile._player_claim_findings`'
"no resolvable subject; coverage not checkable" note, so the player's asserted
effect is never held against the diff at all. Every empty-predicate claim with
a resolvable subject becomes an omission reading "player-asserted completed
effect '' on <subject>", which buys a full `resolve_repair` Director call for a
claim with no content.
"""

from __future__ import annotations

from agents.common import _extract_authority_claims

#: Verbatim from stored variant 29272, trimmed. Hinami is the PLAYER; the
#: element's targets name The Doctor, so the claim about Hinami's own body was
#: never checked.
LIVE_ELEMENT = {
    "type": "action",
    "attempt": ("Hinami sits down on the double bed, and turns her attention "
                "to watch The Doctor."),
    "targets": ["The Doctor"],
    "commitment": "asserted",
    "asserted_effects": [
        {"target_id": None, "kind": "Hinami is seated on the bed"},
    ],
}


def test_a_claim_about_the_actors_own_body_survives_a_transitive_element():
    claims = _extract_authority_claims(
        [dict(LIVE_ELEMENT)], LIVE_ELEMENT["attempt"], actor_name="Hinami")
    assert claims
    assert claims[0]["subject_id"] == "Hinami", claims[0]
    assert claims[0]["subject_inferred"] is True


def test_a_dropped_reference_is_still_left_for_the_director():
    """The floor this must not breach: an effect that names nobody, on an
    element that named somebody else, is a dropped reference and NOT the
    self. Resolving it to the player hands them authorship of another
    character's body."""
    element = dict(LIVE_ELEMENT,
                   asserted_effects=[{"target_id": None, "kind": "staggers"}])
    claims = _extract_authority_claims(
        [element], "I punch the guard", actor_name="Hinami")
    assert claims and claims[0]["subject_id"] != "Hinami"


def test_a_named_cast_member_still_wins_over_the_actor():
    element = {
        "type": "action", "attempt": "shove the guard", "targets": [],
        "commitment": "asserted",
        "asserted_effects": [
            {"target_id": None, "kind": "the guard staggers back"}],
    }
    claims = _extract_authority_claims(
        [element], "shove the guard", actor_name="Hinami",
        target_forms={"Guard": ["guard"]})
    assert claims and claims[0]["subject_id"] == "Guard"


def test_an_effect_that_claims_nothing_is_not_minted():
    element = {
        "type": "action", "attempt": "wait", "targets": [],
        "commitment": "asserted",
        "asserted_effects": [{"target_id": None, "kind": "", "details": {}},
                             {"target_id": None, "kind": "you are standing"}],
    }
    claims = _extract_authority_claims([element], "wait", actor_name="Hinami")
    assert [c["predicate"] for c in claims] == ["you are standing"]


def test_an_intended_effect_is_scoped_the_same_way():
    """The intent branch was a verbatim copy of the asserted one, including
    the scope error."""
    element = dict(LIVE_ELEMENT, commitment="contestable",
                   asserted_effects=[],
                   intended_effects=[
                       {"target_id": None, "kind": "Hinami is seated on the bed"}])
    claims = _extract_authority_claims(
        [element], element["attempt"], actor_name="Hinami")
    assert claims and claims[0]["scope"] == "intent"
    assert claims[0]["subject_id"] == "Hinami"
