"""Character-authority guards on `director_resolve`'s resolved_event.

A character owns their own conduct exactly as the player owns theirs. The
Director resolves what their declared acts ACHIEVE; it does not hand them
acts or words they never declared.

Live case, chat 56 "Run!" turn idx 3 (turn_id 1391). The Doctor's character
step declared exactly one thing -- draw the sonic screwdriver and scan "from
several feet away", "while staying at distance" -- and `speech: null`. The
resolve returned him stepping closer and speaking:

    He takes a half-step closer, hands open at his sides, and speaks in a
    low, steady voice. 'You're alright, Hinami. Nothing broken, nothing out
    of place. Just breathe. You're safe here.'

`_check_character_speech_authority` was armed (the Doctor was in
`_silent_names`) and returned nothing, for three independent reasons:

  1. it only selected sentences OPENING with the literal name, and every
     fabricated sentence opened with the pronoun "He";
  2. its verb window measured three words from the name, so the attribution
     verb in a compound predicate ("takes ..., hands ..., and speaks ...")
     sat far outside it;
  3. the invented line lived in prose, never in `dialogue_log`, so the
     dialogue-fidelity backstop that WOULD have dropped it had nothing to
     inspect -- while the speech check deliberately strips quoted spans on
     the assumption that path covers them.

Nothing guarded a character's ACTS at all -- `_check_player_act_authority`
is applied only to the player.

The narrator dropped both fabrications, so the player never saw them; the
Doctor's own perception view kept them and they were committed as his
episodic memory (memories.id 11712). That is the shape this defends: a
fabrication invisible in the player-facing prose that still becomes a
character's memory of their own conduct.
"""

import pytest

from agents.common import (
    _check_character_act_authority,
    _check_character_speech_authority,
    _check_prose_quote_authority,
    _sentence_subjects,
)


# The resolved_event exactly as director_resolve returned it (step 12268).
RUN_RESOLVED_EVENT = (
    "Hinami stays pressed against the wall, one hand splayed over her chest, "
    "her breath coming in ragged, shuddering gasps. Her eyes are squeezed "
    "shut, and a fine tremor runs through her frame. The warm golden light of "
    "the console room holds her still. The Doctor, a few feet away, draws the "
    "sonic screwdriver from his coat pocket and aims it at her. It emits a "
    "low, soft warble as he sweeps it over her, the tip glowing blue. The "
    "sound is gentle, almost like a lullaby hum, and it washes over her "
    "without adding to her distress. He watches the readout, his expression "
    "calm and focused, noting her vitals and the absence of any temporal "
    "distortion. After a moment, he lowers the device, the warble fading. He "
    "takes a half-step closer, hands open at his sides, and speaks in a low, "
    "steady voice. 'You're alright, Hinami. Nothing broken, nothing out of "
    "place. Just breathe. You're safe here.'"
)

# What the character step actually declared: one action, no speech.
RUN_DECLARED_ACTIONS = [{
    "type": "action",
    "attempt": (
        "draws the sonic screwdriver and activates it at low power from "
        "several feet away to scan Hinami for injuries or temporal disruption"
    ),
    "observable": (
        "draws sonic screwdriver from coat pocket, aims it at Hinami and "
        "activates it with a low warble"
    ),
}]

CAST = ["The Doctor", "Hinami"]


# --------------------------------------------------------------------------
# subject resolution


def test_pronoun_subject_binds_to_most_recent_named_subject():
    """"He watches"/"he lowers"/"He takes" all continue "The Doctor"."""
    bound = [s for s, subj in _sentence_subjects(RUN_RESOLVED_EVENT, CAST)
             if subj == "The Doctor"]
    # Four: the named sentence, then "He watches", "After a moment, he
    # lowers", "He takes". "It emits ... as he sweeps it" has "It" for a
    # subject and is deliberately not bound.
    assert len(bound) == 4, bound
    assert bound[0].startswith("The Doctor, a few feet away, draws")
    assert any(s.startswith("He takes a half-step closer") for s in bound)
    assert any(s.startswith("After a moment, he lowers") for s in bound)


def test_pronoun_does_not_bind_across_a_new_named_subject():
    """A newer named subject takes the pronoun; the older one is not blamed."""
    prose = ("The Doctor draws the sonic screwdriver. Hinami flinches back "
             "against the wall. She says nothing at all.")
    subjects = dict((s, subj) for s, subj in _sentence_subjects(prose, CAST))
    assert subjects["She says nothing at all."] == "Hinami"


def test_unanchored_pronoun_binds_to_nobody():
    """With no named subject yet established, a pronoun is not guessed at."""
    prose = "He steps closer and speaks in a low voice."
    assert [subj for _, subj in _sentence_subjects(prose, CAST)] == [None]


