"""A body that died where nobody filed a presence for it is still LAID, lying.

`charter_harm.in_a_room` (L11, audit world_charter_behaviours F11) took the
dead out of every presentation of the living: no crowd, no voice, no derived
presence record (`background_presence_records`). Perception laid a body only
from `presence_figures_for_room`'s rows -- the ledger's people plus the
derived records -- so a FRESH corpse, one no durable record had been filed
for, reached no view at all, though `charter_place.charter_placements` still
derives its placement where it fell, with `posture: "lying"`.

The corpse is now a row of its own, marked ``remains``: perception lays it at
its cell with the lying pose, and the voices' figures (`lay_charter_figures`)
lay it on the stage's scene without ever offering it as somebody who could
speak.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

from world.charter import normalize_charter


def _scene():
    return {"rooms": {"hall": {"name": "Hall", "size": "large",
                               "adjacent": []}},
            "positions": {"Rowan": "hall"}, "entities": {}}


def _chat(db):
    from world.charter_runtime import save_registry
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("A fresh corpse", "", time.time()))
    save_registry(cid, {"inn": normalize_charter({
        "key": "inn", "posts": {}, "watch": {},
        "bodies": {
            "clerk": {"name": "Ysra", "place": "hall"},
            "porter": {"name": "Oren", "place": "hall"},
            "guest": {"name": "Tam", "place": "hall", "condition": "dead"},
        }})})
    return cid


def test_the_corpse_is_a_row_laid_lying_and_marked_remains(temp_db):
    from agents.common import presence_figures_for_room
    cid = _chat(temp_db)
    rows = {r["name"]: r for r in presence_figures_for_room(
        cid, _scene(), "hall")}
    assert "Tam" in rows, sorted(rows)
    corpse = rows["Tam"]
    assert corpse.get("remains") is True
    assert corpse["placement"]["posture"] == "lying"
    # The living are rows as before, and none of them is remains.
    assert {"Ysra", "Oren"} <= set(rows)
    assert not any(r.get("remains") for n, r in rows.items() if n != "Tam")


def test_the_voices_lay_the_corpse_but_never_offer_it_a_voice(temp_db):
    from agents.common import lay_charter_figures
    cid = _chat(temp_db)
    scene = _scene()
    ctx = SimpleNamespace(chat={"id": cid}, turn=SimpleNamespace(idx=3,
                                                                 frame_id=None),
                          cast=[], extra_players=[], add_warning=lambda m: None)
    rows = lay_charter_figures(ctx, scene, ["hall"])
    names = [r["name"] for r in rows]
    assert "Tam" not in names, names
    assert {"Ysra", "Oren"} <= set(names)
    assert scene["positions"].get("Tam") == "hall"
    assert (scene.get("poses") or {}).get("Tam", {}).get("posture") == "lying"


def test_a_dead_body_with_a_ledger_record_is_remains_too(temp_db):
    """The ledger keeps the person a body was after it dies; the row that
    record yields is laid lying and is no voice either."""
    from agents.common import lay_charter_figures, presence_figures_for_room
    cid = _chat(temp_db)
    temp_db.wset(cid, "background_presences", {"p_tam": {
        "uid": "p_tam", "name": "Tam",
        "charter_refs": [{"charter": "inn", "body": "guest"}],
        "sketch": {"station_room": "hall", "role_hint": "a guest"},
        "first_turn": 0, "last_turn": 0}})
    rows = {r["name"]: r for r in presence_figures_for_room(
        cid, _scene(), "hall")}
    assert rows["Tam"].get("remains") is True
    assert rows["Tam"]["placement"]["posture"] == "lying"
    scene = _scene()
    ctx = SimpleNamespace(chat={"id": cid}, turn=SimpleNamespace(idx=3,
                                                                 frame_id=None),
                          cast=[], extra_players=[], add_warning=lambda m: None)
    voices = [r["name"] for r in lay_charter_figures(ctx, scene, ["hall"])]
    assert "Tam" not in voices, voices
    assert (scene.get("poses") or {}).get("Tam", {}).get("posture") == "lying"
