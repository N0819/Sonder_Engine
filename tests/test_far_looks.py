"""A far place reads by how it looks from a distance, where the plan says
(`world/landscape.py`, UNBUILT_WORLD §2.40).

The owner chose §2.40's open option on 2026-10-08: the planner writes, for
an outdoor place or a region, HOW IT LOOKS FROM A DISTANCE -- a field of its
own, `far_look`, read by the far layer and never a desc -- and the far layer
says it in place of "open ground", "a sheltered place" or "a building",
keeping those words only where no look is declared. Measured before: about
two thirds of the 259 far-line items in the scratch play db were ground
words ("open ground stretching on" 122, "a wide stretch of open ground"
106). Three rulings bind it: a far place is named only once the mind knows
it, so a look may not carry a name the mind has not learned; a look carries
no light or hour (UNBUILT_WORLD §1.174), no people and no events; and it is
a declared fact a beat may change. Hand-made scenes; the places and words
are illustrations, not the rule.
"""

from __future__ import annotations

import json
import time

from agents import composer
from world.landscape import far_places
from world.scene_memo import scene_read_pass


def _valley(**over):
    """A yard looking east down a line of open fields -- orchard, meadow (an
    oak on it), mill field (a mill fronting it), river bank, far hill -- as
    `test_landscape` lays it out."""
    def field(name, prev, nxt, **room):
        adj = []
        if prev:
            adj.append({"to": prev, "barrier": "open", "dir": "w"})
        if nxt:
            adj.append({"to": nxt, "barrier": "open", "dir": "e"})
        return {"name": name, "desc": ".", "exposure": "open", "adjacent": adj, **room}
    rooms = {
        "yard": field("The Yard", None, "orchard"),
        "orchard": field("The Orchard", "yard", "meadow"),
        "meadow": field("The Meadow", "orchard", "mill_field", anchors={
            "oak": {"desc": "a great spreading oak", "dir": "n",
                    "height": "full", "footprint": "large"}}),
        "mill_field": field("The Mill Field", "meadow", "riverbank"),
        "riverbank": field("The River Bank", "mill_field", "far_hill"),
        "far_hill": field("The Far Hill", "riverbank", None),
        "mill": {"name": "The Mill", "desc": ".", "exposure": "enclosed",
                 "adjacent": [{"to": "mill_field", "barrier": "closed_door", "dir": "s"}]},
    }
    rooms["mill_field"]["adjacent"].append({"to": "mill", "barrier": "closed_door", "dir": "n"})
    sc = {"rooms": rooms, "positions": {"Ada": "yard"}, "stations": {},
          "entities": {}, "day_phase": "afternoon", "weather": {"air": "clear"}}
    sc.update(over)
    return sc


def _places(sc, who="Ada", **kw):
    with scene_read_pass(sc):
        return far_places(sc, who, **kw)


def _lines(sc, who="Ada", language="en", **kw):
    percepts = composer.landscape_percepts(_places(sc, who, **kw))
    if language == "en":
        return [composer.render_landscape_line(line)
                for _rep, line in composer.landscape_lines(percepts)]
    return [composer.render_view(percepts, mode="character", language=language).text]


# --------------------------------------------------------------------------
# The far layer says the look
# --------------------------------------------------------------------------

def test_a_far_place_with_a_look_is_said_by_it_in_place_of_its_ground():
    sc = _valley()
    sc["rooms"]["meadow"]["far_look"] = "a long hay meadow"
    line = _lines(sc)[0]
    # What stands on it is set apart from the look's own phrase, which may
    # end in one ("lined with stalls"): never "...stalls with an oak".
    assert line.startswith("To the east, you can see a long hay meadow, with a great spreading oak")
    # Only where no look is declared do today's words stand.
    sc = _valley()
    assert "open ground with a great spreading oak" in _lines(sc)[0]


def test_a_building_is_said_by_its_look_and_named_beside_it_once_known():
    sc = _valley()
    sc["rooms"]["mill"]["far_look"] = "a squat stone mill"
    assert "with a squat stone mill" in _lines(sc)[0]
    assert "a squat stone mill where The Mill is" in _lines(sc, known={"mill": ""})[0]


def test_a_known_place_is_said_by_its_name_and_its_unknown_neighbour_by_its_look():
    sc = _valley()
    sc["rooms"]["meadow"]["far_look"] = "a long hay meadow"
    sc["rooms"]["mill_field"]["far_look"] = "a strip of stubble"
    line = _lines(sc, known={"meadow": ""})[0]
    assert "The Meadow with a great spreading oak" in line and "a long hay meadow" not in line
    assert "then a strip of stubble" in line


def test_japanese_says_the_look():
    sc = _valley()
    sc["rooms"]["meadow"]["far_look"] = "刈り入れ前の長い草地"
    text = _lines(sc, language="ja")[0]
    assert "刈り入れ前の長い草地" in text and "開けた土地のある" not in text.split("、")[0]


def test_places_that_read_alike_from_afar_are_said_once():
    sc = _valley()
    for rid in ("riverbank", "far_hill"):
        sc["rooms"][rid]["far_look"] = "low water-meadows"
    line = _lines(sc)[0]
    assert line.count("low water-meadows") == 1


def _shown(sc, **kw):
    """How many places the view's lines tell this mind about."""
    lines = composer.landscape_lines(composer.landscape_percepts(_places(sc, **kw)))
    return sum(len(line["shown"]) for _rep, line in lines)


def test_a_run_of_ground_tells_the_mind_every_place_it_did_and_is_said_by_its_ends():
    """NO MIND IS TOLD ABOUT FEWER PLACES (review F10). A run of plain
    unnamed ground of one kind folds as it always did, so the three-row trim
    reaches no place the run said; with looks it is said by its nearest
    place's look and its farthest's. Replayed on chat 166, the split as
    first built -- each distinct look its own row -- told minds about
    414 -> 347 places; trading places for detail is the owner's switch
    (`landscape.LOOKS_SPLIT_RUNS`), off."""
    sc = _valley()
    base = _shown(sc)
    sc["rooms"]["riverbank"]["far_look"] = "a reedy bank along slow water"
    sc["rooms"]["far_hill"]["far_look"] = "a bare green hill"
    assert _shown(sc) == base
    line = _lines(sc)[0]
    assert "then a reedy bank along slow water, stretching on to a bare green hill" in line
    # Only one end with a look says the other by its kind.
    del sc["rooms"]["riverbank"]["far_look"]
    assert "then open ground stretching on to a bare green hill" in _lines(sc)[0]


def test_the_owners_switch_splits_a_run_by_its_looks(monkeypatch):
    import world.landscape as landscape
    sc = _valley()
    sc["rooms"]["riverbank"]["far_look"] = "a reedy bank along slow water"
    sc["rooms"]["far_hill"]["far_look"] = "a bare green hill"
    folded = _shown(sc)
    monkeypatch.setattr(landscape, "LOOKS_SPLIT_RUNS", True)
    assert _shown(sc) < folded
    assert "stretching on" not in _lines(sc)[0]


def _lane(per_row, look="a narrow house of tarred board with a steep slate roof"):
    """A yard looking east down a lane of open ground, `per_row` houses
    fronting each of its far stretches, every house with the same look."""
    seq = ["yard", "lane1", "lane2", "lane3", "lane4"]
    rooms = {}
    for i, rid in enumerate(seq):
        adj = ([{"to": seq[i - 1], "barrier": "open", "dir": "w"}] if i else []) + (
            [{"to": seq[i + 1], "barrier": "open", "dir": "e"}] if i < len(seq) - 1 else [])
        rooms[rid] = {"name": rid.title(), "desc": ".", "exposure": "open", "adjacent": adj}
    for lane in seq[2:]:
        for b in range(per_row):
            bid = f"{lane}_house{b}"
            side = "n" if b % 2 == 0 else "s"
            rooms[bid] = {"name": f"House {lane} {b}", "desc": ".", "exposure": "enclosed",
                          "far_look": look,
                          "adjacent": [{"to": lane, "barrier": "closed_door",
                                        "dir": "s" if side == "n" else "n"}]}
            rooms[lane]["adjacent"].append({"to": bid, "barrier": "closed_door", "dir": side})
    return {"rooms": rooms, "positions": {"Ada": "yard"}, "stations": {}, "entities": {},
            "day_phase": "afternoon", "weather": {"air": "clear"}}


