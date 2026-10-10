"""A player's declared follow carries her (the owner's ruling, 2026-10-09, D1).

"A mind moves only by its own declaration" is honoured by a declared follow,
not overridden by it: the follow IS her declaration. Measured on scratch
story 166 (the Brackwater run):

* F101, turn 4607: "walks a step behind the pilot along the low walk and up
  the stair to the landing outside Abel Gale's door". The encoder filed her
  follow and her walk; the walk's last leg was refused because the landing
  was built that same beat; the follow floor read the shortened walk as a
  walk away from the pilot and stopped the follow; she stayed on the stage
  while the page walked her to the door.
* F88, turns 4598 and 4607: the player's walk ran at the onset, before the
  one she followed had moved, so every word said to her on the way was
  graded from where the onset had put her -- lost as fog fragments.
* The field every follow reader takes the player's decision from,
  `director_interpret.follow_op`, had not been written since the monolithic
  interpret card went (2026-09-12): 8 of 4,214 stored interprets, all older;
  the encoder's player follows (19) were never put on it.

And what the reviews of 2026-10-09 held it to: a place she declared is hers,
and wins over a follow declared in the same breath (F2); her walk with the
one she follows waits on theirs from the moment the cast perceives the beat,
not only in the committed steps (F3), takes nobody else's move with it (N3)
and keeps its time where nothing prices it again (N7); riding their steps,
she is never moved ahead of an act of her own (N2); a follow goes only where
its follower last saw the one it follows or heard a sound they made, this
beat or the one before -- never to where the world alone knows a body to
be (F1), nor because a voice could have crossed between the rooms (N1); and
the interpret's own record is not rewritten by the resolve (F8). A follow
nobody declared still never moves anyone.
"""

from __future__ import annotations

import copy
import json

import pytest

from tests.director_fakes import _make_ctx, encoder_event

pytestmark = pytest.mark.usefixtures("prose_director")

PLAYER = "The Stranger"


def _trail(following=None, player_room="trail_a", mara_room="trail_a", extra=None):
    """Trail A opens on Trail B and the Side Path; the Far Glade is beyond
    Trail B, out of sight and earshot of Trail A."""
    scene = {
        "location": "Open Trail", "time": "day",
        "rooms": {
            "trail_a": {"name": "Trail A", "adjacent": [
                {"to": "trail_b", "barrier": "open", "distance": "near"},
                {"to": "side_path", "barrier": "open", "distance": "near"},
            ]},
            "trail_b": {"name": "Trail B", "adjacent": [
                {"to": "trail_a", "barrier": "open", "distance": "near"},
                {"to": "far_glade", "barrier": "open", "distance": "near"},
            ]},
            "side_path": {"name": "Side Path", "adjacent": [
                {"to": "trail_a", "barrier": "open", "distance": "near"},
            ]},
            "far_glade": {"name": "Far Glade", "adjacent": [
                {"to": "trail_b", "barrier": "open", "distance": "near"},
            ]},
        },
        "positions": {PLAYER: player_room, "Mara": mara_room, **(extra or {})},
        "following": following or {}, "stations": {}, "entities": {},
        "attire": {}, "overlays": {},
    }
    return scene


def _staged(answers):
    """A fake `_agent_json` answering each step key from a queue, in call
    order: the interpret's prose and encoder first, then the resolve's."""
    queues = {key: list(values) for key, values in answers.items()}

    def fake(role, step_key, system, payload, **kw):
        queue = queues.get(step_key) or []
        value = queue.pop(0) if queue else {}
        return json.loads(json.dumps(value))
    return fake


def _follow(follower, target, op="start"):
    row = {"op": op, "follower": follower}
    if op == "start":
        row["target"] = target
    return {"item": follower, "patch": {"following_ops": [row]}}


def _walk(who, room):
    return {"item": who, "patch": {"positions": {who: room}}}


def _interpret(temp_db, monkeypatch, *, scene, interpret_events, player_input="I go with her."):
    import agents.director as director
    ctx = _make_ctx(temp_db, scene=scene, player_input=player_input)
    monkeypatch.setattr(director, "_agent_json", _staged({
        "director_prose": [{"prose": "She goes with Mara."}],
        "director_specialist": [{"events": interpret_events, "missing_tools": []}],
    }))
    interp = director.director_interpret(ctx, nonce=0)
    ctx.director_interpret = interp
    return ctx, interp


def _beat(temp_db, monkeypatch, *, scene, interpret_events, resolve_events,
          mara_walks=True, mara_follow=None, before_resolve=None):
    """Interpret, then resolve, the way the runtime runs them; returns
    (ctx, interpret output, resolve output)."""
    import agents.director as director
    ctx = _make_ctx(temp_db, scene=scene, player_input="I go with her.")
    mara = ctx.cast[0]["id"]
    ctx.character_results[mara] = {
        "name": "Mara",
        "sequence": [{"type": "action", "attempt": "walks on" if mara_walks else "waits",
                      "observable": "walks on" if mara_walks else "waits",
                      "visibility": "overt", "conceal_from": []}],
        "follow_op": mara_follow,
    }
    monkeypatch.setattr(director, "_agent_json", _staged({
        "director_prose": [{"prose": "She goes with Mara."},
                           {"prose": "Mara answers, and goes."}],
        "director_specialist": [
            {"events": interpret_events, "missing_tools": []},
            {"events": [dict(e, source_entity_id=e.get("source_entity_id")
                             .replace("MARA", f"character:{mara}"))
                        for e in resolve_events], "missing_tools": []},
        ],
    }))
    interp = director.director_interpret(ctx, nonce=0)
    ctx.director_interpret = interp
    if before_resolve is not None:
        before_resolve(ctx)
    resolved = director.director_resolve(ctx, nonce=0)
    return ctx, interp, resolved


def _falls_in(room="trail_b"):
    return [
        encoder_event(f"{PLAYER} falls in behind Mara.", source="persona:primary",
                      transforms=[_follow(PLAYER, "Mara")]),
        encoder_event(f"{PLAYER} walks behind Mara.", source="persona:primary",
                      movement={"mover": PLAYER, "to_room": room, "arrives": True},
                      transforms=[_walk(PLAYER, room)]),
    ]


def _mara_goes(room="trail_b"):
    return [
        encoder_event("This way.", source="MARA", speech=True),
        encoder_event(f"Mara walks to {room}.", source="MARA",
                      movement={"mover": "Mara", "to_room": room, "arrives": True},
                      transforms=[_walk("Mara", room)]),
        encoder_event("Mind the roots.", source="MARA", speech=True),
    ]


def _worlds(scene, diff):
    from world.spatial import merge_scene_with_diff
    worlds = []
    merged = merge_scene_with_diff(scene, diff, causal_worlds=worlds)
    return worlds, merged


