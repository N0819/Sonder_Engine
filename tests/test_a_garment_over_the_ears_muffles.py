"""A GARMENT OVER THE EARS MUFFLES (DESIGN_SOUND_FIELD.md § 18, round 2,
lane D, 2026-10-20; the owner's § 13.7 item 7).

Real world: a hood drawn up, a scarf wound over the ears, a helmet, a pair
of earmuffs take some 5-15 dB from what reaches the ear -- less than hands
pressed over them (15-25), and never on top of them: the second covering
lies under the first.

What existed: the attire ledger had a `head` region and no `ears` zone, so
the hearing floor (`spatial_listener.ear_cover_db`) read contacts only, and
a body in a hood followed a whisper at its elbow as if bare-headed -- and a
garment's NAME is prose, so reading "hood" out of it was the word list this
engine refuses.

The class, read from TYPED state only:

  1. `ears` is a zone of the head a garment covers ONLY WHEN IT NAMES IT
     (`attire.OPT_IN_ZONES`): a hat, a ribbon, a mask name nothing and
     cover nothing; a hood written `{"head": ["head", "ears"]}` covers
     both, one written `{"head": ["ears"]}` the ears alone, and one pushed
     back (`{"head": []}`) nothing -- and the head stays OUT of the
     bareness axis (`REGION_ZONES`), because ears are not nakedness;
  2. a worn head garment naming the ears takes `GARMENT_OVER_EARS_DB` (10)
     from everything that reaches the listener; removed, attached or
     pushed back, nothing;
  3. the ledger and the contact ledger are read together as THE LARGER of
     the two, never their sum: hands over a hood are the hands' 20;
  4. the vocabulary is one: the card's authored outfit seeds it, the
     encoder's `coverage` channel writes and clears it, the ledger line
     says it, and the editor offers it unticked.
"""

from __future__ import annotations

from pathlib import Path

from story import attire
from story.character_schema import default_character_data, normalize_character_data
from story.scene import seed_initial_attire
from world.spatial import (EARS_COVERED_DB, GARMENT_OVER_EARS_DB, ear_cover_db,
                           garment_over_ears_db, hear_level, hearing_reason,
                           sound_field, spatial_rel_between)

ROOT = Path(__file__).resolve().parents[1]
VOLUMES = ("whisper", "mutter", "normal", "loud", "shout")
HOOD_UP = {"head": ["head", "ears"]}


def _scene(cells, *, contacts=(), back_room=None, hood=None, wearer="C"):
    rooms = {"shop": {"name": "the workshop", "exposure": "enclosed",
                      "extent": {"w": 10, "d": 8}, "anchors": {},
                      "adjacent": []}}
    positions = {k: "shop" for k in cells}
    stations = {k: {"cell": list(v)} for k, v in cells.items()}
    if back_room:
        rooms["shop"]["adjacent"] = [{"to": "back", "barrier": "open",
                                      "bearing": "e"}]
        rooms["back"] = {"name": "the back room", "exposure": "enclosed",
                         "extent": {"w": 6, "d": 6}, "anchors": {},
                         "adjacent": [{"to": "shop", "barrier": "open",
                                       "bearing": "w"}]}
        for who, cell in back_room.items():
            positions[who] = "back"
            stations[who] = {"cell": list(cell)}
    sc = {"rooms": rooms, "positions": positions, "stations": stations,
          "entities": {}, "poses": {}, "orientation": {}, "contained": {},
          "contacts": list(contacts)}
    if hood is not None:
        garment = {"name": "a hood", "state": "worn", **hood}
        sc["attire"] = {wearer: {"wearing": ["a hood"], "state": [],
                                 "regions": {"head": {"garments": [garment],
                                                      "beneath": ""}}}}
    return sc


def _hands(who="C"):
    return {"actor": who, "actor_part": "hands", "target": who,
            "target_part": "ears", "manner": "press", "relation": "surface",
            "motion": "settled"}


def _heard(sc, listener="C", speaker="A"):
    rel = spatial_rel_between(sc, listener, speaker,
                              sound=sound_field(sc, listener))
    return rel, {v: hear_level(rel, v, addressed=True) for v in VOLUMES}


# --- 1. the zone is named, never guessed ---------------------------------------

