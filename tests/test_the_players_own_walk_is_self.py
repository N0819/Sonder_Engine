"""The declaring player's own walk is spelled `mover: "self"`, at ingest.

The encoder names a walker as the beat names them, so the player's own move
arrived as `"mover": "Tamsin Coyle"` (scratch story 165, turn 4581,
2026-10-07). The field's readers split over the spelling: the movement subject
resolver accepted "self", "player" or the name; the follow-stop floor and the
commit's heard-rooms read accepted only "self"; perception's own-walk channel
read anything else as a vehicle. The player walked into the inn while
following the pilot who stayed outside, the stop never fired, and the follow
survived into the committed scene with the two in different rooms.
"""

import agents.director as director
from tests.director_fakes import encoder_event
from tests.test_interpret_reconciliation import _full_repair, _run


def test_only_the_players_own_spellings_fold():
    for spelled in ("", "self", "Self", "player", "The Stranger", "the stranger"):
        assert director._mover_as_self(
            {"mover": spelled, "to_room": "hallway"}, "The Stranger"
        )["mover"] == "self", spelled
    for other in ("the carriage", "Mara"):
        assert director._mover_as_self(
            {"mover": other}, "The Stranger")["mover"] == other
    assert director._mover_as_self(None, "The Stranger") is None


def test_the_encoder_naming_the_player_is_the_players_own_walk(
        temp_db, prose_director, monkeypatch):
    walk = encoder_event(
        "The Stranger walks into the hallway.",
        movement={"mover": "The Stranger", "to_room": "hallway",
                  "arrives": True},
        transforms=[{"item": "The Stranger",
                     "patch": {"positions": {"The Stranger": "hallway"}}}])
    _ctx, out, _steps = _run(temp_db, monkeypatch, encoder={
        "events": [walk], "missing_tools": [], "missing_referents": [],
        "notes": []})
    assert out["movement"]["to_room"] == "hallway"
    assert out["movement"]["mover"] == "self"


def test_a_repair_naming_the_player_is_the_players_own_walk(
        temp_db, prose_director, monkeypatch):
    _ctx, out, _steps = _run(temp_db, monkeypatch,
                             repair=_full_repair(mover="The Stranger"))
    assert out["movement"]["to_room"] == "armory"
    assert out["movement"]["mover"] == "self"
