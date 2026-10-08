"""A PITCHED LINE IS SOLVED FOR ITS LISTENER, AND A QUIET ANSWER STANDS.

The engine's vocabulary says so to the encoder (`encoder/core.txt`): a voice
aimed at one listener is `pitched` -- lowered so only they would catch it, or
raised so it reaches them. Two rules here:

* THE INTERACTION LOOP SOLVES A PITCHED LINE from its addressee's cell, as
  both perception passes do. Read by its word, `pitched` is no volume
  `hear_level` knows and fell through to an ordinary voice, so a line
  lowered for one listener reached every bystander in the round whole.

* THE CHARACTER READ-BACK'S QUIET ANSWER IS BOOKED AS ANSWERED. Scratch
  story 166 turn 4614 (the Brackwater run, 2026-10-07): Hester, outside the
  Gale house door, spoke to Tamsin inside it ("through the shut door, voice
  pitched low and even") and the read-back booked it `whisper`; Tamsin never
  received the line. A code-side rebooking -- a whisper or mutter kept from
  nobody and aimed at someone booked as `pitched` -- was built (1833958f)
  and withdrawn on review the same day: the read-back names its addressee
  in the speaker's own words, a description for a stranger, which no solver
  can place, so the line fell back to an ordinary voice the whole room
  heard; and three readers (charter observation, two background paths)
  grade the bare word and never solve it. Failing quiet is the firewall's
  direction. Asking for reach is the read-back's own question to change
  (`docs/UNBUILT_CHARACTERS.md` §6.19).

Same class as the 2026-09-14 case `test_a_line_pitched_to_its_addressee.py`
opens with ("low, so that only his table would hear" filed as a whisper and
dead four paces off), one contract later.
"""

from __future__ import annotations

import json
import time

from agents import character_bare
from mind import character_jev as jev
from story.character_schema import default_character_data
from world.spatial import (SPEECH_DB, hear_level, pitched_level_db,
                           spatial_rel_between)


def _holding():
    return jev.Holding(
        name="Hester Gale", language="en", psychology="",
        events=[], people=["Tamsin Coyle", "Abel Gale"],
        known=["Tamsin Coyle", "Abel Gale"], memories=[], aims=[],
        beliefs=[], associations=[], concerns=[], contacts=[], promises=[],
        strategies=[], heard=[], drive={}, charge=0.0)


def _reply(how="through the shut door, voice pitched low and even"):
    return {"sequence": [{
        "say": "Mrs Coyle. That reed was cut a day or two before you ever "
               "hired me.",
        "to": "Tamsin Coyle", "how": how,
        "why": "put the reed straight through the wood"}]}


def _answers(volume, kept=()):
    def one(choice):
        return {"type": "choice", "probabilities": {choice: 1.0}}
    out = {"say:0:volume": one(volume), "say:0:to:0": one("yes"),
           "say:0:to:1": one("no")}
    for p, person in enumerate(_holding().people):
        out[f"say:0:kept:{p}"] = one("yes" if person in kept else "no")
    return out


def _line(answers, reply=None):
    out, _ = character_bare.compile_bare(reply or _reply(), answers,
                                         _holding())
    return out["sequence"][0]


class TestTheBookedVolume:
    def test_a_quiet_answer_aimed_at_someone_is_booked_as_answered(self):
        for volume in ("whisper", "mutter"):
            line = _line(_answers(volume))
            assert (line["volume"], line["targets"], line["conceal_from"]) == (
                volume, ["Tamsin Coyle"], [])

    def test_words_kept_from_someone_keep_their_whisper(self):
        line = _line(_answers("whisper", kept=("Abel Gale",)))
        assert (line["volume"], line["conceal_from"]) == (
            "whisper", ["Abel Gale"])

    def test_an_ordinary_or_raised_answer_stands(self):
        for volume in ("normal", "loud", "shout"):
            assert _line(_answers(volume))["volume"] == volume

    def test_unread_a_voice_is_still_an_ordinary_one(self):
        """The owner's 2026-09-30 default is untouched: with no read-back
        a line is normal, never pitched."""
        assert _line({})["volume"] == "normal"


