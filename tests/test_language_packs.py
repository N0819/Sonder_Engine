"""Language packs are real runtime inputs, with English as the parity pack."""

from __future__ import annotations

import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from web import app
import language_runtime
from agents.composer import Percept, RenderedView, render_episode, render_view
from agents.common import (
    _compose_residue_view, _inject_dialogue,
    _is_autonomous_response, _is_mental_action,
)
from persist.checkpoints import PRESERVED_SETTING_KEYS, ensure_checkpoint, restore_checkpoint
from language_runtime import (
    LanguagePackError, apply_common_prompt_policy, current_language_id,
    installed_language_packs, language_pack, linguistic,
    require_language_pack, story_language,
)
from llm.prompts import DEFAULT_PROMPTS, character_prompt, get_prompt


ROOT = Path(__file__).resolve().parents[1]


def _chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _speech():
    return Percept(
        kind="speech", channel="hearing", source_label="Reya",
        fidelity="full",
        data={"body": "Mind the rail.", "level": "full",
              "volume": "normal", "can_see": True},
        salience=0.8, order_key=0, dedupe_key="speech:rail",
    )


def test_english_is_an_installed_complete_default_pack():
    packs = installed_language_packs(refresh=True)
    assert "en" in packs
    assert packs["en"].story is True
    assert packs["en"].ui is True
    assert packs["en"].adapter == "english"
    assert packs["en"].translation_status == "native"
    assert packs["en"].card("compositor")["ordinal_words"]["2"] == "second"
    # 41, not 43: `move_repeat_screen` was retired with the quality re-ask it
    # existed to gate, and `gap_medium` with the gap generator's second rung
    # (superseded by `offscreen.profile_summary_record`, which does the same
    # bounded call out of band and in state fields rather than prose). A floor
    # rather than an equality, so a prompt going MISSING still fails here
    # while a deliberate retirement is one edit.
    assert len(packs["en"].card("system_prompts")["prompts"]) >= 41
    # Perception composes every view deterministically and has no model role,
    # so it must carry no prompt: one in the pack is 28k characters shipped to
    # nobody, surfaced in the host's prompt editor as if it were editable, and
    # paid for again in every translation.
    assert "perception" not in packs["en"].card("system_prompts")["prompts"]
    # The Director monolith is gone; only the scoped prose-author sheet remains.
    assert "director_resolve" not in packs["en"].card("system_prompts")["prompts"]
    assert "director_resolve_lean" in packs["en"].card("system_prompts")["prompts"]
    assert "agents.common" in packs["en"].card("linguistics")
    assert len(packs["en"].ui_catalog) > 1000


def test_japanese_is_a_complete_selectable_story_and_ui_pack():
    packs = installed_language_packs(refresh=True)
    japanese = packs["ja"]
    assert japanese.native_name == "日本語"
    assert japanese.story is True
    assert japanese.ui is True
    assert japanese.adapter == "japanese"
    assert japanese.translation_status == "model-draft"
    assert require_language_pack("ja", capability="story") is japanese
    assert set(japanese.card("system_prompts")["prompts"]) == set(DEFAULT_PROMPTS)
    assert set(japanese.ui_catalog) == set(packs["en"].ui_catalog)
    exceptions = json.loads((ROOT / "language_packs/ja/translation_exceptions.json")
                            .read_text(encoding="utf-8"))
    unchanged = {
        key for key, value in packs["en"].ui_catalog.items()
        if japanese.ui_catalog[key] == value
    }
    assert unchanged == set(exceptions)


def test_japanese_prompt_requires_japanese_values_and_english_schema(temp_db):
    temp_db.set_setting("active_preset", "Default")
    prompt = get_prompt("narrator", language="ja")
    assert "自然な日本語" in prompt
    assert "JSONキー" in prompt
    # "常に英語のまま", not the old "正規の英語" -- 正規 invites a reading as
    # "regular expression" or "the official version".
    assert "常に英語のまま" in prompt
    # The register and typography the surrounding deterministic prose uses.
    assert "常体" in prompt
    assert "全角" in prompt
    assert "body-region" not in prompt.rsplit("言語およびスキーマ契約", 1)[-1]
    raw = language_pack("ja").card("system_prompts")["prompts"]["narrator"]
    assert raw != language_pack("en").card("system_prompts")["prompts"]["narrator"]
    assert any("ぁ" <= char <= "龯" for char in raw)


def test_japanese_prompt_translation_preserves_protocol_literals():
    prompts = language_pack("ja").card("system_prompts")["prompts"]
    generator = prompts["generator_character"]
    assert '{"kind":"tail","count":1,"at":"waist","aspect":"back"' in generator
    assert "embodiment.extra_parts" in generator
    assert "through_clothing" in generator


