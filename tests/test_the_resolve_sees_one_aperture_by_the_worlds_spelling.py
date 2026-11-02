"""The resolve derives the rooms in view ONCE, from the destination as the
world spells it.

Every resolve reader of the destination takes the compiler's resolved id
(`director_movement.movement_for_resolve`; its docstring names "the figures
in view"). The charter voices did not: their aperture was derived from the
interpret's RAW `movement.to_room`, the payload's and the floors' from the
compiler's id. On a beat whose destination the compiler re-spelled
("the lamp room" -> `lamp_room`), the voices were laid and heard in an
aperture holding a room id nothing holds, so the destination's bodies were
never voiced, while the present figures, the causal index and the identity
floor were handed a second aperture's bodies -- and the one-entry memo
derived the set twice (review 2026-11-01, director core F9).
"""

from __future__ import annotations

import agents.common as common
import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp, prose_resolve_agent


def test_the_voices_and_the_payload_read_one_aperture_with_the_worlds_spelling(
        temp_db, monkeypatch, prose_director):
    interp = _speech_interp()
    interp["movement"] = {"mover": "self", "to_room": "the lamp room"}
    ctx = _make_ctx(temp_db, interp=interp, player_input="I go up to the lamp.")
    ctx["_player_room"] = "keeper_room"
    ctx.compile_world_context = {"movement": {
        "status": "known", "to_room": "lamp_room"}}
    asked, laid = [], []
    real = common.rooms_in_view

    def counting(ctx_, sc, player_room, destination=None):
        asked.append(destination)
        return real(ctx_, sc, player_room, destination)

    monkeypatch.setattr(common, "rooms_in_view", counting)
    monkeypatch.setattr(common, "lay_charter_figures",
                        lambda ctx_, sc, rooms: laid.append(set(rooms)) or [])
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "She climbs to the lamp room."}))

    director.director_resolve(ctx, nonce=0)

    assert asked == ["lamp_room"], asked
    assert laid and "lamp_room" in laid[0] and "the lamp room" not in laid[0], laid
