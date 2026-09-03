"""Institutions at scale, on real `world.spatial` room graphs.

The hand-written fixtures in `charter_fixtures.py` are six and seven bodies in
one place. These are five hundred and a thousand, across compartments and
streets that `world.spatial.passable_path` walks — which is what turns "the
nearest rated hand" from a phrase into a constraint.

Generated rather than authored, and PURELY so a test can assert against them:
every count, every adjacency and every competence here is a function of the
literal numbers below, so a run is reproducible without storing a fixture the
size of a novel.
"""

from __future__ import annotations

#: Barrier the generated doorways use. `world.spatial` treats this as passable.
DOOR = "open_door"


def _spine(prefix, count, hub=None):
    """`count` rooms in a line, each adjacent to the next, optionally hung off
    a hub. A corridor, a street, a deck — the engine does not care which."""
    rooms = {}
    keys = [f"{prefix}_{i}" for i in range(count)]
    for index, key in enumerate(keys):
        edges = []
        if index:
            edges.append({"to": keys[index - 1], "barrier": DOOR})
        if index + 1 < count:
            edges.append({"to": keys[index + 1], "barrier": DOOR})
        rooms[key] = {"name": key.replace("_", " "), "adjacent": edges}
    if hub and keys:
        rooms[keys[0]]["adjacent"].append({"to": hub, "barrier": DOOR})
    return rooms, keys


def ship_scene(decks=6, per_deck=15):
    """A hull: decks of compartments hung off a central spine.

    90 rooms at the default, which is the scale at which a watch bill has to
    start caring where people are.
    """
    rooms = {}
    spine_rooms, spine = _spine("spine", decks)
    rooms.update(spine_rooms)
    for index, anchor in enumerate(spine):
        deck_rooms, _ = _spine(f"d{index}", per_deck, hub=anchor)
        rooms.update(deck_rooms)
    return {"rooms": rooms}


def town_scene(streets=8, per_street=12):
    """A settlement: streets off a market square, plus fields at the edge."""
    rooms = {"square": {"name": "square", "adjacent": []}}
    for index in range(streets):
        street_rooms, keys = _spine(f"s{index}", per_street, hub="square")
        rooms.update(street_rooms)
        rooms["square"]["adjacent"].append({"to": keys[0], "barrier": DOOR})
    field_rooms, fields = _spine("field", 6, hub="square")
    rooms.update(field_rooms)
    rooms["square"]["adjacent"].append({"to": fields[0], "barrier": DOOR})
    return {"rooms": rooms}


def twin_towns_scene(per_town=10, road=9):
    """Two settlements joined by one long road, and nothing else.

    The road is the only path between them, which is what makes it worth
    guarding: `world.spatial.passable_path` has no alternative to route
    around, so a body on the wrong side of a cut road is genuinely stuck.
    """
    rooms = {}
    up_rooms, up = _spine("up", per_town)
    low_rooms, low = _spine("low", per_town)
    road_rooms, road_keys = _spine("road", road)
    rooms.update(up_rooms)
    rooms.update(low_rooms)
    rooms.update(road_rooms)
    rooms[up[-1]]["adjacent"].append({"to": road_keys[0], "barrier": DOOR})
    rooms[road_keys[0]]["adjacent"].append({"to": up[-1], "barrier": DOOR})
    rooms[road_keys[-1]]["adjacent"].append({"to": low[0], "barrier": DOOR})
    rooms[low[0]]["adjacent"].append({"to": road_keys[-1], "barrier": DOOR})
    return {"rooms": rooms}, up, low, road_keys


