"""Regression tests for movement adjacency validation in director_resolve.

director_interpret derives `movement.to_room` purely from an LLM reading
of the player's declared intent, with no adjacency check. director_resolve
must not commit a position change into a room with no passable route from
the player's current room -- otherwise a misparsed declaration can
teleport the player through a wall.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

def _make_ctx(temp_db, to_room):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )

    temp_db.wset(
        chat_id,
        "scene",
        {
            "location": "Blackthorn Lighthouse",
            "time": "night",
            "rooms": {
                "keeper_room": {
                    "name": "Keeper's Room",
                    "adjacent": [
                        {"to": "lamp_room", "barrier": "open", "distance": "near"},
                        {"to": "vault", "barrier": "closed_door",
                         "distance": "near"},
                    ],
                },
                "lamp_room": {"name": "Lamp Room", "adjacent": []},
                "cliff_path": {"name": "Cliff Path", "adjacent": []},
                "vault": {"name": "Vault", "adjacent": []},
            },
            "positions": {"The Stranger": "keeper_room", "Mara": "lamp_room"},
            "entities": {},
            "attire": {},
            "overlays": {},
        },
    )

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "move", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="move",
                      created=time.time()),
        cast=cast,
        input="move",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None,
        "movement": {"to_room": to_room},
        "flow": {"reactors": [], "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx

def test_movement_into_disconnected_room_is_blocked(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, "cliff_path")  # no adjacency to keeper_room
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)

def test_movement_into_adjacent_room_is_applied(temp_db, monkeypatch):
    import agents.director as director

    ctx = _make_ctx(temp_db, "lamp_room")  # open adjacency to keeper_room
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "lamp_room"
    assert not ctx.warnings

def test_blocked_movement_strips_llm_asserted_position(temp_db, monkeypatch):
    """A blocked route must strip a position the resolve LLM itself wrongly
    asserted, not just warn while the impossible move commits anyway."""
    import agents.director as director

    ctx = _make_ctx(temp_db, "cliff_path")
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {
            "positions": {"The Stranger": "cliff_path"}}},
    )

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Blocked movement" in w for w in ctx.warnings)

def test_movement_through_closed_door_is_contested_not_forced(
    temp_db, monkeypatch,
):
    """closed_door means crossing requires an action whose outcome the
    resolve owns. When the door stays closed this beat and the resolve diff
    does not assert the move, interpret's declared intent must not be
    force-committed through it (observed live: narration described bumping
    into a sealed door while the committed position walked through)."""
    import agents.director as director

    ctx = _make_ctx(temp_db, "vault")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {})

    out = director.director_resolve(ctx, nonce=0)

    assert "The Stranger" not in out["state_diff"]["positions"]
    assert any("Contested movement" in w for w in ctx.warnings)

def test_movement_through_closed_door_honors_resolve_assertion(
    temp_db, monkeypatch,
):
    """When the resolve diff itself asserts the move (the causality owner
    decided the door was opened and crossed), the backstop lets it stand."""
    import agents.director as director

    ctx = _make_ctx(temp_db, "vault")
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {"positions": {"The Stranger": "vault"}}},
    )

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "vault"

def test_movement_through_door_opened_this_beat_is_applied(
    temp_db, monkeypatch,
):
    """A door the resolve diff opens THIS beat reads open_door in the route
    check (known_rooms carries the diff), so the ordinary 'I open the door
    and walk through' flow is not contested."""
    import agents.director as director

    ctx = _make_ctx(temp_db, "vault")
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: {"state_diff": {"rooms": {"keeper_room": {
            "name": "Keeper's Room",
            "adjacent": [
                {"to": "lamp_room", "barrier": "open", "distance": "near"},
                {"to": "vault", "barrier": "open_door", "distance": "near"},
            ],
        }}}},
    )

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["positions"]["The Stranger"] == "vault"
    assert not [w for w in ctx.warnings if "movement" in w.casefold()]

