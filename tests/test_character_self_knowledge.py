"""A character must know its own established public biography.

character_public_history is fed to the Director and Mapping stages (for
scene-building) and to other characters' perception of this one, but was
never included in the character's own decision payload -- meaning the
character had no way to stay consistent with facts already established
about itself (e.g. how long it has held a role), and could contradict its
own sheet's public_history purely because that information was never in
its own context.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

def test_character_payload_includes_own_public_history(temp_db, monkeypatch):
    import agents.character as character_module

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Dr. Elena Voss")
    sheet["knowledge"]["public_history"] = (
        "Resident psychiatrist at Blackwood Sanatorium for eleven years."
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Dr. Elena Voss", json.dumps(sheet), "{}", time.time(), "char_voss"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )

    temp_db.wset(
        chat_id,
        "scene",
        {
            "location": "Blackwood Sanatorium", "time": "day",
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Dr. Elena Voss": "hall"},
            "entities": {}, "attire": {}, "overlays": {},
        },
    )

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "how long have you worked here?", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="how long have you worked here?",
                      created=time.time()),
        cast=cast,
        input="how long have you worked here?",
    )
    ctx.director_interpret = {
        "flow": {"reactors": [char_id], "tom_triggers": []},
    }

    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)

    character_module.character_step(ctx, char_id, nonce=0)

    assert captured["payload"]["self"]["public_history"] == (
        "Resident psychiatrist at Blackwood Sanatorium for eleven years."
    )


def test_character_payload_never_includes_another_bodys_vitals(temp_db, monkeypatch):
    """Own-body interoception must not become omniscient medical telemetry."""
    import agents.character as character_module

    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Vitals isolation", "", time.time()),
    )
    sheet = default_character_data("Observer")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Observer", json.dumps(sheet), "{}", time.time(), "char_observer"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "Room", "time": "now",
        "rooms": {"room": {"name": "Room", "adjacent": []}},
        "positions": {"Observer": "room", "Hidden Patient": "room"},
        "entities": {}, "attire": {}, "overlays": {},
        "vitals": {
            "Observer": {
                "air": 1.0, "stamina": 0.8,
                "nourishment": 1.0, "injury": 0.1,
            },
            "Hidden Patient": {
                "air": 0.123456, "stamina": 0.234567,
                "nourishment": 0.345678, "injury": 0.987654,
            },
        },
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "Wait.", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Vitals isolation", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="Wait.", created=time.time()),
        cast=cast, input="Wait.",
    )
    ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": []}}
    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, char_id, nonce=0)

    assert captured["payload"]["self"]["body_state"]["injury"] == 0.1
    blob = json.dumps(captured["payload"])
    for forbidden in ("0.123456", "0.234567", "0.345678", "0.987654"):
        assert forbidden not in blob


class TestACharacterKnowsWhatItIsWearing:
    """`self.attire` was reaching the payload and nothing was reading it.

    Reported from chat 57: NPCs behaving as if unaware of their own clothing.
    The data was never missing -- `agents/character.py` has passed a full
    region-by-region view of the character's OWN attire for as long as the
    field has existed, and chat 57's Doctor carried six garments with
    descriptions. The 44,888-character `character` prompt simply never
    mentioned it, so nothing told the character the field was there or that it
    was allowed to act on it.

    That is the failure mode CLAUDE.md warns about from the other direction: a
    field that is populated, valid, and read by nobody fails silently and looks
    like a model problem fifty beats later.
    """

    def test_the_prompt_tells_the_character_the_field_exists(self):
        from prompts import DEFAULT_PROMPTS
        prompt = DEFAULT_PROMPTS["character"]
        assert "self.attire" in prompt

    def test_it_names_the_three_parts_the_payload_actually_carries(self):
        """`attire_view` returns wearing/regions/state. A prompt that only said
        'you have clothes' would leave the structure unusable."""
        from prompts import DEFAULT_PROMPTS
        prompt = DEFAULT_PROMPTS["character"]
        for part in ("wearing", "regions", "state"):
            assert f"`{part}`" in prompt, part

    def test_it_is_framed_as_the_present_not_the_starting_outfit(self):
        """`scene.attire` is the mutable story ledger, not `initial_outfit`.
        A character reading it as 'what I put on this morning' would contradict
        anything the story has since changed."""
        from prompts import DEFAULT_PROMPTS
        assert "LEDGER" in DEFAULT_PROMPTS["character"]

    def test_it_keeps_the_firewall(self):
        """Own clothing is interoception; another body's is perception's to
        deliver or withhold. The prompt must not invite reading someone else's
        off this field."""
        from prompts import DEFAULT_PROMPTS
        prompt = DEFAULT_PROMPTS["character"]
        assert "do not describe another person's clothing" in prompt.lower()

    def test_the_payload_still_carries_it(self):
        """The other half of the pair: if this field is ever renamed or
        dropped, the prompt above becomes a promise about nothing."""
        import inspect

        import agents.character as character
        src = inspect.getsource(character)
        assert '"attire": attire_view(' in src
