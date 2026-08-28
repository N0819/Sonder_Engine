"""The narration-tense dial: an AUTHORED, closed-vocabulary setting that says
which tense the narrator writes the page in.

Three properties this file exists to hold, because each has a way of failing
silently:

  1. UNSET IS A REAL VALUE and it is the default. A story that never set the
     dial must get the payload it got before the field existed -- no key, no
     instruction, no warning. That is what makes the setting safe to add to a
     corpus of stories already in play.
  2. TENSE IS AUTHORED WHERE PERSON IS DETECTED. They sit in the same narrator
     payload with opposite provenance, and provenance is what decides whether
     a reroll may carry a value across.
  3. THE CHECK IS A WARNING. Tense is a whole-draft property, so a correction
     note cannot patch it locally and it must never buy a rewrite.

Scope, stated because the boundary is the design: this changes NARRATION and
nothing else. Character declarations, memory's own register and the Director's
present-tense state labels are all out of it.
"""

from __future__ import annotations

import json
import time

import pytest

from agents.common import (_check_narration_tense_match,
                           _check_narrator_fidelity, _narration_tense_counts)
from agents.narration import _craft_tells
from core.db import wget, wset
from core.pipeline_context import ChatData, PipelineContext, TurnData
from language_runtime import current_language_id, english_linguistic
from persist.checkpoints import (DETECTED, PRESERVED_SETTING_KEYS,
                                 SET_BY_HAND, SETTING_PROVENANCE)
from story.character_schema import default_character_data
from story.scene import (NARRATION_TENSES, narration_tense,
                         normalize_style_guide, style_guide)


PRESENT_DRAFT = (
    "You push through the door. The hinges give, and the corridor beyond "
    "stretches away into a grey light. She stands at the far end and watches "
    "you come. The air is cold. Your hand finds the rail and holds it."
)
PAST_DRAFT = (
    "You pushed through the door. The hinges gave, and the corridor beyond "
    "stretched away into a grey light. She stood at the far end and watched "
    "you come. The air was cold. Your hand found the rail and held it."
)


def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Test", "", time.time()))


# ---- the setting -------------------------------------------------------

class TestTheSetting:
    def test_the_vocabulary_is_closed(self):
        assert NARRATION_TENSES == ("present", "past")

    @pytest.mark.parametrize("raw, expected", [
        ("past", "past"),
        ("present", "present"),
        ("  PAST  ", "past"),
    ])
    def test_a_known_value_normalizes_to_itself(self, raw, expected):
        assert normalize_style_guide(
            {"narration_tense": raw})["narration_tense"] == expected

    @pytest.mark.parametrize("raw", [
        "", "   ", None, "future", "perfect", "auto", "self-determine",
        "unspecified", 7, {"nested": "dict"},
    ])
    def test_anything_else_becomes_UNSET_rather_than_an_opinion(self, raw):
        """The other closed field in this guide (`weather_severity`) falls back
        to its DEFAULT, because a story always has a sky. This one has no
        default: falling back to `present` would give every story an opinion
        its author never expressed, and that is a behaviour change for the
        whole corpus rather than a normalization."""
        assert "narration_tense" not in normalize_style_guide(
            {"narration_tense": raw})

    def test_it_does_not_disturb_the_rest_of_the_guide(self):
        guide = normalize_style_guide(
            {"tone": "cold", "narration_tense": "past",
             "weather_severity": "harsh"})
        assert guide == {"tone": "cold", "narration_tense": "past",
                         "weather_severity": "harsh"}

    def test_unset_reads_as_the_empty_string_not_as_present(self, temp_db):
        cid = _chat(temp_db)
        assert narration_tense(cid) == ""

    def test_the_dial_is_read_FRESH_so_it_can_be_turned_mid_story(self, temp_db):
        """A story is expected to change tense at beat 40 if its author says
        so. Nothing caches this and nothing needs a restart -- the accessor
        goes through `style_guide`, which is documented as a per-turn read."""
        cid = _chat(temp_db)
        wset(cid, "style_guide", normalize_style_guide(
            {"narration_tense": "past"}))
        assert narration_tense(cid) == "past"
        wset(cid, "style_guide", normalize_style_guide(
            {"narration_tense": "present"}))
        assert narration_tense(cid) == "present"
        wset(cid, "style_guide", normalize_style_guide({}))
        assert narration_tense(cid) == ""

    def test_a_hand_written_world_row_cannot_smuggle_a_bad_value_through(
            self, temp_db):
        """`style_guide` is a KV blob an import or a hand edit can write
        directly, so the accessor re-checks rather than trusting the store."""
        cid = _chat(temp_db)
        wset(cid, "style_guide", {"narration_tense": "pluperfect"})
        assert narration_tense(cid) == ""
        assert style_guide(cid) == {}