def test_resolve_player_room_prefers_canonical_position_over_declared_movement():
    """A declared `movement.to_room` is only a request for director_resolve
    to validate -- it can be rejected by the passable-route check above.
    _resolve_player_room is used by both the action-onset pass
    (perception_act, before resolution) and the outcome pass
    (perception_outcome, after it). If it trusted the declared destination
    over the actual committed scene position, perception_act would show
    the player as having already arrived before the move is even
    resolved, and perception_outcome would still show them as arrived
    even when director_resolve blocked the move.
    """
    from agents.common import _resolve_player_room

    sc = {
        "positions": {"The Stranger": "keeper_room"},
        "rooms": {
            "keeper_room": {"adjacent": [{"to": "lamp_room", "barrier": "open"}]},
            "lamp_room": {"adjacent": []},
            "cliff_path": {"adjacent": []},
        },
    }
    pers = {"name": "The Stranger"}
    interp = {"movement": {"to_room": "cliff_path"}}

    assert _resolve_player_room(sc, pers, interp, cast=[]) == "keeper_room"

def test_perception_outcome_reflects_committed_move_not_stale_onset_cache(
    temp_db, monkeypatch,
):
    """perception_act caches the player's pre-resolution room in
    ctx["_player_room"] for the onset pass. perception_outcome must
    re-resolve against the post-resolution scene rather than reusing that
    cached value, or a successful move never becomes visible in the
    player's own outcome view (and a blocked move would incorrectly keep
    showing the rejected destination).
    """
    import agents.perception as perception

    ctx = _make_ctx(temp_db, "lamp_room")
    # Simulate perception_act having already cached the pre-move room.
    ctx["_player_room"] = "keeper_room"
    ctx.director_resolve = {
        "resolved_event": "The Stranger moves to the lamp room.",
        "dialogue_log": [],
        "state_diff": {"positions": {"The Stranger": "lamp_room"}},
    }

    monkeypatch.setattr(
        perception, "_agent_json",
        lambda *a, **k: {"views": {"player": "You are in the Lamp Room."}},
    )

    perception.perception_outcome(ctx, nonce=0)

    assert ctx["_player_room"] == "lamp_room"


def _travelling_group_scene():
    return {
        "location": "Misty Mountains",
        "time": "day",
        "rooms": {
            "broad_region": {
                "name": "Misty Mountains",
                "adjacent": [{"to": "mossy_path", "barrier": "open",
                              "distance": "near"}],
            },
            "mossy_path": {
                "name": "Mossy Path",
                "adjacent": [{"to": "broad_region", "barrier": "open",
                              "distance": "near"}],
            },
        },
        "positions": {"The Stranger": "mossy_path", "Mara": "mossy_path"},
        "stations": {}, "entities": {}, "attire": {}, "overlays": {},
    }


def _travelling_group_resolve_output(with_near=True):
    stations = {
        "The Stranger": {
            "at": "torii_beam", "near": ["Mara"] if with_near else [],
        },
        "Mara": {
            "at": None, "near": ["The Stranger"] if with_near else [],
        },
    }
    lines = [
        "Everything? Now that's a plan.",
        "The universe is stuffed with wonders.",
        "After the shrine we could start with Saturn at sunset.",
        "Or tame dragons if you're feeling bold.",
    ]
    return {
        "resolved_event": (
            "The Stranger and Mara continue together through the torii gate, "
            "Mara matching the Stranger's pace just behind one shoulder."
        ),
        "dialogue_log": [
            {"speaker": "Mara", "exact_quote": f'"{line}"',
             "volume": "normal", "intended_target": "The Stranger",
             "tone": "bright", "visibility": "overt", "conceal_from": []}
            for line in lines
        ],
        # Reproduce chat 38 turn 136: room positions split the pair while the
        # same structured result places them near one another at a unique
        # anchor.  The player's coarse interpret target points backwards to a
        # broad region while the companion is put too far ahead.
        "state_diff": {
            "rooms": {
                "mossy_path": {
                    "name": "Mossy Path",
                    "adjacent": [
                        {"to": "broad_region", "barrier": "open",
                         "distance": "near"},
                        {"to": "torii_gate", "barrier": "open",
                         "distance": "near"},
                    ],
                },
                "torii_gate": {
                    "name": "Torii Gate",
                    "adjacent": [
                        {"to": "mossy_path", "barrier": "open",
                         "distance": "near"},
                        {"to": "shrine_approach", "barrier": "open",
                         "distance": "near"},
                    ],
                    "anchors": {"torii_beam": {"desc": "red crossbeam"}},
                },
                "shrine_approach": {
                    "name": "Shrine Approach",
                    "adjacent": [{"to": "torii_gate", "barrier": "open",
                                  "distance": "near"}],
                },
            },
            "positions": {
                "The Stranger": "broad_region",
                "Mara": "shrine_approach",
            },
            "stations": stations,
        },
    }


