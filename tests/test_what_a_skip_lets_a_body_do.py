"""What a skip lets a body do: reach, walk, and say what failed
(`world/skip_itinerary.py`'s executor, `agents/skip_stage.py`'s resolution,
`persist/commit_skip.py`).

THE LIVE EVIDENCE is the lighthouse replayed on 2026-10-21's code (chat 3,
turn 25, idx 8: "Two days later the wind gets up from the west ..."): its
world before the turn (checkpoint 8) and each mind's answer and resolved
itinerary are `tests/data/skip_live_lighthouse.json`. Three defects of the
stage's own executor, each read off that turn's `skip_lives` step:

  1. THE HOLDING CHECK FAILED WHAT WAS WITHIN REACH. The keeper's first three
     stretches -- kneeling at the pedestal, lighting the lamp, keeping the
     watch -- failed `not_held` in the lamp room with the lamp standing in
     it; every stretch of the boatman's that used his boat failed so.
  2. THE BOATMAN WALKED HOME ACROSS THE SEA. His day ended "The Landing, at
     the foot of the iron ladder with the Mary Ann made fast" and the
     executor stood him there, ten minutes a leg across thirteen kilometres
     of channel and the mainland's frontier stub, his boat left in the
     channel.
  3. THE LOG DID NOT SAY WHAT FAILED, so the memory writer could not: his
     memory reads "letter in the fist, into the box" against a
     `failed/not_held` row that named nothing.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from world import skip_itinerary as itin

ROOT = Path(__file__).resolve().parent.parent
LIVE = json.loads((ROOT / "tests" / "data" / "skip_live_lighthouse.json")
                  .read_text(encoding="utf-8"))

ELIAS, PELL, RHONA = "Elias Thorne", "Pell Hardacre", "Rhona Carrick"
FROM, UNTIL = LIVE["span"]["from_s"], LIVE["span"]["until_s"]
STUBS = {stub: spec["frontier_of"]["room"] for stub, spec in LIVE["provisional"].items()}

LAMP = "affb0aacaf0f4eb4"               # "the tower lamp", in the lamp room
CLOCKWORK = "05e347afb3e54734"          # "the new clockwork", in the lamp room
TOOLKIT = "648b29e145654b11"            # "clockmaker's toolkit", in Rhona's hands
LETTER = "d2a5e24893e04b45"             # "a sealed letter", on the hall table
POST_BAG = "2cc99b57e0334ce3"           # "the post bag", in the hall
MARY_ANN = "06813d0bbd5b4d20"           # "The Mary Ann", under way in the channel
PEDESTAL = itin.FIXTURE_PREFIX + "lamp_room:lamp_pedestal"


def _scene():
    return copy.deepcopy(LIVE["scene"])


def _itinerary(name):
    return copy.deepcopy(LIVE["minds"][name]["itinerary"])


def _ways(scene):
    return itin.Ways(scene, joins=itin.frontier_joins(STUBS))


def _judge(reach, named):
    return lambda uses, room, away=None, t=None: reach.missing(uses, named, room, away, t)


#: The things each mind's words name, as the stage resolves them: exactly
#: where a thing's own name is the words, else the decision model's pick --
#: stubbed here with the pick a reader of these words makes -- else nothing
#: the world holds.
PICKS = {
    ELIAS: {"the new clockwork in the crate": CLOCKWORK, "the old lamp mechanism": LAMP,
            "the clockmaker's toolkit": TOOLKIT, "the old mechanism": LAMP},
    PELL: {"Rhona Carrick's sealed letter, dry in the inside pocket of the oilskin jacket":
           LETTER},
}


def _named(name, reach):
    named = {}
    for stretch in _itinerary(name):
        for thing in stretch.get("uses") or ():
            named[thing] = reach.named(thing) or (
                {PICKS[name][thing]} if thing in PICKS[name] else set())
    return named


def _live(name, scene=None):
    scene = scene or _scene()
    ways = _ways(scene)
    under_way = itin.journeys(scene, FROM)
    here = scene["positions"][name]
    reach = itin.Reach(scene, name, journeys=under_way)
    log, far = itin.live_through(
        _itinerary(name), scene=scene, start_room=here, ways=ways,
        missing_from=_judge(reach, _named(name, reach)),
        journey=itin.journey_under_way(scene, here, under_way, ways))
    return itin.place_words(log, scene), far, here


# --------------------------------------------------------------------------
# 1. What a stretch uses is met by what the mind carries and what it can reach
# --------------------------------------------------------------------------

def test_the_keepers_lamp_is_within_his_reach_and_lighting_it_is_not_failed():
    """The lamp is the lamp room's own: "Light the lamp" (uses the lamp and
    the logbook) is no longer failed `not_held`. The live run failed it, and
    the keeper's two stretches beside it, with the lamp standing in the room."""
    log, _far, _here = _live(ELIAS)
    as_run = LIVE["minds"][ELIAS]["log_as_run"]
    assert [(r["outcome"], r["reason"]) for r in as_run[:3]] == [("failed", "not_held")] * 3
    lighting = log[1]
    assert lighting["doing"].startswith("Light the lamp")
    assert (lighting["outcome"], lighting["reason"], lighting["missing"]) == \
        ("not_known", None, [])