def _her_steps(record):
    """The interpret record's steps that move the player."""
    return [(s.get("chrono_id"), (s.get("patch") or {}).get("positions"))
            for s in (record or {}).get("causal_steps") or []
            if PLAYER in ((s.get("patch") or {}).get("positions") or {})]


def test_her_own_follow_is_on_the_interprets_follow_op(temp_db, monkeypatch):
    _ctx, interp, _resolved = _beat(
        temp_db, monkeypatch, scene=_trail(),
        interpret_events=_falls_in(), resolve_events=_mara_goes())
    assert interp["follow_op"]["op"] == "start"
    assert interp["follow_op"]["target"] == "Mara"


def test_a_place_she_declared_wins_over_the_follow_declared_with_it(temp_db, monkeypatch):
    """Review F2. She falls in behind Mara and walks to Trail B; Mara takes
    the side path instead. The place she named stands and the follow ends --
    round 1 exempted a follow declared this beat from that floor and walked
    her down the side path, a destination nobody declared for her. Her walk
    waited on Mara's, so she is still on Trail A when Mara leaves, and goes
    on alone after."""
    ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(),
        interpret_events=_falls_in("trail_b"), resolve_events=_mara_goes("side_path"))
    diff = resolved["state_diff"]
    assert diff["positions"][PLAYER] == "trail_b"
    assert diff["positions"]["Mara"] == "side_path"
    assert any(op.get("op") == "stop" and op.get("follower") == PLAYER
               for op in diff["following_ops"])
    assert any("the place declared stands" in w for w in ctx.warnings)
    worlds, merged = _worlds(_trail(), diff)
    [left] = [w for w in worlds if w["before"]["positions"].get("Mara") == "trail_a"
              and w["after"]["positions"].get("Mara") == "side_path"]
    assert left["before"]["positions"][PLAYER] == "trail_a"
    assert merged["positions"][PLAYER] == "trail_b"


def test_an_act_at_the_end_of_her_walk_keeps_the_walk_where_she_took_it(
        temp_db, monkeypatch):
    """Review F2's probe. She follows Mara to Trail B and lifts the latch of
    the gate there; Mara takes the side path. The walk with an act after it
    is hers at the onset -- it does not wait -- and neither the walk nor the
    latch is moved to where Mara went (round 1 put her on the side path
    before Mara moved, lifting a latch two rooms from its gate)."""
    events = _falls_in("trail_b") + [encoder_event(
        f"{PLAYER} lifts the latch of the gate.", source="persona:primary",
        transforms=[{"item": "gate", "patch": {
            "entities": {"gate": {"name": "the gate", "kind": "fixture",
                                  "state": {"latch": "lifted"}}},
            "positions": {"gate": "trail_b"}}}])]
    ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(),
        interpret_events=events, resolve_events=_mara_goes("side_path"))
    assert not [e for e in interp["sequence"] if e.get("walks_with")]
    assert interp["movement"]["to_room"] == "trail_b"
    diff = resolved["state_diff"]
    assert diff["positions"][PLAYER] == "trail_b"
    assert any(op.get("op") == "stop" for op in diff["following_ops"])
    worlds, _merged = _worlds(_trail(), diff)
    [latch] = [w for w in worlds
               if "gate" in ((w.get("patch") or {}).get("entities") or {})]
    assert latch["before"]["positions"][PLAYER] == "trail_b"
    assert latch["after"]["positions"]["gate"] == "trail_b"


def test_a_follow_from_an_earlier_beat_ends_when_she_goes_her_own_way(
        temp_db, monkeypatch):
    """The floor holds for a follow nothing this beat declared. Scratch
    story 166 idx 6 (turn 4591): following the pilot since idx 3, the player
    reached the chapel while the pilot was still on the rope bridge, and the
    follow ended. Declared again in the same breath as a walk of her own
    elsewhere, the place she named still wins."""
    standing = {PLAYER: {"target": "Mara", "since_turn": 0}}
    own_way = [encoder_event(
        f"{PLAYER} takes the side path.", source="persona:primary",
        movement={"mover": PLAYER, "to_room": "side_path", "arrives": True},
        transforms=[_walk(PLAYER, "side_path")])]
    _ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(following=standing),
        interpret_events=own_way, resolve_events=_mara_goes("trail_b"))
    diff = resolved["state_diff"]
    assert diff["positions"][PLAYER] == "side_path"
    assert any(op.get("op") == "stop" and op.get("follower") == PLAYER
               for op in diff["following_ops"])
    again = [encoder_event(f"{PLAYER} keeps with Mara.", source="persona:primary",
                           transforms=[_follow(PLAYER, "Mara")])] + own_way
    _ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(following=standing),
        interpret_events=again, resolve_events=_mara_goes("trail_b"))
    assert resolved["state_diff"]["positions"][PLAYER] == "side_path"


def test_she_walks_when_the_one_she_follows_walks(temp_db, monkeypatch):
    """F88: Mara's first line is said before she moves, her second after;
    the player hears both beside her, because she moves when Mara does --
    not at the onset, ahead of everyone."""
    scene = _trail()
    ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene,
        interpret_events=_falls_in(), resolve_events=_mara_goes())
    assert [e.get("walks_with") for e in interp["sequence"]
            if e.get("phase") == "continuation"] == ["Mara"]
    diff = resolved["state_diff"]
    steps = diff["causal_steps"]
    onset = [s for s in steps if s.get("stage") == "interpret"]
    assert not any(PLAYER in ((s.get("patch") or {}).get("positions") or {})
                   for s in onset), "she does not walk ahead at the onset"
    [walk] = [s for s in steps if s.get("stage") == "resolve"
              and "Mara" in ((s.get("patch") or {}).get("positions") or {})]
    assert walk["patch"]["positions"][PLAYER] == "trail_b"
    worlds, merged = _worlds(scene, diff)
    for world in worlds:
        here = world["before"]["positions"]
        assert here[PLAYER] == here["Mara"], (world.get("stage"), world.get("chrono_id"))
    assert merged["positions"][PLAYER] == merged["positions"]["Mara"] == "trail_b"


