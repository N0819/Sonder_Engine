"""What a mind can get inside a skip's stretch, what can be missing off the
map, and what a routine holds (`world/skip_itinerary.py`'s `Reach.fetch`,
`Reach.missing` and `Holding`, `agents/skip_stage.py`'s wiring, the
`character_skip` card).

THE LIVE EVIDENCE is the lighthouse replayed a THIRD time, on cb69070e (chat
3): turn 25 (idx 8, "Two days later the wind gets up from the west ...") and
turn 26 (idx 9, "That night, when Elias comes down from the first watch
..."). Each turn's world before it, every mind's answer, itinerary, log as
run and far end, the thing resolutions the stage noted, the memories the job
wrote and turn 26's narration are `tests/data/skip_live_lighthouse_3.json`.
Three defects:

  1. A FALSE FAILURE BECAME CANON. The keeper's lamp work failed `not_held`
     for want of "paraffin" for two nights -- filling the reservoir,
     lighting, both watches, checking the lamp -- while the paraffin crate
     lay in the hall of his own tower, two flights down. His memories said
     "the paraffin was down to the dregs and there was none in the stores",
     and the next beat gave him "The paraffin's spent. Two nights
     hand-turned."
  2. A THING OFF THE MAP. At home on the mainland, off the map, the
     boatman's "kitchen table" was read as the lighthouse kitchen's table
     and counted missing; on the quay, "crates" were the pile of stores on
     the rock's steps.
  3. ONE-OFFS IN THE ROUTINE. The boatman put his day-0 crossing and his
     errand to post the letter in `routine`; the itinerary lays a routine
     on every day, so both ran again on day 1 and failed again.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from world import skip_itinerary as itin

ROOT = Path(__file__).resolve().parent.parent
LIVE = json.loads((ROOT / "tests" / "data" / "skip_live_lighthouse_3.json")
                  .read_text(encoding="utf-8"))["turns"]
T25, T26 = LIVE["25"], LIVE["26"]

ELIAS, PELL, RHONA = "Elias Thorne", "Pell Hardacre", "Rhona Carrick"

TOOLKIT = "9d60602b2df941ac"        # "clockmaker's toolkit", carried by Rhona
PARAFFIN = "47210ed830fd4bbd"       # "paraffin crate", in the hall
CLOCKWORK = "70255631487949b6"      # "the new clockwork", in the lamp room
LAMP = "9b55ad7022074164"           # "the tower lamp", in the lamp room
LETTER = "7c995446a21c43e9"         # "a sealed letter", in the hall on the rock
PILE = "24259f01104d46ef"           # "a pile of stores" (cargo), on the steps
POST_BAG = "352763c6913d4cbe"       # "the post bag", in the hall
MARY_ANN = "89e8858add634b3a"       # "The Mary Ann", under way in the channel
KITCHEN_TABLE = itin.FIXTURE_PREFIX + "kitchen:kitchen_table"
PEDESTAL = itin.FIXTURE_PREFIX + "lamp_room:lamp_pedestal"

#: The things each mind's words name, as the stage resolves them: exactly
#: where a thing's own name is the words, else the decision model's pick.
#: The live run noted its picks cut at 400 characters (`decisions_as_noted`):
#: the small tools to the toolkit, the letter, the crates to the pile of
#: stores, the post bag, the Mary Ann, the kitchen table to the lighthouse
#: kitchen's. "paraffin" lies past the cut: the paraffin crate in the hall,
#: where the keeper's own next answer puts it ("the paraffin crate opened --
#: the one Pell brought, still below in the hall"). With these picks the
#: cb69070e reach gives every `missing` of the live LOGs
#: (`test_the_picks_reproduce_the_third_replays_live_logs`).
PICKS = {
    ELIAS: {"small tools from the hall shelf": TOOLKIT, "small tools": TOOLKIT,
            "paraffin": PARAFFIN, "the new clockwork from the Board's crate": CLOCKWORK,
            "new clockwork": CLOCKWORK, "the iron pedestal": PEDESTAL},
    PELL: {"Rhona Carrick's sealed letter": LETTER, "crates": PILE,
           "the post bag": POST_BAG, "kitchen table": KITCHEN_TABLE},
}

#: The live decision model's answers to "can {name} do '{doing}' without
#: {missing}?" on turn 25, by the doing's first words: the keeper's rows 0, 5,
#: 12 and 13 yes, his seven others and all three of the boatman's no.
WITHOUT = {
    "standing at the pedestal examining": 0.9, "extinguishing the lamp, cleaning": 0.9,
    "checking the lamp after the second": 0.9, "standing at the lamp pedestal in": 0.9,
    "lighting the lamp for the night": 0.1, "first night watch": 0.1,
    "checking the lamp — trimming": 0.1, "working on the mechanism": 0.1,
    "preparing the lamp for the night": 0.1, "lighting the lamp — striking": 0.1,
    "night watch — scanning": 0.1, "Walks the letter up": 0.1,
    "Loads the Tuesday run early": 0.1,
}


def _scene(turn):
    return copy.deepcopy(turn["scene"])


def _stubs(turn):
    return {stub: spec["frontier_of"]["room"] for stub, spec in turn["provisional"].items()}


def _ways(turn, scene):
    return itin.Ways(scene, joins=itin.frontier_joins(_stubs(turn)))


def _named(turn, name, reach, stretches=None):
    named = {}
    for stretch in stretches if stretches is not None else turn["minds"][name]["itinerary"]:
        for thing in stretch.get("uses") or ():
            named[thing] = reach.named(thing) or (
                {PICKS[name][thing]} if thing in PICKS[name] else set())
    return named


def _start(turn, name, scene):
    """Where the mind stands as the stretch opens, as the stage reads it."""
    here = scene["positions"].get(name)
    record = (turn.get("whereabouts") or {}).get(name) or {}
    away = None if here else (record.get("label") or None)
    return here, away, record.get("left_from")


def _live(turn, name, stretches=None, scene=None, here=None):
    """The executor over one mind's itinerary, as the stage runs it: its
    holding check (`Holding`) reading the picks, fetching over the ways a
    body walks."""
    scene = scene or _scene(turn)
    stretches = copy.deepcopy(stretches if stretches is not None
                              else turn["minds"][name]["itinerary"])
    ways = _ways(turn, scene)
    under_way = itin.journeys(scene, turn["span"]["from_s"])
    start, away, left = _start(turn, name, scene)
    here = here or start
    reach = itin.Reach(scene, name, journeys=under_way, ways=ways)
    holding = itin.Holding(reach, _named(turn, name, reach, stretches))
    log, far = itin.live_through(
        stretches, scene=scene, start_room=here, start_away=away, start_exit=left,
        ways=ways, missing_from=holding, fetch_from=holding.fetch,
        journey=itin.journey_under_way(scene, here, under_way, ways))
    return itin.place_words(log, scene), far


def _judge(log, name):
    """`judge_without` over `log`, the live decision model's answers stubbed."""
    answers = {}
    for key, question in itin.without_questions(name, log).items():
        yes = next((p for start, p in WITHOUT.items()
                    if f'"{start}' in question["instructions"]), None)
        if yes is not None:
            answers[key] = {"type": "noul", "noul": yes}
    return itin.judge_without(log, answers)


