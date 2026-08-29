"""A mind is present at its own conduct.

`deterministic_micro_perception` builds one view per OBSERVER and skips the
actor, which is right for that function: every gate it applies -- recognition,
spatial relation, earshot, concealment, the observer's senses -- answers "did
this reach someone else". None of them is a question about the actor.

The consequence was that a character granted a second micro-round in the same
beat had no record of the first. Nothing has committed yet at that point, so
the within-turn views are the only ledger there is, and the actor was
deliberately excluded from their own. Measured 2026-08-28 in chat 98: asked
for parameters, Data asked for them again inside the same beat; a captain
restated his own granted permission as a second quoted line. Both read as a
character who does not listen. Both were a character who had not been told
what they themselves had just said.
"""
from __future__ import annotations

from agents.loops import self_micro_view


def _speech(quote, **extra):
    return dict({"type": "speech", "quote": quote}, **extra)


def test_a_mind_carries_its_own_words_verbatim():
    view = self_micro_view({"sequence": [_speech("State your parameters.")]})
    assert any("State your parameters." in line for line in view)


def test_a_mind_carries_its_own_deed_by_the_observable_surface():
    view = self_micro_view({"sequence": [
        {"type": "action", "observable": "sets the padd on the console",
         "attempt": "buy time before answering"}]})
    joined = " ".join(view)
    assert "sets the padd on the console" in joined
    # The DEED, never the purpose behind it: intent reaches the next step
    # through psychology, not through a view.
    assert "buy time" not in joined


def test_a_mental_beat_is_imperceptible_to_its_own_owner_too():
    """`observable: ""` is imperceptible to everybody, and a mind's own
    interiority reaches its next step through psychology rather than by being
    replayed to it as something it watched itself do."""
    assert self_micro_view({"sequence": [
        {"type": "action", "observable": "", "attempt": "reconsiders"}]}) == []


def test_a_muffled_rendering_is_for_listeners_not_for_the_speaker():
    """Distance and volume garble what OTHERS receive. A speaker does not
    hear their own line through the room."""
    view = self_micro_view({"sequence": [
        _speech("Belay that.", volume="whisper")]})
    assert any("Belay that." in line for line in view)
    assert not any("..." in line for line in view)


def test_a_concealed_line_is_still_the_speakers_own_line():
    """`conceal_from` is an exclusion aimed at other minds. Concealing a line
    from somebody does not conceal it from the person who said it."""
    view = self_micro_view({"sequence": [
        _speech("Meet me after.", visibility="concealed",
                conceal_from=["Someone Else"])]})
    assert any("Meet me after." in line for line in view)


def test_nothing_said_and_nothing_done_yields_nothing():
    assert self_micro_view({}) == []
    assert self_micro_view({"sequence": []}) == []
    assert self_micro_view(None) == []


# ---------------------------------------------------------------------------
# the rehydrated view is the live one, not an approximation of it
# ---------------------------------------------------------------------------

class _Ctx:
    """The two attributes `rehydrate_loop_views` reads."""

    def __init__(self, views):
        self.perception_act = {"views": views}
        self._extra = {}


def test_a_rerun_rebuilds_the_speakers_own_conduct_into_their_view():
    """`rehydrate_loop_views` reconstructs the side channel a resumed or
    rerolled turn never carried. It rebuilt every OBSERVER's additions and
    dropped the speaker's own, so a rerun handed a second-round speaker a
    different view than the uninterrupted run did -- 'the property
    storage.active_content calls the worst kind of difference'.
    """
    from agents.loops import rehydrate_loop_views

    ctx = _Ctx({"7": "Onset.", "9": "Onset."})
    rehydrate_loop_views(ctx, "interaction_loop", {"rounds": [
        {"round": 0, "speaker_id": 7,
         "delivered_views": {"9": ["Seven says something."]},
         "self_view": ['You said: "State your parameters."']},
    ]})
    views = ctx._extra["interaction_views"]
    assert 'State your parameters.' in views[7], views[7]
    assert "Seven says something." in views[9]
    # ...and the speaker did not receive the observer's rendering of them
    assert "Seven says something." not in views[7]


def test_a_round_recorded_before_self_views_existed_still_rehydrates():
    """Rounds already on disk carry no `self_view`. They must rebuild to what
    they always rebuilt to rather than raising."""
    from agents.loops import rehydrate_loop_views

    ctx = _Ctx({"7": "Onset."})
    rehydrate_loop_views(ctx, "interaction_loop", {"rounds": [
        {"round": 0, "speaker_id": 7, "delivered_views": {}},
    ]})
    assert ctx._extra["interaction_views"][7] == "Onset."
