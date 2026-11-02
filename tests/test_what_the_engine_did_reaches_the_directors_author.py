"""What the engine did with the last beat reaches the Director that writes
this one -- and the residue of a room the party walks back into reaches the
Director that stages it.

`ctx.tell_director` and `add_engine_notice` file "for next beat" corrections
under the world key `engine_notices` (51 production call sites: an attire
coverage the encoder never stated, a contact moved, a lamp gone out, a
silent beat's warning). `Design.md` ("The Director can see what the engine
did") and `core/pipeline_context.py` ("This one is for the model") say they
reach the Director. Since the prose contract their only two readers were the
staging payloads, which no model call receives: 71 of 132 chats held notices
nobody read (review 2026-11-01, director core F4).

Living-world approach A's destination residue was computed on every movement
beat into a room the party had been away from, handed to the same dead
staging payload, and reported `delivered` to the commit's fire-rate record
(director core F5).

Both now ride the prose author's own payload, only when present, so a beat
with neither is byte-identical. The notices are bounded by a named constant
(`director.ENGINE_NOTICES_SHOWN`, the owner's number to set).
"""

from __future__ import annotations

import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp, prose_resolve_agent


def _author_payloads(calls):
    return [payload for step_key, payload in calls if step_key == "director_prose"]


def test_the_notices_reach_both_stages_authors(temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input='"Quiet night."')
    temp_db.wset(ctx.chat.id, "engine_notices", [
        "attire: nothing knows what Hinami's 'fitted tank top' covers"])
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "The keeper's room is quiet."}, calls=calls))

    ctx.director_interpret = director.director_interpret(ctx, nonce=0)
    director.director_resolve(ctx, nonce=0)

    authors = _author_payloads(calls)
    assert len(authors) >= 2
    for payload in authors:
        assert payload.get("engine_notices") == [
            "attire: nothing knows what Hinami's 'fitted tank top' covers"], payload.keys()


def test_a_beat_with_no_notice_carries_no_key(temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input='"Quiet night."')
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "The keeper's room is quiet."}, calls=calls))
    director.director_resolve(ctx, nonce=0)
    assert all("engine_notices" not in p for p in _author_payloads(calls))


def test_the_notices_are_bounded_and_the_cut_is_said(temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input='"Quiet night."')
    many = [f"notice {n}" for n in range(director.ENGINE_NOTICES_SHOWN + 3)]
    temp_db.wset(ctx.chat.id, "engine_notices", many)
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "The keeper's room is quiet."}, calls=calls))
    director.director_resolve(ctx, nonce=0)
    shown = _author_payloads(calls)[0]["engine_notices"]
    assert shown == many[:director.ENGINE_NOTICES_SHOWN]
    assert [w for w in ctx.warnings if "engine notices" in w and "3" in w], ctx.warnings


def test_the_residue_of_a_room_reentered_reaches_the_resolves_author(
        temp_db, monkeypatch, prose_director):
    import world.routines as routines
    interp = _speech_interp()
    interp["movement"] = {"mover": "self", "to_room": "lamp_room"}
    ctx = _make_ctx(temp_db, interp=interp, player_input="I go up to the lamp.")
    residue = {"room": "lamp_room", "since_turn": 1,
               "facts": ["The lamp has burned down to a stub."]}
    monkeypatch.setattr(routines, "residue_for", lambda *a, **k: dict(residue))
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "The lamp room is dim."}, calls=calls))

    director.director_resolve(ctx, nonce=0)

    payload = _author_payloads(calls)[0]
    assert payload.get("destination_residue", {}).get("facts") == residue["facts"], \
        payload.keys()
    assert ctx.get("_destination_residue_report") == {"to_room": "lamp_room",
                                                      "delivered": 1}
