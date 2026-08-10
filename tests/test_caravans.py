"""Caravans: multi-stop trader routes that trade news both ways.

Every test here defends the line the design deferred the feature over: "a
courier with waypoints is a loop over the same object, but honest trader
behaviour (loitering, markets, picking up news en route) needs design". So
these pin the dwell (a halt charged in simulation time, which is what makes
robbing the wagon at the market possible), the two-way exchange at a stop
(a caravan that only delivers is a courier with extra hops), degradation at
every mouth it crosses, interception that stops the whole wagon, and a road
that rewinds with the story.
"""

from __future__ import annotations

import json
import time
import types

FARM, LANE, MARKET, ROAD, TOWN = "farm", "lane", "market", "road", "town"

THE_NEWS = "three riders took the grain at the square"


def _edges(*targets):
    return [{"to": t, "barrier": "open"} for t in targets]


def _scene():
    return {
        "rooms": {
            FARM: {"name": "The Farm", "adjacent": _edges(LANE)},
            LANE: {"name": "The Lane", "adjacent": _edges(FARM, MARKET)},
            MARKET: {"name": "The Market", "size": "large",
                     "adjacent": _edges(LANE, ROAD)},
            ROAD: {"name": "The Road", "adjacent": _edges(MARKET, TOWN)},
            TOWN: {"name": "The Town", "adjacent": _edges(ROAD)},
        },
        "positions": {"Maelor": FARM, "Sera": TOWN, "Corin": ROAD,
                      "Bram": MARKET},
    }


def _world(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Caravan story", "", time.time()))
    chars = {}
    for name in ("Maelor", "Sera", "Corin", "Bram"):
        sheet = json.dumps({"identity": {"name": name,
                                         "uid": "%s_uid" % name.lower()}})
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, sheet, "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars[name] = char_id
    db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
          (json.dumps({"carried_reports": [{
              "world_event_id": "event:grain", "source_event_id": "",
              "claim": THE_NEWS, "kind": "consequence",
              "occurred_at": 10.0, "acquired_turn": 1,
              "acquired_location": FARM, "current_location": FARM,
              "route": [FARM], "hops": 0, "retellings": 0, "told_by": "",
              "provenance": "witnessed_surface"}]}),
           cid, chars["Maelor"]))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=1, idx=4, frame_id=None),
    )
    return cid, chars, _scene(), ctx


def _market_crowd(db, cid, *, reports=()):
    import crowds

    crowd = crowds.new_crowd(cid, MARKET, band="a few dozen",
                             composition="market traders", since_turn=1)
    for report in reports:
        crowd = crowds.add_hearsay(crowd, dict(report))
    db.wset(cid, "crowds", [crowd])
    return crowd


def _witnessed(claim=THE_NEWS):
    return {"world_event_id": "event:grain", "source_event_id": "",
            "claim": claim, "kind": "consequence", "occurred_at": 10.0,
            "acquired_turn": 1, "retellings": 0, "told_by": "",
            "provenance": "witnessed_surface"}


def _caravan_send(**over):
    op = {"op": "send", "to_room": TOWN, "stops": [MARKET],
          "from_room": FARM, "description": "a trader's caravan",
          "pace": "walking"}
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


