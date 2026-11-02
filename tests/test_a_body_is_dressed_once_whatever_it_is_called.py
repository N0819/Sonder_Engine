"""A card's starting outfit seeds a body once, under any spelling of it.

THE SPELLING (story_scene_schema audit F4). `seed_initial_attire` asked
`name in ledger` -- an exact key -- while `attire.entry_for`, whose own
docstring calls it "THE ONLY WAY TO READ ONE BODY'S WARDROBE", tolerates the
case-variant keys the ledger routinely holds. A presence the Director dressed
as `mirela`, promoted to a card named `Mirela`, got a SECOND record holding
the card's outfit; every reader then preferred the exact key, and the next
commit's `_heal_attire_identity_keys` folded the two together by UNION -- the
body wearing its live clothes and the card's starting outfit at once, the
overwrite AGENTS.md forbids ("seed once and never reset existing attire from
a card").

THE ABSENT BODY (F16). The seed at scene creation walked `active_cast` only,
and nothing seeds a body later on its way back in: a character attached and
then made dormant before the opening never had their authored outfit, so
every view carried no clothing for them until a beat happened to dress them.
Clothing belongs to the body, not to its presence in the room.
"""

from __future__ import annotations

import json
import time

from story import attire, scene
from story.character_schema import default_character_data


OUTFIT = {"wearing": ["green wool dress", "leather boots"]}


def test_a_case_variant_key_is_the_same_body():
    sc = {"attire": {"mirela": attire.authored_entry(["wet shift"])}}
    before = json.dumps(sc, sort_keys=True)
    assert scene.seed_initial_attire(sc, "Mirela", OUTFIT) is False
    assert json.dumps(sc, sort_keys=True) == before


def test_a_punctuation_variant_key_is_the_same_body():
    sc = {"attire": {"Dr Sarah Moon": attire.authored_entry(["lab coat"])}}
    assert scene.seed_initial_attire(sc, "Dr. Sarah Moon", OUTFIT) is False
    assert list(sc["attire"]) == ["Dr Sarah Moon"]


def test_an_alias_the_caller_knows_is_the_same_body():
    sc = {"attire": {"Mira": attire.authored_entry(["wet shift"])}}
    assert scene.seed_initial_attire(
        sc, "Mirela Vane", OUTFIT, aliases=["Mira"]) is False
    assert list(sc["attire"]) == ["Mira"]


def test_a_body_with_no_record_is_still_seeded():
    sc = {"attire": {"Someone Else": attire.authored_entry(["cloak"])}}
    assert scene.seed_initial_attire(sc, "Mirela", OUTFIT) is True
    assert sc["attire"]["Mirela"]["wearing"]


def _attach(temp_db, cid, name, outfit, status):
    sheet = default_character_data(name)
    sheet["initial_outfit"] = outfit
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,?)",
               (cid, char_id, status))
    return char_id


def test_a_character_absent_when_the_scene_is_made_owns_their_outfit(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("t", "", time.time()))
    _attach(temp_db, cid, "Here Now", {"wearing": ["grey coat"]}, "active")
    _attach(temp_db, cid, "Away Yet", {"wearing": ["red scarf"]}, "dormant")
    sc = scene.get_scene(cid)
    assert attire.entry_for(sc["attire"], "Here Now").get("wearing")
    assert attire.entry_for(sc["attire"], "Away Yet").get("wearing") == [
        "red scarf"]


def test_a_departed_character_is_not_dressed_at_creation(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("t", "", time.time()))
    _attach(temp_db, cid, "Long Gone", {"wearing": ["red scarf"]}, "departed")
    sc = scene.get_scene(cid)
    assert attire.entry_for(sc["attire"], "Long Gone") == {}
