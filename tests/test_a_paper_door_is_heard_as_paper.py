"""A paper door is heard as paper, from both sides, and a line keeps its
addressee.

Chat 168 (2026-10-12): Tamamo stood at Hinami's shoji and said "Hinami? It
is late." The engine has always known a shoji is not an oak door -- an edge's
`material` moves a door one rung more open for sound alone
(`spatial_senses._material_shifted_barrier`) -- but no card ever asked for
it, and the mirror that copies a doorway's barrier and name to its other side
left the material behind. So every shoji in every story was heard as solid
wood. The cards now ask for `material`, and the mirror carries it.

A whisper through a shut door stays breath-private -- the owner's ruling of
2026-09-26 -- so this is about a voice, a footfall, a door: whatever a paper
door lets through, from either side.
"""
from __future__ import annotations

from agents.director import _restamped_target
from world.spatial import hear_level, merge_scene_with_diff, spatial_rel_between


def _house(material_on_hall=None):
    edge = {"to": "bedroom", "barrier": "closed_door", "name": "a shoji door"}
    if material_on_hall:
        edge["material"] = material_on_hall
    return {"rooms": {
        "hall": {"name": "Hall", "adjacent": [edge]},
        "bedroom": {"name": "Bedroom",
                    "adjacent": [{"to": "hall", "barrier": "closed_door",
                                  "name": "a shoji door"}]}},
        "positions": {"Tamamo": "hall", "Hinami": "bedroom"}}


def _bedroom_edge(scene):
    return next(e for e in scene["rooms"]["bedroom"]["adjacent"] if e["to"] == "hall")


def test_the_material_written_on_one_side_is_the_doorways():
    scene = merge_scene_with_diff(_house(), {"rooms": {"hall": {"adjacent": [
        {"to": "bedroom", "barrier": "closed_door", "material": "paper"}]}}})
    assert _bedroom_edge(scene).get("material") == "paper"


def test_a_voice_through_a_paper_door_carries_from_the_far_side():
    wood = merge_scene_with_diff(_house(), {})
    paper = merge_scene_with_diff(_house(), {"rooms": {"hall": {"adjacent": [
        {"to": "bedroom", "barrier": "closed_door", "material": "paper"}]}}})
    heard = {name: hear_level(spatial_rel_between(scene, "Hinami", "Tamamo"), "normal")
             for name, scene in (("wood", wood), ("paper", paper))}
    assert heard == {"wood": "fragment", "paper": "full"}, heard


def test_a_whisper_through_it_stays_breath_private():
    paper = merge_scene_with_diff(_house(), {"rooms": {"hall": {"adjacent": [
        {"to": "bedroom", "barrier": "closed_door", "material": "paper"}]}}})
    assert hear_level(spatial_rel_between(paper, "Hinami", "Tamamo"), "whisper") != "full"


def test_a_line_whose_declaration_named_nobody_keeps_the_rows_addressee():
    assert _restamped_target({"targets": []}, {"intended_target": "Hinami"}) == "Hinami"
    assert _restamped_target({"targets": ["Tamamo"]}, {"intended_target": "Hinami"}) == "Tamamo"
    assert _restamped_target({"intended_target": "Kaede"}, {"intended_target": "Hinami"}) == "Kaede"
    assert _restamped_target({}, {}) is None
