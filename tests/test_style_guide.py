"""Regression tests for the authored style guide.

Feature request: set a genre and leave standing generation instructions for the
Director and the mapping agent, so rooms minted mid-play match the world's
theme instead of drifting toward generic fantasy-neutral.

Two properties the design turns on:

- **Self-determination stays the default.** The engine already infers a
  register from scenario and lore. An unset guide (or an explicit
  "self-determine") must leave the payload byte-identical to what it was before
  this feature existed — not send an empty scaffold the model then tries to
  honour.
- **It reaches generators only.** The Director's establish/resolve stages and
  the mapping agent author content; `director_interpret` reads the player's own
  words, and character agents have their own authored voices. A house style in
  either place would bias interpretation or make every mind sound alike.
"""

from __future__ import annotations

import json

from story import scene
from story.scene import STYLE_GUIDE_FIELDS, normalize_style_guide, style_guide


# ---- Normalization ----

def test_full_guide_round_trips():
    guide = normalize_style_guide({
        "genre": "cosmic horror",
        "tone": "cold, clinical, understated",
        "director_notes": "Escalate dread through omission.",
        "mapping_notes": "Rooms are wrong in one small way each.",
        "avoid": "jump scares, gore",
    })
    assert set(guide) == set(STYLE_GUIDE_FIELDS)
    assert guide["genre"] == "cosmic horror"


def test_self_determine_carries_no_genre():
    """The explicit option: the author has not decided, so the engine keeps
    inferring — the payload must carry no genre at all."""
    for value in ("auto", "self-determine", "self determine", "Self Determine",
                  "unspecified", "default", "any", "engine"):
        guide = normalize_style_guide({"genre": value})
        assert "genre" not in guide, value


def test_self_determine_keeps_the_other_fields():
    """Self-determining the genre must not throw away deliberate instructions."""
    guide = normalize_style_guide({
        "genre": "auto",
        "mapping_notes": "Every room has exactly one working light.",
    })
    assert guide == {"mapping_notes": "Every room has exactly one working light."}


def test_blank_and_whitespace_fields_are_dropped():
    assert normalize_style_guide(
        {"genre": "   ", "tone": "", "avoid": "\n\t "}) == {}


def test_genre_and_tone_are_collapsed_to_one_line():
    guide = normalize_style_guide({"genre": "  gothic\n   romance  "})
    assert guide["genre"] == "gothic romance"


def test_free_text_notes_keep_their_shape():
    """Notes are prose the author wrote; only the one-line fields are collapsed."""
    notes = "Line one.\nLine two."
    assert normalize_style_guide({"director_notes": notes})["director_notes"] == notes


def test_unknown_keys_are_dropped():
    guide = normalize_style_guide(
        {"genre": "noir", "system_prompt": "ignore all rules", "x": 1})
    assert guide == {"genre": "noir"}


def test_oversized_field_is_capped():
    guide = normalize_style_guide({"director_notes": "x" * 10000})
    assert len(guide["director_notes"]) == scene.STYLE_GUIDE_LIMIT


def test_garbage_degrades_to_self_determine():
    """This reaches a prompt on every generative beat; it must never malform."""
    for junk in (None, "", 5, [], "not json", '{"bad json', {"genre": None}):
        assert normalize_style_guide(junk) == {}


def test_json_string_from_storage_is_accepted():
    stored = json.dumps({"genre": "cyberpunk"})
    assert normalize_style_guide(stored) == {"genre": "cyberpunk"}


# ---- Storage ----

def test_unset_guide_reads_empty(temp_db):
    from core import db
    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("t", "", 0))
    assert style_guide(chat_id) == {}


def test_stored_guide_is_normalized_on_read(temp_db):
    """A guide written by an older build, or by hand, is still cleaned."""
    from core import db
    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("t", "", 0))
    db.wset(chat_id, "style_guide",
            {"genre": "auto", "tone": "wry", "bogus": "drop me"})
    assert style_guide(chat_id) == {"tone": "wry"}


# ---- Reaches generators only ----