def test_a_rooms_things_and_fixtures_are_within_reach_and_elsewhere_is_not():
    """Within reach in a room: the things the scene stands there and its
    fixtures (`anchors`). Elsewhere -- the same lamp from the kitchen -- the
    thing is missing, named as the mind wrote it."""
    scene = _scene()
    reach = itin.Reach(scene, ELIAS)
    assert reach.named("the lamp") == {LAMP}                 # an alias, exactly
    named = {"the lamp": {LAMP}, "the new clockwork in the crate": {CLOCKWORK},
             "the pedestal": {PEDESTAL}}
    assert reach.missing(list(named), named, "lamp_room") == []
    assert reach.missing(["the lamp", "the pedestal"], named, "kitchen") == \
        ["the lamp", "the pedestal"]


def test_a_thing_on_another_body_is_theirs_and_out_of_reach():
    """The clockmaker's toolkit is in the player's hands: the keeper reaches
    it nowhere -- not even in the room she stands in -- and his stretches that
    meant to use it fail `not_held`, naming it. In her own reach it is
    carried."""
    log, _far, _here = _live(ELIAS)
    at_the_pedestal, _lighting, the_watch = log[:3]
    assert (at_the_pedestal["reason"], at_the_pedestal["missing"]) == \
        ("not_held", ["clockmaker's toolkit"])
    assert (the_watch["reason"], the_watch["missing"]) == \
        ("not_held", ["the clockmaker's toolkit"])
    scene = _scene()
    named = {"the kit roll": {TOOLKIT}}
    assert itin.Reach(scene, ELIAS).missing(["the kit roll"], named, "tower_hall") == \
        ["the kit roll"]
    assert itin.Reach(scene, RHONA).missing(["the kit roll"], named, "tower_hall") == []


def test_words_that_name_no_thing_the_world_holds_are_never_missing():
    """The brass shim was a sound with no thing behind it and "the logbook"
    nothing at all: the executor does not deny what the world never said was
    absent, so the stretch stays the world's to judge (`not_known`) -- and
    nothing is put in the mind's hands either."""
    scene = _scene()
    assert not any(e.get("name", "").casefold().endswith("shim")
                   for e in scene["entities"].values())
    reach = itin.Reach(scene, ELIAS)
    named = {"the brass shim": reach.named("the brass shim"),
             "the logbook": reach.named("the logbook")}
    assert named == {"the brass shim": set(), "the logbook": set()}
    assert reach.missing(list(named), named, "lamp_room") == []
    stretch = dict(_itinerary(ELIAS)[1], uses=["the brass shim", "the logbook"])
    log, _far = itin.live_through([stretch], scene=scene, start_room="lamp_room",
                                  missing_from=_judge(reach, named))
    assert (log[0]["outcome"], log[0]["reason"]) == ("not_known", None)


