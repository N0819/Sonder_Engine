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
from llm.schemas import RoomDef


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



def test_a_quoted_line_no_row_carries_is_still_the_players_line():
    """The total drop: no row carries the line at all. Chat 167 turn 4631
    (validation story, 2026-10-10): the Director's interpretation stopped
    after the player's first sentence, the ledger held her walk and her look,
    and both quoted lines -- and so everything Ffion was answering -- reached
    no view; Ffion answered the silence. The input is ground truth for what
    the player said: each quoted span becomes her line, word for word, after
    her last row and in the order she wrote them."""
    raw = ('Nell stops at the corner and looks at Ffion. "Thank you. I\'ll not '
           'forget who told me." She nods down the row. "Go home to your boy, '
           'Mrs Rees." She walks on alone and knocks.')
    walk = {"chrono_id": 1, "item_id": 1, "object_name": "Nell Hartley",
            "source_entity_id": "persona:22", "authority_mode": "world_author",
            "source_event_id": "turn:4631:primary:raw",
            "event": "Nell comes down the pithead road to Rhes Isaf.",
            "categories": ["positions"], "targets": ["lower_terrace"], "volume": "normal"}
    look = {"chrono_id": 2, "item_id": 3, "object_name": "persona:22",
            "source_entity_id": "persona:22", "authority_mode": "world_author",
            "source_event_id": "turn:4631:primary:raw",
            "event": "Nell stops at the corner and looks at Ffion Rees.",
            "categories": ["attention"], "targets": ["Ffion Rees"], "volume": "normal"}
    out = {"ledgers": [walk, look]}
    warnings = []
    restore_declared_quotes(out, raw, warn=warnings.append)
    rows = out["ledgers"]
    assert rows[:2] == [walk, look], "what the interpretation carried stays as it was"
    lines = rows[2:]
    assert [r["event"] for r in lines] == [
        "Thank you. I'll not forget who told me.", "Go home to your boy, Mrs Rees."]
    for row in lines:
        assert row["categories"] == ["speech"]
        assert row["source_entity_id"] == "persona:22"
        assert row["authority_mode"] == "world_author"
        assert row["chrono_id"] > look["chrono_id"]
    assert lines[0]["chrono_id"] < lines[1]["chrono_id"]
    assert len({r["item_id"] for r in rows}) == len(rows)
    assert warnings and "Thank you" in warnings[-1]


def test_a_dropped_line_is_restored_in_either_packs_quote_marks():
    """The engine's own closed set of quotation marks, both packs: a line the
    Japanese player wrote in 「」 is a line as surely as one in quotes."""
    look = {"chrono_id": 1, "item_id": 1, "object_name": "persona:22",
            "source_entity_id": "persona:22", "authority_mode": "world_author",
            "event": "ネルは角で立ち止まる。", "categories": ["attention"], "targets": []}
    out = {"ledgers": [look]}
    restore_declared_quotes(out, "ネルは角で立ち止まる。「ありがとう。」")
    assert [r["event"] for r in out["ledgers"][1:]] == ["ありがとう。"]


def test_a_line_carried_in_other_punctuation_or_split_is_not_said_twice():
    """The words decide, not the exact text: a line the interpretation carried
    with its punctuation normalised, or split over two rows, is carried."""
    raw = '"Take me up, Mrs Rees. I\'ll want his house, and then Mr Prothero\'s door."'
    out = {"ledgers": [
        {"chrono_id": 1, "item_id": 1, "source_entity_id": "persona:22",
         "event": "Take me up, Mrs Rees!", "categories": ["speech"], "targets": ["Ffion Rees"]},
        {"chrono_id": 2, "item_id": 2, "source_entity_id": "persona:22",
         "event": "I'll want his house -- and then Mr Prothero's door",
         "categories": ["speech"], "targets": ["Ffion Rees"]}]}
    restore_declared_quotes(out, raw)
    assert len(out["ledgers"]) == 2