def test_the_ears_are_a_zone_a_garment_covers_only_when_it_names_them():
    assert attire.OPT_IN_ZONES == {"head": ("ears",)}
    assert attire.zone_vocabulary("head") == ("head", "ears")
    assert attire.zones_of("head") == ("head",)          # default coverage
    assert "head" not in attire.REGION_ZONES              # ears are not nakedness
    # The validator: the head's own zone alone is the default and stores
    # nothing; a named ears zone is kept, with or without the head; pushed
    # off is kept; a word the vocabulary does not know keeps what was true.
    assert attire._clean_covered_zones({"head": ["head"]}) == {}
    assert attire._clean_covered_zones({"head": ["ears", "head"]}) == HOOD_UP
    assert attire._clean_covered_zones({"head": ["ears"]}) == {"head": ["ears"]}
    assert attire._clean_covered_zones({"head": []}) == {"head": []}
    assert attire._clean_covered_zones({"head": ["hair"]}) == {}
    hood = {"name": "a hood", "state": "worn", "covered_zones": HOOD_UP}
    hat = {"name": "a hat", "state": "worn"}
    assert attire.covered_zones_for(hood, "head") == ("head", "ears")
    assert attire.covered_zones_for(hat, "head") == ("head",)
    assert attire.zones_named(hood, "head") == ("ears",)
    assert attire.zones_named(hat, "head") == ()
    regions = {"head": {"garments": [hood, hat]}}
    assert attire.garments_over_zone(regions, "head", "ears") == ["a hood"]
    assert attire.garments_over_zone(regions, "head", "head") == ["a hood", "a hat"]


def test_a_hood_naming_the_ears_is_a_covering_not_a_displaced_garment():
    """`describe` says the fact on the ledger line, so the encoder -- which
    rewrites coverage from what it is shown -- can keep it; and the
    ears-only shape is a covering too, never "[displaced]"."""
    regs = attire.normalize_regions({"regions": {"head": {"garments": [
        {"name": "a hood", "state": "worn", "covered_zones": HOOD_UP}]}}})
    assert regs["head"]["garments"][0]["covered_zones"] == HOOD_UP
    assert attire.describe(regs) == ["head: a hood [over the ears]"]
    assert attire.region_is_covered(regs, "head")
    muffs = attire.normalize_regions({"regions": {"head": {"garments": [
        {"name": "a pair of earmuffs", "state": "worn",
         "covered_zones": {"head": ["ears"]}}]}}})
    assert attire.describe(muffs) == ["head: a pair of earmuffs [over the ears]"]
    back = attire.normalize_regions({"regions": {"head": {"garments": [
        {"name": "a hood", "state": "worn", "covered_zones": {"head": []}}]}}})
    assert attire.describe(back) == [
        "head: a hood [displaced; not covering this region], bare here"]
    # A newcomer still takes a hood's place at region grain: the ears it
    # names do not make it immune to a hat put on in its stead.
    assert attire.displaced_by(regs, "a hat") == ["a hood"]


def test_the_encoders_coverage_channel_names_and_clears_the_ears():
    """The `coverage` channel (`apply_coverage_changes`): a hood drawn up
    names the ears beside the head and the record keeps it; the head's own
    full list clears the override and un-names them; the ears alone is a
    covering of the ears and nothing of the head proper."""
    regs = attire.normalize_regions({"regions": {"head": {"garments": [
        {"name": "a hood", "state": "worn"}]}}})
    regs, notes = attire.apply_coverage_changes(
        regs, {"hood": {"head": ["head", "ears"]}})
    assert regs["head"]["garments"][0].get("covered_zones") == HOOD_UP, notes
    assert not notes
    regs, notes = attire.apply_coverage_changes(regs, {"hood": {"head": ["head"]}})
    assert "covered_zones" not in regs["head"]["garments"][0], notes
    regs, notes = attire.apply_coverage_changes(regs, {"hood": {"head": ["ears"]}})
    assert regs["head"]["garments"][0].get("covered_zones") == {"head": ["ears"]}
    assert attire.covered_zones_for(regs["head"]["garments"][0], "head") == ("ears",)


# --- 2. and 3. what it takes, and how it combines ------------------------------

def test_a_worn_hood_naming_the_ears_takes_ten_decibels_and_nothing_else_does():
    cells = {"A": (1, 1), "C": (2, 1)}
    assert garment_over_ears_db(_scene(cells, hood={"covered_zones": HOOD_UP}), "C") \
        == GARMENT_OVER_EARS_DB == 10.0
    assert ear_cover_db(_scene(cells, hood={"covered_zones": HOOD_UP}), "C") \
        == GARMENT_OVER_EARS_DB
    assert ear_cover_db(_scene(cells, hood={"covered_zones": {"head": ["ears"]}}),
                        "C") == GARMENT_OVER_EARS_DB
    for shape in ({},                                           # a hat
                  {"covered_zones": {"head": []}},              # pushed back
                  {"covered_zones": HOOD_UP, "state": "removed"},
                  {"covered_zones": HOOD_UP, "attaches": True}):
        assert ear_cover_db(_scene(cells, hood=shape), "C") == 0.0, shape
    # Somebody else's hood covers nothing of C's.
    assert ear_cover_db(_scene(cells, hood={"covered_zones": HOOD_UP},
                               wearer="A"), "C") == 0.0
    # Case-variant ledger keys are read (`attire.entry_for`).
    sc = _scene(cells, hood={"covered_zones": HOOD_UP}, wearer="c")
    assert ear_cover_db(sc, "C") == GARMENT_OVER_EARS_DB