def test_a_caravan_route_is_one_walkable_road_through_its_stops(temp_db):
    """Two pathfinders diverge and then disagree: the stop list must be
    stitched into ONE route over the same passable graph everyone walks,
    or a caravan could reach a market no walking body could."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(ctx, scene, [_caravan_send()])
    assert metrics["dispatched"] == 1 and not rejected
    caravan = _couriers(temp_db, cid)[0]
    assert caravan["kind"] == "caravan"
    assert caravan["route"] == [FARM, LANE, MARKET, ROAD, TOWN]
    assert caravan["stop_legs"] == [2]
    assert caravan["at"] == FARM                # seen leaving, not teleported


def test_a_caravan_dwells_at_its_stop_instead_of_passing_through(temp_db):
    """A caravan that sweeps through its stop is a courier with extra hops
    -- the exact cheap version the design deferred. The halt must be paid in
    simulation time, because 'ridden with, robbed, or beaten there' all
    require the wagon to genuinely stand in the market for a while."""
    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_caravan_send()])
    _tick(temp_db, cid, 1200)                   # two walking paces
    _run(ctx, scene)
    assert _couriers(temp_db, cid)[0]["at"] == MARKET

    _tick(temp_db, cid, 2200)                   # pace paid, dwell not yet
    _run(ctx, scene)
    assert _couriers(temp_db, cid)[0]["at"] == MARKET

    _tick(temp_db, cid, 200)                    # dwell + pace now paid
    _run(ctx, scene)
    assert _couriers(temp_db, cid)[0]["at"] == ROAD


def test_news_boards_at_a_stop_and_arrives_fainter_down_the_road(temp_db):
    """The deferred feature itself: a caravan must PICK NEWS UP as well as
    put it down, or a far town can only ever learn what somebody paid a
    rider to say. The market's talk boards the wagon one mouth on and is
    delivered another mouth on -- late, vague, and by a route a body could
    have ridden with."""
    cid, chars, scene, ctx = _world(temp_db)
    _market_crowd(temp_db, cid, reports=[_witnessed()])
    metrics, rejected = _run(
        ctx, scene, [_caravan_send()],
        names=("Maelor",), places=("the square",))
    assert metrics["dispatched"] == 1 and not rejected

    _tick(temp_db, cid, 1200)
    metrics, _ = _run(ctx, scene, names=("Maelor",), places=("the square",))
    assert metrics["caravan_stops"] == 1
    assert metrics["caravan_picked_up"] == 1
    caravan = _couriers(temp_db, cid)[0]
    assert caravan["at"] == MARKET
    assert caravan["cargo"][0]["retellings"] == 1     # the crowd told the trader
    assert caravan["cargo"][0]["provenance"] == "told"

    _tick(temp_db, cid, 3000)
    metrics, _ = _run(ctx, scene, names=("Maelor",), places=("the square",))
    assert metrics["courier_delivered"] == 1
    report = _reports(temp_db, cid, chars["Sera"])[0]
    assert report["retellings"] == 2            # crowd -> trader -> Sera
    assert "three" not in report["claim"]       # the count went first
    assert "the square" not in report["claim"]  # the place went second
    assert report["told_by"] == "a trader's caravan"
    assert report["provenance"] == "told"


def test_a_caravan_tells_the_market_what_it_carries(temp_db):
    """A caravan that only collects is a vacuum, not a trader: what rides in
    the wagon must be put down where it dwells, into the CROWD -- the
    market's own mouth -- one retelling fainter, so the town between the
    endpoints hears the news too."""
    import crowds

    cid, chars, scene, ctx = _world(temp_db)
    _market_crowd(temp_db, cid)
    metrics, rejected = _run(
        ctx, scene,
        [_caravan_send(sender="Maelor", from_room="",
                       world_event_id="event:grain", method="word")],
        names=("Maelor",), places=("the square",))
    assert metrics["dispatched"] == 1 and not rejected

    _tick(temp_db, cid, 1200)
    metrics, _ = _run(ctx, scene, names=("Maelor",), places=("the square",))
    assert metrics["caravan_put_down"] == 1
    crowd = (temp_db.wget(cid, "crowds", []) or [])[0]
    heard = crowds.crowd_hearsay(crowd)
    assert len(heard) == 1
    # Maelor -> trader at dispatch, trader -> market at the stop.
    assert heard[0]["retellings"] == 2
    assert heard[0]["told_by"] == "a trader's caravan"
    assert "three" not in heard[0]["claim"]

    # The wagon still carries it: putting news down is not giving it away.
    caravan = _couriers(temp_db, cid)[0]
    assert caravan["cargo"][0]["world_event_id"] == "event:grain"


def test_a_silenced_caravan_delivers_nothing_anywhere(temp_db):
    """Interception must stop the whole wagon, or a caravan would be the
    broadcast the courier rules exist to refuse: news it gathered at the
    market dies on the road with it."""
    cid, chars, scene, ctx = _world(temp_db)
    _market_crowd(temp_db, cid, reports=[_witnessed()])
    _run(ctx, scene, [_caravan_send()])
    _tick(temp_db, cid, 3600)                   # through the market, onto the road
    _run(ctx, scene)
    caravan = _couriers(temp_db, cid)[0]
    assert caravan["at"] == ROAD and caravan["cargo"]
    metrics, rejected = _run(
        ctx, scene, [{"op": "silence", "courier_id": caravan["uid"],
                      "by": "Corin"}])
    assert metrics["courier_silenced"] == 1 and not rejected
    _tick(temp_db, cid, 100_000)
    _run(ctx, scene)
    assert _reports(temp_db, cid, chars["Sera"]) == []


def test_questioning_a_caravan_yields_its_gathered_news(temp_db):
    """A trader on the road is the interceptable version of the market he
    left: stopping to ask must hand over what the wagon gathered, one mouth
    on, without cutting the route."""
    cid, chars, scene, ctx = _world(temp_db)
    _market_crowd(temp_db, cid, reports=[_witnessed()])
    _run(ctx, scene, [_caravan_send()])
    _tick(temp_db, cid, 3600)
    _run(ctx, scene)
    caravan = _couriers(temp_db, cid)[0]
    assert caravan["at"] == ROAD
    metrics, rejected = _run(
        ctx, scene, [{"op": "question", "courier_id": caravan["uid"],
                      "listener": "Corin"}])
    assert metrics["courier_questioned"] == 1 and not rejected
    corin = _reports(temp_db, cid, chars["Corin"])[0]
    assert corin["retellings"] == 2             # crowd -> trader -> Corin
    assert corin["told_by"] == "a trader's caravan"
    _tick(temp_db, cid, 1000)
    _run(ctx, scene)
    assert _reports(temp_db, cid, chars["Sera"])  # still delivered


def test_a_standing_bill_boards_the_wagon_and_a_torn_one_does_not(temp_db):
    """The artifact network and the caravan network must compose: a notice
    on the market post is public standing information, so a dwelling trader
    reads it and carries it on -- and tearing the bill down BEFORE the
    caravan rolls in must stop that spread, exactly as silencing a courier
    stops a delivery."""
    from artifacts import run_artifacts

    cid, chars, scene, ctx = _world(temp_db)

    # Bram, standing in the market, posts what he is inventing.
    metrics, rejected = run_artifacts(ctx, scene, [{
        "op": "post", "poster": "Bram",
        "claim": "the well on the square is cursed",
        "description": "a warning chalked on a board"}])
    assert metrics["artifacts_posted"] == 1 and not rejected
    artifact_uid = (temp_db.wget(cid, "artifacts", []) or [])[0]["uid"]

    _run(ctx, scene, [_caravan_send()])
    _tick(temp_db, cid, 1200)
    _run(ctx, scene)
    caravan = _couriers(temp_db, cid)[0]
    assert caravan["at"] == MARKET
    assert [c for c in caravan["cargo"] if c["provenance"] == "read"]

    # The negative twin, fresh caravan: the bill comes down first.
    temp_db.wset(cid, "couriers", [])
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    metrics, rejected = run_artifacts(ctx, scene, [{
        "op": "remove", "by": "Bram", "artifact_id": artifact_uid}])
    assert metrics["artifacts_removed"] == 1 and not rejected
    _run(ctx, scene, [_caravan_send()])
    _tick(temp_db, cid, 1200)
    _run(ctx, scene)
    assert _couriers(temp_db, cid)[0]["cargo"] == []


def test_checkpoint_restore_rewinds_the_caravan_and_its_cargo(temp_db):
    """New durable state must rewind with the story: a caravan that
    survived a rollback would deliver news gathered on a road that no
    longer happened."""
    from checkpoints import ensure_checkpoint, restore_checkpoint

    cid, chars, scene, ctx = _world(temp_db)
    _market_crowd(temp_db, cid, reports=[_witnessed()])
    ensure_checkpoint(cid, 4)
    _run(ctx, scene, [_caravan_send()])
    assert _couriers(temp_db, cid)
    restore_checkpoint(cid, 4)
    assert _couriers(temp_db, cid) == []

    _run(ctx, scene, [_caravan_send()])
    _tick(temp_db, cid, 1200)
    _run(ctx, scene)                            # cargo aboard at the market
    assert _couriers(temp_db, cid)[0]["cargo"]
    ensure_checkpoint(cid, 5)
    _tick(temp_db, cid, 3000)
    _run(ctx, scene)                            # delivered at the town
    assert _reports(temp_db, cid, chars["Sera"])
    restore_checkpoint(cid, 5)
    caravan = _couriers(temp_db, cid)[0]
    assert caravan["at"] == MARKET and caravan["status"] == "en_route"
    assert _reports(temp_db, cid, chars["Sera"]) == []


def test_a_courier_without_a_message_is_refused_but_a_caravan_is_not(temp_db):
    """An empty SEND used to be unreachable and must stay refused for a
    courier -- a rider with nothing to say is nobody. A caravan moves for
    its own reasons, so it may set out empty from a named known room and
    let the road fill the wagon; an unknown room stays refused (the
    crowd-minting precedent)."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(ctx, scene, [
        {"op": "send", "to_room": TOWN, "from_room": FARM,
         "description": "a rider"}])
    assert metrics["dispatched"] == 0 and len(rejected) == 1

    metrics, rejected = _run(ctx, scene, [
        _caravan_send(from_room="nowhere_special")])
    assert metrics["dispatched"] == 0 and len(rejected) == 1

    metrics, rejected = _run(ctx, scene, [_caravan_send()])
    assert metrics["dispatched"] == 1 and not rejected
