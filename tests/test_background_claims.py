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

from world.background_claims import (
    CLAIM_TTL_TURNS,
    claimant_credence,
    novel_proper_nouns,
    record_claims,
    settle_claims,
    unratified_claims,
)
from core.db import wget

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
    assert out["ratified"] == 0 and out["contradicted"] == 0
    assert out["expired"] == 0
    assert len(unratified_claims(cid, 2)) == 1


# --- a ratified claim must reach canon ------------------------------------

def test_ratifying_a_claim_writes_it_into_canon(temp_db):
    """The whole ratification path existed except the last write.
    `settle_claims` set rec["status"]="ratified" in a world-KV blob and wrote
    nothing into `lore_entries`, so a claim became TRUE and unreachable in the
    same instant: `search_lore` over the chat's books is the only route back
    into a prompt, and it had nothing to find. The prompt promised canon
    ("it becomes canon and the world must honour it") and the code set a flag.
    """
    from mind.memory import chat_lorebook_weights, search_lore
    cid = _chat(temp_db)
    record_claims(cid, 2, [{"claimant": "Old Man by the Hearth",
                            "text": "That'd be Tam Briddock's boy",
                            "refs": ["Tam Briddock"], "credence": "low"}])
    settle_claims(cid, 3, "The barkeep says nothing of it.",
                  ratified_refs=["Tam Briddock"])
    hits = search_lore(chat_lorebook_weights(cid), "Tam Briddock", k=10)
    assert any("Tam Briddock" in (h.get("content") or "") for h in hits)


def test_canon_write_survives_a_chat_that_never_wrote_lore_before(temp_db):
    """A ratified claim can be the FIRST thing a chat ever writes to canon.
    Only `commit_mapping` minted the chat's canon lorebook, and it is skipped
    on any beat with no staged lore / world_facts / introductions -- so a
    ratification landing on such a beat had no book to be written into."""
    from core.db import q
    cid = _chat(temp_db)
    assert q("SELECT lorebook_id FROM chats WHERE id=?",
             (cid,), one=True)["lorebook_id"] is None
    record_claims(cid, 1, [{"claimant": "Old Man", "text": "The east wing "
                            "has been shut since the flood",
                            "refs": ["the east wing"]}])
    settle_claims(cid, 2, "", ratified_refs=["the east wing"])
    assert q("SELECT lorebook_id FROM chats WHERE id=?",
             (cid,), one=True)["lorebook_id"] is not None


def test_ratifying_the_same_claim_twice_does_not_duplicate_canon(temp_db):
    """A rerun replays commit. The canon row is keyed by the claim's own
    content hash so a second settle of the same beat cannot mint a second
    entry -- the same stable-identifier rule memories already live under."""
    from core.db import q
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "Old Man", "text": "Tam Briddock's boy",
                            "refs": ["Tam Briddock"]}])
    settle_claims(cid, 2, "", ratified_refs=["Tam Briddock"])
    stored = wget(cid, "background_claims", {})
    for rec in stored.values():
        rec["status"] = "unratified"
    from core.db import wset
    wset(cid, "background_claims", stored)
    settle_claims(cid, 2, "", ratified_refs=["Tam Briddock"])
    rows = q("SELECT id FROM lore_entries WHERE content LIKE ?",
             ("%Tam Briddock%",))
    assert len(rows) == 1


# --- contradiction ---------------------------------------------------------