def test_anchored_near_group_reconciles_positions_and_delivers_every_line(
        temp_db, monkeypatch):
    """Live chat 38 t136: two walkers were explicitly near at the torii beam
    but committed into separate rooms. Hearing then dropped three of four
    normal-volume lines. Fresh near + one unique anchor must co-locate the
    party before perception, without relaxing hear_level itself.
    """
    import agents.director as director
    import agents.perception as perception

    ctx = _make_ctx(temp_db, "broad_region")
    temp_db.wset(ctx.chat.id, "scene", _travelling_group_scene())
    temp_db.wset(ctx.chat.id, "known", {"The Stranger": ["Mara"]})
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: _travelling_group_resolve_output(with_near=True),
    )

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"]["The Stranger"] == "torii_gate"
    assert resolved["state_diff"]["positions"]["Mara"] == "torii_gate"
    assert any("Reconciled near group" in warning for warning in ctx.warnings)

    ctx.director_resolve = resolved

    def bare_views(role, step_key, system, payload, **kwargs):
        return {"views": {
            str(p["id"]): f"You are in {p['room_name']}."
            for p in payload["perceivers"]
        }}

    monkeypatch.setattr(perception, "_agent_json", bare_views)
    player_view = perception.perception_outcome(ctx, nonce=0)["views"]["player"]

    for entry in resolved["dialogue_log"]:
        assert entry["exact_quote"].strip('"') in player_view


def test_split_positions_without_fresh_near_evidence_remain_separate(
        temp_db, monkeypatch):
    """A shared starting room is not permission to carry every bystander.
    Without a fresh near edge the resolver's explicit separation stands.
    """
    import agents.director as director

    ctx = _make_ctx(temp_db, "broad_region")
    temp_db.wset(ctx.chat.id, "scene", _travelling_group_scene())
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    monkeypatch.setattr(
        director, "_agent_json",
        lambda *a, **k: _travelling_group_resolve_output(with_near=False),
    )

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"]["The Stranger"] == "broad_region"
    assert resolved["state_diff"]["positions"]["Mara"] == "shrine_approach"
    assert not any("Reconciled near group" in warning for warning in ctx.warnings)


def _unanchored_group_scene(*, mara_room="trail_a"):
    return {
        "location": "Open Trail", "time": "day",
        "rooms": {
            "trail_a": {"name": "Lower Trail", "adjacent": [
                {"to": "trail_b", "barrier": "open", "distance": "near"},
            ]},
            "trail_b": {"name": "Middle Trail", "adjacent": [
                {"to": "trail_a", "barrier": "open", "distance": "near"},
                {"to": "trail_c", "barrier": "open", "distance": "near"},
            ]},
            "trail_c": {"name": "Upper Trail", "adjacent": [
                {"to": "trail_b", "barrier": "open", "distance": "near"},
            ]},
        },
        "positions": {"The Stranger": "trail_a", "Mara": mara_room},
        "stations": {}, "following": {}, "entities": {}, "attire": {},
        "overlays": {},
    }


def _unanchored_split_output():
    return {
        "resolved_event": (
            "The Stranger and Mara continue up the open trail together, "
            "Mara matching the Stranger's walking pace."
        ),
        "state_diff": {
            "positions": {
                "The Stranger": "trail_c",
                "Mara": "trail_b",
            },
            "stations": {
                "The Stranger": {"at": None, "near": ["Mara"]},
                "Mara": {"at": None, "near": ["The Stranger"]},
            },
        },
    }


