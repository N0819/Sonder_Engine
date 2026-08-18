"""Place purpose: what a character may know about what places are FOR.

Built to docs/design/DESIGN_PLACE_PURPOSE.md. The firewall shape under test: the
`assumed` basis is DERIVED from the character's own place-graph node names
and never stored (so the doc's breach condition -- the lexicon consulted
for an unperceived name -- is structurally impossible); `witnessed` comes
only from own vitals and own posture, never the event row; `told` is a
read-model of a mind-model belief and must die with it; and recall at need
routes only over walked doorways, the same taken-edge firewall en_route
uses.

Database-independent: pure derivation, writer, and payload-shape contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from world.place_purpose import (RECALL_AT, affords_here, assumed_affords,
                           felt_needs, here_affords, mirror_told_affords,
                           place_options, witness_affords)


def _scene(rooms=None, entities=None, positions=None, vitals=None,
           contacts=None, stations=None):
    sc = {
        "rooms": rooms or {}, "entities": entities or {},
        "positions": positions or {}, "attire": {},
        "contacts": contacts or [], "stations": stations or {},
    }
    if vitals is not None:
        sc["vitals"] = vitals
    return sc


def _graph(nodes):
    return {"nodes": nodes, "edges": {}}


class TestAssumedLexicon:
    """The sharp edge: cultural competence without oracle knowledge."""

    def test_a_tavern_name_yields_purposes_not_contents(self):
        got = assumed_affords("The Gilded Boar Tavern")
        assert set(got) == {"food", "drink", "shelter"}
        for entry in got.values():
            assert entry["basis"] == "assumed"
            assert set(entry) == {"basis", "note"}, (
                "purpose keys only -- never rooms, doors, counts or "
                "contents; structure is where competence becomes oracle")

    def test_exact_tokens_never_prefixes(self):
        """comfort.py's fur/furnace rule: 'inner sanctum' contains i-n-n
        and must not read as lodging."""
        assert assumed_affords("Inner Sanctum") == {}
        assert assumed_affords("Wellington Hall") == {}

    def test_an_unevocative_name_yields_nothing(self):
        assert assumed_affords("Chamber 0603") == {}
        assert assumed_affords("") == {}

    def test_the_note_names_its_own_ground(self):
        got = assumed_affords("The Old Well")
        assert got["water"]["note"] == "the name says 'well'"


class TestHereAffords:
    """Live perception echo: current room, visible things only."""

    def _tavern(self, light="lit"):
        return _scene(
            rooms={"r1": {"name": "Taproom", "light": light,
                          "anchors": {"hearth": {"desc": "a stone hearth"}},
                          "adjacent": []}},
            entities={"bed1": {"name": "Oak Bed", "kind": "furniture",
                               "description": "a broad oak bed"}},
            positions={"Orrin": "r1", "bed1": "r1"},
        )

    def test_anchors_and_entities_echo(self):
        got = here_affords(self._tavern(), "Orrin")
        assert "rest (the Oak Bed)" in got
        assert "warmth (a stone hearth)" in got

    def test_darkness_echoes_nothing(self):
        """A dark room's bed is not visible; echoing it would out-see the
        view prose it claims to echo."""
        assert here_affords(self._tavern(light="dark"), "Orrin") == []

    def test_the_room_name_contributes_nothing(self):
        """Expecting food of a taproom is memory's business (assumed on
        the graph node), not perception's -- the room's own name must not
        smuggle an expectation into the here-and-now."""
        sc = _scene(rooms={"r1": {"name": "Taproom", "light": "lit",
                                  "adjacent": []}},
                    positions={"Orrin": "r1"})
        assert here_affords(sc, "Orrin") == []

    def test_a_body_is_never_furniture(self):
        """A character in a fur cloak carries a soft token and must not
        read as somewhere to rest -- comfort.py's body rule, held here."""
        sc = _scene(
            rooms={"r1": {"name": "Cell", "light": "lit", "adjacent": []}},
            entities={"karen": {"name": "Karen", "kind": "character",
                                "description": "wrapped in a fur blanket"}},
            positions={"Orrin": "r1", "Karen": "r1"},
        )
        sc["attire"] = {"Karen": {"worn": ["fur cloak"]}}
        assert here_affords(sc, "Orrin") == []

    def test_an_entity_elsewhere_is_not_here(self):
        sc = self._tavern()
        sc["positions"]["bed1"] = "r2"
        got = here_affords(sc, "Orrin")
        assert not any(a.startswith("rest") for a in got)