def test_the_cast_sees_her_beside_them_until_they_go(temp_db, monkeypatch):
    """Review F3. The cast declares from the onset, and the onset had walked
    her up the trail before Mara moved -- "The person of unremarkable
    appearance is in Trail B." -- while the committed beat walked them
    together. Her walk waits from the start: the onset preview, the room the
    act views place her in and Mara's own view keep her beside Mara."""
    from agents.common import preview_player_state_assertions
    from agents.perception import perception_act
    scene = _trail()
    ctx, interp = _interpret(temp_db, monkeypatch, scene=scene,
                             interpret_events=_falls_in(),
                             player_input="I fall in behind Mara.")
    assert not _her_steps(interp["onset_state_assertions"])
    assert _her_steps(interp["state_assertions"]), "the declaration keeps her walk"
    onset = preview_player_state_assertions(
        scene, interp["onset_state_assertions"], ctx, PLAYER)
    assert onset["positions"][PLAYER] == "trail_a"
    out = perception_act(ctx, nonce=0)
    assert out["player_room"] == "trail_a"
    mara = ctx.cast[0]["id"]
    view = str((out.get("views") or {}).get(str(mara)) or "")
    assert "in trail b" not in view.casefold(), view


def test_the_resolve_is_told_her_walk_is_still_to_happen(temp_db, monkeypatch):
    """A walk that waits is out of the world the resolve author is shown, so
    it is not in `already_happened` -- which the interpret's prose, telling
    the whole declaration as done, used to fill -- and it is in the author's
    `event_inputs`, the stage it happens in. Replayed on scratch story 166
    turn 4607 with the prose in `already_happened` and both bodies still on
    the boat, the author once stopped mid-sentence and once opened "The
    stair brought them up", and neither time walked the pilot. Its span is
    the author's to price, so the interpret's row for it is not summed a
    second time."""
    import agents.director as director
    seen = []
    events = [
        encoder_event(f"{PLAYER} falls in behind Mara.", source="persona:primary",
                      transforms=[_follow(PLAYER, "Mara")]),
        encoder_event(f"{PLAYER} walks behind Mara up the trail.", source="persona:primary",
                      movement={"mover": PLAYER, "to_room": "trail_b", "arrives": True},
                      transforms=[_walk(PLAYER, "trail_b")], seconds=600),
    ]
    resolve_events = [dict(e) for e in _mara_goes()]
    resolve_events[1]["seconds"] = 60

    _ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(), interpret_events=events,
        resolve_events=resolve_events,
        before_resolve=lambda ctx: monkeypatch.setattr(
            director, "_agent_json", _wrap(director._agent_json, seen)))
    [payload] = [p for p in seen if p.get("already_happened") is not None] or [{}]
    told = str(payload.get("already_happened") or "")
    assert "falls in behind Mara" in told
    assert "walks behind Mara" not in told and "She goes with Mara" not in told
    mine = [e for group in payload.get("event_inputs") or ()
            if str(group.get("entity_id")).startswith("persona:")
            for e in group.get("events") or ()]
    assert [e.get("walks_with") for e in mine] == ["Mara"], mine
    assert resolved["state_diff"]["time"]["duration_seconds"] == 60


def test_a_stop_the_resolve_writes_on_her_walk_ends_the_follow(temp_db, monkeypatch):
    """Her walk that waited reaches the resolve as her own input, so the
    encoder may write her own ops on it -- here a stop, as she goes up the
    trail while Mara stays. Her declaration's start came first in the beat
    and must come first in the ledger: appended after the resolve's ops, the
    interpret's `follow_op` and the onset's own start undid the stop (scratch
    story 166 turn 4607, replayed 2026-10-09, where the floor happened to
    end the follow anyway). Mara does not move, so the floor has nothing to
    compare."""
    import agents.director as director
    from world.spatial import merge_scene_with_diff

    def her_walk_alone(ctx):
        [waiting] = [e["event_id"] for e in ctx.director_interpret["sequence"]
                     if e.get("walks_with")]
        mara = ctx.cast[0]["id"]
        monkeypatch.setattr(director, "_agent_json", _staged({
            "director_prose": [{"prose": "Mara stays; she goes on up the trail alone."}],
            "director_specialist": [{"events": [
                encoder_event("Mara waits.", source=f"character:{mara}"),
                encoder_event(f"{PLAYER} goes on up the trail alone.",
                              source="persona:primary", source_event_id=waiting,
                              movement={"mover": PLAYER, "to_room": "trail_b",
                                        "arrives": True},
                              transforms=[_walk(PLAYER, "trail_b"),
                                          _follow(PLAYER, None, op="stop")]),
            ], "missing_tools": []}],
        }))

    scene = _trail()
    _ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene, interpret_events=_falls_in(),
        resolve_events=[], mara_walks=False, before_resolve=her_walk_alone)
    diff = resolved["state_diff"]
    mine = [op.get("op") for op in diff["following_ops"] if op.get("follower") == PLAYER]
    assert mine[-1] == "stop", diff["following_ops"]
    merged = merge_scene_with_diff(scene, diff)
    assert PLAYER not in (merged.get("following") or {})
    assert merged["positions"][PLAYER] == "trail_b"


def _wrap(fake, seen):
    """The staged fake, recording each prose author payload it answers."""
    def spy(role, step_key, system, payload, **kw):
        if step_key == "director_prose":
            seen.append(json.loads(json.dumps(payload, default=str)))
        return fake(role, step_key, system, payload, **kw)
    return spy


def test_a_follow_with_no_walk_of_her_own_moves_her_when_they_move(
        temp_db, monkeypatch):
    """Scratch story 166 turn 4588: "falls in a half-step behind Hester on
    the narrow boards" -- a follow and no walk. The carry took her to the
    low walk at the END of the beat, after every word the pilot said on the
    way; now she goes at the step the pilot goes, and the follow her own."""
    scene = _trail()
    ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene,
        interpret_events=[encoder_event(
            f"{PLAYER} falls in behind Mara.", source="persona:primary",
            transforms=[_follow(PLAYER, "Mara")])],
        resolve_events=_mara_goes())
    assert interp["follow_op"]["target"] == "Mara"
    diff = resolved["state_diff"]
    [walk] = [s for s in diff["causal_steps"] if s.get("stage") == "resolve"
              and "Mara" in ((s.get("patch") or {}).get("positions") or {})]
    assert walk["patch"]["positions"][PLAYER] == "trail_b"
    worlds, _merged = _worlds(scene, diff)
    assert all(w["before"]["positions"][PLAYER] == w["before"]["positions"]["Mara"]
               for w in worlds)


def test_going_after_someone_she_sees_in_the_next_room_is_her_walk(temp_db, monkeypatch):
    """A follow she declared toward someone she sees in the next room, with
    no walk of her own, takes her to them: the approach used to skip the
    player outright."""
    _ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(mara_room="trail_b"),
        interpret_events=[encoder_event(
            f"{PLAYER} goes after Mara.", source="persona:primary",
            transforms=[_follow(PLAYER, "Mara")])],
        resolve_events=[encoder_event("Mara waits.", source="MARA")],
        mara_walks=False)
    assert interp["follow_op"]["target"] == "Mara"
    assert resolved["state_diff"]["positions"][PLAYER] == "trail_b"
    assert resolved["state_diff"]["stations"][PLAYER]["near"] == ["Mara"]


