"""Couriers: information on a route with a body, never on a timer.

Every test here defends the author's §9.1 constraint against the cheap
implementation: a `due_seconds` fuse wearing a courier's name would be a timer
in a costume, uninterceptable by construction. So these pin position-on-route,
clock-driven movement over the one passable graph, delivery that degrades,
interference that requires a body in the room, silencing that actually stops
the news, and a road that rewinds with the story.
"""

from __future__ import annotations

import json
import time
import types

KEEP, GATE, ROAD, SQUARE = "keep", "gate", "road", "square"


def _edges(*targets):
    return [{"to": t, "barrier": "open"} for t in targets]


def _scene():
    return {
        "rooms": {
            KEEP: {"name": "The Keep", "adjacent": _edges(GATE)},
            GATE: {"name": "The Gate", "adjacent": _edges(KEEP, ROAD)},
            ROAD: {"name": "The Road", "adjacent": _edges(GATE, SQUARE)},
            SQUARE: {"name": "The Square", "adjacent": _edges(ROAD)},
        },
        "positions": {"Maelor": KEEP, "Sera": SQUARE, "Corin": ROAD},
    }


def _world(db, *, held_claim="three riders took the grain at the square"):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Courier story", "", time.time()))
    chars = {}
    for name, uid in (("Maelor", "maelor_uid"), ("Sera", "sera_uid"),
                      ("Corin", "corin_uid")):
        sheet = json.dumps({"identity": {"name": name, "uid": uid}})
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, sheet, "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars[name] = char_id
    # The sender already witnessed something; couriers move what is HELD.
    db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
          (json.dumps({"carried_reports": [{
              "world_event_id": "event:grain", "source_event_id": "",
              "claim": held_claim, "kind": "consequence",
              "occurred_at": 10.0, "acquired_turn": 1,
              "acquired_location": KEEP, "current_location": KEEP,
              "route": [KEEP], "hops": 0, "retellings": 0, "told_by": "",
              "provenance": "witnessed_surface"}]}),
           cid, chars["Maelor"]))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=1, idx=4, frame_id=None),
    )
    return cid, chars, _scene(), ctx


def _send(sender="Maelor", to=SQUARE, **over):
    op = {"op": "send", "sender": sender, "to_room": to,
          "world_event_id": "event:grain", "method": "word",
          "pace": "riding", "description": "a rider"}
    op.update(over)
    return op


def _run(ctx, scene, ops=(), names=(), places=()):
    from couriers import run_couriers

    return run_couriers(ctx, scene, list(ops), names=names, places=places)


def _tick(db, cid, seconds):
    clock = db.wget(cid, "simulation_clock", {}) or {}
    clock["elapsed_seconds"] = float(clock.get("elapsed_seconds") or 0) + seconds
    db.wset(cid, "simulation_clock", clock)


def _couriers(db, cid):
    return db.wget(cid, "couriers", []) or []


def _reports(db, cid, char_id):
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (cid, char_id), one=True)
    return (json.loads(row["state"] or "{}")).get("carried_reports") or []


def test_a_courier_is_somewhere_specific_and_the_clock_moves_him(temp_db):
    """A due_seconds fuse wearing a courier's name is a timer in a costume:
    nothing 'in transit' can be intercepted. The courier must stand in a real
    room on a real route and advance one passable edge per paid pace."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(ctx, scene, [_send()])
    assert metrics["dispatched"] == 1 and not rejected
    courier = _couriers(temp_db, cid)[0]
    assert courier["at"] == KEEP                # seen leaving, not teleported
    assert courier["route"] == [KEEP, GATE, ROAD, SQUARE]

    _tick(temp_db, cid, 240)                    # one riding pace
    _run(ctx, scene)
    assert _couriers(temp_db, cid)[0]["at"] == GATE

    _tick(temp_db, cid, 480)                    # two more paces at once
    metrics, _ = _run(ctx, scene)
    courier = _couriers(temp_db, cid)[0]
    assert courier["status"] == "delivered"     # reached the square and spoke
    assert metrics["courier_delivered"] == 1


def test_a_beat_too_short_to_pay_a_pace_moves_nobody(temp_db):
    """Movement is priced in simulation time, not in beats: fifty rapid
    dialogue beats must not walk a rider across the map for free."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    for _ in range(5):
        _tick(temp_db, cid, 30)
        _run(ctx, scene)
    assert _couriers(temp_db, cid)[0]["at"] == KEEP