# --------------------------------------------------------------------------
# speech


def test_invented_speech_for_a_silent_character_is_caught():
    """The live regression: the Doctor declared no speech and was given a line."""
    warnings = _check_character_speech_authority(
        RUN_RESOLVED_EVENT, ["The Doctor"])
    assert warnings, "invented speech for a silent character went unflagged"
    assert any("The Doctor" in w for w in warnings)


def test_speech_verb_in_a_compound_predicate_is_caught():
    """The verb window must reach past the first conjunct of a shared subject."""
    prose = ("The Doctor takes a half-step closer, hands open at his sides, "
             "and speaks in a low, steady voice.")
    assert _check_character_speech_authority(prose, ["The Doctor"])


def test_a_character_who_spoke_is_not_checked():
    """Only characters who declared NO speech are in scope."""
    assert _check_character_speech_authority(RUN_RESOLVED_EVENT, []) == []


def test_silent_character_may_still_act_and_be_described():
    """Silence forbids speech, not conduct. This must not cry wolf."""
    prose = ("The Doctor watches her, his expression calm and focused. He "
             "lowers the device, the warble fading. He waits.")
    assert _check_character_speech_authority(prose, ["The Doctor"]) == []


def test_subordinate_clause_with_its_own_subject_is_not_the_character():
    """"...as she says" is her speech, not his."""
    prose = "The Doctor lowers the device, and she says nothing."
    assert _check_character_speech_authority(prose, ["The Doctor"]) == []


# --------------------------------------------------------------------------
# acts


def test_invented_approach_for_a_character_who_stayed_put_is_caught():
    """The Doctor declared a scan "from several feet away"; the resolve moved him.

    His own declared want was to scan her "without crowding her", so the
    half-step is not elaboration of the declared act -- it reverses it.
    """
    warnings = _check_character_act_authority(
        RUN_RESOLVED_EVENT, RUN_DECLARED_ACTIONS, "The Doctor", CAST)
    assert warnings, "invented approach went unflagged"
    assert any("half-step" in w for w in warnings)


def test_declared_act_may_be_elaborated_freely():
    """Rendering a declared act richly is the Director's job, not a violation."""
    prose = ("The Doctor draws the sonic screwdriver from his coat pocket in "
             "one smooth motion and aims it at her, the tip glowing blue.")
    assert _check_character_act_authority(
        prose, RUN_DECLARED_ACTIONS, "The Doctor", CAST) == []


def test_a_character_who_declared_movement_may_be_moved():
    """The guard is about undeclared movement, not movement."""
    declared = [{"attempt": "steps carefully toward the console"}]
    prose = "The Doctor steps closer to the console and leans over it."
    assert _check_character_act_authority(
        prose, declared, "The Doctor", CAST) == []


def test_character_with_no_declared_action_gets_the_full_act_check():
    """Declaring nothing is a declaration; any act is invented by construction."""
    prose = "The Doctor nods slowly and hands her the screwdriver."
    assert _check_character_act_authority(prose, [], "The Doctor", CAST)


def test_non_locomotive_description_is_not_an_act():
    """Stative description of a character who declared an act is fine."""
    prose = ("The Doctor is quiet, his expression calm and focused, the blue "
             "glow washing across her face.")
    assert _check_character_act_authority(
        prose, RUN_DECLARED_ACTIONS, "The Doctor", CAST) == []


# --------------------------------------------------------------------------
# prose quotes


def test_prose_quote_not_traceable_to_any_declaration_is_caught():
    """The line never reached dialogue_log, so only a prose check can see it."""
    warnings = _check_prose_quote_authority(RUN_RESOLVED_EVENT, set())
    assert warnings
    assert any("You're alright" in w for w in warnings)


def test_declared_line_quoted_in_prose_is_allowed():
    allowed = {"You're alright, Hinami. Nothing broken, nothing out of "
               "place. Just breathe. You're safe here."}
    assert _check_prose_quote_authority(RUN_RESOLVED_EVENT, allowed) == []


def test_possessives_are_not_read_as_quotes():
    """Apostrophes are not quote delimiters."""
    prose = ("The ship's hull groaned and Mara's grip tightened on the rail "
             "as the Doctor's coat snapped in the wind.")
    assert _check_prose_quote_authority(prose, set()) == []


def test_short_quoted_fragments_are_left_alone():
    """Scare quotes and single-word labels are not utterances."""
    prose = 'The readout flashed "STABLE" and he frowned at the word "safe".'
    assert _check_prose_quote_authority(prose, set()) == []


@pytest.mark.parametrize("style", ['"{}"', "“{}”", "'{}'"])
def test_quote_styles_are_all_seen(style):
    """The resolve model picks a quote style at random; all must be checked."""
    prose = "The Doctor lowers the device. " + style.format(
        "You are alright now, nothing is broken here.")
    assert _check_prose_quote_authority(prose, set())


