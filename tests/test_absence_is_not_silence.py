"""An absence from a bounded retrieval is not proof that canon is silent.

The mapping stage is told: check the location book's candidates, and "only if
canon is silent" mint a new room. `candidates` is a bounded, ranked retrieval
— the top few entries a search returned this beat — so an authored room can be
missing from it because retrieval failed, and that is indistinguishable from a
room nobody ever wrote. The clause asked the model to make a claim about the
whole book from a truncated view of it.

MEASURED, live, chat 63 turn 165. `mapping_stage` received exactly ONE
candidate for a location_query of "Tamamo's Shrine upstairs hallway and
stairs": the building's FIRST floor. The same book already held entry 2791, a
3,763-character authored second floor whose keys begin
`second floor,shrine,hallway,meditation room,Hinami's room`. It was absent
from every candidate — its eleven person-authored entries carry 256-wide
fallback vectors while the engine's own play-written entries carry 2560-wide
ones, and only the 2560-wide entries came back.

Reading that single candidate as silence, the stage authored a replacement
second floor into the same book (entry 2799). It moved the staircase from the
back of the first floor to the north side, dropped the meditation room,
dropped Hinami's own bedroom, dropped the stairs onward to the third floor,
and inverted the atmosphere. The engine wrote canon it had never retrieved.

Nothing downstream catches this: `mapping_stage` validates only
`relevant_books`, and `merge_lore`'s dedupe key is identity-based — it exists
to keep two revisions of one entry distinct, which is precisely the property
that stops it noticing a new entry that CONTRADICTS an old one.
"""

from __future__ import annotations

from prompts import DEFAULT_PROMPTS


def _mapping_prompt():
    body = DEFAULT_PROMPTS["mapping_stage"]
    assert "ROOM GENERATION:" in body
    return body


def test_the_retrieval_is_named_as_bounded():
    """The load-bearing correction. Without this the clause reads as "you have
    been shown the book", which is the false premise the whole defect rests
    on.
    """
    body = _mapping_prompt()
    assert "ABSENCE FROM `candidates` IS NOT SILENCE" in body
    assert "BOUNDED, RANKED" in body


def test_it_says_why_a_miss_looks_like_an_absence():
    """Naming the failure mode, not just forbidding the conclusion: retrieval
    failing and nobody having written it produce the same empty result.
    """
    body = _mapping_prompt()
    assert "retrieval failed to surface it" in body
    assert "identical to a room nobody has ever written" in body


def test_minting_inside_an_established_place_assumes_the_author_got_there_first():
    """The occasion, named concretely rather than prohibited in the abstract —
    a floor of a building, a wing, a deck. A bare "be careful" inverts.
    """
    body = _mapping_prompt()
    assert "assume the author has described it and you have not been shown it" in body
    for occasion in ("a floor of a building", "a wing of a house",
                     "a deck of a ship"):
        assert occasion in body, occasion


def test_the_generated_room_must_declare_itself_and_stay_thin():
    """The two halves that make a wrong guess cheap: say it was generated, and
    do not furnish it. A thin room costs a sentence to correct; a richly
    furnished wrong one has to be argued with for the rest of the story.
    """
    body = _mapping_prompt()
    assert "generated because no candidate described this floor" in body
    assert "MINIMAL" in body
    assert "do not invent named sub-rooms" in body


def test_the_measurement_travels_with_the_rule():
    """This project's rule: a constant or a clause carries the measurement
    behind it, so the next person to read it can tell instruction from
    superstition.
    """
    body = _mapping_prompt()
    assert "exactly ONE candidate" in body
    assert "3,763-character" in body
    assert "wrote canon it had never retrieved" in body


def test_the_original_instruction_survives():
    """The fix is additive. Checking candidates first and staging a `layout`
    entry keyed off the movement declaration is still the procedure.
    """
    body = _mapping_prompt()
    assert "FIRST check the relevant location book's candidates" in body
    assert "staged_lore entry with category 'layout'" in body
    assert "keys field prefix" in body