def test_mutual_near_group_without_anchor_follows_ordinary_player_move(
        temp_db, monkeypatch):
    """Live chat 38 t137: both walkers began at the torii, both fresh station
    records said they remained near, and both walked onward, but the resolve
    wrote them into path rooms two nodes apart. The next onset then dropped
    the player's normal-volume line. Fresh mutual nearness preserves the
    ordinary group even when a path beat has no named station anchor.
    """
    import agents.director as director

    ctx = _make_ctx(temp_db, "trail_c")
    temp_db.wset(ctx.chat.id, "scene", _unanchored_group_scene())
    ctx.director_interpret.update({
        "sequence": [{
            "type": "action", "attempt": "walks up the trail",
            "observable": "walks up the trail", "verb": "walk",
            "visibility": "overt", "conceal_from": [],
        }],
        "movement": {"to_room": "trail_c", "mover": "self", "arrives": True},
    })
    monkeypatch.setattr(
        director, "_agent_json", lambda *a, **k: _unanchored_split_output())

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"] == {
        "The Stranger": "trail_c",
        "Mara": "trail_c",
    }
    assert any("ordinary player-led travel" in w for w in ctx.warnings)


def test_unanchored_near_repair_never_teleports_a_separated_companion(
        temp_db, monkeypatch):
    """A fresh but contradictory near claim cannot erase prior separation.
    Catching up remains a real movement decision, as following requires.
    """
    import agents.director as director

    ctx = _make_ctx(temp_db, "trail_c")
    temp_db.wset(
        ctx.chat.id, "scene", _unanchored_group_scene(mara_room="trail_b"))
    ctx.director_interpret.update({
        "sequence": [{
            "type": "action", "attempt": "walks up the trail",
            "observable": "walks up the trail", "verb": "walk",
            "visibility": "overt", "conceal_from": [],
        }],
        "movement": {"to_room": "trail_c", "mover": "self", "arrives": True},
    })
    monkeypatch.setattr(
        director, "_agent_json", lambda *a, **k: _unanchored_split_output())

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"]["Mara"] == "trail_b"
    assert not any("ordinary player-led travel" in w for w in ctx.warnings)


def test_unanchored_near_repair_never_grants_running_pursuit(
        temp_db, monkeypatch):
    """Mutual-near prose cannot make following all-powerful when the target
    runs. Rapid movement may create real separation and stays separated.
    """
    import agents.director as director

    ctx = _make_ctx(temp_db, "trail_c")
    temp_db.wset(ctx.chat.id, "scene", _unanchored_group_scene())
    ctx.director_interpret.update({
        "sequence": [{
            "type": "action", "attempt": "runs up the trail",
            "observable": "runs up the trail", "verb": "run",
            "visibility": "overt", "conceal_from": [],
        }],
        "movement": {"to_room": "trail_c", "mover": "self", "arrives": True},
    })
    monkeypatch.setattr(
        director, "_agent_json", lambda *a, **k: _unanchored_split_output())

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"]["Mara"] == "trail_b"
    assert not any("ordinary player-led travel" in w for w in ctx.warnings)


def test_unanchored_near_repair_respects_explicit_npc_follow_stop(
        temp_db, monkeypatch):
    """The resolver's contradictory near output cannot overrule the NPC's
    actor-owned decision to stop following before the player moves.
    """
    import agents.director as director

    ctx = _make_ctx(temp_db, "trail_c")
    scene = _unanchored_group_scene()
    scene["following"] = {
        "Mara": {"target": "The Stranger", "since_turn": 0,
                 "reason": "walking together"},
    }
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret.update({
        "sequence": [{
            "type": "action", "attempt": "walks up the trail",
            "observable": "walks up the trail", "verb": "walk",
            "visibility": "overt", "conceal_from": [],
        }],
        "movement": {"to_room": "trail_c", "mover": "self", "arrives": True},
    })
    mara_id = int(ctx.cast[0]["id"])
    ctx.character_results = {mara_id: {
        "sequence": [],
        "follow_op": {"op": "stop", "reason": "chooses to hang back"},
    }}
    monkeypatch.setattr(
        director, "_agent_json", lambda *a, **k: _unanchored_split_output())

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"]["Mara"] == "trail_b"
    assert any(op.get("op") == "stop"
               for op in resolved["state_diff"]["following_ops"])
    assert not any("ordinary player-led travel" in w for w in ctx.warnings)


