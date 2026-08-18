"""What a presence IS, asked once where a model is already looking.

The engine had two lists trying to read animacy off a `kind` string a model
chose in passing: `_INERT_ENTITY_KINDS` at 50 entries and
`_ANIMATE_ENTITY_KINDS` at 35, and still no way to separate a suppression
device from a "dalek war machine" -- both live kinds. That is the enumeration
treadmill `AGENTS.md` warns about: the list never finishes, because the space
of nouns a story can invent does not.

`blurb_mint` already visits every newly tracked presence, batched per room,
with the place, the Director's own description and the story's genre in front
of it. It was already asking a model about this exact thing -- and asking the
wrong question. Its prompt opened "You give brief, concrete PERSONALITIES to
background PEOPLE", so when it was handed chat 80's Scranton Reality Anchors --
a ceiling-mounted suppression fixture -- it dutifully produced a manner of
talking ("flat, clipped speech, each word weighed before release") and a
standing grievance ("refuses to blink or shift posture"). The phantom that
interrogated the restrained player on turns 3 and 7 was wearing a personality
the engine had commissioned for it.

So the question moves to where the answer already costs nothing.
"""

from __future__ import annotations

import json

from llm.schemas import PRESENCE_NATURES, BlurbMintEntry
from persist.commit import _presence_speech_verdict

DEVICE_SCENE = {
    "positions": {"Anchors": "cell", "Reyes": "cell"},
    "rooms": {"cell": {"name": "Interview Cell"}},
    "entities": {"e1": {"name": "Anchors", "kind": "device"},
                 "e2": {"name": "Reyes", "kind": "person"}},
}


class TestTheFrozenAnswer:
    def test_it_outranks_the_kind_guess_in_both_directions(self):
        """A judgement about THIS presence in THIS story beats an inference
        from a noun. Both directions matter: `device` is not proof of a thing
        (a dalek war machine is a device), and `person` is not proof of a
        someone (a shop dummy can be typed person)."""
        assert _presence_speech_verdict(DEVICE_SCENE, "Anchors") == "undecided"
        assert _presence_speech_verdict(
            DEVICE_SCENE, "Anchors", {"nature": "person"}) == "person"
        assert _presence_speech_verdict(
            DEVICE_SCENE, "Reyes", {"nature": "thing"}) == "thing"

    def test_a_voice_is_a_thing_to_this_gate(self):
        """A bodiless voice speaks -- but it is the DIRECTOR's mouth, never a
        background reaction. `director_resolve_lean` says so in as many words:
        they "are never characters and never get a character step"."""
        assert _presence_speech_verdict(
            DEVICE_SCENE, "Anchors", {"nature": "voice"}) == "thing"

    def test_an_unanswered_nature_is_not_a_yes(self):
        """The whole defect was an unasked question being read as a person. A
        blank falls through to the graded guesses rather than granting a
        voice."""
        for record in ({}, {"nature": ""}, {"nature": None}, None):
            assert _presence_speech_verdict(
                DEVICE_SCENE, "Anchors", record) == "undecided"

    def test_an_unrecognised_answer_is_treated_as_unanswered(self):
        """A model writing "machine" has not answered the question it was
        asked, and must not be read as having said "person"."""
        assert BlurbMintEntry(name="x", nature="machine").nature == ""
        assert _presence_speech_verdict(
            DEVICE_SCENE, "Anchors", {"nature": "machine"}) == "undecided"

    def test_the_vocabulary_is_the_three_the_prompt_offers(self):
        assert PRESENCE_NATURES == ("person", "thing", "voice")


class TestThePromptStopsAssumingPersonhood:
    """The prompt commissioned the personality that made the phantom credible.
    Fixing the gate without fixing the question would leave the engine paying
    a model to invent a grievance for a wall fixture."""

    def _prompt(self, language):
        from llm.prompts import get_prompt

        return get_prompt("blurb_mint", language)

    def test_it_asks_what_the_presence_is_before_asking_who(self):
        for language in ("en", "ja"):
            body = self._prompt(language)
            for nature in PRESENCE_NATURES:
                assert f'"{nature}"' in body, (language, nature)

    def test_it_says_a_thing_gets_no_personality(self):
        body = self._prompt("en")

        assert "nature` and NOTHING ELSE" in body
        assert "no manner" in body

    def test_it_no_longer_promises_the_list_is_people(self):
        """It received presences assembled by NAME and was told they were
        people. That premise is what it acted on."""
        body = self._prompt("en")

        assert "background presences" in body
        assert "not guaranteed to be people" in body

    def test_both_packs_declare_the_field(self):
        for language in ("en", "ja"):
            assert "nature" in self._prompt(language), language


class TestAThingKeepsNoPersonality:
    def test_a_stale_answer_cannot_store_a_manner_for_a_fixture(self):
        """The prompt no longer asks for one, but a stored blurb is exactly
        what made a suppression device sound like somebody who "refuses to
        blink" -- so a model that answers anyway must not have it kept."""
        import inspect

        import agents.background as background

        source = inspect.getsource(background._mint_blurbs)

        assert 'if nature in ("thing", "voice"):' in source
        assert 'entry = {k: "" for k in entry}' in source


class TestTheListsAreNoLongerTheAuthority:
    def test_every_gate_consults_the_record(self):
        """A frozen answer nothing passes to the gate is a field that changed
        nothing -- the failure shape this repo keeps re-learning (both halves
        built, never introduced)."""
        import inspect

        import agents.background as background
        import agents.director as director
        from persist import commit as commit_module

        for module in (background, director, commit_module):
            source = inspect.getsource(module)
            for call in _verdict_calls(source):
                assert call.count(",") >= 2, call

    def test_the_live_case_is_settled_by_the_answer_not_the_noun(self):
        """chat 80: `kind` "device" left the engine undecided and needing the
        Director's explicit judgment every beat. The blurb pass settles it once
        and the presence is quiet thereafter."""
        assert _presence_speech_verdict(DEVICE_SCENE, "Anchors") == "undecided"
        assert _presence_speech_verdict(
            DEVICE_SCENE, "Anchors", {"nature": "thing"}) == "thing"


def _verdict_calls(source):
    import re

    return re.findall(r"_presence_speech_verdict\([^)]*\)", source)
