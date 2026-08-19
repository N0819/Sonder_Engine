"""Quality of the structured observations perception derives from its views.

The leak properties of this projection are covered by
tests/test_perception_intent_leak.py; this file covers whether the projection
says anything TRUE.

WHAT THIS FILE USED TO TEST, AND WHY IT MOVED. The first derivation
(`perception._observations_from_clean_views`) read finished prose back with
substring cues: 'paint' matched 'pain', one quoted line relabelled a page of
body sensation as hearing, and 'something' pinned fidelity to ambiguous on any
view long enough to contain it. Those were real defects and they were fixed --
and then the whole prose-reading derivation was retired. `composer` builds a
typed IR, renders it, and `observations_from_render` projects the atoms back
off the rendered spans, so channel, suddenness, intensity and self-direction
are KNOWN from the percept rather than guessed from the wording.

Two of the original cases therefore have no successor and are gone rather than
translated: a cue matching inside a longer word, and a lone hedge word
deciding fidelity, are both defects of a classifier that no longer exists. The
other eight properties are the same properties and are asserted here against
the live derivation. The invariant that carries across both eras, and the
reason the projection is safe at all, is the last test in the file: an atom's
text is a span of the rendered view, so the second representation cannot
exceed the first.
"""

from __future__ import annotations

from agents import composer


def _render(percepts):
    return composer.render_view(percepts, mode="character")


def _atoms(percepts, pid="7"):
    return composer.observations_from_render(pid, _render(percepts))


def _room(note="The lantern light gutters against the far wall."):
    return composer.environment_percept("hall", "Hall", note, "lit")


def _voice(body="hold still", *, volume="normal", target="", order_key=0):
    return composer.speech_percept(
        {"speaker": "Mara", "exact_quote": body, "volume": volume,
         "intended_target": target},
        {"same_room": True}, "7", display="Mara", can_see=True,
        order_key=order_key)


def _smell(desc="The scent of woodsmoke thickens."):
    return composer.ambient_percepts([{"desc": desc, "channel": "smell"}],
                                     "hall")[0]


def _body(posture="hunched", activity="breathing shallowly"):
    return composer.body_state_percept(
        {"posture": posture, "activity": activity})


def test_a_view_decomposes_into_per_channel_atoms():
    atoms = _atoms([_room(), _smell(), _voice(order_key=1)])
    assert [a["channel"] for a in atoms] == ["sight", "smell", "hearing"]
    assert [a["observation_id"] for a in atoms] == [
        "current:7:0", "current:7:1", "current:7:2"]


def test_atoms_are_capped_but_never_collapse_to_one():
    percepts = [_voice(f"line number {i}", order_key=i) for i in range(40)]
    atoms = _atoms(percepts)
    assert 1 < len(atoms) <= 8


def test_one_quoted_line_no_longer_relabels_a_whole_view():
    """A body-sensation view carrying a single line of dialogue keeps its own
    channel for the body sentences. Under the IR this is structural rather
    than earned: the channel rides the percept."""
    atoms = _atoms([
        _body(),
        composer.contact_percepts(
            [({"actor": "Mara", "actor_part": "palm", "target": "you",
               "target_part": "sternum", "manner": "press"},
              "Your sternum registers Mara's palm against it.")])[0],
        _voice(order_key=1),
    ])
    channels = [a["channel"] for a in atoms]
    assert "interoception" in channels
    assert "touch" in channels
    assert "hearing" in channels


def test_fidelity_follows_the_admitted_percept_not_the_wording():
    """A hedge word in a fully-admitted line is prose, not a perception
    verdict. The old derivation read 'something' out of the text and downgraded
    the atom; fidelity now comes from what the channel actually delivered."""
    atoms = _atoms([_voice("something heavy just landed", order_key=1)])
    hearing = [a for a in atoms if a["channel"] == "hearing"]
    assert hearing and hearing[0].get("fidelity", "rendered") == "rendered"
    assert hearing[0].get("ambiguity", 0.15) < 0.5


def test_a_degraded_channel_still_reads_ambiguous():
    """The property the hedge-word test was reaching for, asserted where it is
    actually true: a muffled line arrives at `fragment` fidelity and the atom
    says so."""
    muffled = composer.speech_percept(
        {"speaker": "Mara", "exact_quote": "you cannot make this out",
         "volume": "normal"},
        {"same_room": True, "source_enclosed": True}, "7",
        display="a voice", can_see=False, order_key=1)
    assert muffled is not None and muffled.fidelity == "fragment"
    atoms = _atoms([muffled])
    assert atoms[0]["fidelity"] == "ambiguous"
    assert atoms[0]["ambiguity"] >= 0.5


def test_contact_with_the_perceiver_is_directed_at_self():
    atoms = _atoms(composer.contact_percepts(
        [({"actor": "Mara", "actor_part": "hand", "target": "you",
           "target_part": "shoulder", "manner": "grip"},
          "Your shoulder registers Mara's hand closing on it.")]))
    assert atoms[0]["directed_at_self"] is True


def test_a_line_addressed_to_the_perceiver_is_directed_at_self():
    atoms = _atoms([_voice("hold still", target="7", order_key=1)])
    assert atoms[0]["directed_at_self"] is True


def test_own_body_state_is_directed_at_self_without_a_cue():
    """Interoception is self-directed by definition -- no cue is consulted,
    which is what the `_SELF_DIRECTED` table used to get wrong for any
    construction that did not put the agent first."""
    atoms = _atoms([_body()])
    assert atoms[0]["channel"] == "interoception"
    assert atoms[0]["directed_at_self"] is True


def test_an_event_across_the_room_is_not_directed_at_self():
    atoms = _atoms([_room(), _voice("get the crate", order_key=1)])
    # `directed_at_self: False` is the resting default and is compacted out
    # of the payload entirely (`OBSERVATION_DEFAULTS`); absent means False.
    assert all(a.get("directed_at_self", False) is False for a in atoms)


def test_an_empty_view_yields_no_atoms():
    assert composer.observations_from_render("7", _render([])) == []
    assert composer.observations_from_render("7", _render(None)) == []


def test_every_atoms_text_is_a_span_of_the_rendered_view():
    """The invariant that survived the move, and the reason the projection is
    safe: the atoms are re-derived from the rendered view, so the second
    representation cannot widen the information budget the first was gated
    to."""
    percepts = [_room(), _smell(), _body(), _voice(order_key=1)]
    rendered = _render(percepts)
    atoms = composer.observations_from_render("7", rendered)
    # Merging only ever joins ADJACENT spans, and the view is those same spans
    # joined by a space -- so every atom's text is a contiguous substring of
    # the view, byte for byte.
    assert atoms
    for atom in atoms:
        assert atom["observed"]["text"] in rendered.text
    assert "".join(a["observed"]["text"] for a in atoms).replace(" ", "") \
        == rendered.text.replace(" ", "")
