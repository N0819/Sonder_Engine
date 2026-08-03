"""A guard against self-narration must not take the perceiver's eyes with it.

Live, chat 38 "The Doctor — Hinami ⎇14 ⎇17 ⎇16 ⎇23 ⎇54 ⎇58", turn idx 140.
The player ran across a shrine clearing and threw her arms around Tamamo. All
three bodies stood in `shrine_clearing`; `visual_level_between` returned
`shapes` for the Doctor to both of them; he was in no containment and no
contact, so no channel gate closed on him; and `director_resolve` wrote, in as
many words, "The Doctor remains near the genkan, watching the reunion with
bright interest."

His delivered view was:

    "Her voice rises, bright and joyful, carrying through the mist, followed
     by a soft, low, warm murmur from the embraced figure. The mountain air is
     still, the subtle spiritual pressure of the grounds pressing against his
     skin..."

No sight in it at all — and the "his" is the tell. Perception wrote that view
in the third person, `_strip_self_narration` dropped every sentence whose
subject was the perceiver, and in a third-person view those are exactly the
sentences carrying what he saw. The sentences left standing were the weather
and a voice. It reached his structured observations and his committed memory
the same way: what that mind knows about that beat is now a sound.

Two fixes, and this file pins the second. The first is upstream, where the data
first goes wrong: the perception prompt now requires each view to be written
from inside its own perceiver (`test_the_prompt_requires_the_perceivers_own
_frame`). The second is this floor — when the guard's own drop would leave a
view with no sight in it, the view stands and the refusal is reported.
"""

from __future__ import annotations

from agents.perception import _strip_self_narration

ROSTER = ["Hinami", "Tamamo", "The Doctor"]

# Reconstructed from the delivered view: the two sentences below are what the
# stored view actually contained, so the dropped pair is what the guard took.
T140_DOCTOR_VIEW = (
    "The Doctor stands near the genkan as the young woman runs across the "
    "raked gravel and throws her arms around the nine-tailed kitsune. "
    "He sees the kitsune return the embrace with one arm, her tails curling "
    "around the young woman. "
    "Her voice rises, bright and joyful, carrying through the mist, followed "
    "by a soft, low, warm murmur from the embraced figure. "
    "The mountain air is still, the spiritual pressure of the grounds "
    "pressing against his skin."
)


class TestTheLiveFailure:
    def test_the_hug_is_not_deleted_out_of_his_view(self):
        kept, dropped = _strip_self_narration(
            T140_DOCTOR_VIEW, "The Doctor", ROSTER)
        assert dropped == []
        assert kept == T140_DOCTOR_VIEW

    def test_without_the_floor_the_view_loses_exactly_its_sight(self):
        """The guard's raw behaviour, so the floor is measured against what it
        actually prevents rather than against an assumption about it."""
        from agents.perception import _SENTENCE_SPLIT, _sentence_subjects
        dropped = [
            sentence
            for sentence, subject in _sentence_subjects(
                T140_DOCTOR_VIEW, ROSTER, split=_SENTENCE_SPLIT)
            if subject == "The Doctor"
        ]
        assert len(dropped) == 2
        assert "throws her arms around" in dropped[0]
        assert "return the embrace" in dropped[1]

    def test_the_refusal_is_reported(self):
        """The whole reason this cost a database excavation: the guard warned
        into a list nothing read, and a refusal that says nothing is the same
        failure one layer up."""
        refusals = []
        _strip_self_narration(
            T140_DOCTOR_VIEW, "The Doctor", ROSTER, refusals=refusals)
        assert len(refusals) == 1
        assert "no sight" in refusals[0]
        assert "throws her arms around" in refusals[0]

    def test_a_caller_that_wants_no_refusals_still_gets_two_values(self):
        assert _strip_self_narration("", "The Doctor") == ("", [])


class TestTheFloorIsNarrow:
    """It must not become a general amnesty. Self-narration that costs the
    perceiver nothing they could see is still dropped."""

    def test_an_interior_state_is_still_dropped(self):
        view = ("Warm amber light fills the console chamber. "
                "Hinami feels her breathing slow, the terror in her eyes "
                "beginning to recede.")
        kept, dropped = _strip_self_narration(view, "Hinami", ROSTER)
        assert dropped and "terror in her eyes" not in kept

    def test_a_face_is_still_dropped_when_sight_survives_elsewhere(self):
        view = ("Elyndra's teasing smile falters as she watches. "
                "You see Hinami shrink back into the quilt.")
        kept, dropped = _strip_self_narration(view, "Elyndra", ["Hinami"])
        assert dropped and "teasing smile" not in kept
        assert "You see Hinami" in kept

    def test_a_view_with_no_sight_on_either_side_is_untouched_by_the_floor(self):
        view = ("The Doctor hears a sharp call from the mist. "
                "Rain hisses on the gravel.")
        kept, dropped = _strip_self_narration(view, "The Doctor", ROSTER)
        assert dropped == ["The Doctor hears a sharp call from the mist."]
        assert kept == "Rain hisses on the gravel."


class TestTheProseTheFloorReads:
    """The floor keys on the verbs a view uses to assert sight, and a view
    written in the third person cannot be relied on to say "you see"."""

    def test_third_person_sight_verbs_count(self):
        from agents.perception import _SIGHT_ASSERTION
        for prose in ("He sees the door open.",
                      "The Doctor watches her cross the gravel.",
                      "She notices the tails uncurl.",
                      "He catches sight of a figure at the torii.",
                      "The kitsune is visible through the mist."):
            assert _SIGHT_ASSERTION.search(prose), prose

    def test_the_other_channels_do_not(self):
        from agents.perception import _SIGHT_ASSERTION
        for prose in ("He hears a sharp call.",
                      "The scent of woodsmoke is thick and close.",
                      "Rain hisses on the gravel.",
                      "The pressure presses against his skin."):
            assert not _SIGHT_ASSERTION.search(prose), prose


def test_the_prompt_requires_the_perceivers_own_frame():
    """The floor is a floor. The reason the model wrote an outside-view at all
    is that nothing told it not to: the perception prompt carried no person
    discipline while a deterministic scrub enforced one, so the two disagreed
    and the character paid for it."""
    from prompts import get_prompt
    text = get_prompt("perception")
    assert "PERSON" in text
    lowered = text.lower()
    assert "'you'" in lowered or '"you"' in lowered
    assert "never" in lowered
