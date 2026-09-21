"""A body in a room can see the other bodies in that room.

`_present_others` builds a presence's co-located list from the player and
`ctx.cast` -- the registered characters -- and from nothing else. Other
BACKGROUND PRESENCES standing in the same room were never named, so a body
was told about the one attached character in front of it and not about the
four colleagues at its elbow.

Measured (Aldermill, fourth run, 2026-09-19, idx 15). Sal Weatherby ordered a
small ale in a taproom holding an innkeeper, a tapster, a cook and an ostler.
The ostler answered it exactly as an ostler should --

    "I mind the horses, mistress. You'll want the tapster for ale."
    Watisett jerks a muck-spattered thumb toward the kitchen passage.

-- and pointed AWAY, at a door, for a tapster standing in the same room. His
payload read `present_others: ["the weathered woman"]`. He did not point
wrongly; he pointed with what he had been given.

Same gates as the cast half, because a presence is a mind like any other: the
room decides admission, and what it may CALL them is its own recognition
(`_presence_recognizes`), so an unmet colleague arrives as an appearance
label and never as a name.
"""

import types

import agents.background as background


def _ctx():
    chat = {"id": 1, "persona_id": None}
    return types.SimpleNamespace(
        chat=chat, turn=types.SimpleNamespace(idx=15, frame_id=2), cast=[],
        get=lambda k, d=None: d)


SCENE = {"rooms": {"taproom": {}, "yard": {}}, "positions": {}}


def test_a_colleague_in_the_room_is_in_the_payload(monkeypatch):
    monkeypatch.setattr(background, "_room_presences_in", lambda ctx, sc, room: [
        ("Robanot Appleytonwood", "a rangy man in a stained apron"),
        ("Host Pennytonwood", "a broad man with a ledger"),
    ])
    others = background._present_others(_ctx(), SCENE, "taproom")
    assert "a rangy man in a stained apron" in others, (
        "a tapster standing in the room must be somebody the ostler can "
        "point AT rather than away from")
    assert len(others) == 2


def test_a_colleague_in_another_room_is_not(monkeypatch):
    monkeypatch.setattr(background, "_room_presences_in", lambda ctx, sc, room: [])
    assert background._present_others(_ctx(), SCENE, "yard") == []


def test_an_unknown_room_still_fails_closed(monkeypatch):
    monkeypatch.setattr(background, "_room_presences_in", lambda ctx, sc, room: [
        ("Robanot Appleytonwood", "a rangy man")])
    assert background._present_others(_ctx(), SCENE, "") == []


def test_a_recognised_colleague_is_named(monkeypatch):
    """Recognition is the presence's OWN, as everywhere else in this file."""
    monkeypatch.setattr(background, "_room_presences_in", lambda ctx, sc, room: [
        ("Robanot Appleytonwood", "a rangy man in a stained apron")])
    others = background._present_others(
        _ctx(), SCENE, "taproom", recognized={"Robanot Appleytonwood"})
    assert others == ["Robanot Appleytonwood"]