# ---- provenance: authored vs detected ----------------------------------

class TestProvenance:
    def test_every_preserved_key_is_classified(self):
        assert set(PRESERVED_SETTING_KEYS) <= set(SETTING_PROVENANCE)
        for key in PRESERVED_SETTING_KEYS:
            assert SETTING_PROVENANCE[key] is not DETECTED

    def test_a_detected_key_is_never_preserved(self):
        """The distinction the checkpoint comment asked for, as a rule rather
        than as a paragraph: a value the ENGINE inferred from play is story
        state, so a rewind must take it back with the story."""
        detected = [key for key, source in SETTING_PROVENANCE.items()
                    if source is DETECTED]
        assert "narration_person" in detected
        for key in detected:
            assert key not in PRESERVED_SETTING_KEYS

    def test_the_authored_dial_survives_a_reroll(self):
        """It rides `style_guide`, which is preserved -- so the author's tense
        is not rolled back by a rewind that predates the day they set it."""
        assert SETTING_PROVENANCE["style_guide"] is SET_BY_HAND
        assert "style_guide" in PRESERVED_SETTING_KEYS


# ---- the payload -------------------------------------------------------

def _narrator_ctx(temp_db, *, idx, tense=None):
    cid = _chat(temp_db)
    if tense is not None:
        wset(cid, "style_guide", normalize_style_guide(
            {"narration_tense": tense}))
    scene = {"rooms": {"r1": {"name": "Hall", "notes": "a hall"}},
             "positions": {"Player": "r1"}, "entities": {}}
    temp_db.wset(cid, "scene", scene)
    sheet = default_character_data("Mara")
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=idx, player_input="hi",
                      created=time.time()),
        cast=[{"id": 1, "sheet": json.dumps(sheet), "cstate": "{}",
               "status": "active"}],
        input="I push through the door.")
    ctx._extra["outcome_scene"] = scene
    ctx["_player_room"] = "r1"
    ctx["director_interpret"] = {"sequence": [], "speech": None}
    ctx["perception_outcome"] = {"views": {"player": "The hall is quiet."}}
    ctx["perception_establish"] = {"views": {"player": "The hall is quiet."}}
    return ctx


def _render(temp_db, monkeypatch, *, idx, tense):
    import agents.narration as narration

    captured = {}

    def _fake_agent_json(step_key, model_key, prompt, payload, **kw):
        captured["payload"] = payload
        return {"prose": PRESENT_DRAFT, "new_specifics": []}

    monkeypatch.setattr(narration, "_agent_json", _fake_agent_json)
    monkeypatch.setattr(narration, "validate_llm_output",
                        lambda key, out: (out, []))
    narration.narrator(_narrator_ctx(temp_db, idx=idx, tense=tense), 0)
    return captured["payload"]


