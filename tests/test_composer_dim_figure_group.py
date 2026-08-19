"""Layer A minted the label from the active pack; Layer B compared English.

`presence_percepts` reads the dim-figure label at use time through
`_dim_figure()`, so a body seen only as shapes carries the ACTIVE pack's
wording. `_render_presence_group` -- the consumer, and the reason the label
has a plural at all ("three of them in one room rendered as the same
sentence three times, 282 views in the corpus replay") -- tested that label
against the English compat export `DIM_FIGURE`. Where the two differ the
`startswith` can never be true and the counting rule silently does not run.

Where they differ is the English reference renderer running on non-English
percepts, which is not hypothetical: `render_view` falls through to it
whenever a pack's own adapter raises, deliberately, so that "a malformed
pack must cost wording, never the whole beat". The wording it costs should
not include a rule that has nothing to do with the pack.
"""

from language_runtime import current_language_id

from agents.composer import (
    DIM_FIGURE, Percept, _dim_figure, _render_presence_group,
)


def _dim_presence(label, key):
    return Percept(
        kind="presence", channel="sight", source_label=label,
        fidelity="degraded",
        data={"tier": "near", "source_key": key},
        salience=0.4, dedupe_key="presence:" + key,
    )


def _group_in(language):
    token = current_language_id.set(language)
    try:
        label, plural = _dim_figure(), _dim_figure(True)
        percepts = [_dim_presence(label, "a"), _dim_presence(label, "b")]
        return label, plural, _render_presence_group(percepts)
    finally:
        current_language_id.reset(token)


def test_two_shapes_are_counted_in_english():
    """The baseline. English is the one language where the compat export and
    the active pack agree, which is why the defect never showed here."""
    label, plural, group = _group_in("en")
    assert label == DIM_FIGURE
    assert len(group) == 1
    sentence = group[0][1]
    assert "Two" in sentence, sentence
    assert sentence.casefold().count(DIM_FIGURE.casefold()) == 0, sentence


def test_two_shapes_are_counted_when_the_label_is_not_english():
    """The defect, and what it actually costs.

    Identical clauses collapse either way, so the stutter half of the rule
    survives. What does not is the COUNT: with the comparison missing, an
    observer who can see that there are two figures in the room is told
    about one. That is a fact their own eyes have, dropped by a string
    comparison against a language they are not reading."""
    label, plural, group = _group_in("ja")
    assert label != DIM_FIGURE, (
        "this test needs a pack whose dim-figure label differs from English")
    assert len(group) == 1
    sentence = group[0][1]
    assert "Two" in sentence, (
        f"two figures were rendered as one: {sentence!r}")
    assert plural in sentence, (
        f"the plural label came from the wrong pack: {sentence!r}")
