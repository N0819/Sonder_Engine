"""A LINE KEPT FROM SOMEBODY IS KEPT FROM THAT BODY, whatever the speaker
calls them.

The character read-back names the people here in the speaker's own words
(the view's labels), and for a stranger that is a description -- "the tall
man in the oilskin", "the unfamiliar person". No concealment reader resolves
one: the micro round's floor reads ids, the engine handle, names and aliases
(`common._conceal_from_targets_observer`), the composer's reads a name or the
handle (`composer.concealed_from_observer`), and the resolve files an
unresolvable entry as excluding nobody. So a line a character kept from a
stranger reached that stranger, in the loop and on the page. Found by the
review of the 2026-10-08 landing (a defect older than that range; the
handle reader ba783757 added does not reach it).

`character_bare.name_concealed_bodies` reads every kept-from entry back
through the speaker's own label map (`director._bodies_addressed_as`, the
floor every payload shares) and appends the engine's handle for each body
it names. Never a name the speaker was not given; never the line's own
addressee; and a label naming two bodies hides the line from both.
"""

from __future__ import annotations

import inspect
import json
import time

from agents import character_bare
from story.character_schema import default_character_data


def _line(conceal_from, targets=("Matron",), volume="normal"):
    return {"type": "speech", "text": "The marker is under the third table.",
            "volume": volume, "tone": "", "visibility": "concealed",
            "conceal_from": list(conceal_from), "targets": list(targets)}


class TestTheHandleIsAppended:
    def test_a_label_gains_the_handle_of_the_body_it_names(self):
        out = {"sequence": [_line(["the tall man in the oilskin"])]}
        named = {"the tall man in the oilskin": ["Crane"], "Matron": ["Matron"]}
        character_bare.name_concealed_bodies(
            out, lambda label: named.get(label, []),
            {"Crane": "character:2", "Matron": "character:3"}.get)
        assert out["sequence"][0]["conceal_from"] == [
            "the tall man in the oilskin", "character:2"]

    def test_the_lines_own_addressee_is_never_excluded(self):
        out = {"sequence": [_line(["the woman at the wall"])]}
        named = {"the woman at the wall": ["Matron"], "Matron": ["Matron"]}
        character_bare.name_concealed_bodies(
            out, lambda label: named.get(label, []),
            {"Matron": "character:3"}.get)
        assert out["sequence"][0]["conceal_from"] == ["the woman at the wall"]

    def test_a_label_naming_two_bodies_hides_the_line_from_both(self):
        out = {"sequence": [_line(["the unfamiliar person"], targets=())]}
        character_bare.name_concealed_bodies(
            out, lambda label: ["Crane", "Rook"],
            {"Crane": "character:2", "Rook": "character:4"}.get)
        assert out["sequence"][0]["conceal_from"] == [
            "the unfamiliar person", "character:2", "character:4"]

    def test_an_unconcealed_element_is_untouched(self):
        out = {"sequence": [dict(_line([]), visibility="overt")]}
        character_bare.name_concealed_bodies(
            out, lambda label: ["Crane"], {"Crane": "character:2"}.get)
        assert out["sequence"][0]["conceal_from"] == []


def _ballroom():
    """The speaker at the card-room door, a stranger at the table through
    it, and the line's addressee in the ballroom beside her."""
    return {
        "location": "ballroom", "time": "night",
        "rooms": {
            "ballroom": {"name": "ballroom", "extent": {"w": 12, "d": 8},
                         "anchors": {
                             "near_door": {"desc": "beside the card-room door",
                                           "dir": "e"},
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
                     "Matron": {"at": "near_door", "near": []}},
        "entities": {}, "attire": {}, "overlays": {},
    }


def _ctx(temp_db):
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
    # Clara knows Matron and has never learned the man at the table.
    temp_db.wset(chat_id, "known", {"Clara": ["Matron"],
                                     "Crane": ["Matron"],
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


def test_a_line_kept_from_a_stranger_does_not_reach_him(temp_db):
    from agents.common import observer_label_fn
    from agents.director import _bodies_addressed_as
    from agents.loops import deterministic_micro_perception

    ctx, ids = _ctx(temp_db)
    sc = _ballroom()
    label = observer_label_fn(ctx.chat, "Clara", ctx.cast, sc)("Crane")
    assert label and label.casefold() != "crane", \
        "the fixture must leave the man at the table a stranger to Clara"

    def _delivered(conceal_from):
        result = {"sequence": [dict(
            _line(conceal_from),
            event_id=f"turn:{ctx.turn.id}:character:{ids['Clara']}:0:speech")]}
        views, _ = deterministic_micro_perception(ctx, ids["Clara"], result, sc)
        return {name: " ".join(views.get(ids[name]) or [])
                for name in ("Crane", "Matron")}

    words = _line([])["text"]
    # The defect: kept from him by the only name Clara has for him, the line
    # reached him whole.
    assert words in _delivered([label])["Crane"]

    out = {"sequence": [_line([label])]}
    handles = {"Crane": f"character:{ids['Crane']}",
               "Matron": f"character:{ids['Matron']}"}
    character_bare.name_concealed_bodies(
        out, lambda ref: _bodies_addressed_as(ctx, sc, "Clara", [ref]),
        lambda body: handles.get(body, body))
    kept = out["sequence"][0]["conceal_from"]
    assert kept == [label, f"character:{ids['Crane']}"]
    assert "Crane" not in kept, "never a name the speaker was not given"
    delivered = _delivered(kept)
    assert words not in delivered["Crane"], delivered
    assert words in delivered["Matron"], delivered


def test_the_character_step_reads_kept_from_back_before_the_floors():
    """Wired between the read-back and the addressee floor: after
    `compile_bare` writes the labels, before `strip_addressee_concealment`
    and the ids."""
    from agents import character
    source = inspect.getsource(character.character_step)
    compiled = source.index("character_bare.compile_bare(")
    named = source.index("character_bare.name_concealed_bodies(")
    stripped = source.index("strip_addressee_concealment(")
    assert compiled < named < stripped
