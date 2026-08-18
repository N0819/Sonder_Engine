"""Prompt presets: language tagging, and the portable import/export document.

A preset is a whole-sheet replacement for authored human-language text, so it
carries the language it was written in. The two things these tests hold down
are that a preset never crosses a language boundary, and that a file which
cannot be applied faithfully is refused rather than half-imported.
"""

import json

import pytest

from core.db import get_setting, set_setting
from language_runtime import DEFAULT_LANGUAGE, LanguagePackError
from llm import prompts


JA = "ja"


@pytest.fixture
def saved(temp_db):
    """Store presets in the tagged shape and make one active."""
    def _save(name, language, bodies, active=True):
        stored = json.loads(get_setting("prompt_presets") or "{}")
        stored[name] = {"language": language, "prompts": bodies}
        set_setting("prompt_presets", json.dumps(stored))
        if active:
            set_setting("active_preset", name)
        return name
    return _save


# --- the language tag decides whether a preset applies at all ---------------

def test_a_preset_overrides_its_own_language(saved):
    saved("Grittier", DEFAULT_LANGUAGE, {"narrator": "ENGLISH OVERRIDE"})
    body = prompts.get_prompt_body("narrator", DEFAULT_LANGUAGE)
    assert body == "ENGLISH OVERRIDE"


def test_an_english_preset_does_not_reach_a_japanese_prompt(saved):
    """The defect this tag exists for: an English sheet replacing a Japanese
    one changes which language the model is addressed in, and carries that
    sheet's own English schema policy along with it."""
    saved("Grittier", DEFAULT_LANGUAGE, {"narrator": "ENGLISH OVERRIDE"})
    body = prompts.get_prompt_body("narrator", JA)
    assert body != "ENGLISH OVERRIDE"
    assert body == str(prompts._prompt_card(JA)["prompts"]["narrator"])


def test_a_japanese_preset_does_not_reach_an_english_prompt(saved):
    saved("和風", JA, {"narrator": "日本語の上書き"})
    assert prompts.get_prompt_body("narrator", DEFAULT_LANGUAGE) != "日本語の上書き"
    assert prompts.get_prompt_body("narrator", JA) == "日本語の上書き"


def test_the_specialists_and_prose_author_honour_the_tag(saved):
    """Every preset-aware assembly path, not just get_prompt_body."""
    saved("Grittier", DEFAULT_LANGUAGE, {
        "director_body": "BODY OVERRIDE",
        "director_resolve_lean": "PROSE OVERRIDE",
    })
    assert "BODY OVERRIDE" in prompts.specialist_prompt(
        "body", ("attire",), DEFAULT_LANGUAGE)
    assert "PROSE OVERRIDE" in prompts.prose_author_prompt(None, DEFAULT_LANGUAGE)
    assert "BODY OVERRIDE" not in prompts.specialist_prompt("body", ("attire",), JA)
    assert "PROSE OVERRIDE" not in prompts.prose_author_prompt(None, JA)


def test_default_preset_overrides_nothing(saved):
    saved("Grittier", DEFAULT_LANGUAGE, {"narrator": "ENGLISH OVERRIDE"},
          active=False)
    set_setting("active_preset", "Default")
    assert prompts.get_prompt_body("narrator", DEFAULT_LANGUAGE) != "ENGLISH OVERRIDE"


# --- reading what is already on disk ---------------------------------------

def test_presets_saved_before_languages_are_read_as_english(temp_db):
    """Presets predate story languages; a bare {pid: text} map was authored
    against the English pack and must keep working, not vanish."""
    set_setting("prompt_presets", json.dumps({"Old": {"narrator": "LEGACY"}}))
    set_setting("active_preset", "Old")
    assert prompts.presets()["Old"] == {
        "language": DEFAULT_LANGUAGE, "prompts": {"narrator": "LEGACY"}}
    assert prompts.get_prompt_body("narrator", DEFAULT_LANGUAGE) == "LEGACY"
    assert prompts.get_prompt_body("narrator", JA) != "LEGACY"


def test_an_unreadable_language_tag_does_not_break_the_editor(temp_db):
    """A hand-edited or uninstalled tag stops the preset matching; it must not
    take the whole prompt surface down with it."""
    set_setting("prompt_presets", json.dumps(
        {"Broken": {"language": "!!not a language!!", "prompts": {"narrator": "X"}}}))
    set_setting("active_preset", "Broken")
    assert prompts.presets()["Broken"]["language"] == DEFAULT_LANGUAGE
    assert prompts.get_prompt_body("narrator", JA) != "X"


def test_junk_entries_are_dropped_not_raised(temp_db):
    set_setting("prompt_presets", json.dumps({"Bad": ["not", "a", "map"]}))
    assert prompts.presets() == {}


# --- the portable document -------------------------------------------------

def test_export_round_trips_through_import(saved):
    saved("和風", JA, {"narrator": "日本語の上書き"}, active=False)
    document = prompts.preset_export_document("和風")
    assert document["kind"] == prompts.PRESET_FILE_KIND
    assert document["version"] == prompts.PRESET_FILE_VERSION
    assert document["language"] == JA
    name, preset = prompts.preset_import_document(document)
    assert name == "和風"
    assert preset == {"language": JA, "prompts": {"narrator": "日本語の上書き"}}


