"""A background presence knows what its body perceived, and nothing else.

Measured on the tavern probe (2026-10-20, chat 2). The barman Hollis is a
background presence. Turn 6: the player asked Davey, across their table at
an ordinary level, about "the woman with the scar through her eyebrow" --
and Hollis's payload carried the question verbatim, which he quoted back.
On the turn's own checkpoint scene the cast's hearing gate gives him, 7.2
paces off in the taproom's 68 dB din, only pieces (`din_bystander`): his
readers built the relation with no field of the beat at all, so the crowd
that made the din was not in it. Turn 7: two whispers reached him as
nothing, so his payload fell through to the beat's omniscient prose, which
carried an event out in the street ("two revenue men in plain coats walk up
Market Strand") that no view in the taproom held; he spoke of the revenue
men.

The class: every line reaches a presence through the hearing rule as it
reaches the cast (the din, whom it was spoken to, the ear rung; a fragment
as its pieces, never the sentence), every act through sight, and a
happening no body performs only where the cast's gate would show it to a
body standing where the presence stands. The beat's prose is never a
presence's view. The same gate grades the address it must answer and the
reply debt the commit writes, and the lines a conversation thread's people
are handed.
"""

from __future__ import annotations

import json
import time

import agents.background as background
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import _character_address_of, track_background_presences

PLAYER, DAVEY, HOLLIS = "Tamsin Reed", "Davey Mott", "Hollis"
QUESTION = ("Listen -- the woman with the scar through her eyebrow. Corner "
            "table, market nights. You know her? Who is she?")
STREET = ("A customs galley puts in at the quay and two revenue men in plain "
          "coats walk up the strand inspecting the boats.")


def _taproom():
    """Chat 2's taproom in miniature (the din test's own tavern,
    `test_a_din_reaches_an_addressee_beyond_reach`): ten paces by eight, the
    player and Davey at one table, Hollis at the bar nine paces off, and the
    strand outside behind a shut door."""
    cells = {PLAYER: (1, 1), DAVEY: (2, 1), HOLLIS: (8, 6)}
    return {
        "location": "The Gull and Anchor", "time": "evening",
        "rooms": {
            "tap": {"name": "the taproom", "exposure": "enclosed",
                    "extent": {"w": 10, "d": 8}, "anchors": {},
                    "adjacent": [{"to": "strand", "barrier": "closed_door"}]},
            "strand": {"name": "the strand", "exposure": "open",
                       "adjacent": [{"to": "tap", "barrier": "closed_door"}]}},
        "positions": {k: "tap" for k in cells},
        "stations": {k: {"cell": list(v)} for k, v in cells.items()},
        "entities": {}, "poses": {}, "orientation": {}, "contained": {},
        "attire": {}, "overlays": {},
    }


