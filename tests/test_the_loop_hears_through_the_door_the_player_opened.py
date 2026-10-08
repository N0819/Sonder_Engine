"""Every delivery inside the loop is judged against the world the player's
onset left.

`perception_act` previews the player's onset onto a copy of the scene before
it builds a single view (`preview_player_state_assertions`), so the act views
already see the door the player opened. The interaction loop then judged its
micro-rounds against the COMMITTED scene, where that door was still shut.

Measured, Brackwater (scratch play db, chat 166 turn idx 30): the player
opened the house door at onset ("Come in, Mrs Gale"), the pilot answered from
the threshold, and her brother at the table received "...them... them's...
still..." -- on the committed scene hearing graded `fragment` and sight
`none`; on the onset scene, `full` and `conduct` (`loops._beat_onset_scene`).
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data


PLAYER = "Tamsin"
LINE = "You called me in, so here is the last of what I am carrying."


def _door(barrier):
    return {
        "house": {"name": "House", "adjacent": [
            {"to": "landing", "barrier": barrier}]},
        "landing": {"name": "Landing", "adjacent": [
            {"to": "house", "barrier": barrier}]},
    }


def _story(temp_db):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Brackwater", "", time.time(), persona_id))
    ids = {}
    for name in ("Hester", "Abel"):
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.lower()}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    # They know each other: the line is attributed by name either way, so
    # the only thing the door can change is how much of it carries.
    temp_db.wset(chat_id, "known", {"Abel": ["Hester"], "Hester": ["Abel"]})
    temp_db.wset(chat_id, "scene", {
        "location": "the fen", "time_of_day": "night",
        "rooms": _door("closed_door"),
        "positions": {PLAYER: "house", "Abel": "house", "Hester": "landing"},
        "entities": {}, "attire": {}, "overlays": {}})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 30, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Brackwater", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=30, player_input="",
                      created=time.time()),
        cast=cast, input="")
    return ctx, chat_id, ids


def _beat(ids, *, opens_the_door):
    interp = {"flow": {"reactors": [ids["Hester"]],
                       "addressed_to": [ids["Hester"]],
                       "resolution_flags": {}},
              "sequence": [{"type": "speech", "text": "Come in, Mrs Gale.",
                            "targets": [f"character:{ids['Hester']}"]}]}
    if opens_the_door:
        interp["onset_state_assertions"] = {"rooms": _door("open_door")}
    return interp


def _run(ctx, ids, monkeypatch):
    from agents import loops

    def step(c, cid, nonce):
        return {"sequence": [{"type": "speech", "text": LINE,
                              "volume": "normal", "targets": [PLAYER]}],
                "interaction": {"addresses": [PLAYER],
                                "expects_response": True}}

    monkeypatch.setattr(loops, "character_step", step)
    out = loops.interaction_loop(ctx, nonce=0)
    first = out["rounds"][0]
    assert first["speaker_id"] == ids["Hester"]
    return " ".join(first["delivered_views"].get(str(ids["Abel"])) or [])


def test_a_line_carries_through_the_door_the_player_opened(temp_db, monkeypatch):
    ctx, chat_id, ids = _story(temp_db)
    ctx.director_interpret = _beat(ids, opens_the_door=True)
    ctx.perception_act = {"views": {}}

    heard = _run(ctx, ids, monkeypatch)

    assert LINE in heard, f"the brother heard: {heard!r}"


def test_the_door_nobody_opened_still_muffles_it(temp_db, monkeypatch):
    """The paired case: the onset changes the channel, nothing else does."""
    ctx, chat_id, ids = _story(temp_db)
    ctx.director_interpret = _beat(ids, opens_the_door=False)
    ctx.perception_act = {"views": {}}

    heard = _run(ctx, ids, monkeypatch)

    assert LINE not in heard
    assert heard, "a shut door muffles a line; it does not erase it"


def test_the_character_steps_keep_the_committed_scene(temp_db, monkeypatch):
    """Only the loop's own deliveries read the onset: the shared snapshot
    every character step reads is left as the committed scene, and nothing
    is written back."""
    from story.scene import get_scene
    ctx, chat_id, ids = _story(temp_db)
    ctx.director_interpret = _beat(ids, opens_the_door=True)
    ctx.perception_act = {"views": {}}

    _run(ctx, ids, monkeypatch)

    snapshot = ctx._extra["character_turn_snapshot"]["scene"]
    assert snapshot["rooms"]["house"]["adjacent"][0]["barrier"] == "closed_door"
    assert get_scene(chat_id)["rooms"]["house"]["adjacent"][0]["barrier"] \
        == "closed_door"


def test_an_onset_that_cannot_be_previewed_reads_the_committed_scene(
        temp_db, monkeypatch):
    """Fails to the channels the loop always used -- never wider -- and says
    so."""
    from agents import loops
    ctx, chat_id, ids = _story(temp_db)
    ctx.director_interpret = _beat(ids, opens_the_door=True)
    ctx.perception_act = {"views": {}}

    def broken(*a, **kw):
        raise ValueError("no preview")

    monkeypatch.setattr(loops, "preview_player_state_assertions", broken)
    heard = _run(ctx, ids, monkeypatch)

    assert LINE not in heard
    assert any("onset could not be previewed" in w for w in ctx.warnings)
