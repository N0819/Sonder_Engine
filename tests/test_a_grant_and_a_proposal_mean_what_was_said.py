"""The Room's ledgers of grants and proposals keep what was said (audit
2026-11-01, story_room_carriers F5, F6, F17, F18 and efficiency 3).

* `room_mandates` was read-modify-written with no transaction by four
  threads: a revocation made in the panel while a reply wrote a grant erased
  the grant, and the reverse order brought a revoked licence back.
* A proposal filed again after it was refused was minted the refused one's
  uid, so judging the new one flipped the old row and left the new one
  pending forever.
* A grant enumerating more than 24 capabilities was cut to 24 when stored,
  while its writer was shown the uncut row: `region_events` granted by name
  and refused at use.
* The same short sentence granting something else was answered with the
  first grant, its new capability dropped.
* Every read of the standing grants re-swept their expiry and re-parsed the
  whole package ledger once per package-scoped grant.
"""
from __future__ import annotations

import threading
import time

import pytest

from core import db as core_db
from story import mandates as md
from story import room_conversation as room
from story import room_proposals as rp


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Room", "", time.time()))


# ---------------------------------------------------------------------------
# F5 (lane F4) -- one writer at a time
# ---------------------------------------------------------------------------

def _held_writer(fn):
    """Run ``fn`` inside a transaction on another thread and hold it open
    until released: a reply or a commit mid-write."""
    written, release = threading.Event(), threading.Event()

    def run():
        with core_db.transaction():
            fn()
            written.set()
            release.wait(5)
        core_db.close_connection()

    worker = threading.Thread(target=run)
    worker.start()
    assert written.wait(5)
    threading.Timer(0.3, release.set).start()
    return worker


def test_a_revocation_does_not_erase_a_grant_written_meanwhile(temp_db):
    cid = _chat(temp_db)
    first = md.grant_mandate(cid, None, text="You may plan rooms",
                             capabilities=["plan_rooms"], turn_idx=1)
    worker = _held_writer(lambda: md.grant_mandate(
        cid, None, text="You may plan people too",
        capabilities=["plan_entity"], turn_idx=2))
    room.revoke_mandate(cid, first["uid"], None, turn_idx=2)
    worker.join(5)
    stored = {m["text"]: m["status"] for m in room.mandates(cid, None)}
    assert stored == {"You may plan rooms": "revoked",
                      "You may plan people too": "active"}


def test_a_grant_does_not_bring_back_a_revocation_written_meanwhile(temp_db):
    cid = _chat(temp_db)
    first = md.grant_mandate(cid, None, text="You may plan rooms",
                             capabilities=["plan_rooms"], turn_idx=1)
    worker = _held_writer(
        lambda: room.revoke_mandate(cid, first["uid"], None, turn_idx=2))
    md.grant_mandate(cid, None, text="You may plan people too",
                     capabilities=["plan_entity"], turn_idx=2)
    worker.join(5)
    stored = {m["text"]: m["status"] for m in room.mandates(cid, None)}
    assert stored == {"You may plan rooms": "revoked",
                      "You may plan people too": "active"}


# ---------------------------------------------------------------------------
# F17, F18 -- a grant keeps what it said
# ---------------------------------------------------------------------------

def test_a_grant_naming_every_capability_keeps_every_one(temp_db):
    cid = _chat(temp_db)
    kinds = [c for c in md.MANDATE_CAPABILITIES if c != md.TOTAL_CAPABILITY]
    assert len(kinds) > 24
    row = md.grant_mandate(cid, None, text="All of it, by name.",
                           capabilities=kinds)
    (stored,) = room.mandates(cid, None)
    assert stored["capabilities"] == row["capabilities"] == kinds
    for kind in kinds:
        assert md.permits(stored, kind), kind


def test_the_same_words_granting_something_else_are_a_second_grant(temp_db):
    cid = _chat(temp_db)
    courier = md.grant_mandate(cid, None, text="Yes, go ahead.",
                               capabilities=["arrival"], request="pkg_courier")
    tower = md.grant_mandate(cid, None, text="Yes, go ahead.",
                             capabilities=["plan_rooms"], request="pkg_tower")
    assert courier["uid"] != tower["uid"]
    assert md.coverage(cid, None, ["plan_rooms"])["ok"]
    assert md.coverage(cid, None, ["arrival"])["ok"]
    # A re-emission of the SAME grant is still the same grant.
    again = md.grant_mandate(cid, None, text="yes, go ahead.",
                             capabilities=["plan_rooms"], request="pkg_tower")
    assert again["uid"] == tower["uid"]
    assert len(room.mandates(cid, None)) == 2


# ---------------------------------------------------------------------------
# Efficiency 3 -- a sweep reads the ledger once
# ---------------------------------------------------------------------------

def test_a_sweep_parses_the_package_ledger_once(temp_db, monkeypatch):
    from story import plot_packages as pp
    cid = _chat(temp_db)
    for i in range(4):
        pkg = pp.new_package(cid, title="Package %d" % i, premise="p")
        md.grant_mandate(cid, None, text="For package %d." % i,
                         capabilities=["plan_rooms"], request=pkg["uid"])
    reads = []
    real = pp.packages
    monkeypatch.setattr(pp, "packages",
                        lambda *a, **k: reads.append(1) or real(*a, **k))
    rows = md.active_mandates(cid, None)
    assert len(rows) == 4
    assert len(reads) == 1


def test_coverage_answers_from_rows_already_read(temp_db, monkeypatch):
    cid = _chat(temp_db)
    md.grant_mandate(cid, None, text="Plan rooms.", capabilities=["plan_rooms"])
    rows = md.active_mandates(cid, None)
    monkeypatch.setattr(md, "active_mandates",
                        lambda *a, **k: pytest.fail("re-read the grants"))
    assert md.coverage(cid, None, ["plan_rooms"], rows=rows)["ok"]
    assert not md.coverage(cid, None, ["plan_entity"], rows=rows)["ok"]


# ---------------------------------------------------------------------------
# F6 (lane F5) -- a proposal filed again is a new proposal
# ---------------------------------------------------------------------------

def test_a_proposal_filed_again_after_a_refusal_is_its_own_row(temp_db):
    cid = _chat(temp_db)
    first = rp.file_proposal(cid, None, kind="pressure", title="The tide comes early",
                             wants_true="The tide floods the quay.", why_now="now")
    rp.judge_proposal(cid, None, first["uid"], verdict="refuse",
                      reason="the tide tables say otherwise")
    again = rp.file_proposal(cid, None, kind="pressure",
                             title="The tide comes early",
                             wants_true="The tide floods the quay.", why_now="later",
                             turn_idx=7)
    assert again["uid"] != first["uid"]
    rp.judge_proposal(cid, None, again["uid"], verdict="accept", reason="now it fits",
                      package_uid="plot:tide")
    rows = {p["uid"]: p["status"] for p in rp.proposals(cid, None)}
    assert rows == {first["uid"]: "refused", again["uid"]: "implemented"}
    assert rp.pending_proposals(cid, None) == []


def test_a_proposal_still_pending_is_answered_by_its_own_row(temp_db):
    """The dedupe a re-emitting model relies on is unchanged."""
    cid = _chat(temp_db)
    first = rp.file_proposal(cid, None, kind="pressure", title="The tide comes early",
                             wants_true="The tide floods the quay.", why_now="now")
    same = rp.file_proposal(cid, None, kind="pressure", title="The tide comes early",
                            wants_true="The tide floods the quay.", why_now="now")
    assert same["uid"] == first["uid"]
    assert len(rp.proposals(cid, None)) == 1
