"""What the page owes the beat, and what it may call the bodies in it.

Every case here was measured in the play campaign of 2026-09-05 (the five
runs under `docs/experiments/PLAY_2026_09_05C_*.md`). Each test names its run
and finding id, because each rule was EARNED rather than guessed:

  * PX2 (masque) -- FIREWALL. `cast_pronouns` was the last narrator field
    still keyed by the identity behind a body rather than by what the
    player's own view called it, so the page was handed the real names of
    every stranger in the room.
  * PM8 (multitude) -- the quote-attribution guard resolved a line's owner by
    the nearest preceding NAME rather than by the subject of the sentence
    that introduces it: 15 fires in 20 beats, 0 true.
  * PM4 (multitude) -- the player's declared conduct is handed to the page in
    numbered items marked "not yet on the page", and nothing read the page
    back; it went missing on four of twenty beats.
  * PM22 (multitude) -- subject tracking continued a "she" onto a he/him body
    and the warning named the wrong sheet.
  * PS20 (solitude) -- the narrator wrote seventeen beats present, one past,
    then present again, with no tense in the payload to hold it.
  * PX18 (masque) -- the engine's own weld met the model's dialogue-tag
    comma and shipped a comma outside the closing quotation mark, four times
    in one beat.
"""

from __future__ import annotations

import json
import time

from agents.common import (
    _check_narrator_fidelity,
    _check_player_act_rendered,
    _check_quote_attribution,
    _sentence_subjects,
)
from agents.narration import (
    _cast_pronouns,
    _resolve_narration_tense,
    _substitute_dialogue_tokens,
)


HE = {"subject": "he", "object": "him", "possessive": "his"}
SHE = {"subject": "she", "object": "her", "possessive": "hers"}


def _sheet_row(name, pronouns, appearance=""):
    """One `ctx.cast`-shaped row: `_cast_pronouns` reads `sheet` only."""
    return {"sheet": json.dumps({
        "identity": {"name": name, "pronouns": pronouns},
        "embodiment": {"visible": {"summary": appearance}},
    })}


# ---- PX2: a body the view labels has no name in the prose -----------------

def test_cast_pronouns_are_keyed_by_what_the_view_called_the_body():
    """masque 2026-09-05, PX2. The player's view read "The heavy unhurried
    man near fifty stands motionless near the wall"; `cast_pronouns` carried
    `Mattin Ruel`, and the narrator wrote the name three beats before the
    player had any channel to it."""
    cast = [_sheet_row("Mattin Ruel", HE),
            _sheet_row("Lisenne Corvay", SHE)]

    def label(name):
        return ("the heavy unhurried man near fifty"
                if name == "Mattin Ruel" else name)

    keys = set(_cast_pronouns(cast, label=label))
    assert "Mattin Ruel" not in keys
    assert "the heavy unhurried man near fifty" in keys
    # A body the view DOES name keeps its name -- the gate subtracts, it does
    # not anonymise everybody.
    assert "Lisenne Corvay" in keys


def test_cast_pronouns_without_a_label_are_unchanged():
    """The label is the caller's; a caller that supplies none is the
    pre-change behaviour exactly."""
    cast = [_sheet_row("Mattin Ruel", HE)]
    assert set(_cast_pronouns(cast)) == {"Mattin Ruel"}


def test_two_bodies_one_label_is_dropped_rather_than_resolved():
    """The view cannot tell them apart, so neither may claim the entry. The
    narrator card already says a character absent from `cast_pronouns` keeps
    whatever the view established."""
    cast = [_sheet_row("Mattin Ruel", HE), _sheet_row("Verrin Sault", SHE)]
    same = _cast_pronouns(cast, label=lambda _n: "an unfamiliar person")
    assert same == {}


# ---- PM8: the subject of the introducing sentence -------------------------