def test_word_of_mouth_arrives_two_mouths_fainter_and_anonymous(temp_db):
    """The rumor mechanic dies if delivery hands over the sender's exact
    words with the sender's name on them: the recipient would hold the truth
    they never earned, attributed to a mind three rooms away."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()], names=("Maelor",), places=("the square",))
    _tick(temp_db, cid, 720)
    _run(ctx, scene, names=("Maelor",), places=("the square",))
    report = _reports(temp_db, cid, chars["Sera"])[0]
    assert report["retellings"] == 2            # sender->rider, rider->Sera
    assert "three" not in report["claim"]       # the count went first
    assert report["told_by"] == "a rider"       # a role, never a name
    assert report["provenance"] == "told"


def test_a_letter_arrives_verbatim_because_it_is_not_retold(temp_db):
    """Degrading a sealed letter per room crossed would rebuild the
    hops-degrade confusion carriers.py exists to keep apart: movement is
    free, mouths cost. A letter has no mouths."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send(method="letter", addressee="Sera")],
         names=("Maelor",), places=("the square",))
    _tick(temp_db, cid, 720)
    _run(ctx, scene, names=("Maelor",), places=("the square",))
    report = _reports(temp_db, cid, chars["Sera"])[0]
    assert report["claim"] == "three riders took the grain at the square"
    assert report["retellings"] == 0
    assert report["provenance"] == "letter"


def test_silencing_a_courier_stops_the_information(temp_db):
    """The whole point of a route existing: if killing the rider changed
    nothing, the courier was a broadcast with scenery. After a silence, the
    news must never arrive anywhere, however long the clock runs."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    _tick(temp_db, cid, 480)
    _run(ctx, scene)                            # rider now on the road
    courier = _couriers(temp_db, cid)[0]
    assert courier["at"] == ROAD
    metrics, rejected = _run(
        ctx, scene, [{"op": "silence", "courier_id": courier["uid"],
                      "by": "Corin"}])
    assert metrics["courier_silenced"] == 1 and not rejected
    _tick(temp_db, cid, 10_000)
    _run(ctx, scene)
    assert _reports(temp_db, cid, chars["Sera"]) == []
    assert _couriers(temp_db, cid)[0]["status"] == "silenced"


def test_interference_requires_a_body_in_the_riders_room(temp_db):
    """A route the player can cut from anywhere is a route in name only --
    silencing would be a menu action, not a deed. Corin on the road cannot
    stop a rider still inside the keep."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    courier = _couriers(temp_db, cid)[0]        # still at the keep
    metrics, rejected = _run(
        ctx, scene, [{"op": "silence", "courier_id": courier["uid"],
                      "by": "Corin"}])
    assert metrics["courier_silenced"] == 0 and len(rejected) == 1
    _tick(temp_db, cid, 720)
    _run(ctx, scene)
    assert _reports(temp_db, cid, chars["Sera"])  # the news still arrived


def test_questioning_copies_the_story_without_stopping_the_rider(temp_db):
    """Question and silence must stay different acts: a player who stops a
    rider to ask has not cut the route, and a rider once questioned must not
    ride on message-less."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    _tick(temp_db, cid, 480)
    _run(ctx, scene)
    courier = _couriers(temp_db, cid)[0]
    assert courier["at"] == ROAD
    metrics, rejected = _run(
        ctx, scene, [{"op": "question", "courier_id": courier["uid"],
                      "listener": "Corin"}])
    assert metrics["courier_questioned"] == 1 and not rejected
    corin = _reports(temp_db, cid, chars["Corin"])[0]
    assert corin["retellings"] == 2 and corin["told_by"] == "a rider"
    _tick(temp_db, cid, 240)
    _run(ctx, scene)
    assert _reports(temp_db, cid, chars["Sera"])  # still delivered


def test_the_player_persona_can_silence_a_rider(temp_db):
    """Found played, not read: `persona_of` normalizes to the character
    shape with the name under `identity`, and reading the top level made
    every player nameless -- so the one body the design most wants stopping
    riders was refused as 'not a body the story can place'."""
    from pipeline_context import ChatData

    cid, chars, scene, ctx = _world(temp_db)
    pid = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                     ("Wren", json.dumps({"name": "Wren"}), "{}"))
    temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (pid, cid))
    ctx.chat = ChatData(id=cid, name="", persona_id=pid, lorebook_id=None,
                        scenario="", created=0.0)
    scene["positions"]["Wren"] = ROAD
    _run(ctx, scene, [_send()])
    _tick(temp_db, cid, 480)
    _run(ctx, scene)
    courier = _couriers(temp_db, cid)[0]
    assert courier["at"] == ROAD
    metrics, rejected = _run(
        ctx, scene, [{"op": "silence", "courier_id": courier["uid"],
                      "by": "Wren"}])
    assert metrics["courier_silenced"] == 1 and not rejected
    _tick(temp_db, cid, 10_000)
    _run(ctx, scene)
    assert _reports(temp_db, cid, chars["Sera"]) == []


def test_a_sender_cannot_dispatch_what_nobody_holds(temp_db):
    """The firewall: without the holding check the Director could hand any
    mind any fact by writing one op -- the exact omniscience-by-sentence
    defect apply_tellings refuses, arriving through a new door."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(
        ctx, scene, [_send(sender="Sera", world_event_id="event:grain")])
    assert metrics["dispatched"] == 0 and len(rejected) == 1
    assert _couriers(temp_db, cid) == []


