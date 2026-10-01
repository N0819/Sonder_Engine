"""What an opening passage shows people saying and doing reaches minds.

Before 2026-09-26 the opening had no channel for it: the establish prompt
sent a quoted line to `world_facts` ("a line it quotes has been said -- a
world_fact"), `DirectorEstablish` declared no log, the tail set
`dialogue_log = []` unconditionally, the opening's perception composed only
the standing scene, and the commit filed a mind's own conduct only from a
character step, which turn 0 never runs. So nothing said at an opening --
a card character's own greeting included -- reached any memory; each
mind's only turn-0 row was its view of the room. The owner, 2026-09-26: "it
is not correctly commiting intro dialogu and actions to character
memoreis esepcailly in greetings."

The chain these tests hold, stage by stage: the establish tail TRANSCRIBES
the Director's `sequence` (a line stands only where the passage quotes it)
into the `dialogue_log` every reader keys on; the opening's perception hears
those lines through the ordinary gates; the commit files each mind's own
words and acts as its own conduct.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

import agents.director as director


def _establish_ctx(temp_db, *, scenario="", seed=""):
    from tests.director_fakes import _make_ctx
    ctx = _make_ctx(temp_db, player_input=seed)
    ctx.chat.scenario = scenario
    return ctx


# ---- the tail transcribes, it never invents -----------------------------------

def test_a_line_the_passage_quotes_is_transcribed_even_split_around_its_verb(temp_db):
    ctx = _establish_ctx(temp_db, scenario=(
        'Mara looks up from the lamp. "The lamp is cold," she says, "and the oil is gone."'))
    out = {"sequence": [
        {"who": "Mara", "type": "speech", "text": "The lamp is cold, and the oil is gone.",
         "volume": "normal", "to": "The Stranger"},
        {"who": "Mara", "type": "action", "act": "set down the empty oil can"},
    ]}
    log, seq = director._opening_conduct(ctx, out, "The Stranger")
    assert [(d["speaker"], d["exact_quote"]) for d in log] == [
        ("Mara", '"The lamp is cold, and the oil is gone."')]
    assert log[0]["intended_target"] == "The Stranger"
    assert [(s["who"], s["type"]) for s in seq] == [("Mara", "speech"), ("Mara", "action")]
    assert seq[1]["attempt"] == "set down the empty oil can"


def test_a_line_the_passage_does_not_quote_is_dropped_and_said_so(temp_db):
    """Live, 2026-09-26: a harbour opening whose passage quoted nobody gave
    both of its characters a line, filed as a world fact. A person's words
    are their own; the Director transcribes, never authors."""
    ctx = _establish_ctx(temp_db, scenario="The tide is out. Mara watches a boat come in.")
    out = {"sequence": [
        {"who": "Mara", "type": "speech", "text": "If that's you, I'm not in the mood."},
        {"who": "Mara", "type": "action", "act": "watch the boat come in"},
    ]}
    log, seq = director._opening_conduct(ctx, out, "The Stranger")
    assert log == []
    assert [s["type"] for s in seq] == ["action"]
    assert any("not transcribed" in w for w in ctx.warnings)


def test_the_players_own_seed_is_a_passage_too(temp_db):
    ctx = _establish_ctx(temp_db, seed='The Stranger steps in and says, "Evening, keeper."')
    out = {"sequence": [{"who": "The Stranger", "type": "speech", "text": "Evening, keeper."}]}
    log, _seq = director._opening_conduct(ctx, out, "The Stranger")
    assert [d["speaker"] for d in log] == ["The Stranger"]


def test_a_short_line_must_match_whole_words(temp_db):
    """"No." is not in "north": the match is on word boundaries."""
    ctx = _establish_ctx(temp_db, scenario="Mara faces north and says nothing.")
    out = {"sequence": [{"who": "Mara", "type": "speech", "text": "No."}]}
    log, _seq = director._opening_conduct(ctx, out, "The Stranger")
    assert log == []


# ---- the opening's perception hears the lines ----------------------------------

def _opening_story(temp_db):
    """Reya and Oskar in the hall with the player; Pell in the cellar, behind
    a wall. Reya says one line at the opening."""
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Ferry", "", time.time()))
    ids = {}
    for name in ("Reya", "Oskar", "Pell"):
        sheet = default_character_data(name)
        ids[name] = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), "char_" + name.casefold()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
                   (chat_id, ids[name], "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "Ferry house", "time": "night",
        "rooms": {"hall": {"name": "the hall", "adjacent": [{"to": "cellar", "barrier": "wall"}]},
                  "cellar": {"name": "the cellar", "adjacent": [{"to": "hall", "barrier": "wall"}]}},
        "positions": {"The Stranger": "hall", "Reya": "hall", "Oskar": "hall", "Pell": "cellar"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                     "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                         (chat_id, 0, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Ferry", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=0, player_input="", created=time.time()),
        cast=cast, input="")
    ctx.director_establish = {
        "state_diff": {}, "sensory_events": [], "entity_states": {},
        "dialogue_log": [{"speaker": "Reya", "exact_quote": '"The ferry left an hour ago."',
                          "volume": "normal", "intended_target": None, "tone": "",
                          "visibility": "overt", "conceal_from": []}],
        "sequence": [{"who": "Reya", "type": "speech", "text": "The ferry left an hour ago."},
                     {"who": "Reya", "type": "action", "attempt": "bar the door"}],
    }
    return ctx, ids


def test_those_in_earshot_hear_an_opening_line_and_the_speaker_does_not_perceive_her_own(temp_db):
    from agents.perception import perception_establish
    ctx, ids = _opening_story(temp_db)
    views = perception_establish(ctx, "n0")["views"]
    assert "The ferry left an hour ago" in views[str(ids["Oskar"])]
    assert "The ferry left an hour ago" in views["player"]
    assert "The ferry left an hour ago" not in views[str(ids["Reya"])]
    assert "The ferry left an hour ago" not in views[str(ids["Pell"])], "a wall carries no normal line"


# ---- the commit files a mind's own conduct from the opening ---------------------

def test_a_mind_remembers_what_it_said_and_did_at_the_opening(temp_db, monkeypatch):
    """The greeting case: the card character speaks and acts in the passage,
    and turn 0 runs no character step -- its own words and acts are filed as
    the row a beat's own sequence makes. Nobody else gets a row for them."""
    from persist.commit import prepare_memory_commit
    from tests.test_own_conduct_memory import _capture_batch
    ctx, ids = _opening_story(temp_db)
    captured = _capture_batch(monkeypatch)
    ctx.perception_establish = {"views": {str(i): "You are in the hall." for i in ids.values()}}
    prepare_memory_commit(ctx)
    # In the turn's one memory, beside what the mind perceived (2026-09-30).
    selves = [m for m in captured["memories"] if "What I did:" in m["content"]]
    assert [(m["char_id"], m["content"]) for m in selves] == [
        (ids["Reya"], "What I experienced: You are in the hall.\n"
                      "What I did: I said 'The ferry left an hour ago.' Then I tried to bar the door.")]
    assert selves[0]["turn_idx"] == 0
