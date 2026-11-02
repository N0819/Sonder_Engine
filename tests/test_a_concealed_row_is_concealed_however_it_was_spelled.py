"""A row's `visibility` and `commitment` are canonical from the moment the
ledger is normalised, so no two readers can read one row two ways.

`normalize_causal_ledger` copied both fields raw, while the firewall reader
(`composer.concealed_from_observer`) matches exactly `"concealed"` and the
floors in `director_floors` compare `.strip().lower()`. A whispered aside the
encoder (whose schema declares `visibility: str`) filed as "Concealed " was
concealed to the floors, which rewrote its `conceal_from`, and OVERT to the
reader, which delivered it in full to the body it was hidden from. The same
split for `commitment`: "Contestable" was contestable to the resolve's event
inputs and asserted to `already_happened` (review 2026-11-01, director floors
F1 -- a LEAK). Measured on the owner's database, 3000 recent interpret and
resolve variants: besides `overt` (4877 rows) the ledger carried `public` 97,
`normal` 87, `visible` 15, `private` 8, `unobscured` 7, `open` 7,
`concealed` 4, `low` 4, `plain_sight` 4 ... -- so a value outside the two
canonical words is ordinary, and almost always means overt. The fold is the
dialogue log's own (`concealed`, `hidden`, `secret` -> concealed; anything
else overt), stated once, at ingest.
"""

from __future__ import annotations

import pytest

from agents.composer import concealed_from_observer
from agents.director import normalize_causal_ledger


def _row(**fields):
    row = {"chrono_id": 1, "item_id": 1, "item_ids": [1], "item_names": ["Ivo"],
           "source_entity_id": "persona:1", "event": "Meet me at the mill.",
           "categories": ["speech"], "targets": ["Mara"]}
    row.update(fields)
    return row


@pytest.mark.parametrize("spelled", ["Concealed ", "CONCEALED", "hidden", "secret"])
def test_a_concealed_line_is_concealed_to_the_firewall_reader(spelled):
    out = normalize_causal_ledger({"ledgers": [_row(visibility=spelled,
                                                    conceal_from=["Ivo"])]})
    projected = out["sequence"][0]
    assert projected["visibility"] == "concealed"
    assert out["causal_ledger"][0]["visibility"] == "concealed"
    assert concealed_from_observer(projected, "Ivo") is True


@pytest.mark.parametrize("spelled", ["public", "normal", "visible", "open", "", None])
def test_an_overt_spelling_stays_overt(spelled):
    out = normalize_causal_ledger({"ledgers": [_row(visibility=spelled)]})
    assert out["sequence"][0]["visibility"] == "overt"


@pytest.mark.parametrize("spelled, canonical", [
    ("Contestable", "contestable"), (" contestable ", "contestable"),
    ("asserted", "asserted"), ("", "asserted"), (None, "asserted"),
])
def test_the_commitment_is_canonical_at_ingest(spelled, canonical):
    out = normalize_causal_ledger({"ledgers": [_row(
        categories=["poses"], event="Ivo lunges for the knife.",
        commitment=spelled)]})
    assert out["causal_ledger"][0]["commitment"] == canonical
    assert out["sequence"][0]["commitment"] == canonical