def test_a_vessel_is_never_held_one_is_aboard_it_or_beside_it():
    """Beside the Mary Ann in the channel, or aboard her, the boatman has her;
    on the landing, with her out in the channel, he has not; and once her
    journey has ended she stands where it ended."""
    scene = _scene()
    under_way = itin.journeys(scene, FROM)
    reach = itin.Reach(scene, PELL, journeys=under_way)
    named = {"the Mary Ann": reach.named("the Mary Ann")}
    assert named["the Mary Ann"] == {MARY_ANN}
    ends = under_way[MARY_ANN]["until_s"]
    assert reach.missing(["the Mary Ann"], named, "the_channel", t=FROM) == []
    assert reach.missing(["the Mary Ann"], named, "mary_ann_interior", t=FROM) == []
    assert reach.missing(["the Mary Ann"], named, "rock_landing", t=FROM) == ["the Mary Ann"]
    assert reach.missing(["the Mary Ann"], named, "the_mainland", t=ends - 1.0) == \
        ["the Mary Ann"]
    assert reach.missing(["the Mary Ann"], named, "the_mainland", t=ends) == []
    # Off the map nothing is in reach that the mind does not carry.
    assert reach.missing(["the Mary Ann"], named, None, "the mainland quay", ends) == \
        ["the Mary Ann"]


def test_what_lies_inside_a_thing_goes_where_the_thing_goes():
    """A thing lying inside another is within reach wherever the outermost
    thing holding it is: the post bag stowed in the Mary Ann is the
    boatman's to hand aboard her or beside her, and on the mainland once she
    is in -- never from the hall, where it would lie on its own."""
    scene = _scene()
    scene["contained"][POST_BAG] = {"in": MARY_ANN, "mode": "stowed"}
    under_way = itin.journeys(scene, FROM)
    reach = itin.Reach(scene, PELL, journeys=under_way)
    named = {"the post bag": reach.named("the post bag")}
    ends = under_way[MARY_ANN]["until_s"]
    for room, t in (("mary_ann_interior", FROM), ("the_channel", FROM), ("the_mainland", ends)):
        assert reach.missing(["the post bag"], named, room, t=t) == [], room
    assert reach.missing(["the post bag"], named, "tower_hall", t=FROM) == ["the post bag"]


# --------------------------------------------------------------------------
# 2. A body walks only a walkable way
# --------------------------------------------------------------------------

def test_a_frontier_stubs_join_is_not_a_way():
    """The mainland is a space the plan holds open (`provisional`, minted
    off the landing): the open door it hangs off the landing, with no
    distance, says what lies that way and never what stands between. A
    planned room of the tower's own plan -- the keeper's bedroom -- is walked
    as ever, and so is the same join once a plan has claimed the space."""
    scene = _scene()
    ways = _ways(scene)
    assert itin.frontier_joins(STUBS) == {frozenset(("the_mainland", "rock_landing"))}
    route, why = ways.route("rock_landing", "the_mainland")
    assert route is None and why == itin.REASON_NO_CROSSING       # only by the channel
    route, _why = ways.route("kitchen", "bedroom_elias")
    assert route == ["kitchen", "bedroom_elias"]
    assert scene["rooms"]["bedroom_elias"]["planned"]
    # Without the channel the frontier is no way at all...
    dry = _scene()
    dry["rooms"].pop("the_channel")
    for room in dry["rooms"].values():
        room["adjacent"] = [e for e in room.get("adjacent") or () if e.get("to") != "the_channel"]
    assert _ways(dry).route("rock_landing", "the_mainland") == (None, itin.REASON_NO_ROUTE)
    # ...and a space a plan has claimed is a room like any other.
    assert itin.Ways(dry).route("rock_landing", "the_mainland")[0] == \
        ["rock_landing", "the_mainland"]


