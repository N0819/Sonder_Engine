"""Regression tests for the background_react stage (agents/background.py)
and its deterministic gate (commit.py's pick_background_reactor).

Motivation: live play showed a named background presence (no character
sheet, voiced only through the director's own resolved_event/dialogue_log
authorship) can go inert for 25+ turns despite being directly addressed,
given orders, and present at dramatic beats -- even though prompts.py's
director_resolve entry explicitly licenses voicing them. This mirrors the
"prompt compliance alone is unreliable" lesson already learned for spatial
zone-tagging and speech concealment, so the fix is the same shape: a
deterministic gate (pick_background_reactor) decides WHETHER a reaction is
warranted this beat, and only then is a cheap, stateless LLM call spent
deciding WHAT it is.
"""

from __future__ import annotations

import json
import time

from story.character_schema import default_character_data
from persist.commit import pick_background_reactor
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _make_ctx(temp_db, background_presences=None, cast_names=None, player_input=""):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    cast_rows = []
    for name in (cast_names or []):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
            (name, json.dumps(default_character_data(name)), "{}", time.time(), f"char_{name.lower()}"),
        )
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"),
        )
    cast_rows = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    temp_db.wset(chat_id, "scene", {
        "location": "x", "time": "day", "rooms": {}, "positions": {},
        "entities": {}, "attire": {}, "overlays": {},
    })
    if background_presences is not None:
        temp_db.wset(chat_id, "background_presences", background_presences)

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 5, player_input, time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=5, player_input=player_input,
                      created=time.time()),
        cast=cast_rows, input=player_input,
    )
    return ctx


def test_no_candidates_when_no_background_presences_tracked(temp_db):
    ctx = _make_ctx(temp_db, background_presences={})
    assert pick_background_reactor(ctx, {"resolved_event": "Nothing happens.", "dialogue_log": []}) is None


def test_picks_presence_with_prior_dialogue_history(temp_db):
    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": [2, 3, 4]},
    })
    dr_output = {"resolved_event": "The alarm blares through the corridor.", "dialogue_log": []}
    assert pick_background_reactor(ctx, dr_output) == "Reya"


def test_excludes_presence_already_voiced_this_beat(temp_db):
    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
    })
    dr_output = {
        "resolved_event": "Reya nods.",
        "dialogue_log": [{"speaker": "Reya", "exact_quote": '"On it."'}],
    }
    assert pick_background_reactor(ctx, dr_output) is None


def test_excludes_presence_with_no_history_and_no_beat_salience(temp_db):
    ctx = _make_ctx(temp_db, background_presences={
        "Docking Control Operator": {"first_turn": 1, "last_turn": 1,
                                      "dialogue_turns": [], "mention_turns": []},
    })
    dr_output = {"resolved_event": "The Doctor keeps cutting the panel.", "dialogue_log": []}
    assert pick_background_reactor(ctx, dr_output) is None


def test_excludes_registered_cast_member_even_if_tracked(temp_db):
    ctx = _make_ctx(
        temp_db,
        cast_names=["Reya"],
        background_presences={
            "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
        },
    )
    dr_output = {"resolved_event": "Reya says nothing.", "dialogue_log": []}
    assert pick_background_reactor(ctx, dr_output) is None


def test_prioritizes_addressed_presence_over_merely_mentioned(temp_db):
    ctx = _make_ctx(
        temp_db,
        player_input="Reya, can you cut the feed?",
        background_presences={
            "Reya": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [], "mention_turns": []},
            "Docking Control Operator": {"first_turn": 1, "last_turn": 4,
                                          "dialogue_turns": [1, 2], "mention_turns": [3, 4]},
        },
    )
    dr_output = {
        "resolved_event": "The Docking Control Operator relays a status update.",
        "dialogue_log": [],
    }
    assert pick_background_reactor(ctx, dr_output) == "Reya"


def test_background_react_stage_skips_llm_call_when_no_candidate(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={})
    ctx.director_resolve = {"resolved_event": "Nothing happens.", "dialogue_log": []}

    def fail_if_called(*a, **k):
        raise AssertionError("LLM call must not fire when the gate finds no candidate")

    monkeypatch.setattr(background, "_agent_json", fail_if_called)

    result = background.background_react(ctx, nonce=0)
    assert result["fired"] is False
    assert result["name"] is None
    assert result["dialogue_log_entry"] is None
    assert result["reactions"] == []
    assert result["selected"] == []


