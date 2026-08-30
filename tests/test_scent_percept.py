"""`CHANNELS` declared "smell" and no builder ever emitted one.

The percept is where a graded reach and an authored smell finally meet, and
it has one job the other builders do not: a `muffled` scent must ARRIVE
muffled. `scent_level` has always returned three values and the two that are
not `none` were, downstream of it, the same value -- there was nothing for
the grade to be a grade OF.

What a half-open door actually withholds is not the smell; it is which body
the smell belongs to. So the degradation is structural rather than a mangled
string: a muffled scent is delivered UNATTRIBUTED. Attribution is a second
channel's work, and the percept carries a source label only when the observer
has that second channel.
"""

import pytest

from agents.composer import (
    CHANNELS, PERCEPT_KINDS, Percept, _STANDING_ORDER, render_episode,
    render_view, scent_percepts,
)


def _source(**over):
    source = {"key": "body:kesa", "label": "Kesa",
              "scent": "woodsmoke and cold iron", "level": "full",
              "attributed": True}
    source.update(over)
    return source


def test_the_kind_and_channel_are_declared():
    assert "scent" in PERCEPT_KINDS
    assert "smell" in CHANNELS
    assert "scent" in _STANDING_ORDER


def test_a_scent_percept_rides_the_smell_channel():
    [percept] = scent_percepts([_source()])
    assert percept.channel == "smell"
    assert percept.kind == "scent"
    assert percept.fidelity == "full"


def test_a_muffled_scent_is_marked_degraded_and_loses_its_source():
    """The firewall question this builder exists to answer. A grade the
    percept records but does not act on is not a grade."""
    [percept] = scent_percepts([_source(level="muffled")])
    assert percept.fidelity == "degraded"
    assert percept.source_label == ""
    assert "Kesa" not in repr(percept)


def test_an_unattributed_full_scent_also_carries_no_label():
    """Same room, no light: the smell arrives, the body it belongs to does
    not. Attribution is the second channel's work."""
    [percept] = scent_percepts([_source(attributed=False)])
    assert percept.fidelity == "full"
    assert percept.source_label == ""
    assert "Kesa" not in repr(percept)


def test_a_level_of_none_is_never_a_percept():
    assert scent_percepts([_source(level="none")]) == []


def test_a_source_with_nothing_to_smell_is_never_a_percept():
    assert scent_percepts([_source(scent="")]) == []
    assert scent_percepts([_source(scent="   ")]) == []


def test_the_dedupe_key_moves_when_the_grade_does():
    """A smell that goes from muffled to full is a CHANGE, and the player
    view renders standing state only when its dedupe key is new."""
    [full] = scent_percepts([_source()])
    [muffled] = scent_percepts([_source(level="muffled")])
    assert full.dedupe_key != muffled.dedupe_key


def test_two_sources_of_the_same_smell_are_one_percept_each():
    percepts = scent_percepts([
        _source(key="body:kesa", label="Kesa"),
        _source(key="entity:oven", label="", attributed=False,
                scent="hot flour"),
    ])
    assert len(percepts) == 2


@pytest.mark.parametrize("language", ["en", "ja"])
def test_every_pack_renders_all_three_shapes(language):
    """A kind no renderer branch matches renders as the empty string -- the
    silent failure `Percept.__post_init__` was written against. Both packs,
    because a pack that drops a channel drops it for the whole story."""
    percepts = scent_percepts([
        _source(),
        _source(key="entity:oven", attributed=False, scent="hot flour"),
        _source(key="entity:byre", level="muffled", scent="wet straw"),
    ])
    rendered = render_view(percepts, mode="character", language=language)
    assert rendered.text.strip()
    assert len(rendered.spans) == 3
    for _, sentence in rendered.spans:
        assert sentence.strip(), "a scent percept rendered as nothing"


@pytest.mark.parametrize("language", ["en", "ja"])
def test_a_memory_of_a_smell_is_minted_too(language):
    content, _gist, _entities = render_episode(
        scent_percepts([_source()]), language=language)
    assert content.strip()


def test_the_rendered_view_never_names_a_muffled_source():
    """The percept holds no label; this pins that no renderer puts one back."""
    rendered = render_view(scent_percepts([_source(level="muffled")]),
                           mode="character")
    assert "Kesa" not in rendered.text


def test_an_attributed_scent_uses_the_label_it_was_given():
    rendered = render_view(scent_percepts([_source(label="the hooded figure")]),
                           mode="character")
    assert "hooded figure" in rendered.text


def test_the_observations_projection_tags_the_smell_channel():
    """The narrator's per-sense manifest reads `observations_from_render`, so
    this is the whole distance between a scent percept and the smell row
    reading anything but "nothing ledgered rides this channel"."""
    from agents.composer import observations_from_render

    rendered = render_view(scent_percepts([_source()]), mode="character")
    channels = {obs["channel"] for obs in observations_from_render("p", rendered)}
    assert channels == {"smell"}


class TestOneSmellIsSaidOnce:
    """The three scent ledgers are separate facts and are right to be:
    `_substance_id` hashes the source and the source part, so arousal
    reaching a nose from two sites on one body is two records, and collapsing
    them in the ledger would lose which site. A nose does not smell the
    ledger.

    Measured live (chat 95 t59): Mirelle's view carried "Hinami smells of
    arousal. Hinami smells of arousal." verbatim, from two substance records
    on one body with identical scent, placement and grade -- in a beat where
    Hinami was inside her throat."""

    @staticmethod
    def _sources(perception):
        scene = {
            "rooms": {"room": {}},
            "positions": {"Mira": "room", "Corin": "room"},
            "entities": {},
            "substances": [
                {"substance_id": "substance:aaa", "target": "Corin",
                 "placement": "surface", "scent": "arousal"},
                {"substance_id": "substance:bbb", "target": "Corin",
                 "placement": "surface", "scent": "arousal"},
            ],
        }
        return perception._scent_sources_for(
            scene, "Mira", "room",
            [{"name": "Corin", "room": "room"}],
            {"Corin": "Corin"}, {}, body_scents={})

    def test_two_records_of_one_smell_render_once(self):
        from agents import perception
        got = self._sources(perception)
        assert len([s for s in got if s["scent"] == "arousal"]) == 1

    def test_two_different_smells_both_land(self):
        from agents import perception
        scene = {
            "rooms": {"room": {}},
            "positions": {"Mira": "room", "Corin": "room"},
            "entities": {},
            "substances": [
                {"substance_id": "substance:aaa", "target": "Corin",
                 "placement": "surface", "scent": "arousal"},
                {"substance_id": "substance:bbb", "target": "Corin",
                 "placement": "surface", "scent": "woodsmoke"},
            ],
        }
        got = perception._scent_sources_for(
            scene, "Mira", "room", [{"name": "Corin", "room": "room"}],
            {"Corin": "Corin"}, {}, body_scents={})
        assert {s["scent"] for s in got} == {"arousal", "woodsmoke"}
