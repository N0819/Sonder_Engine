"""Tells reach the page (review D1; Wood/Stanislavski: the actor's body).

`_delivered_manifest` has gated each character's physical tells and surface
demeanor per observer since Phase 4 -- channel, subtlety, familiarity,
attention -- and the payload was computed on every beat and read by nothing
(A36): 101 beats of a character with no glance, grip or catch in the voice
that was not a declared action, so deception and dramatic irony had no
channel. The delivered manifest is now minted into percepts: a `cue` event
per tell and a `demeanor` standing state, named through the observer's own
display map and scrubbed like an act surface. Only the cue text and the
demeanor cross; a tell's `because` and `betrays` never enter a percept, and
observations derive from the render, so nothing downstream can recover more
than the page says.
"""

from __future__ import annotations

from agents import composer
from agents.composer import render_view, standing_key, body_key
from agents.perception import _manifest_percepts


def _scene():
    return {"rooms": {"hall": {"name": "Hall", "adjacent": [], "light": "lit"}},
            "positions": {"Aurel Voss": "hall", "Sarah Moon": "hall",
                          "Stranger": "hall"},
            "entities": {}}


class TestThePerceptsRender:
    def test_a_cue_renders_as_an_event_in_both_languages(self):
        p = composer.cue_percept("Sarah Moon", "Sarah Moon",
                                 "her thumb works at the seam of her cuff.",
                                 order_key=3)
        assert p.kind == "cue" and p.channel == "sight"
        en = render_view([p], mode="player", language="en").text
        assert "Sarah Moon: her thumb works at the seam of her cuff." in en
        ja = render_view([p], mode="player", language="ja").text
        assert "Sarah Moon：her thumb works at the seam of her cuff。" in ja

    def test_a_tell_only_heard_is_a_hearing_percept(self):
        p = composer.cue_percept("Sarah Moon", "a voice", "a catch on the last word",
                                 order_key=1, can_see=False)
        assert p.channel == "hearing"

    def test_demeanor_is_standing_state_that_costs_one_sentence(self):
        p = composer.demeanor_percept("Sarah Moon", "Sarah Moon", "Calm, attentive.")
        assert p.order_key is None
        assert p.data["demeanor"] == "calm, attentive"
        first = render_view([p], mode="player", language="en")
        assert "Sarah Moon seems calm, attentive." in first.text
        assert p.dedupe_key in first.standing_keys
        again = render_view([p], mode="player", language="en",
                            prev_standing=frozenset(first.standing_keys))
        assert "seems calm" not in again.text
        changed = composer.demeanor_percept("Sarah Moon", "Sarah Moon", "tight, watchful")
        third = render_view([changed], mode="player", language="en",
                            prev_standing=frozenset(first.standing_keys))
        assert "Sarah Moon seems tight, watchful." in third.text


class TestOnlyTheObservableCrosses:
    def test_the_manifest_is_minted_through_the_display_map(self):
        manifest = {"Sarah Moon": {"surface_demeanor": "composed",
                                   "cues": ["a glance at the door"]},
                    "Stranger": {"surface_demeanor": "twitchy",
                                 "cues": ["fingers drumming"]}}
        display_map = {"Sarah Moon": "Sarah Moon", "Stranger": "the tall man"}
        percepts, order = _manifest_percepts(
            _scene(), manifest, "Aurel Voss", display_map, set(), [], 7)
        labels = {(p.kind, p.source_label) for p in percepts}
        assert ("demeanor", "Sarah Moon") in labels
        assert ("cue", "the tall man") in labels
        assert order == 9
        assert all("because" not in p.data and "betrays" not in p.data
                   for p in percepts)

    def test_a_body_this_observer_was_not_shown_names_nothing(self):
        manifest = {"Stranger": {"surface_demeanor": "twitchy",
                                 "cues": ["fingers drumming"]}}
        percepts, order = _manifest_percepts(
            _scene(), manifest, "Aurel Voss", {}, set(), [], 0)
        assert percepts == [] and order == 0

    def test_the_observers_own_manifest_is_not_a_percept_of_theirs(self):
        manifest = {"Aurel Voss": {"surface_demeanor": "steady", "cues": ["a nod"]}}
        percepts, _ = _manifest_percepts(
            _scene(), manifest, "Aurel Voss", {"Aurel Voss": "you"}, set(), [], 0)
        assert percepts == []

    def test_the_gate_itself_still_hands_over_only_cue_text(self):
        """`_delivered_manifest` is the firewall; this pins the shape the
        minting relies on: cues are strings, the entry has no `because`."""
        import inspect
        from agents import perception
        src = inspect.getsource(perception._delivered_manifest)
        assert 'cues.append(t.get("cue"))' in src
        assert "because" not in src


def test_the_new_kinds_are_declared_where_every_kind_must_be():
    assert "cue" in composer.PERCEPT_KINDS and "demeanor" in composer.PERCEPT_KINDS
    assert "demeanor" in composer._STANDING_ORDER
    assert "cue" not in composer._STANDING_ORDER, "a cue is this beat's event"