def test_a_name_after_a_preposition_is_not_the_speaker():
    """multitude 2026-09-05, PM8, turn 4. Hallam is the subject; Vaunt is the
    object of `toward` and merely stands last."""
    prose = ("Devereux Hallam kept his gloved hands resting open upon the oak "
             "and inclined his head deferentially toward Maren Vaunt. "
             "\"Mrs Sarr is entirely right to put the question, Madam Chair.\"")
    events = [
        {"n": 1, "actor": "Devereux Hallam", "kind": "speech",
         "quote": "\"Mrs Sarr is entirely right to put the question, "
                  "Madam Chair.\""},
        {"n": 2, "actor": "Maren Vaunt", "kind": "speech",
         "quote": "\"The question stands.\""},
    ]
    assert _check_quote_attribution(prose, events) == []


def test_a_possessive_is_not_the_speaker_either():
    """Same rule one step over: a possessive names a modifier, never the
    sentence's actor."""
    prose = ("Devereux Hallam set his palm flat on Maren Vaunt's ledger. "
             "\"The hour was entered twice.\"")
    events = [
        {"n": 1, "actor": "Devereux Hallam", "kind": "speech",
         "quote": "\"The hour was entered twice.\""},
        {"n": 2, "actor": "Maren Vaunt", "kind": "speech",
         "quote": "\"Then read it out.\""},
    ]
    assert _check_quote_attribution(prose, events) == []


def test_the_true_misattribution_still_fires():
    """The case the guard exists for is untouched: the subject of the
    introducing sentence is a different body from the one who spoke."""
    prose = ("The unfamiliar woman pulls her hands back from the console. "
             "\"Don't say I didn't warn you.\"")
    events = [
        {"n": 1, "actor": "Vorne", "kind": "speech",
         "quote": "\"Don't say I didn't warn you.\""},
        {"n": 2, "actor": "the unfamiliar woman", "kind": "speech",
         "quote": "\"I second that.\""},
    ]
    found = _check_quote_attribution(prose, events)
    assert found and "Vorne" in found[0]


# ---- PM22: a pronoun redirects only when there is somebody to redirect to --

def test_a_pronoun_of_another_bodys_paradigm_does_not_continue_this_one():
    """multitude 2026-09-05, PM22, turn 16. "She turns the key twice..." was
    bound to Tobin Slake, who is he/him and was at the doors."""
    prose = ("Tobin Slake sets both palms against the door frame. "
             "She turns the key twice with a harsh screech of tumblers.")
    pronouns = {"Tobin Slake": HE, "Maren Vaunt": SHE}
    pairs = list(_sentence_subjects(
        prose, ["Tobin Slake", "Maren Vaunt"], pronouns=pronouns))
    assert pairs[0][1] == "Tobin Slake"
    assert pairs[1][1] == "Maren Vaunt"


def test_two_bodies_answer_the_pronoun_so_it_binds_to_neither():
    prose = ("Tobin Slake sets both palms against the door frame. "
             "She turns the key twice.")
    pronouns = {"Tobin Slake": HE, "Maren Vaunt": SHE, "Ilsabet Roon": SHE}
    pairs = list(_sentence_subjects(
        prose, ["Tobin Slake", "Maren Vaunt", "Ilsabet Roon"],
        pronouns=pronouns))
    assert pairs[1][1] is None


def test_a_disagreement_with_no_other_candidate_keeps_the_subject():
    """A card nobody edited is not a change of body. The tracker must not
    switch itself off for every cast carrying a default paradigm."""
    prose = ("The Doctor lowers the device. "
             "He takes a half-step closer, hands open at his sides.")
    pronouns = {"The Doctor": {"subject": "they", "object": "them",
                               "possessive": "their"}}
    pairs = list(_sentence_subjects(prose, ["The Doctor"], pronouns=pronouns))
    assert pairs[1][1] == "The Doctor"


def test_no_roster_means_the_old_paradigm_blind_continuation():
    prose = "Tobin Slake sets both palms against the frame. She turns the key."
    pairs = list(_sentence_subjects(prose, ["Tobin Slake", "Maren Vaunt"]))
    assert pairs[1][1] == "Tobin Slake"


# ---- PM4: what the page was told is not yet on it must end up on it -------

VIEW_WITH_THE_DOORS = (
    "You stand in the guild hall. The tall yard doors are shut at the far "
    "end. Devereux Hallam is at the factors table."
)


