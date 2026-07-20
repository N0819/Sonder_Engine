"""Background NPCs responding to a REGISTERED character's (or the player's)
direct address -- this beat if the single-winner gate is free, otherwise via
a one-beat `pending_reply` debt so the answer lands next turn instead of never
(commit._character_address_of / pick_background_reactor / track_background_
presences). Concealed lines never trigger; audibility is enforced when
provable; owed replies expire so none surfaces turns later."""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from commit import pick_background_reactor, track_background_presences
from pipeline_context import ChatData, PipelineContext, TurnData


def _setup(temp_db, *, cast_names=(), scene=None, presences=None,
           player_input="", turn_idx=5):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    for nm in cast_names:
        cch = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (nm, json.dumps(default_character_data(nm)), "{}", time.time(),
             f"char_{nm.lower()}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, cch, "active", "{}"),
        )
    cast_rows = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    temp_db.wset(chat_id, "scene", scene or {
        "location": "x", "rooms": {}, "positions": {}, "entities": {},
        "attire": {}, "overlays": {}})
    if presences is not None:
        temp_db.wset(chat_id, "background_presences", presences)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=cast_rows, input=player_input)
    return chat_id, ctx


def _line(speaker, target, **kw):
    entry = {"speaker": speaker, "exact_quote": f'"{speaker} to {target}."',
             "intended_target": target, "volume": "normal",
             "visibility": "overt", "conceal_from": []}
    entry.update(kw)
    return entry


def _bare(name, **extra):
    rec = {"first_turn": 1, "last_turn": 1, "dialogue_turns": [], "mention_turns": []}
    rec.update(extra)
    return rec


# ---- the gate: character-address salience ----

def test_gate_picks_presence_addressed_by_character(temp_db):
    # Reya has no dialogue history, is not in the prose, and is not in player
    # input -- pre-feature she would never qualify. A character speaking TO her
    # is now enough.
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"],
                          presences={"Reya": _bare("Reya")})
    dr = {"resolved_event": "Sara turns to the guard.",
          "dialogue_log": [_line("Sara", "Reya")]}
    assert pick_background_reactor(ctx, dr) == "Reya"


def test_concealed_address_does_not_trigger(temp_db):
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"],
                          presences={"Reya": _bare("Reya")})
    dr = {"resolved_event": "Sara mutters.",
          "dialogue_log": [_line("Sara", "Reya", visibility="concealed")]}
    assert pick_background_reactor(ctx, dr) is None


def test_address_concealed_from_the_presence_does_not_trigger(temp_db):
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"],
                          presences={"Reya": _bare("Reya")})
    dr = {"resolved_event": "Sara leans past the guard.",
          "dialogue_log": [_line("Sara", "Reya", conceal_from=["Reya"])]}
    assert pick_background_reactor(ctx, dr) is None


def test_player_address_outranks_character_address(temp_db):
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"], player_input="Reya, get down!",
                          presences={"Reya": _bare("Reya"), "Doran": _bare("Doran")})
    dr = {"resolved_event": "Sara shouts across the room.",
          "dialogue_log": [_line("Sara", "Doran")]}
    assert pick_background_reactor(ctx, dr) == "Reya"


def test_address_from_separated_room_does_not_trigger(temp_db):
    scene = {"location": "inn", "positions": {"Sara": "cellar"},
             "rooms": {"taproom": {"name": "Taproom"}, "cellar": {"name": "Cellar"}},
             "entities": {}, "attire": {}, "overlays": {}}
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"], scene=scene,
                          presences={"Reya": _bare("Reya", sketch={"station_room": "taproom"})})
    # Sara (cellar) at normal volume cannot be fully heard in the taproom.
    dr = {"resolved_event": "Sara calls out from below.",
          "dialogue_log": [_line("Sara", "Reya")]}
    assert pick_background_reactor(ctx, dr) is None