def twin_towns(folk=240):
    """Two towns that cannot feed themselves alone, and the road between them.

    EACH NEEDS WHAT THE OTHER MAKES. The upland grows and cannot mill; the
    lowland mills and cannot grow. So `up_bread` draws on `low_flour` and
    `low_bread` draws on `up_grain`, and both draw on `road_open` — the road
    is an INPUT to both chains rather than a thing beside them, which is what
    makes cutting it a famine in two places instead of an inconvenience.

    The road drifts on its own (weather, washouts, whoever is out there) and
    is held open by patrols. It is the only upkeep here that nothing else
    feeds, and the only one whose failure starves two chains at once.

    Modelled as ONE charter over two places rather than two charters with a
    treaty, which is the honest limit of the current model: `depends_on` names
    upkeeps inside one institution. Two genuinely separate charters
    negotiating is a real next step and is registered as such rather than
    faked here.
    """
    scene, up, low, road = twin_towns_scene()
    homes = {"up_field": up[1], "up_oven": up[3], "up_gate": up[-1],
             "low_mill": low[2], "low_oven": low[4], "low_gate": low[0],
             "road_mid": road[len(road) // 2]}

    upkeeps = {
        "road_open": {"place": homes["road_mid"], "drift_per_hour": 0.020,
                      "service_per_hour": 0.075, "floor": 0.30,
                      "requires": {"arms": 1}},
        "up_grain": {"place": homes["up_field"], "drift_per_hour": 0.008,
                     "service_per_hour": 0.045, "floor": 0.20,
                     "requires": {"husbandry": 1}},
        "low_flour": {"place": homes["low_mill"], "drift_per_hour": 0.012,
                      "service_per_hour": 0.060, "floor": 0.25,
                      "requires": {"milling": 1},
                      "depends_on": ["up_grain", "road_open"]},
        "up_bread": {"place": homes["up_oven"], "drift_per_hour": 0.024,
                     "service_per_hour": 0.095, "floor": 0.30,
                     "requires": {"baking": 1},
                     "depends_on": ["low_flour", "road_open"]},
        "low_bread": {"place": homes["low_oven"], "drift_per_hour": 0.024,
                      "service_per_hour": 0.095, "floor": 0.30,
                      "requires": {"baking": 1},
                      "depends_on": ["low_flour"]},
    }
    posts = {
        "patrol_a": {"place": homes["road_mid"], "serves": ["road_open"],
                     "requires": {"arms": 1}},
        "patrol_b": {"place": homes["road_mid"], "serves": ["road_open"],
                     "requires": {"arms": 1}},
        "up_fields": {"place": homes["up_field"], "serves": ["up_grain"],
                      "requires": {"husbandry": 1}},
        "low_mill": {"place": homes["low_mill"], "serves": ["low_flour"],
                     "requires": {"milling": 1}},
        "up_bakehouse": {"place": homes["up_oven"], "serves": ["up_bread"],
                         "requires": {"baking": 1}},
        "low_bakehouse": {"place": homes["low_oven"], "serves": ["low_bread"],
                          "requires": {"baking": 1}},
    }

    bodies = {}
    uplanders = ["husbandry", "baking", "arms", "labour"]
    lowlanders = ["milling", "baking", "arms", "labour"]
    for index in range(folk):
        upland = index % 2 == 0
        trades = uplanders if upland else lowlanders
        trade = trades[(index // 2) % len(trades)]
        home = up if upland else low
        bodies[f"{'up' if upland else 'low'}_{index:03d}"] = {
            "competence": {trade: 2 if index % 11 == 0 else 1},
            "available": True,
            "place": home[(index // 2) % len(home)],
        }
    return {"key": "twin_towns", "scene": scene, "upkeeps": upkeeps,
            "posts": posts, "bodies": bodies,
            "priority": ["road_open", "up_grain", "low_flour", "up_bread",
                         "low_bread"]}


def _departments(scene, names, per_department):
    """Assign each named department a home room off the graph, round-robin."""
    rooms = sorted(scene["rooms"])
    return {name: rooms[(i * per_department) % len(rooms)]
            for i, name in enumerate(names)}


def big_ship(crew=500):
    """A ship with a real watch bill: eight departments, ~1 post per 8 hands.

    Upkeeps drift slowly enough that a full crew holds them and fast enough
    that losing a department is felt within days.
    """
    scene = ship_scene()
    depts = ["engineering", "environmental", "navigation", "medical",
             "ordnance", "supply", "signals", "structural"]
    homes = _departments(scene, depts, 7)

    upkeeps, posts, bodies = {}, {}, {}
    for dept in depts:
        place = homes[dept]
        upkeeps[f"{dept}_readiness"] = {
            "place": place, "drift_per_hour": 0.012,
            "service_per_hour": 0.070, "floor": 0.25,
            "requires": {dept: 1}}
        # Three watches a department, so a rota exists to be short-handed.
        for watch in range(3):
            posts[f"{dept}_watch_{watch}"] = {
                "place": place, "serves": [f"{dept}_readiness"],
                "requires": {dept: 2 if watch == 0 else 1}}

    # BERTHED NEAR THEIR OWN STATION, because a body scattered uniformly over
    # ninety-six compartments mostly cannot reach the post it is rated for.
    # The first run of this fixture put every supply hand out of reach of the
    # supply space and the department failed for want of a corridor rather
    # than for want of people — which is a layout mistake, not an engine one,
    # and exactly the sort a big generated world makes silently.
    from world.spatial import passable_neighbors
    near = passable_neighbors(scene)

    def berths(place, wanted):
        """`place` and its neighbourhood, breadth-first, until `wanted` rooms."""
        seen, frontier = [place], [place]
        while frontier and len(seen) < wanted:
            nxt = []
            for room in frontier:
                for other in sorted(near.get(room, ())):
                    if other not in seen:
                        seen.append(other)
                        nxt.append(other)
            frontier = nxt
        return seen

    quarters = {d: berths(homes[d], 12) for d in depts}
    for index in range(crew):
        dept = depts[index % len(depts)]
        # One rated hand in seven, and SEVEN rather than eight on purpose:
        # with a period equal to the department count, every rated hand lands
        # in the same department and every other `watch_0` reports
        # `no_competence` on day one. The simulation found that within a
        # minute of the crew being generated, which is the argument for
        # generating crews and running them rather than authoring rosters and
        # trusting them.
        level = 2 if index % 7 == 0 else 1
        home = quarters[dept]
        bodies[f"hand_{index:03d}"] = {
            "competence": {dept: level},
            "available": True,
            "place": home[index % len(home)],
        }
    return {"key": "ship", "scene": scene, "upkeeps": upkeeps, "posts": posts,
            "bodies": bodies,
            "priority": [f"{d}_readiness" for d in
                         ["environmental", "engineering", "medical",
                          "navigation", "structural", "ordnance", "signals",
                          "supply"]]}


def big_town(folk=1000):
    """A settlement with a supply chain and a thousand people in it.

    The chain is the same one the small fixture proved: water feeds the
    fields, the fields feed the mill, the mill the ovens, the ovens the
    market.
    """
    scene = town_scene()
    trades = ["labour", "husbandry", "milling", "baking", "trade", "carting"]
    homes = _departments(scene, trades, 11)

    upkeeps = {
        "water_drawn": {"place": homes["labour"], "drift_per_hour": 0.018,
                        "service_per_hour": 0.080, "floor": 0.30,
                        "requires": {"labour": 1}},
        "grain_standing": {"place": homes["husbandry"],
                           "drift_per_hour": 0.006,
                           "service_per_hour": 0.040, "floor": 0.20,
                           "requires": {"husbandry": 1},
                           "depends_on": ["water_drawn"]},
        "flour_milled": {"place": homes["milling"], "drift_per_hour": 0.012,
                         "service_per_hour": 0.060, "floor": 0.25,
                         "requires": {"milling": 1},
                         "depends_on": ["grain_standing"]},
        "bread_baked": {"place": homes["baking"], "drift_per_hour": 0.026,
                        "service_per_hour": 0.100, "floor": 0.30,
                        "requires": {"baking": 1},
                        "depends_on": ["flour_milled"]},
        "market_stocked": {"place": homes["trade"], "drift_per_hour": 0.022,
                           "service_per_hour": 0.090, "floor": 0.25,
                           "requires": {"trade": 1},
                           "depends_on": ["bread_baked"]},
        "roads_kept": {"place": homes["carting"], "drift_per_hour": 0.003,
                       "service_per_hour": 0.030, "floor": 0.15,
                       "requires": {"carting": 1}},
    }
    posts = {}
    for trade, upkeep in zip(trades, upkeeps):
        for shift in range(2):
            posts[f"{trade}_shift_{shift}"] = {
                "place": upkeeps[upkeep]["place"], "serves": [upkeep],
                "requires": {trade: 1}}

    rooms = sorted(scene["rooms"])
    bodies = {}
    for index in range(folk):
        trade = trades[index % len(trades)]
        bodies[f"folk_{index:04d}"] = {
            "competence": {trade: 2 if index % 9 == 0 else 1},
            "available": True,
            "place": rooms[index % len(rooms)],
        }
    return {"key": "town", "scene": scene, "upkeeps": upkeeps, "posts": posts,
            "bodies": bodies,
            "priority": ["water_drawn", "grain_standing", "flour_milled",
                         "bread_baked", "market_stocked", "roads_kept"]}


def small_town():
    """A dozen rooms a body can be watched walking across.

    Two streets off a square, a market, a tavern, a smithy, two houses and
    one private back room (a berth that is no post's and no commons' place).
    Every charter place IS a room id, so `charter_move` takes its scene
    branch rather than the no-scene branch every live charter world takes
    (`docs/UNBUILT.md` §1.10a). Built for the traversal prototype: small
    enough that a walk of four rooms is most of the map, so a body that
    teleports and a body that walks are distinguishable in one window.
    """
    rooms = {}

    def room(key, *edges):
        rooms[key] = {"name": key.replace("_", " "),
                      "adjacent": [{"to": to, "barrier": DOOR}
                                   for to in edges]}

    room("square", "north_0", "south_0", "market")
    room("north_0", "square", "north_1")
    room("north_1", "north_0", "north_2", "tavern")
    room("north_2", "north_1", "house_a")
    room("south_0", "square", "south_1", "smithy")
    room("south_1", "south_0", "house_b")
    room("market", "square")
    room("tavern", "north_1")
    room("smithy", "south_0")
    room("house_a", "north_2")
    room("house_b", "south_1", "house_b_back")
    room("house_b_back", "house_b")
    scene = {"rooms": rooms}

    upkeeps = {
        "forge_lit": {"place": "smithy", "drift_per_hour": 0.02,
                      "service_per_hour": 0.08, "floor": 0.3,
                      "requires": {"smithing": 1}},
        "stall_stocked": {"place": "market", "drift_per_hour": 0.02,
                          "service_per_hour": 0.08, "floor": 0.3,
                          "requires": {"trade": 1}},
        "ale_kept": {"place": "tavern", "drift_per_hour": 0.02,
                     "service_per_hour": 0.08, "floor": 0.3,
                     "requires": {"hosting": 1}},
    }
    posts = {
        "smith_shift": {"place": "smithy", "serves": ["forge_lit"],
                        "requires": {"smithing": 1}},
        "stall_shift": {"place": "market", "serves": ["stall_stocked"],
                        "requires": {"trade": 1}},
        "tavern_shift": {"place": "tavern", "serves": ["ale_kept"],
                         "requires": {"hosting": 1}},
    }
    bodies = {
        "smith": {"competence": {"smithing": 2}, "place": "house_a",
                  "berth": "house_a", "available": True},
        "stallholder": {"competence": {"trade": 2}, "place": "house_b",
                        "berth": "house_b", "available": True},
        "tapster": {"competence": {"hosting": 2}, "place": "house_b_back",
                    "berth": "house_b_back", "available": True},
    }
    for index in range(5):
        berth = ("house_a", "house_b")[index % 2]
        bodies[f"folk_{index}"] = {
            "competence": {"labour": 1}, "place": berth, "berth": berth,
            "available": True}
    return {"key": "small_town", "scene": scene, "upkeeps": upkeeps,
            "posts": posts, "bodies": bodies,
            "commons": ["square", "tavern"],
            "priority": ["forge_lit", "stall_stocked", "ale_kept"]}


# ---------------------------------------------------------------------------
# Creatures as charter (`docs/design/DESIGN_CREATURES_AS_CHARTER.md`). Three
# institutions whose upkeep is fed from a town's bodies or stock, each the
# same schema with different tables. Nothing below appears in `world/`: the
# nouns here are the fixture's, as `charter_fixtures.py`'s are.
# ---------------------------------------------------------------------------

#: A pasture with a pen and a treasury with silver: the two things a creature
#: can want that are not people. Keyed by place so any town scene can host it.
def pasture_economy(pen_place, treasury_place):
    return {
        "goods": {"livestock": {"base_value": 2.0, "unit": "head"},
                  "silver": {"base_value": 5.0, "unit": "lot"}},
        "stocks": {"pen": {"livestock": 12.0}, "treasury": {"silver": 6.0}},
        "targets": {"pen": {"livestock": {"minimum": 3, "desired": 12,
                                          "capacity": 16}},
                    "treasury": {"silver": {"minimum": 1, "desired": 6,
                                            "capacity": 12}}},
        "flows": {"lambing": {"holder": "pen", "good": "livestock",
                              "kind": "produce", "lots_per_hour": 0.01}},
        "markets": {"pen": {"place": pen_place, "holder": "pen"},
                    "treasury": {"place": treasury_place,
                                 "holder": "treasury"}},
    }


def with_wilds(scene, edge_room, *, den="den", wood="wood", cave="cave"):
    """The rooms beyond a town's edge: a wood off ``edge_room``, a den off the
    wood (small), and a cave off the wood (large, for a large thing). One
    tiny room off the wood too, so a footprint has something not to fit."""
    scene = {"rooms": {k: dict(v, adjacent=list(v.get("adjacent") or ()))
                       for k, v in scene["rooms"].items()}}
    rooms = scene["rooms"]
    rooms[edge_room]["adjacent"].append({"to": wood, "barrier": "open"})
    rooms[wood] = {"name": wood, "adjacent": [
        {"to": edge_room, "barrier": "open"}, {"to": den, "barrier": "open"},
        {"to": cave, "barrier": "open"}, {"to": "burrow", "barrier": "open"}]}
    rooms[den] = {"name": den, "size": "small",
                  "adjacent": [{"to": wood, "barrier": "open"}]}
    rooms[cave] = {"name": cave, "size": "large",
                   "adjacent": [{"to": wood, "barrier": "open"}]}
    rooms["burrow"] = {"name": "burrow", "size": "tiny",
                       "adjacent": [{"to": wood, "barrier": "open"}]}
    return scene


def guarded_town(town, *, pen_place, hall_place, treasury_place=None):
    """A town that can answer: a reeve with the authority to call the watch,
    a herder posted at the pen who reports to the reeve, stock to lose and
    silver to pay with. The town's own posts and bodies are untouched."""
    town = {k: (dict(v) if isinstance(v, dict) else v)
            for k, v in town.items()}
    town["posts"] = dict(town["posts"])
    town["bodies"] = dict(town["bodies"])
    town["economy"] = pasture_economy(pen_place, treasury_place or hall_place)
    town["posts"]["reeve"] = {"place": hall_place, "serves": [],
                              "requires": {"office": 1},
                              "authority": ["mobilise"]}
    town["posts"]["herder"] = {"place": pen_place, "serves": [],
                               "requires": {"husbandry": 1},
                               "reports_to": "reeve"}
    town["bodies"]["reeve"] = {"competence": {"office": 2, "arms": 1},
                               "place": hall_place, "berth": hall_place,
                               "available": True}
    # A crew of three, as the generator tops every continuous post: one at
    # the pen, two off the bill -- and the two off it are who carries what
    # the pen saw to the square (`charter_move.errands`, social phases).
    for index in range(3):
        town["bodies"][f"herder_{index}"] = {
            "competence": {"husbandry": 1}, "place": pen_place,
            "berth": pen_place, "available": True}
    # A claim told once arrives at `RETOLD_RETENTION` (0.6) of its strength;
    # this town acts on a neighbour's word, not only on what its reeve saw.
    town["mobilisation"] = {"credence": 0.5, "duration_hours": 48.0,
                            "crew_fraction": 0.25, "requires": {}}
    return town


def wolf_pack(scene, *, lair="den", ground, size=4):
    """Nocturnal, livestock first, no doors, moves its den when a member is
    killed, hunts harder when nothing has fed it."""
    bodies = {f"hound_{i}": {"competence": {"fang": 1}, "place": lair,
                             "berth": lair, "available": True}
              for i in range(size)}
    return {
        "key": "pack", "scene": scene,
        "upkeeps": {"belly": {"place": lair, "level": 0.7, "floor": 0.3,
                              "drift_per_hour": 0.015,
                              "service_per_hour": 0.0}},
        "posts": {"hunt": {"place": ground, "serves": ["belly"],
                           "requires": {"fang": 1}}},
        "bodies": bodies, "priority": ["belly"],
        "creature": {
            "prey": ["stock", "unposted", "posted"],
            "senses": {"range_rooms": 2}, "footprint": "small",
            "can_open_doors": False, "encounter_odds": 0.6,
            "kill_ceiling": 1, "stock_lots": 1.0,
            "fed": {"upkeep": "belly", "per_body": 0.5, "per_lot": 0.3},
            "spoor": {"body": "a carcass torn open",
                      "stock": "a broken fence and blood on the grass",
                      "tracks": "paw prints in the mud", "hours": 72},
            "active_phases": ["dusk", "night", "pre-dawn"],
            "boldness": 0.5,
        },
        "triggers": [
            {"id": "a_member_killed_moves_the_den",
             "on": "event:harm_done", "where": {"side": "suffered"},
             "refractory_hours": 48.0,
             "then": [{"op": "intervene",
                       "intervention": {"op": "relocate", "to": "nearest",
                                        "cause": "a member was hurt"}}]},
        ],
    }


def bandit_band(scene, *, lair="cave", ground, size=5):
    """Robbery as predation on stock: opens doors, takes people rather than
    killing them, loses its nerve and moves on when hunted."""
    bodies = {f"cutthroat_{i}": {"competence": {"knife": 1}, "place": lair,
                                 "berth": lair, "available": True}
              for i in range(size)}
    return {
        "key": "band", "scene": scene,
        "upkeeps": {"purse": {"place": lair, "level": 0.5, "floor": 0.25,
                              "drift_per_hour": 0.01,
                              "service_per_hour": 0.0}},
        "posts": {"lookout": {"place": ground, "serves": ["purse"],
                              "requires": {"knife": 1}}},
        "bodies": bodies, "priority": ["purse"],
        "creature": {
            "prey": ["stock", "unposted"],
            "senses": {"range_rooms": 3}, "footprint": "point",
            "can_open_doors": True, "encounter_odds": 0.5,
            "kill_ceiling": 1, "stock_lots": 2.0, "take": True,
            "fed": {"upkeep": "purse", "per_body": 0.3, "per_lot": 0.4},
            "spoor": {"body": "", "stock": "a broken strongbox",
                      "tracks": "boot prints and a dropped knife",
                      "hours": 96},
            "active_phases": [], "boldness": 0.6,
            "hoard_holder": "loot",
        },
        "triggers": [
            {"id": "hunted_once_loses_nerve",
             "on": "event:harm_done", "where": {"side": "suffered"},
             "refractory_hours": 24.0,
             "then": [{"op": "intervene",
                       "intervention": {"op": "creature_dial",
                                        "field": "boldness",
                                        "delta": -0.5}}]},
            {"id": "hunted_again_moves_on",
             "on": "event:harm_done", "where": {"side": "suffered"},
             "refractory_hours": 0.0, "odds": 0.5,
             "then": [{"op": "intervene",
                       "intervention": {"op": "relocate", "to": "nearest",
                                        "cause": "hunted"}}]},
        ],
    }


def dragon(scene, *, lair="cave", ground, town_key="town"):
    """Solitary, large, a hoard it wants filled, a tribute bargain it keeps
    until it goes hungry, and a long sleep after it eats."""
    return {
        "key": "wyrm", "scene": scene,
        "upkeeps": {"maw": {"place": lair, "level": 0.8, "floor": 0.3,
                            # Half a maw a week: a lot of tribute a week
                            # (`per_lot` 0.5) exactly keeps it, so the
                            # bargain holds while the town pays and breaks
                            # the week it cannot.
                            "drift_per_hour": 0.003,
                            "service_per_hour": 0.0}},
        "posts": {"perch": {"place": ground, "serves": ["maw"],
                            "requires": {"flame": 1}}},
        "bodies": {"wyrm": {"competence": {"flame": 3}, "place": lair,
                            "berth": lair, "available": True}},
        "priority": ["maw"],
        "creature": {
            "prey": ["stock", "posted", "unposted"],
            "senses": {"range_rooms": 4}, "footprint": "run",
            "can_open_doors": False, "encounter_odds": 0.8,
            "kill_ceiling": 2, "stock_lots": 3.0,
            "contest": {"capability": 6.0, "caution": 0.05},
            "fed": {"upkeep": "maw", "per_body": 0.9, "per_lot": 0.5},
            "spoor": {"body": "a scorched carcass",
                      "stock": "a scorched, emptied pen",
                      "tracks": "a wide swathe of scorched ground",
                      "hours": 168},
            "active_phases": [], "boldness": 0.9, "hoard_holder": "hoard",
            "bargains": [{"with": town_key, "good": "silver", "lots": 1.0,
                          "every_hours": 168.0, "holder": "treasury"}],
        },
        "triggers": [
            {"id": "fed_it_sleeps",
             "on": "event:goods_exchanged", "where": {"side": "dealt"},
             "refractory_hours": 72.0,
             "then": [{"op": "intervene",
                       "intervention": {"op": "drift_dial", "upkeep": "maw",
                                        "drift_per_hour": 0.0,
                                        "until_hours": 72.0,
                                        "cause": "fed"}}]},
        ],
    }
