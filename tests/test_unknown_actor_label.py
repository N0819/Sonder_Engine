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

    # A LINKING PARTICIPLE dangles exactly as a preposition does, and is the
    # commoner slice: appearance summaries overwhelmingly read "<body>
    # appearing in her early twenties" / "<body> wearing a grey cloak", so the
    # 5-word cap lands on the participle and the phrase it introduced is gone.
    # "the beautiful young woman appearing" promises a clause and delivers
    # none. It matters more than it reads: this label is what a character's
    # own MEMORY calls a stranger.
    label2 = _unknown_actor_label(
        "Hinami",
        "A beautiful young woman appearing in her early twenties, with golden "
        "fox ears and six golden tails",
    )
    assert label2 == "the beautiful young woman"

    assert _unknown_actor_label(
        "Vrenak", "A broad-shouldered smuggler wearing a patched flight jacket",
    ) == "the broad-shouldered smuggler"

    # Only verbs that INTRODUCE a following phrase are trimmed -- a bare -ing
    # rule would eat real nouns.
    assert _unknown_actor_label(
        "Grey", "A veiled figure in mourning",
    ) == "the veiled figure in mourning"


def test_a_label_never_ends_on_a_function_word():
    """The two tail trims must CONVERGE, because each exposes a tail for the
    other.

    Found in a live A/B run, 2026-08-19, not by any test here: a persona
    summary of "a lean courier in a rain-darkened canvas coat, hair cropped
    short" capped to "lean courier in a rain-darkened", lost "a rain-darkened"
    to the amputated-phrase rule, and stood as "the lean courier IN". Every
    unrecognised body in that story wore one -- in perception views, in
    narrated prose, and in the memories written from them, where it is durable.
    "the broad man in". "the old porter in".

    Neither rule was wrong; they ran once each and neither re-read what the
    other uncovered. The failure needs a summary long enough to be capped AND
    a preposition in the first five words, which is why five earlier fixes to
    this function never produced it.
    """
    for summary in ("a lean courier in a rain-darkened canvas coat, "
                    "hair cropped short",
                    "a broad man in a lift operator's uniform",
                    "an old porter in a green coat",
                    "a tall figure with a long scar across one cheek",
                    "a stooped clerk of the outer registry office",
                    "a young runner and a battered leather satchel"):
        label = _unknown_actor_label("Nobody", summary)
        last = label.split()[-1]
        assert last not in ("in", "with", "of", "a", "an", "the", "and",
                            "at", "by", "for", "from", "on", "or", "to",
                            "as", "his", "her", "its", "their"), (
            f"{summary!r} -> {label!r} ends on a function word")


def test_a_short_phrase_that_was_never_capped_keeps_its_preposition():
    """The converse, and the reason the trim is conditional on `truncated`:
    a summary that fits was not cut off, so its trailing phrase is whole."""
    assert _unknown_actor_label("Nobody", "the figure in mourning") == \
        "the figure in mourning"
    assert _unknown_actor_label("Nobody", "a small woman with ink-stained "
                                "fingers") == \
        "the small woman with ink-stained fingers"
