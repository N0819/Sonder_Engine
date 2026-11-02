"""A row about a doorway is not reported "routed" when nothing routes it.

`_route_doorway_rows` added `rooms` to the categories of a row whose object
is a doorway in view and warned "the engine routed rooms". Under the hands,
an added category dispatched the spatial hand, which wrote the edge. Under
the prose contract a row's categories are the channels the encoder ALREADY
wrote, and an owner runs only for channels granted or written
(`director_prose.dispatch`): the added category re-asks nobody, the door
stays as the encoder left it, and the warning says the opposite of what
happened (review 2026-11-01, director core F13). The rule it stood for is
the encoder's own: "A DOOR BETWEEN ROOMS IS ITS EDGE" (`encoder/rooms.txt`,
`encoder/core.txt`).
"""

from __future__ import annotations

import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp, encoder_event

SCENE = {
    "location": "Farm",
    "rooms": {
        "scullery": {"name": "Scullery", "adjacent": [
            {"to": "yard", "barrier": "closed_door", "name": "the back door to the yard"}]},
        "yard": {"name": "Farmyard", "adjacent": [
            {"to": "scullery", "barrier": "closed_door", "name": "the back door to the yard"}]},
    },
    "positions": {"The Stranger": "scullery", "Mara": "scullery"},
    "entities": {}, "attire": {}, "overlays": {},
}


def test_no_doorway_row_is_reported_routed_on_a_prose_beat(
        temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, scene=SCENE, interp=_speech_interp(),
                    player_input="I push the yard door wide.")
    ctx.director_interpret = None

    def fake(role, step_key, system, payload, **kw):
        if step_key == "director_prose":
            return {"prose": "The Stranger pushes the yard door wide."}
        if step_key == "director_specialist":
            return {"events": [dict(encoder_event(
                "The Stranger pushes the yard door wide."),
                item_names=["yard door"])]}
        return {}
    monkeypatch.setattr(director, "_agent_json", fake)

    out = director.director_interpret(ctx, nonce=0)

    assert not [w for w in ctx.warnings if "the engine routed rooms" in w], ctx.warnings
    assert all("rooms" not in (row.get("categories") or [])
               for row in out.get("ledgers") or []), out.get("ledgers")