def test_hands_over_a_hood_are_the_hands_twenty_never_thirty():
    cells = {"A": (1, 1), "C": (2, 1)}
    both = _scene(cells, hood={"covered_zones": HOOD_UP}, contacts=[_hands()])
    assert ear_cover_db(both, "C") == EARS_COVERED_DB == 20.0
    assert ear_cover_db(_scene(cells, contacts=[_hands()]), "C") == EARS_COVERED_DB


def test_a_whisper_at_the_elbow_is_lost_through_a_hood_and_a_mutter_is_not():
    """Measured through the hearing rule's own budgets: at arm's reach an
    open ear follows a whisper whole; through a hood (10 dB) the whisper
    is gone and a mutter still arrives, where hands (20 dB) take the mutter
    too; through an open doorway a normal voice still arrives whole under
    a hood where hands leave a fragment."""
    near = {"A": (1, 1), "C": (2, 1)}
    _rel, open_ear = _heard(_scene(near))
    rel, hooded = _heard(_scene(near, hood={"covered_zones": HOOD_UP}))
    _rel, hands = _heard(_scene(near, contacts=[_hands()]))
    assert open_ear["whisper"] == "full"
    assert hooded["whisper"] == "none" and hooded["mutter"] == "full"
    assert hands["whisper"] == "none" and hands["mutter"] == "none"
    assert hearing_reason(rel, "whisper", addressed=True) == "ears_covered"
    _rel, door_open = _heard(_scene({"A": (1, 1)}, back_room={"C": (3, 3)}))
    _rel, door_hood = _heard(_scene({"A": (1, 1)}, back_room={"C": (3, 3)},
                                    hood={"covered_zones": HOOD_UP}))
    _rel, door_hands = _heard(_scene({"A": (1, 1)}, back_room={"C": (3, 3)},
                                     contacts=[_hands()]))
    assert door_open["normal"] == door_hood["normal"] == "full"
    assert door_hands["normal"] == "fragment"


# --- 4. one vocabulary, every surface -------------------------------------------

def test_the_cards_authored_outfit_seeds_the_ears_into_the_ledger():
    card = default_character_data("Ivo")
    card["initial_outfit"] = {"regions": {"head": {"garments": [
        {"name": "a lined hood", "state": "worn", "covered_zones": HOOD_UP}]}}}
    sheet = normalize_character_data(card)
    garment = sheet["initial_outfit"]["regions"]["head"]["garments"][0]
    assert garment["covered_zones"] == HOOD_UP
    scene = {"rooms": {}, "positions": {}}
    assert seed_initial_attire(scene, "Ivo", sheet["initial_outfit"])
    seeded = scene["attire"]["Ivo"]["regions"]["head"]["garments"][0]
    assert seeded["covered_zones"] == HOOD_UP
    assert attire.garments_over_zone(scene["attire"]["Ivo"]["regions"],
                                     "head", "ears") == ["a lined hood"]


def test_the_editor_offers_the_ears_unticked_and_the_prompts_state_the_zone():
    components = (ROOT / "static/js/components.js").read_text(encoding="utf-8")
    assert 'const ATTIRE_OPT_IN_ZONES_FALLBACK = { head: ["ears"] }' in components
    assert "S.boot.attire_opt_in_zones" in components
    # The picker's default is the region's OWN zones; an opt-in zone is
    # ticked only by a record that names it.
    assert "explicit ? (coveredZones[region] || []) : zonesFor(region)" in components
    for language in ("en", "ja"):
        base = ROOT / "language_packs" / language / "cards" / "system_prompts"
        encoder = (base / "encoder" / "attire.txt").read_text(encoding="utf-8")
        fill = (base / "prompts" / "fill_appearance.txt").read_text(encoding="utf-8")
        assert "coverage:{'hood':{head:['head','ears']}}" in encoder, language
        assert "{head:['ears']}" in encoder and "['head']" in encoder, language
        assert "covered_zones:{head:['head','ears']}" in fill, language