def test_a_follow_toward_someone_out_of_sight_and_earshot_moves_nobody(
        temp_db, monkeypatch):
    """Review F1. Mara is in the Far Glade, beyond Trail B: nothing of her
    reaches Trail A. Round 1 walked the player there anyway -- the route and
    the room came from the world, which she has no channel to, so she
    learned where a hidden body was by being put beside it. Nothing
    perceived, nothing followed: the relation stands, she stays, and the
    beat says so."""
    from world.spatial import hear_level, spatial_rel_between, visual_level_between
    scene = _trail(mara_room="far_glade")
    assert visual_level_between(scene, PLAYER, "Mara", None) == "none"
    assert hear_level(spatial_rel_between(scene, PLAYER, "Mara"), "normal") == "none"
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene,
        interpret_events=[encoder_event(
            f"{PLAYER} goes after Mara.", source="persona:primary",
            transforms=[_follow(PLAYER, "Mara")])],
        resolve_events=[encoder_event("Mara waits.", source="MARA")],
        mara_walks=False)
    assert (resolved["state_diff"].get("positions") or {}).get(PLAYER) in (None, "trail_a")
    assert not ((resolved.get("travel") or {}).get("advanced") or [])
    said = [w for w in ctx.warnings if "nothing perceived to follow" in w]
    assert len(said) == 1, ctx.warnings


def test_she_goes_where_she_last_saw_them(temp_db, monkeypatch):
    """She sees Mara on Trail B and goes after her; Mara walks on into the
    Far Glade, out of her sight and hearing. She goes to Trail B, where she
    saw her -- not beside Mara in the glade, which the world alone knows."""
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(mara_room="trail_b"),
        interpret_events=[encoder_event(
            f"{PLAYER} goes after Mara.", source="persona:primary",
            transforms=[_follow(PLAYER, "Mara")])],
        resolve_events=_mara_goes("far_glade"))
    diff = resolved["state_diff"]
    assert diff["positions"]["Mara"] == "far_glade"
    assert diff["positions"][PLAYER] == "trail_b"
    assert "Mara" not in ((diff.get("stations") or {}).get(PLAYER) or {}).get("near", [])
    assert any("where they were last seen or heard" in w for w in ctx.warnings)


def test_a_character_goes_only_where_it_perceives_the_one_it_follows(
        temp_db, monkeypatch):
    """The class, not the player alone: Mara, in the Far Glade, decides to
    go after the player on Trail A, two rooms off and out of sight and
    earshot. The world's knowledge of where the player stands gives Mara no
    way to her; at eddf7b4e she was walked straight there."""
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(mara_room="far_glade"),
        interpret_events=[encoder_event(f"{PLAYER} waits.", source="persona:primary")],
        resolve_events=[encoder_event("Mara sets off.", source="MARA")],
        mara_walks=False, mara_follow={"op": "start", "target": PLAYER})
    assert (resolved["state_diff"].get("positions") or {}).get("Mara") in (None, "far_glade")
    assert any("Mara started following" in w and "nothing perceived" in w
               for w in ctx.warnings), ctx.warnings


def _store(barrier="curtain", light=None, player_room="trail_a", mara_room="store"):
    """Trail A opens on a store, through a curtain or a doorway; nothing in
    the store is seen from the trail when it is curtained or dark."""
    rooms = {
        "trail_a": {"name": "Trail A", "adjacent": [
            {"to": "store", "barrier": barrier, "distance": "near"}]},
        "store": {"name": "The Store", "adjacent": [
            {"to": "trail_a", "barrier": barrier, "distance": "near"}]},
    }
    if light:
        rooms["store"]["light"] = light
    return {"location": "x", "time": "day", "rooms": rooms,
            "positions": {PLAYER: player_room, "Mara": mara_room},
            "following": {}, "stations": {}, "entities": {}, "attire": {},
            "overlays": {}}


def _goes_after_mara():
    return [encoder_event(f"{PLAYER} goes after Mara.", source="persona:primary",
                          transforms=[_follow(PLAYER, "Mara")])]


@pytest.mark.parametrize("barrier,light", [("curtain", None), ("open", "dark")])
def test_a_silent_body_she_cannot_see_is_not_followed(temp_db, monkeypatch, barrier, light):
    """Review N1. Mara stands silent in the store, behind a curtain or in a
    dark doorway: nothing of her is seen from the trail, and she makes no
    sound. Round 2 walked the player in beside her anyway, because a NORMAL
    VOICE WOULD have carried between the rooms -- a channel a voice could
    cross, not anything Mara did. Nothing perceived, nothing followed."""
    from world.spatial import visual_level_between
    scene = _store(barrier, light)
    assert visual_level_between(scene, PLAYER, "Mara", None) == "none"
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene, interpret_events=_goes_after_mara(),
        resolve_events=[encoder_event("Mara keeps still.", source="MARA")],
        mara_walks=False)
    assert (resolved["state_diff"].get("positions") or {}).get(PLAYER) in (None, "trail_a")
    assert PLAYER not in ((resolved["state_diff"].get("stations") or {}))
    assert [w for w in ctx.warnings if "nothing perceived to follow" in w], ctx.warnings


def test_a_character_does_not_follow_a_silent_hidden_player(temp_db, monkeypatch):
    """The class: Mara on the trail decides to go after the player, who
    holds her breath in the dark store. The world knows where the player
    is; nothing of her reached Mara, so Mara stays."""
    scene = _store("open", "dark", player_room="store", mara_room="trail_a")
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene,
        interpret_events=[encoder_event(f"{PLAYER} holds her breath.",
                                        source="persona:primary")],
        resolve_events=[encoder_event("Mara sets off after her.", source="MARA")],
        mara_walks=False, mara_follow={"op": "start", "target": PLAYER})
    assert (resolved["state_diff"].get("positions") or {}).get("Mara") in (None, "trail_a")
    assert any("Mara started following" in w and "nothing perceived" in w
               for w in ctx.warnings), ctx.warnings


@pytest.mark.parametrize("volume,follows", [("normal", True), ("whisper", False)])
def test_a_line_she_hears_through_the_curtain_is_followed(temp_db, monkeypatch,
                                                          volume, follows):
    """A sound the one followed MADE, at its own volume: Mara calls from
    behind the curtain and the player goes in to her; a whisper does not
    carry through it, so the same follow moves nobody."""
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_store("curtain"),
        interpret_events=_goes_after_mara(),
        resolve_events=[encoder_event("In here.", source="MARA", speech=True,
                                      volume=volume)],
        mara_walks=False)
    where = (resolved["state_diff"].get("positions") or {}).get(PLAYER)
    if follows:
        assert where == "store"
        assert resolved["state_diff"]["stations"][PLAYER]["near"] == ["Mara"]
    else:
        assert where in (None, "trail_a")
        assert [w for w in ctx.warnings if "nothing perceived to follow" in w]


