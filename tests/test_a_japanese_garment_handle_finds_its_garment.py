"""A Japanese garment named the short way is the garment it names.

Japanese drops a garment's modifiers exactly as English does -- ブラウス for
白いブラウス, as "the blouse" for "white silk blouse" -- and every reader of a
handle measured it in spaces and ASCII: `resolve_garment`'s head noun was
the last whitespace word (the whole unspaced name), its containment test was
`\\b` (which cannot fire between two kana), and the licence readers' word sets
were `[a-z0-9]`. So `remove: ["ブラウス"]` was a no-op, the licence never saw
the garment named, the write gate's subject reading never fired on a
Japanese sentence (a paragraph was one "sentence" and `\\bヒナミ\\b` failed
before a particle), and the gate -- which fails CLOSED -- refused the
undressing (story_attire_import audit F8; the lane brief's F4).

A garment name in a head-final script ends on its noun, so the head of an
unspaced name is its last script run; its edges are judged by the engine's
script-aware name boundary; and a Japanese sentence ends at 。.

Not here, and why: 「ヒナミは服を着替えた。」 names clothing only through 服
("clothes"), a word the English `_CLOTHING_CONTEXT` vocabulary has no entry
for. A Japanese clothing vocabulary is pack data, not engine code.
"""

from __future__ import annotations

from story import attire


BLOUSE = "白いブラウス"


def test_the_short_handle_resolves_to_the_worn_garment():
    assert attire.resolve_garment("ブラウス", [BLOUSE, "黒いスカート"]) == BLOUSE
    assert attire.resolve_garment("white blouse", ["white silk blouse"]) \
        == "white silk blouse"                    # the English control


def test_an_ambiguous_japanese_handle_resolves_to_nothing():
    assert attire.resolve_garment("ブラウス", [BLOUSE, "青いブラウス"]) is None


def test_a_word_inside_a_longer_one_is_not_the_garment():
    # 帯 (sash) is not 帯締め (the cord tied over it), nor 一帯 (an area).
    assert attire.resolve_garment("帯", ["帯締め"]) is None
    assert attire.resolve_garment("帯", ["絹の帯"]) == "絹の帯"


def test_the_licence_sees_a_garment_named_the_short_way():
    assert attire.garments_named_in(["ヒナミはブラウスを脱いだ。"], [BLOUSE],
                                    [BLOUSE]) == [BLOUSE]
    assert attire.garments_named_in(["ヒナミは窓を開けた。"], [BLOUSE],
                                    [BLOUSE]) == []


def test_the_write_gate_knows_whose_clothing_the_sentence_is_about():
    wardrobe = {"ヒナミ": [BLOUSE], "ドクター": ["白衣"]}
    assert attire.wardrobe_change_subjects(
        "ヒナミはブラウスを脱いだ。", [], wardrobe, "ヒナミ") == {"ヒナミ"}
    assert attire.wardrobe_change_subjects(
        "二人は黙って座っていた。", [], wardrobe, "ヒナミ") == set()


def test_a_japanese_paragraph_is_several_sentences():
    wardrobe = {"ヒナミ": [BLOUSE], "ドクター": ["白衣"]}
    subjects = attire.wardrobe_change_subjects(
        "", ["ドクターは窓を開けた。ヒナミはブラウスを脱いだ。"], wardrobe,
        "ヒナミ")
    assert subjects == {"ヒナミ"}


def test_a_restatement_with_the_short_handle_keeps_the_garment():
    before = attire.normalize_regions({"wearing": [BLOUSE, "黒いスカート"]})
    after = attire.apply_flat_change(before, ["ブラウス", "スカート"])
    assert attire.newly_removed(before, after) == []