def test_buildings_that_read_alike_are_said_once_with_their_count():
    """A line's length is bounded (review F6): houses that share a look are
    one phrase with their count, a later row of the same is said as more of
    them with its own count, and the line no longer grows with the houses --
    four alike houses a row had run it to 1,270 characters, six to 1,858."""
    look = "a narrow house of tarred board with a steep slate roof"
    lengths = []
    for per_row, more in ((2, "two more such buildings"), (4, "a few more such buildings"),
                          (6, "many more such buildings")):
        line = _lines(_lane(per_row))[0]
        assert line.count(look) == 1, line
        assert "then open ground with " + more in line, line
        lengths.append(len(line))
    assert "a few buildings alike, each " + look in _lines(_lane(4))[0]
    assert max(lengths) - min(lengths) < 30, lengths
    ja = _lines(_lane(4, look="タール塗りの板の細い家"), language="ja")[0]
    assert ja.count("タール塗りの板の細い家") == 1 and "数棟のタール塗りの板の細い家" in ja
    # At dusk each shows a lit window: still one phrase, the light in it.
    dusk = _lane(4)
    dusk["day_phase"] = "dusk"
    for rid, room in dusk["rooms"].items():
        if "house" in rid:
            room.update(light="lit", windows=["n", "s", "e", "w"])
    line = _lines(dusk)[0]
    assert line.count(look) == 1 and "a few buildings alike, each " + look + ", with a light" in line


def _mixed_lane(rows, big=None):
    """A yard looking east down a lane of open ground: `rows` maps a stretch
    of the lane to the looks of the buildings fronting it (None, no look),
    `big` a stretch to one great tree standing on it."""
    seq = ["yard", "lane1", "lane2", "lane3"]
    rooms = {}
    for i, rid in enumerate(seq):
        adj = ([{"to": seq[i - 1], "barrier": "open", "dir": "w"}] if i else []) + (
            [{"to": seq[i + 1], "barrier": "open", "dir": "e"}] if i < len(seq) - 1 else [])
        rooms[rid] = {"name": rid.title(), "desc": ".", "exposure": "open", "adjacent": adj}
    if big:
        rooms[big]["anchors"] = {"oak": {"desc": "a great spreading oak", "dir": "n",
                                         "height": "full", "footprint": "large"}}
    for lane, looks in rows.items():
        for b, look in enumerate(looks):
            bid = f"{lane}_b{b}"
            side = "n" if b % 2 == 0 else "s"
            rooms[bid] = {"name": f"B {lane} {b}", "desc": ".", "exposure": "enclosed",
                          **({"far_look": look} if look else {}),
                          "adjacent": [{"to": lane, "barrier": "closed_door",
                                        "dir": "s" if side == "n" else "n"}]}
            rooms[lane]["adjacent"].append({"to": bid, "barrier": "closed_door", "dir": side})
    return {"rooms": rooms, "positions": {"Ada": "yard"}, "stations": {}, "entities": {},
            "day_phase": "afternoon", "weather": {"air": "clear"}}


def test_more_of_a_kind_leads_its_row_and_only_where_it_is_the_one_kind_said():
    """MORE OF THEM IS SAID FIRST, AND ONLY WHERE NOTHING ELSE CAN BE WHAT
    THEY ARE MORE OF (review R2-1). Said after a new look on the same row,
    the back-reference read as more of THAT -- "a tall brick warehouse with a
    hoist and more of the same", in Japanese 「倉庫と同じような建物」 -- and the
    mind was told of warehouses that were tarred houses. Where the line has
    said other kinds of building too, the look is said again whole."""
    house, store = "a narrow house of tarred board", "a tall brick warehouse with a hoist"
    line = _lines(_mixed_lane({"lane2": [house, house], "lane3": [store, house]}))[0]
    assert "then open ground with another such building and " + store in line, line
    assert "more" not in line.split(store, 1)[1]
    # Ahead of what else stands on the row, a tree included.
    line = _lines(_mixed_lane({"lane2": [house, house], "lane3": [house]}, big="lane3"))[0]
    assert "then open ground with another such building and a great spreading oak" in line, line
    # Two kinds said before: which one a back-reference meant would be a guess.
    line = _lines(_mixed_lane({"lane2": [house, store], "lane3": [house]}))[0]
    assert line.count(house) == 2 and "such" not in line, line
    line = _lines(_mixed_lane({"lane2": [house, None], "lane3": [house]}))[0]
    assert line.count(house) == 2 and "such" not in line, line
    # Japanese: the back-reference leads the row, never after a list's と.
    house_ja, store_ja = "タール塗りの板の細い家", "滑車のある高い煉瓦の倉庫"
    ja = _lines(_mixed_lane({"lane2": [house_ja, house_ja], "lane3": [store_ja, house_ja]}),
                language="ja")[0]
    assert "もう一棟の同じような建物と" + store_ja in ja and "と同じような" not in ja, ja


def test_the_owners_cap_says_the_nearest_looks_of_a_row_and_counts_the_rest(monkeypatch):
    import world.landscape as landscape
    sc = _valley()
    sc["rooms"]["mill"]["far_look"] = "a squat stone mill"
    sc["rooms"]["byre"] = {"name": "The Byre", "desc": ".", "exposure": "enclosed",
                           "far_look": "a long low byre of turf",
                           "adjacent": [{"to": "mill_field", "barrier": "closed_door", "dir": "n"}]}
    sc["rooms"]["mill_field"]["adjacent"].append({"to": "byre", "barrier": "closed_door", "dir": "s"})
    both = _lines(sc)[0]
    assert "a squat stone mill" in both and "a long low byre of turf" in both
    monkeypatch.setattr(landscape, "DESCRIBED_BUILDINGS_PER_ROW", 1)
    one = _lines(sc)[0]
    assert one.count("a squat stone mill") + one.count("a long low byre of turf") == 1
    assert "a building" in one
    # A building past the cap is said as if it had no look -- its light
    # included, as the base words said it (review R2-8: counted as plain,
    # a lit byre lost its light).
    dusk = json.loads(json.dumps(sc))
    dusk["day_phase"] = "dusk"
    for rid in ("mill", "byre"):
        dusk["rooms"][rid].update(light="lit", windows=["n", "s", "e", "w"])
    one = _lines(dusk)[0]
    assert one.count("a light") == 2 and "a building with a light" in one, one


# --------------------------------------------------------------------------
# Named only once known; nobody the mind has not met
# --------------------------------------------------------------------------

def test_a_look_naming_a_place_is_said_only_once_the_mind_knows_that_place():
    sc = _valley()
    sc["rooms"]["far_hill"]["far_look"] = "a bare hill behind The Mill Field"
    assert "behind The Mill Field" not in " ".join(_lines(sc))
    assert "then open ground stretching on" in _lines(sc)[0]   # its ground, as before
    assert "a bare hill behind The Mill Field" in _lines(sc, known={"mill_field": ""})[0]


def test_a_place_the_mind_knows_shields_an_unknown_name_inside_its_own():
    """"The Mill" is unknown and sits inside the known "The Mill Field":
    the longest name wins at every position, as it does for people
    (`common._scrub_unknown_identities`)."""
    sc = _valley()
    sc["rooms"]["far_hill"]["far_look"] = "a bare hill past The Mill Field"
    line = _lines(sc, known={"mill_field": ""})[0]
    assert "a bare hill past The Mill Field" in line


def _looks(sc, **kw):
    return {p["room"]: p["look"] for p in _places(sc, **kw)}


def _valley_ja():
    sc = _valley()
    names = {"orchard": "果樹園", "meadow": "牧草地", "mill_field": "石段",
             "riverbank": "川岸", "far_hill": "丘", "mill": "水車小屋"}
    for rid, name in names.items():
        sc["rooms"][rid]["name"] = name
    return sc