def test_a_way_across_water_is_a_vessels():
    """Into, across or out of a room whose floor is water, or the space a
    vessel under way moves through, a body goes only by vessel: the walk
    fails `no_crossing`. Either reading stands alone. A `remote` way over
    ground is walked -- the tavern's quay is one from its market."""
    scene = _scene()
    assert scene["rooms"]["the_channel"]["floor"] == "water"
    assert itin.media(scene) == {"the_channel"}
    assert _ways(scene).route("rock_landing", "the_channel") == (None, itin.REASON_NO_CROSSING)
    # Out of the water to somewhere off the map is a crossing too: a body in
    # the channel with no vessel carrying it stays in the channel.
    ashore = [{"from_s": FROM, "until_s": FROM + 3600.0, "room": None,
               "away": "the harbour pub", "where_text": "the harbour pub",
               "doing": "a pint", "asleep": False, "with": [], "why": "", "uses": []}]
    log, far = itin.live_through(ashore, scene=scene, start_room="the_channel",
                                 ways=_ways(scene))
    assert (log[0]["reason"], log[0]["meant"], far["room"]) == \
        (itin.REASON_NO_CROSSING, "the harbour pub", "the_channel")
    no_floor = _scene()
    no_floor["rooms"]["the_channel"].pop("floor")
    assert itin.media(no_floor) == {"the_channel"}             # the boat's route
    docked = _scene()
    docked["entities"][MARY_ANN]["state"]["transit"]["phase"] = "docked"
    assert itin.media(docked) == {"the_channel"}               # the floor
    docked["rooms"]["the_channel"].pop("floor")
    assert itin.media(docked) == set()
    assert itin.Ways(docked).route("rock_landing", "the_channel")[0] == \
        ["rock_landing", "the_channel"]
    tavern = {"rooms": {
        "gull_taproom": {"name": "The Gull", "adjacent": [{"to": "market_strand",
                                                           "barrier": "open_door"}]},
        "market_strand": {"name": "Market Strand", "planned": True, "adjacent": [
            {"to": "gull_taproom", "barrier": "open_door"},
            {"to": "saltreach_quay", "barrier": "open", "distance": "remote"}]},
        "saltreach_quay": {"name": "Saltreach Quay", "planned": True, "floor": "stone",
                           "adjacent": [{"to": "market_strand", "barrier": "open",
                                         "distance": "remote"}]}}}
    assert itin.Ways(tavern).route("gull_taproom", "saltreach_quay")[0] == \
        ["gull_taproom", "market_strand", "saltreach_quay"]


def test_off_the_map_a_body_comes_back_by_where_it_left():
    """A body that left the map from the mainland comes back onto it by the
    mainland: the rock's landing is across the channel from there, so the
    stretch fails `no_crossing` and it stays where it was. One whose leaving
    the world never saw comes back with no walk, as before."""
    scene = _scene()
    ways = _ways(scene)
    stretches = [
        {"from_s": 0.0, "until_s": 3600.0, "room": None, "away": "the harbour pub",
         "where_text": "the harbour pub", "doing": "a pint", "asleep": False,
         "with": [], "why": "", "uses": []},
        {"from_s": 3600.0, "until_s": 7200.0, "room": "rock_landing", "away": None,
         "where_text": "The Landing", "doing": "makes fast", "asleep": False,
         "with": [], "why": "", "uses": []}]
    log, far = itin.live_through(stretches, scene=scene, start_room="the_mainland", ways=ways)
    assert [(r["outcome"], r["reason"]) for r in log] == [
        ("not_known", None), ("failed", itin.REASON_NO_CROSSING)]
    assert (log[1]["room"], log[1]["away"], log[1]["meant"]) == \
        (None, "the harbour pub", "The Landing")
    assert far["away"] == "the harbour pub" and far["room"] is None
    assert itin.left_the_map_from(log, "the_mainland") == "the_mainland"
    # Left from the landing's own side: the walk home is up the ladder.
    log, far = itin.live_through(stretches, scene=scene, start_room="the_stair", ways=ways)
    assert far["room"] == "rock_landing" and log[1]["from_s"] > 3600.0
    # Away since before the span, by nowhere the world kept: no walk to price.
    log, far = itin.live_through(stretches[1:], scene=scene, start_away="the harbour pub",
                                 ways=ways)
    assert far["room"] == "rock_landing" and log[0]["from_s"] == 3600.0
    # ...and by the room its whereabouts kept, the walk is the world's again.
    log, far = itin.live_through(stretches[1:], scene=scene, start_away="the harbour pub",
                                 start_exit="the_mainland", ways=ways)
    assert far["away"] == "the harbour pub" and log[0]["reason"] == itin.REASON_NO_CROSSING


