"""Authored initial outfits seed mutable story attire without becoming anatomy."""

from __future__ import annotations

import json
import time

from web import app
from story import attire
from story.character_schema import (
    default_character_data,
    default_persona_data,
)
from story.importers import (
    REINT_CHAR_SYS,
    REINT_PERSONA_SYS,
    heuristic_character_sheet,
    import_persona,
)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.scene import get_scene


def test_heuristic_character_import_separates_labeled_outfit():
    sheet = heuristic_character_sheet({
        "name": "Iris",
        "description": (
            "Tall and broad-shouldered, with silver hair.\n"
            "Outfit: a charcoal coat; scuffed leather boots"
        ),
        "personality": "Reserved, observant",
    })

    assert sheet["initial_outfit"]["wearing"] == [
        "a charcoal coat", "scuffed leather boots",
    ]
    appearance = sheet["embodiment"]["visible"]["summary"]
    assert "silver hair" in appearance
    assert "charcoal coat" not in appearance
    assert "boots" not in appearance


def test_heuristic_persona_import_separates_direct_outfit(temp_db):
    _, sheet = import_persona({
        "name": "Nia",
        "description": "Compact, dark-eyed, with a dimple in one cheek.",
        "outfit": ["a linen shirt", "weathered trousers"],
    })

    assert sheet["initial_outfit"]["wearing"] == [
        "a linen shirt", "weathered trousers",
    ]
    assert "linen shirt" not in sheet["embodiment"]["visible"]["summary"]


def test_generators_and_ai_importers_require_body_outfit_separation():
    from llm.prompts import DEFAULT_PROMPTS

    texts = {
        "character generator": DEFAULT_PROMPTS["generator_character"],
        "persona generator": DEFAULT_PROMPTS["generator_persona"],
        "promotion generator": DEFAULT_PROMPTS["promote_character"],
        "character importer": REINT_CHAR_SYS,
        "persona importer": REINT_PERSONA_SYS,
    }
    for label, text in texts.items():
        assert "initial_outfit" in text, label
        assert "BODY" in text or "body" in text, label
        assert "clothing" in text or "garment" in text, label
        assert "appearance summary" in text, label


def test_establishment_outfits_are_authoritative_without_private_card_leaks(
    temp_db, monkeypatch,
):
    import agents.director as director

    persona = default_persona_data("Nia")
    persona["initial_outfit"]["wearing"] = ["a linen shirt"]
    persona["knowledge"]["private_history"] = [
        {"content": "PERSONA_PRIVATE_MARKER"},
    ]
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Nia", json.dumps(persona), "{}", persona["identity"]["uid"]),
    )
    character = default_character_data("Iris")
    character["initial_outfit"] = {
        "wearing": ["a charcoal coat"], "state": ["rain-damp"],
    }
    character["knowledge"]["private_history"] = [
        {"content": "CHARACTER_PRIVATE_MARKER"},
    ]
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            "Iris", json.dumps(character), "{}", time.time(),
            character["identity"]["uid"],
        ),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Rain", persona_id, "", time.time()),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    cast = temp_db.q(
        "SELECT ch.id,ch.name,COALESCE(cc.sheet,ch.sheet) AS sheet,"
        "ch.source,ch.created,ch.resource_uid,cc.state AS cstate,cc.status "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 0, "", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(
            id=chat_id, name="Rain", persona_id=persona_id,
            lorebook_id=None, scenario="", created=time.time(),
        ),
        turn=TurnData(
            id=turn_id, chat_id=chat_id, idx=0, player_input="",
            created=time.time(),
        ),
        cast=cast,
        input="",
    )
    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured.update(payload)
        return {
            "location": "room",
            "positions": {},
            "rooms": {},
            "entities": {},
            "attire": {
                "Nia": {"wearing": ["invented dress"], "state": []},
                "Iris": {"wearing": ["invented uniform"], "state": []},
            },
        }

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    monkeypatch.setattr(
        director, "validate_llm_output", lambda step, value: (value, []),
    )
    result = director.director_establish(ctx, nonce=0)

    # The card's own two fields, unchanged. `regions` rides alongside them and
    # is empty on both these cards, so compare the fields the test is about.
    for authored, sent in (
        (persona, captured["player"]["initial_outfit"]),
        (character, captured["present_characters"][0]["initial_outfit"]),
    ):
        assert sent["wearing"] == authored["initial_outfit"]["wearing"]
        assert sent["state"] == authored["initial_outfit"].get("state", [])
    payload_text = json.dumps(captured)
    assert "PERSONA_PRIVATE_MARKER" not in payload_text
    assert "CHARACTER_PRIVATE_MARKER" not in payload_text
    # The authored outfit wins over the model's invention, and now arrives with
    # its regions -- the opening turn must not be the one beat that drops them.
    for name, authored in (("Nia", persona), ("Iris", character)):
        entry = result["attire"][name]
        assert sorted(entry["wearing"]) == sorted(
            authored["initial_outfit"]["wearing"])
        assert entry["state"] == authored["initial_outfit"].get("state", [])
        assert attire.flat_wearing(entry["regions"]) == entry["wearing"]