def test_a_place_named_for_what_it_is_reads_by_its_look_in_a_script_without_spaces():
    """THE WORD FOR WHAT A PLACE IS, IS WHAT AN EYE MEETS (review F3). A
    story names a place by what it is as readily as by whose it is, and in
    a script with no spaces nothing tells the name from the word: Kirinoura
    named in Japanese refused six of its seven looks to a stranger, five for
    carrying the place's own name and one for the stair's, and the far
    layer said "open ground" where the plan had said what stood there. A
    room's name its OWN far look uses is that word, in that look."""
    sc = _valley_ja()
    sc["rooms"]["mill_field"]["far_look"] = "山腹を下るまっすぐで長い灰色の石段"
    sc["rooms"]["far_hill"]["far_look"] = "小川の向こうの低い草の丘"
    by = _looks(sc, known={})
    assert by["mill_field"] == "山腹を下るまっすぐで長い灰色の石段"
    assert by["far_hill"] == "小川の向こうの低い草の丘"
    # A name nothing describes the place by is still a name: the water mill
    # declares no look, so a look carrying "水車小屋" names it.
    sc["rooms"]["riverbank"]["far_look"] = "水車小屋の下手の低い岸"
    assert _looks(sc, known={})["riverbank"] == ""


def test_a_name_said_as_a_word_reaches_only_its_own_look_by_the_owners_switch(monkeypatch):
    """WHERE A SIGHT WORD IS SAID IS THE OWNER'S (`landscape.SIGHT_NAMES`;
    review R2-2). Said in every look that carries it, a coined name a plan
    wrote into its own place's look -- which nothing in a script without
    capitals tells from a word -- was said in every OTHER look naming that
    place too: the inn's own look naming the inn made a hill's look "behind
    潮返り亭" sayable to every stranger. "own", the default, keeps it to the
    one look, at the cost measured on Kirinoura: a look naming another
    place by the word for what that place is ("at the foot of the stone
    stair") reads by its ground. "every" says both; None neither."""
    import world.landscape as landscape
    sc = _valley_ja()
    sc["rooms"]["mill_field"]["far_look"] = "山腹を下るまっすぐで長い灰色の石段"
    sc["rooms"]["meadow"]["far_look"] = "石段のふもとに広がる刈り入れ前の長い牧草地"
    sc["rooms"]["mill"]["name"] = "潮返り亭"
    sc["rooms"]["mill"]["far_look"] = "潮返り亭、タール塗りの木造の長い酒場"
    sc["rooms"]["far_hill"]["far_look"] = "潮返り亭の裏の低い丘"
    assert landscape.SIGHT_NAMES == "own"
    by = _looks(sc, known={})
    assert by["mill_field"] and by["mill"] == "潮返り亭、タール塗りの木造の長い酒場"
    assert by["meadow"] == "" and by["far_hill"] == ""
    monkeypatch.setattr(landscape, "SIGHT_NAMES", "every")
    by = _looks(sc, known={})
    assert by["meadow"] and by["far_hill"] == "潮返り亭の裏の低い丘"
    monkeypatch.setattr(landscape, "SIGHT_NAMES", None)
    assert not any(_looks(sc, known={}).values())


def test_the_owners_switch_withholds_every_name_a_mind_lacks(monkeypatch):
    """`landscape.SIGHT_NAMES` off is the floor as first built: a room name
    the mind lacks refuses the look that carries it even where it is the
    word for what the place is -- the owner's to choose."""
    import world.landscape as landscape
    sc = _valley()
    sc["rooms"]["mill_field"]["name"] = "石段"
    sc["rooms"]["mill_field"]["far_look"] = "山腹を下るまっすぐで長い灰色の石段"
    assert _looks(sc, known={})["mill_field"]
    monkeypatch.setattr(landscape, "SIGHT_NAMES", None)
    assert _looks(sc, known={})["mill_field"] == ""


def test_a_proper_name_in_its_own_look_is_still_a_name(monkeypatch):
    """Two marks keep a name a name though its own look uses it: a CAPITAL
    WHERE THE LOOK WRITES IT, which is how running text in a script with
    case marks a proper name, and a stranger inside it, which the mind's own
    people gate changes. Both looks are withheld from a stranger and the
    places read by their ground. The mark is read from the look and not from
    the room's name (review R2-2): a one-word coined name carries no capital
    after its first letter ("Thornby"), and was said -- in its own look and,
    as the rule then stood, in every other; a room's name set in title case
    as a label is the common word where the look writes it as one."""
    import world.landscape as landscape
    sc = _valley()
    sc["rooms"]["mill"]["name"] = "the Turned Wheel"
    sc["rooms"]["mill"]["far_look"] = "the Turned Wheel, a squat stone mill"
    sc["rooms"]["meadow"]["name"] = "the hester meadow"
    sc["rooms"]["meadow"]["far_look"] = "the hester meadow, long and uncut"
    gate = lambda text: str(text).replace("hester", "a broad woman's")
    by = _looks(sc, known={}, gate=gate)
    assert by["mill"] == "" and by["meadow"] == ""
    assert "with a building" in _lines(sc, known={}, gate=gate)[0]
    sc = _valley()
    sc["rooms"]["mill"]["name"] = "Thornby"
    sc["rooms"]["mill"]["far_look"] = "the squat stone mill of Thornby"
    sc["rooms"]["far_hill"]["far_look"] = "a bare hill above Thornby"
    for reach in ("own", "every"):
        monkeypatch.setattr(landscape, "SIGHT_NAMES", reach)
        by = _looks(sc, known={})
        assert by["mill"] == "" and by["far_hill"] == "", reach
    monkeypatch.setattr(landscape, "SIGHT_NAMES", "own")
    sc = _valley()
    sc["rooms"]["meadow"]["name"] = "The Meadow"
    sc["rooms"]["meadow"]["far_look"] = "the meadow, long and uncut"
    assert _looks(sc, known={})["meadow"] == "the meadow, long and uncut"


def test_a_look_naming_a_part_of_the_map_is_said_by_the_owners_switch_alone(monkeypatch):
    """A REGION'S NAME IS A NAME (review F4), and no engine channel carries
    one to a mind, so a look that carries one -- the region's own, or a
    room's naming the town -- is said to nobody by default and the place
    reads by its ground (`landscape.REGION_NAMES_TO_LOCALS`, off). On (review
    R2-9: the round-2 floor hard-coded it), a mind that knows some place of
    the region is taken to know what that part of the map is called."""
    import world.landscape as landscape
    sc = _valley()
    for rid in sc["rooms"]:
        sc["rooms"][rid]["region"] = "saltmarsh"
    sc["rooms"]["yard"]["region"] = "the_vale"
    regions = {"saltmarsh": {"name": "Saltmarsh",
                             "far_look": "the tarred roofs of Saltmarsh crowding the shore"},
               "the_vale": {"name": "The Vale"}}
    sc["rooms"]["meadow"]["far_look"] = "a hay meadow on the edge of Saltmarsh"
    sc["rooms"]["mill"]["far_look"] = "a squat stone mill"
    assert landscape.REGION_NAMES_TO_LOCALS is False
    stranger = {p["room"]: p for p in _places(sc, regions=regions, known={})}
    assert stranger["far_hill"]["tier"] == "outline" and stranger["far_hill"]["look"] == ""
    assert stranger["meadow"]["look"] == ""
    local = _looks(sc, regions=regions, known={"orchard": ""})
    assert local["far_hill"] == "" and local["meadow"] == ""
    assert _looks(sc, regions=regions, known={})["mill"] == "a squat stone mill"
    monkeypatch.setattr(landscape, "REGION_NAMES_TO_LOCALS", True)
    assert _looks(sc, regions=regions, known={})["meadow"] == ""
    local = _looks(sc, regions=regions, known={"orchard": ""})
    assert local["far_hill"] == "the tarred roofs of Saltmarsh crowding the shore"
    assert local["meadow"] == "a hay meadow on the edge of Saltmarsh"


