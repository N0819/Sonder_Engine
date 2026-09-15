"""Four engine defects from the owner's chat 125 ("Attempt two",
2026-09-14, z-ai/glm-5.2 and 5.3), each firing on every beat.

1. The spatial and objects hands wrote transforms with no `status`, the
   repair omitted it again, and fail-open dropped every station, pose and
   entity they wrote. A transform is a verdict.
2. The establish wrote exits under `room`, every reader asked for `to`,
   and one room of a two-room parlour lost its only way back.
3. The establish copied `{{PLAYER}}` from the example as the player's
   positions key; the commit tracked the token as a background presence
   with an open person need, and the resolve addressed lines to it.
4. The causal ledger filed the player's quoted lines as ACTION rows; no
   dialogue log carried them and the composer's tripwire fired on every
   view.
"""
from agents.director import restore_declared_quotes, substitute_player_token
from llm.schemas import RoomDef, semantic_output_errors


def test_a_transform_is_a_verdict():
    out = {"results": [{"transforms": [{"patch": {"stations": {"M": {"at": None}}}}]}]}
    errors = semantic_output_errors(
        "director_spatial", out,
        source_payload={"ledgers": [{"item_id": 1, "categories": ["stations"]}]})
    assert errors == []
    assert out["results"][0]["status"] == "encoded"
    bad = {"results": [{"status": "done", "transforms": [{"patch": {}}]}]}
    assert semantic_output_errors(
        "director_spatial", bad, source_payload={"ledgers": [{"item_id": 1}]})


def test_an_exit_names_its_far_room_under_to():
    room = RoomDef(name="Reception Parlor",
                   adjacent=[{"room": "treatment_chamber", "barrier": "curtain"},
                             {"to": "hall", "barrier": "open"},
                             {"room_id": "yard"}])
    assert [e["to"] for e in room.adjacent] == ["treatment_chamber", "hall", "yard"]


def test_the_players_slot_is_the_persona():
    out = {"positions": {"{{PLAYER}}": "reception_parlor", "Mirelle": "reception_parlor"},
           "dialogue_log": [{"speaker": "{{player}}", "intended_target": "Mirelle"}],
           "resolved_event": "{{PLAYER}} steps inside.", "n": 3}
    fixed = substitute_player_token(out, "Hinami")
    assert fixed["positions"] == {"Hinami": "reception_parlor", "Mirelle": "reception_parlor"}
    assert fixed["dialogue_log"][0]["speaker"] == "Hinami"
    assert fixed["resolved_event"] == "Hinami steps inside."
    assert out["positions"] != fixed["positions"]       # rebuilt, not mutated


def test_a_quoted_span_in_the_input_is_the_players_line():
    raw = '"Hello is anyone here?" You look around'
    out = {"ledgers": [{
        "chrono_id": 1, "item_id": 1, "object_name": "Hinami",
        "source_entity_id": "persona:10", "authority_mode": "world_author",
        "event": 'calls out "Hello is anyone here?" and looks around the Reception Parlor',
        "act": "", "observable": 'calls out "Hello is anyone here?" and looks around',
        "commitment": "asserted", "targets": [], "visibility": "overt",
        "conceal_from": [], "volume": "normal", "categories": ["rooms"]}]}
    warnings = []
    restore_declared_quotes(out, raw, warn=warnings.append)
    rows = out["ledgers"]
    assert [r["categories"] for r in rows] == [["speech"], ["rooms"]]
    assert rows[0]["event"] == "Hello is anyone here?" and rows[0]["chrono_id"] == 1
    assert rows[0]["item_id"] != rows[1]["item_id"]
    assert "Hello" not in rows[1]["event"] and "looks around" in rows[1]["event"]
    assert warnings and "player speech restored" in warnings[0]


def test_a_line_already_filed_as_speech_is_left_alone_and_a_bare_verb_goes():
    raw = '"I\'m Hinami." You look at her curiously. "It\'s not often I see a succubus."'
    out = {"ledgers": [
        {"chrono_id": 1, "item_id": 1, "event": "I'm Hinami.", "categories": ["speech"], "targets": ["Mirelle"]},
        {"chrono_id": 2, "item_id": 2, "event": "looks at Mirelle somewhat curiously", "categories": ["poses"]},
        {"chrono_id": 3, "item_id": 3, "event": 'says "It\'s not often I see a succubus."', "observable": "says", "categories": ["rooms"], "targets": ["Mirelle"]},
    ]}
    restore_declared_quotes(out, raw)
    rows = out["ledgers"]
    assert [r.get("categories") for r in rows] == [["speech"], ["poses"], ["speech"]]
    assert rows[2]["event"] == "It's not often I see a succubus." and rows[2]["targets"] == ["Mirelle"]