def _trip(scene, turn, here, there):
    """Seconds to walk from `here` to `there` and back, over the ways a
    body walks."""
    ways = _ways(turn, scene)
    return (itin.walk_seconds(scene, ways.route(here, there)[0])
            + itin.walk_seconds(scene, ways.route(there, here)[0]))


# --------------------------------------------------------------------------
# The live run, reproduced
# --------------------------------------------------------------------------

def _assert_the_picks_reproduce_the_keepers_live_log():
    """The stubs stand for the live run: on the map, the reach of where a
    stretch finds the mind (no fetch) gives every `missing` the keeper's
    live LOG has -- paraffin on six rows, the small tools on six."""
    scene = _scene(T25)
    reach = itin.Reach(scene, ELIAS, journeys=itin.journeys(scene, T25["span"]["from_s"]))
    named = _named(T25, ELIAS, reach)
    as_run = T25["minds"][ELIAS]["log_as_run"]
    for row in as_run:
        stretch = itin._stretch_under(T25["minds"][ELIAS]["itinerary"], row)
        assert reach.missing(stretch["uses"], named, row["room"], row["away"],
                             row["from_s"]) == row["missing"], row["doing"][:40]
    assert sum("paraffin" in r["missing"] for r in as_run) == 6
    assert sum(any("small tools" in m for m in r["missing"]) for r in as_run) == 6