def test_a_registry_the_stage_could_not_read_withholds_every_look(monkeypatch):
    """FAIL CLOSED (review R2-3). A failed read of the region registry was
    read as "no regions", so no region's name was withheld and a look naming
    the town was said to a stranger. The floor cannot tell which names are
    regions' without it, so the stage withholds every far look for that view
    and the places read by their ground."""
    import types
    import world.regions as regions_mod
    from agents import perception
    from world.landscape import REGIONS_UNREAD

    def locked(*_a, **_k):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(regions_mod, "region_registry", locked)
    ctx = types.SimpleNamespace(chat=types.SimpleNamespace(id=1),
                                turn=types.SimpleNamespace(frame_id=None))
    unread = perception._far_regions(ctx)
    assert unread is REGIONS_UNREAD
    sc = _valley()
    for rid in sc["rooms"]:
        sc["rooms"][rid]["region"] = "saltmarsh"
    sc["rooms"]["meadow"]["far_look"] = "the tarred roofs of Saltmarsh crowding the shore"
    sc["rooms"]["mill"]["far_look"] = "a squat stone mill"
    assert not any(_looks(sc, regions=unread, known={}).values())
    assert not any(_looks(sc, regions=unread, known={"orchard": ""}).values())
    assert "open ground" in _lines(sc, regions=unread, known={})[0]


def test_the_people_gate_is_asked_once_a_look_and_never_about_a_room_out_of_view():
    """THE COST FOLLOWS THE LOOKS SAID, NEVER THE ROOMS (review R2-4). Asked
    about every room whose own look used its name, on every walk, the
    observer's people gate cost 80 ms a walk on a world of chat 166's size
    named in Japanese and 335 ms at 60 rooms. Whether a sight word carries a
    stranger is now read from the gate call the look pays to be said at
    all, and a stage's two walks over one view -- the standing one and a
    look's own -- share that call."""
    from world.landscape import looked_far
    seq = ["yard"] + [f"plot{i}" for i in range(40)]
    rooms = {}
    for i, rid in enumerate(seq):
        adj = ([{"to": seq[i - 1], "barrier": "open", "dir": "w"}] if i else []) + (
            [{"to": seq[i + 1], "barrier": "open", "dir": "e"}] if i < len(seq) - 1 else [])
        rooms[rid] = {"name": f"畑{i}", "desc": ".", "exposure": "open", "adjacent": adj,
                      "far_look": f"低い石垣に囲まれた畑{i}"}
    sc = {"rooms": rooms, "positions": {"Ada": "yard"}, "stations": {}, "entities": {},
          "day_phase": "afternoon", "weather": {"air": "clear"}}
    gated, named = [], []

    def gate(text):
        gated.append(text)
        return text

    def names(text, labels=None):
        named.append(text)
        return text
    gate.names = names
    with scene_read_pass(sc):
        places = far_places(sc, "Ada", known={}, gate=gate)
        said = [p["look"] for p in places if p.get("look")]
        looked_far(sc, "Ada", ["east"], known={}, gate=gate)
    assert said and sorted(gated) == sorted(said) and not named, (len(gated), len(said))
    assert len(said) < len(rooms) - 1


def test_a_look_naming_a_stranger_is_said_as_the_minds_own_gate_says_it():
    sc = _valley()
    sc["rooms"]["meadow"]["far_look"] = "Hester Gale's hay meadow"
    gate = lambda text: str(text).replace("Hester Gale's", "a broad woman's")
    line = _lines(sc, gate=gate)[0]
    assert "a broad woman's hay meadow" in line and "Hester" not in line


def test_a_place_named_for_a_stranger_is_judged_as_written_before_the_gate():
    """The people gate rewrites a name's own parts ("Gale" of "Hester
    Gale"), so a place called after somebody must be refused on the look as
    the planner wrote it -- read after the gate it would name no place."""
    sc = _valley()
    sc["rooms"]["mill"]["name"] = "the Gale mill"
    sc["rooms"]["far_hill"]["far_look"] = "a bare hill behind the Gale mill"
    gate = lambda text: str(text).replace("Gale", "a broad woman's")
    by = {p["room"]: p for p in _places(sc, gate=gate)}
    assert by["far_hill"]["look"] == ""
    by = {p["room"]: p for p in _places(sc, gate=gate, known={"mill": ""})}
    assert by["far_hill"]["look"] == "a bare hill behind the a broad woman's mill"


# --------------------------------------------------------------------------
# Never a placeholder, and never the hour
# --------------------------------------------------------------------------

def test_a_look_is_said_by_day_and_the_dark_shows_only_the_lights():
    sc = _valley()
    sc["rooms"]["mill"]["far_look"] = "a squat stone mill"
    sc["rooms"]["mill"]["light"] = "lit"
    sc["rooms"]["mill"]["windows"] = ["s"]
    assert "a squat stone mill" in _lines(sc)[0]
    night = _valley(day_phase="night", weather={"air": "clear", "moon": "none"})
    night["rooms"]["mill"].update(far_look="a squat stone mill", light="lit", windows=["s"])
    text = " ".join(_lines(night))
    assert "a light" in text and "squat stone mill" not in text
    # A mind that knows the mill by name is told where the light is, never
    # what the dark mass is built of (review F5) -- in its standing view,
    # and when its own look is aimed at the mill.
    text = " ".join(_lines(night, known={"mill": ""}))
    assert "a light at a building where The Mill is" in text and "squat" not in text
    from world.landscape import looked_far
    with scene_read_pass(night):
        found = looked_far(night, "Ada", ["The Mill"], known={"mill": ""})
    seen = [p.data.get("desc", "") for p in composer.landscape_look_percepts(found)]
    assert seen and "light" in seen[0] and "squat" not in seen[0], seen


# --------------------------------------------------------------------------
# A region's look, at the outline only
# --------------------------------------------------------------------------

def test_a_regions_far_look_stands_for_its_ground_only_at_the_outline():
    sc = _valley()
    for rid in sc["rooms"]:
        sc["rooms"][rid]["region"] = "vale"
    regions = {"vale": {"name": "The Vale", "far_look": "farmland to the edge of sight"}}
    by = {p["room"]: p for p in _places(sc, regions=regions, known={"yard": ""})}
    assert by["far_hill"]["tier"] == "outline"
    assert by["far_hill"]["look"] == "farmland to the edge of sight"
    assert by["meadow"]["tier"] == "mid" and by["meadow"]["look"] == ""
    assert by["mill"]["look"] == ""                             # buildings: their own only
    sc["rooms"]["far_hill"]["far_look"] = "a bare green hill"   # its own wins
    by = {p["room"]: p for p in _places(sc, regions=regions, known={"yard": ""})}
    assert by["far_hill"]["look"] == "a bare green hill"


def _quiet_outcome(db, scene, *, region=None):
    """`perception_outcome` for one quiet beat of the player, Pip, against
    the database: the stage reads the frame's region registry itself."""
    from agents import perception
    from story.character_schema import default_persona_data
    from world.regions import set_region_far_look
    persona = default_persona_data("Pip")
    persona_id = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                       ("Pip", json.dumps(persona), "{}"))
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
                ("Far", "", time.time(), persona_id))
    db.wset(cid, "scene", dict(scene, location="x", attire={}, overlays={}))
    db.wset(cid, "known", {})
    if region:
        set_region_far_look(cid, None, *region)
    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                 (cid, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Far", persona_id=persona_id, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn, chat_id=cid, idx=1, player_input="", created=time.time()),
        cast=[], input="")
    ctx["_player_room"] = "yard"
    ctx.director_interpret = {
        "action": {"attempt": "waits", "visibility": "overt", "conceal_from": [],
                   "targets": [], "commitment": "asserted"},
        "sequence": [{"type": "action", "attempt": "waits", "observable": "waits",
                      "visibility": "overt", "conceal_from": [], "targets": [],
                      "commitment": "asserted", "verb": "wait", "stage": "immediate",
                      "event_id": "turn:1:player:0:action"}],
        "speech": None, "speech_volume": "normal", "flow": {"reactors": []}}
    ctx.director_resolve = {"resolved_event": "Nothing much happens.", "state_diff": {},
                            "dialogue_log": [], "dialogue_order": []}
    return json.dumps(perception.perception_outcome(ctx, nonce="n"), ensure_ascii=False)


