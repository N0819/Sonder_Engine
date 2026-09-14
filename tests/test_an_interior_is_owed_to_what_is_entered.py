"""An interior is owed to the entity a body goes into or the span is about,
never to everything the span touches.

Scratch play 2026-09-14, chat 7 turn 11: "pushed the porch door wide with the
lantern held up" listed the lantern among the span's targets; the interior
requirement read targets, demanded an inside for a lantern, the spatial hand
refused to mint one, and its whole reply -- the walk into the chapel included
-- was thrown away while the narrator wrote her at the porch anyway. A thing a
hand carries has no inside to author.
"""

import pytest

from agents.director import _require_complete_entity_interiors


def _scene():
    return {"rooms": {"quay": {"name": "Quay"}}, "positions": {}}


def _view(span):
    return {"spans": [span]}


def test_a_lantern_among_the_targets_owes_no_interior():
    extras = {"entity_interiors": {"lantern": {
        "name": "lantern", "portable": True, "container": False,
        "interior_rooms": [], "aliases": ["the lantern"]}}}
    span = {"categories": ["rooms", "poses"], "object_name": "porch door",
            "targets": ["persona:7", "lantern"], "movement": None}
    _require_complete_entity_interiors({}, _scene(), _view(span), extras, "interpret")


def test_a_walk_into_an_entity_still_owes_its_interior():
    extras = {"entity_interiors": {"tardis": {
        "name": "the TARDIS", "portable": False, "container": True,
        "interior_rooms": [], "aliases": []}}}
    span = {"categories": ["rooms"], "object_name": "the TARDIS",
            "targets": [], "movement": {"to_room": "tardis", "arrives": True}}
    with pytest.raises(RuntimeError):
        _require_complete_entity_interiors(
            {"orchestration": {}}, _scene(), _view(span), extras, "interpret")


def test_a_span_about_a_portable_thing_owes_nothing_either():
    extras = {"entity_interiors": {"carpetbag": {
        "name": "a carpet bag", "portable": True, "container": True,
        "interior_rooms": [], "aliases": []}}}
    span = {"categories": ["rooms"], "object_name": "a carpet bag",
            "targets": [], "movement": None}
    # A portable container may be opened, and its inside is the objects
    # hand's; nothing a body walks into is minted for it here.
    with pytest.raises(RuntimeError):
        _require_complete_entity_interiors(
            {"orchestration": {}}, _scene(), _view(span), extras, "interpret")