def _assert_the_picks_reproduce_the_boatmans_live_logs():
    """Off the map, the boatman's live `missing` is what the reach now gives
    plus the words that named only things no body carries -- the crates (the
    pile of stores on the rock's steps), the lighthouse kitchen's table and,
    since fix lane B5 (the owner's ruling of 2026-10-22: a vessel is never
    missing), the Mary Ann."""
    immovable = {"crates", "kitchen table", "the Mary Ann"}
    for turn in (T25, T26):
        scene = _scene(turn)
        reach = itin.Reach(scene, PELL, journeys=itin.journeys(scene, turn["span"]["from_s"]))
        named = _named(turn, PELL, reach)
        stretches = turn["minds"][PELL]["itinerary"]
        for row in turn["minds"][PELL]["log_as_run"]:
            if row["reason"] != itin.REASON_NOT_HELD:
                continue
            stretch = itin._stretch_under(stretches, row)     # a ride adds a landed row
            now = reach.missing(stretch["uses"], named, row["room"], row["away"], row["from_s"])
            assert [m for m in row["missing"] if m not in immovable] == now
    assert ["crates" in r["missing"] for r in T25["minds"][PELL]["log_as_run"]].count(True) == 1
    assert "kitchen table" in T26["minds"][PELL]["log_as_run"][0]["missing"]


# --------------------------------------------------------------------------
# 1. A thing is to hand when the mind can get it inside the stretch
# --------------------------------------------------------------------------

def test_paraffin_two_flights_down_is_to_hand_for_the_lamp_stretches():
    """The paraffin crate lies in the hall, two flights below the lamp room:
    the keeper walks down for it and back up inside every lamp stretch. No
    row fails for paraffin -- five are no longer failed at all -- and the
    one that also wanted the small tools names those alone. Each such row
    begins when he is back up with it, the round trip's seconds after its
    stretch. Live, six rows failed for it, and what the story made of it is
    on record: his memories of the stretch said "there was none in the
    stores", and the next beat's narration "The paraffin's spent"."""
    _assert_the_picks_reproduce_the_keepers_live_log()
    memories = " ".join(m["content"] for m in T25["memories_as_written"][ELIAS])
    assert "none in the stores" in memories
    assert "The paraffin's spent" in T26["narration_as_written"]
    assert _scene(T25)["positions"][PARAFFIN] == "tower_hall"
    log, far = _live(T25, ELIAS)
    as_run = T25["minds"][ELIAS]["log_as_run"]
    scene = _scene(T25)
    trip = _trip(scene, T25, "lamp_room", "tower_hall")
    assert 0 < trip < 120
    assert not any("paraffin" in row["missing"] for row in log)
    for row, live in zip(log, as_run):
        if "paraffin" not in live["missing"]:
            continue
        assert row["from_s"] == pytest.approx(live["from_s"] + trip), row["doing"][:40]
        if live["missing"] == ["paraffin"]:
            assert (row["outcome"], row["reason"], row["missing"]) == ("done", None, [])
        else:
            assert (row["reason"], row["missing"]) == (itin.REASON_NOT_HELD, ["small tools"])
    assert sum(1 for r in log if r["outcome"] == "failed") == 6
    assert sum(1 for r in as_run if r["outcome"] == "failed") == 11 - 4   # 4 judged live
    assert far["room"] == T25["minds"][ELIAS]["far_end_as_run"]["room"]


