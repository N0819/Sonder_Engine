"""A mouth the ledger says is sealed cannot deliver ordinary dialogue.

Live (chat 69 "Horny Story. ⎇49"): across 24 turns a character spoke at
`normal` volume while the standing contact ledger had her mouth engaged, and
on the worst beats she delivered full sentences with her tongue mid-act and
another body pressed against her lips. Nothing deterministic ever compared
`dialogue_log` against `contacts`.

The fix is advisory on purpose. In the SAME story, the same speaker held five
beats of legitimate conversation while a stale kiss record sat on her lips
(the ledger's own defect, aged out later), so a hard gate -- muffling or
dropping the line on the ledger's word -- would have garbled the legitimate
half while fixing the impossible one. The engine names the contradiction to
the Director (`tell_director`), the same channel displacement notices use,
and the prompt names the two honest ways out: end the contact first, or keep
the line to a muffled word or two.
"""

from __future__ import annotations

from agents.director import _sealed_mouth_speech_notices
from prompts import DEFAULT_PROMPTS
from spatial import speech_obstructed_by_contact


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


class TestThePredicate:

    def test_something_inside_the_speakers_mouth_blocks(self):
        scene = _scene([{
            "actor": "Bram", "actor_part": "finger", "target": "Reya",
            "target_part": "", "target_interior": "mouth",
            "manner": "rest", "relation": "interior", "motion": "settled"}])

        assert "inside Reya's mouth" in \
            speech_obstructed_by_contact(scene, "Reya")

    def test_the_speakers_own_tongue_mid_act_blocks(self):
        scene = _scene([{
            "actor": "Reya", "actor_part": "tongue", "target": "Bram",
            "target_part": "ear", "target_interior": "",
            "manner": "press", "relation": "interior", "motion": "moving"}])

        assert speech_obstructed_by_contact(scene, "Reya")

    def test_a_body_pressed_against_the_speakers_lips_blocks(self):
        # The live shape: another body's surface sealed over the speaker's
        # mouth from outside.
        scene = _scene([{
            "actor": "Bram", "actor_part": "palm", "target": "Reya",
            "target_part": "lips", "target_interior": "",
            "manner": "press", "relation": "surface", "motion": "settled"}])

        assert "pressed against Reya's lips" in \
            speech_obstructed_by_contact(scene, "Reya")

    def test_lips_resting_on_someone_do_not_block(self):
        """The direction is the rule: the speaker's own lips against a scalp
        (the stale-kiss residue, five beats of legitimate conversation) leave
        the mouth free to turn and speak. Flagging it would have scolded the
        half of the story that was right."""
        scene = _scene([{
            "actor": "Reya", "actor_part": "lips", "target": "Bram",
            "target_part": "head", "target_interior": "",
            "manner": "kiss", "relation": "surface", "motion": "settled"}])

        assert speech_obstructed_by_contact(scene, "Reya") == ""

    def test_an_uninvolved_speaker_is_free(self):
        scene = _scene([{
            "actor": "Bram", "actor_part": "finger", "target": "Reya",
            "target_part": "", "target_interior": "mouth",
            "manner": "rest", "relation": "interior", "motion": "settled"}])

        assert speech_obstructed_by_contact(scene, "Bram") == ""


class TestTheNotices:

    BLOCKED = [{
        "actor": "Bram", "actor_part": "finger", "target": "Reya",
        "target_part": "", "target_interior": "mouth",
        "manner": "rest", "relation": "interior", "motion": "settled"}]

    def test_a_normal_line_through_a_sealed_mouth_is_noticed(self):
        notices = _sealed_mouth_speech_notices(
            _scene(self.BLOCKED), {}, [_line()])

        assert len(notices) == 1
        assert "contact_ops" in notices[0]

    def test_a_mutter_passes(self):
        """A muffled word or two is exactly what a blocked mouth can do."""
        assert _sealed_mouth_speech_notices(
            _scene(self.BLOCKED), {}, [_line(volume="mutter")]) == []

    def test_one_notice_per_speaker_not_per_line(self):
        notices = _sealed_mouth_speech_notices(
            _scene(self.BLOCKED), {}, [_line(), _line()])

        assert len(notices) == 1

    def test_a_beat_that_ends_the_contact_first_is_not_scolded(self):
        """The check runs against the POST-op ledger: ending the contact in
        the same beat as the line is one of the two honest ways out."""
        sd = {"contact_ops": [
            {"op": "remove", "actor": "Bram", "target": "Reya"}]}
        assert _sealed_mouth_speech_notices(
            _scene(self.BLOCKED), sd, [_line()]) == []


class TestThePromptNamesTheOccasion:

    def test_the_dialogue_contract_names_the_filled_mouth(self):
        resolve = DEFAULT_PROMPTS["director_resolve"]
        assert "A FILLED MOUTH SPEAKS LAST OR BARELY" in resolve
        assert "end that contact in contact_ops" in resolve

    def test_the_contact_contract_names_the_envelopment_direction(self):
        resolve = DEFAULT_PROMPTS["director_resolve"]
        assert "AN ENVELOPMENT IS RECORDED FROM THE ENCLOSED SIDE" in resolve
