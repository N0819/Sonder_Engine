"""Unratified lore claimed by background presences (background_claims.py).

Motivation is a live result, not a hypothetical: in demo/tavern_scene_life the
scene manager invented "Tam Briddock's boy" (turn 2) and "the tinker's lot last
month" (turn 3) -- neither string appears anywhere in director_resolve for those
turns -- and by turn 6 the first had been absorbed into canon and become the
dramatic spine of the best scene in the run.

So invention is kept. What these tests pin is that every OUTCOME of an invented
claim is coherent: adopted, contradicted, or expired as tavern talk. The failure
being designed out is "the engine forgot it said this."
"""

from __future__ import annotations

from background_claims import (
    CLAIM_TTL_TURNS,
    claimant_credence,
    novel_proper_nouns,
    record_claims,
    settle_claims,
    unratified_claims,
)
from db import wget

KNOWN = {"The Barkeep", "Ysolde Marr", "Bran Holt", "Kessa Vane",
         "The Moorside", "common room"}


# --- detecting what was invented -----------------------------------------

def test_detects_the_real_turn2_fabrication():
    quote = "Three drovers... end of autumn. That'd be Tam Briddock's boy, and..."
    assert "Tam Briddock" in " ".join(novel_proper_nouns(quote, KNOWN))


def test_known_names_are_not_claims():
    quote = "Ysolde Marr asked The Barkeep about it."
    assert novel_proper_nouns(quote, KNOWN) == []


def test_sentence_initial_capital_is_not_a_name():
    assert novel_proper_nouns("Two silver. Bet that's gone up.", KNOWN) == []


def test_mid_quote_sentence_start_is_not_a_name():
    """The tavern run produced a spurious "That'd" claim: capitalized, not at
    offset 0, but opening a sentence all the same."""
    quote = "Three drovers... end of autumn. That'd be Tam Briddock's boy, and..."
    assert novel_proper_nouns(quote, KNOWN) == ["Tam Briddock"]


def test_possessive_is_stripped_to_one_name():
    assert novel_proper_nouns("Tam Briddock's boy didn't.", KNOWN) == ["Tam Briddock"]


def test_article_stripped_reference_matches_an_established_name():
    """An extra saying "the Widow" refers to the Director-established "The
    Widow" -- not a new invention."""
    assert novel_proper_nouns("She's at the Widow now.",
                              KNOWN | {"The Widow"}) == []


def test_lowercase_lore_is_not_caught_by_the_scan():
    """"the tinker's lot last month" is real invented lore the proper-noun scan
    CANNOT see -- which is exactly why the manager self-declares `asserts` and
    the scan is only a backstop for what it fails to declare."""
    assert novel_proper_nouns("what he charged the tinker's lot last month",
                              KNOWN) == []


# --- recording -------------------------------------------------------------

def _chat(temp_db):
    import time
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("T", "", time.time()))


def test_record_and_surface(temp_db):
    cid = _chat(temp_db)
    record_claims(cid, 2, [{"claimant": "Old Man by the Hearth",
                            "text": "That'd be Tam Briddock's boy",
                            "refs": ["Tam Briddock"], "credence": "low"}])
    live = unratified_claims(cid, 3)
    assert len(live) == 1
    assert live[0]["claimant"] == "Old Man by the Hearth"
    assert live[0]["names"] == ["Tam Briddock"]
    assert live[0]["credence"] == "low"
    assert live[0]["turns_ago"] == 1


def test_recording_is_idempotent(temp_db):
    cid = _chat(temp_db)
    claim = [{"claimant": "A", "text": "same line", "refs": ["X"]}]
    assert record_claims(cid, 1, claim) == 1
    assert record_claims(cid, 1, claim) == 0
    assert len(unratified_claims(cid, 1)) == 1


# --- the three outcomes, all coherent -------------------------------------

