"""How speech is FORMED when the speaker's mouth is engaged -- three layers.

Live (chat 69 "Horny Story. \u234749"): across 24 turns a character spoke at
`normal` volume while the standing contact ledger had her mouth engaged; and
after the first (notice-only) fix, turns 74-75 exposed the case it missed --
her tongue extended mid-lick on an external surface, delivering clean full
sentences ("Every inch of you, darling."). You cannot articulate cleanly with
your tongue on someone.

The layers, earliest first, per the repo rule (fix where the data first
becomes wrong):

  1. SELF-KNOWLEDGE. The line was composed by a mind that believed its mouth
     was free: her private payload never said otherwise. A person knows
     their tongue is on someone -- it is their own body, so the recognition
     gate owes nothing here -- and a mind that knows can CHOOSE: lift, finish
     first, or speak anyway and mean the slur. (`self.speaking_now`)
  2. FORMATION. `articulation` is stamped on each dialogue entry
     deterministically from the post-op ledger -- the sibling of `volume`, a
     fact about how the sound was MADE -- and rendered identically to every
     listener. The words stay verbatim; fidelity scrubs keep matching them.
     This is the backstop for a model that ignores (1).
  3. NOT HEARING. hear_level models transmission (walls, doors, distance),
     which is per-listener and path-dependent; malformation is identical for
     all listeners, and someone close hears the slur BETTER, not less of it.
     Modelling this as hearing would hand a companion beside her wall-like
     fragments -- exactly wrong -- so no hearing change exists here.

The stale-ledger risk stays priced in: in the SAME story the same speaker
held five beats of ordinary conversation while a stale kiss record sat on
her LIPS, so the speaker-side surface rule is tongue-only, and hard notices
go out only for the stifled kind.
"""

from __future__ import annotations

from agents.common import _inject_dialogue
from agents.director import _stamp_dialogue_articulation
from llm.prompts import DEFAULT_PROMPTS
from llm.schemas import DialogueLogEntry
from world.spatial import speech_articulation_impediment


def _scene(contacts):
    return {
        "rooms": {"room": {"name": "Room", "adjacent": []}},
        "positions": {"Reya": "room", "Bram": "room"},
        "entities": {},
        "contacts": contacts,
    }


def _line(speaker="Reya", volume="normal"):
    return {"speaker": speaker, "exact_quote": '"Hold still."',
            "volume": volume}


TONGUE_LICK = [{
    # The turn 74/75 shape: her own tongue on an external surface.
    "actor": "Reya", "actor_part": "tongue", "target": "Bram",
    "target_part": "shoulder", "target_interior": "",
    "manner": "lick", "relation": "surface", "motion": "moving"}]

MOUTH_FILLED = [{
    "actor": "Bram", "actor_part": "finger", "target": "Reya",
    "target_part": "", "target_interior": "mouth",
    "manner": "rest", "relation": "interior", "motion": "settled"}]


class TestTheImpediment:

    def test_something_inside_the_speakers_mouth_stifles(self):
        kind, reason = speech_articulation_impediment(
            _scene(MOUTH_FILLED), "Reya")

        assert kind == "stifled"
        assert "inside Reya's mouth" in reason

    def test_the_speakers_own_tongue_interior_stifles(self):
        scene = _scene([{
            "actor": "Reya", "actor_part": "tongue", "target": "Bram",
            "target_part": "ear", "target_interior": "",
            "manner": "press", "relation": "interior", "motion": "moving"}])

        assert speech_articulation_impediment(scene, "Reya")[0] == "stifled"

    def test_a_body_pressed_against_the_speakers_lips_stifles(self):
        scene = _scene([{
            "actor": "Bram", "actor_part": "palm", "target": "Reya",
            "target_part": "lips", "target_interior": "",
            "manner": "press", "relation": "surface", "motion": "settled"}])

        assert speech_articulation_impediment(scene, "Reya")[0] == "stifled"

    def test_a_tongue_on_an_external_surface_slurs(self):
        """The turn 74/75 gap: none of the original three occasions covered
        a tongue extended onto a SURFACE, so 'Every inch of you, darling.'
        arrived perfectly articulate mid-lick."""
        kind, reason = speech_articulation_impediment(
            _scene(TONGUE_LICK), "Reya")

        assert kind == "slurred"
        assert "tongue is against" in reason

    def test_lips_resting_on_someone_do_not_impede(self):
        """Tongue-only on the speaker's own surface side: lips on a scalp
        accompanied five beats of ordinary conversation in the same story,
        and a broader rule would have slurred the legitimate half."""
        scene = _scene([{
            "actor": "Reya", "actor_part": "lips", "target": "Bram",
            "target_part": "head", "target_interior": "",
            "manner": "kiss", "relation": "surface", "motion": "settled"}])

        assert speech_articulation_impediment(scene, "Reya") == ("", "")

    def test_stifled_outranks_slurred_whatever_the_ledger_order(self):
        scene = _scene(TONGUE_LICK + MOUTH_FILLED)

        assert speech_articulation_impediment(scene, "Reya")[0] == "stifled"

    def test_an_uninvolved_speaker_is_free(self):
        assert speech_articulation_impediment(
            _scene(MOUTH_FILLED), "Bram") == ("", "")


