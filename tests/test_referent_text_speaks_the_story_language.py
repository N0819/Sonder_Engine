"""Text the composer builds BEFORE the language adapter sees it speaks the
story's language, not the reference renderer's.

`render_view` hands a Japanese story to the Japanese adapter, but the pose
referents and spliced nouns are minted upstream by `_pose_referent` and
`_noun_phrase`, and both read the ENGLISH card regardless of the story
language -- so the adapter rendered them verbatim. Measured on chat 122 (a
fresh Japanese story on a copy, 2026-09-07): "the 砂浜の上に", a body
arranged "youの向かってに" (the composer's self sentinel printed as a word),
and a stranger label "見知らぬごく普通の人間の若い女性。" carrying the 。 of
the presented appearance it was cut from, because the terminal-stop strip
knew the ASCII full stop alone.
"""

from __future__ import annotations

from agents import composer
from agents.composer import Percept, render_view
from language_runtime import language_scope


def _scene():
    return {"rooms": {"beach": {"name": "月明かりの浜辺", "adjacent": [],
                                "anchors": {"tide_line": {"desc": "波打ち際。"}}}},
            "positions": {"Hinami": "beach", "The Doctor": "beach"},
            "entities": {"tardis": {"name": "青い警察電話ボックス", "kind": "object"}}}


class TestReferentsInJapanese:
    def test_a_bare_noun_takes_no_english_article(self):
        with language_scope("ja"):
            assert composer._noun_phrase("砂浜") == "砂浜"
            assert composer._pose_referent(
                _scene(), "Hinami", {}, [], "砂浜", is_self=True) == "砂浜"

    def test_an_entity_is_named_through_the_packs_own_template(self):
        with language_scope("ja"):
            assert composer._pose_referent(
                _scene(), "Hinami", {}, [], "tardis", is_self=True) \
                == "青い警察電話ボックス"
        assert composer._pose_referent(
            _scene(), "Hinami", {}, [], "tardis", is_self=True) \
            == "the 青い警察電話ボックス"

    def test_a_fixture_keeps_the_english_article_only_in_english(self):
        with language_scope("ja"):
            assert composer._pose_referent(
                _scene(), "Hinami", {}, [], "tide_line", is_self=True) \
                == "tide line"

    def test_the_packs_terminal_stop_is_stripped_from_a_spliced_phrase(self):
        with language_scope("ja"):
            assert composer._noun_phrase("波打ち際。") == "波打ち際"
            assert composer._strip_sentence_ends("若い女性。") == "若い女性"
        assert composer._noun_phrase("The tide line.") == "the tide line"


def test_the_self_sentinel_inside_a_pose_is_the_readers_own_word():
    pose = Percept(
        kind="pose", channel="sight", source_label="見知らぬ男",
        data={"posture": "立っている", "support": "砂浜",
              "relative_to": "you", "relation": "向かって"},
        salience=0.8, order_key=0, dedupe_key="pose:x")
    text = render_view([pose], language="ja").text
    assert "you" not in text
    assert "あなた" in text


def test_the_english_renderer_is_unchanged():
    pose = Percept(
        kind="pose", channel="sight", source_label="you",
        data={"posture": "kneeling", "support": "the floor",
              "relative_to": "the altar", "relation": "below"},
        salience=0.8, order_key=0, dedupe_key="pose:self")
    assert composer._render_pose(pose).startswith(
        "You are kneeling on the floor below the altar")