def test_a_fetch_takes_its_time_out_of_the_stretch_and_must_fit_inside_it():
    """A fetch is priced as a walk is, out of the stretch's start, and only
    a thing the mind can be back with before the stretch ends is to hand: a
    stretch shorter than the round trip to the hall still goes without the
    paraffin, and begins where it began."""
    scene = _scene(T25)
    trip = _trip(scene, T25, "lamp_room", "tower_hall")
    lighting = dict(T25["minds"][ELIAS]["itinerary"][1], uses=["paraffin"])
    start = lighting["from_s"]
    for length, fetched in ((trip + 1.0, True), (trip - 0.01, False), (trip / 2, False)):
        stretch = dict(lighting, until_s=start + length)
        log, _far = _live(T25, ELIAS, stretches=[stretch])
        if fetched:
            assert (log[0]["from_s"], log[0]["missing"]) == (pytest.approx(start + trip), [])
        else:
            assert (log[0]["from_s"], log[0]["missing"]) == (start, ["paraffin"])
    # Things in two rooms: each room walked to and back once, nearest first,
    # for as long as the trips leave the mind back in time.
    reach = itin.Reach(scene, ELIAS, ways=_ways(T25, scene))
    named = {"paraffin": {PARAFFIN}, "the mug": {"212ebdfa639b4608"}}   # in the kitchen
    kitchen = _trip(scene, T25, "lamp_room", "kitchen")
    assert reach.fetch(["paraffin", "the mug"], named, "lamp_room", t=start,
                       until=start + 3600.0) == (["the mug", "paraffin"], kitchen + trip)
    assert reach.fetch(["paraffin", "the mug"], named, "lamp_room", t=start,
                       until=start + kitchen + 1.0) == (["the mug"], kitchen)


def test_tools_on_another_body_are_never_fetched():
    """The clockmaker's toolkit is carried by the player, who stands in the
    hall the keeper walks to for the paraffin: it is hers, never fetched, so
    his stretches that meant to use "the small tools" still go without them
    -- and the decision model's no keeps the mechanism work failed."""
    scene = _scene(T25)
    assert scene["contained"][TOOLKIT]["in"] == RHONA
    assert scene["positions"][TOOLKIT] == "tower_hall" == scene["positions"][RHONA]
    reach = itin.Reach(scene, ELIAS, ways=_ways(T25, scene))
    named = {"small tools": {TOOLKIT}}
    assert reach.fetch(["small tools"], named, "lamp_room", t=T25["span"]["from_s"],
                       until=T25["span"]["until_s"]) == ([], 0.0)
    log, _far = _live(T25, ELIAS)
    _judge(log, ELIAS)
    tools = [r for r in log if any("small tools" in m for m in r["missing"])]
    assert len(tools) == 6
    work = next(r for r in log if r["doing"].startswith("working on the mechanism"))
    assert (work["outcome"], work["reason"], work["missing"]) == \
        ("failed", "not_held", ["small tools"])
    # In her own reach it is carried.
    assert itin.Reach(scene, RHONA).missing(["small tools"], named, "lamp_room") == []