def test_a_body_under_way_goes_where_its_vessel_goes():
    """The boatman stood in the channel beside the Mary Ann, bound for the
    mainland: his first stretch there begins when her way is done (the price
    the mechanics book, `spatial.journey_seconds`), not ten minutes in. A
    stretch that ends before she arrives went nowhere of its own; a body
    aboard steps out onto the mainland once she is in."""
    scene = _scene()
    ways = _ways(scene)
    under_way = itin.journeys(scene, FROM)
    journey = itin.journey_under_way(scene, "the_channel", under_way, ways)
    assert (journey["vessel"], journey["room"], journey["aboard"]) == \
        (MARY_ANN, "the_mainland", False)
    ends = journey["until_s"]
    assert ends - FROM == pytest.approx(10007.7, abs=1.0)
    log, _far = itin.live_through(_itinerary(PELL)[:1], scene=scene, start_room="the_channel",
                                  ways=ways, journey=journey)
    assert (log[0]["from_s"], log[0]["room"]) == (pytest.approx(ends), "the_mainland")
    assert LIVE["minds"][PELL]["log_as_run"][0]["from_s"] == FROM + 600.0
    early = [{"from_s": FROM, "until_s": FROM + 3600.0, "room": None,
              "away": "the harbour pub", "where_text": "the harbour pub",
              "doing": "a pint", "asleep": False, "with": [], "why": "", "uses": []}]
    log, _far = itin.live_through(early, scene=scene, start_room="the_channel",
                                  ways=ways, journey=journey)
    assert (log[0]["reason"], log[0]["room"], log[0]["meant"]) == \
        (itin.REASON_TOO_FAR, "the_channel", "the harbour pub")
    aboard = itin.journey_under_way(scene, "mary_ann_interior", under_way, ways)
    assert aboard["aboard"] and aboard["dock"] == "mary_ann_interior"
    ashore = [{"from_s": FROM, "until_s": UNTIL, "room": "the_mainland", "away": None,
               "where_text": "The Mainland", "doing": "ashore", "asleep": False,
               "with": [], "why": "", "uses": []}]
    log, far = itin.live_through(ashore, scene=scene, start_room="mary_ann_interior",
                                 ways=ways, journey=aboard)
    assert far["room"] == "the_mainland" and log[0]["from_s"] >= ends
    # Not with the vessel: nobody else is carried.
    assert itin.journey_under_way(scene, "rock_landing", under_way, ways) is None


def test_the_boatmans_live_day_ends_away_on_the_mainland():
    """His whole answered day, as the stage resolved it: on the mainland
    from the boat's arrival, his runs back across the channel and up onto the
    landing failed `no_crossing` -- a crossing of his own is not built -- and
    he is AWAY at the last place his day could reach, where the live run stood
    him on the rock's landing."""
    log, far, here = _live(PELL)
    assert LIVE["minds"][PELL]["far_end_as_run"]["room"] == "rock_landing"
    assert far == {"room": None, "away": "the mainland quay", "asleep": False,
                   "asleep_since_s": None}
    assert itin.left_the_map_from(log, here) == "the_mainland"
    home = log[-3:]
    assert [r["reason"] for r in home] == [itin.REASON_NO_CROSSING] * 3
    assert [r["meant"] for r in home] == [
        "the channel", "The Landing and The Steps",
        "The Landing, at the foot of the iron ladder with the Mary Ann made fast"]
    assert all(r["where_text"] == "the mainland quay" and r["away"] == "the mainland quay"
               for r in home)
    assert not any(r["room"] in ("rock_landing", "the_channel") for r in log)


# --------------------------------------------------------------------------
# 3. Every row says what failed
# --------------------------------------------------------------------------