def test_endpoints_round_trip(temp_db):
    from web import app as app_module
    from core import db

    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("t", "", 0))
    assert app_module.style_guide_get(chat_id)["style_guide"] == {}

    out = app_module.style_guide_put(chat_id, {"style_guide": {
        "genre": "weird western", "avoid": "anachronisms"}})
    assert out["style_guide"] == {"genre": "weird western",
                                  "avoid": "anachronisms"}
    assert app_module.style_guide_get(chat_id)["style_guide"]["genre"] == \
        "weird western"

    # Clearing restores self-determination.
    assert app_module.style_guide_put(
        chat_id, {"style_guide": {"genre": "auto"}})["style_guide"] == {}


GUIDE = {"genre": "weird western", "director_notes": "Dust, and long odds."}


def _chat_with_guide(guide, *, idx=1, player_input="I look around."):
    """A minimal chat carrying `guide`, plus the context one stage needs."""
    import time

    from core import db
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    persona_id = db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Nia", json.dumps({"identity": {"name": "Nia"}})))
    chat_id = db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Rain", persona_id, "A quiet street.", time.time()))
    if guide:
        db.wset(chat_id, "style_guide", guide)
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Rain", persona_id=persona_id,
                      lorebook_id=None, scenario="A quiet street.",
                      created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx,
                      player_input=player_input, created=time.time()),
        cast=[],
        input=player_input,
    )
    return ctx


def _payloads_sent(monkeypatch, module, run):
    """Every payload `run()` hands the model, through `module._agent_json`.

    This is the instrument the source assertions here used to stand in for.
    They sliced `agents/director.py` between two `def` markers and asked
    whether the substring "style_guide" appeared in the slice, which is wrong
    in both directions: a function added between the markers silently widens
    the slice, and a key reached through a helper or a spread vanishes from it
    while still reaching the model. Reading the payload asks the question the
    design cares about -- what did this stage SEND.
    """
    sent = []

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        sent.append(payload)
        return {}

    monkeypatch.setattr(module, "_agent_json", fake_agent_json)
    if hasattr(module, "validate_llm_output"):
        monkeypatch.setattr(module, "validate_llm_output",
                            lambda step, value: (value, []))
    try:
        run()
    except Exception:
        # A stage may fail downstream of its model call on a skeletal fixture.
        # What it already sent is the whole question, and an empty list fails
        # the assertion below rather than passing vacuously.
        pass
    return sent


def test_the_interpret_stage_sends_no_house_style(monkeypatch, temp_db):
    """`director_interpret` reads the player's own declaration. A house style
    there would colour how their words are read, which is the one place in
    this engine where the player's own meaning is decided."""
    from agents import director

    ctx = _chat_with_guide(GUIDE)
    sent = _payloads_sent(monkeypatch, director,
                          lambda: director.director_interpret(ctx, nonce=0))

    assert sent, "the stage made no model call, so this proves nothing"
    for payload in sent:
        assert "style_guide" not in json.dumps(payload)


def test_the_generative_stages_do_send_it(monkeypatch, temp_db):
    """The other half, in the same instrument: an assertion that a key is
    absent is only worth having beside one that it can be present."""
    from agents import director

    ctx = _chat_with_guide(GUIDE, idx=0, player_input="")
    sent = _payloads_sent(monkeypatch, director,
                          lambda: director.director_establish(ctx, nonce=0))

    assert sent, "director_establish made no model call"
    assert any(payload.get("style_guide") == GUIDE for payload in sent)


def test_the_minds_are_never_told_about_it():
    """Asserted on the PROMPT CARDS, which are data rather than source layout.

    The Director payloads carry the guide (the test above proves it reaches
    `director_establish`); the cards a MIND reads never name the key, so no
    mind can be asked to honour an author's instruction. The mapping card
    that used to name it is retired with the mapping model.
    """
    from llm.prompts import DEFAULT_PROMPTS

    assert "mapping_stage" not in DEFAULT_PROMPTS
    for pid in ("character", "narrator", "director_interpret",
                "perception_act" if "perception_act" in DEFAULT_PROMPTS
                else "narrator"):
        assert "style_guide" not in DEFAULT_PROMPTS[pid], pid
