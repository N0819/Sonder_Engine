"""A name written without spaces is withheld by its PARTS, as a spaced one is.

Two places decide what an observer who has not met a body may read: the
stranger's label (`_summary_label`, under `_unknown_actor_label` and
`stranger_label_ladder`) and the identity scrub that runs LAST on every view
(`_scrub_unknown_identities`). Both found a name's parts by whitespace -- the
label's head-final branch stripped only the whole name and the authored
aliases, and the scrub derived parts only from a name holding a space -- so a
Japanese card named 佐藤ヒナミ (or 佐藤・ヒナミ) whose summary or whose prose
used the bare given name reached every stranger's view as ヒナミ (agents_common
audit F1 and F2: "見知らぬヒナミは狐耳の背の高い女性", and
`('ヒナミが手を振る。', [])` with the leak unreported). The parts are the
name's script runs (`_name_tokens`: 佐藤 | ヒナミ, the middle dot outside every
class), each at the length an unspaced script identifies somebody in.
"""

from __future__ import annotations

import pytest

from language_runtime import language_scope

from agents import common


FOX = {"appearance": "狐耳の背の高い女性。", "aliases": []}


@pytest.mark.parametrize("name, summary", [
    ("佐藤ヒナミ", "ヒナミは狐耳の背の高い女性。"),
    ("佐藤ヒナミ", "狐耳の背の高い女性、ヒナミ。"),
    ("佐藤・ヒナミ", "ヒナミは狐耳の背の高い女性。"),
    ("佐藤ヒナミ", "佐藤は狐耳の背の高い女性。"),
    ("佐藤ヒナミ", "ヒナミさんは狐耳の背の高い女性。"),
])
def test_a_japanese_strangers_label_carries_no_part_of_her_name(name, summary):
    with language_scope("ja"):
        label = common._unknown_actor_label(name, summary, [])
        base, wider = common.stranger_label_ladder(name, summary, [])
    for part in ("ヒナミ", "佐藤"):
        assert part not in label, label
        assert part not in base and not any(part in w for w in wider), base
    assert "狐耳" in label, label


def test_the_label_still_reads_the_body_and_keeps_a_role_worn_in_the_name():
    with language_scope("ja"):
        plain = common._unknown_actor_label("佐藤ヒナミ", "狐耳の背の高い女性。", [])
        guard = common._unknown_actor_label(
            "衛兵ハルト", "ハルトは衛兵の制服を着た若い男。", [], role="衛兵")
    assert plain == "見知らぬ狐耳の背の高い女性", plain
    assert "ハルト" not in guard and "衛兵" in guard, guard


def test_an_english_label_is_unchanged():
    assert common._unknown_actor_label(
        "Hinami Sato", "Hinami, a fox-eared young woman with amber eyes.", []
    ) == "the fox-eared young woman"


@pytest.mark.parametrize("name", ["佐藤ヒナミ", "佐藤・ヒナミ"])
def test_the_last_pass_scrub_withholds_a_bare_given_name(name):
    with language_scope("ja"):
        view, leaked = common._scrub_unknown_identities(
            "ヒナミが手を振る。", allowed_forms=[],
            unknown_sources=[dict(FOX, name=name)])
    assert "ヒナミ" not in view, view
    assert leaked == [name]


def test_a_part_the_observer_commands_or_too_short_to_identify_is_left():
    with language_scope("ja"):
        known, leaked = common._scrub_unknown_identities(
            "ヒナミが手を振る。", allowed_forms=["ヒナミ"],
            unknown_sources=[dict(FOX, name="佐藤ヒナミ")])
        forest, none = common._scrub_unknown_identities(
            "林の中を歩く。", allowed_forms=[],
            unknown_sources=[dict(FOX, name="林ヒナミ")])
    assert known == "ヒナミが手を振る。" and leaked == []
    assert forest == "林の中を歩く。" and none == []


def test_an_english_scrub_is_unchanged():
    view, leaked = common._scrub_unknown_identities(
        "Hinami waves. Jean-Luc nods.", allowed_forms=[],
        unknown_sources=[
            {"name": "Hinami Sato", "appearance": "A fox-eared woman.",
             "aliases": []},
            {"name": "Jean-Luc", "appearance": "A bald man.", "aliases": []}])
    assert "Hinami" not in view and "Jean-Luc" not in view, view
    assert leaked == ["Hinami Sato", "Jean-Luc"]
    # A hyphenated Latin name is one word: no fragment of it is scrubbed.
    alone, none = common._scrub_unknown_identities(
        "Luc is a common enough word here.", allowed_forms=[],
        unknown_sources=[{"name": "Jean-Luc", "appearance": "A bald man.",
                          "aliases": []}])
    assert alone == "Luc is a common enough word here." and none == []