def _following_scene(following=None, player_room="trail_a", mara_room="trail_a"):
    return {
        "location": "Open Trail", "time": "day",
        "rooms": {
            "trail_a": {"name": "Trail A", "adjacent": [
                {"to": "trail_b", "barrier": "open", "distance": "near"},
                {"to": "side_path", "barrier": "open", "distance": "near"},
            ]},
            "trail_b": {"name": "Trail B", "adjacent": [
                {"to": "trail_a", "barrier": "open", "distance": "near"},
            ]},
            "side_path": {"name": "Side Path", "adjacent": [
                {"to": "trail_a", "barrier": "open", "distance": "near"},
            ]},
        },
        "positions": {"The Stranger": player_room, "Mara": mara_room},
        "following": following or {}, "stations": {}, "entities": {},
        "attire": {}, "overlays": {},
    }


def _quiet_character_result(follow_op=None, verb="", attempt="waits"):
    return {
        "sequence": [{"type": "action", "attempt": attempt,
                      "observable": attempt, "verb": verb,
                      "visibility": "overt", "conceal_from": []}],
        "follow_op": follow_op,
    }


def test_npc_can_choose_to_start_following_and_travels_with_target(
        temp_db, monkeypatch):
    """The NPC owns the start decision; ordinary open-route travel then keeps
    the new group together in the same beat."""
    import agents.director as director
    from spatial import merge_scene_with_diff

    ctx = _make_ctx(temp_db, "trail_b")
    scene = _following_scene()
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    mara_id = ctx.cast[0]["id"]
    ctx.character_results[mara_id] = _quiet_character_result(
        {"op": "start", "target": "The Stranger", "reason": "go together"})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "state_diff": {"positions": {"The Stranger": "trail_b"}},
    })

    resolved = director.director_resolve(ctx, nonce=0)
    diff = resolved["state_diff"]
    merged = merge_scene_with_diff(scene, diff)

    assert diff["positions"]["Mara"] == "trail_b"
    assert merged["following"]["Mara"]["target"] == "The Stranger"


def test_npc_can_stop_following_before_target_moves(temp_db, monkeypatch):
    """An NPC's stop decision takes effect before carry; agency wins."""
    import agents.director as director
    from spatial import merge_scene_with_diff

    following = {"Mara": {"target": "The Stranger", "since_turn": 1}}
    scene = _following_scene(following)
    ctx = _make_ctx(temp_db, "trail_b")
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    mara_id = ctx.cast[0]["id"]
    ctx.character_results[mara_id] = _quiet_character_result(
        {"op": "stop", "reason": "chooses to stay"})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "state_diff": {"positions": {"The Stranger": "trail_b"}},
    })

    resolved = director.director_resolve(ctx, nonce=0)
    merged = merge_scene_with_diff(scene, resolved["state_diff"])

    assert "Mara" not in resolved["state_diff"]["positions"]
    assert "Mara" not in merged["following"]
    assert merged["positions"]["Mara"] == "trail_a"


def test_following_does_not_grant_speed_when_target_runs(temp_db, monkeypatch):
    """A sprint breaks automatic group travel. The follower is left behind,
    but the durable relation remains so they can choose whether to chase."""
    import agents.director as director
    from spatial import merge_scene_with_diff

    following = {"Mara": {"target": "The Stranger", "since_turn": 1}}
    scene = _following_scene(following)
    ctx = _make_ctx(temp_db, "trail_b")
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret.update({
        "movement": {"to_room": "trail_b", "mover": "self", "arrives": True},
        "sequence": [{"type": "action", "attempt": "runs down the trail",
                      "observable": "runs down the trail", "verb": "run"}],
    })
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "state_diff": {"positions": {"The Stranger": "trail_b"}},
    })

    resolved = director.director_resolve(ctx, nonce=0)
    merged = merge_scene_with_diff(scene, resolved["state_diff"])

    assert "Mara" not in resolved["state_diff"]["positions"]
    assert merged["positions"]["Mara"] == "trail_a"
    assert merged["following"]["Mara"]["target"] == "The Stranger"