def test_export_carries_bodies_verbatim(saved):
    """Bodies travel exactly as authored, schema policy and all -- the tag is
    what keeps them out of the wrong story, not a rewrite of the text."""
    body = prompts.DEFAULT_PROMPTS["narrator"] + "\n\nAnd be grittier."
    saved("Grittier", DEFAULT_LANGUAGE, {"narrator": body}, active=False)
    assert prompts.preset_export_document("Grittier")["prompts"]["narrator"] == body


def test_exporting_an_unknown_preset_raises(temp_db):
    with pytest.raises(KeyError):
        prompts.preset_export_document("nothing here")


@pytest.mark.parametrize("document, fragment", [
    ("not an object", "must contain an object"),
    ({"kind": "character_card", "version": 1, "name": "x",
      "prompts": {"narrator": "y"}}, "not a prompt preset"),
    ({"kind": prompts.PRESET_FILE_KIND, "name": "x",
      "prompts": {"narrator": "y"}}, "no usable version"),
    ({"kind": prompts.PRESET_FILE_KIND, "version": 99, "name": "x",
      "prompts": {"narrator": "y"}}, "newer than this engine"),
    ({"kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "",
      "prompts": {"narrator": "y"}}, "name of its own"),
    ({"kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "Default",
      "prompts": {"narrator": "y"}}, "name of its own"),
    ({"kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "x",
      "prompts": {}}, "carries no prompts"),
    ({"kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "x",
      "prompts": {"no_such_prompt": "y"}}, "does not have"),
    ({"kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "x",
      "prompts": {"narrator": 17}}, "must be text"),
])
def test_a_document_that_cannot_be_applied_faithfully_is_refused(
        temp_db, document, fragment):
    """Fail closed: a preset importing with half its sheets silently dropped
    reappears many beats later as a model behaving oddly."""
    with pytest.raises(ValueError, match=fragment):
        prompts.preset_import_document(document)


def test_an_uninstalled_language_is_refused(temp_db):
    with pytest.raises(LanguagePackError):
        prompts.preset_import_document({
            "kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "x",
            "language": "zz", "prompts": {"narrator": "y"}})


def test_an_untagged_document_imports_as_english(temp_db):
    _name, preset = prompts.preset_import_document({
        "kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "x",
        "prompts": {"narrator": "y"}})
    assert preset["language"] == DEFAULT_LANGUAGE


def test_import_can_be_renamed_by_the_caller(temp_db):
    name, _preset = prompts.preset_import_document({
        "kind": prompts.PRESET_FILE_KIND, "version": 1, "name": "x",
        "prompts": {"narrator": "y"}}, name="mine")
    assert name == "mine"


def test_import_never_overwrites_a_saved_preset():
    existing = {"Grittier", "Grittier (2)"}
    assert prompts.unique_preset_name("Grittier", existing) == "Grittier (3)"
    assert prompts.unique_preset_name("Fresh", existing) == "Fresh"


# --- the routes ------------------------------------------------------------

@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient
    from web import app as app_module
    from web import guest_access as guest

    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        assert c.post("/api/auth/setup",
                      json={"username": "host", "password": "pw12345"}
                      ).status_code == 200
        yield c


def test_save_export_import_round_trip_over_http(client):
    body = prompts.DEFAULT_PROMPTS["narrator"] + "\n\nAnd be grittier."
    r = client.put("/api/prompt_presets", json={
        "name": "Grittier", "language": DEFAULT_LANGUAGE,
        "prompts": {"narrator": body}})
    assert r.status_code == 200, r.text
    assert r.json()["language"] == DEFAULT_LANGUAGE

    document = client.get("/api/prompt_presets/Grittier/export").json()
    assert document["kind"] == prompts.PRESET_FILE_KIND
    assert document["prompts"]["narrator"] == body

    # Importing the same file again must not clobber the original.
    imported = client.post("/api/prompt_presets/import",
                           json={"preset": document}).json()
    assert imported["renamed"] is True
    assert imported["name"] == "Grittier (2)"
    stored = prompts.presets()
    assert stored["Grittier"] == stored["Grittier (2)"]


def test_exporting_an_unknown_preset_is_404(client):
    assert client.get("/api/prompt_presets/nope/export").status_code == 404


def test_importing_a_foreign_file_is_refused(client):
    r = client.post("/api/prompt_presets/import",
                    json={"preset": {"kind": "character_card", "version": 1}})
    assert r.status_code == 400
    assert "not a prompt preset" in r.json()["detail"]
    assert prompts.presets() == {}


def test_saving_an_uninstalled_language_is_refused(client):
    r = client.put("/api/prompt_presets", json={
        "name": "Nope", "language": "zz", "prompts": {"narrator": "x"}})
    assert r.status_code == 400
    assert prompts.presets() == {}


def test_default_prompts_serves_each_story_language(client):
    english = client.get("/api/default_prompts").json()
    assert english["language"] == DEFAULT_LANGUAGE
    assert english["prompts"]["narrator"] == prompts.DEFAULT_PROMPTS["narrator"]

    japanese = client.get(f"/api/default_prompts?language={JA}").json()
    assert japanese["language"] == JA
    assert japanese["prompts"]["narrator"] != english["prompts"]["narrator"]
    assert set(japanese["prompts"]) == set(english["prompts"])

    assert client.get("/api/default_prompts?language=zz").status_code == 400