def test_every_row_says_what_failed():
    """Every LOG row carries `missing` and `meant`. A row failed `not_held`
    got where it meant to be and names what was not to hand, as the mind
    wrote it; a row failed on the way says where the body WAS in its words
    and where it meant to be in `meant`; every other row leaves both
    empty. The boatman's letter lay on the hall table on the rock."""
    log, _far, _here = _live(PELL)
    for row in log:
        assert {"missing", "meant"} <= set(row)
        if row["reason"] == itin.REASON_NOT_HELD:
            assert row["missing"] and row["meant"] is None
        elif row["reason"] in itin.ROUTE_REASONS:
            assert row["meant"] and row["missing"] == []
        else:
            assert row["missing"] == [] and row["meant"] is None
    first = log[0]
    assert first["room"] == "the_mainland"
    assert (first["outcome"], first["reason"], first["missing"]) == (
        "failed", "not_held",
        ["Rhona Carrick's sealed letter, dry in the inside pocket of the oilskin jacket"])
    assert first["where_text"] == "the mainland quay and the post office on the quay"


def test_the_towns_rows_say_what_failed_too():
    """A row the town's charter wrote (`world/charter_skip`) is laid over the
    same way (`lay_over`): one it failed on the way says where it got to and
    keeps the mind's words in `meant`; one inside a stretch that uses a thing
    out of reach fails `not_held`, naming it; and every row carries both
    fields."""
    scene = _scene()
    reach = itin.Reach(scene, ELIAS)
    named = {"the lamp": {LAMP}}
    stretches = [{"from_s": 0.0, "until_s": 100.0, "room": "lamp_room", "away": None,
                  "where_text": "The Lamp Room", "doing": "lights it", "asleep": False,
                  "with": [], "why": "", "uses": ["the lamp"]}]
    rows = [{"from_s": 0.0, "until_s": 50.0, "room": "kitchen", "away": None,
             "where_text": "The Lamp Room", "doing": "lights it", "asleep": False,
             "seen": [], "weather": None, "outcome": "failed", "reason": "no_route"},
            {"from_s": 50.0, "until_s": 100.0, "room": "kitchen", "away": None,
             "where_text": "The Kitchen", "doing": "lights it", "asleep": False,
             "seen": [], "weather": None, "outcome": "done", "reason": None}]
    log = itin.lay_over(rows, stretches, missing_from=_judge(reach, named))
    assert (log[0]["meant"], log[0]["where_text"], log[0]["missing"]) == \
        ("The Lamp Room", "", [])
    assert itin.place_words(log, scene)[0]["where_text"] == "The Kitchen"
    assert (log[1]["outcome"], log[1]["reason"], log[1]["missing"]) == \
        ("failed", "not_held", ["the lamp"])


# --------------------------------------------------------------------------
# The stage: its resolution, its frontier, its payload, its whereabouts
# --------------------------------------------------------------------------

def _decisions(picks):
    """The decision model, made deterministic: a thing question whose quoted
    words are a key of `picks` gets the option whose words begin with the
    pick; everything else `none`. Every request is recorded."""
    asked = []

    def override(state, questions):
        asked.append(dict(questions))
        out = {}
        for key, question in questions.items():
            pick = "none"
            for words, option in picks.items():
                if f'"{words}"' in question["instructions"]:
                    pick = next((k for k, v in question["criteria"].items()
                                 if str(v).startswith(option)), "none")
            out[key] = {"type": "choice", "choice": pick, "probabilities": {pick: 0.9}}
        return out

    return override, asked


