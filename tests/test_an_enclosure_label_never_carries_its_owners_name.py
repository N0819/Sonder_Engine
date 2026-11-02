"""An interior contact's `target_interior` never carries its holder's name
past the identity floor.

Audit world_spatial_structure_light F1 (2026-11-01, LEAK, CONFIRMED at the
renderer): the engine writes the interior ROOM's name into `target_interior`
(`_restation_interior_contact`), and a room minted for a body is named for its
holder -- chat 97 stored "Mirelle's Mouth", 2 of the corpus's 24 interior
contacts name their own holder. `contact_sensation` relabelled the other party
through `label_for` FIRST and then stripped the possessive by the LABEL, so an
occupant who had not learned the name read "You feel the woman's Mirelle's
Mouth enclosing your hand"; `contact_phrase`, handed the record already
relabelled the way `agents.character` builds `standing_contacts`, rendered
"your hand remains within the woman's Mirelle's Mouth". The composed view's
scrub caught the first (garbling it, with a tripwire every beat); the
character payload is not scrubbed.
"""

from world.spatial import contact_phrase, contact_sensation

OWNER = "Mirelle Sulmirath"


def _scene():
    return {
        "rooms": {"maw": {"name": "Mirelle's Mouth", "parent_entity": "mirelle_s",
                          "adjacent": []},
                  "hall": {"name": "Hall", "adjacent": []}},
        "positions": {OWNER: "hall", "Hinami": "maw"},
        "entities": {"mirelle_s": {"name": OWNER, "kind": "person",
                                   "aliases": ["Mira"]}},
        "attire": {OWNER: {}, "Hinami": {}},
        "contacts": [],
    }


def _contact(interior):
    return {"actor": "Hinami", "actor_part": "hand", "target": OWNER,
            "target_part": "tongue", "manner": "press", "relation": "interior",
            "motion": "settled", "target_interior": interior}


def _hide(name):
    return "the woman" if "mirelle" in str(name).casefold() \
        or "mira" == str(name).casefold() else name


def test_the_occupants_sensation_names_no_holder_it_has_not_learned():
    for interior in ("Mirelle's Mouth", "Mirelle Sulmirath's Throat",
                     "Mira's Gullet", "Sulmirath’s Maw"):
        text = contact_sensation(_contact(interior), you="Hinami",
                                 scene=_scene(), label_for=_hide)
        assert text, interior
        low = text.casefold()
        assert "mirelle" not in low and "sulmirath" not in low \
            and "mira's" not in low, text
        assert "the woman's" in text


def test_the_relabelled_standing_contact_phrase_names_no_holder():
    """Exactly the record `agents.character` builds: parties relabelled, the
    interior label as stored."""
    for interior in ("Mirelle's Mouth", "Mirelle Sulmirath's Throat"):
        record = dict(_contact(interior), target="the woman")
        text = contact_phrase(record, you="Hinami")
        low = text.casefold()
        assert "mirelle" not in low and "sulmirath" not in low, text
        assert "within the woman's" in text


def test_a_label_naming_no_one_is_kept_whole():
    text = contact_sensation(_contact("throat"), you="Hinami", scene=_scene(),
                             label_for=_hide)
    assert "the woman's throat" in text
    record = dict(_contact("lower throat"), target="the woman")
    assert "within the woman's lower throat" in contact_phrase(record, you="Hinami")
