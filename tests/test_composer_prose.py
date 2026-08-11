"""The prose defects the full-corpus replay found by reading the output.

Information fidelity was the composer's strong suit — delivered-line recall
98.5% against the model's 95.0%, identity leaks down, memory twins down 36×.
Texture was not. §E of design_notes/14 lists what a reader hits within
minutes, and the owner's bar is "same quality as the current engine, just
faster": a composer that says less, less gracefully, does not clear it even
with cleaner information.

Four of the five are fixed here. The fifth — 94.2% of composed views opening
with the same sentence — is not a defect: character-mode views render the
full standing state every beat BY DESIGN, because a character agent is
stateless and its view is the whole context it gets. Player views are
deltas and do not repeat. That figure needs re-measuring split by mode
before anyone "fixes" it.
"""

from __future__ import annotations

from agents.composer import DIM_FIGURE, Percept, render_view


def _presence(key, label, tier, side=None, fidelity="full"):
    return Percept(
        kind="presence", channel="sight", source_label=label,
        fidelity=fidelity,
        data={"tier": tier, "side": side, "arc": "front",
              "sight": "full" if fidelity == "full" else "shapes"},
        salience=0.35, dedupe_key="presence:" + key)


def _speech(label, body, tone="", order_key=0):
    return Percept(
        kind="speech", channel="hearing", source_label=label,
        fidelity="full",
        data={"body": body, "level": "full", "volume": "normal",
              "can_see": True, "tone": tone},
        salience=0.8, order_key=order_key, dedupe_key="speech:" + body)


def _crossing(label, direction, order_key=0):
    from agents.composer import crossing_percept
    return crossing_percept(label, label, direction, order_key=order_key)


# --- tone grammar --------------------------------------------------------

def test_an_adjectival_tone_reads_as_an_adjective():
    """'says with quietly authoritative in their voice' — the tone slot was
    built for abstract nouns and fed adjectives, constantly."""
    text = render_view([_speech("the fox woman", "Mind the rail.",
                                tone="quietly authoritative")]).text
    assert "in a quietly authoritative voice" in text
    assert "with quietly authoritative" not in text


def test_a_noun_tone_still_reads_as_a_noun():
    """The other half must not break to fix the first: 'in a warmth voice'
    would be the same bug pointed the other way."""
    text = render_view([_speech("Reya", "Sit down.", tone="warmth")]).text
    assert "with warmth in their voice" in text


def test_a_behaviour_tone_is_still_something_they_did():
    text = render_view([_speech("Reya", "Sit down.",
                                tone="a faint smirk")]).text
    assert "with a faint smirk" in text


def test_the_article_agrees():
    text = render_view([_speech("Reya", "Go.", tone="icy")]).text
    assert "in an icy voice" in text


# --- capitalization ------------------------------------------------------

def test_a_sentence_after_a_full_stop_starts_with_a_capital():
    """Live shape: '… is close by. the fox woman says: …' — the dialogue
    tag opens with a display label, which is lowercase by construction."""
    text = render_view([
        _presence("a", "the fox woman", "near"),
        _speech("the fox woman", "Mind the rail."),
    ]).text
    assert ". the fox woman" not in text
    assert "The fox woman says" in text


# --- chronology ----------------------------------------------------------

def test_someone_speaks_after_they_walk_in_not_before():
    """'X says … X comes in.' The outcome stage numbers dialogue first and
    movement last from one running counter, so a body who arrived and spoke
    rendered back to front. A crossing bounds the beat for that body; it
    does not queue inside it."""
    text = render_view([
        _speech("the fox woman", "Mind the rail.", order_key=0),
        _crossing("the fox woman", "arrived", order_key=0),
    ]).text
    assert text.index("comes in") < text.index("Mind the rail")


def test_and_leaves_after_their_last_word():
    text = render_view([
        _speech("Reya", "Goodbye.", order_key=0),
        _crossing("Reya", "left", order_key=0),
    ]).text
    assert text.index("Goodbye") < text.index("leaves")


# --- presence as one observation -----------------------------------------

def test_a_room_full_of_people_is_one_sentence():
    """Four bodies produced four sentences of identical shape. Who is here
    is one observation however many bodies it covers, and the staccato was
    the dominant texture complaint in the replay's prose sample."""
    view = render_view([
        _presence("a", "Reya", "near", "left"),
        _presence("b", "the tall man", "across"),
    ])
    assert view.text == ("Reya is close by on your left and the tall man is "
                         "across the room.")


def test_three_bodies_you_cannot_make_out_are_counted():
    """282 views rendered two or more co-present dim bodies as the same
    fixed sentence repeated — referentially indistinguishable, and reading
    as a stutter. Counted, it is both shorter and more accurate about what
    the observer can actually tell."""
    text = render_view([
        _presence(k, DIM_FIGURE, "near", fidelity="degraded")
        for k in "abc"
    ]).text
    assert text == "Three indistinct figures are close by."


def test_a_body_seen_clearly_is_never_folded_in_with_one_that_is_not():
    """The boundary a prose choice could launder. A degraded body inside a
    full body's sentence reads as clearly perceived — so fidelity splits
    the group before anything is joined, the same rule
    `observations_from_render` applies to its atoms."""
    view = render_view([
        _presence("a", "Reya", "near"),
        _presence("b", DIM_FIGURE, "across", fidelity="degraded"),
    ])
    sentences = [s for _, s in view.spans]
    assert len(sentences) == 2
    assert any("Reya" in s and DIM_FIGURE not in s for s in sentences)
    fidelities = {p.fidelity for p, _ in view.spans}
    assert fidelities == {"full", "degraded"}


def test_every_rendered_span_is_still_verbatim_in_the_view():
    """The invariant `observations_from_render` rests on: an observation's
    text is a rendered span, byte-for-byte part of the view, so the second
    representation cannot exceed the first. Fusing spans must not break
    it."""
    view = render_view([
        _presence("a", "Reya", "near", "left"),
        _presence("b", "the tall man", "across"),
        _presence("c", DIM_FIGURE, "near", fidelity="degraded"),
        _speech("Reya", "Mind the rail.", tone="dry"),
    ])
    for _p, sentence in view.spans:
        assert sentence in view.text
