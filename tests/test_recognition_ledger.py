"""One recognition ledger, one answer to "does this text name this person".

`known` is the only per-mind recognition ledger the engine has, and two commit
domains write it. They were asking the same two questions with different
machinery:

  * WHO EXISTS. `commit_memory` builds its roster from the cast, the player
    AND every Charter body standing in the world; `commit_mapping` built its
    from the cast and the player only. A Charter body is a real, co-located
    identity that is absent from `chat_chars` by construction, so an
    introduction naming one could never resolve and was dropped in silence.
  * DOES THIS TEXT NAME THIS PERSON. `commit_memory` answers it with the
    address index (`_address_forms`: a surname, a titled variant, an
    honorific), which is how a name spoken aloud is recognised. `commit_
    mapping` answered it with `casefold` equality and then a raw substring
    test, which cannot see that "Lieutenant Oyelaran" is Sabine Oyelaran.

MEASURED, chat 98 (the 40-turn Enterprise-D run), every row below copied from
that database:

  turn 1  six `ok: true` introductions; two survived. Three of the four
          dropped were dropped on the titled form alone --
          `{"who": "Data", "learns": "Lieutenant Oyelaran", "ok": true}`.
  turn 16 the player says her own name aloud to a table of strangers. Five
          `ok: true` introductions, INCLUDING the reverse edge
          `{"who": "<a Charter body>", "learns": "<the player>"}`. All five
          dropped: neither end resolved against a cast-only roster.
  turn 37 twenty-one turns later she still calls that man "the unfamiliar
          person", and `known` holds no row for any Charter body at all --
          so `_presence_recognizes` returned the empty set on every beat of
          the run and no presence could use her name either.
"""

from __future__ import annotations

import inspect
import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_mapping
from story.character_schema import default_character_data, default_persona_data
from world.charter_runtime import save_registry


PLAYER = "Sabine Oyelaran"
CREW = "Data"
PRESENCE = "lieutenant_commander Jenanez Laiez"


def _story(temp_db, *, presence_place="ten_forward"):
    """A player and one registered colleague in a room, and two Charter bodies
    -- one in the room with them, one two decks away."""
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Recognition", "", time.time(), persona_id))
    sheet = default_character_data(CREW)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (CREW, json.dumps(sheet), "{}", time.time(), "crew"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (cid, char_id, "active", "{}"))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    save_registry(cid, {"ship": {
        "key": "ship",
        "naming": {
            "formal_format": "{title} {name}",
            "titles": {"ranks": {
                "lieutenant_commander": "lieutenant_commander"}},
        },
        "bodies": {
            "laiez": {"name": "Jenanez Laiez", "rank": "lieutenant_commander",
                      "place": presence_place},
            "yarardez": {"name": "Jenaam Yarardez", "rank": "lieutenant",
                         "place": "main_engineering"},
        },
    }})
    temp_db.wset(cid, "scene", {
        "rooms": {"ten_forward": {"name": "Ten Forward"},
                  "main_engineering": {"name": "Main Engineering"}},
        "positions": {PLAYER: "ten_forward", CREW: "ten_forward"},
    })
    chat = ChatData(id=cid, name="Recognition", persona_id=persona_id,
                    lorebook_id=None, scenario="", created=time.time())
    turn = TurnData(id=9016, chat_id=cid, idx=16, player_input="",
                    created=time.time())
    ctx = PipelineContext(chat=chat, turn=turn, cast=cast, input="",
                          director_resolve={"state_diff": {}, "summary": ""})
    return cid, ctx


def _commit(ctx, introductions):
    return commit_mapping(ctx, "nonce", prepared={
        "skipped": False, "mout": {},
        "introductions": introductions,
        "ops": [], "book_ops": [], "book_ids": [], "seed": "seed",
        "needs": [],
    })


def test_an_introduction_naming_a_charter_body_is_written(temp_db):
    """Chat 98 turn 16, verbatim. She says her own name to a table of people
    the story simulates but does not register; the model saw it and said so."""
    cid, ctx = _story(temp_db)
    _commit(ctx, [
        {"who": PLAYER, "learns": PRESENCE, "ok": True},
        {"who": PRESENCE, "learns": PLAYER, "ok": True},
    ])
    known = temp_db.wget(cid, "known", {})
    assert PRESENCE in (known.get(PLAYER) or [])
    assert PLAYER in (known.get(PRESENCE) or []), (
        "the reverse edge is the one the run needed: without a row of his "
        "own, _presence_recognizes returns the empty set and he can never "
        "use her name")


def test_a_titled_form_of_a_roster_name_resolves(temp_db):
    """Chat 98 turn 1, verbatim. "Lieutenant Oyelaran" is the persona's name
    wearing a rank, and the substring test could not see it."""
    cid, ctx = _story(temp_db)
    _commit(ctx, [{"who": CREW, "learns": "Lieutenant " + PLAYER.split()[-1],
                   "ok": True}])
    assert PLAYER in (temp_db.wget(cid, "known", {}).get(CREW) or [])


def test_an_introduction_across_two_rooms_is_refused(temp_db):
    """A body the engine can place in another room was not there to be
    introduced. Chat 98 turn 36: the selected presence stood in main
    engineering while she talked to a table in the lounge."""
    cid, ctx = _story(temp_db, presence_place="main_engineering")
    _commit(ctx, [
        {"who": PLAYER, "learns": PRESENCE, "ok": True},
        {"who": PRESENCE, "learns": PLAYER, "ok": True},
    ])
    assert temp_db.wget(cid, "known", {}) == {}


def test_a_row_naming_one_person_two_ways_writes_no_self_edge(temp_db):
    """Reading address forms makes this reachable for the first time: a row
    whose two ends are the same body written two ways used to fail resolution
    on one end and vanish. Now both ends resolve, and nobody is recognised
    against themselves. The two spellings are chat 98's own -- the model wrote
    "Sabine Oyelaran" and "Lieutenant Oyelaran" for her in the same turn."""
    cid, ctx = _story(temp_db)
    _commit(ctx, [{"who": "Lieutenant " + PLAYER.split()[-1],
                   "learns": PLAYER, "ok": True}])
    assert PLAYER not in (temp_db.wget(cid, "known", {}).get(PLAYER) or [])


def test_both_commit_domains_read_one_charter_projection():
    """The ownership, which is the defect: two rosters answering one question
    is how a population visible to one writer stayed invisible to the other."""
    # Named at the modules that DEFINE these two, not through the
    # `persist.commit` facade, because what is read here is each module's own
    # source; the facade's re-export is the same object under a name that says
    # nothing about where the roster is built.
    from persist import commit_mapping as mapping_mod
    from persist import commit_memory as memory_mod

    for owner in (getattr(mapping_mod, "commit_mapping"),
                  getattr(memory_mod, "prepare_memory_commit")):
        source = inspect.getsource(owner)
        assert "charter_recognition_projection(" in source, owner.__name__
        assert "charter_speaker_records(" not in source, (
            f"{owner.__name__} builds its own Charter roster by hand")
