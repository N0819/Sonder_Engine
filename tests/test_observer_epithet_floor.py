"""A minted epithet is not a name, and an index is not prose.

Design note 20. Three defects from the three-model playthrough of the same
village-square scene (2026-08-12), all visible only because three narrator
models failed differently against IDENTICAL perception views.

1. The player, Corin, reads "A young smith's apprentice with a borrowed
   sword", so `_unknown_actor_label` mints "the young smith's apprentice" for
   every mind that has not recognized him. The Director then took that label
   into the OBJECTIVE account -- "Bryn turns toward the young smith's
   apprentice standing at the group's edge" -- and the cast shortened it in
   their own declarations. The composer translates a canonical NAME into "you"
   for the body it belongs to; handed the epithet it minted, it had nothing to
   translate, so Corin's own view read "eyes settling on the sword at the
   apprentice's hip" and the narrator wrote him in the third person, described
   by a label that exists only because other people do not know who he is.

2. Three cast members with no authored appearance all reduce to "the person of
   unremarkable appearance", so the last-resort distinguisher fired and the
   player's own view contained, verbatim: "The person of unremarkable
   appearance is within arm's reach, the person of unremarkable appearance (2)
   is within arm's reach, and the person of unremarkable appearance (3)...".
   One narrator copied the index onto the page ("The person of unremarkable
   appearance (2) speaks in a flat, appraising voice"); another paraphrased it
   away. Neither misbehaved -- the view contained an engine device.

3. `_narration_person_counts` was called in exactly one place, on the PLAYER's
   raw input, to CHOOSE `narration_person`. Nothing ever read the prose that
   came back.
"""

from __future__ import annotations

import json
import time

from agents import composer
from agents.narration import _ordered_beat_events
from agents.perception import _composer_self_forms, _joint_stranger_labels
from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from agents.common import (
    _check_narration_person_match,
    _check_narrator_fidelity,
    _self_second_person,
    _unknown_actor_label,
    self_name_forms,
    self_reference_forms,
)

# The four bodies in the square, exactly as the playthrough had them: three
# cast cards with an empty `embodiment.visible` (which normalizes to the
# generic summary) and one persona.
PLAIN = "A person of unremarkable appearance."
CORIN = "A young smith's apprentice with a borrowed sword."
SQUARE = [("Sera", PLAIN, []), ("Bryn", PLAIN, []),
          ("Wren", PLAIN, []), ("Corin", CORIN, [])]

# All four standing together in one lit place. `observer_display_map` hands
# out an appearance descriptor only where sight is `full`, so a scene with no
# positions in it puts every body out of sight of every other and the epithets
# under test are never minted at all -- the assertions below would pass
# against a map holding nothing but the sightless fallback.
SQUARE_SCENE = {
    "rooms": {"square": {"name": "The Village Square", "light": "bright"}},
    "positions": {name: "square" for name, _a, _al in SQUARE},
}


class TestTheLabelsThemselves:
    def test_the_observed_labels_are_still_what_gets_minted(self):
        """The premise of everything below: these two exact strings."""
        assert _unknown_actor_label("Corin", CORIN) == "the young smith's apprentice"
        assert _unknown_actor_label("Sera", PLAIN) == \
            "the person of unremarkable appearance"


class TestAnIndexIsNotProse:
    def test_identical_strangers_are_distinguished_in_prose(self):
        """Defect 2. Distinct, stable, and free of the `(2)`/`(3)` device."""
        labels = composer.assign_stranger_labels(SQUARE)
        minted = [labels["Sera"], labels["Bryn"], labels["Wren"]]
        assert len(set(minted)) == 3
        for label in minted:
            assert "(" not in label and ")" not in label
            assert not any(ch.isdigit() for ch in label)
        assert set(minted) == {
            "the person of unremarkable appearance",
            "the second person of unremarkable appearance",
            "the third person of unremarkable appearance",
        }

    def test_the_distinguisher_adds_nothing_the_observer_cannot_see(self):
        """The firewall constraint on the fix: an ordinal counts bodies the
        observer is already looking at. It must not smuggle in an attribute --
        two bodies that look identical stay described identically apart from
        the count, so nothing distinguishes them but their number."""
        labels = composer.assign_stranger_labels(SQUARE)
        for name in ("Sera", "Bryn", "Wren"):
            tail = labels[name].split("person of ", 1)[-1]
            assert tail == "unremarkable appearance"

    def test_the_same_stranger_is_the_same_stranger_across_a_beat(self):
        """Stability within a beat: the assignment is a pure function of the
        body list, so every sentence of one view refers alike."""
        first = composer.assign_stranger_labels(SQUARE)
        second = composer.assign_stranger_labels(list(SQUARE))
        assert first == second

    def test_a_distinguishing_appearance_still_wins_over_an_ordinal(self):
        """Unchanged, and the reason ordinals are a LAST resort: when the
        appearances can tell two bodies apart, they do."""
        labels = composer.assign_stranger_labels([
            ("Hinami", "a fox woman with six tails and amber eyes", []),
            ("Kuzunoha", "a fox woman with a single silver tail", []),
        ])
        assert labels["Hinami"] != labels["Kuzunoha"]
        assert "second" not in " ".join(labels.values())

    def test_a_crowd_past_the_ordinal_words_still_renders_as_prose(self):
        labels = composer.assign_stranger_labels(
            [(f"Body{i}", PLAIN, []) for i in range(14)])
        assert len(set(labels.values())) == 14
        assert all("(" not in label for label in labels.values())


