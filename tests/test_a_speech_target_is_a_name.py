"""A PERSON A LINE IS SAID TO HAS ONE SPELLING ON THE LEDGER: THEIR NAME.

O28 of the Cwm Du run (chat 167, turn 4630): the encoder wrote the
player's line as said to `character:84` -- the card allows keys or readable
names -- and the handle reached the dialogue log, the evidence and the
narrator's own account of what the player declared ("says: Nell Hartley ->
character:84"), where every other beat carried "Ffion Rees". Two spellings
of one person split the readers that accept both from the one that read
handles alone. `normalize_causal_ledger` now maps every identity handle to
the name it stands for, and the one handle-only reader -- which cast
members a spoken row addresses -- reads names too.
"""

from __future__ import annotations

import json

from agents.director import _addressed_characters, normalize_causal_ledger


def _row(chrono, **kw):
    row = {"chrono_id": chrono, "item_ids": [chrono], "item_names": ["a line"],
           "source_entity_id": "persona:22", "source_event_id": "scene:1",
           "event": "Nell asks the way", "categories": ["speech"]}
    row.update(kw)
    return row


INDEX = {"persona:22": "Nell Hartley", "character:84": "Ffion Rees",
         "Gwenafryn Abogwyn": "Gwenafryn Abogwyn"}


def test_a_handle_on_a_spoken_row_becomes_the_name_it_stands_for():
    out = {"ledgers": [_row(1, targets=["character:84"]),
                       _row(2, targets=["Gwenafryn Abogwyn", "lamp_room_book"])]}
    normalize_causal_ledger(out, identity_index=INDEX)
    targets = [row["targets"] for row in out["causal_ledger"]]
    assert targets == [["Ffion Rees"], ["Gwenafryn Abogwyn", "lamp_room_book"]]
    assert "character:84" not in json.dumps(out["causal_ledger"])


def test_the_cast_a_spoken_row_addresses_is_read_by_name_or_handle():
    cast = [{"id": 84, "sheet": json.dumps({"name": "Ffion Rees"})},
            {"id": 85, "sheet": json.dumps({"name": "Emrys Vaughan"})}]
    rows = [_row(1, targets=["Ffion Rees"]), _row(2, targets=["character:85"]),
            _row(3, targets=["Ffion Rees"]), _row(4, targets=["Prysenlas Cadyfawr"]),
            _row(5, targets=["Emrys Vaughan"], categories=["action"])]
    assert _addressed_characters(rows, cast) == [84, 85]