def test_new_scene_seeds_character_and_persona_initial_outfits(temp_db):
    persona = default_persona_data("Nia")
    persona["initial_outfit"] = {
        "wearing": ["a linen shirt", "weathered trousers"],
        "state": ["rain-damp"],
    }
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Nia", json.dumps(persona), "{}", persona["identity"]["uid"]),
    )
    character = default_character_data("Iris")
    character["initial_outfit"] = {
        "wearing": ["a charcoal coat", "scuffed boots"],
        "state": [],
    }
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            "Iris", json.dumps(character), "{}", time.time(),
            character["identity"]["uid"],
        ),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Rain", persona_id, "", time.time()),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )

    scene = get_scene(chat_id, dict(temp_db.q(
        "SELECT * FROM chats WHERE id=?", (chat_id,), one=True,
    )))

    # Seeding also sorts the flat list into regions (attire.authored_entry), so
    # the ledger entry is a superset of the card's two fields rather than equal
    # to it. What must not change is the clothes themselves.
    for name, authored in (("Nia", persona), ("Iris", character)):
        entry = scene["attire"][name]
        assert sorted(entry["wearing"]) == sorted(
            authored["initial_outfit"]["wearing"])
        assert entry["state"] == authored["initial_outfit"].get("state", [])


def test_initial_outfit_never_resets_existing_live_attire(temp_db):
    character = default_character_data("Iris")
    character["initial_outfit"]["wearing"] = ["a charcoal coat"]
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            "Iris", json.dumps(character), "{}", time.time(),
            character["identity"]["uid"],
        ),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Wardrobe", "", time.time()),
    )
    live_scene = {
        "location": "room", "time": "now", "description": "",
        "rooms": {}, "entities": {}, "positions": {}, "overlays": {},
        "attire": {
            "Iris": {
                "wearing": ["borrowed coveralls"],
                "state": ["oil-stained"],
            },
        },
    }
    temp_db.wset(chat_id, "scene", live_scene)

    app.chat_add_char(chat_id, {"char_id": char_id})
    assert temp_db.wget(chat_id, "scene")["attire"]["Iris"] == {
        "wearing": ["borrowed coveralls"],
        "state": ["oil-stained"],
    }


def test_first_attachment_to_existing_story_seeds_outfit(temp_db):
    character = default_character_data("Iris")
    character["initial_outfit"]["wearing"] = ["a charcoal coat"]
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (
            "Iris", json.dumps(character), "{}", time.time(),
            character["identity"]["uid"],
        ),
    )
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Wardrobe", "", time.time()),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "room", "time": "now", "description": "",
        "rooms": {}, "entities": {}, "positions": {}, "overlays": {},
        "attire": {},
    })

    app.chat_add_char(chat_id, {"char_id": char_id})

    entry = temp_db.wget(chat_id, "scene")["attire"]["Iris"]
    assert entry["wearing"] == ["a charcoal coat"]
    assert entry["state"] == []
    # A coat is not a torso garment: it goes over the shoulders and past the
    # waist, and is ONE garment across all three (attire.regions_covered).
    # Field by field rather than as a whole dict: a garment grows fields
    # (description, condition, attaches) and pinning the shape here only ever
    # breaks a test that is about seeding.
    coat, = entry["regions"]["torso"]["garments"]
    assert coat["name"] == "a charcoal coat"
    assert coat["state"] == "worn"
    # A coat is not a torso garment: it goes over the shoulders and past the
    # waist, and is ONE garment across all three (attire.regions_covered).
    assert coat["covers"] == ["torso", "arms", "waist"]
    assert attire.covered_regions(entry["regions"]) == ["torso", "arms", "waist"]


def test_card_editors_place_initial_outfit_near_identity():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "static/js/editors.js"
    ).read_text(encoding="utf-8")

    # Clothing is authored by REGION now; the flat "initial outfit" and
    # "clothing condition" inputs are retired (docs/UNBUILT.md §2.14 landed).
    # The legacy `wearing` list survives as an INPUT format -- imports and the
    # generators still emit it, and character_schema migrates it into regions
    # on read -- but nothing types into it any more.
    assert "Initial outfit — clothing only" not in source
    assert "Initial clothing condition" not in source
    assert source.count("fAttireGarments(\n    \"Starting clothes\"") == 2
    assert source.count("Body appearance — stable visible features") == 2
    assert source.count("initial_outfit: { regions:") >= 4


def test_director_establishment_respects_initial_outfit_separation():
    from llm.prompts import DEFAULT_PROMPTS

    text = DEFAULT_PROMPTS["director_establish"]
    assert "initial_outfit is authoritative" in text
    assert "Never infer clothing" in text