class TestTheEpithetIsSelfReference:
    def _forms(self, name=None, avoid=None):
        labels = composer.assign_stranger_labels(SQUARE)
        display = {k: v for k, v in labels.items() if k != "Corin"}
        return self_name_forms("Corin", ["Corin"]) + self_reference_forms(
            "Corin", CORIN, [], labels=[labels["Corin"]],
            avoid=(display.values() if avoid is None else avoid))

    def test_the_minted_label_reads_as_you_in_its_own_view(self):
        """Defect 1, the Director's sentence, delivered to Corin."""
        out = _self_second_person(
            "Bryn turns toward the young smith's apprentice standing at the "
            "group's edge", self._forms())
        assert "apprentice" not in out
        assert out == "Bryn turns toward you standing at the group's edge"

    def test_the_shortened_epithet_reads_as_your(self):
        """The form that actually reached the player's view: prose shortens a
        long descriptor on second mention."""
        out = _self_second_person(
            "shifts weight to one side, eyes settling on the sword at the "
            "apprentice's hip", self._forms())
        assert out == ("shifts weight to one side, eyes settling on the sword "
                       "at your hip")

    def test_the_canonical_name_still_reads_as_you(self):
        """The floor that already existed is not traded for the new one."""
        assert _self_second_person("Corin goes still", self._forms()) == \
            "You go still"

    def test_a_generic_head_noun_is_never_shortened(self):
        """"the person of unremarkable appearance" must not yield "the
        person": that is the word every stranger label is built from, and
        claiming it as self-reference would claim any passing body."""
        forms = self_reference_forms("Sera", PLAIN, [])
        assert "the person" not in forms
        assert "the appearance" not in forms

    def test_a_descriptor_two_bodies_share_is_never_claimed(self):
        """The collision guard. Sera's own label is also Bryn's and Wren's
        before the ordinal falls, so nothing in Sera's view may be rewritten
        into "you" on the strength of it -- under-matching costs a clumsy
        sentence, over-matching invents an act she did not commit."""
        assert self_reference_forms(
            "Sera", PLAIN, [],
            avoid=["the person of unremarkable appearance"]) == []
        # The same rule at the head-noun level: another apprentice in the room
        # withdraws the short form, keeping the unambiguous full one.
        forms = self_reference_forms(
            "Corin", CORIN, [],
            avoid=["the older smith's apprentice"])
        assert "the apprentice" not in forms
        assert "the young smith's apprentice" in forms

    def test_an_indefinite_introduction_is_left_alone(self):
        """"a young smith's apprentice" is how prose introduces a body nobody
        has met. Matching it would reach for referents this cannot check."""
        src = "a young smith's apprentice waits by the well"
        assert _self_second_person(src, self._forms()) == src

    def test_a_spoken_epithet_survives_verbatim(self):
        """Dialogue fidelity outranks person: a label said ALOUD is sensory
        signal, and `_self_second_person` never edits inside quotes."""
        src = 'Bryn says: "That sword isn\'t yours, apprentice."'
        assert "apprentice" in _self_second_person(src, self._forms())