def test_the_letter_across_the_water_stays_missing():
    """The sealed letter lies in the hall on the rock. From the mainland's
    stub the only way there is across the channel and the frontier's join,
    so it is never fetched; off the map nothing is -- the world holds no way
    from a place it does not hold. The boatman's post office still fails
    `not_held` for it, twice, and the decision model's no keeps it failed."""
    scene = _scene(T25)
    ways = _ways(T25, scene)
    assert ways.route("the_mainland", "tower_hall")[0] is None
    reach = itin.Reach(scene, PELL, ways=ways)
    named = {"the letter": {LETTER}}
    span = T25["span"]
    assert reach.fetch(["the letter"], named, "the_mainland", t=span["from_s"],
                       until=span["until_s"]) == ([], 0.0)
    assert reach.fetch(["the letter"], named, None, "the quay", t=span["from_s"],
                       until=span["until_s"]) == ([], 0.0)
    log, _far = _live(T25, PELL)
    _judge(log, PELL)
    posting = [r for r in log if r["doing"].startswith("Walks the letter up")]
    assert len(posting) == 2
    for row in posting:
        assert (row["outcome"], row["reason"], row["missing"]) == \
            ("failed", "not_held", ["Rhona Carrick's sealed letter"])
    # Turn 26, at home on the mainland: the same letter, the same want.
    log26, _far = _live(T26, PELL)
    assert [r["missing"] for r in log26] == [["Rhona Carrick's sealed letter"]] * 2


def test_a_thing_no_body_carries_is_never_fetched():
    """A fixture is used where it stands and a thing too big to carry is
    gone to, never fetched -- and, since fix lane B5 (the owner's ruling of
    2026-10-22: a stretch fails its holding check only on positive evidence,
    and only a thing a body can carry is ever missing), never missing
    either: from the kitchen the lamp and the pedestal are not. Read as the
    pile of stores on the steps -- cargo, not portable -- "paraffin" is
    neither fetched nor missing; the fourth live replay read it so, and the
    keeper's lamp failed for it
    (`tests/test_a_skip_fails_only_on_positive_evidence.py`)."""
    scene = _scene(T25)
    reach = itin.Reach(scene, ELIAS, ways=_ways(T25, scene))
    named = {"the lamp": {LAMP}, "the pedestal": {PEDESTAL}, "paraffin": {PILE}}
    span = T25["span"]
    assert not any(reach.in_reach(k, "kitchen") for keys in named.values() for k in keys)
    assert reach.missing(list(named), named, "kitchen") == []
    assert reach.fetch(list(named), named, "kitchen", t=span["from_s"],
                       until=span["until_s"]) == ([], 0.0)
    assert scene["entities"][PILE]["portable"] is False


def test_the_towns_rows_fetch_as_the_stages_own_do():
    """`lay_over`, the holding check over the town charter's rows, fetches
    by the same rule and takes the trip out of the row's start."""
    scene = _scene(T25)
    reach = itin.Reach(scene, ELIAS, ways=_ways(T25, scene))
    holding = itin.Holding(reach, {"paraffin": {PARAFFIN}, "small tools": {TOOLKIT}})
    stretch = dict(T25["minds"][ELIAS]["itinerary"][1], uses=["paraffin", "small tools"])
    row = {"from_s": stretch["from_s"], "until_s": stretch["until_s"], "room": "lamp_room",
           "away": None, "where_text": "The Lamp Room", "doing": stretch["doing"],
           "asleep": False, "seen": [], "weather": None, "outcome": "done", "reason": None}
    log = itin.lay_over([row], [stretch], missing_from=holding, fetch_from=holding.fetch)
    trip = _trip(scene, T25, "lamp_room", "tower_hall")
    assert (log[0]["outcome"], log[0]["reason"], log[0]["missing"]) == \
        ("failed", "not_held", ["small tools"])
    assert log[0]["from_s"] == pytest.approx(stretch["from_s"] + trip)


# --------------------------------------------------------------------------
# 2. Off the map, only a thing that could have been brought is missing
# --------------------------------------------------------------------------

