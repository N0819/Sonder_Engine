"""A VOICE CARRIES A TYPED AFFECT (DESIGN_SOUND_FIELD.md § 15, lane A,
2026-10-20).

Wave A's § 12.2 carried a voice's feeling through a wall as ONE WORD of a
line's free-text `tone`, under a deterministic guard over free prose
(`composer._carried_tone`) -- the class of guard this repo retires where it
can. The channel is now a closed set the engine owns: `vocal_affect` on the
encoder's spoken event and on the dialogue entry, the emotion families a
listener decodes from a voice's sound alone (Scherer 1986; Banse & Scherer
1996; Juslin & Laukka 2003: anger, fear, sadness, joy, tenderness, and
neutral). The voice rung reads it first and falls back to the tone floor
ONLY for a record carrying none, so every line recorded before the field
renders exactly as it did.

The class, a test (or more) each:

  1. the set and the normaliser: a member, its grammatical forms and the
     literature's labels land on the member; anything else is "" -- no
     affect, never a guess;
  2. the record: the encoder's event keeps it through validation, the row
     and the projected speech element carry it, the dialogue entry takes it
     from the span that transcribed the line (a declaration never carries
     one), and a filled affect stands;
  3. the voice rung reads it first: the percept carries the typed affect and
     not the free-text tone; both packs say it; a memory keeps it; a fragment
     carries it too;
  4. the fallback: a record with no affect renders as before, through the
     tone floor; `neutral` is an affect -- the free text behind it is not
     read -- and a pack may leave it unsaid;
  5. the card states the field as a class and prints the schema's set.
"""

from __future__ import annotations

from agents import composer
from agents.composer import render_view
from agents.director import (_addressees_from_speech_spans,
                             normalize_causal_ledger)
from agents.director_prose import ledger_from_events
from llm.schemas import (VOCAL_AFFECTS, DialogueLogEntry, normalize_vocal_affect,
                         validate_llm_output)

WALL = {"same_room": False, "barrier": "wall", "distance": "near"}
IRON_DOOR = {"same_room": False, "barrier": "closed_door", "material": "iron",
             "distance": "near"}

LINE = {"speaker": "Mara", "exact_quote": "Where is the ledger, Ivo?",
        "intended_target": "Ivo", "tone": "furious, pacing the floorboards"}


def _percept(rel, volume="loud", **line):
    entry = dict(LINE, volume=volume, **line)
    return composer.speech_percept(
        entry, rel, "Eve", display="Mara", can_see=False, bearing="beyond the wall",
        prev_standing=frozenset())


# --- 1. the set and the normaliser -------------------------------------------

def test_the_set_is_what_a_voice_carries_without_its_words():
    assert VOCAL_AFFECTS == ("anger", "fear", "sadness", "joy", "tenderness",
                             "neutral")
    for member in VOCAL_AFFECTS:
        assert normalize_vocal_affect(member) == member
        assert normalize_vocal_affect(member.upper()) == member
    # the family's own forms and the literature's labels
    assert normalize_vocal_affect("Angry") == "anger"
    assert normalize_vocal_affect("hot anger") == "anger"
    assert normalize_vocal_affect("afraid") == "fear"
    assert normalize_vocal_affect("panic fear") == "fear"
    assert normalize_vocal_affect("sad") == "sadness"
    assert normalize_vocal_affect("amusement") == "joy"
    assert normalize_vocal_affect("tender") == "tenderness"
    assert normalize_vocal_affect("calm") == "neutral"
    # anything else is no affect, never a guess
    for value in ("", None, "furious, pacing the floorboards", "Ivo",
                  "a 3 am rasp", "mocking Ivo", "warm and lightly teasing"):
        assert normalize_vocal_affect(value) == ""


# --- 2. the record ------------------------------------------------------------

def _event(**extra):
    return {"source_entity_id": "character:11", "source_event_id": "scene:1",
            "event": "Where is the ledger, Ivo?", "observable": "",
            "speech": True, "targets": ["Ivo"], "volume": "loud",
            "seconds": 2, "movement": None, "commitment": "asserted",
            "item_names": ["Mara"], "transforms": [], **extra}


def test_the_encoders_event_keeps_the_affect_through_validation():
    out, _warnings = validate_llm_output(
        "director_specialist",
        {"events": [_event(vocal_affect="Angry"), _event(vocal_affect="pacing")],
         "missing_tools": [], "missing_referents": [], "notes": []})
    assert out["events"][0]["vocal_affect"] == "anger"
    assert out["events"][1]["vocal_affect"] == ""


def test_the_row_and_the_projected_line_carry_it():
    rows, _transforms = ledger_from_events([_event(vocal_affect="anger")])
    assert rows[0]["vocal_affect"] == "anger"
    out = normalize_causal_ledger(
        {"ledgers": rows}, identity_index={"character:11": "Mara"})
    assert out["ledgers"][0]["vocal_affect"] == "anger"
    spoken = [e for e in out["sequence"] if e.get("type") == "speech"]
    assert spoken and spoken[0]["vocal_affect"] == "anger"
    assert spoken[0]["intended_target"] == "Ivo"
    # a row written with none projects none -- and never a guess
    rows, _ = ledger_from_events([_event()])
    out = normalize_causal_ledger({"ledgers": rows},
                                  identity_index={"character:11": "Mara"})
    assert out["ledgers"][0]["vocal_affect"] == ""