class TestWitnessedWriter:
    """Own vitals, own posture, own room -- and nothing else."""

    def _state(self, name="Taproom"):
        return {"place_graph": _graph(
            {"r1": {"basis": "walked", "name": name}})}

    def _fed_scene(self, nourishment):
        return _scene(
            rooms={"r1": {"name": "Taproom", "light": "lit",
                          "adjacent": []}},
            positions={"Orrin": "r1"},
            vitals={"Orrin": {"air": 1.0, "stamina": 0.6,
                              "nourishment": nourishment, "injury": 0.0}},
        )

    def test_a_nourishment_rise_witnesses_food_here(self):
        st = self._state()
        witness_affords(st, self._fed_scene(0.4), "Orrin", 70)
        witness_affords(st, self._fed_scene(0.9), "Orrin", 71)
        got = st["place_graph"]["nodes"]["r1"]["affords"]["food"]
        assert got == {"basis": "witnessed", "last": 71}

    def test_a_rise_across_a_move_credits_no_room(self):
        """They ate SOMEWHERE during the gap; crediting where they now
        stand would witness the wrong place."""
        st = self._state()
        witness_affords(st, self._fed_scene(0.4), "Orrin", 70)
        moved = self._fed_scene(0.9)
        moved["rooms"]["r2"] = {"name": "Yard", "light": "lit",
                                "adjacent": []}
        moved["positions"]["Orrin"] = "r2"
        st["place_graph"]["nodes"]["r2"] = {"basis": "walked", "name": "Yard"}
        witness_affords(st, moved, "Orrin", 71)
        for node in st["place_graph"]["nodes"].values():
            assert "affords" not in node

    def test_a_gap_in_turns_credits_nothing(self):
        st = self._state()
        witness_affords(st, self._fed_scene(0.4), "Orrin", 70)
        witness_affords(st, self._fed_scene(0.9), "Orrin", 75)
        assert "affords" not in st["place_graph"]["nodes"]["r1"]

    def test_survival_off_yields_no_vitals_signal(self):
        st = self._state()
        sc = self._fed_scene(0.4)
        sc.pop("vitals")
        witness_affords(st, sc, "Orrin", 70)
        witness_affords(st, sc, "Orrin", 71)
        assert "affords" not in st["place_graph"]["nodes"]["r1"]
        assert "last_vitals" not in st

    def test_lying_on_a_soft_support_witnesses_rest(self):
        """The seam comfort.py left open, taken deliberately: the
        witnessed-basis fact its docstring names. Works with survival off
        -- rest evidence is postural, not metabolic."""
        st = self._state(name="Bunkroom")
        sc = _scene(
            rooms={"r1": {"name": "Bunkroom", "light": "lit",
                          "adjacent": []}},
            entities={"bunk": {"name": "Bunk", "kind": "furniture",
                               "description": "a narrow bunk"}},
            positions={"Orrin": "r1", "bunk": "r1"},
            contacts=[{"actor": "Orrin", "target": "Bunk",
                       "manner": "lie"}],
        )
        sc["entities"]["orrin_body"] = {"name": "Orrin",
                                        "state": {"posture": "lying"}}
        witness_affords(st, sc, "Orrin", 70)
        got = st["place_graph"]["nodes"]["r1"]["affords"]["rest"]
        assert got == {"basis": "witnessed", "last": 70}


