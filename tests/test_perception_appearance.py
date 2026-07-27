"""Two perception faults found auditing a 47-turn chat, present start to finish.

1. THE APPEARANCE SUMMARY WAS PASTED AS PROSE. `appearance_of` builds a
   STRUCTURED summary for payload fields -- labelled segments joined by
   semicolons -- which is right for a field a model reads and wrong for a
   narrative view. It reached views verbatim, so nearly every view of every
   turn contained:

       "You see A tall figure in a grey travelling coat, hood raised.;
        clothing state: soaked through, ..."

   -- a capital mid-sentence, a full stop before a semicolon, and the field
   labels themselves narrated. It appeared in BOTH perception steps of a turn,
   which is what read as descriptions being repeated.

2. THE APPEARANCE WAS HANDED OVER EVEN WHEN NOBODY COULD SEE. The payload
   carried `actor_present_appearance` unconditionally. Live, the player was inside
   a sealed interior room with no adjacency to the room its owner stood in -- and the view still described what she
   looked like. The deterministic injector was correctly gated on has_visual
   and stayed silent; this was the channel that went around it.

   The engine already applies exactly this reasoning to IDENTITY one block
   earlier: when no perceiver recognizes the player, the canonical name is
   withheld rather than handed over with an instruction not to use it. Sight
   deserved the same treatment.
"""

from __future__ import annotations

import pytest

from agents.common import _appearance_as_prose, _inject_visible_actor
from scene import appearance_of

BASE = "A tall figure in a grey travelling coat, hood raised."


def _scene(**over):
    scene = {"attire": {}, "overlays": {}}
    scene.update(over)
    return scene


class TestAppearanceReadsAsProse:
    def test_the_live_string_becomes_a_sentence(self):
        raw = appearance_of("H", BASE, _scene(
            attire={"H": {"wearing": ["strips of silk"],
                          "state": ["completely nude", "soaked"]}},
            overlays={"H": ["flushed"]}))
        prose = _appearance_as_prose(raw)

        # The three things that made it read as machine output.
        assert "clothing state:" not in prose
        assert "wearing:" not in prose
        assert ".;" not in prose
        assert "raised," in prose          # the stop became a clause join

    def test_it_lowercases_a_leading_article(self):
        """It is appended after "You see", where a capital A reads as a fault."""
        assert _appearance_as_prose(BASE).startswith("a tall figure")

    def test_a_proper_noun_keeps_its_capital(self):
        assert _appearance_as_prose("Bramwell, tall and pale.") \
            .startswith("Bramwell")

    def test_the_facts_all_survive(self):
        raw = appearance_of("H", BASE, _scene(
            attire={"H": {"wearing": ["a silk robe"], "state": ["torn"]}},
            overlays={"H": ["bleeding"]}))
        prose = _appearance_as_prose(raw)

        for fact in ("grey travelling coat", "a silk robe", "torn", "bleeding"):
            assert fact in prose

    def test_the_injected_sentence_is_grammatical(self):
        view = _inject_visible_actor(
            "The room is quiet.",
            display="Hinami",
            appearance=appearance_of("H", BASE, _scene(
                attire={"H": {"state": ["completely nude"]}})),
            relation={"same_room": True},
        )
        assert "You see a tall figure" in view
        assert "clothing state:" not in view

    def test_empty_and_junk(self):
        assert _appearance_as_prose("") == ""
        assert _appearance_as_prose(None) == ""


class TestAppearanceIsNotHandedOverUnseen:
    def test_the_injector_stays_silent_without_a_visual(self):
        """This half was already correct and must stay so."""
        view = _inject_visible_actor(
            "Darkness presses in.",
            display="Hinami", appearance=BASE,
            relation={"same_room": False, "barrier": "separated"},
        )
        assert view == "Darkness presses in."

    def test_it_speaks_when_there_is_a_visual(self):
        view = _inject_visible_actor(
            "The room is quiet.", display="Hinami", appearance=BASE,
            relation={"same_room": True},
        )
        assert "You see" in view

    def test_a_sealed_interior_has_no_visual_to_the_room_outside(self):
        """The live geometry: an interior room with no adjacency to the room
        its owner stands in. Nothing should see through that."""
        from spatial import has_visual, spatial_rel

        scene = {"rooms": {
            "bedroom": {"name": "Bedroom", "adjacent": []},
            "inside": {"name": "Inside", "parent_entity": "Bramwell",
                       "adjacent": []},
        }}
        assert has_visual(spatial_rel(scene, "inside", "bedroom")) is False
        assert has_visual(spatial_rel(scene, "bedroom", "inside")) is False

    def test_touch_is_untouched_by_the_sight_gate(self):
        """The report was precise: she should not SEE them, though she might
        feel them. Contact is a separate channel and stays open."""
        from spatial import contacts_of, merge_scene_with_diff

        scene = merge_scene_with_diff({
            "rooms": {"inside": {"name": "Inside"}},
            "positions": {"Hinami": "inside", "Bramwell": "inside"},
            "entities": {}, "contacts": [], "scales": {}, "contained": {},
        }, {"contact_ops": [{"op": "add", "actor": "Bramwell",
                             "target": "Hinami", "manner": "press"}]})

        assert contacts_of(scene, "Hinami")