def _ctx(temp_db, *, crowd="a few dozen", sequence=None, resolve=None,
         presences=None):
    persona = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                         (PLAYER, json.dumps({"name": PLAYER}), "{}"))
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                     "VALUES(?,?,?,?)", ("Gull", "", time.time(), persona))
    temp_db.wset(cid, "scene", _taproom())
    if crowd:
        temp_db.wset(cid, "crowds", [{"uid": "drinkers", "room_uid": "tap",
                                      "band": crowd}])
    temp_db.wset(cid, "background_presences", presences or {
        HOLLIS: {"first_turn": 0, "sketch": {"station_room": "tap",
                                             "role_hint": "the barman"}}})
    turn = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                      "VALUES(?,?,?,?)", (cid, 3, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Gull", persona_id=persona, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn, chat_id=cid, idx=3, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_interpret = {"sequence": sequence or [], "flow": {}}
    ctx.director_resolve = resolve or {"resolved_event": "", "dialogue_log": []}
    return ctx


def _line(text, *, to, volume="normal", speaker=PLAYER):
    return {"speaker": speaker, "exact_quote": '"%s"' % text, "volume": volume,
            "intended_target": to, "visibility": "overt", "conceal_from": []}


def _asked_davey():
    return [{"type": "speech", "text": QUESTION, "volume": "normal",
             "targets": [DAVEY], "visibility": "overt", "conceal_from": []}]


def _payload(ctx, monkeypatch, *, player_addressed=False):
    """The presence's payload as `background_react` hands it to the model."""
    monkeypatch.setattr(background, "pick_voice_demand", lambda *a, **k: {
        "picks": [HOLLIS], "meta": {HOLLIS: {"addressed": player_addressed,
                                             "player_addressed": player_addressed}}})
    seen = []

    def model(role, step_key, system, payload, **kwargs):
        seen.append(payload)
        return {"reacts": False}

    monkeypatch.setattr(background, "_agent_json", model)
    background.background_react(ctx, nonce=0)
    (payload,) = seen
    return payload


def test_a_question_across_a_table_reaches_the_bar_in_pieces(temp_db, monkeypatch):
    """Turn 6: the player's line to Davey, at the bar nine paces off in a
    din. The barman catches pieces of it, as the cast's gate gives a
    bystander there -- never the question."""
    ctx = _ctx(temp_db, sequence=_asked_davey(),
               resolve={"resolved_event": "", "dialogue_log": [
                   _line(QUESTION, to=DAVEY)]})
    beat = _payload(ctx, monkeypatch)["beat"]
    for field in ("player_declaration", "resolved_event"):
        assert QUESTION not in beat[field], field
        assert "eyebrow. Corner table" not in beat[field], field
    assert beat["player_declaration"].startswith("an indistinct remark: ...")
    assert beat["resolved_event"].startswith("an indistinct exchange from ")


def test_with_no_din_the_question_carries_across_the_room(temp_db, monkeypatch):
    """The complement: in a quiet taproom a voice in one room is heard in
    full (the hearing rule's `same_room`), so the barman has the words."""
    ctx = _ctx(temp_db, crowd=None, sequence=_asked_davey(),
               resolve={"resolved_event": "", "dialogue_log": [
                   _line(QUESTION, to=DAVEY)]})
    beat = _payload(ctx, monkeypatch)["beat"]
    assert QUESTION in beat["player_declaration"]
    assert QUESTION in beat["resolved_event"]


def test_the_beats_prose_is_never_the_presences_view(temp_db, monkeypatch):
    """Turn 7: no line reached him, and the resolve's prose carried an event
    out in the street. What he is given is what he SAW: the act at the
    table, from its typed row -- not the street, and not the prose."""
    rows = [{"chrono_id": 1, "source_entity_id": DAVEY,
             "event": "Davey sets the second tankard down over the letter.",
             "observable": "sets a tankard down over a folded paper on the table",
             "targets": [], "visibility": "overt", "conceal_from": [],
             "categories": ["inventory"]},
            {"chrono_id": 2, "source_entity_id": "world", "event": STREET,
             "observable": "a customs galley puts in and two men walk up the "
                           "strand inspecting the boats",
             "targets": ["strand"], "visibility": "overt", "conceal_from": [],
             "categories": []}]
    ctx = _ctx(temp_db, resolve={
        "resolved_event": "Davey Mott: Davey sets the second tankard down over "
                          "the letter. world: " + STREET,
        "dialogue_log": [_line("Who paid you?", to=PLAYER, volume="whisper",
                               speaker=DAVEY)],
        "ledgers": rows})
    seen = _payload(ctx, monkeypatch)["beat"]["resolved_event"]
    assert "sets a tankard down over a folded paper" in seen
    assert "revenue" not in seen and "galley" not in seen
    assert "Who paid you" not in seen


def test_an_address_he_caught_in_pieces_is_not_an_address_he_answers(temp_db, monkeypatch):
    """A line aimed at the barman, at an ordinary voice from nine paces off
    in the din, arrives in pieces; the address readers took it whole on a
    room-to-room read, so he was handed the words to answer."""
    order = "Two more of the dark, when you've a minute"
    ctx = _ctx(temp_db, resolve={"resolved_event": "", "dialogue_log": [
        _line(order, to=HOLLIS)]})
    payload = _payload(ctx, monkeypatch)
    assert not payload["beat"]["addressed_by"]
    assert order not in json.dumps(payload["beat"])
    # Raised, with her face to him, it carries -- and he is asked to answer.
    ctx = _ctx(temp_db, resolve={"resolved_event": "", "dialogue_log": [
        _line(order, to=HOLLIS, volume="loud")]})
    sc = background._beat_scene(ctx)
    hears = background.presence_hearing(ctx, sc, HOLLIS, "tap")
    assert _character_address_of(ctx.director_resolve, HOLLIS,
                                 {PLAYER.casefold()}, sc, "tap",
                                 hears=hears)["exact_quote"] == '"%s"' % order


def test_an_act_it_cannot_see_is_not_its_beat(temp_db):
    """Before the resolve, the declared beat was everyone's observables in
    one string, delivered whole to a presence standing in the player's
    room. A body declared acting out on the strand, behind a shut door, is
    not seen from the bar; the one at the table is."""
    ctx = _ctx(temp_db)
    sc = _taproom()
    sc["positions"]["Abel Trask"] = "strand"
    decls = [{"name": "Abel Trask", "sequence": [
                 {"type": "action", "attempt": "signals the galley",
                  "observable": "waves a lantern at the galley",
                  "visibility": "overt", "conceal_from": []}]},
             {"name": DAVEY, "sequence": [
                 {"type": "action", "attempt": "hides the letter",
                  "observable": "sets his tankard down over a paper",
                  "visibility": "overt", "conceal_from": []}]}]
    beat = background._provisional_beat(ctx, {"ledgers": []}, decls, PLAYER)
    seen = background._beat_for_presence(beat, sc, "tap", HOLLIS, beat_room="tap")
    assert "sets his tankard down over a paper" in seen
    assert "lantern" not in seen


def test_the_reply_debt_carries_only_what_reached_him(temp_db):
    """The commit's debt quote is handed to the presence next beat as the
    address it owes an answer to. It was the player's whole overt text --
    every line she said to anyone -- past a room-level check; it is now what
    of her beat his body caught."""
    secret = "The letter is for Isolde. Nobody else."
    ctx = _ctx(temp_db, crowd=None, sequence=[
        {"type": "speech", "text": "Hollis! Two more of the dark!",
         "volume": "loud", "targets": [HOLLIS], "visibility": "overt",
         "conceal_from": []},
        {"type": "speech", "text": secret, "volume": "whisper",
         "targets": [DAVEY], "visibility": "overt", "conceal_from": []}])
    ctx.director_interpret["flow"] = {"addressed_to_refs": [HOLLIS]}
    ctx["background_react"] = {"selected": [], "reactions": []}
    track_background_presences(ctx, nonce=0)
    ledger = temp_db.wget(ctx.chat.id, "background_presences", {})
    (record,) = [r for r in ledger.values() if r.get("name") == HOLLIS
                 or r.get("sketch", {}).get("role_hint") == "the barman"]
    debt = record.get("pending_reply") or {}
    assert "Two more of the dark" in debt.get("quote", "")
    assert "Isolde" not in debt.get("quote", "")


def test_a_thread_is_handed_only_the_lines_its_people_heard(temp_db, monkeypatch):
    """The thread's shared payload took every overt line of the beat whole,
    wherever and however quietly it was said: a question whispered at the
    player's table reached the two at the bar nine paces off."""
    ctx = _ctx(temp_db, crowd=None)
    ctx.language = "en"
    sc = _taproom()
    sc["positions"]["Pot Girl"] = "tap"
    sc["stations"]["Pot Girl"] = {"cell": [9, 6]}
    temp_db.wset(ctx.chat.id, "scene", sc)
    beat = {"dialogue_log": [
        _line("Two pots, the good barrel.", to=HOLLIS, volume="loud"),
        _line(QUESTION, to=DAVEY, volume="whisper")]}
    seen = {}

    def model(role, step_key, system, payload, **kwargs):
        seen["payload"] = payload
        return {"lines": [], "hands_over": None, "hands_over_by": "", "done": False}

    monkeypatch.setattr(background, "_agent_json", model)
    monkeypatch.setattr(background, "_place_block", lambda ctx, room, **k: {"room": room})
    monkeypatch.setattr(background, "_common_knowledge", lambda ctx, room: [])
    monkeypatch.setattr(background, "get_prompt", lambda pid, language=None: pid)
    thread = {"room": "tap", "participants": [HOLLIS, "Pot Girl"],
              "purpose": "draw two pots", "to": PLAYER, "last": []}
    background._voice_thread(ctx, beat, thread,
                             [{"name": HOLLIS, "room": "tap"},
                              {"name": "Pot Girl", "room": "tap"}], 0)
    words = [h["words"] for h in seen["payload"]["heard"]]
    assert words == ['"Two pots, the good barrel."']


def test_a_name_it_never_learned_reaches_it_as_the_body_it_sees(temp_db, monkeypatch):
    """An act's outward form names the bodies it involves, and a cast view
    admits it through the identity floor (`perception._composer_scrub_
    surface`). The barman has met nobody at the table: he sees a man set a
    tankard down in front of a woman, and is never handed her name."""
    rows = [{"chrono_id": 1, "source_entity_id": DAVEY,
             "event": "Davey sets a tankard down in front of Tamsin.",
             "observable": "sets a tankard down in front of Tamsin Reed",
             "targets": [PLAYER], "visibility": "overt", "conceal_from": [],
             "categories": ["inventory"]}]
    ctx = _ctx(temp_db, crowd=None, resolve={
        "resolved_event": "Davey sets a tankard down in front of Tamsin.",
        "dialogue_log": [], "ledgers": rows})
    seen = _payload(ctx, monkeypatch)["beat"]["resolved_event"]
    assert "sets a tankard down in front of" in seen
    assert "Tamsin" not in seen


def test_a_line_kept_from_it_by_name_is_kept_from_it(temp_db, monkeypatch):
    """Register X3: an element concealed from this presence by name, its
    `visibility` left overt -- models half-comply, and every other reader
    in this module already fails closed on `conceal_from` alone."""
    ctx = _ctx(temp_db, crowd=None, sequence=[
        {"type": "speech", "text": "Don't let the barman hear this.",
         "volume": "normal", "targets": [DAVEY], "visibility": "overt",
         "conceal_from": [HOLLIS]}])
    beat = _payload(ctx, monkeypatch)["beat"]
    assert "barman hear" not in beat["player_declaration"]