def _ballroom():
    """`test_a_line_pitched_to_its_addressee.py`'s rooms: the speaker at
    the card-room door, the addressee at the table through it, a bystander
    at the ballroom's far wall."""
    return {
        "location": "ballroom", "time": "night",
        "rooms": {
            "ballroom": {"name": "ballroom", "extent": {"w": 12, "d": 8},
                         "anchors": {
                             "far_wall": {"desc": "the far wall", "dir": "w"},
                             "card_room_door": {
                                 "desc": "the door through to the card room",
                                 "dir": "e"}},
                         "adjacent": [{"to": "card_room",
                                       "barrier": "open_door", "dir": "e"}]},
            "card_room": {"name": "card room", "extent": {"w": 8, "d": 6},
                          "anchors": {"near_table": {
                              "desc": "the table nearest the door",
                              "dir": "w"}},
                          "adjacent": [{"to": "ballroom",
                                        "barrier": "open_door", "dir": "w"}]},
        },
        "positions": {"Clara": "ballroom", "Crane": "card_room",
                      "Matron": "ballroom"},
        "stations": {"Clara": {"at": "card_room_door", "near": []},
                     "Crane": {"at": "near_table", "near": []},
                     "Matron": {"at": "far_wall", "near": []}},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _micro_ctx(temp_db):
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Ballroom", "", time.time()))
    ids = {}
    for name in ("Clara", "Crane", "Matron"):
        ids[name] = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}",
             time.time(), f"char_{name.casefold()}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, ids[name], "active", "{}"))
    temp_db.wset(chat_id, "scene", _ballroom())
    # Each knows the other, so the line is attributed by name.
    temp_db.wset(chat_id, "known", {"Clara": ["Crane", "Matron"],
                                     "Crane": ["Clara", "Matron"],
                                     "Matron": ["Clara", "Crane"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) "
        "VALUES(?,?,?,?)", (chat_id, 3, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Ballroom", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=3, player_input="",
                      created=time.time()),
        cast=cast, input="")
    return ctx, ids


def test_a_pitched_line_reaches_its_addressee_in_a_micro_round(temp_db):
    """The interaction loop's own delivery solves a pitched line from its
    addressee's cell, as both perception passes do. Read by its word it
    was no volume `hear_level` knows and fell through to an ordinary voice,
    so a line lowered for the man at the table reached the bystander at the
    far wall whole."""
    from agents.loops import deterministic_micro_perception

    sc = _ballroom()
    to_crane = spatial_rel_between(sc, "Crane", "Clara")
    to_matron = spatial_rel_between(sc, "Matron", "Clara")
    level = pitched_level_db(sc, "Clara", "Crane")
    assert hear_level(to_crane, "whisper") == "none", \
        "the fixture must put the addressee out of a whisper's reach"
    assert hear_level(to_matron, "normal") == "full", \
        "and the bystander inside an ordinary voice's"
    assert hear_level(to_crane, "pitched", level_db=level) == "full"
    assert hear_level(to_matron, "pitched", level_db=level) == "none"

    ctx, ids = _micro_ctx(temp_db)
    words = "The marker is under the third table. Bring it."

    def _delivered(volume):
        result = {"sequence": [{
            "type": "speech", "text": words, "volume": volume,
            "tone": "", "visibility": "overt", "conceal_from": [],
            "targets": ["Crane"],
            "event_id": f"turn:{ctx.turn.id}:character:{ids['Clara']}:0:speech",
        }]}
        views, _ = deterministic_micro_perception(
            ctx, ids["Clara"], result, sc)
        return {name: " ".join(views.get(ids[name]) or [])
                for name in ("Crane", "Matron")}

    pitched = _delivered("pitched")
    assert words in pitched["Crane"], pitched
    assert words not in pitched["Matron"], pitched
    assert words not in _delivered("whisper")["Crane"]
    assert SPEECH_DB["whisper"] <= level <= SPEECH_DB["shout"]


def test_the_card_says_a_line_carries_only_its_words():
    """The marked stage direction has a deterministic floor
    (`split_stage_directions`); an unmarked delivery note has none, because
    the only structural sign of one -- a leading clause ended by a colon --
    is spoken in 39 of the 40 stored lines that carry it (play.db, 7,311
    lines). Turn 4614's "Through the door, flat and level: Mrs Coyle. ..."
    is the one. So the card states the class, in both packs, with the
    protocol spans verbatim."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "language_packs"
    en = (root / "en/cards/system_prompts/prompts/character_bare.txt"
          ).read_text(encoding="utf-8")
    ja = (root / "ja/cards/system_prompts/prompts/character_bare.txt"
          ).read_text(encoding="utf-8")
    assert ("`say` is only the words a listener hears, and nothing about "
            "how they are said: that is `how`, with `to` whom.") in en
    assert "`say`は聞き手に聞こえる言葉だけで、どう言うかは含めません。" in ja
    for span in ("`say`", "`how`", "`to`"):
        assert span in en and span in ja
