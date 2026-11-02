"""A movement heard behind the observer is told as HEARD, in every pack and
in memory as in the view -- and a reported act of speech is remembered.

`composer.act_percept`'s rear-arc branch mints a hearing percept with no
label and `unseen: True`: what crosses is that something moved, and where,
never who. Three renderers disagreed about it (audit agents_composer F4-F6,
2026-11-01):

  * the Japanese VIEW had no `unseen` branch and took the `shapes` one with an
    empty label -- 「が動いているが、それ以上は見て取れない。」, no subject, and
    a claim of SIGHT for a sound behind the reader; the pack's own
    `act_heard`/`act_heard_placed` were written and never used;
  * the English EPISODE had none either -- " moved, too little of it to make
    out.", the bearing gone, a heard event filed as a seen one -- and every
    such percept signed the same string, so at the outcome a second body's
    movement was dropped as a "repeat" of the first's;
  * the English episode had no `communication` branch at all, so "Rhona
    warns the tide is turning" was remembered by the Japanese pack and by no
    English mind.
"""

import pytest

from agents import composer
from language_runtime import compositor_text, language_scope


def _unseen(bearing="", actor="Bo"):
    return composer.Percept(
        kind="act", channel="hearing", source_label="", fidelity="shapes",
        data={"motion": True, "unseen": True,
              **({"bearing": bearing} if bearing else {})},
        salience=0.4, suddenness=0.3, order_key=1,
        dedupe_key="act-heard:" + composer._short_hash(actor))


def _template(language, key, **values):
    with language_scope(language):
        return compositor_text(key, **values)


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_view_says_it_was_heard_in_both_packs(language):
    behind = composer.render_view([_unseen()], mode="character",
                                  language=language).text
    assert behind.strip() == _template(language, "act_heard").strip(), behind
    where = "あなたの左手" if language == "ja" else "to your left"
    placed = composer.render_view([_unseen(where)], mode="character",
                                  language=language).text
    assert placed.strip() == _template(
        language, "act_heard_placed", where=where).strip(), placed


@pytest.mark.parametrize("language", ["en", "ja"])
def test_memory_files_it_as_heard_with_its_bearing(language):
    where = "あなたの左手" if language == "ja" else "to your left"
    content, _gist, _entities = composer.render_episode(
        [_unseen(where)], language=language)
    mine = "私の左手" if language == "ja" else "to my left"
    assert mine in content, content
    for seen in ("make out", "見て取れ"):
        assert seen not in content, content


def test_two_bodies_heard_moving_are_two_events_to_the_outcome():
    """A heard movement is keyed by its body already (`act-heard:`), so its
    signature does not stand in for it: one body's movement at the onset
    must not swallow another body's at the outcome."""
    one, two = _unseen(actor="Bo"), _unseen(actor="Cy")
    assert one.dedupe_key != two.dedupe_key
    assert composer.episode_signature(one) == ""
    assert composer.episode_signature(two) == ""


def test_an_english_mind_remembers_a_reported_act_of_speech():
    told = composer.Percept(
        kind="communication", channel="hearing", source_label="Rhona",
        fidelity="full",
        data={"surface": "warns the tide is turning", "level": "full",
              "volume": "normal", "can_see": True},
        salience=0.7, order_key=1, dedupe_key="communication:x")
    content, _gist, entities = composer.render_episode([told], language="en")
    assert "Rhona" in content and "tide is turning" in content, content
    assert "Rhona" in entities
    over = composer.Percept(
        kind="communication", channel="hearing", source_label="Rhona",
        fidelity="full",
        data={"surface": "warns the tide is turning", "via": "the radio"},
        salience=0.7, order_key=1, dedupe_key="communication:y")
    content, _gist, _entities = composer.render_episode([over], language="en")
    assert "the radio" in content, content
