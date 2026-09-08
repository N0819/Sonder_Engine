"""D6 (review 2026-09-07): a line that got no answer is an event.

Perception is built out of what ARRIVED, and a silence arrives as nothing at
all -- so the beat where somebody was spoken to and said nothing back had no
channel anywhere in the engine. The page either let it pass as though nobody
had been addressed, or wrote "no answer came" about a body that had in fact
answered.

The rule now: for a declared line naming a target, where the line REACHED
that target and no speech of theirs is anywhere in the beat's stream, the
addresser's own view carries "<label> says nothing." It states the fact and
never the reason -- refusal, distraction and an answer given to somebody
else are all still the reader's to infer, which is the entire point of the
beat.

Every condition subtracts. An address nobody could hear mints nothing (the
addresser does not know they were heard). A target the scene cannot place
mints nothing (there is no relation to grade delivery over). A target this
observer has no label for mints nothing ("a voice says nothing" is not a
fact anybody has). A target WHO NEVER RAN mints nothing -- the dialogue log
records what was said and never who was asked, so a reactor the Director's
pacing left out of `flow.reactors`, or one the interaction loop's round
budget skipped, is not a body that declined to answer. An answer over any
channel is an answer, a radio call included. And it reaches the ADDRESSER'S
view alone: to everybody else in the room, a person who did not speak is a
person who did not speak.
"""

from __future__ import annotations

from agents import composer
from agents.perception import _outcome_event_stream, _unanswered_addresses


class Ctx(dict):
    __getattr__ = dict.__getitem__


def _shrug():
    """A declared sequence that is not speech: the body ran and answered
    nothing. What `sequences` needs to hold for a silence to be a refusal
    rather than a body the beat never reached."""
    return {"type": "action", "attempt": "shrugs", "observable": "shrugs",
            "visibility": "overt"}


def _ctx(*, ran=("Reya",), sequence=None):
    """`ran` are the bodies the beat actually gave a turn to. Empty is the
    shape the Director's pacing produces when it leaves a reactor out."""
    rounds = [{"speaker": who,
               "result": {"sequence": list(sequence or [_shrug()])}}
              for who in ran]
    return Ctx(extra_players=[], cast=[], character_results={},
               reaction_results={}, reaction_loop={"rounds": []},
               interaction_loop={"rounds": rounds},
               chat={"persona_id": None})


def _scene(*, reya_room="bay"):
    return {
        "rooms": {"bay": {"name": "Bay", "adjacent": [
                      {"to": "vault", "barrier": "sealed"}]},
                  "vault": {"name": "Vault", "adjacent": [
                      {"to": "bay", "barrier": "sealed"}]}},
        "positions": {"Dana": "bay", "Reya": reya_room},
        "entities": {}, "contacts": [], "poses": {}, "stations": {},
    }


def _line(text="Reya?", target="Reya", **fields):
    row = {"type": "speech", "text": text, "intended_target": target,
           "volume": "normal"}
    row.update(fields)
    return row


def _kinds(stream):
    return [(e.get("kind"), e.get("actor")) for e in stream]


# ---------------------------------------------------------------------------
# The stream
# ---------------------------------------------------------------------------

def test_an_address_that_got_no_answer_enters_the_stream():
    stream = _outcome_event_stream(
        _ctx(), _scene(), {"sequence": [_line()]}, {}, "Dana", [], [])
    assert ("silence", "Reya") in _kinds(stream)
    entry = next(e for e in stream if e.get("kind") == "silence")
    assert entry["addresser"] == "Dana"


def test_an_answered_address_mints_nothing():
    dialogue = [{"speaker": "Dana", "exact_quote": "Reya?"},
                {"speaker": "Reya", "exact_quote": "Here."}]
    stream = _outcome_event_stream(
        _ctx(), _scene(), {"sequence": [_line()]}, {}, "Dana", dialogue, [])
    assert not [e for e in stream if e.get("kind") == "silence"]


def test_a_line_they_could_not_hear_mints_nothing():
    """A sealed bulkhead between them: the addresser does not know whether
    they were heard, so the engine may not report a refusal to answer."""
    stream = _outcome_event_stream(
        _ctx(), _scene(reya_room="vault"), {"sequence": [_line()]}, {},
        "Dana", [], [])
    assert not [e for e in stream if e.get("kind") == "silence"]


