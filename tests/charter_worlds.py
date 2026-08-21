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
