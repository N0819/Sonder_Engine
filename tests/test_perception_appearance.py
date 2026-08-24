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
from agents.perception import _appearance_ledger_changed
from story.scene import appearance_of

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

    def test_structured_overlay_renders_description_not_python_dict(self):
        raw = appearance_of("H", BASE, _scene(overlays={"H": [{
            "name": "flush", "description": "red across her cheeks"}]}))

        assert "red across her cheeks" in raw
        assert "{'name':" not in raw

    def test_reasserted_overlay_does_not_reearn_full_appearance(self):
        before = _scene(overlays={"H": [{
            "name": "flush", "description": "red across her cheeks"}]})
        same = _scene(overlays={"H": [{
            "name": "flush", "description": "red across her cheeks"}]})
        changed = _scene(overlays={"H": [{
            "name": "flush", "description": "fading from her cheeks"}]})

        assert not _appearance_ledger_changed(before, same, "overlays", "H")
        assert _appearance_ledger_changed(before, changed, "overlays", "H")


class TestAppearancePruningBoundary:
    def _percepts(self, *, prune):
        from agents.perception import _composer_standing_percepts

        scene = {
            "rooms": {"hall": {"name": "Hall", "light": "normal"}},
            "positions": {"Reya": "hall", "Tamamo": "hall"},
            "entities": {}, "poses": {}, "contacts": [], "attire": {},
            "overlays": {}, "scales": {}, "contained": {},
        }
        observer = {"room": "hall", "room_name": "Hall",
                    "room_notes": "", "sense_card": None}
        others = [{
            "name": "Tamamo", "room": "hall",
            "appearance": "nine golden tails; wearing a ceremonial kimono",
            "aliases": [], "disguise_known_to": [],
            "disguise_conceals_identity": False,
        }]
        return _composer_standing_percepts(
            scene, observer, "Reya", others, {"Tamamo": "Tamamo"},
            {"Reya": ["Tamamo"]}, prev_seen={"Tamamo"},
            prune_appearance=prune)

    def test_npc_view_keeps_another_bodys_complete_string(self):
        from agents import composer

        percepts = self._percepts(prune=False)
        appearance = next(p for p in percepts if p.kind == "appearance")
        rendered = composer.render_view(
            percepts, mode="character",
            prev_described={appearance.data["source_key"]})

        assert "nine golden tails" in rendered.text
        assert "ceremonial kimono" in rendered.text

    def test_player_pruning_can_drop_the_same_unchanged_string(self):
        percepts = self._percepts(prune=True)

        assert not any(p.kind == "appearance" for p in percepts)


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

    def test_a_natural_paraphrase_is_not_followed_by_a_duplicate_tail(self):
        view = _inject_visible_actor(
            "A beautiful young woman with golden fox ears and six golden "
            "tails stands beside the console in modern casual attire.",
            display="the young woman",
            appearance=("A beautiful young woman with golden fox ears and "
                        "six golden tails; wearing: modern casual attire."),
            relation={"same_room": True},
        )

        assert "You see" not in view
        assert view.casefold().count("six golden tails") == 1

    def test_a_sealed_interior_has_no_visual_to_the_room_outside(self):
        """The live geometry: an interior room with no adjacency to the room
        its owner stands in. Nothing should see through that."""
        from world.spatial import has_visual, spatial_rel

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
        from world.spatial import contacts_of, merge_scene_with_diff

        scene = merge_scene_with_diff({
            "rooms": {"inside": {"name": "Inside"}},
            "positions": {"Hinami": "inside", "Bramwell": "inside"},
            "entities": {}, "contacts": [], "scales": {}, "contained": {},
        }, {"contact_ops": [{"op": "add", "actor": "Bramwell",
                             "target": "Hinami", "manner": "press"}]})

        assert contacts_of(scene, "Hinami")