def test_a_lie_rides_exactly_like_the_truth(temp_db):
    """§9.2: an antagonist's invented claim enters the network at a point in
    space and travels like everything else -- and the listener's copy must be
    indistinguishable from a report of something real, or minds could detect
    lies by introspection and stop being deceivable."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(ctx, scene, [_send(
        world_event_id="", claim="the boy from the Fenwater poisoned it")])
    assert metrics["dispatched"] == 1 and not rejected
    own = [r for r in _reports(temp_db, cid, chars["Maelor"])
           if r["provenance"] == "invented"]
    assert own and own[0]["world_event_id"].startswith("claim:")
    _tick(temp_db, cid, 720)
    _run(ctx, scene)
    report = _reports(temp_db, cid, chars["Sera"])[0]
    assert report["provenance"] == "told"       # nothing marks it false
    assert report["world_event_id"].startswith("claim:")


def test_a_shut_door_holds_the_rider_where_he_is(temp_db):
    """Rerouting around a closed door would need a second pathfinder, and
    honouring the stale route would ride through a wall. A held rider stays
    somewhere specific -- which is what makes him catchable."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    scene["rooms"][GATE]["adjacent"] = [
        {"to": KEEP, "barrier": "open"}, {"to": ROAD, "barrier": "closed_door"}]
    scene["rooms"][ROAD]["adjacent"] = [
        {"to": GATE, "barrier": "closed_door"}, {"to": SQUARE, "barrier": "open"}]
    _tick(temp_db, cid, 100_000)
    _run(ctx, scene)
    assert _couriers(temp_db, cid)[0]["at"] == GATE
    assert _reports(temp_db, cid, chars["Sera"]) == []


def test_no_passable_route_refuses_the_dispatch(temp_db):
    """A courier minted onto an unwalkable route would be the timer in a
    costume again: with no rooms to pass through there is nothing to
    intercept, so the send must fail loudly at dispatch."""
    cid, chars, scene, ctx = _world(temp_db)
    scene["rooms"][KEEP]["adjacent"] = [{"to": GATE, "barrier": "wall"}]
    scene["rooms"][GATE]["adjacent"][0] = {"to": KEEP, "barrier": "wall"}
    metrics, rejected = _run(ctx, scene, [_send()])
    assert metrics["dispatched"] == 0 and len(rejected) == 1


def test_the_perception_surface_shows_the_rider_and_never_the_message(temp_db):
    """Interception is theoretical until somebody can SEE the courier -- and
    a surface that included the claim would broadcast the very report whose
    delivery the route exists to price."""
    from agents.common import couriers_for_room

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    seen = couriers_for_room(cid, scene, KEEP)
    assert seen and seen[0]["courier_id"].startswith("courier:")
    assert seen[0]["heading"] == GATE
    assert "grain" not in json.dumps(seen)
    assert couriers_for_room(cid, scene, SQUARE) == []


def test_an_observer_glimpses_a_rider_who_swept_through(temp_db):
    """A courier that only ever exists in the room it stops in teleports
    between sightings, and a route nobody can watch cannot be followed."""
    from agents.common import couriers_for_room

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    _tick(temp_db, cid, 480)                     # two paces: keep -> road
    _run(ctx, scene)
    seen = couriers_for_room(cid, scene, GATE)   # he crossed the gate
    assert seen and "passing through" in seen[0]["what"]
    assert seen[0]["heading"] == ROAD