class TestTheStamp:

    def test_a_slurred_line_is_stamped_and_not_scolded(self):
        line = _line()
        notices = _stamp_dialogue_articulation(
            _scene(TONGUE_LICK), {}, [line])

        assert line["articulation"] == "slurred"
        assert notices == []

    def test_a_stifled_line_is_stamped_and_noticed(self):
        line = _line()
        notices = _stamp_dialogue_articulation(
            _scene(MOUTH_FILLED), {}, [line])

        assert line["articulation"] == "stifled"
        assert len(notices) == 1
        assert "contact_ops" in notices[0]

    def test_the_stamp_clears_a_model_invented_value(self):
        """The stamp is authoritative in both directions: a value the model
        wrote without ledger support does not survive reconciliation."""
        line = dict(_line(), articulation="slurred")
        _stamp_dialogue_articulation(_scene([]), {}, [line])

        assert line["articulation"] == ""

    def test_a_beat_that_ends_the_contact_first_is_clean(self):
        line = _line()
        sd = {"contact_ops": [
            {"op": "remove", "actor": "Bram", "target": "Reya"}]}
        notices = _stamp_dialogue_articulation(
            _scene(MOUTH_FILLED), sd, [line])

        assert line["articulation"] == ""
        assert notices == []

    def test_the_schema_keeps_a_stamped_value_through_revalidation(self):
        """The field exists in the schema precisely so a re-validation of a
        stamped log cannot silently strip it -- an empty field fails
        silently."""
        entry = DialogueLogEntry(speaker="Reya", exact_quote='"Hm."',
                                 articulation="slurred")
        assert entry.dict()["articulation"] == "slurred"
        junk = DialogueLogEntry(speaker="Reya", exact_quote='"Hm."',
                                articulation="operatic")
        assert junk.dict()["articulation"] == ""


class TestSelfKnowledge:
    """The character's own payload carries the fact; layer 1 is primary.

    The mind composing the turn-74 line was never told her tongue was out --
    her view said the contact existed (tactile floor) but nothing stated its
    consequence for speech, so the model had no reason not to write a clean
    sentence. What a person notices, phrased without the other party's name:
    it is a fact about this body's own mouth.
    """

    def test_the_payload_fact_is_deterministic_from_the_ledger(self):
        # The payload builder consumes the same predicate; assert the seam's
        # inputs/outputs rather than rebuilding a full character context.
        kind, _ = speech_articulation_impediment(_scene(TONGUE_LICK), "Reya")
        assert kind == "slurred"

    def test_the_payload_block_exists_in_the_builder(self):
        import inspect
        import agents.character as character
        src = inspect.getsource(character)
        assert '"speaking_now"' in src
        assert "speech_articulation_impediment" in src

    def test_the_character_contract_names_the_occasion(self):
        character = DEFAULT_PROMPTS["character"]
        assert "SPEAKING WITH YOUR MOUTH ENGAGED" in character
        assert "lift your head" in character


class TestTheRendering:

    def test_a_slurred_line_reads_slurred_to_a_watcher(self):
        view = _inject_dialogue(
            "", "Reya", '"Hold still."', "full", "normal", True,
            articulation="slurred")

        assert "the words slurred around an occupied tongue" in view
        assert '"Hold still."' in view  # verbatim: formation, not rewording

    def test_a_slurred_line_reads_slurred_unseen_too(self):
        """Formation, not transmission: the listener who cannot see the
        speaker hears the same slur, not a wall's muffling."""
        view = _inject_dialogue(
            "", "Reya", '"Hold still."', "full", "normal", False,
            articulation="slurred")

        assert "the words slurred around an occupied tongue" in view

    def test_a_stifled_line_reads_barely_shaped(self):
        view = _inject_dialogue(
            "", "Reya", '"Hold still."', "full", "normal", True,
            articulation="stifled")

        assert "stifled and barely shaped" in view

    def test_a_clean_line_renders_exactly_as_before(self):
        view = _inject_dialogue(
            "", "Reya", '"Hold still."', "full", "normal", True)

        assert view == 'Reya says: "Hold still."'

    def test_a_fragment_is_transmission_and_ignores_articulation(self):
        """A wall's muffling already has its own rendering; articulation
        never doubles it -- the two degradations are different facts."""
        view = _inject_dialogue(
            "", "Reya", '"Hold still and wait."', "fragment", "normal",
            False, articulation="slurred")

        assert view.startswith("A muffled voice:")
        assert "occupied tongue" not in view


class TestThePromptNamesTheOccasion:

    def test_the_dialogue_contract_names_the_filled_mouth(self):
        resolve = DEFAULT_PROMPTS["director_resolve_lean"]
        assert "A FILLED MOUTH SPEAKS LAST OR BARELY" in resolve
        assert "end that contact in contact_ops" in resolve

    def test_the_dialogue_contract_names_the_engaged_tongue(self):
        resolve = DEFAULT_PROMPTS["director_resolve_lean"]
        assert "A TONGUE MID-ACT SLURS" in resolve