def test_the_director_can_record_that_a_presence_was_wrong(temp_db):
    """The module documented a `contradicted` state in its own header comment
    and never wrote it. A claim the Director rejected was byte-identical to one
    it ignored, so the payoff the comment promises -- "because the claimant is
    recorded the world can show that" -- was unreachable, and the rejected
    claim went on being offered back to the Director until it expired."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "Old Man", "text": "Tam Briddock's boy",
                            "refs": ["Tam Briddock"]}])
    out = settle_claims(cid, 2, "Nobody by that name ever lived here.",
                        contradicted_refs=["Tam Briddock"])
    assert out["contradicted"] == 1
    rec = list(wget(cid, "background_claims", {}).values())[0]
    assert rec["status"] == "contradicted"
    assert rec["contradicted_turn"] == 2
    # The claimant survives: that a bystander was WRONG is the thing a later
    # beat gets to show.
    assert rec["claimant"] == "Old Man"
    # And it stops being offered for adjudication.
    assert unratified_claims(cid, 2) == []


def test_a_contradicted_claim_never_reaches_canon(temp_db):
    """Ratification is a one-way door into `lore_entries`. A claim named in
    both lists is the Director disagreeing with itself, and the safe reading of
    a disagreement is the one that does not write."""
    from core.db import q
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "Old Man", "text": "Tam Briddock's boy",
                            "refs": ["Tam Briddock"]}])
    settle_claims(cid, 2, "Tam Briddock's boy never existed.",
                  ratified_refs=["Tam Briddock"],
                  contradicted_refs=["Tam Briddock"])
    rec = list(wget(cid, "background_claims", {}).values())[0]
    assert rec["status"] == "contradicted"
    # Not averaged into a half-truth: both verdicts stay on the record.
    assert rec["ratification_conflict"] is True
    assert q("SELECT id FROM lore_entries", ()) == []


def test_the_commit_path_carries_both_verdicts_end_to_end(temp_db):
    """The module-level halves can both be right while the wire between them is
    not: commit read only `state_diff.ratified_claims`, so `contradicted_claims`
    would have been a schema field and a prompt clause with nothing reading it
    -- and the canon write has to survive the real `track_background_presences`
    call, embeddings prepared ahead of the transaction and all."""
    import time
    from persist.commit import prepare_background_claims, track_background_presences
    from mind.memory import chat_lorebook_weights, search_lore
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    cid = _chat(temp_db)
    record_claims(cid, 1, [
        {"claimant": "Old Man", "text": "That'd be Tam Briddock's boy",
         "refs": ["Tam Briddock"]},
        {"claimant": "The Drunk", "text": "The Moorside burned in the spring",
         "refs": ["the spring fire"]},
    ])
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=2, chat_id=cid, idx=2, player_input="",
                      created=time.time()),
        cast=[], input="",
        director_resolve={
            "resolved_event": "The barkeep sets down the jug.",
            "state_diff": {"ratified_claims": ["Tam Briddock"],
                           "contradicted_claims": ["the spring fire"]},
        },
    )
    track_background_presences(ctx, nonce=0,
                              prepared=prepare_background_claims(ctx))

    stored = wget(cid, "background_claims", {})
    by_claimant = {r["claimant"]: r for r in stored.values()}
    assert by_claimant["Old Man"]["status"] == "ratified"
    assert by_claimant["The Drunk"]["status"] == "contradicted"
    hits = search_lore(chat_lorebook_weights(cid), "Tam Briddock", k=10)
    contents = " ".join(h.get("content") or "" for h in hits)
    assert "Tam Briddock" in contents
    assert "spring" not in contents


def test_contradiction_is_never_inferred_from_prose(temp_db):
    """Text matching cannot tell "the Widow denies it" from "the Widow says it
    again". Only an explicit `contradicted_claims` entry contradicts; prose
    that merely sounds incompatible leaves the claim hearsay, as before."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "Old Man", "text": "…",
                            "refs": ["Tam Briddock"]}])
    settle_claims(cid, 2, "There was never any Tam Briddock, the Widow says.")
    rec = list(wget(cid, "background_claims", {}).values())[0]
    # The loose text-match ADOPTION path is what fires here, and deliberately:
    # the Director wrote the ref into the objective record.
    assert rec["status"] != "contradicted"


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
    from world.background_claims import is_title_only
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


# --- ratification is a deliberate act, not a brush-past --------------------

def test_a_claim_is_not_ratified_by_its_own_beat(temp_db):
    """`background_react` runs AFTER `director_resolve` (agents/runtime.py's
    plan), so the resolved event of the beat a claim was made in was written
    BEFORE the presence spoke. A reference appearing there is the presence
    echoing the Director's prose, not the Director adopting the presence's
    invention. Measured, chat 67: 7 claims, 7 ratified, 0 contradicted, 0
    expired -- the three-outcome design collapsed onto its one irreversible
    branch, and this is the beat that collapsed it."""
    cid = _chat(temp_db)
    record_claims(cid, 4, [{"claimant": "innkeeper",
                            "text": "The Dragon Kingdom, dear.",
                            "refs": ["The Dragon Kingdom"]}])
    out = settle_claims(cid, 4, "The innkeeper looks up from the ledger. "
                                "The Dragon Kingdom's roads are bad this year.")
    assert out["ratified"] == 0
    rec = list(wget(cid, "background_claims", {}).values())[0]
    assert rec["status"] == "unratified"