def test_a_stage_reads_the_regions_far_look_and_says_it_at_the_outline(temp_db):
    """THE HAND-OFF, end to end (review F9): the outcome stage reads the
    frame's region registry from the database (`perception._far_regions`)
    and the far layer says a region's far look for a place of it with none
    of its own at the outline -- the far hill, five rooms east, at the far
    end of the run of open ground it closes."""
    sc = _valley(positions={"Pip": "yard"})
    for rid in sc["rooms"]:
        sc["rooms"][rid]["region"] = "vale"
    told = _quiet_outcome(temp_db, sc, region=("vale", "farmland to the edge of sight"))
    # The river bank and the hill are one run of open ground, said to its
    # far end by the region's look (`landscape.LOOKS_SPLIT_RUNS`, off).
    assert "then open ground stretching on to the farmland to the edge of sight" in told
    assert "farmland to the edge of sight" not in _quiet_outcome(temp_db, sc)


def test_every_stage_hands_the_far_layer_the_region_registry():
    """Each of the three stages that compose a standing view hands the far
    layer the registry it read (review F9): one stage dropping the argument
    would read every region's look as absent and every region's name as
    one no mind lacks."""
    import inspect
    from agents import perception
    for builder in (perception._composer_establish_views, perception._composer_act_views,
                    perception._composer_outcome_views):
        source = inspect.getsource(builder)
        assert "regions = _far_regions(ctx)" in source, builder.__name__
        assert "regions=regions)" in source, builder.__name__
    source = inspect.getsource(perception._composer_standing_percepts)
    assert source.count("regions=regions)") == 2


# --------------------------------------------------------------------------
# A changed look is news; a place with none keeps its key
# --------------------------------------------------------------------------

def test_a_changed_look_is_news_and_a_place_without_one_keeps_the_key_it_had():
    def keys(sc):
        return {p.data["landscape"]["id"]: p.dedupe_key
                for p in composer.landscape_percepts(_places(sc, known={}))}
    plain = _valley()
    looked = _valley()
    looked["rooms"]["meadow"]["far_look"] = "a long hay meadow"
    burned = _valley()
    burned["rooms"]["meadow"]["far_look"] = "a blackened field of stubble"
    meadow = composer._short_hash("landscape-place", "meadow")
    a, b, c = keys(plain), keys(looked), keys(burned)
    assert a[meadow] != b[meadow] != c[meadow]
    assert {k: v for k, v in a.items() if k != meadow} == \
        {k: v for k, v in b.items() if k != meadow}
    # The key a place with no look carries is the one it carried before
    # looks existed, so no standing far line re-announces on the upgrade.
    place = next(p for p in _places(plain, known={}) if p["room"] == "far_hill")
    data = next(p.data["landscape"] for p in composer.landscape_percepts([place]))
    old = (data["grain"], data["ground"], data["breadth"], data["height"],
           data["lights"], data["high"], data["dark"], len(data["big"]), data["over"])
    assert a[data["id"]] == composer.standing_key("landscape", ("far_hill",), old)


# --------------------------------------------------------------------------
# One spelling for every writer
# --------------------------------------------------------------------------

def test_a_far_look_is_one_phrase_of_at_most_the_named_length():
    from world.landscape import FAR_LOOK_CHARS, normalize_far_look
    assert normalize_far_look("  a long   hay meadow ") == "a long hay meadow"
    assert normalize_far_look(None) == "" and normalize_far_look(["x"]) == ""
    long = "a long hay meadow, " + "silvered " * 40
    out = normalize_far_look(long)
    assert len(out) <= FAR_LOOK_CHARS and out == "a long hay meadow"
    words = "word " * 60
    assert len(normalize_far_look(words)) <= FAR_LOOK_CHARS
    assert not normalize_far_look(words).endswith(" ")


# --------------------------------------------------------------------------
# The plan writes it, and it travels
# --------------------------------------------------------------------------

def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Far", "", time.time()))


def test_plan_rooms_keeps_a_far_look_shows_it_back_and_says_when_it_was_cut():
    from story.plot_packages import _preview_plan_rooms, _shape_plan_rooms
    from world.landscape import FAR_LOOK_CHARS
    raw = {"structure": {"key": "vale", "name": "The Vale",
                         "far_look": " farmland  to the edge of sight "},
           "rooms": {"meadow": {"name": "The Meadow", "exposure": "open",
                                "far_look": "a long hay meadow"},
                     "barn": {"name": "Barn", "far_look": ""},
                     "fen": {"name": "Fen", "far_look": "a flat of reed, " + "grey " * 60}}}
    op = _shape_plan_rooms(raw)
    assert op["rooms"]["meadow"]["far_look"] == "a long hay meadow"
    assert "far_look" not in op["rooms"]["barn"]
    assert op["rooms"]["fen"]["far_look"] == "a flat of reed"
    assert op["structure"]["far_look"] == "farmland to the edge of sight"
    # The preview reads the STORED op, as `preview_package` does -- the
    # shaped one -- and still says what the engine cut.
    world = {"rooms": {}, "planned": {}, "described_rooms": set(), "containment": {}}
    preview = _preview_plan_rooms(1, None, op, world)
    change = preview["changes"][0]
    assert change["geometry"]["meadow"]["far_look"] == "a long hay meadow"
    assert change["region_far_look"] == "farmland to the edge of sight"
    assert any("'fen'" in w and str(FAR_LOOK_CHARS) in w and "'a flat of reed'" in w
               for w in preview["warnings"]), preview["warnings"]
    assert not any("meadow" in w for w in preview["warnings"])


def test_the_preview_of_a_stored_plan_says_when_a_measurement_was_clamped():
    """The same class one field over: the preview reads the STORED op, which
    holds only the clamped extent, so the clamp warning written for the
    solitude run's 28-for-24 terraces (PS19) could never fire from a
    drafted package."""
    from story.plot_packages import _preview_plan_rooms, _shape_plan_rooms
    op = _shape_plan_rooms({"structure": {"key": "k", "name": "K"},
                            "rooms": {"yard": {"name": "Yard", "extent": {"w": 300, "d": 10}}}})
    world = {"rooms": {}, "planned": {}, "described_rooms": set(), "containment": {}}
    warnings = _preview_plan_rooms(1, None, op, world)["warnings"]
    assert any("'yard' was drawn" in w and "not 300 by 10" in w for w in warnings), warnings


def test_a_planned_far_look_travels_to_the_stub_and_survives_its_development(temp_db):
    from world.spatial import merge_scene_with_diff
    from world.structure import plant_structure, planned_room_brief, skeleton_rooms
    cid = _chat(temp_db)
    plant_structure(cid, {"key": "vale", "max_planned": 8},
                    {"meadow": {"name": "The Meadow", "purpose": "hay",
                                "exposure": "open", "far_look": "a long hay meadow"}})
    stub = skeleton_rooms(cid, "vale")["rooms"]["meadow"]
    assert stub["far_look"] == "a long hay meadow"
    # The hand that furnishes it is told what far eyes have been seeing.
    brief = planned_room_brief(cid, {"rooms": {"meadow": stub}}, ["meadow"])
    assert brief["meadow"]["far_look"] == "a long hay meadow"
    # A beat that describes it keeps the look: silence keeps.
    scene = merge_scene_with_diff({"rooms": {"meadow": dict(stub)}},
                                  {"rooms": {"meadow": {"desc": "Hay, cut and stooked."}}})
    assert scene["rooms"]["meadow"]["far_look"] == "a long hay meadow"