def test_a_target_the_scene_cannot_place_mints_nothing():
    """A voice that ran this beat and stands in no room: there is no
    relation to grade the delivery over, so there is no evidence it heard."""
    stream = _outcome_event_stream(
        _ctx(ran=("the ship",)), _scene(),
        {"sequence": [_line(target="the ship")]}, {}, "Dana", [], [])
    assert not [e for e in stream if e.get("kind") == "silence"]


def test_a_target_the_beat_never_ran_mints_nothing():
    """WHO WAS ASKED IS NOT IN THE DIALOGUE LOG. `build_plan` plans
    character steps from `flow.reactors` alone and the interaction loop has
    a round budget, so an addressed body can be one the beat never gave a
    turn to. Measured before this gate: an empty context, in which no
    character ran at all, yielded `[('silence', 'Reya')]` -- a refusal
    minted about somebody who was never asked to speak."""
    stream = _outcome_event_stream(
        _ctx(ran=()), _scene(), {"sequence": [_line()]}, {}, "Dana", [], [])
    assert not [e for e in stream if e.get("kind") == "silence"]


def test_an_answer_over_a_comm_channel_is_an_answer():
    """Measured on the shape an interaction_loop round takes when the
    reactor answers by radio: the stream came back
    `[('communication', 'Reya'), ('silence', 'Reya')]`, so the addresser's
    view carried Reya's answer and a sentence saying she gave none. Any
    stream entry carrying a speaker counts, whatever channel carried it."""
    stream = _outcome_event_stream(
        _ctx(sequence=[{"type": "communication", "channel": "radio",
                        "content": "that she is on her way"}]),
        _scene(), {"sequence": [_line()]}, {}, "Dana", [], [])
    assert ("communication", "Reya") in _kinds(stream)
    assert not [e for e in stream if e.get("kind") == "silence"]


def test_an_unnamed_target_and_a_wordless_line_mint_nothing():
    for event in (_line(target=""), _line(text="")):
        stream = _outcome_event_stream(
            _ctx(), _scene(), {"sequence": [event]}, {}, "Dana", [], [])
        assert not [e for e in stream if e.get("kind") == "silence"], event


def test_a_blocked_line_was_never_spoken_so_nobody_declined_to_answer():
    event = _line(event_id="hail", phase_id="hail", commitment="contestable")
    res = {"sequence_dispositions": [{"event_id": "hail", "status": "blocked"}]}
    stream = _outcome_event_stream(
        _ctx(), _scene(), {"sequence": [event]}, res, "Dana", [], [])
    assert not [e for e in stream if e.get("kind") == "silence"]


def test_a_character_addresser_gets_one_too():
    """BEING IGNORED IS A SOCIAL FACT, and a character has a view for it to
    arrive in exactly like a player does -- the per-observer loop has always
    routed this percept by `_is_the_observer`, so the addresser being a
    character was never the thing that made it unrenderable. The rule the
    docstring states is universal; player-only was one instance of it."""
    scene = _scene()
    sequences = [("Reya", [_line(target="Dana")], False),
                 ("Dana", [_shrug()], False)]
    entries = _unanswered_addresses(scene, sequences, [], {})
    assert [e["actor"] for e in entries] == ["Dana"]
    assert entries[0]["addresser"] == "Reya"


def test_an_aliased_target_resolves_to_the_body_the_view_is_keyed_by():
    """`display_map` is an exact lookup on the scene body name, so a target
    the player spelled as an alias passed every gate here and then minted
    nothing at all downstream. The name that goes out is the one the beat's
    own declarations use."""
    scene = _scene()
    scene["entities"] = {"reya_ent": {"name": "Reya",
                                      "aliases": ["the medic"]}}
    sequences = [("Dana", [_line(target="the medic")], True),
                 ("Reya", [_shrug()], False)]
    assert [e["actor"] for e in
            _unanswered_addresses(scene, sequences, [], {})] == ["Reya"]


def test_one_entry_per_pair_however_many_times_they_were_addressed():
    stream = _outcome_event_stream(
        _ctx(), _scene(),
        {"sequence": [_line("Reya?"), _line("Reya, answer me.")]},
        {}, "Dana", [], [])
    assert len([e for e in stream if e.get("kind") == "silence"]) == 1