def test_an_explicit_verdict_still_lands_on_the_claims_own_beat(temp_db):
    """Only the INFERRED half needs a later beat. Naming the claim in
    `state_diff.ratified_claims` is the Director's deliberate act whenever it
    arrives."""
    cid = _chat(temp_db)
    record_claims(cid, 4, [{"claimant": "innkeeper", "text": "...",
                            "refs": ["The Dragon Kingdom"]}])
    out = settle_claims(cid, 4, "", ratified_refs=["The Dragon Kingdom"])
    assert out["ratified"] == 1


def test_a_reference_inside_a_longer_word_is_not_adoption(temp_db):
    """A substring is not a reference. Ratification writes canon, and canon is
    a one-way door, so the match that opens it must be to the name rather than
    to a run of letters that happens to contain it."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "patron", "text": "...",
                            "refs": ["Rose"]}])
    settle_claims(cid, 2, "She sets it down in prose nobody will read.")
    rec = list(wget(cid, "background_claims", {}).values())[0]
    assert rec["status"] == "unratified"


def test_a_name_may_still_inflect_where_it_is_taken_up(temp_db):
    """The boundary is required at the name's leading edge only: a plural or a
    possessive is the fiction using the name, not a different word."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "patron", "text": "...",
                            "refs": ["Briddock"]}])
    settle_claims(cid, 2, "The Briddocks have not been seen since.")
    rec = list(wget(cid, "background_claims", {}).values())[0]
    assert rec["status"] == "ratified"


# --- what canon may say, and who it may say it about ----------------------

def _canon_rows(temp_db):
    return temp_db.q("SELECT content FROM lore_entries", ())


def test_canon_never_attributes_a_claim_to_an_engine_handle(temp_db):
    """Live, chat 67: two of seven canon rows read `a8becaa367e148be said:
    "..."`. The background lane keys some presences by scene entity id, and
    canon is PROSE -- a player reads it, and every payload that quotes a lore
    entry reads it -- so an id spliced into a sentence is a name nobody in the
    fiction could have used. Where no ledger owns the handle, canon says a
    bystander."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "a8becaa367e148be",
                            "text": "Never heard of Lugunica.",
                            "refs": ["Lugunica"]}])
    settle_claims(cid, 2, "", ratified_refs=["Lugunica"])
    content = " ".join(r["content"] for r in _canon_rows(temp_db))
    assert "a8becaa367e148be" not in content
    assert "a bystander said" in content


def test_canon_calls_a_claimant_by_the_name_its_ledger_holds(temp_db):
    """When a ledger DOES own the handle, the fix is the name rather than the
    anonymisation: `world/subjects.py` round-trips an id to the display name
    the fiction uses."""
    from core.db import wset
    cid = _chat(temp_db)
    wset(cid, "scene", {"entities": {"a8becaa367e148be": {"name": "Innkeeper"}}})
    record_claims(cid, 1, [{"claimant": "a8becaa367e148be",
                            "text": "The Dragon Kingdom, dear.",
                            "refs": ["The Dragon Kingdom"]}])
    settle_claims(cid, 2, "", ratified_refs=["The Dragon Kingdom"])
    content = " ".join(r["content"] for r in _canon_rows(temp_db))
    assert "a8becaa367e148be" not in content
    assert "Innkeeper said" in content


def test_canon_records_that_a_line_was_said_not_that_it_is_true(temp_db):
    """Live, chat 67: `Never heard of Lugunica... -- the Director has
    established this as true.` What ratification establishes is that the line
    was SAID and the fiction is keeping it. A denial, a boast and a mistake
    are all ordinary things for a bystander to say, and canon that asserts
    their content as fact turns every one of them into its opposite."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "the innkeeper",
                            "text": "Never heard of Lugunica.",
                            "refs": ["Lugunica"]}])
    settle_claims(cid, 2, "", ratified_refs=["Lugunica"])
    content = " ".join(r["content"] for r in _canon_rows(temp_db))
    assert "established this as true" not in content
    assert "Never heard of Lugunica." in content
    assert "said" in content


def test_canon_does_not_quote_a_line_that_already_carries_quotes(temp_db):
    """Live, chat 67: `635a740debcd433f said: ""Greens, fresh-picked
    today...""`. A quotation of a quotation is a different sentence."""
    cid = _chat(temp_db)
    record_claims(cid, 1, [{"claimant": "the grocer",
                            "text": '"Greens, fresh-picked today."',
                            "refs": ["Greens"]}])
    settle_claims(cid, 2, "", ratified_refs=["Greens"])
    content = " ".join(r["content"] for r in _canon_rows(temp_db))
    assert '""' not in content
    assert 'said: "Greens, fresh-picked today."' in content