def test_a_structures_far_look_becomes_its_regions_and_leaves_the_regions_picture_look(temp_db):
    from story.plot_packages import _apply_plan_rooms, _shape_plan_rooms
    from world.regions import region_registry
    cid = _chat(temp_db)
    op = _shape_plan_rooms({"structure": {"key": "vale", "name": "The Vale",
                                          "far_look": "farmland to the edge of sight"},
                            "rooms": {"meadow": {"name": "The Meadow", "exposure": "open"}}})
    out = _apply_plan_rooms(cid, None, op, 0)
    assert out["region_far_look"] == "farmland to the edge of sight"
    assert region_registry(cid, None)["vale"]["far_look"] == "farmland to the edge of sight"
    # A different fact from the picture's register: the region's `look` is
    # untouched.
    assert "look" not in region_registry(cid, None)["vale"]


def test_a_host_edit_of_a_regions_far_look_outlives_a_replan_that_repeats_the_plan(temp_db):
    """THE PLAN SEEDS A REGION'S LOOK; IT DOES NOT HOLD IT (review R2-5) --
    the stub's rule one level up. A re-plan that added a barn and repeated
    the structure's look put the plan's farmland back over the host's
    burned waste. The plan's word lands when it says something new."""
    from story.plot_packages import _apply_plan_rooms, _shape_plan_rooms
    from world.regions import region_registry, set_region_far_look
    cid = _chat(temp_db)

    def publish(look, room, turn):
        op = _shape_plan_rooms({"structure": {"key": "vale", "name": "The Vale",
                                              **({"far_look": look} if look else {})},
                                "rooms": {room: {"name": room.title(), "exposure": "open"}}})
        return _apply_plan_rooms(cid, None, op, turn)

    def look():
        return region_registry(cid, None)["vale"].get("far_look")
    publish("farmland to the edge of sight", "meadow", 0)
    set_region_far_look(cid, None, "vale", "a burned waste of black stubble")
    out = publish("farmland to the edge of sight", "barn", 1)
    assert look() == "a burned waste of black stubble"
    assert out["region_far_look"] == "a burned waste of black stubble"
    publish("", "byre", 2)                  # a publish that names no look
    assert look() == "a burned waste of black stubble"
    set_region_far_look(cid, None, "vale", "")      # the host clears it
    publish("farmland to the edge of sight", "orchard", 3)
    assert look() is None
    publish("orchards to the edge of sight", "loft", 4)   # something new
    assert look() == "orchards to the edge of sight"
    # A region the host described before any plan said a word keeps it.
    set_region_far_look(cid, None, "fen", "a grey flat of reed")
    op = _shape_plan_rooms({"structure": {"key": "fen", "name": "The Fen",
                                          "far_look": "a wide wet flat"},
                            "rooms": {"staithe": {"name": "Staithe", "exposure": "open"}}})
    _apply_plan_rooms(cid, None, op, 5)
    assert region_registry(cid, None)["fen"]["far_look"] == "a grey flat of reed"


def test_a_structure_renamed_after_its_far_look_is_laid_renames_its_region(temp_db):
    """(review B1) A far look laid on a structure stored the region's entry
    with the structure's name of that moment, and a stored entry won over
    the structure, so a re-plan that renamed it renamed nothing here: the
    name floor withheld the old name and let the new one through to a
    stranger. The structure's name is the region's; a host's rename stands."""
    from story.plot_packages import _apply_plan_rooms, _shape_plan_rooms
    from world.regions import region_registry, set_region_name
    cid = _chat(temp_db)
    for name, far, room in (("The Vale", "farmland to the edge of sight", "meadow"),
                            ("Thornvale", None, "barn")):
        op = _shape_plan_rooms({"structure": {"key": "vale", "name": name,
                                              **({"far_look": far} if far else {})},
                                "rooms": {room: {"name": room.title(), "exposure": "open"}}})
        _apply_plan_rooms(cid, None, op, 0)
    registry = region_registry(cid, None)
    assert registry["vale"]["name"] == "Thornvale"
    assert registry["vale"]["far_look"] == "farmland to the edge of sight"

    def field(name, prev, nxt, **room):
        adj = ([{"to": prev, "barrier": "open", "dir": "w"}] if prev else []) + (
            [{"to": nxt, "barrier": "open", "dir": "e"}] if nxt else [])
        return {"name": name, "desc": ".", "exposure": "open", "adjacent": adj,
                "region": "vale", **room}
    sc = {"rooms": {"yard": field("The Yard", None, "a"), "a": field("The Lane", "yard", "b"),
                    "b": field("The Barn Field", "a", None,
                               far_look="hedged fields below Thornvale")},
          "positions": {"Ada": "yard"}, "stations": {}, "entities": {},
          "day_phase": "afternoon", "weather": {"air": "clear"}}
    with scene_read_pass(sc):
        told = {p["room"]: p.get("look")
                for p in far_places(sc, "Ada", known={}, regions=registry)}
    assert "Thornvale" not in str(told.get("b") or ""), told
    # A host who renames the region keeps their name over the structure's.
    set_region_name(cid, None, "vale", "The Long Vale")
    op = _shape_plan_rooms({"structure": {"key": "vale", "name": "Thornvale"},
                            "rooms": {"byre": {"name": "Byre", "exposure": "open"}}})
    _apply_plan_rooms(cid, None, op, 1)
    assert region_registry(cid, None)["vale"]["name"] == "The Long Vale"


def test_a_far_look_travels_through_the_archive_and_the_checkpoint(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    from world.regions import region_registry, set_region_far_look
    from world.structure import plant_structure, skeleton_rooms
    cid = _chat(temp_db)
    plant_structure(cid, {"key": "vale", "max_planned": 8},
                    {"meadow": {"name": "The Meadow", "purpose": "hay",
                                "exposure": "open", "far_look": "a long hay meadow"}})
    from world.regions import lay_planned_region_far_look
    from world.structure import LAID_LOOKS_KEY
    lay_planned_region_far_look(cid, None, "vale", "farmland to the edge of sight")
    temp_db.wset(cid, "scene", {"rooms": {"meadow": skeleton_rooms(cid, "vale")["rooms"]["meadow"]},
                                LAID_LOOKS_KEY: {"meadow": "a long hay meadow"},
                                "positions": {}, "entities": {}})
    ensure_checkpoint(cid, 0)
    temp_db.wset(cid, "scene", {"rooms": {}, "positions": {}, "entities": {}})
    lay_planned_region_far_look(cid, None, "vale", "orchards to the edge of sight")
    set_region_far_look(cid, None, "vale", "")
    restore_checkpoint(cid, 0)
    restored = json.loads(json.dumps(temp_db.wget(cid, "scene")))
    assert restored["rooms"]["meadow"]["far_look"] == "a long hay meadow"
    assert restored[LAID_LOOKS_KEY] == {"meadow": "a long hay meadow"}
    assert region_registry(cid, None)["vale"]["far_look"] == "farmland to the edge of sight"
    # And what the plan last laid on the region, which keeps a host's edit
    # standing past a re-plan.
    assert region_registry(cid, None)["vale"]["far_look_laid"] == "farmland to the edge of sight"
    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(cid)})
    icid = imported["id"] if isinstance(imported, dict) else imported
    scene = temp_db.wget(icid, "scene")
    scene = json.loads(scene) if isinstance(scene, str) else scene
    assert scene["rooms"]["meadow"]["far_look"] == "a long hay meadow"
    assert scene[LAID_LOOKS_KEY] == {"meadow": "a long hay meadow"}
    assert skeleton_rooms(icid, "vale")["rooms"]["meadow"]["far_look"] == "a long hay meadow"
    assert region_registry(icid, None)["vale"]["far_look"] == "farmland to the edge of sight"
    assert region_registry(icid, None)["vale"]["far_look_laid"] == "farmland to the edge of sight"


def test_a_sketched_room_carries_how_much_sky_it_stands_under_and_its_far_look():
    from story.room_sketch import _seen_from_afar
    assert _seen_from_afar({"exposure": "Open", "far_look": "a tarred net loft on piles"}) == \
        {"exposure": "open", "far_look": "a tarred net loft on piles"}
    # JSON's null written out as a word is an empty field; a word the engine
    # cannot read is no value.
    assert _seen_from_afar({"exposure": "breezy", "far_look": "null"}) == {}