def test_address_with_unknown_station_room_still_triggers(temp_db):
    # Best-effort audibility: with no station_room the co-presence assumption
    # holds and the address is allowed through.
    scene = {"location": "inn", "positions": {"Sara": "cellar"},
             "rooms": {"cellar": {"name": "Cellar"}}, "entities": {},
             "attire": {}, "overlays": {}}
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"], scene=scene,
                          presences={"Reya": _bare("Reya")})
    dr = {"resolved_event": "Sara calls out.",
          "dialogue_log": [_line("Sara", "Reya")]}
    assert pick_background_reactor(ctx, dr) == "Reya"


# ---- next-turn fallback: the owed reply ----

def test_displaced_character_address_writes_pending_reply(temp_db):
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"], player_input="Reya, cover me!",
                          turn_idx=5,
                          presences={"Reya": _bare("Reya"), "Doran": _bare("Doran")})
    ctx.director_resolve = {"resolved_event": "Chaos erupts.",
                            "dialogue_log": [_line("Sara", "Doran")]}
    # Reya won this beat (player-addressed); Doran was addressed but not picked.
    ctx["background_react"] = {"fired": True, "name": "Reya",
                               "dialogue_log_entry": {"speaker": "Reya",
                                                      "exact_quote": '"On it."',
                                                      "volume": "normal",
                                                      "intended_target": None,
                                                      "tone": "", "visibility": "overt",
                                                      "conceal_from": []},
                               "action": ""}
    track_background_presences(ctx, nonce=0)
    presences = temp_db.wget(chat_id, "background_presences", {})
    assert presences["Doran"]["pending_reply"]["from"] == "Sara"
    assert presences["Doran"]["pending_reply"]["expires_turn"] == 7
    assert "pending_reply" not in presences["Reya"]  # the winner owes nothing


def test_gate_selects_owed_presence_next_turn(temp_db):
    chat_id, ctx = _setup(temp_db, turn_idx=6, presences={
        "Doran": _bare("Doran", pending_reply={
            "from": "Sara", "quote": '"Doran, bar the door!"', "tone": "",
            "turn": 5, "expires_turn": 7})})
    dr = {"resolved_event": "The room settles.", "dialogue_log": []}
    assert pick_background_reactor(ctx, dr) == "Doran"


def test_owed_reply_cleared_after_firing(temp_db):
    chat_id, ctx = _setup(temp_db, turn_idx=6, presences={
        "Doran": _bare("Doran", pending_reply={
            "from": "Sara", "quote": "x", "tone": "", "turn": 5, "expires_turn": 7})})
    ctx.director_resolve = {"resolved_event": "Doran answers at last.", "dialogue_log": []}
    ctx["background_react"] = {"fired": True, "name": "Doran",
                               "dialogue_log_entry": {"speaker": "Doran",
                                                      "exact_quote": '"Aye."',
                                                      "volume": "normal",
                                                      "intended_target": None,
                                                      "tone": "", "visibility": "overt",
                                                      "conceal_from": []},
                               "action": ""}
    track_background_presences(ctx, nonce=0)
    assert "pending_reply" not in temp_db.wget(chat_id, "background_presences", {})["Doran"]


def test_stale_pending_reply_ignored_and_swept(temp_db):
    chat_id, ctx = _setup(temp_db, turn_idx=9, presences={
        "Doran": _bare("Doran", pending_reply={
            "from": "Sara", "quote": "x", "tone": "", "turn": 5, "expires_turn": 7})})
    dr = {"resolved_event": "Nothing stirs.", "dialogue_log": []}
    # Gate ignores the expired debt (9 > 7) and Doran has no other salience.
    assert pick_background_reactor(ctx, dr) is None
    ctx.director_resolve = dr
    ctx["background_react"] = {"fired": False, "name": None,
                               "dialogue_log_entry": None, "action": ""}
    track_background_presences(ctx, nonce=0)
    assert "pending_reply" not in temp_db.wget(chat_id, "background_presences", {})["Doran"]


