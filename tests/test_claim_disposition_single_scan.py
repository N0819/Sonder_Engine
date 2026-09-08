"""One claim-disposition scan, read by every site that asks about a claim.

Finding B13 (2026-09-07 review, `docs/experiments/REVIEW_2026-09-07.md`
Section B): the scan over a resolution's `claim_dispositions` lived twice in
`agents/common.py` -- once in `_claim_realized`, which decides the sequence
verdict a phase gets, and once in `adjudicated_player_action_text`, which
decides how much of the player's declared surface the narrator and
perception may show. Same rows, same matching rule, same "was this act
realized" answer, written out twice and free to drift. A third site,
`director_reconcile._player_claim_findings`, spelled out for itself where
the rows live (top-level, then the diff's).

The rule that now holds: `common.claim_disposition_rows` is where a
resolution's disposition rows come from, and `common.scan_claims_for` is the
only place that decides which of them bear on one action and whether it was
realized.
"""

import pytest

from agents import common
from agents.common import (
    adjudicated_player_action_text,
    claim_disposition_rows,
    scan_claims_for,
    settle_sequence_dispositions,
)

ELEM = {
    "type": "action", "event_id": "turn:7:player:0:action",
    "commitment": "contestable",
    "observable": "tests the wound edge, irrigates it, then sutures it",
}

# Each row is one resolution shape the two readers must agree about.
CASES = [
    # nothing said about the act at all
    {},
    {"claim_dispositions": []},
    # the act's own event id, adjudicated directly
    {"claim_dispositions": [
        {"claim_id": ELEM["event_id"], "status": "realized"}]},
    {"state_diff": {"claim_dispositions": [
        {"claim_id": ELEM["event_id"], "status": "deferred"}]}},
    # intent claims of the same sequence index
    {"state_diff": {"claim_dispositions": [
        {"claim_id": "claim:0:intent:0", "status": "realized"},
        {"claim_id": "claim:0:intent:1", "status": "realized"}]}},
    {"state_diff": {"claim_dispositions": [
        {"claim_id": "claim:0:intent:0", "status": "realized"},
        {"claim_id": "claim:0:intent:1", "status": "deferred"}]}},
    {"state_diff": {"claim_dispositions": [
        {"claim_id": "claim:0:intent:0", "status": "contested"},
        {"claim_id": "claim:0:intent:1", "status": "rejected"}]}},
    # a claim of some other sequence index says nothing about this act
    {"claim_dispositions": [
        {"claim_id": "claim:3:intent:0", "status": "rejected"}]},
    # realization reached only through realized_event_ids
    {"claim_dispositions": [
        {"claim_id": "claim:9:intent:0", "status": "realized",
         "realized_event_ids": [ELEM["event_id"]]}]},
    {"claim_dispositions": [
        {"claim_id": "claim:9:intent:0", "status": "deferred",
         "realized_event_ids": [ELEM["event_id"]]}]},
    # malformed rows must not be read as adjudication by either site
    {"claim_dispositions": ["not a row", None],
     "state_diff": {"claim_dispositions": "not a list"}},
    # both containers carry rows at once
    {"claim_dispositions": [
        {"claim_id": "claim:0:intent:0", "status": "realized"}],
     "state_diff": {"claim_dispositions": [
         {"claim_id": "claim:0:intent:1", "status": "deferred"}]}},
]


def _verdict(resolved):
    """The sequence status `_claim_realized` produces for the act."""
    rows = settle_sequence_dispositions([dict(ELEM)], resolved, {})
    return rows[0]["status"]


@pytest.mark.parametrize("resolved", CASES)
def test_verdict_and_surface_answer_the_same_question(resolved):
    """A phase judged 'realized' shows its whole surface, and only then."""
    realized = _verdict(resolved) == "realized"
    surface = adjudicated_player_action_text(dict(ELEM), resolved)
    assert realized == (surface == ELEM["observable"])
    assert realized == scan_claims_for(ELEM, resolved).realized


def test_both_readers_go_through_the_one_scan(monkeypatch):
    """Patch the scan and BOTH answers move -- the proof there is one.

    Patching the module that defines it, per the house rule; before B13 each
    reader carried its own copy of the loop and this patch would have moved
    neither.
    """
    monkeypatch.setattr(
        common, "scan_claims_for",
        lambda elem, resolved: common.ClaimScan([], [], True))
    realized_everything = {"state_diff": {"claim_dispositions": [
        {"claim_id": "claim:0:intent:0", "status": "rejected"}]}}

    assert _verdict(realized_everything) == "realized"
    assert adjudicated_player_action_text(
        dict(ELEM), realized_everything) == ELEM["observable"]


def test_rows_come_from_the_resolution_and_then_from_its_diff():
    """Order matters: the diff is the later word for a claim-id index."""
    resolved = {
        "claim_dispositions": [{"claim_id": "c1", "status": "deferred"}],
        "state_diff": {"claim_dispositions": [
            {"claim_id": "c1", "status": "realized"}]},
    }
    rows = claim_disposition_rows(resolved)
    assert [row["status"] for row in rows] == ["deferred", "realized"]
    assert claim_disposition_rows(None) == []
    assert claim_disposition_rows({"claim_dispositions": [7, {"claim_id": "c"}],
                                   "state_diff": []}) == [{"claim_id": "c"}]


def test_the_reconciler_reads_the_same_row_source():
    """`_player_claim_findings` no longer spells out where the rows live.

    Live shape from chat 72 turn 45: an asserted effect claim marked
    'rejected' is a player-authority contract violation, and it must be
    caught whether the resolve put the row at the top level or in the diff.
    """
    from agents.director import _player_claim_findings

    interp = {"flow": {"authority_claims": [
        {"claim_id": "claim:0:event", "scope": "effect",
         "subject_id": "vault_door", "predicate": "is shattered"}]}}
    for out, sd in (
            ({"claim_dispositions": [
                {"claim_id": "claim:0:event", "status": "rejected"}]}, {}),
            ({}, {"claim_dispositions": [
                {"claim_id": "claim:0:event", "status": "rejected"}]}),
    ):
        _, _, contract = _player_claim_findings(
            out, sd, interp, [], {}, player_input="I shatter the vault door")
        assert any("may not be rejected" in warning for warning in contract)