def test_background_react_stage_returns_fired_entry_when_gate_passes(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
    })
    ctx.director_resolve = {"resolved_event": "The alarm blares.", "dialogue_log": []}

    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {
        "reacts": True,
        "dialogue_log_entry": {
            "speaker": "someone else", "exact_quote": '"That is not good."',
            "volume": "normal", "intended_target": None, "tone": "alarmed",
        },
        "action": "grips the console.",
    })

    result = background.background_react(ctx, nonce=0)
    assert result["fired"] is True
    assert result["name"] == "Reya"
    # Speaker is forced to the gate-picked name regardless of what the LLM echoed back --
    # never trust the model to correctly self-attribute the speaker it was asked to voice.
    assert result["dialogue_log_entry"]["speaker"] == "Reya"
    assert result["dialogue_log_entry"]["exact_quote"] == '"That is not good."'
    assert result["action"] == "grips the console."


def test_payload_carries_role_hint_from_sketch(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "Doran": {"first_turn": 0, "last_turn": 4, "dialogue_turns": [1, 2],
                  "mention_turns": [],
                  "sketch": {"role_hint": "grizzled one-eyed barkeep",
                             "station_room": "taproom"}},
    })
    ctx.director_resolve = {"resolved_event": "A tankard slams down.", "dialogue_log": []}

    captured = {}

    def capture(role, name, system, payload, **kw):
        captured["payload"] = payload
        return {"reacts": True, "dialogue_log_entry": {
            "speaker": "x", "exact_quote": '"Aye."', "volume": "normal",
            "intended_target": None, "tone": "gruff",
            "visibility": "overt", "conceal_from": []}, "action": ""}

    monkeypatch.setattr(background, "_agent_json", capture)

    background.background_react(ctx, nonce=0)
    assert captured["payload"]["entity"]["role_hint"] == "grizzled one-eyed barkeep"
    assert captured["payload"]["entity"]["station_room"] == "taproom"


def test_payload_role_hint_empty_when_no_sketch(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
    })
    ctx.director_resolve = {"resolved_event": "The alarm blares.", "dialogue_log": []}

    captured = {}

    def capture(role, name, system, payload, **kw):
        captured["payload"] = payload
        return {"reacts": False, "dialogue_log_entry": None, "action": ""}

    monkeypatch.setattr(background, "_agent_json", capture)

    background.background_react(ctx, nonce=0)
    # No sketch on the record -> empty strings, never a KeyError.
    assert captured["payload"]["entity"]["role_hint"] == ""
    assert captured["payload"]["entity"]["station_room"] == ""


def test_background_react_stage_handles_reacts_false(temp_db, monkeypatch):
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1], "mention_turns": []},
    })
    ctx.director_resolve = {"resolved_event": "The alarm blares.", "dialogue_log": []}

    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {
        "reacts": False, "dialogue_log_entry": None, "action": "",
    })

    result = background.background_react(ctx, nonce=0)
    assert result["fired"] is False
    assert result["dialogue_log_entry"] is None


# --- a presence minted THIS beat can still be handed the line -------------
#
# Live, chat 72 turn 45 (turn_id 2426). The player rang a hotel service bell
# and said so in as many words: "it is a hotel. even at late hour someone
# should be staffing it, use logic and reasoning instead of assuming no one
# is there". The Director agreed and resolved it correctly -- a night clerk
# comes out of the back office, mutters "I'm coming, I'm coming... Keep your
# shirt on," and takes his place behind the desk.
#
# The engine deleted him. `director_may_voice` routed his lines to this
# stage (correct: he is person-shaped and deserves his own call), and the
# hand-off silently failed, because `pick_background_reactors` iterates
# `background_presences` -- and a presence MINTED THIS BEAT is not in that
# store yet. `track_background_presences` writes it at commit, after this
# gate has already run. So the one presence the Director actively chose to
# speak for was the one class of presence the forced pick could never see.
#
# The result was not a warning. It was a story that would not resolve: the
# narrator's last line was "Somewhere beyond the desk, a door might shift.
# Or not." -- against a player who had explicitly asked for the opposite.