def test_a_character_follows_the_voice_of_a_hidden_player(temp_db, monkeypatch):
    """The player speaks from the dark store this beat; Mara hears her and
    goes in after her -- her own line placed her."""
    scene = _store("open", "dark", player_room="store", mara_room="trail_a")
    _ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene,
        interpret_events=[encoder_event("Over here.", source="persona:primary",
                                        speech=True, volume="normal")],
        resolve_events=[encoder_event("Mara sets off after her.", source="MARA")],
        mara_walks=False, mara_follow={"op": "start", "target": PLAYER})
    assert resolved["state_diff"]["positions"]["Mara"] == "store"


def test_a_voice_drowned_where_the_follower_stands_places_nobody():
    """The follow's ear is the outcome's: graded through the same field, a
    throng in the taproom drowns a voice from behind the snug's curtain, so
    that voice tells the follower nothing of where its speaker is; in a quiet
    taproom the same line is heard. Without the story's crowds the gate would
    hear what the page never delivers."""
    from types import SimpleNamespace
    from agents.director import _voice_reaches
    from tests.test_field_sentences import room, scene

    class _Ctx(dict):
        def __init__(self, crowds):
            super().__init__(_sound_crowds=crowds)
            self.chat = SimpleNamespace(id=0, persona_id=None)
            self.turn = SimpleNamespace(id=1, idx=1, frame_id=None)
            self.cast, self.extra_players = [], []

    taproom = room("the Taproom", size="medium", light="lit",
                   adjacent=[{"to": "snug", "barrier": "curtain", "distance": "near", "dir": "e"}])
    snug = room("the Snug", size="small", light="lit",
                adjacent=[{"to": "taproom", "barrier": "curtain", "distance": "near", "dir": "w"}])
    world = scene({"taproom": taproom, "snug": snug}, {PLAYER: "taproom", "Mara": "snug"})
    line = {"volume": "normal", "categories": ["speech"], "visibility": "overt",
            "conceal_from": []}
    throng = [{"room_uid": "taproom", "band": "a throng", "uid": "crowd_1"}]
    assert _voice_reaches(_Ctx([]), world, PLAYER, "Mara", line, None)
    assert not _voice_reaches(_Ctx(throng), world, PLAYER, "Mara", line, None)


def _beat_before(temp_db, ctx, ledger, steps, positions=None):
    """Files the beat before this one: a committed resolve carrying `ledger`
    and `steps`, as the runtime leaves it."""
    import time
    turn = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (ctx.chat.id, ctx.turn.idx - 1, "", time.time()))
    step = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                      (turn, "director_resolve", "", 0))
    temp_db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
               (step, json.dumps({"causal_ledger": ledger,
                                  "state_diff": {"causal_steps": steps,
                                                 "positions": positions or {}}}),
                time.time()))


@pytest.mark.parametrize("case,follows", [
    ("still", True), ("moved_after", False), ("elsewhere_since", False)])
def test_a_call_heard_on_the_beat_before_is_followed(temp_db, monkeypatch,
                                                     case, follows):
    """Mara called from behind the curtain on the beat before, and is
    silent now: the player heard where she was, and goes. Had Mara gone
    into the store only after the call -- or had that beat left her
    somewhere else, and she came here since -- the call came from somewhere
    the scene no longer says: it is not read, and the follow moves
    nobody."""
    def before(ctx):
        mara = ctx.cast[0]["id"]
        ledger = [{"chrono_id": 1, "source_entity_id": f"character:{mara}",
                   "categories": ["speech"], "volume": "normal",
                   "event": "Over here.", "visibility": "overt", "conceal_from": []}]
        steps = [{"chrono_id": 1, "stage": "resolve", "events": [], "patch": {}}]
        if case == "moved_after":
            steps.append({"chrono_id": 2, "stage": "resolve", "events": [],
                          "patch": {"positions": {"Mara": "store"}}})
        _beat_before(temp_db, ctx, ledger, steps,
                     positions={"Mara": "trail_a"} if case == "elsewhere_since" else None)

    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_store("curtain"),
        interpret_events=_goes_after_mara(),
        resolve_events=[encoder_event("Mara keeps still.", source="MARA")],
        mara_walks=False, before_resolve=before)
    where = (resolved["state_diff"].get("positions") or {}).get(PLAYER)
    if follows:
        assert where == "store"
    else:
        assert where in (None, "trail_a")
        assert [w for w in ctx.warnings if "nothing perceived to follow" in w]


def _dark(scene, *rooms):
    for room in rooms:
        scene["rooms"][room]["light"] = "dark"
    return scene


def test_one_who_slips_away_silently_in_the_dark_is_lost(temp_db, monkeypatch):
    """The relation carry is a follow too (review N1, the class): beside
    Mara in the dark, following her since an earlier beat, the player does
    not see her go, and Mara says nothing on the way -- so she is not walked
    to where Mara went, which the world alone knows. Lit, the same beat
    carries her, as it always did."""
    standing = {PLAYER: {"target": "Mara", "since_turn": 0}}
    silent_walk = [encoder_event("Mara walks to trail_b.", source="MARA",
                                 movement={"mover": "Mara", "to_room": "trail_b",
                                           "arrives": True},
                                 transforms=[_walk("Mara", "trail_b")])]
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_dark(_trail(following=standing), "trail_a", "trail_b"),
        interpret_events=[encoder_event(f"{PLAYER} waits.", source="persona:primary")],
        resolve_events=silent_walk)
    diff = resolved["state_diff"]
    assert diff["positions"]["Mara"] == "trail_b"
    assert diff["positions"].get(PLAYER) in (None, "trail_a")
    assert [w for w in ctx.warnings if "lost Mara" in w], ctx.warnings
    _ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(following=standing),
        interpret_events=[encoder_event(f"{PLAYER} waits.", source="persona:primary")],
        resolve_events=silent_walk)
    assert resolved["state_diff"]["positions"][PLAYER] == "trail_b"


def test_a_character_beside_the_player_in_the_dark_loses_her_silent_walk(
        temp_db, monkeypatch):
    """Mara follows the player; in the dark the player walks off up the
    trail without a word. Mara stays: nothing of the going reached her."""
    standing = {"Mara": {"target": PLAYER, "since_turn": 0}}
    ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=_dark(_trail(following=standing), "trail_a", "trail_b"),
        interpret_events=[encoder_event(
            f"{PLAYER} walks up the trail.", source="persona:primary",
            movement={"mover": PLAYER, "to_room": "trail_b", "arrives": True},
            transforms=[_walk(PLAYER, "trail_b")])],
        resolve_events=[encoder_event("Mara waits.", source="MARA")],
        mara_walks=False)
    diff = resolved["state_diff"]
    assert diff["positions"][PLAYER] == "trail_b"
    assert diff["positions"].get("Mara") in (None, "trail_a")
    assert [w for w in ctx.warnings if "Mara lost" in w], ctx.warnings


