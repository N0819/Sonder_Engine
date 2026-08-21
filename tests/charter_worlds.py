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
