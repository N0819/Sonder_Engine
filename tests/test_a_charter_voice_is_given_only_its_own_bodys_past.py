"""A charter body's voice is handed the institutional context of THAT body,
named by its record's own charter refs -- never by a display name two
bodies can share.

`charter_runtime.presence_view` matched a body by display name across every
charter and returned up to two, so an inn's and a mill's "Ada Fenn" standing
in one square handed one voice both private slices -- two people sharing a
head (audit world_charter_core F1, reproduced). Lane L11 made it ONE BODY OR
NONE, resolved outright by the presence record's exact `charter_refs`; the
call site here (`_react_one`) now passes them.
"""

from __future__ import annotations

import world.charter_runtime as charter_runtime
from agents import background

from tests.test_background_character_reply import _setup

REFS = [{"charter": "mill", "body": "miller:0002"}]


def test_the_voice_asks_for_its_own_body_by_its_refs(temp_db, monkeypatch):
    scene = {"location": "x", "rooms": {"square": {"name": "Square", "adjacent": []}},
             "positions": {"Ada Fenn": "square"}, "entities": {}, "attire": {},
             "overlays": {}}
    _cid, ctx = _setup(temp_db, scene=scene)
    asked = {}

    def view(cid, place, name, frame_id=None, figures=None, **kw):
        asked.update(kw, place=place, name=name)
        return []

    monkeypatch.setattr(charter_runtime, "presence_view", view)
    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {"reacts": False})
    rec = {"name": "Ada Fenn", "charter_refs": REFS,
           "sketch": {"station_room": "square"}}
    background._react_one(ctx, {"dialogue_log": []}, "Ada Fenn", [], set(), scene, rec, 0)
    assert asked.get("name") == "Ada Fenn" and asked.get("place") == "square"
    assert asked.get("refs") == REFS