def test_a_walk_into_a_room_the_beat_builds_ends_there(temp_db, monkeypatch):
    """F101's first wrong datum: the walk's last leg named the landing the
    room author built that beat, and the walk was cut to the stage."""
    _ctx, interp, _resolved = _beat(
        temp_db, monkeypatch, scene=_trail(),
        interpret_events=[
            encoder_event(f"{PLAYER} walks to Trail B.", source="persona:primary",
                          movement={"mover": PLAYER, "to_room": "trail_b", "arrives": True},
                          transforms=[_walk(PLAYER, "trail_b")]),
            encoder_event(f"{PLAYER} climbs to the lookout above it.",
                          source="persona:primary",
                          movement={"mover": PLAYER, "to_room": "lookout", "arrives": True},
                          transforms=[
                              {"item": "lookout", "patch": {"rooms": {"lookout": {
                                  "name": "The Lookout", "adjacent": [
                                      {"to": "trail_b", "barrier": "open",
                                       "distance": "near"}]}}}},
                              _walk(PLAYER, "lookout")]),
        ],
        resolve_events=[encoder_event("Mara waits.", source="MARA")],
        mara_walks=False)
    assert interp["movement"]["to_room"] == "lookout"


def test_the_interprets_own_record_keeps_its_steps(temp_db, monkeypatch):
    """Review F8. The onset's steps reach the resolve's diff by reference,
    so writing the follower into a step of theirs wrote into the interpret's
    own record too. Here the porter she follows moves in her own declaration
    (a figure's walk is the world's), so the step that carries her is an
    onset step: the resolve's diff has her in it, the interpret's record
    does not."""
    scene = _trail(extra={"the porter": "trail_a"})
    events = [
        encoder_event(f"{PLAYER} falls in behind the porter.", source="persona:primary",
                      transforms=[_follow(PLAYER, "the porter")]),
        encoder_event("The porter shoulders the pack and heads up the trail.",
                      source="persona:primary",
                      transforms=[_walk("the porter", "trail_b")]),
    ]
    held = {}

    def snapshot(ctx):
        held["onset"] = copy.deepcopy(ctx.director_interpret["onset_state_assertions"])
        held["record"] = ctx.director_interpret["onset_state_assertions"]

    _ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene, interpret_events=events,
        resolve_events=[encoder_event("Mara waits.", source="MARA")],
        mara_walks=False, before_resolve=snapshot)
    diff = resolved["state_diff"]
    [carried] = [s for s in diff["causal_steps"]
                 if "the porter" in ((s.get("patch") or {}).get("positions") or {})]
    assert carried["stage"] == "interpret"
    assert carried["patch"]["positions"][PLAYER] == "trail_b"
    assert held["record"] == held["onset"], "the interpret's record was rewritten"


def test_a_walk_beside_someone_her_declaration_walks_does_not_wait(temp_db, monkeypatch):
    """The one she follows moves inside her own declaration -- a porter her
    span walks up the trail -- so both walks are in one chronology already,
    the onset's: hers does not wait, and the cast sees them go together."""
    scene = _trail(extra={"the porter": "trail_a"})
    events = [
        encoder_event(f"{PLAYER} falls in behind the porter.", source="persona:primary",
                      transforms=[_follow(PLAYER, "the porter")]),
        encoder_event("The porter heads up the trail.", source="persona:primary",
                      transforms=[_walk("the porter", "trail_b")]),
        encoder_event(f"{PLAYER} walks behind him.", source="persona:primary",
                      movement={"mover": PLAYER, "to_room": "trail_b", "arrives": True},
                      transforms=[_walk(PLAYER, "trail_b")]),
    ]
    _ctx, interp = _interpret(temp_db, monkeypatch, scene=scene, interpret_events=events)
    assert not [e for e in interp["sequence"] if e.get("walks_with")]
    assert _her_steps(interp["onset_state_assertions"])


def _gate(room="trail_a"):
    return {"item": "gate", "patch": {
        "entities": {"gate": {"name": "the gate", "kind": "fixture",
                              "state": {"latch": "lifted"}}},
        "positions": {"gate": room}}}


def _latch_step(worlds):
    [latch] = [w for w in worlds if "gate" in ((w.get("patch") or {}).get("entities") or {})]
    return latch


def test_her_own_act_after_they_leave_is_done_where_she_stood(temp_db, monkeypatch):
    """Review N2, F2's class: her acts keep their order. Following the
    porter since an earlier beat, her declaration walks him up the trail and
    then she lifts the latch of the gate on Trail A. Round 2 rode her into
    the porter's step, so she lifted a latch on Trail A from Trail B; the
    latch is lifted where she stood, and she goes up after it, landing where
    he ended when the beat does."""
    standing = {PLAYER: {"target": "the porter", "since_turn": 0}}
    scene = _trail(following=standing, extra={"the porter": "trail_a"})
    events = [
        encoder_event("The porter shoulders the pack and heads up the trail.",
                      source="persona:primary", transforms=[_walk("the porter", "trail_b")]),
        encoder_event(f"{PLAYER} lifts the latch of the gate.", source="persona:primary",
                      transforms=[_gate()]),
    ]
    _ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene, interpret_events=events,
        resolve_events=[encoder_event("Mara waits.", source="MARA")], mara_walks=False)
    worlds, merged = _worlds(scene, resolved["state_diff"])
    latch = _latch_step(worlds)
    assert latch["before"]["positions"][PLAYER] == "trail_a"
    assert merged["positions"][PLAYER] == "trail_b"