def test_checkpoint_restore_rewinds_the_road(temp_db):
    """New durable state must rewind with the story: a reroll that left a
    rider (or un-silenced one) would deliver news from a beat that no longer
    happened -- the relationship_events precedent, applied to the road."""
    from checkpoints import ensure_checkpoint, restore_checkpoint

    cid, chars, scene, ctx = _world(temp_db)
    ensure_checkpoint(cid, 4)
    _run(ctx, scene, [_send()])
    assert _couriers(temp_db, cid)
    restore_checkpoint(cid, 4)
    assert _couriers(temp_db, cid) == []

    _run(ctx, scene, [_send()])
    ensure_checkpoint(cid, 5)
    courier = _couriers(temp_db, cid)[0]
    _run(ctx, scene, [{"op": "silence", "courier_id": courier["uid"],
                       "by": "Maelor"}])
    assert _couriers(temp_db, cid)[0]["status"] == "silenced"
    restore_checkpoint(cid, 5)
    assert _couriers(temp_db, cid)[0]["status"] == "en_route"


def test_the_archive_carries_the_road(temp_db):
    """Archive export/import must move couriers with the chat, or an
    imported story would quietly lose every message still travelling."""
    from chat_archive import ChatArchiveService

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_send()])
    blob = ChatArchiveService.export_chat(None, cid)
    assert any("couriers" in key for key in (blob.get("world") or {}))


class _Chat(dict):
    """A chat with both `.id` and `.get`, as the real one has.

    The bare `SimpleNamespace(id=cid)` every other test here uses has no
    `.get`, so `persona_of` cannot resolve a persona from it and the player
    stays out of the index -- which is the safe default and the reason those
    tests are untouched by this.
    """

    @property
    def id(self):
        return self["id"]


class TestThePlayerCanSendNews:
    """The player was the one participant who structurally could not.

    `_cast_index` reads cast rows; a persona has none, so every carrier verb
    refused the player by construction -- "courier sender 'Corin' is not a
    registered character". Two independent models, given a beat where the
    player pays a rider to carry word east, both wrote a well-formed
    `courier_ops` send and both were refused for this reason. One of them also
    wrote an artifact op when the player nailed a notice to a board, refused
    the same way.

    The deeper half was that a persona had nowhere to HOLD a report:
    `chat_chars.cstate` is a cast row's column. Player carrier state now lives
    in a world key, which is the right shape because there is exactly one
    persona per chat.
    """

    def _world_with_persona(self, db):
        persona_id = db.qi(
            "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
            ("Corin", json.dumps({"name": "Corin"}), "{}"))
        cid = db.qi(
            "INSERT INTO chats(name,scenario,created,persona_id) "
            "VALUES(?,?,?,?)", ("Player sends", "", time.time(), persona_id))
        for name, uid in (("Sera", "sera_uid"),):
            sheet = json.dumps({"identity": {"name": name, "uid": uid}})
            char_id = db.qi(
                "INSERT INTO characters(name,sheet,source,created) "
                "VALUES(?,?,?,?)", (name, sheet, "{}", time.time()))
            db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                  "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
        ctx = types.SimpleNamespace(
            chat=_Chat(id=cid, persona_id=persona_id),
            turn=types.SimpleNamespace(id=1, idx=4, frame_id=None),
        )
        return cid, _scene(), ctx

    def _paid_a_rider(self):
        """The op both models actually wrote, claim and all."""
        return {"op": "send", "sender": "Corin", "to_room": SQUARE,
                "world_event_id": "", "method": "word", "pace": "riding",
                "claim": "the wells of the Vale market are sealed",
                "description": "a lean man on a short-coupled bay pony"}

    def test_the_players_rider_leaves(self, temp_db):
        cid, scene, ctx = self._world_with_persona(temp_db)
        metrics, rejected = _run(ctx, scene, [self._paid_a_rider()])
        assert rejected == []
        assert metrics["dispatched"] == 1

    def test_what_the_player_invented_is_held_where_a_persona_can_hold_it(
            self, temp_db):
        """A claim with no event behind it lands on its author's own row, so
        the player needs a row-shaped place to keep it."""
        from carriers import PERSONA_STATE_KEY, STATE_KEY

        cid, scene, ctx = self._world_with_persona(temp_db)
        _run(ctx, scene, [self._paid_a_rider()])
        held = (temp_db.wget(cid, PERSONA_STATE_KEY, {}) or {}).get(STATE_KEY)
        assert [r["claim"] for r in held] == [
            "the wells of the Vale market are sealed"]

    def test_a_chat_with_no_resolvable_persona_still_refuses(self, temp_db):
        """Failing toward fewer carriers is the safe direction, and keeps
        every existing story behaving exactly as it did. `_world` builds its
        chat with no persona at all, so a sender nobody has registered stays
        refused."""
        cid, chars, scene, ctx = _world(temp_db)
        op = dict(self._paid_a_rider(), sender="Nobody At All")
        _metrics, rejected = _run(ctx, scene, [op])
        assert any("not a registered character" in r for r in rejected)
