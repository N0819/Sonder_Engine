"""Three identity/naming leaks found auditing "Elevator Adventure branch 41".

1. ATTIRE keyed two ways. A character answers to several scene keys
   (display name, identity.uid, aliases -- character_scene_keys) and the
   Director uses whichever it reaches for. Positions survived that because
   readers try every key and duplicates get collapsed; attire got neither,
   and every reader looks under the display NAME. Dr. Moon ended up with
   `char_f0ef86a7...` holding her lab coat, shirt, trousers and loafers and
   `Dr. Moon` holding `wearing: []` -- so she rendered wearing nothing while
   her clothing state still read "lab coat ripped at the hem".

2. ROOM NAMES overwritten by their own id. The staged-lore materializers
   name a room `room_id.replace("_"," ").title()` as a placeholder, and
   re-ran for rooms that already existed -- so mapping's "Branching
   Junction" became "Site17 Deep Shelter Branching Junction", the id slug,
   as the player-visible location label.

3. OBJECT VOCABULARY handed to perception. Entity aliases and dict keys are
   lookup handles for code, not perceivable facts. Dr. Moon's own view came
   back naming "The TARDIS" -- in the same sentence where the man himself
   was correctly anonymized as "the lean energetic man".
"""

from __future__ import annotations

import json

from agents.common import _perceptible_entities
from persist.commit import _heal_attire_identity_keys
from world.spatial import is_derived_room_name, merge_scene_with_diff


# --- 1. attire ------------------------------------------------------------

_MOON = {"identity": {"uid": "char_f0ef86a7c2dd44f99160fa746e263263",
                      "name": "Dr. Moon", "aliases": ["Sarah Moon"]}}


def _cast():
    return [{"sheet": json.dumps(_MOON)}]


def test_attire_records_collapse_onto_the_display_name():
    scene = {"attire": {
        "char_f0ef86a7c2dd44f99160fa746e263263": {
            "wearing": ["white Foundation lab coat", "dark trousers"],
            "state": ["smudged with light soot"]},
        "Dr. Moon": {"wearing": [],
                     "state": ["lab coat ripped at the hem"]},
    }}
    _heal_attire_identity_keys(scene, _cast())

    assert set(scene["attire"]) == {"Dr. Moon"}
    moon = scene["attire"]["Dr. Moon"]
    # The clothes are back where every reader actually looks...
    assert moon["wearing"] == ["white Foundation lab coat", "dark trousers"]
    # ...and neither record's state was lost in the merge.
    assert set(moon["state"]) == {"lab coat ripped at the hem",
                                  "smudged with light soot"}


def test_the_folded_record_keeps_its_per_garment_facts():
    """`regions` is the authoring surface, and the fold has to carry it.

    A garment's `state`, `condition`, `covered_zones` and hand-placed region
    live only there -- `wearing` is a list of names. Merging the two flat
    lists and dropping the folded record's regions leaves the ledger
    self-consistent (`rederive_entry` rebuilds regions from the merged
    `wearing` through the cue tables) and amnesiac: a loosened, wine-stained,
    hand-placed kimono comes back pristine and torso-anchored.
    """
    scene = {"attire": {
        "char_f0ef86a7c2dd44f99160fa746e263263": {
            "wearing": ["silk kimono", "obi sash"],
            "state": [],
            "regions": {
                "legs": {"garments": [{
                    "name": "silk kimono", "state": "loosened",
                    "condition": "wine-stained", "attaches": False,
                    "description": "deep indigo"}],
                    "beneath": "bare skin"},
                "waist": {"garments": [{
                    "name": "obi sash", "state": "worn", "attaches": True}],
                    "beneath": ""},
            }},
        "Dr. Moon": {"wearing": [], "state": []},
    }}
    _heal_attire_identity_keys(scene, _cast())

    regions = scene["attire"]["Dr. Moon"].get("regions") or {}
    kimono = [g for entry in regions.values()
              for g in (entry.get("garments") or [])
              if g.get("name") == "silk kimono"]
    assert kimono, "the folded record's regions were dropped"
    assert kimono[0]["state"] == "loosened"
    assert kimono[0]["condition"] == "wine-stained"
    # The region it was actually placed on, not the one the cue table guesses.
    assert "legs" in regions
    assert regions["legs"]["beneath"] == "bare skin"


