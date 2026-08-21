"""Two institutions, defined only in this test file.

THE POINT OF KEEPING THEM HERE: if a starship's watch bill and a monastery's
hours are the same five primitives with different nouns, then the engine
learned nothing about spaceflight — which is the whole genre claim of
`docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md` §9. The moment either fixture
needs a field the other does not, the abstraction has sprung a leak and this
file is where it shows.

Neither noun below appears anywhere in `world/charter*.py`. That is asserted,
not merely intended, by `test_charter_genre.py`.
"""

from __future__ import annotations

#: A ship's engineering and bridge watch. Four upkeeps, five posts, six hands.
SHIP = {
    "key": "ship",
    "priority": ["life_support_scrub", "reactor_thermal", "hull_integrity",
                 "watch_bridge"],
    "upkeeps": {
        "life_support_scrub": {
            "place": "environmental", "drift_per_hour": 0.010,
            "service_per_hour": 0.060, "floor": 0.30,
            "requires": {"environmental": 1}},
        "reactor_thermal": {
            "place": "engine_room", "drift_per_hour": 0.020,
            "service_per_hour": 0.080, "floor": 0.25,
            "requires": {"engineering": 2}},
        "hull_integrity": {
            "place": "hull", "drift_per_hour": 0.002,
            "service_per_hour": 0.040, "floor": 0.20,
            "requires": {"engineering": 1}},
        "watch_bridge": {
            "place": "bridge", "drift_per_hour": 0.015,
            "service_per_hour": 0.070, "floor": 0.35,
            "requires": {"navigation": 1}},
    },
    "posts": {
        "engine_watch": {"place": "engine_room",
                         "serves": ["reactor_thermal"],
                         "requires": {"engineering": 2}},
        "damage_control": {"place": "hull", "serves": ["hull_integrity"],
                           "requires": {"engineering": 1}},
        "scrubber_watch": {"place": "environmental",
                           "serves": ["life_support_scrub"],
                           "requires": {"environmental": 1}},
        "bridge_watch": {"place": "bridge", "serves": ["watch_bridge"],
                         "requires": {"navigation": 1}},
        "galley": {"place": "galley", "serves": [], "requires": {}},
    },
    "bodies": {
        "chief":  {"competence": {"engineering": 3}, "available": True},
        "ramos":  {"competence": {"engineering": 2}, "available": True},
        "okonjo": {"competence": {"environmental": 2}, "available": True},
        "vega":   {"competence": {"navigation": 2}, "available": True},
        "hale":   {"competence": {"navigation": 1, "engineering": 1},
                   "available": True},
        "cook":   {"competence": {"engineering": 1}, "available": True},
    },
}

#: The same five primitives, wearing a different century. The priority
#: ordering IS the characterisation: the office above all, and the fire and
#: the copying beneath it.
ABBEY = {
    "key": "abbey",
    "priority": ["the_hours_are_sung", "the_fire_is_kept",
                 "the_copying_advances"],
    "upkeeps": {
        "the_hours_are_sung": {
            "place": "choir", "drift_per_hour": 0.030,
            "service_per_hour": 0.090, "floor": 0.40,
            "requires": {"plainchant": 1}},
        "the_fire_is_kept": {
            "place": "kitchen", "drift_per_hour": 0.020,
            "service_per_hour": 0.070, "floor": 0.25,
            "requires": {"hearth": 1}},
        "the_copying_advances": {
            "place": "scriptorium", "drift_per_hour": 0.004,
            "service_per_hour": 0.030, "floor": 0.10,
            "requires": {"latin": 2}},
    },
    "posts": {
        "cantor": {"place": "choir", "serves": ["the_hours_are_sung"],
                   "requires": {"plainchant": 2}},
        "hebdomadary": {"place": "kitchen", "serves": ["the_fire_is_kept"],
                        "requires": {"hearth": 1}},
        "desk": {"place": "scriptorium", "serves": ["the_copying_advances"],
                 "requires": {"latin": 2}},
    },
    "bodies": {
        "anselm":  {"competence": {"plainchant": 3, "latin": 2},
                    "available": True},
        "bede":    {"competence": {"hearth": 2}, "available": True},
        "cuthbert": {"competence": {"latin": 3}, "available": True},
    },
}

#: A town, which is the fixture that made the model grow `depends_on`.
#:
#: The ship and the abbey are four independent conditions each. A town is a
#: CHAIN: the field feeds the mill, the mill feeds the bakery, the bakery
#: feeds the counter, and the well feeds everybody. Nothing downstream can be
#: kept above what its inputs allow, however competent and however present the
#: body standing the post -- a baker with a cold oven and no flour bakes at
#: the rate the flour permits.
#:
#: Deliberately short-handed: seven bodies, eight posts. A town that could
#: staff everything would never show what it does under strain, which is the
#: only interesting thing about a town.
TOWN = {
    "key": "town",
    "priority": ["water_drawn", "grain_standing", "flour_milled",
                 "bread_baked", "counter_stocked", "road_kept"],
    "upkeeps": {
        "water_drawn": {
            "place": "well", "drift_per_hour": 0.020,
            "service_per_hour": 0.090, "floor": 0.30,
            "requires": {"labour": 1}},
        "grain_standing": {
            "place": "fields", "drift_per_hour": 0.006,
            "service_per_hour": 0.040, "floor": 0.20,
            "requires": {"husbandry": 1},
            "depends_on": ["water_drawn"]},
        "flour_milled": {
            "place": "mill", "drift_per_hour": 0.014,
            "service_per_hour": 0.070, "floor": 0.25,
            "requires": {"milling": 1},
            "depends_on": ["grain_standing"]},
        "bread_baked": {
            "place": "bakehouse", "drift_per_hour": 0.030,
            "service_per_hour": 0.110, "floor": 0.30,
            "requires": {"baking": 1},
            "depends_on": ["flour_milled"]},
        "counter_stocked": {
            "place": "shop", "drift_per_hour": 0.025,
            "service_per_hour": 0.100, "floor": 0.25,
            "requires": {"trade": 1},
            "depends_on": ["bread_baked"]},
        "road_kept": {
            "place": "road", "drift_per_hour": 0.003,
            "service_per_hour": 0.030, "floor": 0.15,
            "requires": {"labour": 1}},
    },
    "posts": {
        "well_turn":   {"place": "well", "serves": ["water_drawn"],
                        "requires": {"labour": 1}},
        "field_hand":  {"place": "fields", "serves": ["grain_standing"],
                        "requires": {"husbandry": 1}},
        "mill_turn":   {"place": "mill", "serves": ["flour_milled"],
                        "requires": {"milling": 1}},
        "oven":        {"place": "bakehouse", "serves": ["bread_baked"],
                        "requires": {"baking": 1}},
        "counter":     {"place": "shop", "serves": ["counter_stocked"],
                        "requires": {"trade": 1}},
        "roadwork":    {"place": "road", "serves": ["road_kept"],
                        "requires": {"labour": 1}},
    },
    "bodies": {
        "maud":   {"competence": {"husbandry": 2, "labour": 1},
                   "available": True},
        "tobin":  {"competence": {"milling": 2, "labour": 1},
                   "available": True},
        "greta":  {"competence": {"baking": 2}, "available": True},
        "alder":  {"competence": {"trade": 2, "labour": 1},
                   "available": True},
        "pell":   {"competence": {"labour": 2}, "available": True},
        "wynn":   {"competence": {"labour": 1, "husbandry": 1},
                   "available": True},
        "harrow": {"competence": {"labour": 1}, "available": True},
    },
}