def test_a_presence_minted_this_beat_is_forced_into_the_picks(temp_db):
    """The routed name has no record yet, by construction. Requiring one is
    requiring the presence to have existed before the beat that created it.
    """
    from persist.commit import pick_background_reactors

    ctx = _make_ctx(temp_db, background_presences={},
                    player_input="I ring the bell until someone comes.")
    dr_output = {
        "resolved_event": (
            "A disheveled man in a wrinkled uniform steps into the lobby, "
            "rubbing his eyes, and moves behind the desk."),
        # The line was stripped by the ownership guard; this list is the
        # hand-off it wrote in its place.
        "dialogue_log": [],
        "routed_to_background": ["Night Clerk"],
        # The live shape: the Director MINTED him in the same beat, as a
        # `character` entity with a position. That is the Director doing
        # exactly its job -- it owns what exists -- and it must not be read
        # as evidence the line is already handled, or the two halves of the
        # ownership split race and the mint silences the hand-off.
        "state_diff": {
            "cast_changes": [
                {"who": "Night Clerk", "status": "arrived",
                 "reason": "Comes out after the bell."}],
            "entities": {"night_clerk": {
                "name": "Night Clerk", "kind": "character",
                "description": "A disheveled man in a wrinkled uniform."}},
            "positions": {"Night Clerk": "hotel_lobby"},
        },
    }

    assert pick_background_reactors(ctx, dr_output, cap=1) == ["Night Clerk"]


def test_a_routed_presence_forces_past_the_cap_like_an_address(temp_db):
    """Same rule the flow-addressed presence gets: the Director already
    judged them worth speaking for, so they do not compete for a slot."""
    from persist.commit import pick_background_reactors

    ctx = _make_ctx(temp_db, background_presences={
        "Reya": {"first_turn": 1, "last_turn": 4, "dialogue_turns": [1, 2, 3],
                 "mention_turns": [4]},
    })
    dr_output = {
        "resolved_event": "Reya looks up as a porter arrives.",
        "dialogue_log": [],
        "routed_to_background": ["Porter"],
    }

    picks = pick_background_reactors(ctx, dr_output, cap=1)
    assert "Porter" in picks


def test_a_routed_name_that_is_registered_cast_is_not_minted(temp_db):
    """The forced list is already filtered against the roster upstream, and
    this is the floor under that: a sheeted character's dropped line is a
    different failure (director-invented dialogue) and must never arrive
    here as a background presence with the same name."""
    from persist.commit import pick_background_reactors

    ctx = _make_ctx(temp_db, background_presences={}, cast_names=["Mara"])
    dr_output = {
        "resolved_event": "Mara says nothing.",
        "dialogue_log": [],
        "routed_to_background": ["Mara"],
    }

    assert pick_background_reactors(ctx, dr_output, cap=1) == []


# --- at their post, one open doorway away ---------------------------------
#
# The architectural hole, named by the owner: "they should be able to respond
# from adjacent rooms."
#
# Perception already models this correctly. `hear_level` is barrier- and
# distance-aware, an open doorway carries a voice, and `_beat_for_presence`
# runs exactly that check before handing a presence anything -- a body in the
# back office hears the lobby and is told so. What did not exist was any way
# for that body to be CHOSEN to answer: the salience gate's at-post signal
# compared rooms with `==`, so a clerk stationed one open doorway from a
# ringing bell was structurally mute. The engine granted him the perception
# and withheld the agency.
#
# Live evidence that the models kept trying to work around it, chat 72: the
# Director walked a night clerk INTO the lobby so he could speak (turn 45),
# and the spatial specialist put another at the doorway "near" the guests
# (turn 47) -- which teleported the player into the back office.

HOTEL = {
    "location": "Hotel", "time": "night",
    "rooms": {
        "lobby": {"name": "Lobby", "adjacent": [
            {"to": "office", "barrier": "open", "distance": "adjacent"},
            {"to": "vault", "barrier": "closed_door", "distance": "adjacent"}]},
        "office": {"name": "Back Office", "adjacent": [
            {"to": "lobby", "barrier": "open", "distance": "adjacent"}]},
        "vault": {"name": "Vault", "adjacent": [
            {"to": "lobby", "barrier": "closed_door", "distance": "adjacent"}]},
    },
    "positions": {"The Stranger": "lobby"},
    "entities": {}, "attire": {}, "overlays": {},
}