def test_a_beats_room_write_carries_a_far_look_and_silence_keeps_it():
    from llm.schemas import RoomDef, _dump
    from tests.helpers import model_from
    from world.spatial import merge_scene_with_diff
    room = _dump(model_from(RoomDef, {"name": "The Meadow",
                                      "far_look": "a blackened field of stubble"}))
    assert room["far_look"] == "a blackened field of stubble"
    assert "far_look" not in _dump(model_from(RoomDef, {"name": "The Meadow"}))
    scene = merge_scene_with_diff(
        {"rooms": {"meadow": {"name": "The Meadow", "far_look": "a long hay meadow"}}},
        {"rooms": {"meadow": {"desc": "Ash to the hedges."}}})
    assert scene["rooms"]["meadow"]["far_look"] == "a long hay meadow"


def test_a_beats_far_look_is_stored_and_briefed_as_the_far_layer_reads_it(temp_db):
    """ONE SPELLING FOR EVERY WRITER AND READER (review R2-7). A beat's room
    write stored its far look as written: 412 characters, double spaces
    kept, of which the far layer said the first clause -- while the brief
    handed the room author and the encoder all 412 and told them the place
    they build is the one the look describes."""
    from llm.schemas import validated_state_diff_channels
    from world.landscape import far_look_of
    from world.spatial import merge_scene_with_diff
    from world.structure import planned_room_brief, skeleton_rooms
    raw = "a  long   hay meadow, " + "silvered and " * 30
    clean, _dropped = validated_state_diff_channels(
        {"rooms": {"meadow": {"name": "The Meadow", "far_look": raw}}})
    scene = merge_scene_with_diff(
        {"rooms": {"meadow": {"name": "The Meadow", "desc": ".", "far_look": "a flat"}}}, clean)
    assert scene["rooms"]["meadow"]["far_look"] == far_look_of(scene, "meadow") \
        == "a long hay meadow"
    # A look stored raw by a writer that kept no spelling is briefed as the
    # far layer reads it.
    cid = _chat(temp_db)
    _plan_meadow(cid, "a long hay meadow")
    stub = dict(skeleton_rooms(cid, "vale")["rooms"]["meadow"], far_look=raw)
    brief = planned_room_brief(cid, {"rooms": {"meadow": stub}}, ["meadow"])
    assert brief["meadow"]["far_look"] == "a long hay meadow"
    # And a plan planted by a writer that kept no spelling seeds the one.
    from world.structure import plant_structure
    plant_structure(cid, {"key": "fen", "max_planned": 8},
                    {"staithe": {"name": "Staithe", "purpose": "boats", "exposure": "open",
                                 "far_look": raw}})
    assert skeleton_rooms(cid, "fen")["rooms"]["staithe"]["far_look"] == "a long hay meadow"


def test_a_room_write_that_echoes_the_look_empty_keeps_it():
    """An empty string is the encoder echoing the key, never a clear --
    `exposure` and `light` beside it are kept the same way (review F7). The
    validator keeps the empty string, so the merge is what must read it as
    silence."""
    from llm.schemas import validated_state_diff_channels
    from world.spatial import merge_scene_with_diff
    clean, _dropped = validated_state_diff_channels({"rooms": {"meadow": {
        "name": "The Meadow", "desc": "Ash to the hedges.", "far_look": "", "exposure": ""}}})
    scene = merge_scene_with_diff(
        {"rooms": {"meadow": {"name": "The Meadow", "desc": ".", "exposure": "open",
                              "far_look": "a long hay meadow"}}}, clean)
    assert scene["rooms"]["meadow"]["far_look"] == "a long hay meadow"
    assert scene["rooms"]["meadow"]["exposure"] == "open"


def _commit_beat(db, cid, idx, diff):
    """One beat through the commit's own preparation (`prepare_scene_commit`:
    the diff merged, then the planned fringe), stored as `commit_scene`
    would store it."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist import commit
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Far", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=idx, chat_id=cid, idx=idx, player_input="", created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": json.loads(json.dumps(diff))}
    scene = commit.prepare_scene_commit(ctx)["scene"]
    db.wset(cid, "scene", scene)
    return scene


def _plan_meadow(cid, look):
    from world.structure import plant_structure
    plant_structure(cid, {"key": "vale", "max_planned": 8},
                    {"meadow": {"name": "The Meadow", "purpose": "hay", "exposure": "open",
                                **({"far_look": look} if look else {}),
                                "adjacent": [{"to": "yard", "barrier": "open"}]}})


def test_a_beat_or_a_host_changes_a_planned_stubs_far_look_and_the_commit_keeps_it(temp_db):
    """THE PLAN SEEDS A FAR LOOK; IT DOES NOT HOLD IT (review F1). While a
    stub is prose-free the commit gives it back the plan's name, purpose and
    measurements every beat, and a far look ridden in with them came back
    too: the meadow the encoder burned read as hay again the same commit,
    and a host's edit or clear lasted one beat -- on exactly the unvisited
    places far looks are for. The plan's word lands when the plan says
    something new; until then the stub's look stands, whoever wrote it."""
    cid = _chat(temp_db)
    _plan_meadow(cid, "a long hay meadow")
    temp_db.wset(cid, "scene", {
        "rooms": {"yard": {"name": "The Yard", "desc": "A yard.", "exposure": "open",
                           "adjacent": [{"to": "meadow", "barrier": "open"}]}},
        "positions": {"Ada": "yard"}, "entities": {}})

    def look(sc):
        return sc["rooms"]["meadow"].get("far_look")
    sc = _commit_beat(temp_db, cid, 1, {})
    assert sc["rooms"]["meadow"].get("planned") and not sc["rooms"]["meadow"].get("desc")
    assert look(sc) == "a long hay meadow"
    # A beat burns it, and neither that commit nor the next puts the hay back.
    sc = _commit_beat(temp_db, cid, 2, {"rooms": {"meadow": {
        "name": "The Meadow", "far_look": "a blackened field of stubble"}}})
    assert look(sc) == "a blackened field of stubble"
    sc = _commit_beat(temp_db, cid, 3, {})
    assert look(sc) == "a blackened field of stubble"
    # A host clears it from the World Browser (the room PATCH pops it): it
    # stays cleared, and the place reads by its ground.
    sc["rooms"]["meadow"].pop("far_look")
    temp_db.wset(cid, "scene", sc)
    sc = _commit_beat(temp_db, cid, 4, {})
    assert "far_look" not in sc["rooms"]["meadow"]
    # The plan says something new -- a re-plan, a claim -- and its word lands.
    _plan_meadow(cid, "a market ground of trestles")
    sc = _commit_beat(temp_db, cid, 5, {})
    assert look(sc) == "a market ground of trestles"
    # A re-plan that says nothing takes nothing away, and is remembered as
    # silence, so the plan's next word is new.
    _plan_meadow(cid, "")
    sc = _commit_beat(temp_db, cid, 6, {})
    assert look(sc) == "a market ground of trestles"
    _plan_meadow(cid, "a fairground of striped awnings")
    sc = _commit_beat(temp_db, cid, 7, {})
    assert look(sc) == "a fairground of striped awnings"
    # Described, the room is its own: the record lets go of it.
    sc = _commit_beat(temp_db, cid, 8, {"rooms": {"meadow": {
        "name": "The Meadow", "desc": "Trestles and awnings."}}})
    assert look(sc) == "a fairground of striped awnings"
    from world.structure import LAID_LOOKS_KEY
    assert LAID_LOOKS_KEY not in sc