def test_an_off_map_stretchs_foreign_fixture_is_never_missing():
    """At home on the mainland the boatman's "kitchen table" is no table the
    world holds there: the lighthouse kitchen's table is a fixture of a room
    the world holds, and was never going to be on the mainland. It is never
    missing; the letter -- a thing he could have carried -- is. On the quay
    the crates (the pile of stores, cargo nobody carries) are never missing
    either, while the post bag (portable) could have been there and was not.
    The Mary Ann, a vessel, is boarded where she lies and is never missing
    (fix lane B5, the owner's ruling of 2026-10-22; B4 read a moving kind as
    a thing that could have been brought)."""
    _assert_the_picks_reproduce_the_boatmans_live_logs()
    scene = _scene(T26)
    reach = itin.Reach(scene, PELL)
    named = {"kitchen table": {KITCHEN_TABLE}, "the letter": {LETTER},
             "the fire": set(), "oilskin jacket": set()}
    assert reach.missing(list(named), named, None, "home") == ["the letter"]
    # From the next room the table is not to hand, and still never missing:
    # a fixture is used where it stands (fix lane B5).
    assert not reach.in_reach(KITCHEN_TABLE, "bedroom_elias")
    assert reach.missing(["kitchen table"], named, "bedroom_elias") == []
    log, _far = _live(T26, PELL)
    assert log[0]["missing"] == ["Rhona Carrick's sealed letter"]
    assert T26["minds"][PELL]["log_as_run"][0]["missing"] == \
        ["Rhona Carrick's sealed letter", "kitchen table"]
    scene = _scene(T25)
    under_way = itin.journeys(scene, T25["span"]["from_s"])
    reach = itin.Reach(scene, PELL, journeys=under_way)
    named = {"the Mary Ann": {MARY_ANN}, "crates": {PILE}, "the post bag": {POST_BAG}}
    day1 = 141300.0
    assert reach.missing(list(named), named, None, "the quay, aboard the Mary Ann", day1) == \
        ["the post bag"]
    log, _far = _live(T25, PELL)
    loading = next(r for r in log if r["doing"].startswith("Loads the Tuesday run"))
    assert loading["missing"] == ["the post bag"]


def test_a_thing_inside_a_thing_a_body_can_carry_can_be_missing_off_the_map():
    """The can-carry test (`Reach.can_carry`) follows a thing to what holds
    it: a thing whose own record does not say a body carries it, stowed in
    the post bag, goes where a body carries the bag and can be missing off
    the map; a thing inside the pile of stores, which nobody carries, is
    portable on its own record and can be too. Stowed in the Mary Ann, a
    thing that is not portable itself is never missing: a vessel is no thing
    a body carries (fix lane B5, the owner's ruling of 2026-10-22; B4 read a
    moving kind as one that could have been brought)."""
    scene = _scene(T25)
    scene["entities"][LETTER]["portable"] = False
    scene["contained"][LETTER] = {"in": POST_BAG, "mode": "stowed"}
    reach = itin.Reach(scene, PELL)
    assert reach.can_carry(LETTER) and reach.can_carry(POST_BAG)
    assert reach.missing(["the letter"], {"the letter": {LETTER}}, None, "home") == ["the letter"]
    assert not any(reach.can_carry(k) for k in (PILE, KITCHEN_TABLE, MARY_ANN))
    scene = _scene(T25)
    scene["entities"][POST_BAG]["portable"] = False
    scene["contained"][POST_BAG] = {"in": MARY_ANN, "mode": "stowed"}
    scene["contained"][LETTER] = {"in": PILE, "mode": "stowed"}
    reach = itin.Reach(scene, PELL)
    assert not reach.can_carry(POST_BAG)
    assert reach.missing(["the post bag"], {"the post bag": {POST_BAG}}, None, "home") == []
    assert reach.can_carry(LETTER)
    assert reach.missing(["the letter"], {"the letter": {LETTER}}, None, "home") == ["the letter"]


# --------------------------------------------------------------------------
# The stage, end to end
# --------------------------------------------------------------------------