def _hotel_ctx(temp_db, station, player_input="I ring the bell."):
    ctx = _make_ctx(temp_db, background_presences={
        "Night Clerk": {
            "first_turn": 1, "last_turn": 1, "dialogue_turns": [],
            "mention_turns": [], "sketch": {"station_room": station,
                                            "role_hint": "The night clerk."}},
    }, player_input=player_input)
    temp_db.wset(ctx.chat.id, "scene", json.loads(json.dumps(HOTEL)))
    return ctx


def test_a_presence_at_their_post_next_door_can_be_picked(temp_db):
    """One open doorway. He can hear the bell, so he can answer it."""
    from persist.commit import pick_background_reactors

    ctx = _hotel_ctx(temp_db, "office")
    dr = {"resolved_event": "The bell rings out across the empty lobby.",
          "dialogue_log": []}

    assert pick_background_reactors(ctx, dr, cap=1) == ["Night Clerk"]


def test_a_shut_door_still_means_nobody_comes(temp_db):
    """The floor this must not break. The bar is a line heard in FULL, which
    is the bar `_character_address_of` already sets -- a closed door yields
    `fragment`, and at-post is the weakest claim any presence has on a beat.
    A muffled thump through a shut door must not summon a body; where the
    beat warrants one, the stronger signals fire regardless of room."""
    from persist.commit import pick_background_reactors

    ctx = _hotel_ctx(temp_db, "vault")
    dr = {"resolved_event": "The bell rings out across the empty lobby.",
          "dialogue_log": []}

    assert pick_background_reactors(ctx, dr, cap=1) == []


def test_a_presence_with_no_station_is_still_not_picked_on_post(temp_db):
    """Not knowing where somebody stands is a reason to deliver nothing --
    the rule `_beat_for_presence` already follows. An unplaced presence has
    no post to be at."""
    from persist.commit import pick_background_reactors

    ctx = _make_ctx(temp_db, background_presences={
        "Someone": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                    "mention_turns": []},
    }, player_input="I ring the bell.")
    temp_db.wset(ctx.chat.id, "scene", json.loads(json.dumps(HOTEL)))
    dr = {"resolved_event": "The bell rings out.", "dialogue_log": []}

    assert pick_background_reactors(ctx, dr, cap=1) == []


# --- a routed line must survive whichever path runs -----------------------
#
# Live, chat 72, turns 45 through 50: SIX beats in which the Director wrote a
# night clerk speaking and the player never heard one word of it.
#
# The Director does not author a background presence's dialogue -- it mints
# them and moves them, and the words belong to this stage. Dropping the line
# is what makes the speaker eligible again, so `routed_to_background` is a
# FORCED pick: the Director already judged them worth speaking for, and the
# hand-off exists precisely so removing a line cannot become silence.
#
# `pick_background_reactors` honours that. The scene MANAGER does not, and at
# `scene_life: "full"` the manager is the only path that runs -- when it
# declines to speak, `background_react` returns its empty result and the gate
# holding the forced pick is never consulted. `managed_presences` says in as
# many words that it is "deliberately NOT pick_background_reactors", which is
# right for salience and wrong for a hand-off: the manager is handed the
# room's populace and decides for itself, and it cannot decide about a debt
# it was never told about.
#
# So the line was deleted by a guard whose whole justification is that
# another stage will do it better, and handed to a stage that could not see
# it had been handed anything.

