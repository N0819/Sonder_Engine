"""A character must keep its durable baseline voice and not drift terse.

Observed in a 56-turn session (chat 12, "The Doctor"): the character's mean
spoken-line length collapsed from ~233 chars (turns 1-38) to ~53 chars
(turns 39-55) -- a step-change at turn 39-40 (a legitimately somber Time-War
beat) that then NEVER recovered even when the scene lightened again. The
model's reasoning stayed strong; it simply kept choosing terse lines.

Root cause: the character's baseline voice (sheet.social.voice, verbosity
"high") was already in the decision payload every turn, but the "character"
prompt never referenced it, while two channels buried it -- the prompt's
"smallest plausible behavior" / "go silent" pressures against a 4-turn window
of recently-terse memories, and the autobiographical summary editorializing
the character's MANNER ("quiet precision", "sincere simplicity") and feeding
that self-characterization back every turn.

These tests pin the deterministic plumbing of the fix (prompt-only, levers A
and B): the voice anchor and a voice-honoring instruction co-occur in the
assembled character context even when the memory channels are poisoned, the
instruction is symmetric for low-verbosity characters, and the memory
consolidator is instructed never to describe speaking manner. The actual
recovery of line fullness is a model-behavior improvement validated by a
live reroll, not asserted here.
"""

import json
import time

import memory
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _make_verbose_doctor_chat(temp_db, verbosity):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Voice test", "", time.time()),
    )

    sheet = default_character_data("Verbose Vic")
    sheet.setdefault("social", {})["voice"] = {
        "register": "expressive",
        "cadence": "rapid, excitable, prone to sudden rises",
        "verbosity": verbosity,
        "markers": ["Brilliant!", "Allons-y!"],
        "notes": "",
    }
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Verbose Vic", json.dumps(sheet), "{}", time.time(), "char_vic"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(
        chat_id,
        "scene",
        {
            "location": "Shrine", "time": "evening",
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Verbose Vic": "hall"},
            "entities": {}, "attire": {}, "overlays": {},
        },
    )
    return chat_id, char_id


def _poison_memory_with_terse_manner(temp_db, chat_id, char_id, current_turn_idx):
    """Saturate both memory channels with terse 'quiet' self-characterization,
    reproducing the state that locked the Doctor into terseness."""
    memory.save_memory_summary(
        chat_id, char_id,
        "Vic answered with quiet precision and sincere simplicity, saying "
        "little and keeping every reply clipped and spare.",
        start_turn_idx=max(0, current_turn_idx - 6), end_turn_idx=current_turn_idx - 1,
        key_phrases=["Many. Not all.", "I am fine", "Lead the way"],
        unresolved_threads=["What is she guarding?"],
    )
    for i in range(1, 5):
        memory.add_memory(
            chat_id, char_id, None, "episodic", "witnessed", 0.5,
            "Vic said little, keeping his reply clipped and quiet.",
            turn_idx=current_turn_idx - i, frame_id=None,
        )


def _run_character_step(temp_db, monkeypatch, chat_id, char_id, current_turn_idx):
    import agents.character as character_module

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, current_turn_idx, "Lovely evening, isn't it?", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Voice test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=current_turn_idx,
                      player_input="Lovely evening, isn't it?", created=time.time()),
        cast=cast,
        input="Lovely evening, isn't it?",
    )
    ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": []}}

    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["system"] = system
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, char_id, nonce=0)
    return captured


def test_voice_anchor_and_instruction_survive_poisoned_memory(temp_db, monkeypatch):
    """The reproduction: even with the summary + recent episodes saturated
    with terse 'quiet' self-characterization, the assembled context carries
    the high-verbosity voice anchor AND the voice-honoring instruction."""
    chat_id, char_id = _make_verbose_doctor_chat(temp_db, "high")
    _poison_memory_with_terse_manner(temp_db, chat_id, char_id, current_turn_idx=10)

    cap = _run_character_step(temp_db, monkeypatch, chat_id, char_id, current_turn_idx=10)

    # Baseline voice anchor is present in the payload.
    voice = cap["payload"]["self"]["voice"]
    assert voice["verbosity"] == "high"
    assert "Brilliant!" in voice["markers"]

    # The poison co-occurs -- this is the lock-in state we are counterweighting.
    assert "quiet precision" in cap["payload"]["memory"]["autobiographical_summary"]

    # The prompt now instructs the model to honor that anchor and return to
    # baseline rather than let recent terse lines redefine its voice.
    system = cap["system"]
    assert "VOICE AND REGISTER" in system
    assert "never redefines your voice" in system
    assert "NOT" in system and "word count" in system


def test_low_verbosity_symmetry_guard(temp_db, monkeypatch):
    """The fix must not inflate laconic characters: the instruction must
    explicitly protect low/terse baselines."""
    chat_id, char_id = _make_verbose_doctor_chat(temp_db, "low")
    cap = _run_character_step(temp_db, monkeypatch, chat_id, char_id, current_turn_idx=3)

    assert cap["payload"]["self"]["voice"]["verbosity"] == "low"
    assert "must not be inflated" in cap["system"]


def test_consolidator_is_forbidden_from_describing_manner(temp_db, monkeypatch):
    """Lever B: the memory consolidator prompt must forbid characterizing
    speaking manner and must tell it to drop such phrasing carried in a
    prior summary -- the channel that crystallized the terseness."""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Consolidate test", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Vic", json.dumps(default_character_data("Vic")), "{}", time.time()),
    )
    memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.5,
                      "Learned the shrine was built 800 years ago.", turn_idx=1, frame_id=None)
    memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.5,
                      "Was offered tea and accepted.", turn_idx=2, frame_id=None)

    captured = {}

    def fake_chat_complete(role, system, user, **kwargs):
        captured["system"] = system
        return json.dumps({"summary": "stub", "key_phrases": [], "unresolved_threads": []})

    monkeypatch.setattr(memory, "chat_complete", fake_chat_complete)
    memory.consolidate_character_memory(chat_id, char_id, through_turn_idx=10)

    assert "speaking manner" in captured["system"]
    assert "drop them" in captured["system"]