def _turn25_chat(temp_db):
    """The lighthouse before turn 25 (checkpoint 8): its world, its clock,
    the frontier the plan holds open, and the keeper and the boatman as
    active cast where the scene stands them."""
    import time
    from core.db import qi, wset
    from story.character_schema import default_character_data
    now = time.time()
    chat = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
              ("The Lamp Room", "", now))
    for name in (ELIAS, PELL):
        cid = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                 "VALUES(?,?,?,?,?)", (name, json.dumps(default_character_data(name)),
                                       "{}", now, "uid_" + name.split()[0].casefold()))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
           (chat, cid, "active", "{}"))
    for stub, spec in T25["provisional"].items():
        qi("INSERT INTO room_registry(chat_id,room_uid,name,payload) VALUES(?,?,?,?)",
           (chat, stub, "The Mainland", json.dumps({"planned": {
               "name": "The Mainland", "provisional": True,
               "frontier_of": spec["frontier_of"]}})))
    wset(chat, "scene", _scene(T25))
    wset(chat, "simulation_clock", {k: T25["clock"][k] for k in (
        "elapsed_seconds", "anchor_hour", "day_length_hours")})
    turn = qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (chat, 8, T25["input"], now))
    return chat, turn


def test_the_stage_fetches_and_its_record_no_longer_loses_the_paraffin(temp_db, monkeypatch):
    """The whole stage on turn 25's world and recorded answers, the decision
    model stubbed with the picks and its live `without` answers: the keeper's
    holding check fetches over the stage's own ways, no row of his is short
    of paraffin, and the record his memories are written from says none of
    his lamp work failed for it -- where the live record said "It did not
    come off, for want of paraffin" five times."""
    from agents import skip_stage
    from core.db import q
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from llm import decisions
    from mind import skip_memories as sm
    from story.scene import active_cast
    chat, turn = _turn25_chat(temp_db)
    answers = {name: T25["minds"][name]["answer"] for name in (ELIAS, PELL)}
    rooms = {name: {s["where_text"]: s["room"] for s in T25["minds"][name]["itinerary"]}
             for name in (ELIAS, PELL)}
    monkeypatch.setattr(skip_stage, "ask", lambda ctx, row, span, nonce=0: (
        copy.deepcopy(answers[skip_stage._row_name(row)]), None))
    scene_rooms, entities = T25["scene"]["rooms"], T25["scene"]["entities"]

    def decide(state, questions):
        out = {}
        for key, question in questions.items():
            words = question["instructions"]
            if key.startswith("without:"):
                yes = next((p for start, p in WITHOUT.items() if f'"{start}' in words), None)
                if yes is not None:
                    out[key] = {"type": "noul", "noul": yes}
                continue
            pick, mind = None, state.get("mind")
            if key.startswith("place:"):
                for where, room in rooms[mind].items():
                    if room and f'"{where}"' in words:
                        name = scene_rooms[room]["name"]
                        pick = next((k for k, v in question["criteria"].items()
                                     if v == name or str(v).startswith(name + " (")), None)
            elif key.startswith("thing:"):
                for thing, key_ in PICKS[mind].items():
                    if f'"{thing}"' in words and key_ in entities:
                        name = entities[key_]["name"]
                        pick = next((k for k, v in question["criteria"].items()
                                     if v == name or str(v).startswith(name + " (")), None)
            pick = pick or "none"
            out[key] = {"type": "choice", "choice": pick, "probabilities": {pick: 0.9}}
        return out

    monkeypatch.setattr(decisions, "OVERRIDE", decide)
    ctx = PipelineContext(
        chat=ChatData.from_row(q("SELECT * FROM chats WHERE id=?", (chat,), one=True)),
        turn=TurnData.from_row(q("SELECT * FROM turns WHERE id=?", (turn,), one=True)),
        cast=active_cast(chat), input=T25["input"])
    block = {"days": 2, "until_phase": "morning",
             "duration_seconds": T25["span"]["until_s"] - T25["span"]["from_s"]}
    ctx.director_interpret = {
        "state_assertions": {"time": dict(block), "causal_steps": [
            {"chrono_id": 1, "stage": "interpret", "patch": {"time": dict(block)}}]},
        "causal_ledger": [{"chrono_id": 1, "seconds": 0.0, "commitment": "asserted"}],
        "flow": {"reactors": [], "tom_triggers": []}, "authorial_offers": []}
    out = skip_stage.skip_lives(ctx, 0)
    elias = out["minds"][ELIAS]["log"]
    assert len(elias) == len(T25["minds"][ELIAS]["log_as_run"])
    assert not any("paraffin" in r["missing"] for r in elias)
    lamp = [r for r in elias if r["doing"].startswith(("lighting the lamp", "first night watch",
                                                       "checking the lamp — trimming",
                                                       "night watch — scanning"))]
    assert len(lamp) == 5 and all(r["outcome"] == "done" for r in lamp)
    record = sm.record_rows(elias, span_from=T25["span"]["from_s"], anchor=15.75,
                            length=24.0, name=ELIAS)
    told = " ".join(r.get("how_it_went") or "" for r in record)
    assert "paraffin" not in told and "small tools" in told
    pell = out["minds"][PELL]["log"]
    posting = [r for r in pell if r["doing"].startswith("Walks the letter up")]
    assert [(r["outcome"], r["missing"]) for r in posting] == \
        [("failed", ["Rhona Carrick's sealed letter"])] * 2