def test_a_routed_line_survives_a_silent_scene_manager(temp_db, monkeypatch):
    """`scene_life: full` + a manager that stays quiet must still let the
    routed presence speak. The `ambient` level already falls through for
    exactly this reason -- a directed line is withheld from the manager --
    and a ROUTED line is directed by construction."""
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "night clerk": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                        "mention_turns": [],
                        "sketch": {"role_hint": "The hotel's night clerk."}},
    }, player_input="Hello? Is anyone there?")
    temp_db.wset(ctx.chat.id, "background_config",
                 {"scene_life": "full", "max_reactors": 1})
    ctx.director_resolve = {
        "resolved_event": "Hinami calls into the dim back office.",
        "dialogue_log": [],
        "routed_to_background": ["night clerk"],
    }

    monkeypatch.setattr(background, "scene_life",
                        lambda *a, **k: background._result([], []))
    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {
        "reacts": True, "action": "straightens from the cot",
        "dialogue_log_entry": {"speaker": "night clerk",
                               "exact_quote": '"All right, all right..."',
                               "volume": "normal"}})

    out = background.background_react(ctx, nonce=0)

    assert out["selected"] == ["night clerk"], (
        "the routed hand-off never reached the gate that honours it")
    assert out["fired"] is True


def test_a_manager_that_did_speak_for_them_is_not_second_guessed(temp_db,
                                                                 monkeypatch):
    """The fall-through is for a DEBT, not a quota. A presence the manager
    already voiced has been spoken for, and asking again would give them two
    lines in one beat."""
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "night clerk": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                        "mention_turns": []},
    }, player_input="Hello?")
    temp_db.wset(ctx.chat.id, "background_config",
                 {"scene_life": "full", "max_reactors": 1})
    ctx.director_resolve = {
        "resolved_event": "Hinami calls out.", "dialogue_log": [],
        "routed_to_background": ["night clerk"],
    }
    voiced = background._result(
        ["night clerk"],
        [{"name": "night clerk", "action": "",
          "dialogue_log_entry": {"speaker": "night clerk",
                                 "exact_quote": '"Coming."'}}],
        mode="scene_life")
    monkeypatch.setattr(background, "scene_life", lambda *a, **k: voiced)

    calls = []
    monkeypatch.setattr(background, "_agent_json",
                        lambda *a, **k: calls.append(1) or {"reacts": False})

    out = background.background_react(ctx, nonce=0)

    assert out is voiced
    assert calls == [], "the manager spoke for them and was asked again anyway"


def test_the_managers_work_survives_somebody_elses_unpaid_debt(temp_db,
                                                               monkeypatch):
    """The case neither test above covers, and the one that loses work: the
    manager voiced A while C carries an unpaid routed debt. Control falls past
    both returns to the per-presence path, and `out` was never referenced
    again -- A's line, the minted blurbs and the recorded claims all dropped,
    after the `blurb_mint` call had been paid for."""
    import agents.background as background

    ctx = _make_ctx(temp_db, background_presences={
        "night clerk": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                        "mention_turns": []},
        "porter": {"first_turn": 1, "last_turn": 1, "dialogue_turns": [],
                   "mention_turns": []},
    }, player_input="Hello?")
    temp_db.wset(ctx.chat.id, "background_config",
                 {"scene_life": "full", "max_reactors": 1})
    ctx.director_resolve = {
        "resolved_event": "Hinami calls out.", "dialogue_log": [],
        "routed_to_background": ["night clerk"],
    }
    voiced = background._result(
        ["porter"],
        [{"name": "porter", "action": "",
          "dialogue_log_entry": {"speaker": "porter",
                                 "exact_quote": '"Mind the step."'}}],
        mode="scene_life:full", agent_calls=["blurb_mint", "scene_life"])
    voiced["blurbs"] = {"porter": {"manner": "brisk"}}
    voiced["claims"] = [{"by": "porter", "refs": ["the east stair"]}]
    monkeypatch.setattr(background, "scene_life", lambda *a, **k: voiced)
    monkeypatch.setattr(background, "_agent_json", lambda *a, **k: {
        "reacts": True, "action": "straightens from the cot",
        "dialogue_log_entry": {"speaker": "night clerk",
                               "exact_quote": '"All right, all right..."',
                               "volume": "normal"}})

    out = background.background_react(ctx, nonce=0)

    spoke = {r["name"] for r in out["reactions"]}
    assert spoke == {"porter", "night clerk"}
    assert set(out["selected"]) == {"porter", "night clerk"}
    assert out["blurbs"] == {"porter": {"manner": "brisk"}}
    assert out["claims"] == [{"by": "porter", "refs": ["the east stair"]}]
    assert "blurb_mint" in out["agent_calls"]