def test_the_players_own_element_keeps_the_affect_through_norm_sequence():
    """At interpret `common.norm_sequence` runs AFTER the encoder's rows were
    projected and rebuilds each spoken element from a fixed key list; the
    dialogue log's copy of the player's line is minted from what survives.
    A declaration without the field builds "" -- never a guess."""
    from agents.common import norm_sequence
    out = {"sequence": [
        {"type": "speech", "text": "Where is the ledger, Ivo?", "volume": "loud",
         "targets": ["Ivo"], "vocal_affect": "Angry"},
        {"type": "speech", "text": "Sit.", "volume": "normal", "tone": "flat"}]}
    norm_sequence(out)
    spoken = [e for e in out["sequence"] if e.get("type") == "speech"]
    assert [e["vocal_affect"] for e in spoken] == ["anger", ""]
    assert spoken[0]["targets"] == ["Ivo"]


def test_the_dialogue_entry_takes_the_affect_from_the_span_that_transcribed_it():
    """A character's own line is re-appended from the declaration, which has
    no affect; the encoder's span of the same words is the only record that
    does. A filled affect, and a filled target, stand."""
    scene = {"entities": {}}
    dlog = [{"speaker": "Mara", "exact_quote": '"Where is the ledger, Ivo?"',
             "intended_target": None, "tone": "furious"},
            {"speaker": "Mara", "exact_quote": '"Sit down."',
             "intended_target": "Ivo", "vocal_affect": "tenderness"},
            {"speaker": "Mara", "exact_quote": '"Now."',
             "intended_target": "Ivo"}]
    spans = [{"type": "speech", "actor": "character:11",
              "text": "Where is the ledger, Ivo?", "targets": ["Ivo"],
              "vocal_affect": "anger"},
             {"type": "speech", "actor": "character:11", "text": "Sit down.",
              "targets": ["Ivo"], "vocal_affect": "anger"},
             {"type": "speech", "actor": "character:11", "text": "Now.",
              "targets": ["Ivo"]}]
    _addressees_from_speech_spans(dlog, spans, scene, {11: "Mara"}, "Eve")
    assert dlog[0]["intended_target"] == "Ivo"
    assert dlog[0]["vocal_affect"] == "anger"
    assert dlog[1]["vocal_affect"] == "tenderness"
    assert "vocal_affect" not in dlog[2]
    assert DialogueLogEntry(speaker="Mara", exact_quote="Now.",
                            vocal_affect="Sad").vocal_affect == "sadness"
    assert DialogueLogEntry(speaker="Mara", exact_quote="Now.").vocal_affect == ""


# --- 3. the voice rung reads it first -------------------------------------------

def test_the_voice_rung_reads_the_typed_affect_and_not_the_free_text():
    p = _percept(WALL, vocal_affect="anger")
    assert p.fidelity == "voice"
    assert p.data["vocal_affect"] == "anger"
    assert "tone_heard" not in p.data
    text = render_view([p], mode="player", language="en").text
    assert text == ("Mara's voice, raised, beyond the wall — the words do "
                    "not carry. It sounds angry.")
    for word in ("ledger", "Ivo", "furious", "pacing"):
        assert word not in text


def test_both_packs_say_it_and_a_memory_keeps_it():
    p = _percept(IRON_DOOR, volume="normal", vocal_affect="sadness")
    ja = render_view([p], mode="player", language="ja").text
    assert "悲しげ" in ja and "sadness" not in ja and "sad" not in ja
    episode = composer.render_episode([p], language="en")
    remembered = getattr(episode, "text", episode)
    remembered = remembered[0] if isinstance(remembered, tuple) else remembered
    assert "It sounded sad." in remembered and "ledger" not in remembered


def test_a_fragment_carries_the_affect_too():
    from world.spatial import hear_level
    rel = {"same_room": False, "barrier": "wall", "distance": "near"}
    p = _percept(rel, volume="shout", vocal_affect="fear")
    assert hear_level(rel, "shout") == "fragment" and p.fidelity == "fragment"
    assert p.data["vocal_affect"] == "fear"
    text = render_view([p], mode="player", language="en").text
    assert "It sounds frightened." in text


# --- 4. the fallback ---------------------------------------------------------------

def test_a_record_with_no_affect_renders_through_the_tone_floor_as_before():
    p = _percept(WALL)
    assert "vocal_affect" not in p.data
    assert p.data["tone_heard"] == "furious"
    text = render_view([p], mode="player", language="en").text
    assert text.endswith("It sounds furious.")
    # an unknown value is no affect
    p = _percept(WALL, vocal_affect="pacing the floorboards")
    assert p.data["tone_heard"] == "furious"


def test_neutral_is_an_affect_the_free_text_cannot_speak_behind():
    p = _percept(WALL, vocal_affect="neutral")
    assert p.data["vocal_affect"] == "neutral"
    assert "tone_heard" not in p.data
    text = render_view([p], mode="player", language="en").text
    assert text == "Mara's voice, raised, beyond the wall — the words do not carry."
    assert "furious" not in text
    ja = render_view([p], mode="player", language="ja").text
    assert "声の調子" not in ja


# --- 5. the card ---------------------------------------------------------------------

def test_the_card_states_the_field_as_a_class_and_prints_the_schemas_set():
    from language_runtime import raw_card
    from llm.prompts import unified_specialist_prompt
    sheet = unified_specialist_prompt([], "en", [])
    bullet = next(line for line in sheet.splitlines()
                  if line.startswith("- vocal_affect"))
    assert "(" + "|".join(VOCAL_AFFECTS) + ")" in bullet
    assert "the feeling a listener would hear in the voice without its words" in bullet
    assert "never what the words mean" in bullet
    ja = raw_card("ja")["encoder"]["core"]
    assert "- vocal_affect (" + "|".join(VOCAL_AFFECTS) + ")" in ja