class TestTheDeliverySites:
    """The floor has to sit where engine prose is HANDED to the mind it is
    about, which is two places: the composed view, and the ordered event
    record the narrator renders the player-facing slice from."""

    def _bodies(self):
        return [{"name": n, "appearance": a, "aliases": al}
                for n, a, al in SQUARE]

    def test_perception_hands_a_mind_its_own_epithets(self):
        bodies = self._bodies()
        joint = _joint_stranger_labels(bodies)
        display = composer.observer_display_map(
            SQUARE_SCENE, "Corin",
            [b for b in bodies if b["name"] != "Corin"], {})
        forms = _composer_self_forms(
            "Corin", ["Corin"],
            {"appearance": CORIN, "aliases": []}, joint, display)
        assert "Corin" in forms
        assert "the young smith's apprentice" in forms
        assert "the apprentice" in forms
        # ...and never a descriptor this observer is using for someone else.
        assert not set(forms) & set(display.values())

    def test_a_shared_descriptor_is_not_claimed_as_self(self):
        """Sera's own label is what she is already calling Bryn and Wren, so
        nothing in her view may be rewritten into "you" on its strength."""
        bodies = self._bodies()
        joint = _joint_stranger_labels(bodies)
        display = composer.observer_display_map(
            SQUARE_SCENE, "Sera",
            [b for b in bodies if b["name"] != "Sera"], {})
        forms = _composer_self_forms(
            "Sera", ["Sera"], {"appearance": PLAIN, "aliases": []},
            joint, display)
        assert forms == ["Sera"]

    def test_the_narrator_slice_carries_the_same_floor(self, temp_db):
        """event_order is a SECOND delivery of this beat's prose to the
        player: the cast's own observable surfaces, naming the player the way
        those minds refer to them. Observed live in the narrator payload."""
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Square", "", time.time()))
        temp_db.wset(chat_id, "scene", {
            "rooms": {"well": {"name": "The Village Well"}},
            "positions": {"Sera": "well", "Corin": "well"}})
        cast = [{"id": 1, "sheet": json.dumps(default_character_data("Sera")),
                 "cstate": "{}", "status": "active"}]
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Square", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=1,
                          player_input="I listen", created=time.time()),
            cast=cast, input="I listen")
        ctx.director_interpret = {"sequence": []}
        ctx.interaction_loop = {"rounds": [
            {"round": 0, "speaker_id": 1, "speaker": "Sera",
             "result": {"sequence": [{
                 "type": "action", "attempt": "watch the sword",
                 "observable": "shifts weight to one side, eyes settling on "
                               "the sword at the apprentice's hip"}]}}]}
        scene = temp_db.wget(chat_id, "scene", {})
        forms = self_name_forms("Corin", ["Corin"]) + self_reference_forms(
            "Corin", CORIN, [], avoid=["the person of unremarkable appearance"])
        events = _ordered_beat_events(
            ctx, "Corin", "", set(),
            {"Sera": {"appearance": PLAIN, "aliases": []}},
            scene=scene, p_room="well", player_forms=forms)
        assert len(events) == 1
        assert events[0]["action"] == (
            "shifts weight to one side, eyes settling on the sword at your hip")


class TestNarrationPersonIsVerified:
    def test_prose_in_the_wrong_person_is_reported(self):
        """Defect 3. Observed shape, from the stored corpus: prose reading
        "Your words land in the corridor's flat hum" on a turn whose person
        resolved to `first`."""
        warnings = _check_narration_person_match(
            "Your words land in the corridor's flat hum. Your declaration "
            "cuts through it, and your hand stays where it is.",
            "first", "Alex")
        assert warnings and warnings[0].startswith("Narrator prose reads as")
        assert "second person" in warnings[0] and "'first'" in warnings[0]

    def test_compliant_prose_is_silent(self):
        """The mix2 draft, which complied: `narration_person` was 'first' and
        the narrator wrote first person."""
        assert _check_narration_person_match(
            "I go still, turning my head a fraction toward the voices pressed "
            "close in the crush.", "first", "Corin") == []

    def test_one_stray_token_is_not_a_voice_change(self):
        """Same hysteresis as `_resolve_narration_person`: the dominant person
        must LEAD the declared one by two."""
        assert _check_narration_person_match(
            "I cross the square. Your name is called somewhere behind me.",
            "first", "Corin") == []

    def test_other_characters_in_third_person_are_not_evidence(self):
        """The false positive this check is narrowed against: every other body
        on the page is legitimately "he"/"she"/"they", and the player's own
        pronouns are routinely the same words. Third-person evidence therefore
        comes from the player's NAME only."""
        assert _check_narration_person_match(
            "She turns from the well. She watches the sword. She says nothing, "
            "and she does not move. You wait her out.", "second", "Corin") == []

    def test_it_rides_the_fidelity_channel(self):
        warnings = _check_narrator_fidelity(
            {"prose": "You cross your arms and wait. Your jaw sets, and your "
                      "weight plants."},
            view="", narration_person="first", player_name="Alex")
        assert any(w.startswith("Narrator prose reads as") for w in warnings)

    def test_it_would_not_have_caught_the_epithet(self):
        """Stated as a test because it is the limit that matters: the offending
        phrase was an epithet, not a name or a pronoun, so it is invisible to
        every person detector. This is a backstop for model non-compliance, not
        a fix for bad input."""
        assert _check_narration_person_match(
            "The nearest one turns toward the young smith's apprentice, gaze "
            "dropping to the sword at his hip.", "first", "Corin") == []
