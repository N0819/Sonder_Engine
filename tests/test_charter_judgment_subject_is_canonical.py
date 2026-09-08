"""A stance is filed under the engine's name for a person, never the label.

Review 2026-09-07 B7. `charter_observe.evidence_claim` keys the actor under
``subject`` by the canonical name and renders ``about`` /
``public_evidence.actor`` as the witnesses' LABEL -- "the slight woman" for
a body nobody has told a name. `charter_social._signals_in_claim` read the
rendered fields, so every judgment a witnessed speech act moved was filed
under a label that no other reader keys by: `judgment_view` filters its
subjects against the canonical body/figure roster, ties walk canonical
pairs, and `judgments[holder][other]` is canonical everywhere. The stance
was written and never found again.
"""

from __future__ import annotations

from world.charter import (judgment_of, judgment_view,
                           update_judgments_from_minds)
from world.charter_news import news_claim
from world.charter_observe import evidence_claim


def _threat(actor="Rowan Ashgrave"):
    return {
        "source_id": "speech:1", "kind": "speech", "actor": actor,
        "exact_quote": '"Cross me again and you will not walk out."',
        "speech_acts": [{"kind": "threat", "target": "porter"}],
        "visibility": "overt", "salience": 0.8,
    }


def test_witnessed_speech_files_its_stance_under_the_canonical_name():
    claim = evidence_claim(_threat(), 4, 12.0, "hall",
                           label="the tall stranger")
    # The claim keeps both representations, and they disagree on purpose.
    assert claim["subject"] == "Rowan Ashgrave"
    assert claim["about"] == "the tall stranger"
    assert claim["public_evidence"]["actor"] == "the tall stranger"

    judgments, movements = update_judgments_from_minds(
        {}, {"porter": {claim["body"]: claim}})

    assert list(judgments.get("porter") or {}) == ["Rowan Ashgrave"]
    assert judgment_of(judgments, "porter", "Rowan Ashgrave")["fear"] > 0.0
    assert judgment_of(judgments, "porter", "the tall stranger") is None
    assert [row["subject"] for row in movements] == ["Rowan Ashgrave"]

    # And the stance is now findable by the reader that filters against the
    # canonical roster -- the check that failed silently before.
    shown = judgment_view(judgments, "porter", subjects=["Rowan Ashgrave"])
    assert [row["subject"] for row in shown] == ["Rowan Ashgrave"]


def test_the_same_person_labelled_twice_is_one_subject():
    first = evidence_claim(_threat(), 4, 12.0, "hall", label="the stranger")
    second = dict(evidence_claim(_threat(), 9, 13.0, "hall",
                                 label="Rowan Ashgrave"))
    second["body"] = second["body"] + ":again"
    judgments, _ = update_judgments_from_minds(
        {}, {"porter": {first["body"]: first, second["body"]: second}})
    stance = judgment_of(judgments, "porter", "Rowan Ashgrave")
    assert len(stance["reasons"]) == 2


def test_a_claim_writer_with_no_canonical_field_still_keys_by_its_actor():
    """`news_claim` mints no ``subject``; its ``about`` IS the canonical name."""
    claim = news_claim({"kind": "commitment_defaulted", "actor": "Oren Vell",
                        "at_hours": 12.0, "place": "hall"}, 12.0)
    assert "subject" not in claim
    judgments, _ = update_judgments_from_minds(
        {}, {"porter": {claim["body"]: claim}})
    assert judgment_of(judgments, "porter", "Oren Vell")["trust"] < 0.0