@pytest.mark.parametrize("onward", [False, True])
def test_she_rides_only_their_steps_after_her_last_act(temp_db, monkeypatch, onward):
    """Following Mara since an earlier beat, she declares, contestably, that
    she tries the latch of the gate on Trail A. The resolve walks Mara up to
    Trail B and then has her work the latch free -- on Trail A, where she
    still stood (round 2 rode her into Mara's step first). When Mara walks
    on into the Far Glade after it, she goes with her from there."""
    import agents.director as director
    standing = {PLAYER: {"target": "Mara", "since_turn": 0}}
    scene = _trail(following=standing)

    def resolve_answers(ctx):
        mara = ctx.cast[0]["id"]
        [contest] = [e["event_id"] for e in ctx.director_interpret["sequence"]
                     if str(e.get("commitment")) == "contestable"]
        events = [
            encoder_event("Mara walks up to Trail B.", source=f"character:{mara}",
                          movement={"mover": "Mara", "to_room": "trail_b", "arrives": True},
                          transforms=[_walk("Mara", "trail_b")]),
            encoder_event(f"{PLAYER} works the latch of the gate free.",
                          source="persona:primary", source_event_id=contest,
                          transforms=[_gate()]),
        ]
        if onward:
            events.append(encoder_event(
                "Mara walks on into the Far Glade.", source=f"character:{mara}",
                movement={"mover": "Mara", "to_room": "far_glade", "arrives": True},
                transforms=[_walk("Mara", "far_glade")]))
        monkeypatch.setattr(director, "_agent_json", _staged({
            "director_prose": [{"prose": "Mara goes up the trail; she works the latch."}],
            "director_specialist": [{"events": events, "missing_tools": []}],
        }))

    _ctx, _interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene,
        interpret_events=[encoder_event(f"{PLAYER} tries the latch of the gate.",
                                        source="persona:primary", commitment="contestable")],
        resolve_events=[], before_resolve=resolve_answers)
    worlds, merged = _worlds(scene, resolved["state_diff"])
    latch = _latch_step(worlds)
    assert latch["before"]["positions"][PLAYER] == "trail_a"
    if onward:
        [glade] = [w for w in worlds
                   if (w.get("patch") or {}).get("positions", {}).get("Mara") == "far_glade"]
        assert glade["after"]["positions"][PLAYER] == "far_glade"
        assert merged["positions"][PLAYER] == "far_glade"
    else:
        assert merged["positions"][PLAYER] == "trail_b"


def test_a_walk_that_waits_takes_no_one_else_out_of_the_beat(temp_db, monkeypatch):
    """Review N3: "walks behind Mara, Rook at her heel" writes the dog's
    room in the same step as hers. A walk waits on the one she follows only
    when every body its steps move is hers; this one stays at the onset, and
    the dog reaches Trail B with her."""
    scene = _trail(extra={"Rook": "trail_a"})
    scene["entities"]["Rook"] = {"name": "Rook", "kind": "dog"}
    events = [
        encoder_event(f"{PLAYER} falls in behind Mara.", source="persona:primary",
                      transforms=[_follow(PLAYER, "Mara")]),
        encoder_event(f"{PLAYER} walks behind Mara, Rook at her heel.",
                      source="persona:primary",
                      movement={"mover": PLAYER, "to_room": "trail_b", "arrives": True},
                      transforms=[{"item": PLAYER, "patch": {"positions": {
                          PLAYER: "trail_b", "Rook": "trail_b"}}}]),
    ]
    _ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=scene, interpret_events=events,
        resolve_events=_mara_goes("trail_b"))
    assert not [e for e in interp["sequence"] if e.get("walks_with")]
    _worlds_, merged = _worlds(scene, resolved["state_diff"])
    assert merged["positions"]["Rook"] == "trail_b"
    assert merged["positions"][PLAYER] == "trail_b"


def test_the_carry_never_takes_her_off_a_room_her_own_walk_gave_her(temp_db, monkeypatch):
    """Review N6. Her walk up to Trail B is written as a position with no
    movement row, under a follow of Mara from an earlier beat, and Mara
    takes the side path. The incompatible-movement floor reads only a
    movement row, so it does not end the follow; the relation carry must
    still not move her: the room her own walk gave her stands, and her step
    in the declaration is not rewritten to the side path before Mara has
    moved."""
    standing = {PLAYER: {"target": "Mara", "since_turn": 0}}
    scene = _trail(following=standing)
    events = [encoder_event(f"{PLAYER} heads up to Trail B.", source="persona:primary",
                            transforms=[_walk(PLAYER, "trail_b")])]
    _ctx, interp, resolved = _beat(temp_db, monkeypatch, scene=scene,
                                   interpret_events=events,
                                   resolve_events=_mara_goes("side_path"))
    assert interp.get("movement") is None
    diff = resolved["state_diff"]
    assert diff["positions"][PLAYER] == "trail_b"
    worlds, merged = _worlds(scene, diff)
    assert merged["positions"][PLAYER] == "trail_b"
    assert [((w.get("patch") or {}).get("positions") or {}).get(PLAYER)
            for w in worlds
            if PLAYER in ((w.get("patch") or {}).get("positions") or {})] == ["trail_b"]


def test_her_walk_keeps_its_time_when_the_one_she_follows_stays(temp_db, monkeypatch):
    """Review N7. Her walk waits on Mara's and is priced at 120 s; Mara
    stays and only speaks, so nothing at the resolve prices it again: the
    beat lasts the walk's 120 s, as it did before it waited. Where Mara's
    walk is priced, she rides it and the beat lasts Mara's walk alone (the
    resolve test above)."""
    events = [
        encoder_event(f"{PLAYER} falls in behind Mara.", source="persona:primary",
                      transforms=[_follow(PLAYER, "Mara")]),
        encoder_event(f"{PLAYER} walks on ahead.", source="persona:primary",
                      movement={"mover": PLAYER, "to_room": "trail_b", "arrives": True},
                      transforms=[_walk(PLAYER, "trail_b")], seconds=120),
    ]
    _ctx, interp, resolved = _beat(
        temp_db, monkeypatch, scene=_trail(), interpret_events=events,
        resolve_events=[encoder_event("Not that way.", source="MARA", speech=True)],
        mara_walks=False)
    assert [e.get("walks_with") for e in interp["sequence"] if e.get("walks_with")] == ["Mara"]
    assert resolved["state_diff"]["time"]["duration_seconds"] == 120
    assert resolved["state_diff"]["positions"][PLAYER] == "trail_b"


# ---------------------------------------------------------------------------
# A follow nobody declared never moves anyone
# ---------------------------------------------------------------------------

def _floor(events, inputs):
    from agents.director_prose import a_walk_is_its_owners
    warnings = []
    index = {"persona:21": "Tamsin Coyle", "character:81": "Hester Gale",
             "Garory Haugowlow": "Garory Haugowlow"}
    return a_walk_is_its_owners(events, inputs, index, {}, warn=warnings.append), warnings


PRIMARY = [{"entity_id": "persona:21", "authority_mode": "world_author",
            "events": [{"event_id": "turn:9:primary:raw", "type": "raw_input"}]}]
HERS = [{"entity_id": "character:81", "authority_mode": "autonomous",
         "events": [{"event_id": "turn:9:character:81:2:action", "type": "action"}]}]


def _span(source, event_id, *transforms):
    return {"source_entity_id": source, "source_event_id": event_id,
            "event": "a span", "movement": None, "transforms": list(transforms)}