class TestThePayload:
    def test_an_unset_story_carries_NO_tense_key(self, temp_db, monkeypatch):
        """Absence is the contract, not an empty string. An always-present
        empty key teaches the model to skip it, and worse, invites it to
        choose -- which is the drift this dial exists to remove."""
        payload = _render(temp_db, monkeypatch, idx=3, tense=None)
        assert "narration_tense" not in payload
        assert payload["narration_person"]

    @pytest.mark.parametrize("tense", ["past", "present"])
    def test_a_set_story_carries_it_on_an_ordinary_beat(
            self, temp_db, monkeypatch, tense):
        payload = _render(temp_db, monkeypatch, idx=3, tense=tense)
        assert payload["narration_tense"] == tense

    @pytest.mark.parametrize("tense", ["past", "present"])
    def test_it_reaches_THE_OPENING_TURN(self, temp_db, monkeypatch, tense):
        """Turn 0 runs `director_establish -> perception_establish ->
        narrator`, not the normal flow, and it is the beat with no earlier
        prose to inherit a tense from -- the one measured landing in either
        tense by accident. Same stage, so the same field must arrive."""
        payload = _render(temp_db, monkeypatch, idx=0, tense=tense)
        assert payload["scene_opening"] is True
        assert payload["narration_tense"] == tense

    def test_the_unset_opening_turn_is_also_untouched(
            self, temp_db, monkeypatch):
        payload = _render(temp_db, monkeypatch, idx=0, tense=None)
        assert "narration_tense" not in payload

    def test_the_PLAYERS_OWN_tense_does_not_decide_the_narrators(
            self, temp_db, monkeypatch):
        """Player input and narration read as one continuous story, but that
        design constrains PERSON, not tense -- the sheet asks for "the same
        voice and the same grammatical person". The player's line is a claim
        about what they attempt; the narration is the record of what happened.
        Measured live: one story ran present-tense player input against
        past-tense narration for its whole length and reads correctly.

        So the input here is present tense throughout, and the authored dial
        still wins -- while `narration_person`, which IS read off that same
        input, keeps taking its answer from it."""
        payload = _render(temp_db, monkeypatch, idx=3, tense="past")
        assert payload["narration_tense"] == "past"
        assert payload["narration_person"] == "first"


# ---- the detector ------------------------------------------------------

class TestTheDetector:
    def test_it_reads_the_tense_a_draft_is_written_in(self):
        past = _narration_tense_counts(PAST_DRAFT)
        present = _narration_tense_counts(PRESENT_DRAFT)
        assert past["past"] > past["present"]
        assert present["present"] > present["past"]

    def test_prose_in_the_asked_for_tense_is_silent(self):
        assert _check_narration_tense_match(PAST_DRAFT, "past") == []
        assert _check_narration_tense_match(PRESENT_DRAFT, "present") == []

    def test_prose_in_the_other_tense_is_reported(self):
        warnings = _check_narration_tense_match(PAST_DRAFT, "present")
        assert len(warnings) == 1
        assert "past tense" in warnings[0]
        assert "'present'" in warnings[0]
        assert _check_narration_tense_match(PRESENT_DRAFT, "past")

    def test_an_unset_story_is_never_scored(self):
        """No instruction was given, so there is nothing to be wrong about --
        and this is the line that keeps the whole feature invisible to every
        story that predates it."""
        for value in ("", None, "auto", "future"):
            assert _check_narration_tense_match(PAST_DRAFT, value) == []
            assert _check_narration_tense_match(PRESENT_DRAFT, value) == []

    def test_a_draft_with_too_little_evidence_declines_to_answer(self):
        assert _check_narration_tense_match("Silence.", "past") == []
        assert _check_narration_tense_match("", "past") == []

    def test_DIALOGUE_IS_NOT_THE_NARRATING_VOICE(self):
        """People speak in the present inside a past-tense narrative; that is
        ordinary convention, not drift. A detector that scored quoted lines
        would report every correct past-tense draft, which is the single most
        likely way for this check to be wrong."""
        draft = (
            'He crossed the room and set the lamp down. "I am going now, and '
            'you are not stopping me. It is what it is, and it always is," he '
            'said. She watched him go, and the door swung shut behind him.'
        )
        assert _check_narration_tense_match(draft, "past") == []

    def test_it_is_a_WARNING_and_never_buys_a_rewrite(self):
        """An enforceable warning costs a whole narrator call. Tense is a
        whole-draft property, so a correction note cannot patch it locally --
        the same argument that keeps the person check out of this list."""
        warning = _check_narration_tense_match(PAST_DRAFT, "present")[0]
        prefixes = english_linguistic("agents.narration",
                                      "_ENFORCEABLE_PREFIXES")
        assert not warning.startswith(tuple(prefixes))

    def test_it_is_wired_into_the_narrator_fidelity_pass(self):
        out = {"prose": PAST_DRAFT}
        assert any("tense" in w for w in _check_narrator_fidelity(
            out, view="", narration_tense="present"))
        assert not any("tense" in w for w in _check_narrator_fidelity(
            out, view="", narration_tense="past"))
        # And the pass is unchanged for every story that set nothing.
        assert not any("tense" in w for w in _check_narrator_fidelity(
            out, view=""))

    def test_the_markers_are_PACK_SCOPED_and_resolved_at_use_time(self):
        """Two live defects came from resolving a pack transform at import,
        which leaves a non-English pack's entries dead. This detector reads
        its markers through `_ling` on every call, so a story told in another
        language is judged by that language's own tense marking."""
        token = current_language_id.set("ja")
        try:
            counts = _narration_tense_counts("彼は扉を押し開けた。廊下は寒かった。")
            assert counts["past"] > counts["present"]
        finally:
            current_language_id.reset(token)


