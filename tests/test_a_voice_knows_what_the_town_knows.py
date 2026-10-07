"""A background voice knows what anyone living here knows -- and no more.

`_place_block` promised "GENERAL WORLD KNOWLEDGE ... what everybody in the
setting knows", and its `world_knowledge` stopped carrying any when lore
filing for rooms was retired (2026-09-03): the helper now returns the room's
own prose. Measured (scratch story 165, turn 4581, 2026-10-07): told the
search bell was ringing, a reeve whose payload held no word of the town's
bells called it "the wreck bell. Something's come up on the Corvina."

The voice now reads the story's lore through the SAME gate a character's
`world_knowledge` passes, as an ordinary person: common depth, no circle,
ranges honoured, and a registered person named only where every reader may
know them. Adversarial on purpose: a kept fact, a Director-only entry and
another room's local fact must never arrive.
"""

import json
import time

import agents.background as background
from core.pipeline_context import ChatData, PipelineContext, TurnData
from mind.memory import add_lore, ensure_chat_canon_book
from story.character_schema import default_character_data, default_persona_data

VEC = [0.1, 0.2, 0.3]


def _ctx(db):
    pid = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                ("Nia", json.dumps(default_persona_data("Nia")), "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
                ("Town", "", time.time(), pid))
    key = db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                "VALUES(?,?,?,?,?)",
                ("Rin", json.dumps(default_character_data("Rin")), "{}",
                 time.time(), "Rin"))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, key, "active", "{}"))
    db.wset(cid, "scene", {
        "rooms": {"taproom": {"name": "Taproom", "adjacent": []},
                  "chapel_nave": {"name": "Chapel Nave", "adjacent": []}},
        "positions": {"Nia": "taproom", "Rin": "chapel_nave"},
        "entities": {}, "attire": {}, "poses": {}, "stations": {},
        "contacts": [], "overlays": {}})
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Town", persona_id=pid, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=tid, chat_id=cid, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    return ctx, cid


def _lore(book, title, content, **gate):
    return add_lore(book, title, content, title=title, embedding=VEC, **gate)


def test_only_what_anyone_here_knows_arrives(temp_db):
    ctx, cid = _ctx(temp_db)
    book = ensure_chat_canon_book(cid)
    _lore(book, "The search bell",
          "Three pulls and a pause: someone is out on the water past dark.",
          knowledge_tag="common", circles=[])
    _lore(book, "The guild's ledger", "The agent skims the premiums.",
          knowledge_tag="common", circles=["guild"])
    _lore(book, "Tide tables", "Spring tides run highest at syzygy.")
    _lore(book, "Chapel lock", "The sexton locks the nave at dusk.",
          knowledge_tag="common", knowledge_range="local",
          knowledge_locations=["chapel_nave"], circles=[])
    _lore(book, "The ferry", "Rin keeps the ferry and takes the toll.",
          knowledge_tag="common", circles=[])

    known = background._common_knowledge(ctx, "taproom")

    assert sorted(k["title"] for k in known) == ["The ferry", "The search bell"]
    assert "Rin" not in json.dumps(known), (
        "a registered person is named to a voice only where it may know them")
    assert background._place_block(ctx, "taproom")["common_knowledge"] == known
    in_chapel = {k["title"] for k in background._common_knowledge(ctx, "chapel_nave")}
    assert "Chapel lock" in in_chapel


def test_a_story_with_no_lore_hands_nothing(temp_db):
    ctx, _cid = _ctx(temp_db)
    assert background._common_knowledge(ctx, "taproom") == []


def test_the_players_briefing_is_the_casts_not_the_towns(temp_db):
    """The premise is filed public "to the cast" -- in the second person, to
    the player, with the player's errand in it. A townsperson handed it knew
    the assessor's mission before she said a word (scratch story 165, turn
    4582). Identified by the engine's own provenance stamp."""
    from persist.commit import OPENING_PREMISE_SOURCE_PREFIX
    ctx, cid = _ctx(temp_db)
    book = ensure_chat_canon_book(cid)
    add_lore(book, "", "You are the guild's assessor; find out why she sank.",
             title="The story's premise, as its author wrote it for Nia",
             knowledge_tag="common", circles=[], embedding=VEC,
             source_notes=OPENING_PREMISE_SOURCE_PREFIX + ": the scenario")
    _lore(book, "The search bell", "Three pulls and a pause.",
          knowledge_tag="common", circles=[])
    titles = [k["title"] for k in background._common_knowledge(ctx, "taproom")]
    assert titles == ["The search bell"]


def test_the_rooms_writers_entries_fit_and_this_rooms_come_first(temp_db):
    """The Writers' Room writes 850-1100 characters an entry; a budget that
    admits two handed a keeper the bells and not his own house."""
    ctx, cid = _ctx(temp_db)
    book = ensure_chat_canon_book(cid)
    for n in range(3):
        _lore(book, "Town fact %d" % n, "x" * 900, knowledge_tag="common",
              circles=[])
    _lore(book, "The taproom", "y" * 900, knowledge_tag="common", circles=[],
          knowledge_range="local", knowledge_locations=["taproom"])
    titles = [k["title"] for k in background._common_knowledge(ctx, "taproom")]
    assert titles[0] == "The taproom"
    assert len(titles) == 4
