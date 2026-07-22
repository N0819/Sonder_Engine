"""Regression test for _unknown_actor_label: every unrecognized actor used
to render as the exact same generic "the unfamiliar person", making two
strangers in one scene indistinguishable in prose and in any memory
recorded from it. It now derives a short, stable descriptor from the
actor's own appearance summary when one is available."""

from __future__ import annotations

from agents.common import _unknown_actor_label


def test_falls_back_to_generic_label_with_no_appearance():
    assert _unknown_actor_label("Vrenak") == "the unfamiliar person"
    assert _unknown_actor_label("Vrenak", None) == "the unfamiliar person"
    assert _unknown_actor_label("Vrenak", "") == "the unfamiliar person"


def test_derives_a_distinct_label_from_appearance():
    label = _unknown_actor_label(
        "Vrenak",
        "A tall, powerfully built reptilian-adjacent humanoid in a "
        "dark-grey military uniform with crimson piping.",
    )
    assert label.startswith("the ")
    assert "unfamiliar person" not in label
    assert "tall" in label


def test_two_different_strangers_get_two_different_labels():
    label_a = _unknown_actor_label(
        "Actor A", "A Starfleet lieutenant in a gold security-division uniform.",
    )
    label_b = _unknown_actor_label(
        "Actor B", "A hooded figure wrapped in a tattered grey cloak.",
    )
    assert label_a != label_b


def test_strips_leading_article_and_stays_short():
    label = _unknown_actor_label("X", "An old woman with silver hair and sharp eyes.")
    assert label == "the old woman with silver hair"


def test_trims_trailing_dangling_function_word():
    # The 5-word cap used to slice mid-phrase and leave a dangling article or
    # preposition ("...five-foot-seven-inches with a"), which reads as broken
    # prose when the label is injected inline. It now ends on a content word.
    label = _unknown_actor_label(
        "Dr. Moon",
        "A young woman, five-foot-seven-inches, with a slightly disheveled uniform",
        aliases=["Sarah Moon"],
    )
    assert label == "the young woman five-foot-seven-inches"
    assert not label.rstrip().endswith((" a", " with", " in", " of"))

    label2 = _unknown_actor_label(
        "Hinami",
        "A beautiful young woman appearing in her early twenties, with golden "
        "fox ears and six golden tails",
    )
    assert label2 == "the beautiful young woman appearing"