def test_japanese_character_prompt_uses_localized_gating_anchors(temp_db):
    temp_db.set_setting("active_preset", "Default")
    marker = language_pack("ja").card(
        "system_prompts")["character_block_keys"][0][0]
    assert marker not in character_prompt({}, language="ja")
    assert marker in character_prompt(
        {"decision": {"player_said_nothing": True}}, language="ja")


def test_japanese_deterministic_guards_use_japanese_cues():
    token = current_language_id.set("ja")
    try:
        assert _is_mental_action("考える", "今後の計画を考える") is True
        assert _is_autonomous_response("同意する", "彼女は同意する") is True
        assert linguistic(
            "agents.director", "_UNCONSCIOUSNESS_CUE").search("彼は気を失った")
        assert linguistic(
            "agents.director", "_SLEEP_CUE").search("彼女は眠っている")
        assert linguistic(
            "agents.director", "_STAY_UNDER_CUE").search("眠り続ける")
        assert not linguistic(
            "agents.director", "_STAY_UNDER_CUE").search("目を覚ます")
    finally:
        current_language_id.reset(token)


def test_japanese_renderer_outputs_japanese_view_and_episode():
    speech = Percept(
        kind="speech", channel="hearing", source_label="レイヤ",
        fidelity="full", data={"body": "手すりに気をつけて。"},
        salience=0.8, order_key=0, dedupe_key="speech:rail:ja")
    view = render_view([speech], language="ja")
    # `can_see` absent means the speaker was HEARD, not seen -- English
    # renders "You hear Reya say", and Japanese must carry the same
    # distinction. It used to collapse both cases to a bare "レイヤ：「…」",
    # dropping a fidelity fact the observer is entitled to.
    # と-quotation, not tag-then-quote: 「…」と言う is the novel norm, while
    # 「レイヤは言う。「…」」 reads as machine translation.
    assert view.text == "「手すりに気をつけて。」とレイヤが言うのが聞こえる。"
    seen = Percept(
        kind="speech", channel="hearing", source_label="レイヤ",
        fidelity="full", data={"body": "手すりに気をつけて。", "can_see": True},
        salience=0.8, order_key=0, dedupe_key="speech:rail:ja")
    assert render_view([seen], language="ja").text == (
        "「手すりに気をつけて。」とレイヤは言う。")
    episode, gist, entities = render_episode([speech], language="ja")
    assert episode == "レイヤの言葉を聞いた。「手すりに気をつけて。」"
    assert gist == episode
    assert entities == ["レイヤ"]


def test_japanese_deterministic_fallback_prose_is_natural_japanese():
    token = current_language_id.set("ja")
    try:
        # 「小声で言う」 doubled the で with the manner slot; ささやく carries
        # the volume in the verb itself.
        assert _inject_dialogue(
            "", "アカリ", "ここは危ないよ。", "full", "whisper", True,
            tone="不安") == (
                "「ここは危ないよ。」とアカリは不安を声ににじませ、ささやく。")
        residue = _compose_residue_view(
            "unconscious", pain=True, loud_event=True)
        # Full stop between fragments, not 読点: each fragment is an
        # independent 終止形 clause, and joining them with 、 is a comma splice.
        assert residue == (
            "闇。遠く、感覚の薄い身体に鈍い痛みがある。"
            "巨大で言葉にならない音が沈んだ意識まで届き、消える。")
        assert ";" not in residue
    finally:
        current_language_id.reset(token)


def test_every_english_system_prompt_carries_the_schema_language_contract(temp_db):
    temp_db.set_setting("active_preset", "Default")
    assert get_prompt("narrator", language="en") == DEFAULT_PROMPTS["narrator"]
    for prompt in DEFAULT_PROMPTS.values():
        assert "LANGUAGE AND SCHEMA CONTRACT" in prompt
        assert "schema field" in prompt
        assert "free-text human-language values" in prompt


def test_provider_boundary_covers_ad_hoc_system_prompts():
    out = apply_common_prompt_policy("A one-off utility instruction.", "en")
    assert out.startswith("A one-off utility instruction.")
    assert "LANGUAGE AND SCHEMA CONTRACT" in out
    assert apply_common_prompt_policy(out, "en") == out


def test_deterministic_linguistics_follow_context_local_story_language(monkeypatch):
    fake = SimpleNamespace(
        id="zz",
        card=lambda name: {
            "agents.common": {
                "_LOOK_VERB_RE": {
                    "$type": "regex", "pattern": r"\bmirar\b", "flags": 2,
                },
            },
        },
    )
    original = language_runtime.language_pack
    monkeypatch.setattr(
        language_runtime, "language_pack",
        lambda language_id="en": fake if language_id == "zz" else original(language_id),
    )
    language_runtime._linguistic_cached.cache_clear()
    token = current_language_id.set("zz")
    try:
        assert linguistic("agents.common", "_LOOK_VERB_RE").search("MIRAR")
    finally:
        current_language_id.reset(token)
        language_runtime._linguistic_cached.cache_clear()