def test_selected_but_silent_presence_gets_no_debt(temp_db):
    # Doran was addressed AND picked, but chose silence -- that silence was the
    # answer; no debt is owed, and any prior debt is discharged.
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"], turn_idx=5,
                          presences={"Doran": _bare("Doran")})
    ctx.director_resolve = {"resolved_event": "Sara barks an order.",
                            "dialogue_log": [_line("Sara", "Doran")]}
    ctx["background_react"] = {"fired": False, "name": "Doran",
                               "dialogue_log_entry": None, "action": ""}
    track_background_presences(ctx, nonce=0)
    assert "pending_reply" not in temp_db.wget(chat_id, "background_presences", {})["Doran"]


def test_story_character_addresses_npc_reply_lands_next_turn(temp_db, monkeypatch):
    """Narrative walk: a registered character (Sara) calls out to a background
    NPC (Doran) on turn 5, but the player addresses someone else, so the single
    slot goes elsewhere -- and Doran answers on turn 6 via the owed reply."""
    import agents.background as background

    chat_id, ctx5 = _setup(temp_db, cast_names=["Sara"], turn_idx=5,
                           player_input="Reya, cover me!",
                           presences={"Reya": _bare("Reya"), "Doran": _bare("Doran")})
    ctx5.director_resolve = {
        "resolved_event": "Sara wheels toward the bar as the brawl spills over.",
        "dialogue_log": [_line("Sara", "Doran", exact_quote='"Doran, bar that door!"')]}

    captured = {}

    def canned(role, name, system, payload, **kw):
        captured["payload"] = payload
        who = payload["entity"]["name"]
        return {"reacts": True, "dialogue_log_entry": {
            "speaker": "x", "exact_quote": f'"{who} answers."', "volume": "normal",
            "intended_target": None, "tone": "", "visibility": "overt",
            "conceal_from": []}, "action": ""}

    monkeypatch.setattr(background, "_agent_json", canned)

    # Turn 5: player-addressed Reya wins the single slot; Doran is owed.
    ctx5["background_react"] = background.background_react(ctx5, nonce=5)
    assert ctx5["background_react"]["name"] == "Reya"
    track_background_presences(ctx5, nonce=5)
    assert temp_db.wget(chat_id, "background_presences", {})["Doran"]["pending_reply"]["from"] == "Sara"

    # Turn 6: same chat, no new address; Doran answers on the owed reply.
    turn6 = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                       (chat_id, 6, "", time.time()))
    ctx6 = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn6, chat_id=chat_id, idx=6, player_input="", created=time.time()),
        cast=ctx5.cast, input="")
    ctx6.director_resolve = {"resolved_event": "The brawl settles.", "dialogue_log": []}
    ctx6["background_react"] = background.background_react(ctx6, nonce=6)

    assert ctx6["background_react"]["name"] == "Doran"          # owed reply fires
    assert captured["payload"]["beat"]["addressed_by"]["speaker"] == "Sara"
    assert captured["payload"]["beat"]["addressed_by"]["beats_ago"] == 1
    track_background_presences(ctx6, nonce=6)
    # debt discharged
    assert "pending_reply" not in temp_db.wget(chat_id, "background_presences", {})["Doran"]


def test_track_pending_reply_is_idempotent(temp_db):
    chat_id, ctx = _setup(temp_db, cast_names=["Sara"], turn_idx=5,
                          presences={"Reya": _bare("Reya"), "Doran": _bare("Doran")})
    ctx.director_resolve = {"resolved_event": "Chaos.",
                            "dialogue_log": [_line("Sara", "Doran")]}
    ctx["background_react"] = {"fired": True, "name": "Reya",
                               "dialogue_log_entry": {"speaker": "Reya",
                                                      "exact_quote": '"On it."',
                                                      "volume": "normal",
                                                      "intended_target": None,
                                                      "tone": "", "visibility": "overt",
                                                      "conceal_from": []},
                               "action": ""}
    track_background_presences(ctx, nonce=0)
    first = temp_db.wget(chat_id, "background_presences", {})["Doran"]["pending_reply"]
    track_background_presences(ctx, nonce=0)
    second = temp_db.wget(chat_id, "background_presences", {})["Doran"]["pending_reply"]
    assert first == second