def test_director_adopts_a_claim_explicitly(temp_db):
    cid = _chat(temp_db)
    record_claims(cid, 2, [{"claimant": "Old Man", "text": "Tam Briddock's boy",
                            "refs": ["Tam Briddock"]}])
    out = settle_claims(cid, 3, "The barkeep says nothing of it.",
                        ratified_refs=["Tam Briddock"])
    assert out["ratified"] == 1
    assert unratified_claims(cid, 3) == []
    rec = list(wget(cid, "background_claims", {}).values())[0]
    assert rec["status"] == "ratified"


def test_director_adopts_by_writing_it_into_the_record(temp_db):
    """Ratification should not depend on the model remembering to fill a list:
    naming the claim in the objective record IS adoption."""
    cid = _chat(temp_db)
    record_claims(cid, 2, [{"claimant": "Old Man", "text": "…",
                            "refs": ["Tam Briddock"]}])
    settle_claims(cid, 3, "The Widow says Tam Briddock's boy never came back.")
    rec = list(wget(cid, "background_claims", {}).values())[0]
    assert rec["status"] == "ratified"


def test_unratified_claim_survives_until_ttl_then_expires(temp_db):
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "Old Man", "text": "…",
                            "refs": ["Tam Briddock"]}])
    # Still hearsay a few beats later -- nobody has taken it up.
    settle_claims(cid, 1 + CLAIM_TTL_TURNS, "unrelated prose")
    assert len(unratified_claims(cid, 1 + CLAIM_TTL_TURNS)) == 1
    # Past its life it is simply gone: something a stranger said once.
    settle_claims(cid, 2 + CLAIM_TTL_TURNS, "unrelated prose")
    assert unratified_claims(cid, 2 + CLAIM_TTL_TURNS) == []
    assert wget(cid, "background_claims", {}) == {}


def test_ignoring_a_claim_never_raises_or_ratifies_it(temp_db):
    """Contradiction is deliberately not inferred by string matching -- an
    unratified claim just stays hearsay."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "Old Man", "text": "…",
                            "refs": ["Tam Briddock"]}])
    out = settle_claims(cid, 2, "Nobody by that name ever lived here.")
    assert out == {"ratified": 0, "expired": 0}
    assert len(unratified_claims(cid, 2)) == 1


def test_surfaced_claims_are_bounded(temp_db):
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "A%d" % i, "text": "t%d" % i,
                            "refs": ["R%d" % i]} for i in range(20)])
    assert len(unratified_claims(cid, 1)) <= 6


# --- credence comes from the frozen blurb ---------------------------------

def test_credence_reads_the_frozen_blurb():
    # The old man's real blurb from the tavern run.
    assert claimant_credence({
        "manner": "Creaking voice, too slow for conversation, trails off "
                  "mid-thought."}) == "low"
    assert claimant_credence({
        "manner": "Short sentences, flat tone.",
        "trait": "Keeps the books precise."}) == "high"
    assert claimant_credence({"manner": "Brisk and clipped."}) == "ordinary"
    assert claimant_credence(None) == "ordinary"


# --- title normalization (Enterprise run) ---------------------------------

def test_bare_rank_is_not_an_invented_name():
    """"...engagement profiles, Captain." addresses someone; it does not name a
    new person. The Enterprise run recorded "Captain" as lore and ratified it."""
    from background_claims import is_title_only
    assert is_title_only("Captain")
    assert is_title_only("Number One")
    assert not is_title_only("Tam Briddock")
    quote = "All three contacts are running pre-scripted profiles, Captain."
    assert novel_proper_nouns(quote, KNOWN) == []


def test_surname_matches_an_established_titled_name():
    """Riker saying "Worf" refers to the established "Lieutenant Worf"."""
    known = KNOWN | {"Lieutenant Worf"}
    assert novel_proper_nouns("Worf, transfer tactical to ops.", known) == []


def test_titled_form_matches_a_bare_established_name():
    known = KNOWN | {"Jean-Luc Picard"}
    assert novel_proper_nouns("Captain Jean-Luc Picard said so.", known) == []