def test_a_declared_act_absent_from_the_prose_warns():
    """multitude 2026-09-05, PM4, turn 7. Three numbered items, marked as not
    yet on the page, and the committed prose carried none of them."""
    order = [{"n": 1, "actor": "Ottoline Sarr", "kind": "action",
              "action": "places both palms flat against the heavy oak doors"}]
    prose = ("Hallam looked up from the factors table. Roon said nothing at "
             "all, and the lamp guttered.")
    found = _check_player_act_rendered(
        prose, VIEW_WITH_THE_DOORS, order, "Ottoline Sarr")
    assert found and "palms" in found[0]


def test_a_declared_act_the_prose_renders_does_not_warn():
    order = [{"n": 1, "actor": "Ottoline Sarr", "kind": "action",
              "action": "places both palms flat against the heavy oak doors"}]
    prose = ("She crossed the hall and set both palms flat against the "
             "doors, and held them there.")
    assert _check_player_act_rendered(
        prose, VIEW_WITH_THE_DOORS, order, "Ottoline Sarr") == []


def test_an_act_that_adds_nothing_to_the_view_is_not_scored():
    """The conservative floor: an act whose every content word already stands
    in the view has no footprint of its own to look for."""
    order = [{"n": 1, "actor": "Ottoline Sarr", "kind": "action",
              "action": "the doors"}]
    assert _check_player_act_rendered(
        "Nothing at all.", VIEW_WITH_THE_DOORS, order, "Ottoline Sarr") == []


def test_only_the_players_own_conduct_is_scored():
    """A character's act is `_check_action_direction`'s business and the
    Director's; this check is about the declaration the page was told to
    render."""
    order = [{"n": 1, "actor": "Devereux Hallam", "kind": "action",
              "action": "places both palms flat against the heavy oak doors"}]
    assert _check_player_act_rendered(
        "Nothing at all.", VIEW_WITH_THE_DOORS, order, "Ottoline Sarr") == []


def test_the_missing_declaration_reaches_the_fidelity_warnings():
    """The check is wired into `_check_narrator_fidelity`, which is where the
    step's own `fidelity_warnings` come from."""
    warnings = _check_narrator_fidelity(
        {"prose": "Hallam looked up from the factors table."},
        VIEW_WITH_THE_DOORS,
        player_name="Ottoline Sarr",
        event_order=[{"n": 1, "actor": "Ottoline Sarr", "kind": "action",
                      "action": "places both palms flat against the heavy "
                                "oak doors"}])
    assert any("declared conduct is missing" in w for w in warnings)


# ---- PS20: one story, one tense -------------------------------------------

PRESENT_BEATS = [
    "You push through the door. The hinges give, and the corridor stretches "
    "away. She stands at the far end and watches you come.",
    "The air is cold. Your hand finds the rail and holds it. She says "
    "nothing at all.",
]
PAST_BEATS = [
    "You pushed through the door. The hinges gave, and the corridor "
    "stretched away. She stood at the far end and watched you come.",
    "The air was cold. Your hand found the rail and held it. She said "
    "nothing at all.",
]


def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Tense", "", time.time()))


def test_an_unset_story_inherits_the_tense_its_own_page_is_in(temp_db):
    """solitude 2026-09-05, PS20. Seventeen beats present, turn 18 past, turn
    19 present again -- with nothing in the payload to hold it and nothing to
    score the drift against."""
    cid = _chat(temp_db)
    assert _resolve_narration_tense(cid, PRESENT_BEATS) == "present"
    assert _resolve_narration_tense(cid, PAST_BEATS) == "past"


def test_a_story_with_no_page_yet_still_gets_no_tense(temp_db):
    """The opening beat, every time: there is no established tense to
    inherit, so the payload carries none and the feature stays invisible."""
    cid = _chat(temp_db)
    assert _resolve_narration_tense(cid, []) == ""
    assert _resolve_narration_tense(cid, ["She stood."]) == ""


def test_the_authored_dial_still_wins(temp_db):
    """Tense is AUTHORED where person is detected; the fallback is only for
    an author who said nothing."""
    from core.db import wset
    from story.scene import normalize_style_guide
    cid = _chat(temp_db)
    wset(cid, "style_guide",
         normalize_style_guide({"narration_tense": "past"}))
    assert _resolve_narration_tense(cid, PRESENT_BEATS) == "past"