# ---- craft tells -------------------------------------------------------

class TestCraftTells:
    def test_a_filtering_line_is_a_tell_in_EITHER_tense(self):
        """The tell is the SHAPE of the sentence. It did not stop being one
        when the page is written in the past -- which this dial makes an
        ordinary thing for a page to be."""
        present = _craft_tells("He takes the room in.")
        past = _craft_tells("He took the room in.")
        assert present and past
        assert past == present

    def test_the_other_filtering_shape_too(self):
        assert _craft_tells("She took in the room.")
        assert _craft_tells("She takes in the room.")

    def test_the_exception_it_already_carried_still_holds(self):
        """`takes the cup in his hands` is a physical act, not filtering, and
        the widened pattern must not have swallowed the guard that says so."""
        assert not _craft_tells("He takes the cup in his hands.")
        assert not _craft_tells("He took the cup in his hands.")


class TestProseRulesLiveInThePrompt:
    """The craft rewrite bought a second full narrator call to enforce a list
    the narrator prompt already carries -- "eyes flick", "middle distance",
    "hangs in the air" are all in its ~37,600 characters. Duplicate
    enforcement, and enforcement by matching a STRING rather than the usage
    the string indicates.

    Measured on a live market-town turn: `\\bregisters?\\b`, listed as
    "sensor-ledger diction", fired on the ordinary English verb in "stepped
    aside for her without seeming to register he'd done it". That one false
    positive cost 21.2s -- the largest single model cost in a 352s turn -- and
    the rewrite it forced came back 40% shorter (1029 chars to 613) and was
    accepted automatically, because the acceptance test asked only for fewer
    tells and intact dialogue.
    """

    def test_the_rules_are_in_the_prompt(self):
        from llm.prompts import get_prompt

        prompt = get_prompt("narrator")

        for rule in ("eyes flick", "middle distance", "hangs in the air"):
            assert rule in prompt.casefold(), rule

    def test_no_craft_rewrite_survives_in_the_narrator(self):
        """A second narrator call is the thing being removed, so the loop that
        spent it must not come back quietly."""
        import inspect
        from agents import narration

        source = inspect.getsource(narration)

        assert "craft_attempts" not in source
        assert "narrator_craft_correction" not in source

    def test_a_tell_is_still_reported(self):
        """Demoted, not deleted: drift stays visible the way content-reuse
        already does, without costing a model call."""
        from agents.narration import _craft_tells

        assert _craft_tells("Her eyes flick to the door.")
        assert not _craft_tells("She looked at the door.")