def test_a_surviving_garment_fact_is_not_overwritten_by_the_folded_one():
    """The fold heals a save; it does not decide between two statements.

    `wearing` merges target-first for the same reason: whichever record holds
    the clothes keeps them, and a fact the canonical record already states is
    not somebody else's to replace.
    """
    scene = {"attire": {
        "Sarah Moon": {
            "wearing": ["lab coat"], "state": [],
            "regions": {"torso": {"garments": [{
                "name": "lab coat", "state": "worn",
                "condition": "scorched"}], "beneath": "shirt"}}},
        "Dr. Moon": {
            "wearing": ["lab coat"], "state": [],
            "regions": {"torso": {"garments": [{
                "name": "lab coat", "state": "removed",
                "condition": ""}], "beneath": ""}}},
    }}
    _heal_attire_identity_keys(scene, _cast())

    torso = scene["attire"]["Dr. Moon"]["regions"]["torso"]
    coat = torso["garments"][0]
    assert len(torso["garments"]) == 1
    assert coat["state"] == "removed"
    # ...and a field the survivor leaves blank is still worth recovering.
    assert coat["condition"] == "scorched"
    assert torso["beneath"] == "shirt"


def test_incoming_attire_keys_are_canonicalized():
    canonical = _heal_attire_identity_keys({"attire": {}}, _cast())
    assert canonical("char_f0ef86a7c2dd44f99160fa746e263263") == "Dr. Moon"
    assert canonical("Sarah Moon") == "Dr. Moon"
    assert canonical("Dr. Moon") == "Dr. Moon"


def test_a_non_cast_wearer_is_left_alone():
    """The player persona is not in ctx.cast; it must pass through."""
    scene = {"attire": {"Hinami": {"wearing": ["elegant traveling robes"],
                                   "state": []}}}
    canonical = _heal_attire_identity_keys(scene, _cast())
    assert canonical("Hinami") == "Hinami"
    assert scene["attire"]["Hinami"]["wearing"] == ["elegant traveling robes"]


# --- 2. room names --------------------------------------------------------

def test_an_id_slug_never_overwrites_an_authored_room_name():
    scene = {"rooms": {"site17_deep_shelter_branching_junction": {
        "name": "Branching Junction", "desc": "A wider junction.",
        "adjacent": []}}}
    diff = {"rooms": {"site17_deep_shelter_branching_junction": {
        "name": "Site17 Deep Shelter Branching Junction",
        "desc": "Re-staged from layout lore.", "adjacent": []}}}
    room = merge_scene_with_diff(scene, diff)["rooms"][
        "site17_deep_shelter_branching_junction"]
    assert room["name"] == "Branching Junction"
    # Only the NAME is protected -- the rest of the redeclaration lands.
    assert room["desc"] == "Re-staged from layout lore."


def test_a_real_rename_still_wins():
    scene = {"rooms": {"site17_deep_shelter_branching_junction": {
        "name": "Branching Junction", "adjacent": []}}}
    diff = {"rooms": {"site17_deep_shelter_branching_junction": {
        "name": "The Crossroads"}}}
    assert merge_scene_with_diff(scene, diff)["rooms"][
        "site17_deep_shelter_branching_junction"]["name"] == "The Crossroads"


def test_derived_room_name_detection():
    assert is_derived_room_name("site17_deep_shelter_branching_junction",
                                "Site17 Deep Shelter Branching Junction")
    assert not is_derived_room_name("site17_deep_shelter_branching_junction",
                                    "Branching Junction")


# --- 3. perception vocabulary --------------------------------------------

def test_perception_never_sees_entity_aliases_or_ids():
    scene = {"entities": {"tardis_001": {
        "name": "Blue Police Box", "kind": "vehicle",
        "description": "A battered blue police box.",
        "aliases": ["tardis", "box", "police box"], "state": {}}}}
    projected = _perceptible_entities(scene)

    assert "tardis" not in json.dumps(projected).casefold()
    # What an observer CAN take in survives, keyed by what they'd call it.
    assert projected["Blue Police Box"]["description"] == \
        "A battered blue police box."
    assert "aliases" not in projected["Blue Police Box"]


def test_entities_sharing_a_name_keep_their_ids():
    """Two lamps must not collapse into one payload entry."""
    scene = {"entities": {
        "lamp_a": {"name": "Lamp", "kind": "object"},
        "lamp_b": {"name": "Lamp", "kind": "object"},
        "solo": {"name": "Anvil", "kind": "object"}}}
    projected = _perceptible_entities(scene)
    assert set(projected) == {"lamp_a", "lamp_b", "Anvil"}


def test_a_nameless_entity_keeps_its_id():
    scene = {"entities": {"41b518dc08c3436f": {"name": "", "kind": "object"}}}
    assert set(_perceptible_entities(scene)) == {"41b518dc08c3436f"}


# ---------------------------------------------------------------------------
# 4. ENTITY RECORDS keyed two ways -- the same leak as (1), on the dict that
#    says what each body is doing and what it is in contact with.
#
#    Found auditing a live chat: one character held TWO entity records --
#    `char_9f13c0a4...`, frozen at the beat it was created, and her display
#    name, rewritten every beat since. Both claimed to describe her, so "who is
#    in contact with whom" had two contradictory answers at once, one of them
#    arbitrarily old, and every reader that walks entities saw one person twice.
#
#    Unlike attire, `state` must NOT merge: a wardrobe accumulates, but posture
#    and contact describe a single instant, so folding a stale snapshot into a
#    fresh one is what manufactures the contradiction.
# ---------------------------------------------------------------------------

