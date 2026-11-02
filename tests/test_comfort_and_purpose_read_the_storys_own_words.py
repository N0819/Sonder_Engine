"""Comfort and place purpose read the story's own script: their tokens are
the script-aware words of `language_runtime.fold_words`, and their closed
vocabularies take the story pack's words beside the engine's own.

world_misc_causal F12 (audit 2026-11-01, CONFIRMED): both modules tokenized
with `re.split(r"[^a-z0-9]+", ...)`, which DELETES every letter outside
ASCII. A body lying (`posture: "横になっている"`) on an entity named 布団 scored
`(0.0, "")` and no rest, where its English twin scored `(0.3, "bed")` -- so a
Japanese story had no comfort floor, no passive stamina recovery
(`survival.tick_vitals`), no `here_affords` and no assumed affordances. An
accented Latin word lost its accented letter too ("café" read as "caf").

The Japanese words here stand in for the pack's: the tables themselves are
the language pack's to carry (`linguistics["world.comfort"]`,
`linguistics["world.place_purpose"]`).
"""

import language_runtime
from world import comfort, place_purpose

JA = {
    ("world.comfort", "SOFT_SUPPORT_TOKENS"): ("布団", "ベッド", "ソファ"),
    ("world.comfort", "WARMTH_TOKENS"): ("暖炉", "囲炉裏"),
    ("world.comfort", "LYING_TOKENS"): ("横", "寝"),
    ("world.comfort", "SITTING_TOKENS"): ("座",),
    ("world.place_purpose", "NAME_LEXICON"): {"宿屋": ["food", "drink",
                                                       "rest", "shelter"],
                                              "台所": ["food"]},
}


def _ja_pack(monkeypatch):
    # The merged tables are kept per language; start from none, and leave
    # nothing this fake pack produced behind for another test.
    monkeypatch.setattr(comfort, "_VOCABULARY", {})
    monkeypatch.setattr(place_purpose, "_LEXICONS", {})
    real = language_runtime.linguistic

    def fake(module, name, language_id=None):
        selected = language_runtime.current_language_id.get() \
            if language_id is None else language_id
        if selected == "ja" and (module, name) in JA:
            return JA[(module, name)]
        return real(module, name, language_id)

    monkeypatch.setattr(language_runtime, "linguistic", fake)


def _scene(posture, bed_id, bed_name, bed_desc):
    return {"rooms": {"room": {"name": "Room", "light": "lit"}},
            "positions": {"Ada": "room", bed_id: "room"},
            "entities": {bed_id: {"name": bed_name, "kind": "furniture",
                                  "description": bed_desc}},
            "poses": {"Ada": {"posture": posture}},
            "contacts": [{"actor": "Ada", "target": bed_id, "manner": "rest"}]}


def test_the_japanese_twin_rests_as_the_english_one_does(monkeypatch):
    _ja_pack(monkeypatch)
    english = _scene("lying down", "bed", "bed", "a feather bed")
    assert comfort.comfort_level(english, "Ada") == (0.3, "bed")
    assert comfort.rest_affording(english, "Ada") is True
    japanese = _scene("横になっている", "e1", "布団", "羽毛の掛け布団")
    with language_runtime.language_scope("ja"):
        assert comfort.comfort_level(japanese, "Ada") == (0.3, "布団")
        assert comfort.rest_affording(japanese, "Ada") is True
        assert place_purpose.here_affords(japanese, "Ada") == ["rest (the 布団)"]


def test_a_compound_holding_the_word_is_read_in_an_unspaced_script(monkeypatch):
    _ja_pack(monkeypatch)
    japanese = _scene("寝そべっている", "e1", "羽毛布団", "")
    with language_runtime.language_scope("ja"):
        assert comfort.rest_affording(japanese, "Ada") is True


def test_the_engine_words_still_read_inside_a_japanese_story(monkeypatch):
    """An imported card's English "bed" in a Japanese story is still a bed:
    the pack's words are added to the engine's, never put in their place."""
    _ja_pack(monkeypatch)
    mixed = _scene("lying", "e1", "bed", "")
    with language_runtime.language_scope("ja"):
        assert comfort.rest_affording(mixed, "Ada") is True


def test_a_place_name_in_the_storys_script_carries_its_assumption(monkeypatch):
    _ja_pack(monkeypatch)
    with language_runtime.language_scope("ja"):
        assert set(place_purpose.assumed_affords("港の宿屋")) == {
            "food", "drink", "rest", "shelter"}
        assert set(place_purpose.assumed_affords("港宿屋")) == {
            "food", "drink", "rest", "shelter"}
    assert set(place_purpose.assumed_affords("The Tavern")) == {
        "food", "drink", "shelter"}


def test_a_pack_with_no_table_leaves_the_engine_words_as_they_were():
    with language_runtime.language_scope("ja"):
        assert comfort.rest_affording(
            _scene("lying", "bed", "bed", ""), "Ada") is True


def test_an_accented_latin_letter_is_part_of_its_word():
    assert comfort._field_tokens("Café Divan") == ["café", "divan"]