def test_an_entity_fold_leaves_the_record_of_laid_looks_keyed_by_room(temp_db):
    """THE RECORD IS KEYED BY ROOM, and a folded entity is never a room
    (review R2-6). An entity fold walks every scene ledger but the room-keyed
    ones, and the record of what each stub last took from its plan was not
    among them: a mint folded as `well` -> `village_well` re-keyed the
    record, the stub `well` read as never laid, and the first-time branch put
    the plan's look back over a host's clear."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist.commit import _fold_duplicate_mints
    from world.structure import LAID_LOOKS_KEY
    cid = _chat(temp_db)
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Far", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=cid, idx=1, player_input="", created=time.time()),
        cast=[], input="")
    well = {"name": "the well", "planned": True, "exposure": "open"}
    keeper = {"name": "the village well", "aliases": ["well"]}
    prev = {"rooms": {"well": dict(well)}, "entities": {"village_well": dict(keeper)},
            LAID_LOOKS_KEY: {"well": "a stone well-head"}}
    diff = {"entities": {"well": {"name": "well"}}}
    sc = {"rooms": {"well": dict(well)}, "positions": {},
          "entities": {"village_well": dict(keeper), "well": {"name": "well"}},
          LAID_LOOKS_KEY: {"well": "a stone well-head"}}
    assert _fold_duplicate_mints(ctx, cid, sc, prev, diff) == [("well", "village_well")]
    assert sc[LAID_LOOKS_KEY] == {"well": "a stone well-head"}
    assert "well" in sc["rooms"] and "well" not in sc["entities"]


def test_the_hand_that_furnishes_a_stub_is_told_the_look_far_eyes_have_seen(temp_db):
    """The furnishing brief carries the stub's own look -- what the far
    layer has been saying -- and the plan's only for a room the scene does
    not hold yet (review F8): read plan-first, it handed the designer the
    hay meadow the beat had burned, and a look the host cleared."""
    from world.structure import planned_room_brief, skeleton_rooms
    cid = _chat(temp_db)
    _plan_meadow(cid, "a long hay meadow")
    stub = skeleton_rooms(cid, "vale")["rooms"]["meadow"]
    burned = {"rooms": {"meadow": dict(stub, far_look="a blackened field of stubble")}}
    assert planned_room_brief(cid, burned, ["meadow"])["meadow"]["far_look"] == \
        "a blackened field of stubble"
    cleared = {"rooms": {"meadow": {k: v for k, v in stub.items() if k != "far_look"}}}
    assert "far_look" not in planned_room_brief(cid, cleared, ["meadow"])["meadow"]
    # The opening's brief is the whole plan over an empty scene.
    assert planned_room_brief(cid, {}, ["meadow"])["meadow"]["far_look"] == "a long hay meadow"


def test_a_stub_takes_the_plans_look_only_where_it_has_none_the_first_time(temp_db):
    """The first pass over a stub this frame has never laid a look on
    cannot tell the plan's word from a beat's, so it fills only an empty
    field: a look the opening wrote onto the place stands. A scene whose
    plans carry no far look is left exactly as it was."""
    from world.structure import materialize_planned_fringe, skeleton_rooms
    cid = _chat(temp_db)
    _plan_meadow(cid, "a long hay meadow")
    stub = skeleton_rooms(cid, "vale")["rooms"]["meadow"]
    yard = {"name": "The Yard", "desc": "A yard.", "exposure": "open",
            "adjacent": [{"to": "meadow", "barrier": "open"}]}
    scene = {"rooms": {"yard": dict(yard), "meadow": dict(stub, far_look="a flooded meadow")},
             "positions": {"Ada": "yard"}, "entities": {}}
    scene, _ = materialize_planned_fringe(cid, scene)
    assert scene["rooms"]["meadow"]["far_look"] == "a flooded meadow"
    from world.structure import LAID_LOOKS_KEY
    assert scene[LAID_LOOKS_KEY] == {"meadow": "a long hay meadow"}
    _plan_meadow(cid, "")
    plain = {"rooms": {"yard": dict(yard)}, "positions": {"Ada": "yard"}, "entities": {}}
    plain, _ = materialize_planned_fringe(cid, plain)
    assert "far_look" not in plain["rooms"]["meadow"] and LAID_LOOKS_KEY not in plain


# --------------------------------------------------------------------------
# The cards ask for it, as a class, in both packs
# --------------------------------------------------------------------------

def test_the_rooms_cards_ask_for_a_far_look_in_both_packs():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "language_packs"
    for lang in ("en", "ja"):
        sketch = (root / lang / "cards/system_prompts/prompts/room_sketch.txt").read_text("utf-8")
        assert '"far_look": "<how it reads from far off, or null>"' in sketch, lang
        assert '"exposure": "<open, sheltered or enclosed>"' in sketch, lang
        planner = (root / lang / "cards/system_prompts/prompts/story_planner.txt").read_text("utf-8")
        assert "`far_look`" in planner, lang
        encoder = (root / lang / "cards/system_prompts/encoder/rooms.txt").read_text("utf-8")
        assert "`far_look`" in encoder and "far_look?," in encoder, lang
    from story.plot_packages import OPERATION_FIELDS
    assert "far_look?" in OPERATION_FIELDS["plan_rooms"]["rooms"]
    assert "far_look?" in OPERATION_FIELDS["plan_rooms"]["structure"]


def test_every_card_that_reads_a_planned_rooms_look_says_what_it_is():
    """The planned-room brief carries a far look to three model readers --
    the room author's `develop`, the encoder's `planned_rooms` and the
    opening's -- and each card now says what it is: how the place has read
    from far off, which the place furnished there is (review F8). And no
    card says a look is told only to minds that do not know the place: a
    known building is said as its look "where" its name is (review F11)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "language_packs"
    cards = ("prose_contract/room_author.txt", "encoder/rooms.txt",
             "prompts/director_establish.txt")
    for lang in ("en", "ja"):
        for card in cards:
            text = (root / lang / "cards/system_prompts" / card).read_text("utf-8")
            assert "`far_look`" in text, (lang, card)
        sketch = (root / lang / "cards/system_prompts/prompts/room_sketch.txt").read_text("utf-8")
        summary = sketch[sketch.index("\n\n", sketch.index('"event"')):]
        summary = summary[:summary.index("\n\n", 2)]
        assert ("how it reads from far off" if lang == "en" else "遠くからどう見えるか") in summary
        for card in ("prompts/room_sketch.txt", "encoder/rooms.txt"):
            text = (root / lang / "cards/system_prompts" / card).read_text("utf-8")
            assert "do not know the place" not in text and "知らない心" not in text \
                and "知らない人々" not in text, (lang, card)
    from story.plot_packages import OPERATION_FIELDS
    assert "do not know the place" not in OPERATION_FIELDS["plan_rooms"]["rooms"]
    # And the planner is told the one name the floor lets through (review
    # R2-2): its place's own, which the look itself may make a word.
    assert "this place's own name, where the look uses it, is read as the word for " \
        "what the place is and may be said to anyone" in OPERATION_FIELDS["plan_rooms"]["rooms"]


# --------------------------------------------------------------------------
# The host writes it too
# --------------------------------------------------------------------------

from tests.test_world_routes import client, story  # noqa: E402,F401  (fixtures)


def test_the_world_browser_writes_a_rooms_and_a_regions_far_look(client, story, temp_db):
    cid = story["chat_id"]
    r = client.patch(f"/api/chats/{cid}/rooms/garden",
                     json={"far_look": "  a walled   garden of clipped box "})
    assert r.status_code == 200, r.text
    assert r.json()["record"]["far_look"] == "a walled garden of clipped box"
    assert temp_db.wget(cid, "scene")["rooms"]["garden"]["far_look"] == \
        "a walled garden of clipped box"
    assert client.patch(f"/api/chats/{cid}/rooms/garden",
                        json={"far_look": ["x"]}).status_code == 400
    r = client.patch(f"/api/chats/{cid}/rooms/garden", json={"far_look": ""})
    assert "far_look" not in temp_db.wget(cid, "scene")["rooms"]["garden"]
    # The region's, a different fact from its picture `look`, on the same route.
    client.patch(f"/api/chats/{cid}/rooms/garden", json={"region": "Grounds"})
    r = client.patch(f"/api/chats/{cid}/regions/grounds",
                     json={"far_look": "lawns and clipped hedges"})
    assert r.status_code == 200, r.text
    assert r.json()["far_look"] == "lawns and clipped hedges" and r.json()["look"] == ""
    assert client.get(f"/api/chats/{cid}/rooms/garden").json()["region_far_look"] == \
        "lawns and clipped hedges"
