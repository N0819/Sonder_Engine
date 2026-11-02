"""The page's identity floor fails CLOSED.

`narration._page_identity_scrub` keeps a stranger's canonical name out of
the three fields that carry the Director's own words about the player's
conduct (`player_declared`, the player's acts in `current_events`,
`spatial_frame.turned`) -- the measured Saltmarsh case was "Goddricey took up
the mooring line" on the page of a player nobody had told his name (scratch
chat 170, 2026-10-11). When its roster could not be built it returned the
identity function, "the Director's words about the player went as written":
exactly the leak it exists to stop, while the same module's
`_player_perceives` states the opposite policy -- "a thin beat is a worse
page, a leaked act is a broken firewall" (review 2026-11-01,
agents_narration_planner F7). Now the words are withheld: the declaration
keeps its shape and its delivery, and loses only the Director-written text
that could name somebody; the player's own input is on the page already.
"""

from __future__ import annotations

import json
import types

from agents import narration


def _ctx():
    warnings = []
    ctx = types.SimpleNamespace(
        chat={"id": 1, "persona_id": None},
        turn=types.SimpleNamespace(idx=3, id=1, frame_id=None),
        # A cast row with no card: the roster cannot be read.
        cast=[{"id": 9}],
        warnings=warnings, add_warning=warnings.append,
        get=lambda key, default=None: default)
    return ctx


def _scrub():
    ctx = _ctx()
    scrub = narration._page_identity_scrub(
        ctx, "Tamsin", {"rooms": {}, "positions": {}, "entities": {}}, {},
        lambda name: "the old square-shouldered ferry hand")
    return ctx, scrub


def test_a_roster_that_cannot_be_built_names_nobody():
    ctx, scrub = _scrub()
    out = scrub("Goddricey took up the mooring line")
    assert "Goddricey" not in str(out)
    assert any("identity roster failed" in w for w in ctx.warnings)


def test_the_declaration_keeps_its_shape_and_loses_the_directors_words():
    _ctx_, scrub = _scrub()
    declared = {
        "sequence": [
            {"type": "action", "event_id": "e1", "visibility": "overt",
             "targets": ["Goddricey"], "onset": "reaches past Goddricey for the line"},
            {"type": "speech", "volume": "normal", "intended_target": "Goddricey",
             "targets": ["Goddricey"], "visibility": "overt"}],
        "spoke": True,
        "action": "takes the line from Goddricey",
        "private_thought": "Goddricey is lying",
    }
    out = narration._declared_through(declared, scrub)
    assert "Goddricey" not in json.dumps(out)
    assert [e["type"] for e in out["sequence"]] == ["action", "speech"]
    assert out["sequence"][1]["volume"] == "normal" and out["spoke"] is True


def test_a_floor_that_was_built_scrubs_as_before():
    ctx = _ctx()
    ctx.cast = []
    scrub = narration._page_identity_scrub(
        ctx, "Tamsin",
        {"rooms": {"quay": {"name": "Quay"}},
         "positions": {"Goddricey": "quay", "Tamsin": "quay"},
         "entities": {"g": {"name": "Goddricey", "kind": "person",
                            "appearance": "an old square-shouldered ferry hand"}}},
        {}, lambda name: "the old square-shouldered ferry hand")
    declared = {"sequence": [{"type": "action", "onset": "reaches past Goddricey"}],
                "spoke": False, "action": None, "private_thought": None}
    out = narration._declared_through(declared, scrub)
    assert out["sequence"][0]["onset"] == "reaches past the old square-shouldered ferry hand"