# --------------------------------------------------------------------------
# 3. A routine holds only what repeats every day
# --------------------------------------------------------------------------

def _assert_a_one_off_in_the_routine_is_lived_on_every_day():
    """Why the card must say it: the boatman's day-0 crossing and his
    errand to post the letter were routine entries, and the itinerary lays
    a routine over every day of the span -- so both ran on day 1 again and
    failed again (`no_crossing`, `not_held`). The same entries in his plan,
    each on its day, are lived once."""
    clock = T25["clock"]
    hour0 = (clock["anchor_hour"] + T25["span"]["from_s"] / 3600.0) % 24.0
    span = itin.Span(T25["span"]["from_s"], T25["span"]["until_s"], hour0, 24.0)
    answer = copy.deepcopy(T25["minds"][PELL]["answer"])
    crossing = " ".join(answer["routine"][0]["doing"].split())
    posting = " ".join(answer["routine"][1]["doing"].split())
    laid = itin.expand_itinerary(answer, span)
    assert sum(s["doing"] == crossing for s in laid) == 2
    assert sum(s["doing"] == posting for s in laid) == 2
    as_run = T25["minds"][PELL]["log_as_run"]
    assert [r["reason"] for r in as_run if r["doing"] == posting] == ["not_held"] * 2
    assert [r["reason"] for r in as_run if r["doing"] == crossing] == [None, "no_crossing"]
    once = copy.deepcopy(answer)
    once["plan"] = [dict(e, day=0) for e in once["routine"][:2]] + once["plan"]
    once["routine"] = once["routine"][2:]
    laid = itin.expand_itinerary(once, span)
    assert sum(s["doing"] == crossing for s in laid) == 1
    assert sum(s["doing"] == posting for s in laid) == 1


def _routine_paragraph(card):
    """The card's paragraph that says what `routine` and `plan` are."""
    return next(line for line in card.split("\n") if line.startswith("`routine`"))


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_card_says_a_routine_holds_only_what_repeats_every_day(language):
    """The card says what a routine is FOR -- it is lived again on every day
    of the stretch, so it holds only what is done on every one of them --
    and that what is done once goes in `plan`. The class, with no instance:
    no person, place, thing or errand of any story."""
    _assert_a_one_off_in_the_routine_is_lived_on_every_day()
    from llm.prompts import get_prompt
    card = get_prompt("character_skip", language=language)
    line = _routine_paragraph(card)
    routine, _sep, plan = line.partition("`plan`")
    assert "`plan`" in line and "`routine`" in plan
    if language == "en":
        assert "lived again on every day of the stretch" in routine
        assert "only what you do on every one of those days" in routine
        assert "whatever you do once goes there, never in `routine`" in plan
    else:
        assert "毎日" in routine and "そのどの日にもすることだけ" in routine
        assert "一度きりのことはここに入れ、`routine`には入れません" in plan
    for instance in ("Pell", "Elias", "Rhona", "Mary Ann", "letter", "post", "boat",
                     "crossing", "手紙", "船"):
        assert instance not in card, instance