class TestToldMirror:
    """A read-model of a belief, alive exactly as long as the belief."""

    def _state(self, confidence=0.7):
        return {
            "place_graph": _graph(
                {"r9": {"basis": "seen", "name": "Gilded Boar"}}),
            "mind_models": {"Gilded Boar": {"hypotheses": [
                {"claim": "The Gilded Boar serves hot stew all day",
                 "kind": "stated_fact", "confidence": confidence,
                 "last_turn": 80},
            ]}},
        }

    def test_a_stated_fact_mirror_lands_with_its_credence(self):
        st = self._state()
        mirror_told_affords(st, 80)
        got = st["place_graph"]["nodes"]["r9"]["affords"]["food"]
        assert got["basis"] == "told"
        assert got["about"] == "Gilded Boar"
        assert 0.0 < got["sureness"] <= 1.0

    def test_an_explained_away_belief_stops_steering(self):
        """The doc's mandatory drift rule: the node entry must not outlive
        the belief it mirrors."""
        st = self._state()
        mirror_told_affords(st, 80)
        st["mind_models"] = {}
        mirror_told_affords(st, 81)
        assert "food" not in st["place_graph"]["nodes"]["r9"]["affords"]

    def test_hearsay_never_overwrites_living_it(self):
        st = self._state()
        st["place_graph"]["nodes"]["r9"]["affords"] = {
            "food": {"basis": "witnessed", "last": 60}}
        mirror_told_affords(st, 80)
        got = st["place_graph"]["nodes"]["r9"]["affords"]["food"]
        assert got["basis"] == "witnessed"

    def test_hearsay_about_a_nodeless_place_stays_a_belief(self):
        """No rid, no node, no walkable route -- the belief lives on in
        mind_models and simply cannot route, which is the same rule
        _destination_from_goals already enforces."""
        st = self._state()
        st["place_graph"] = _graph({})
        assert mirror_told_affords(st, 80) == []

    def test_a_claim_with_no_affordance_noun_writes_nothing(self):
        st = self._state()
        st["mind_models"]["Gilded Boar"]["hypotheses"][0]["claim"] = \
            "The Gilded Boar has a back door onto the alley"
        mirror_told_affords(st, 80)
        assert "affords" not in st["place_graph"]["nodes"]["r9"]


class TestRecallAtNeed:
    """From feeling to option: deterministic, walked-ground, capped."""

    def test_felt_needs_fire_at_the_pressing_tier(self):
        assert felt_needs({"nourishment": RECALL_AT, "stamina": 1.0}) == \
            ["food"]
        assert felt_needs({"nourishment": 0.9, "stamina": 0.2}) == ["rest"]
        assert felt_needs({"nourishment": 0.1, "stamina": 0.3}) == \
            ["food", "rest"], "worst first"

    def test_a_fed_rested_body_asks_for_nothing(self):
        assert felt_needs({"nourishment": 0.9, "stamina": 0.9}) == []
        assert felt_needs({}) == []
        assert felt_needs(None) == []

    def _graph_with_boar(self):
        g = _graph({
            "r0": {"basis": "walked", "name": "Square"},
            "r1": {"basis": "walked", "name": "Gilded Boar",
                   "affords": {"food": {"basis": "witnessed", "last": 70}}},
            "r2": {"basis": "walked", "name": "Old Tavern"},
        })
        return g

    def _adj(self):
        return {"r0": {"r1", "r2"}, "r1": {"r0"}, "r2": {"r0"}}

    def test_witnessed_outranks_assumed_whatever_the_distance(self):
        opts = place_options(self._graph_with_boar(), "r0", "food",
                             self._adj())
        assert [o["name"] for o in opts] == ["Gilded Boar", "Old Tavern"]
        assert opts[0]["basis"] == "witnessed"
        assert opts[1]["basis"] == "assumed"

    def test_no_walked_route_is_no_option(self):
        """The en_route firewall: a place with no remembered way to it is
        a memory, not an option."""
        opts = place_options(self._graph_with_boar(), "r0", "food",
                             {"r0": {"r2"}, "r2": {"r0"}})
        assert [o["name"] for o in opts] == ["Old Tavern"]

    def test_the_standing_room_is_never_an_option(self):
        opts = place_options(self._graph_with_boar(), "r1", "food",
                             self._adj())
        assert all(o["rid"] != "r1" for o in opts)

    def test_affords_here_reads_ledger_and_name(self):
        g = self._graph_with_boar()
        assert "food" in affords_here(g, "r1"), "the witnessed ledger"
        assert "food" in affords_here(g, "r2"), "the name-derived prior"
        assert affords_here(g, "r0") == set()

    def test_junk_is_tolerated(self):
        assert place_options(None, "r0", "food", {}) == []
        assert place_options(_graph({}), None, "food", {}) == []
        assert affords_here(None, None) == set()