# --------------------------------------------------------------------------
# end to end through director_resolve
#
# The unit checks above prove the guards see the violation. These prove the
# guards are actually WIRED -- that `decls`/`char_speech`/`char_actions` reach
# them and that a violation is flagged on the step, naming what was invented.
# The live defect was not a missing check so much as a check that ran and saw
# nothing. On the causal path a violation also fired one correction retry;
# the prose Director warns and never retries, so `player_act_warnings` is the
# only record (UNBUILT_PIPELINE §1.1).

import json
import time

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from tests.director_fakes import prose_resolve_agent


def _make_ctx(temp_db, character_results):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Run!", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("The Doctor", json.dumps(default_character_data("The Doctor")), "{}",
         time.time(), "char_doctor"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "console room", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 3, "You continue to breath raged breaths.", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Run!", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=3,
                      player_input="You continue to breath raged breaths.",
                      created=time.time()),
        cast=cast, input="You continue to breath raged breaths.",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    if character_results:
        ctx.character_results = {char_id: character_results}
    return ctx, char_id


# The Doctor's declaration: one action, explicitly at distance, no speech.
SCAN_ONLY = {
    "name": "The Doctor",
    "speech": None,
    "sequence": [{
        "type": "action",
        "attempt": RUN_DECLARED_ACTIONS[0]["attempt"],
        "observable": RUN_DECLARED_ACTIONS[0]["observable"],
    }],
    "action": None,
}

CLEAN_REWRITE = (
    "Hinami stays pressed against the wall, one hand splayed over her chest. "
    "The Doctor, a few feet away, draws the sonic screwdriver from his coat "
    "pocket and aims it at her, the tip glowing blue. He watches the readout, "
    "his expression calm and focused. He lowers the device, the warble fading."
)


def test_resolve_flags_invented_character_conduct(temp_db, monkeypatch,
                                                 prose_director):
    """The live draft must be flagged, and the flag must name what was
    invented -- the half-step and the line nobody declared.

    Named `..._retries_...` until 2026-09-27: the causal path fired one
    correction retry here, kept only if it lowered the count, so the clean
    rewrite won and the fabrication never committed. The prose Director warns
    and never retries, and the fabrication stays in its account
    (UNBUILT_PIPELINE §1.1).
    """
    import agents.director as director

    ctx, _ = _make_ctx(temp_db, character_results=SCAN_ONLY)
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": RUN_RESOLVED_EVENT}, calls=calls))
    out = director.director_resolve(ctx, nonce=0)

    assert [key for key, _ in calls].count("director_prose") == 1
    warnings = out.get("player_act_warnings") or []
    assert any("character-act authority" in w and "half-step" in w
               for w in warnings), warnings
    assert any("nobody declared" in w and "You're alright" in w
               for w in warnings), warnings
    assert any("character-speech authority" in w for w in warnings), warnings


def test_a_declared_act_alone_is_not_flagged(temp_db, monkeypatch,
                                            prose_director):
    """The guard must not accuse an honest beat. (It must not cost a second
    model call either: named `..._fires_no_retry` while a flag bought one.)"""
    import agents.director as director

    ctx, _ = _make_ctx(temp_db, character_results=SCAN_ONLY)
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": CLEAN_REWRITE}, calls=calls))
    out = director.director_resolve(ctx, nonce=0)

    assert [key for key, _ in calls].count("director_prose") == 1
    assert not out.get("player_act_warnings"), out.get("player_act_warnings")


def test_actions_declared_in_the_sequence_reach_char_actions(temp_db, monkeypatch,
                                                            prose_director):
    """A declaration carrying its act only in `sequence` must not read as
    having declared nothing.

    The `ctx.character_results` branch of the declaration merge read
    `dk["action"]` alone while the interaction-loop branch read the sequence,
    so the same declaration produced different `char_actions` depending on
    which flow resolved it. Latent until character-act authority started
    reading it: an empty entry means "declared no act at all", which is the
    strictest branch of the guard, and it fired on ordinary prose ("He lowers
    the device") for a character who had plainly acted.
    """
    import agents.director as director

    ctx, _ = _make_ctx(temp_db, character_results=SCAN_ONLY)
    assert SCAN_ONLY["action"] is None, "fixture must carry the act in sequence"
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": CLEAN_REWRITE}))
    out = director.director_resolve(ctx, nonce=0)

    # The guard's own verdict is the observable: a character whose act was
    # seen is not accused of acting from nowhere. (On the prose path the
    # verdict is on the step, never in ctx.warnings.)
    assert not any("character-act authority" in w
                   for w in (out.get("player_act_warnings") or []))
