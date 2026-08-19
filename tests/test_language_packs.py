"""Language packs are real runtime inputs, with English as the parity pack."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
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
from llm.prompts import (
    DEFAULT_PROMPTS, character_prompt, default_prompts_for, get_prompt,
)


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
    # A FLOOR, not an equality, so a prompt going MISSING still fails here
    # while a deliberate retirement is one edit. Two have been retired:
    # `move_repeat_screen` with the quality re-ask it existed to gate, and
    # `gap_medium` with the gap generator's second rung (superseded by
    # `offscreen.profile_summary_record`, which makes the same bounded call
    # out of band and into state fields rather than prose).
    #
    # Counted over what the pack PUBLISHES, not what it stores: the seven
    # Director sheets are assembled from `specialists`/`prose_author_sheet`
    # and deliberately carry no stored body of their own.
    assert len(default_prompts_for("en")) >= 41
    # Perception composes every view deterministically and has no model role,
    # so it must carry no prompt: one in the pack is 28k characters shipped to
    # nobody, surfaced in the host's prompt editor as if it were editable, and
    # paid for again in every translation.
    assert "perception" not in packs["en"].card("system_prompts")["prompts"]
    # The Director monolith is gone; only the scoped prose-author sheet remains.
    assert "director_resolve" not in default_prompts_for("en")
    assert "director_resolve_lean" in default_prompts_for("en")
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
    assert set(default_prompts_for("ja")) == set(DEFAULT_PROMPTS)
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


def _assembled_specialist_sheet(card, name):
    spec = card["specialists"][name]
    return spec["core"] + "".join(
        spec["chunks"][channel] for channel in spec["order"])


def test_every_director_sheet_the_editor_publishes_is_the_one_a_beat_assembles():
    """The prompt editor must show the sheet the runtime actually loads.

    A specialist sheet has exactly one authored source -- its core plus the
    per-channel chunks scoping selects from. Publishing a second, separately
    stored body under the same prompt id is a sheet with two spellings, and
    the editor shows the copy no beat runs. Saving that copy as a preset
    replaces the assembled sheet with it for every beat afterwards.
    """
    from language_runtime import apply_prompt_policy
    from llm import prompts as prompt_module

    for pack in installed_language_packs(refresh=True).values():
        if not pack.story:
            continue
        card = pack.card("system_prompts")
        published = prompt_module.default_prompts_for(pack.id)
        for name in card["specialists"]:
            pid = f"director_{name}"
            expected = apply_prompt_policy(
                _assembled_specialist_sheet(card, name), pack.id, pid)
            assert published[pid] == expected, (
                f"{pack.id} pack publishes a {pid} sheet that is not the "
                f"assembly the runtime loads "
                f"({len(published[pid])} chars vs {len(expected)})")
        lean = apply_prompt_policy(
            "".join(text for _name, text in card["prose_author_sheet"]),
            pack.id, "director_resolve_lean")
        assert published["director_resolve_lean"] == lean


def test_no_pack_stores_a_second_copy_of_an_assembled_director_sheet():
    """The duplication itself, refused at the source.

    Byte-equal copies are drift in waiting; these had already drifted (the
    English `director_spatial` body was 1,518 characters short of its own
    assembly -- the whole `comms_ops` chunk -- and every Japanese sheet
    differed). Keeping the bodies out of the card is what makes the equality
    above unbreakable rather than merely currently true.
    """
    from llm.prompts import ASSEMBLED_SHEET_IDS

    for pack in installed_language_packs(refresh=True).values():
        stored = set(pack.card("system_prompts")["prompts"])
        duplicated = sorted(stored & set(ASSEMBLED_SHEET_IDS))
        assert not duplicated, (
            f"language pack {pack.id!r} stores a second body for "
            f"{', '.join(duplicated)}; those sheets are assembled from "
            "`specialists`/`prose_author_sheet` and must live there only")


# --- Decision 2: the deterministic recognizers inside `mind/` ---------------
#
# Two dozen recognizers -- belief-confidence calibration, claim similarity,
# memory salience, durable-quote detection, mood valence -- decided their
# answers from English literals in a pack engine, and the linguistics card had
# no `mind.*` key at all, so a pack had nowhere to put a translation even if
# somebody wrote one. `ja` declares `"story": true`, which under AGENTS.md is a
# claim that deterministic recognition is covered in that language.

#: (module, name) -> the live constant it must still equal in English, or None
#: where the value is inlined at its call site and has no constant to compare.
#: Parity is checked only while the constant EXISTS: the call sites belong to
#: `mind/` and `persist/`, and repointing one deletes its constant.
_MIND_LINGUISTICS = {
    ("mind.theory_of_mind", "_STOPWORDS"): ("mind.theory_of_mind", "_STOPWORDS"),
    ("mind.theory_of_mind", "_TOKEN_RE"): None,
    ("mind.theory_of_mind", "_KIND_CUES"): ("mind.theory_of_mind", "_KIND_CUES"),
    ("mind.affect", "AFFECT_LEXICON"): ("mind.affect", "AFFECT_LEXICON"),
    ("mind.affect", "_QUADRANT_DEFAULTS"): None,
    ("mind.memory", "_STOPWORDS"): ("mind.memory", "_STOPWORDS"),
    ("mind.memory", "_WORD_RE"): None,
    ("mind.memory", "_OLD_CUES"): ("mind.memory", "_OLD_CUES"),
    ("mind.memory", "_RECENT_CUES"): ("mind.memory", "_RECENT_CUES"),
    ("mind.memory", "_ENTITY_CANDIDATE_RE"): None,
    ("mind.memory", "_ENTITY_BLOCKED"): None,
    ("mind.memory", "_MOOD_TOKEN_RE"): None,
    ("mind.memory", "_MOOD_VALENCE"): ("mind.memory", "_MOOD_VALENCE"),
    ("mind.memory", "_PROMISE_QUERY_CUES"): None,
    ("mind.memory", "_CLAUSE_SPLIT"): ("mind.memory", "_CLAUSE_SPLIT"),
    ("mind.memory", "_SUPPORT_STOPWORDS"): ("mind.memory", "_SUPPORT_STOPWORDS"),
    ("mind.memory", "_SUPPORT_WORD_RE"): None,
    ("persist.commit_memory", "_SALIENCE_CUES"): None,
    ("persist.commit_memory", "_DURABLE_QUOTE_MARKERS"): None,
}


def test_every_mind_recognizer_has_a_place_in_every_story_pack():
    for pack in installed_language_packs(refresh=True).values():
        if not pack.story:
            continue
        for module, name in _MIND_LINGUISTICS:
            value = linguistic(module, name, pack.id)
            assert value, f"{pack.id} pack has an empty {module}.{name}"


def test_the_english_mind_cards_still_equal_the_constants_they_replace():
    """A card that has drifted from the module is worse than no card.

    Checked only while the constant still exists -- the call sites live in
    `mind/` and `persist/`, and repointing one to `linguistic(...)` deletes
    its constant. Until then this is what keeps the two spellings level.
    """
    import importlib

    for (card_module, card_name), source in _MIND_LINGUISTICS.items():
        if source is None:
            continue
        module_name, constant_name = source
        constant = getattr(
            importlib.import_module(module_name), constant_name, None)
        if constant is None:
            continue
        value = linguistic(card_module, card_name, "en")
        if hasattr(constant, "pattern"):
            assert value.pattern == constant.pattern, card_name
        else:
            assert value == constant, f"en {card_module}.{card_name}"


def test_japanese_mind_recognizers_actually_recognize_japanese():
    """The point of decision 2: the claim `"story": true` becomes true.

    English word regexes return NOTHING on unspaced Japanese, so before this
    every claim comparison scored 0 against every other claim, every FTS query
    was empty, `_inferred_kind` returned None on every claim (silently
    retiring the confidence-calibration guard entirely), no quote was ever
    kept verbatim and every memory scored the flat length-only salience.
    """
    import re

    claim = "彼女は私が鍵を欲しがっていると思っている"
    tokens = linguistic("mind.theory_of_mind", "_TOKEN_RE", "ja").findall(claim)
    assert len(tokens) > 3, tokens
    assert not linguistic(
        "mind.theory_of_mind", "_TOKEN_RE", "en").findall(claim)

    kinds = [kind for kind, cues
             in linguistic("mind.theory_of_mind", "_KIND_CUES", "ja")
             if any(re.search(cue, claim) for cue in cues)]
    assert kinds[:1] == ["second_order"], kinds

    line = "必ず戻ると約束する"
    markers = linguistic("persist.commit_memory", "_DURABLE_QUOTE_MARKERS", "ja")
    assert any(re.search(pattern, line) for pattern in markers["promise"])

    salient = "血の匂いがした"
    assert any(cue in salient for cue
               in linguistic("persist.commit_memory", "_SALIENCE_CUES", "ja"))

    mood = set(linguistic("mind.memory", "_MOOD_TOKEN_RE", "ja")
               .findall("不安で眠れない"))
    signs = [sign for words, sign
             in linguistic("mind.memory", "_MOOD_VALENCE", "ja")
             if mood & set(words)]
    assert signs == [-1.0], signs

    entities = linguistic(
        "mind.memory", "_ENTITY_CANDIDATE_RE", "ja").findall(
            "カレンさんが桟橋にいた")
    assert "カレン" in entities, entities


def test_the_quadrant_fallback_label_exists_in_every_packs_lexicon():
    """`quadrant_label` is the label used when nothing the model proposed
    survives reconciliation, and `label_matches` must then accept it. A
    Japanese lexicon with English fallback labels would return a label its own
    pack cannot judge, which reads as agreement rather than as a miss."""
    for pack in installed_language_packs(refresh=True).values():
        if not pack.story:
            continue
        lexicon = linguistic("mind.affect", "AFFECT_LEXICON", pack.id)
        defaults = dict(
            linguistic("mind.affect", "_QUADRANT_DEFAULTS", pack.id))
        assert len(defaults) == 9, (pack.id, defaults)
        for (v_sign, a_sign), label in defaults.items():
            entry = lexicon.get(label)
            assert entry is not None, (pack.id, label)
            assert (entry["v"], entry["a"]) == (v_sign, a_sign), (
                pack.id, label, entry)


#: Names that reached the shipped prompt cards from one of the owner's live
#: stories. A prompt is read by EVERY story, so an example drawn from one of
#: them narrows what the model thinks the field is for (CLAUDE.md, fix the
#: class not the instance). This is a tripwire, not the rule: the rule is that
#: a prompt names the distinction -- "any craft whose inside is rooms you
#: stand in", "the perceiver is you" -- and these two are what taught it.
_STORY_INSTANCE_NAMES = ("TARDIS", "Hinami")


def test_no_prompt_card_names_a_character_or_vehicle_from_one_story():
    for pack in installed_language_packs(refresh=True).values():
        if not pack.story:
            continue
        body = json.dumps(
            (ROOT / f"language_packs/{pack.id}/cards/system_prompts.json")
            .read_text(encoding="utf-8"))
        found = [name for name in _STORY_INSTANCE_NAMES if name in body]
        assert not found, (
            f"{pack.id} prompt card names {found} -- an instance from one "
            "story, in a sheet every story reads")


def test_every_nsfw_prompt_id_names_a_prompt_that_exists():
    """`nsfw_prompt_ids` is an ALLOW-list, so an id naming nothing is not a
    no-op waiting to be useful -- it is a claim that a sheet gets the overlay,
    made in a place where being wrong is invisible. `perception` sat in both
    packs' lists after the perception prompt was retired (perception composes
    every view deterministically and has no model role at all)."""
    from llm.prompts import ASSEMBLED_SHEET_IDS

    for pack in installed_language_packs(refresh=True).values():
        card = pack.card("system_prompts")
        known = set(card["prompts"]) | set(ASSEMBLED_SHEET_IDS)
        unmatched = sorted(set(card["nsfw_prompt_ids"]) - known)
        assert not unmatched, (
            f"language pack {pack.id!r} marks {unmatched} NSFW-overlaid, and "
            "no such prompt exists")


def test_the_conditions_shape_a_prompt_shows_is_the_shape_declared():
    """`StateDiff.conditions` is `dict[str, list[dict]]`, and the worked
    example writes a list of one -- while `resolve_repair` and the body
    specialist's own chunk both printed `conditions:{condition_id:{...}}`, a
    bare object under each id. `_coerce_conditions` accepts the singular form
    and wraps it, so nothing ever failed and nothing said the sheet was
    wrong; a model taught the singular simply cannot express the second
    reading of a condition it is otherwise being asked for.
    """
    import re

    singular = re.compile(r"conditions:\\?\{condition_id:\\?\{")
    plural = re.compile(r"conditions:\\?\{condition_id:\\?\[")
    for pack in installed_language_packs(refresh=True).values():
        if not pack.story:
            continue
        blob = (ROOT / f"language_packs/{pack.id}/cards/system_prompts.json"
                ).read_text(encoding="utf-8")
        assert not singular.search(blob), (
            f"{pack.id} shows conditions keyed to a bare object; the field "
            "is dict[str, list[dict]]")
        assert plural.search(blob), f"{pack.id} shows no conditions shape"


def test_every_level_rung_the_engine_accepts_is_published_in_every_pack():
    """A condition whose `state.level` the engine reads must publish the whole
    ladder in the sheet that writes it, in every story pack.

    `awareness` does: the body specialist's chunk carries
    `level in {unconscious|sedated|asleep|dazed}`. `restraint` did not -- what
    the specialist was handed was a parenthetical of examples, and `encased`
    appeared nowhere in either pack. `_normalize_restraint_level` then folded
    every word it could not read down to `held`, the mildest rung, so a body
    pinned under a beam and a hand on a wrist were recorded as the same state.
    An unpublished rung is unreachable in practice and silently wrong in the
    record, which is why this asserts over the enums rather than over a list
    of words: the next `level` ladder is caught by adding its constant here.
    """
    from story.scene import AWARENESS_LEVELS, RESTRAINT_LEVELS

    ladders = {
        # `awake` is the absence of the condition, never a value to record.
        "awareness": tuple(l for l in AWARENESS_LEVELS if l != "awake"),
        "restraint": RESTRAINT_LEVELS,
    }
    for pack in installed_language_packs(refresh=True).values():
        if not pack.story:
            continue
        chunk = pack.card("system_prompts")["specialists"]["body"]["chunks"]["conditions"]
        for kind, rungs in ladders.items():
            assert f"kind:'{kind}'" in chunk, (
                f"{pack.id} never names the {kind} condition to the "
                "specialist that has to write it")
            missing = [rung for rung in rungs if rung not in chunk]
            assert not missing, (
                f"{pack.id} publishes no {kind} rung {missing}; a level the "
                "engine accepts and no prompt states is a rung nothing can "
                "reach")


def test_no_english_compat_export_survives_without_a_reader():
    """`llm/prompts.py`'s module constants are eagerly-bound views of the
    ENGLISH pack, kept under the comment "compatibility exports used by the
    prompt editor, project checks, benches, and tests". Seven of them had no
    reader anywhere -- so they were not compatibility with anything, they were
    the English text of seven fragments resolved at import in a module whose
    whole point is that the story language is resolved at USE time.

    The rule, rather than the seven: a name bound from the English card at
    import must be read by something, or it is a second, language-blind
    spelling of a value the localized accessor already provides.
    """
    import ast

    prompts_path = ROOT / "llm" / "prompts.py"
    tree = ast.parse(prompts_path.read_text(encoding="utf-8"))
    english_bound = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id.startswith("_"):
            continue
        if "_ENGLISH" in ast.dump(node.value):
            english_bound.append(target.id)
    assert english_bound, "the compat exports vanished entirely"

    searched = [path for package in ("agents", "core", "llm", "mind",
                                     "persist", "story", "web", "tools",
                                     "tests", "extension_runtime")
                for path in (ROOT / package).rglob("*.py")
                if path != prompts_path]
    bodies = {path: path.read_text(encoding="utf-8") for path in searched}
    orphans = [name for name in english_bound
               if not any(re.search(rf"\b{name}\b", body)
                          for body in bodies.values())]
    assert not orphans, (
        "English compat exports nothing reads: " + ", ".join(orphans))


#: Authored fragments the prompt card also embeds verbatim inside prompt
#: bodies, with the number of copies English currently carries. Four
#: fragments, seventeen copies, each maintained by hand.
_EMBEDDED_FRAGMENTS = {
    "category_note": 5,
    "book_type_note": 3,
    "transit_note": 3,
    "extra_parts_note": 6,
}


def _authored_leaves(value, path=()):
    # Mapping, not dict: `LanguagePack.card()` hands back the frozen
    # mappingproxy `language_runtime._freeze` builds, which is not a dict
    # subclass -- type-testing for dict walks zero leaves and silently
    # disarms the check, exactly as it once did in tools/project_check.py.
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _authored_leaves(child, path + (str(key),))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _authored_leaves(child, path + (str(index),))
    elif isinstance(value, str):
        yield ".".join(path), value


def test_every_embedded_copy_of_a_fragment_still_equals_the_fragment():
    """Four fragments are ALSO pasted verbatim into seventeen prompt bodies.

    `category_note` into five, `book_type_note` into three, `transit_note`
    into three, `extra_parts_note` into six -- each a hand-maintained copy of
    a value the card already holds once. Editing the fragment and not its
    copies leaves two prompts teaching different rules for the same field,
    and nothing anywhere compares them.

    English is the reference pack and this holds it exact. The Japanese pack
    is a known and separate gap: ZERO of its seventeen copies equal their own
    Japanese fragment, because the translation pass rendered the fragment and
    each embedded copy independently. Closing that needs either seventeen
    re-translations or a fragment-substitution mechanism in the card format,
    which is a bigger decision than this guard.
    """
    english = installed_language_packs(refresh=True)["en"]
    card = english.card("system_prompts")
    leaves = dict(_authored_leaves(card))
    for name, expected in _EMBEDDED_FRAGMENTS.items():
        fragment = str(card[name])
        copies = [path for path, body in leaves.items()
                  if path != name and fragment in body]
        head = fragment[:60]
        drifted = [path for path, body in leaves.items()
                   if path != name and head in body and fragment not in body]
        assert not drifted, (
            f"{name} has drifted from its copies at: {drifted}")
        assert len(copies) == expected, (
            f"{name} is embedded {len(copies)} times, not {expected} -- "
            "update the count deliberately, or a copy went missing")
