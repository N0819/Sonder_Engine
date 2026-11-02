"""A row the world or the dice caused projects as an EVENT, not an act.

`normalize_causal_ledger` decides what a row IS from what it says -- spoken,
an event "because the world or the dice caused it rather than an actor", or
an act -- and read "the world caused it" off the RAW row's
`authority_mode`. Prose rows never carry one (`UnifiedEvent` has no such
field); the engine fills each row's authority three dozen lines later from
what it handed the source (`authority_by_entity`). So a world pressure's
or an authored event's row projected as `type: "action"` with
`actor: "world_pressure:storm"`, an act by a non-body id, for every reader
that branches on `type == "event"` (review 2026-11-01, director floors F10).
"""

from __future__ import annotations

import pytest

from agents.director import normalize_causal_ledger


@pytest.mark.parametrize("source, mode", [
    ("world_pressure:storm", "world"),
    ("authored_event:0", "world"),
    ("engine:dice:0", "mechanical"),
])
def test_a_world_or_dice_row_is_an_event(source, mode):
    out = normalize_causal_ledger(
        {"ledgers": [{"chrono_id": 1, "item_id": 1, "item_ids": [1],
                      "item_names": ["storm"], "source_entity_id": source,
                      "event": "The storm tears a shutter loose.",
                      "categories": ["entities"]}]},
        authority={source: mode})
    projected = out["sequence"][0]
    assert projected["type"] == "event", projected
    assert projected["description"] == "The storm tears a shutter loose."
    assert out["causal_ledger"][0]["authority_mode"] == mode


def test_a_bodys_row_is_still_an_act():
    out = normalize_causal_ledger(
        {"ledgers": [{"chrono_id": 1, "item_id": 1, "item_ids": [1],
                      "item_names": ["shutter"], "source_entity_id": "character:3",
                      "event": "Mara bars the shutter.", "categories": ["entities"]}]},
        authority={"character:3": "autonomous"})
    assert out["sequence"][0]["type"] == "action"
