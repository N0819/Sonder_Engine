"""Every path that AUTHORS a card must know about extra body parts.

`embodiment.extra_parts` is read at runtime by the Director, the character
agents, the perception composer and the scene — but until this was wired, the
only thing that could WRITE one was a human using the editor. Generation,
both import paths, the appearance fill and the promotion draft all emitted
sheets with an empty list, so a kitsune arrived with nine tails in prose and
none the engine could see, cover, or let anybody touch.

It is the failure mode CLAUDE.md names for `psychology.drive`: a structured
field that is empty reads as complete, does not error, and shows up fifty
beats later as a character whose body does not behave.
"""

from __future__ import annotations

import json

import pytest

from story import importers
from llm import prompts
from story.character_schema import default_character_data


CARD_PROMPTS = (
    ("generator_character", prompts.DEFAULT_PROMPTS["generator_character"]),
    ("generator_persona", prompts.DEFAULT_PROMPTS["generator_persona"]),
    ("fill_appearance", prompts.DEFAULT_PROMPTS["fill_appearance"]),
    ("promote_character", prompts.DEFAULT_PROMPTS["promote_character"]),
    ("REINT_CHAR_SYS", importers.REINT_CHAR_SYS),
    ("REINT_PERSONA_SYS", importers.REINT_PERSONA_SYS),
)


@pytest.mark.parametrize("name,text", CARD_PROMPTS, ids=[n for n, _ in CARD_PROMPTS])
def test_every_card_authoring_prompt_carries_the_rule(name, text):
    assert "extra_parts" in text, f"{name} cannot author a body part"
    assert "EXTRA BODY PARTS ARE A FIELD" in text


@pytest.mark.parametrize("name,text", CARD_PROMPTS, ids=[n for n, _ in CARD_PROMPTS])
def test_the_menus_are_stated_not_left_to_guesswork(name, text):
    """The vocabularies are closed, so the prompt has to name them.

    A model that invents `at: "lower back"` gets silently relocated by
    `_normalize_extra_parts` to the per-kind guess, which is a recoverable
    authoring default -- but one the author then has to find and fix.
    """
    for menu_value in ("waist", "underside", "through_clothing"):
        assert menu_value in text, f"{name} omits {menu_value}"


def test_one_wording_so_the_six_cannot_drift():
    """Shared fragment, not six copies. Guidance added to one must reach all."""
    for _name, text in CARD_PROMPTS:
        assert prompts.EXTRA_PARTS_NOTE in text


# ---- The appearance fill actually keeps what the model returns ----

def _stub_fill(monkeypatch, proposed):
    monkeypatch.setattr(importers, "chat_complete",
                        lambda *a, **k: json.dumps(proposed))


def _character(temp_db, sheet=None):
    import time
    sheet = sheet or default_character_data("Tamamo")
    return temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Tamamo", json.dumps(sheet), "{}", time.time(), "char_tamamo"))


def test_a_filled_part_survives_the_merge(temp_db, monkeypatch):
    """It used to be dropped: the merge read `visible` and `initial_outfit`."""
    cid = _character(temp_db)
    _stub_fill(monkeypatch, {
        "embodiment": {
            "visible": {"summary": "A slight woman with russet hair."},
            "extra_parts": [{"kind": "tail", "count": 9, "at": "waist",
                             "aspect": "back", "through_clothing": True,
                             "description": "russet, tipped white"}],
        },
        "initial_outfit": {"wearing": [], "state": [], "regions": {}},
    })
    sheet = importers.fill_appearance("character", cid, "a nine-tailed fox")
    parts = sheet["embodiment"]["extra_parts"]
    assert [p["kind"] for p in parts] == ["tail"]
    assert parts[0]["count"] == 9
    assert parts[0]["at"] == "waist" and parts[0]["aspect"] == "back"