def test_a_follow_is_its_followers_own():
    """The player's span cannot start the pilot following her, nor the
    pilot's span start the player following the pilot; each mind's own span
    can, and a figure is the world's."""
    mine = _span("persona:21", "turn:9:primary:raw",
                 _follow("Tamsin Coyle", "Hester Gale"),
                 _follow("Hester Gale", "Tamsin Coyle"),
                 _follow("Garory Haugowlow", "Tamsin Coyle"))
    out, warnings = _floor([mine], PRIMARY)
    kept = [op["follower"] for t in out[0]["transforms"]
            for op in t["patch"].get("following_ops") or []]
    assert kept == ["Tamsin Coyle", "Garory Haugowlow"]
    assert warnings and "Hester Gale" in warnings[0]

    hers = _span("character:81", "turn:9:character:81:2:action",
                 _follow("Tamsin Coyle", "Hester Gale"),
                 _follow("Hester Gale", "Tamsin Coyle"))
    out, warnings = _floor([hers], HERS)
    kept = [op["follower"] for t in out[0]["transforms"]
            for op in t["patch"].get("following_ops") or []]
    assert kept == ["Hester Gale"]
    assert warnings and "Tamsin Coyle" in warnings[0]


def test_the_world_does_not_make_a_mind_follow():
    """A due pressure moves whom it moves, but a follow is never
    involuntary."""
    tide = [{"entity_id": "world_pressure:7", "authority_mode": "world",
             "events": [{"event_id": "p7", "type": "due_process"}]}]
    pressed = _span("world_pressure:7", "p7", _follow("Tamsin Coyle", "Hester Gale"))
    out, warnings = _floor([pressed], tide)
    assert not out[0]["transforms"]
    assert warnings and "Tamsin Coyle" in warnings[0]


def test_a_follow_spelled_by_a_record_id_reaches_the_ledger():
    """Scratch story 166 turn 4598 filed the player's follow of the pilot as
    target `char_hester_gale` -- her scene record's id -- and no positions
    key answered to it, so the ledger dropped it. A card uid folds the same
    way; a thing's id stays its id."""
    from agents.director import _canonical_following_ops

    cast = [{"id": 81, "sheet": json.dumps({"identity": {
        "name": "Hester Gale", "uid": "hester_gale"}})}]
    scene = {"entities": {"char_hester_gale": {"name": "Hester Gale", "kind": "person"},
                          "the_grebe": {"name": "the Grebe", "kind": "vehicle"}}}
    ops = _canonical_following_ops(
        [{"op": "start", "follower": "Tamsin Coyle", "target": "char_hester_gale"},
         {"op": "start", "follower": "Tamsin Coyle", "target": "hester_gale"},
         {"op": "start", "follower": "Tamsin Coyle", "target": "the_grebe"}],
        cast, "Tamsin Coyle", 13, scene=scene)
    assert [(op["follower"], op["target"], op["turn"]) for op in ops] == [
        ("Tamsin Coyle", "Hester Gale", 13), ("Tamsin Coyle", "Hester Gale", 13),
        ("Tamsin Coyle", "the_grebe", 13)]


def test_the_encoder_is_told_a_follow_is_the_followers_own():
    """The card the interpret's follow is written from (the encoder's
    `following_ops` part, en and ja): a follow is written on the follower's
    own conduct; start and stop are stated as the class, with the decision
    model's own line that two going together with neither leading are not
    following (review F5: the draft's "after them or beside them" said the
    opposite); and the follower's own walk is written only to a place its
    own declaration names, since the engine carries a follower from beside
    the one followed -- not "step for step", which held for the player
    alone."""
    from llm import prompts
    en = prompts.unified_specialist_prompt(["following_ops"], "en")
    ja = prompts.unified_specialist_prompt(["following_ops"], "ja")
    assert ("and it is the follower's own: write it on an event of the "
            "follower's own conduct, never for a body because someone else "
            "wished it or led the way") in en
    assert "when someone sets off to go wherever another leads" in en
    assert "two who set off together with neither leading are not following" in en
    assert ("when they go a way the other does not, or stay while the other leaves "
            "-- nothing short of that ends a follow") in en
    # Review N10: the class's complement, never a list of what does not end it.
    assert "Speech, a look or a gesture" not in en
    assert "それに満たない何をしても、追従は終わりません。" in ja
    assert "途中の言葉、視線、身振り" not in ja
    assert ("so write the follower a walk of their own only to a place their "
            "own declaration names") in en
    assert "beside them" not in en and "step for step" not in en
    assert "voluntary, lasting travel relation" in en and "grants no speed" in en
    assert "それは追う者自身のものです。追う者自身のふるまいの出来事に書き" in ja
    assert "どちらも先導せずに連れ立って向かう二人は、追従していません。" in ja
    assert "その者自身の宣言が名指す場所へだけ書きます。" in ja
    assert "{op:'start',follower,target,reason?}" in ja
    assert "{op:'stop',follower,reason?}" in ja
    assert "一歩ごと" not in ja and "横について" not in ja


def test_a_follow_counts_only_what_the_followers_own_senses_take_in(monkeypatch):
    """(review B2) The follow gate asked whether a body COULD be seen and its
    sounds heard, not whether this follower's senses take them in: a blind
    mind was walked toward a lit body in the next room, a deaf one by
    footfalls. Sight is the engine's one rule for whether a mind saw a body
    (`sighted_level`), hearing the listener's own acuity."""
    from types import SimpleNamespace
    import world.spatial as spatial
    import agents.director_movement as movement
    scene = _store("open", "lit")
    scene["rooms"]["trail_a"]["light"] = "lit"
    assert movement._sees_body(scene, PLAYER, "Mara", None)
    for blind in ([{"channel": "vision", "acuity": "blind"}],
                  [{"channel": "sight", "acuity": "absent"}]):
        assert not movement._sees_body(scene, PLAYER, "Mara", blind), blind
    # Whatever carries through the field, a deaf follower takes none of it in.
    monkeypatch.setattr(spatial, "heard_events",
                        lambda *a, **k: [({"detail": "footsteps"}, "full")])
    monkeypatch.setattr(movement, "_sound_crowds", lambda ctx: [])
    ctx = SimpleNamespace(turn=SimpleNamespace(idx=1))
    deaf = [{"channel": "hearing", "acuity": "deaf"}]
    assert movement._treads_reach(ctx, scene, PLAYER, "Mara", "run")
    assert not movement._treads_reach(ctx, scene, PLAYER, "Mara", "run", deaf)
    scrape = {"source": "Mara", "detail": "a crate scrapes", "room": "store"}
    assert movement._sounds_reach(ctx, scene, PLAYER, "Mara", [scrape])
    assert not movement._sounds_reach(ctx, scene, PLAYER, "Mara", [scrape], deaf)
