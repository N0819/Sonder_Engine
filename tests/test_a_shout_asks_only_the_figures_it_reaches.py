"""A raised voice asks a charter figure to answer only where it reaches him.

`declare_charter_figures` admits a figure outside the rooms the beat's people
stand in "only when it was addressed or a voice was raised -- earshot is
what a shout reaches" -- and then admitted EVERY figure in the aperture on
any loud or shouted line, however far off; the figure's own payload, graded
by the cast's hearing gate, then held nothing of the shout and the call was
spent anyway (review 2026-11-01, agents_character_background F20). The
admission now asks that same gate (`presence_hearing`) whether any raised
line reached the figure where it stands.

The gate is stubbed here: what is under test is that the admission ASKS it,
from the figure's own room, for the raised lines -- how far a shout carries
is the hearing model's, and that model is tested where it lives.
"""

from __future__ import annotations

import copy

from agents import background
from tests import test_a_charter_body_speaks_before_the_director_resolves as voices

ROOMS = ["r0", "r1", "r2", "r3"]
SC = {
    "rooms": {r: {"name": r.upper(), "adjacent": [
        {"to": ROOMS[j], "barrier": "closed_door"}
        for j in (i - 1, i + 1) if 0 <= j < len(ROOMS)]}
        for i, r in enumerate(ROOMS)},
    "positions": {"Iris Vale": "r0"},
    "entities": {},
}


def _asked(monkeypatch, temp_db, volume, rows, reaches):
    """`reaches`: {room: grade} -- what the hearing gate says a line in r0
    leaves of itself in each room (absent: nothing)."""
    cid = voices._chat(temp_db)
    asked, graded = [], []
    monkeypatch.setattr(background, "_react_one",
                        lambda ctx, dr, name, *a, **k: asked.append(name) or None)
    monkeypatch.setattr(background, "_player_room", lambda ctx, sc_: "r0")

    def hearing(ctx, sc, name, here, dr=None, **kw):
        def hears(entry, addressed=None):
            graded.append((name, here, entry.get("volume"), entry.get("speaker_room")))
            return reaches.get(here, "none")
        return hears

    monkeypatch.setattr(background, "presence_hearing", hearing)
    interp = copy.deepcopy(voices.TestTheDeclaredBeatIsWhatTheVoiceHears.INTERP)
    for row in interp["ledgers"]:
        if "speech" in (row.get("categories") or []):
            row["volume"] = volume
            row["targets"] = []
    background.declare_charter_figures(voices._ctx(cid), interp, copy.deepcopy(SC), rows, [], 0)
    return asked, graded


def test_a_shout_that_reaches_no_one_three_rooms_off_asks_nobody(monkeypatch, temp_db):
    asked, graded = _asked(monkeypatch, temp_db, "shout",
                           [{"name": "Bran", "room": "r3"}], {"r1": "full", "r2": "voice"})
    assert asked == []
    # Asked of the figure's own room, for the raised line, placed where the
    # player stands (the player's line names no room of its own).
    assert graded and graded[0][:3] == ("Bran", "r3", "shout") and graded[0][3] == "r0"


def test_a_shout_still_asks_the_figure_it_reaches(monkeypatch, temp_db):
    near = [{"name": "Bran", "room": "r2"}]
    asked, _graded = _asked(monkeypatch, temp_db, "shout", near, {"r2": "voice"})
    assert asked == ["Bran"]


def test_a_murmur_asks_no_one_outside_the_room_whatever_it_reaches(monkeypatch, temp_db):
    near = [{"name": "Bran", "room": "r1"}]
    asked, graded = _asked(monkeypatch, temp_db, "normal", near, {"r1": "full"})
    assert asked == [] and graded == []