def test_addressing_yourself_is_not_a_silence():
    stream = _outcome_event_stream(
        _ctx(), _scene(), {"sequence": [_line(target="Dana")]}, {},
        "Dana", [], [])
    assert not [e for e in stream if e.get("kind") == "silence"]
    # And for a character, who does appear among the bodies that ran.
    sequences = [("Reya", [_line(target="Reya")], False)]
    assert _unanswered_addresses(_scene(), sequences, [], {}) == []


# ---------------------------------------------------------------------------
# The percept
# ---------------------------------------------------------------------------

def test_the_percept_says_the_fact_and_nothing_else():
    percept = composer.silence_percept("Reya", order_key=3)
    assert percept.kind == "speech"
    assert percept.channel == "hearing"
    assert percept.fidelity == "silence"
    assert percept.order_key == 3
    assert not percept.data.get("body")
    text = composer.render_view([percept], mode="character").text
    assert text == "Reya says nothing."
    # No reason, and no quotation of a line that was never said.
    assert '"' not in text


def test_a_label_this_observer_does_not_have_mints_nothing():
    assert composer.silence_percept("") is None
    assert composer.silence_percept(None) is None


def test_the_memory_sentence_does_not_quote_an_empty_line():
    """The episode renderer's speech branch quotes `data["body"]`, which a
    silence has none of -- without its own branch a remembered silence read
    `I heard Reya say: ""`."""
    episode = composer.render_episode([composer.silence_percept("Reya")])
    text = episode[0] if isinstance(episode, tuple) else episode
    assert '""' not in text
    assert "Reya" in text


# ---------------------------------------------------------------------------
# The whole stage: it reaches the addresser and nobody else
# ---------------------------------------------------------------------------

def _silent_beat(temp_db):
    """Sabine says "Reya?" across a lit lounge; Reya runs and says nothing.

    She DECLARES -- an action, not a word. A reactor the beat never ran is a
    body nobody has evidence about, and mints no silence at all; the fact
    the addresser has is that the person who had the beat did not answer."""
    import json
    import time

    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import (default_character_data,
                                        default_persona_data)

    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Sabine", json.dumps(default_persona_data("Sabine")), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Silence", "", time.time(), persona_id))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Reya", json.dumps(default_character_data("Reya")), "{}",
         time.time(), "char_silence"))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "Station", "time": "day",
        "rooms": {"lounge": {"name": "The Lounge", "adjacent": [],
                             "light": "lit"}},
        "positions": {"Sabine": "lounge", "Reya": "lounge"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {"Sabine": ["Reya"], "Reya": ["Sabine"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "Reya?", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Silence", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="Reya?", created=time.time()),
        cast=cast, input="Reya?")
    ctx.director_interpret = {
        "sequence": [{"type": "speech", "text": "Reya?",
                      "intended_target": "Reya", "volume": "normal"}],
        "speech": "Reya?", "speech_volume": "normal", "action": None,
        "flow": {"reactors": ["Reya"], "addressed_to": ["Reya"],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}}}
    ctx.character_results = {
        int(cast[0]["id"]): {"sequence": [
            {"type": "action", "attempt": "turns her head away",
             "observable": "turns her head away", "visibility": "overt"}]}}
    ctx.director_resolve = {"resolved_event": "", "dialogue_log": [
        {"speaker": "Sabine", "exact_quote": "Reya?",
         "intended_target": "Reya", "volume": "normal"}], "state_diff": {}}
    ctx["background_react"] = {"fired": False, "name": None, "reactions": [],
                               "selected": [], "mode": "background_react"}
    return ctx


def test_the_silence_reaches_the_addresser_alone(temp_db):
    """The whole stage, on the shape the item was filed for: the player
    speaks to a body within reach and it does not answer.

    Reya's own view must not carry it. She knows perfectly well that she
    said nothing; to her the fact of the beat is that she was spoken to,
    and an engine sentence telling a mind about its own silence is the
    engine narrating a decision back to the mind that made it."""
    from agents.perception import perception_outcome
    views = perception_outcome(_silent_beat(temp_db), "n0")["views"] or {}
    assert "Reya says nothing." in views["player"], views["player"]
    others = [v for pid, v in views.items() if pid != "player"]
    assert others and all("says nothing" not in v for v in others), others
    # And the line she was told about is still the line that was spoken.
    assert any('Sabine says: "Reya?"' in v for v in others), others