def test_one_request_asks_about_the_things_of_the_world_and_what_it_has(monkeypatch):
    """The mind's words for a thing are resolved as its places are: exactly,
    then by the ONE decision-model request per mind -- now over what it has
    on it AND the things and fixtures of the world it may mean, the room it
    stands in first -- then as words naming no thing the world holds."""
    from agents import skip_stage
    from llm import decisions
    scene = _scene()
    override, asked = _decisions({"the new clockwork in the crate": "the new clockwork",
                                  "the old lamp mechanism": "lamp pedestal",
                                  "the clockmaker's toolkit": "clockmaker's toolkit"})
    monkeypatch.setattr(decisions, "OVERRIDE", override)
    stretches = [dict(s) for s in _itinerary(ELIAS)]
    for s in stretches:
        s["kind"] = itin.KIND_PLAN
    placed, missing_from, record = skip_stage.resolve_mind(
        ELIAS, stretches, scene, {}, "lamp_room", skip_stage.held_things(scene, ELIAS),
        under_way=itin.journeys(scene, FROM))
    assert len(asked) == 1
    thing_questions = [q for k, q in asked[0].items() if k.startswith("thing:")]
    offered = set(thing_questions[0]["criteria"].values())
    assert any(v.startswith("lamp pedestal (") for v in offered)    # a fixture
    assert any(v.startswith("clockmaker's toolkit") for v in offered)  # in her hands
    assert "heavy navy wool fisherman's sweater" in offered          # on him
    assert record["things"]["the lamp"] == [LAMP]
    assert record["things"]["the logbook"] == []
    assert record["things"]["the old lamp mechanism"] == [PEDESTAL]
    assert missing_from(["the lamp", "the old lamp mechanism", "the logbook"],
                        "lamp_room", None, FROM) == []
    assert missing_from(["the clockmaker's toolkit"], "lamp_room", None, FROM) == \
        ["the clockmaker's toolkit"]
    assert [s["room"] for s in placed][:2] == ["lamp_room", "lamp_room"]


@pytest.fixture
def chat(temp_db):
    from core.db import qi, wset
    now = time.time()
    cid = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
             ("The Lamp Room", "", now))
    wset(cid, "scene", _scene())
    wset(cid, "simulation_clock", {"elapsed_seconds": FROM, "anchor_hour": 15.75,
                                   "day_length_hours": 24.0})
    return cid


def test_the_stage_reads_the_frontier_the_plan_holds_open(chat):
    """`frontier_stubs` reads the registry: a planned room marked
    `provisional` is a space held open, joined to the room it was minted
    from; a room a plan has claimed is not."""
    from agents import skip_stage
    from core.db import qi
    qi("INSERT INTO room_registry(chat_id,room_uid,name,payload) VALUES(?,?,?,?)",
       (chat, "the_mainland", "The Mainland", json.dumps({"planned": {
           "name": "The Mainland", "provisional": True,
           "frontier_of": {"room": "rock_landing", "axis": "the mainland"}}})))
    qi("INSERT INTO room_registry(chat_id,room_uid,name,payload) VALUES(?,?,?,?)",
       (chat, "bedroom_elias", "Elias's Room", json.dumps({"planned": {
           "name": "Elias's Room", "purpose": "a narrow bedroom"}})))
    assert skip_stage.frontier_stubs(chat) == {"the_mainland": "rock_landing"}


def test_the_far_end_payload_says_what_failed(chat):
    """The boatman's far-end call carries his own log with what failed on
    each row that did: where he meant to be, and what was not to hand."""
    from agents import skip_stage
    log, far, here = _live(PELL)
    output = {"span": {"from_s": FROM, "until_s": UNTIL},
              "minds": {PELL: {"source": "asked", "answer": None, "itinerary": [],
                               "log": log, "far_end": far}}}
    ctx = SimpleNamespace(chat=SimpleNamespace(id=chat),
                          get=lambda key, default=None: output if key == "skip_lives" else default)
    rows = skip_stage.stretch_for_payload(ctx, PELL)
    assert rows[0]["reason"] == "not_held" and rows[0]["missing"] == [
        "Rhona Carrick's sealed letter, dry in the inside pocket of the oilskin jacket"]
    assert "meant" not in rows[0]
    assert rows[-1]["reason"] == "no_crossing" and rows[-1]["where"] == "the mainland quay"
    assert rows[-1]["meant"].startswith("The Landing, at the foot of the iron ladder")
    assert "missing" not in rows[-1]
    assert not any("missing" in r or "meant" in r for r in rows if r["outcome"] != "failed")


