"""Dim light is a rendering fact up close, an admission fact at range.

Design note 18. `dim` used to make an ADMISSION decision — conceal every
region of a body — for what is, at contact range, a RENDERING choice: the
light verdict applied flat, distance could only weaken it, and two bodies
in continuous contact saw each other as silhouettes (chat 70: kneeling
over a body, both hands on it, `vantage: ["seen only in silhouette"]`,
correctly computed surfaces discarded at the gate).

The ladder of kind: dim + a MEASURED closeness -> full admission (Layer B
already renders "The light is dim."); dim at range -> shapes; dark -> sight
fails at every range, because the touch channel already delivers what
closeness in darkness gives. The strengthening evidence is closed —
a standing contact between the pair, or station-measured `within_reach` —
and never `proximity_rel`'s "near", which is the documented
no-station-data fallback and would un-dim every ordinary room.
"""

from __future__ import annotations

import attire
import spatial
from agents.common import _unknown_actor_label, region_visibility


def _dim_room(light="dim"):
    return {
        "rooms": {"r": {"name": "Treatment Room", "light": light,
                        "anchors": ["platform"]}},
        "positions": {"Elyra": "r", "Hinami": "r", "Moth": "r"},
        "contacts": [
            {"actor": "Elyra", "actor_part": "hands", "target": "Hinami",
             "target_part": "stomach", "manner": "resting",
             "relation": "surface", "motion": "settled"},
        ],
        "attire": {"Hinami": attire.authored_entry(
            [], [], {"waist": {"garments": [
                {"name": "utility sash with pouches"}]}})},
    }


class TestTheLadderOfKind:
    def test_dim_at_contact_is_full_admission(self):
        """The incident, recomputed: hands on a body in a dim room see the
        body."""
        sc = _dim_room()
        assert spatial.visual_level_between(sc, "Elyra", "Hinami") == "full"
        # ...and symmetrically: the body being touched sees its toucher.
        assert spatial.visual_level_between(sc, "Hinami", "Elyra") == "full"

    def test_dim_at_range_is_still_a_silhouette(self):
        """The same dim room, a body with no measured closeness: shapes.
        `proximity_rel` answers its "near" DEFAULT for this pair, and the
        default must never masquerade as a measurement."""
        sc = _dim_room()
        assert spatial.visual_level_between(sc, "Elyra", "Moth") == "shapes"
        assert spatial.visual_level_between(sc, "Moth", "Hinami") == "shapes"

    def test_dim_within_measured_reach_is_full(self):
        sc = {
            "rooms": {"r": {"name": "R", "light": "dim",
                            "anchors": ["bed"]}},
            "positions": {"A": "r", "B": "r"},
            "stations": {"A": {"at": "bed"}, "B": {"at": "bed"}},
        }
        assert spatial.visual_level_between(sc, "A", "B") == "full"

    def test_dark_is_never_strengthened(self):
        """Rung three: sight fails, at every range — touch has its own
        channel and already delivers sensation. Closeness must not invent
        sight in darkness."""
        sc = _dim_room(light="dark")
        assert spatial.visual_level_between(sc, "Elyra", "Hinami") == "none"

    def test_cross_room_dim_is_never_strengthened(self):
        """Closeness is a same-room fact; the view-cone and distance caps
        stand across an opening."""
        sc = {
            "rooms": {
                "a": {"name": "A", "light": "lit",
                      "adjacent": [{"to": "b", "barrier": "open"}]},
                "b": {"name": "B", "light": "dim",
                      "adjacent": [{"to": "a", "barrier": "open"}]},
            },
            "positions": {"O": "a", "T": "b"},
        }
        assert spatial.visual_level_between(sc, "O", "T") == "shapes"

    def test_a_carried_light_is_still_light_ats_business(self):
        """The torch prior art is untouched: lit beside the holder without
        any contact or station data, via light on the target."""
        sc = {
            "rooms": {"r": {"name": "R", "light": "dark"}},
            "positions": {"O": "r", "T": "r", "lantern": "r"},
            "entities": {"lantern": {"name": "lantern",
                                     "light_source": "lit"}},
            "stations": {"T": {"near": ["lantern"]},
                         "lantern": {"near": ["T"]}},
        }
        # The target stands in the lantern's pool: fully lit to any observer
        # with a line of sight, however far.
        assert spatial.light_at(sc, "T") == "lit"


class TestRegionVisibilityInheritsIt:
    def test_the_incident_beat_delivers_the_surfaces(self):
        """region_visibility changes nothing itself (attribution only) and
        now inherits the corrected sight answer: garment concealment stands,
        vantage concealment is gone."""
        sc = _dim_room()
        verdicts = region_visibility(sc, "Elyra", "Hinami")
        assert verdicts["torso"]["visibility"] == "overt"
        assert verdicts["waist"] == {
            "visibility": "concealed",
            "by": {"garments": ["utility sash with pouches"]}}

    def test_an_unmeasured_pair_in_the_same_dim_room_stays_silhouetted(self):
        sc = _dim_room()
        verdicts = region_visibility(sc, "Moth", "Hinami")
        assert all(v["visibility"] == "concealed"
                   for v in verdicts.values())
        assert verdicts["torso"]["by"] == {
            "vantage": ["seen only in silhouette"]}


class TestStrangerLabelTruncation:
    def test_a_cap_cut_prepositional_phrase_is_trimmed_to_its_head(self):
        """The live shape: "the towering hooded stranger with smooth" — the
        5-word cap cut a prepositional phrase one word in, which the
        trailing-dangler trim cannot see because "smooth" is a content
        word. A cap-cut label now ends on a whole phrase."""
        label = _unknown_actor_label(
            "Elyra Voss",
            "A towering hooded stranger with smooth lavender skin and "
            "curling horns")
        assert label == "the towering hooded stranger"

    def test_a_complete_phrase_inside_the_cap_survives(self):
        """"the figure in mourning" is whole — nothing was truncated, so
        nothing is second-guessed."""
        assert _unknown_actor_label(
            "X", "A figure in mourning") == "the figure in mourning"


class TestSensationIdentityFloor:
    def test_the_other_party_is_named_through_the_label(self):
        sc = _dim_room()
        contact = sc["contacts"][0]
        clause = spatial.contact_sensation(
            contact, you="Hinami", scene=sc,
            label_for=lambda other: "the stranger")
        assert "the stranger" in clause
        assert "Elyra" not in clause

    def test_without_a_label_the_canonical_name_passes_through(self):
        """Omniscient/self-view callers keep today's behaviour."""
        sc = _dim_room()
        clause = spatial.contact_sensation(
            sc["contacts"][0], you="Hinami", scene=sc)
        assert "Elyra" in clause