def test_silence_is_not_an_amputation(temp_db, monkeypatch):
    """A fill that omits the field must not delete a hand-authored part.

    The fill is allowed to REPLACE body and clothing wholesale -- that is its
    documented contract -- but a model that simply did not mention the list is
    saying nothing, not saying "no tail".
    """
    sheet = default_character_data("Tamamo")
    sheet["embodiment"]["extra_parts"] = [
        {"kind": "tail", "count": 9, "at": "waist", "aspect": "back",
         "through_clothing": True, "description": ""}]
    cid = _character(temp_db, sheet)
    _stub_fill(monkeypatch, {
        "embodiment": {"visible": {"summary": "A slight woman."}},
        "initial_outfit": {"wearing": [], "state": [], "regions": {}},
    })
    filled = importers.fill_appearance("character", cid, "tidy her up")
    assert [p["kind"] for p in filled["embodiment"]["extra_parts"]] == ["tail"]


def test_an_explicit_empty_list_does_clear_them(temp_db, monkeypatch):
    """Saying "none" is different from saying nothing."""
    sheet = default_character_data("Tamamo")
    sheet["embodiment"]["extra_parts"] = [
        {"kind": "tail", "count": 1, "at": "waist", "aspect": "back",
         "through_clothing": True, "description": ""}]
    cid = _character(temp_db, sheet)
    _stub_fill(monkeypatch, {
        "embodiment": {"visible": {"summary": "An ordinary woman."},
                       "extra_parts": []},
        "initial_outfit": {"wearing": [], "state": [], "regions": {}},
    })
    filled = importers.fill_appearance("character", cid, "make her human")
    assert filled["embodiment"]["extra_parts"] == []


def test_a_model_menu_mistake_lands_somewhere_visible(temp_db, monkeypatch):
    """Out-of-vocabulary values fall to the per-kind guess, not to junk."""
    cid = _character(temp_db)
    _stub_fill(monkeypatch, {
        "embodiment": {"visible": {"summary": "Horned."},
                       "extra_parts": [{"kind": "horns", "count": 2,
                                        "at": "forehead", "aspect": "upward"}]},
        "initial_outfit": {"wearing": [], "state": [], "regions": {}},
    })
    part = importers.fill_appearance(
        "character", cid, "give her horns")["embodiment"]["extra_parts"][0]
    assert part["at"] == "head" and part["aspect"] == "top"


# ---- Saying so when a card describes one and declares none ----

def _with_prose(text):
    sheet = default_character_data("Kit")
    sheet["embodiment"]["visible"]["summary"] = text
    sheet["psychology"]["drive"]["essence"] = "keep the shrine"
    sheet["initial_state"]["goals"] = [{"goal": "reach the shrine",
                                        "priority": 0.7}]
    sheet["psychology"]["capacity"] = "ordinary"
    return sheet


def test_a_described_but_undeclared_part_is_reported():
    said = importers.character_import_warnings(
        _with_prose("A slight woman with nine russet tails."))
    assert any("extra_parts" in w for w in said)


def test_a_declared_part_is_not_reported():
    sheet = _with_prose("A slight woman with nine russet tails.")
    sheet["embodiment"]["extra_parts"] = [
        {"kind": "tail", "count": 9, "at": "waist", "aspect": "back",
         "through_clothing": True, "description": ""}]
    assert not any("extra_parts" in w
                   for w in importers.character_import_warnings(sheet))


def test_an_ordinary_body_is_not_reported():
    assert not any("extra_parts" in w for w in
                   importers.character_import_warnings(
                       _with_prose("A tall man with a broken nose.")))


def test_the_check_reads_the_body_not_the_psychology():
    """"Turned tail" is a phrase, not an anatomy.

    A warning that fires on idiom teaches an author to stop reading warnings,
    which costs more than the one it would have caught.
    """
    sheet = _with_prose("An ordinary woman, weathered.")
    sheet["psychology"]["traits"] = [
        {"name": "brave", "strength": 0.8,
         "expression": "never turns tail, takes the bull by the horns",
         "activation_cues": [], "inhibited_by": []}]
    sheet["knowledge"]["public_history"] = "Known for grasping the horns."
    assert not any("extra_parts" in w
                   for w in importers.character_import_warnings(sheet))