def test_where_a_mind_left_the_map_rides_its_whereabouts(chat):
    """The commit keeps the room an away mind left the map by
    (`left_from`), and the next skip starts it there: from the mainland,
    the rock is still across the channel."""
    from agents import skip_stage
    from core.db import qi, wget
    from persist.commit import commit_skip_lives
    from story.character_schema import default_character_data
    now = time.time()
    char = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
              "VALUES(?,?,?,?,?)", (PELL, json.dumps(default_character_data(PELL)),
                                    "{}", now, "uid_pell"))
    qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
       (chat, char, "active", "{}"))
    log, far, here = _live(PELL)
    far = dict(far, left_from=itin.left_the_map_from(log, here))
    ctx = SimpleNamespace(
        chat=SimpleNamespace(id=chat), turn=SimpleNamespace(id=None, idx=8, frame_id=None),
        skip_lives={"span": {"from_s": FROM, "until_s": UNTIL},
                    "minds": {PELL: {"log": log, "far_end": far}}})
    wrote = commit_skip_lives(ctx)
    assert wrote["away"][PELL] == "the mainland quay"
    record = wget(chat, "whereabouts")[PELL]
    assert record["left_from"] == "the_mainland" and record["label"] == "the mainland quay"
    assert skip_stage._left_the_map_from(chat, PELL) == "the_mainland"
    row = {"status": "dormant"}
    assert skip_stage._standing_place(chat, PELL, row) == (None, "the mainland quay")


def test_the_stage_brings_an_away_mind_back_by_where_it_left(chat, monkeypatch):
    """The whole stage, for the boatman left away on the mainland by the
    skip before: dormant, his whereabouts keeping the room he left the map by.
    Asked again, his day ends "The Landing"; the stage starts him off the map
    by the mainland, reads the frontier the plan holds open, and leaves him
    away -- the rock is still across the channel -- with the room he left by
    kept on the far end for the commit."""
    from agents import skip_stage
    from core.db import qi, wset
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from llm import decisions
    from story.character_schema import default_character_data
    from story.scene import active_cast
    now = time.time()
    pell = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
              "VALUES(?,?,?,?,?)", (PELL, json.dumps(default_character_data(PELL)),
                                    "{}", now, "uid_pell"))
    qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
       (chat, pell, "dormant", "{}"))
    qi("INSERT INTO room_registry(chat_id,room_uid,name,payload) VALUES(?,?,?,?)",
       (chat, "the_mainland", "The Mainland", json.dumps({"planned": {
           "name": "The Mainland", "provisional": True,
           "frontier_of": {"room": "rock_landing", "axis": "the mainland"}}})))
    scene = _scene()
    scene["positions"].pop(PELL)
    wset(chat, "scene", scene)
    wset(chat, "whereabouts", {PELL: {"kind": "off_map", "label": "the mainland quay",
                                      "since_s": FROM - 3600.0, "turn_idx": 7,
                                      "char_id": pell, "left_from": "the_mainland"}})
    turn = qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (chat, 8, "A day later ...", now))
    block = {"duration_seconds": 24 * 3600.0}
    interp = {"state_assertions": {"time": dict(block), "causal_steps": [
                  {"chrono_id": 1, "stage": "interpret", "patch": {"time": dict(block)}}]},
              "causal_ledger": [{"chrono_id": 1, "seconds": 0.0, "commitment": "asserted"}],
              "flow": {"reactors": [], "tom_triggers": []}, "authorial_offers": []}
    answer = {"routine": [], "plan": [],
              "at_the_end": {"where": "The Landing", "doing": "makes fast at the ring"}}
    monkeypatch.setattr(skip_stage, "ask", lambda ctx, row, span, nonce=0: (answer, None))
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {})
    ctx = PipelineContext(
        chat=ChatData(id=chat, name="The Lamp Room", persona_id=None, lorebook_id=None,
                      scenario="", created=now),
        turn=TurnData(id=turn, chat_id=chat, idx=8, player_input="A day later ...",
                      created=now),
        cast=active_cast(chat), input="A day later ...")
    ctx.director_interpret = interp
    out = skip_stage.skip_lives(ctx, 0)
    mind = out["minds"][PELL]
    assert mind["log"][-1]["room"] is None
    assert (mind["log"][-1]["reason"], mind["log"][-1]["meant"]) == \
        (itin.REASON_NO_CROSSING, "The Landing")
    assert mind["far_end"]["away"] == "the mainland quay"
    assert mind["far_end"]["left_from"] == "the_mainland"