def _split_scene():
    """One character under both her uid and her display name."""
    return {"entities": {
        "char_9f13c0a4": {
            "name": "Bramwell", "kind": "object",
            "state": {"posture": "leaning_in", "target": "Hinami",
                      "proximity": "close_on_bed"}},
        "Bramwell": {
            "name": "Bramwell", "kind": "object",
            "state": {"posture": "arms_around", "target": "Hinami",
                      "proximity": "pressed_fully_against"}},
    }, "positions": {"Bramwell": "bedroom", "Hinami": "bedroom"}}


def test_one_body_ends_up_with_one_entity_record():
    merged = merge_scene_with_diff(_split_scene(), {})
    assert set(merged["entities"]) == {"Bramwell"}


def test_the_display_name_is_the_surviving_key():
    """The convention every reader uses, matching the positions dedup."""
    merged = merge_scene_with_diff(_split_scene(), {})
    assert "char_9f13c0a4" not in merged["entities"]
    assert merged["entities"]["Bramwell"]["name"] == "Bramwell"


def test_the_stale_snapshot_does_not_survive_the_collapse():
    """The whole point: contact state describes one instant. Merging the two
    records field-by-field would keep the frozen record's posture alive."""
    merged = merge_scene_with_diff(_split_scene(), {})
    state = merged["entities"]["Bramwell"]["state"]

    assert state["posture"] == "arms_around"
    assert "leaning_in" not in json.dumps(merged["entities"])


def test_the_beat_that_just_wrote_wins():
    """When the diff writes the id-keyed record, its content is the fresh one
    -- but it still lands under the display name."""
    scene = _split_scene()
    diff = {"entities": {"char_9f13c0a4": {
        "name": "Bramwell", "kind": "object",
        "state": {"posture": "stepping_back", "proximity": "arm's_length"}}}}

    merged = merge_scene_with_diff(scene, diff)

    assert set(merged["entities"]) == {"Bramwell"}
    assert merged["entities"]["Bramwell"]["state"]["posture"] == "stepping_back"


def test_structural_facts_are_rescued_from_the_discarded_record():
    """Collapsing must never drop a vehicle's interior rooms or an entity's
    aliases -- those are durable facts, not a snapshot of now."""
    scene = {"entities": {
        "tardis_uid": {"name": "The TARDIS", "kind": "vehicle",
                       "interior_rooms": ["console_room"],
                       "aliases": ["box"], "state": {"phase": "docked"}},
        "The TARDIS": {"name": "The TARDIS", "kind": "vehicle",
                       "state": {"phase": "in_transit"}},
    }}

    entity = merge_scene_with_diff(scene, {})["entities"]["The TARDIS"]

    assert entity["interior_rooms"] == ["console_room"]
    assert entity["aliases"] == ["box"]
    assert entity["state"]["phase"] == "in_transit"   # still the fresh snapshot


def test_a_lone_id_keyed_entity_is_untouched():
    """An object with no display-name twin is not a duplicate."""
    scene = {"entities": {
        "dropped_knife": {"name": "Knife", "kind": "object", "state": {}}}}
    assert set(merge_scene_with_diff(scene, {})["entities"]) == {"dropped_knife"}


def test_two_different_entities_sharing_no_name_are_untouched():
    scene = {"entities": {
        "lamp_a": {"name": "Lamp", "kind": "object"},
        "anvil": {"name": "Anvil", "kind": "object"}}}
    assert set(merge_scene_with_diff(scene, {})["entities"]) == {"lamp_a", "anvil"}


def test_an_entity_already_keyed_by_its_name_is_untouched():
    scene = {"entities": {"Lamp": {"name": "Lamp", "kind": "object"}}}
    assert set(merge_scene_with_diff(scene, {})["entities"]) == {"Lamp"}


def test_a_nameless_record_is_not_collapsed():
    scene = {"entities": {
        "41b518dc": {"name": "", "kind": "object", "state": {"x": 1}}}}
    assert set(merge_scene_with_diff(scene, {})["entities"]) == {"41b518dc"}


def test_positions_stay_consistent_with_the_collapsed_entity():
    merged = merge_scene_with_diff(_split_scene(), {})
    assert merged["positions"]["Bramwell"] == "bedroom"
    assert set(merged["entities"]) <= set(merged["positions"]) | {"Hinami"}


def test_perception_sees_the_person_once():
    """The reader-facing consequence: one body, projected once."""
    merged = merge_scene_with_diff(_split_scene(), {})
    projected = _perceptible_entities(merged)
    assert [k for k in projected if "Bramwell" in k] == ["Bramwell"]
