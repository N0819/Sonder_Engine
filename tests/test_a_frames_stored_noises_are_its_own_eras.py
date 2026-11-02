"""The noises a beat stores are the noises of the beat's own era.

`_record_sensory_events` laid the off-screen creatures' noises
(`charter_noises`) into the stored `scene.sensory_events` from
`registry_for(cid)` -- no frame, which `registry_for` reads as the PRESENT
era's town. Perception reads the beat's own (`registry_for(cid,
ctx.turn.frame_id)`), so in a frame of another era (a flashback with its own
town) the stored record carried the present's creature noises wherever room
ids coincided, and that era's own creatures were then fed the present's
sounds (`hearing_for_creatures` reads the stored record). Two readers of one
fact, disagreeing by frame (review 2026-11-01, persist_scene_entities F8).
"""

from __future__ import annotations

import time

import world.charter_runtime as charter_runtime
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import _record_sensory_events
from world.spatial import SENSORY_EVENTS_KEY

FLASHBACK = 7

TOWNS = {
    None: {"items": {"wolves": {"state": {"heard": [
        {"place": "hall", "sound": "claws on the flagstones",
         "level": "audible"}]}}}},
    FLASHBACK: {"items": {"wolves": {"state": {"heard": [
        {"place": "hall", "sound": "a low growl behind the panelling",
         "level": "audible"}]}}}},
}


def _ctx(frame_id):
    return PipelineContext(
        chat=ChatData(id=1, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=1, idx=5, player_input="",
                      created=time.time(), frame_id=frame_id),
        cast=[], input="")


def _stored(monkeypatch, frame_id):
    monkeypatch.setattr(charter_runtime, "registry_for",
                        lambda cid, frame_id=None: TOWNS[frame_id])
    sc = {"rooms": {"hall": {"name": "Hall"}}, "positions": {}}
    _record_sensory_events(_ctx(frame_id), 1, sc, {}, 5)
    return " | ".join(e.get("detail", "")
                      for e in (sc.get(SENSORY_EVENTS_KEY) or {})
                      .get("events", []))


def test_a_flashback_stores_its_own_eras_noises(monkeypatch):
    heard = _stored(monkeypatch, FLASHBACK)
    assert "growl" in heard
    assert "claws" not in heard, \
        "the present era's creature was recorded into the flashback"


def test_the_present_stores_the_present(monkeypatch):
    heard = _stored(monkeypatch, None)
    assert "claws" in heard and "growl" not in heard