def test_player_is_not_auto_carried_when_npc_target_runs_away(
        temp_db, monkeypatch):
    """The inverse direction matters too: following an NPC gives the player
    no automatic pursuit when that NPC chooses to bolt."""
    import agents.director as director
    from spatial import merge_scene_with_diff

    following = {"The Stranger": {"target": "Mara", "since_turn": 1}}
    scene = _following_scene(following)
    ctx = _make_ctx(temp_db, "trail_a")
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"] = None
    mara_id = ctx.cast[0]["id"]
    ctx.character_results[mara_id] = _quiet_character_result(
        verb="run", attempt="runs away down the trail")
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "state_diff": {"positions": {"Mara": "trail_b"}},
    })

    resolved = director.director_resolve(ctx, nonce=0)
    merged = merge_scene_with_diff(scene, resolved["state_diff"])

    assert "The Stranger" not in resolved["state_diff"]["positions"]
    assert merged["positions"]["The Stranger"] == "trail_a"
    assert merged["following"]["The Stranger"]["target"] == "Mara"


def test_following_does_not_teleport_an_already_separated_follower(
        temp_db, monkeypatch):
    import agents.director as director

    following = {"Mara": {"target": "The Stranger", "since_turn": 1}}
    scene = _following_scene(following, mara_room="side_path")
    ctx = _make_ctx(temp_db, "trail_b")
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "state_diff": {"positions": {"The Stranger": "trail_b"}},
    })

    resolved = director.director_resolve(ctx, nonce=0)

    assert "Mara" not in resolved["state_diff"]["positions"]


def test_following_does_not_cross_a_barrier_the_target_got_through(
        temp_db, monkeypatch):
    """The target's resolved success is not inherited by a follower: a shut
    door can admit one actor's contested outcome without granting passage to
    everyone attached to them."""
    import agents.director as director

    following = {"Mara": {"target": "The Stranger", "since_turn": 1}}
    scene = _following_scene(following)
    scene["rooms"]["trail_a"]["adjacent"][0]["barrier"] = "closed_door"
    scene["rooms"]["trail_b"]["adjacent"][0]["barrier"] = "closed_door"
    ctx = _make_ctx(temp_db, "trail_b")
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        # The resolver owns this contested success for the player alone.
        "state_diff": {"positions": {"The Stranger": "trail_b"}},
    })

    resolved = director.director_resolve(ctx, nonce=0)

    assert resolved["state_diff"]["positions"]["The Stranger"] == "trail_b"
    assert "Mara" not in resolved["state_diff"]["positions"]


def test_player_incompatible_movement_stops_following(temp_db, monkeypatch):
    """Even if interpret omits the stop op, resolved contradictory player
    movement is a deterministic agency floor that ends the relation."""
    import agents.director as director
    from spatial import merge_scene_with_diff

    following = {"The Stranger": {"target": "Mara", "since_turn": 1}}
    scene = _following_scene(following)
    ctx = _make_ctx(temp_db, "side_path")
    temp_db.wset(ctx.chat.id, "scene", scene)
    ctx.director_interpret["movement"].update({"mover": "self", "arrives": True})
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "state_diff": {"positions": {
            "The Stranger": "side_path", "Mara": "trail_b",
        }},
    })

    resolved = director.director_resolve(ctx, nonce=0)
    merged = merge_scene_with_diff(scene, resolved["state_diff"])

    assert any(op.get("op") == "stop" and op.get("follower") == "The Stranger"
               for op in resolved["state_diff"]["following_ops"])
    assert "The Stranger" not in merged["following"]
    assert merged["positions"]["The Stranger"] == "side_path"
