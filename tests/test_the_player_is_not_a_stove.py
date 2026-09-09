"""The player-room resolver reads `positions` as a body roster, and it is not.

Measured 2026-09-08 while chasing "turns are taking unusually longer than
usual" (owner, chat 114 replayed at head): the `utility` role was the third
largest consumer of a turn -- ONE call, 21-43 seconds -- and every one of them
was `_llm_resolve_player_room` being asked which of several rooms the player
stands in. The candidate set that decides whether to ask was built from every
non-cast key in `positions`, so a moored boat in one room and a stove in
another made two candidates out of a scene holding exactly one person.

This is review 2026-09-07 A56's class at its third site; `story/room_slice`
and `web/world_routes._is_body` were the first two, fixed the same day. On the
twelve stored scenes, six went from "ask a model" to a deterministic answer.

The filter is written so it can only ever REMOVE a call: a scene standing no
non-cast body at all falls back to the list it has always guessed from.
"""
from __future__ import annotations

import pytest

from agents.common import _resolve_player_room


PLAYER = {"name": "Hinami"}


def _scene(positions, entities):
    return {"rooms": {r: {"name": r} for r in set(positions.values())},
            "positions": dict(positions), "entities": dict(entities)}


def test_one_person_among_things_needs_no_model_call(monkeypatch):
    """The reported shape. The player is not in `positions` under her own
    name -- that is the only reason this resolver runs at all -- and the
    things stand in three different rooms."""
    called = []
    monkeypatch.setattr("agents.common._llm_resolve_player_room",
                        lambda *a, **k: called.append(1))
    scene = _scene(
        {"The Doctor": "quay", "The Moon": "sky",
         "Cast-Iron Stove": "galley", "The TARDIS": "quay"},
        {"The Doctor": {"kind": "person"}, "The Moon": {"kind": "celestial"},
         "Cast-Iron Stove": {"kind": "fixture"},
         "The TARDIS": {"kind": "vehicle"}})
    cast = []          # the Doctor is unattached here, so he is a candidate
    assert _resolve_player_room(scene, PLAYER, {}, cast, "you look around") == "quay"
    assert not called, "a model was asked a question the scene answered"


def test_two_bodies_in_two_rooms_still_asks(monkeypatch):
    """The complement, and the reason the resolver exists: this narrows the
    question rather than answering it. Chats 117 and 122 are really like
    this."""
    asked = []

    def _fake(sc, pers, cast, interp, player_input):
        asked.append(sorted((sc.get("positions") or {}).keys()))
        return "hold"

    monkeypatch.setattr("agents.common._llm_resolve_player_room", _fake)
    scene = _scene(
        {"The Doctor": "quay", "Watchkeeper": "hold", "The Moon": "sky"},
        {"The Doctor": {"kind": "person"}, "Watchkeeper": {"kind": "person"},
         "The Moon": {"kind": "celestial"}})
    assert _resolve_player_room(scene, PLAYER, {}, [], "") == "hold"
    assert asked, "two bodies in two rooms is the ambiguity it is for"


def test_the_resolver_is_offered_bodies_only(monkeypatch):
    """One layer down, same class: the keys the model chooses between. It
    answers with a key and the caller accepts any key `positions` holds, so
    offering the stove made "the player is where the stove is" a reachable
    answer."""
    seen = {}

    def _capture(role, system, user, **kw):
        import json
        seen.update(json.loads(user))
        return '{"key": "Watchkeeper"}'

    monkeypatch.setattr("agents.common.chat_complete", _capture)
    monkeypatch.setattr("agents.common.get_prompt", lambda *a, **k: "sys")
    from agents.common import _llm_resolve_player_room
    scene = _scene(
        {"The Doctor": "quay", "Watchkeeper": "hold",
         "Cast-Iron Stove": "galley", "The Moon": "sky"},
        {"The Doctor": {"kind": "person"}, "Watchkeeper": {"kind": "person"},
         "Cast-Iron Stove": {"kind": "fixture"},
         "The Moon": {"kind": "celestial"}})
    assert _llm_resolve_player_room(scene, PLAYER, [], {}, "") == "hold"
    assert sorted(seen["position_keys"]) == ["The Doctor", "Watchkeeper"]
    assert "Cast-Iron Stove" not in seen["positions"]


def test_a_scene_of_only_things_guesses_as_it_always_did(monkeypatch):
    """The filter may only ever REMOVE a call. A scene that stands no
    non-cast body has not placed the player either, and this is the answer
    that path has always given -- narrowing it to zero candidates would have
    turned a free guess into a model call, which is backwards."""
    called = []
    monkeypatch.setattr("agents.common._llm_resolve_player_room",
                        lambda *a, **k: called.append(1))
    scene = _scene({"Cast-Iron Stove": "galley"},
                   {"Cast-Iron Stove": {"kind": "fixture"}})
    assert _resolve_player_room(scene, PLAYER, {}, [], "") == "galley"
    assert not called


def test_the_committed_position_still_wins(monkeypatch):
    """The ladder above this is untouched: a scene that places the player by
    name never reaches the candidate set at all."""
    called = []
    monkeypatch.setattr("agents.common._llm_resolve_player_room",
                        lambda *a, **k: called.append(1))
    scene = _scene({"Hinami": "quay", "Watchkeeper": "hold"},
                   {"Hinami": {"kind": "person"},
                    "Watchkeeper": {"kind": "person"}})
    assert _resolve_player_room(scene, PLAYER, {}, [], "") == "quay"
    assert not called