# ---- PX18: one mark ends a line -------------------------------------------

def test_a_tag_comma_outside_the_weld_moves_inside_it():
    """masque 2026-09-05, PX18, turn 3, four times in one beat: the engine
    welds the line's own full stop and the model types the tag comma after
    the closing mark."""
    text, missing = _substitute_dialogue_tokens(
        'She turned. "{{L1}}", Lisenne Corvay said.',
        ["Supper will be served in the half-hour."])
    assert '"Supper will be served in the half-hour," Lisenne Corvay said.' \
        in text
    assert missing == []


def test_a_question_mark_keeps_its_meaning_and_loses_the_comma():
    text, _ = _substitute_dialogue_tokens(
        'She turned. "{{L1}}", she said.', ["Who is there?"])
    assert '"Who is there?" she said.' in text


def test_a_doubled_terminal_loses_the_outer_one():
    text, _ = _substitute_dialogue_tokens(
        'She turned. "{{L1}}".', ["I am finished."])
    assert text.endswith('"I am finished."')


def test_a_line_the_model_did_not_punctuate_is_untouched():
    text, _ = _substitute_dialogue_tokens(
        'He said "{{L1}}" and left.', ["no"])
    assert 'He said "no" and left.' == text


# ---- PQ9: the beat with nothing to detect from ----------------------------

def test_the_opening_beat_reads_the_authors_stated_person():
    """quiet 2026-09-05, PQ9. `narration_person` was `second` on turn 0 and
    `third` on all twenty turns after it, so the reader met the switch in the
    first two paragraphs -- while the persona card said "close third person,
    restrained, exact about small things" and nothing read it."""
    from agents.narration import _authored_narration_person
    assert _authored_narration_person(
        "close third person, restrained, exact about small things", "",
        "Tobin", {}) == "third"


def test_a_guide_that_names_two_persons_has_said_nothing_usable():
    from agents.narration import _authored_narration_person
    assert _authored_narration_person(
        "a mix of first person and third person", "", "X", {}) is None


def test_the_scenario_answers_when_the_guide_does_not():
    """The other place the author was asked the question, scored by the same
    detector the player's own turn is scored by."""
    from agents.narration import _authored_narration_person
    assert _authored_narration_person(
        "", "You stand at the intake gate. You have been here since dawn.",
        "Mireille Adjani", {}) == "second"
    assert _authored_narration_person(
        "", "Mireille Adjani stands at the gate. She has been here since "
            "dawn.", "Mireille Adjani",
        {"subject": "she", "object": "her", "possessive": "hers"}) == "third"


def test_an_author_who_said_nothing_still_gets_the_default(temp_db):
    from agents.narration import _resolve_narration_person
    cid = _chat(temp_db)
    assert _resolve_narration_person(cid, "", "X", {}, pending={}) == "second"


def test_an_established_convention_beats_the_authors_seed(temp_db):
    """The guide seeds the beat that has nothing; it does not override what
    the player has since been writing."""
    from core.db import wset
    from agents.narration import _resolve_narration_person
    cid = _chat(temp_db)
    wset(cid, "narration_person", "first")
    assert _resolve_narration_person(
        cid, "", "X", {}, pending={},
        voice_setting="close third person") == "first"


def test_the_players_own_writing_still_wins_on_the_turn_it_speaks(temp_db):
    from agents.narration import _resolve_narration_person
    cid = _chat(temp_db)
    pending = {}
    person = _resolve_narration_person(
        cid, "I push through the door and I do not look back.", "X", {},
        pending=pending, voice_setting="close third person")
    assert person == "first" and pending == {"narration_person": "first"}


def test_the_authors_seed_is_not_written_back(temp_db):
    """The evidence does not change between beats, so there is nothing to
    remember -- and recording it would make an authored guide look like a
    detected convention to every later turn."""
    from agents.narration import _resolve_narration_person
    cid = _chat(temp_db)
    pending = {}
    assert _resolve_narration_person(
        cid, "", "X", {}, pending=pending,
        voice_setting="close third person") == "third"
    assert pending == {}