def test_english_compositor_pack_keeps_reference_output_byte_identical():
    default = render_view([_speech()])
    explicit = render_view([_speech()], language="en")
    assert explicit == default
    assert explicit.text == 'Reya says: "Mind the rail."'

    default_episode = render_episode([_speech()])
    explicit_episode = render_episode([_speech()], language="en")
    assert explicit_episode == default_episode


def test_a_renderer_adapter_receives_only_the_admitted_ir_and_mode_state():
    calls = []

    class Renderer:
        def render_view(self, percepts, **state):
            calls.append((list(percepts), state))
            return RenderedView("otra lengua", [], set(), set())

    rendered = render_view([_speech()], mode="player", renderer=Renderer())
    assert rendered.text == "otra lengua"
    assert calls[0][0] == [_speech()]
    assert calls[0][1]["mode"] == "player"
    assert set(calls[0][1]) == {
        "mode", "prev_standing", "prev_described", "full_render"}


def test_legacy_story_without_a_language_reads_as_english(temp_db):
    cid = _chat(temp_db)
    assert story_language(cid) == "en"


def test_new_story_persists_its_validated_language(temp_db):
    created = app.chat_new({"name": "Pack test", "scenario": "", "language": "en"})
    assert created["story_language"] == "en"
    assert temp_db.wget(created["id"], "story_language") == "en"
    # `stored` and `installed` let the client tell "this chat is English" from
    # "this chat's pack is missing and English is the fallback" -- without
    # that distinction the style-guide save overwrote the real language.
    assert app.chat_language_get(created["id"]) == {
        "language": "en", "stored": "en", "installed": True}


def test_unknown_language_cannot_leave_a_partial_chat(temp_db):
    before = temp_db.q("SELECT COUNT(*) AS n FROM chats", one=True)["n"]
    with pytest.raises(HTTPException) as exc:
        app.chat_new({"name": "Bad", "language": "not-installed"})
    assert exc.value.status_code == 400
    after = temp_db.q("SELECT COUNT(*) AS n FROM chats", one=True)["n"]
    assert after == before


def test_story_language_is_an_author_setting_that_survives_reroll(temp_db):
    cid = _chat(temp_db)
    temp_db.wset(cid, "story_language", "en")
    temp_db.wset(cid, "scene", {"rooms": {}})
    ensure_checkpoint(cid, 1)

    # Re-save after the snapshot, exactly like choosing it in the UI while a
    # story is already open. Restore must preserve the author setting.
    temp_db.wset(cid, "story_language", "en")
    temp_db.wset(cid, "scene", {"rooms": {"discarded": {}}})
    restore_checkpoint(cid, 1)

    assert temp_db.wget(cid, "story_language") == "en"
    assert temp_db.wget(cid, "scene")["rooms"] == {}
    assert "story_language" in PRESERVED_SETTING_KEYS


def test_language_pack_api_exposes_manifest_and_ui_catalog(temp_db):
    listing = app.language_packs_get()["language_packs"]
    assert listing[0]["id"] == "en"
    assert listing[0]["story"] is True
    ui = app.language_pack_ui("en")
    assert ui["language"]["direction"] == "ltr"
    assert ui["messages"]["language.name"] == "English"


def test_ui_language_is_persisted_and_bootstraps_its_catalog(temp_db):
    assert app.ui_language_put({"language": "en"}) == {
        "ok": True, "language": "en"}
    boot = app.bootstrap()
    assert boot["ui_language"] == "en"
    assert boot["ui_direction"] == "ltr"
    assert boot["ui_messages"]["Stories"] == "Stories"


def test_japanese_story_and_interface_language_persist_independently(temp_db):
    created = app.chat_new({
        "name": "日本語テスト", "scenario": "雨の夜", "language": "ja"})
    assert created["story_language"] == "ja"
    assert story_language(created["id"]) == "ja"

    assert app.ui_language_put({"language": "ja"}) == {
        "ok": True, "language": "ja"}
    boot = app.bootstrap()
    assert boot["ui_language"] == "ja"
    assert boot["ui_messages"]["Stories"] == "物語"
    assert story_language(created["id"]) == "ja"


def test_pack_lookup_rejects_invalid_and_uninstalled_ids():
    with pytest.raises(LanguagePackError):
        require_language_pack("../../en", capability="story")
    with pytest.raises(LanguagePackError):
        require_language_pack("es", capability="story")
    assert language_pack("en-US").id == "en"
