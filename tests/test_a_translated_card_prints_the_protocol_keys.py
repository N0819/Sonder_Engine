"""A translated card prints the protocol's keys, never translations of them.

The Japanese opening card's printed output shape -- the thing a model imitates
-- said `服装:{entity_name:{wearing:[], state:[]}}` where the schema key is
`attire`, and translated `posture`, `activity`, `kind`, `description`,
`distance`, `intensity` and `scale` inside its key lists (schemas audit F4).
An establish answer written to that shape validates with `attire: {}` and
empty postures, with no warning, because `DirectorEstablish` ignores keys it
does not declare: a Japanese story's opening clothing -- the richest clothing
detail a story ever has -- was lost at beat 0. `resolve_repair` carried the
same class in its attire diff shape (`服装:{名前:{追加:[],削除:[],...}}`).

The pack's own policy says keys are never translated; the explanation around
a key may be Japanese, the key is the protocol token. `make structure`'s span
check cannot see this shape (it reads quoted, backticked, dotted or
underscored spans), so the class is asserted here over every Japanese part.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JA_PARTS = ROOT / "language_packs" / "ja" / "cards" / "system_prompts"
CJK = "぀-ヿ㐀-䶿一-鿿ｦ-ﾟ"

#: A CJK word printed as a KEY: directly before `:{` or `:[`, not glued to an
#: ASCII key it explains (`overは任意:[room_ids]` is the key `over` and a
#: note), and not a template label before a `{placeholder}` or a quoted JSON
#: example (`記憶: {memory}`, `提案するとき: {"calls": ...}`).
_KEY_BEFORE_OPEN = re.compile(
    r"(?<![A-Za-z0-9_" + CJK + r"])([" + CJK + r"]{1,10})\s?:\s?([\{\[])"
    r"(?![A-Za-z_][A-Za-z0-9_]*\}|\")")
#: One {...} key list.
_BRACE = re.compile(r"\{([^{}]{1,600})\}")


def _translated_keys(text):
    found = [m.group(1) for m in _KEY_BEFORE_OPEN.finditer(text)]
    for match in _BRACE.finditer(text):
        items = [item.strip() for item in re.split(r"[,、]", match.group(1))]
        protocol = [i for i in items
                    if re.match(r"[A-Za-z_][A-Za-z0-9_]*\s*(?::|$)", i)]
        translated = [i for i in items if re.fullmatch("[" + CJK + "]{1,10}", i)]
        if protocol and translated:
            found.extend(translated)
    return found


@pytest.mark.parametrize("path", sorted(JA_PARTS.rglob("*.txt")),
                         ids=lambda p: str(p.relative_to(JA_PARTS)))
def test_no_japanese_part_prints_a_translated_key(path):
    assert _translated_keys(path.read_text(encoding="utf-8")) == []


def test_the_detector_sees_the_shipped_class():
    """The detector is only worth what it catches: the strings that shipped."""
    assert _translated_keys("、服装:{entity_name:{wearing:[], state:[]}}") == ["服装"]
    assert _translated_keys("poses:{entity_name:{姿勢、支え、relative_to}}") == [
        "姿勢", "支え"]
    assert _translated_keys("overは任意:[room_ids]") == []
    assert _translated_keys("記憶: {memory} これを思い出すと") == []
    assert _translated_keys('提案するとき: {"calls": []}') == []


@pytest.mark.parametrize("prompt, shapes", [
    ("prompts/director_establish.txt", [
        "poses:{entity_name:{posture,support,relative_to,relation,constraint,detail}}",
        "attire:{entity_name:{wearing:[], state:[]}}",
        "entity_states:{entity_name:{posture,activity,held_items:[],visible_conditions:[]}}",
        "sensory_events:[{kind,description,source_room,distance,intensity}]",
        "fiction_frame:{frame_id,world_id,location_id,scale,temporal_mode,causal_regime_ids}",
    ]),
    ("prompts/resolve_repair.txt", [
        "attire:{name:{add:[],remove:[],conditions:{},coverage:{garment:"
        "{region:[zones still covered] or []}}}}, cast_changes:[], location:'', time",
    ]),
])
def test_the_japanese_shape_is_the_english_shape(prompt, shapes):
    english = (ROOT / "language_packs" / "en" / "cards" / "system_prompts"
               / prompt).read_text(encoding="utf-8")
    japanese = (JA_PARTS / prompt).read_text(encoding="utf-8")
    for shape in shapes:
        assert shape in english, f"the English card no longer prints {shape!r}"
        assert shape in japanese, shape
