"""A skip's stretch fails only on positive evidence (`world/skip_itinerary.py`'s
`Reach.missing`, `Reach.can_carry`, `answered`, `judge_without` and
`live_through`, `agents/skip_stage.py`'s `resolve_mind` and
`judge_what_was_missing`).

THE LIVE EVIDENCE is the lighthouse replayed a FOURTH time, on 26b50870
(chat 3, decision capture on): turn 25 (idx 8, "Two days later the wind gets
up from the west ...") and turn 26 (idx 9, "That night, when Elias comes
down from the first watch ..."). Each turn's world before it, every mind's
answer, itinerary, log as run and far end, the decision model's own answers
(`decided`: places, things and `without` verdicts, from the capture), the
memories the job wrote and turn 26's narration are
`tests/data/skip_live_lighthouse_4.json`. A FALSE FAILURE BECOMES A STORY
FACT, and the fetch of fix lane B4 had landed, yet:

  1. A STORE TOO BIG TO CARRY. The decision model read the keeper's
     "paraffin" as the pile of stores on the steps (cargo, not portable, "a
     sloshing drum of paraffin" in its description), which is never fetched,
     so his lamp work failed `not_held` on five rows and his memory said "The
     lamp went dark on my watch for want of paraffin I should have had at
     hand". A turn later his tea failed for want of the "wood stove", read as
     the hall's stove while he stood in the kitchen beside its range.
  2. A VESSEL NAMED OFF THE MAP. The boatman's day at "the harbour" resolved
     off the map while the Mary Ann lay docked at the room `the_mainland`, so
     every stretch that named her failed "for want of the Mary Ann" -- his
     dinner among them -- and his memories read as a failure log.
  3. NO ANSWER WAS A FAILURE. A `without` question the decision model does
     not answer left its row failed.
  4. `left_from` AFTER A RIDE. His whereabouts kept `the_channel`, the
     journey's route room, though the ride ended at the mainland.

What must still fail: the letter that lies on the rock, for a post office on
the mainland; the tools in the player's hands, by the judgement; and every
crossing a body cannot make.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from world import skip_itinerary as itin

ROOT = Path(__file__).resolve().parent.parent
LIVE = json.loads((ROOT / "tests" / "data" / "skip_live_lighthouse_4.json")
                  .read_text(encoding="utf-8"))["turns"]
T25, T26 = LIVE["25"], LIVE["26"]

ELIAS, PELL, RHONA = "Elias Thorne", "Pell Hardacre", "Rhona Carrick"

TOOLKIT = "0bcb2b599f134f41"        # "clockmaker's toolkit", carried by Rhona
PILE = "7041a08392c14695"           # "a pile of stores" (cargo, not portable), on the steps
PARAFFIN_CRATE = "bc6c40aab847432d"  # "paraffin crate" (portable), in the hall
LAMP = "2275c0d8a81c43d2"           # "the tower lamp" (not portable), in the lamp room
LETTER = "4b92b2b8653b43d4"         # "a sealed letter", in the hall on the rock
POST_BAG = "b86503d36fb94aa2"       # "the post bag", in the hall
MARY_ANN = "fe01eaf0eb204899"       # "The Mary Ann", under way to the mainland
HALL_STOVE = itin.FIXTURE_PREFIX + "tower_hall:stove"
KITCHEN_RANGE = itin.FIXTURE_PREFIX + "kitchen:range"


def _scene(turn):
    return copy.deepcopy(turn["scene"])


def _stubs(turn):
    return {stub: spec["frontier_of"]["room"] for stub, spec in turn["provisional"].items()}


def _ways(turn, scene):
    return itin.Ways(scene, joins=itin.frontier_joins(_stubs(turn)))


def _picks(turn, name):
    """`{words: key}` -- the things the live decision model read the mind's
    words as (`decided.things`, from the run's capture)."""
    return {words: pick["key"] for words, pick in turn["minds"][name]["decided"]["things"].items()
            if pick["key"]}


def _named(turn, name, reach, stretches=None):
    named = {}
    picks = _picks(turn, name)
    for stretch in stretches if stretches is not None else turn["minds"][name]["itinerary"]:
        for thing in stretch.get("uses") or ():
            named[thing] = reach.named(thing) or ({picks[thing]} if thing in picks else set())
    return named


def _start(turn, name, scene):
    """Where the mind stands as the stretch opens, as the stage reads it."""
    here = scene["positions"].get(name)
    record = (turn.get("whereabouts") or {}).get(name) or {}
    away = None if here else (record.get("label") or None)
    return here, away, record.get("left_from")


def _live(turn, name, stretches=None, scene=None):
    """The executor over one mind's itinerary, as the stage runs it: its
    holding check (`Holding`) reading the live picks, fetching over the ways
    a body walks."""
    scene = scene or _scene(turn)
    stretches = copy.deepcopy(stretches if stretches is not None
                              else turn["minds"][name]["itinerary"])
    ways = _ways(turn, scene)
    under_way = itin.journeys(scene, turn["span"]["from_s"])
    here, away, left = _start(turn, name, scene)
    reach = itin.Reach(scene, name, journeys=under_way, ways=ways)
    holding = itin.Holding(reach, _named(turn, name, reach, stretches))
    log, far = itin.live_through(
        stretches, scene=scene, start_room=here, start_away=away, start_exit=left,
        ways=ways, missing_from=holding, fetch_from=holding.fetch,
        journey=itin.journey_under_way(scene, here, under_way, ways))
    return itin.place_words(log, scene), far


def _verdict(turn, name, doing):
    """The live decision model's answer to "can {name} do '{doing}' without
    ...?" for the row of this doing, or None where it was never asked."""
    return next((w["noul"] for w in turn["minds"][name]["decided"]["without"]
                 if w["doing"] == doing), None)


def _answers(turn, name, log):
    """`without_questions` over `log`, answered with the live verdicts by
    each row's doing; a row the live run never asked about gets no answer."""
    out = {}
    for key in itin.without_questions(name, log):
        noul = _verdict(turn, name, log[int(key.split(":")[1])]["doing"])
        if noul is not None:
            out[key] = {"type": "noul", "noul": noul}
    return out


def _failed(log):
    return [i for i, row in enumerate(log) if row["outcome"] == itin.OUTCOME_FAILED]


# --------------------------------------------------------------------------
# 1. Only a thing a body can carry is ever missing
# --------------------------------------------------------------------------

def test_paraffin_read_as_a_store_never_fails_a_lamp_row():
    """The decision model read "paraffin" as the pile of stores on the steps
    (cargo, `portable: false`). The keeper goes to a store and draws from it
    where it stands; whether he can be there is his stretch's place. No row
    fails for paraffin: the four that failed for it alone are `done`, and the
    one that also wanted the lamp tools names those alone. Live, five rows
    failed for it and his memory kept it as the one failure "with no
    restitution"."""
    picks = _picks(T25, ELIAS)
    assert picks["paraffin"] == PILE
    pile = T25["scene"]["entities"][PILE]
    assert (pile["portable"], pile["kind"]) == (False, "cargo")
    assert "paraffin" in pile["description"]
    as_run = T25["minds"][ELIAS]["log_as_run"]
    for_paraffin = [i for i, r in enumerate(as_run) if "paraffin" in r["missing"]]
    assert for_paraffin == [1, 2, 6, 7, 9]
    assert all(as_run[i]["reason"] == itin.REASON_NOT_HELD for i in for_paraffin)
    memories = " ".join(m["content"] for m in T25["memories_as_written"][ELIAS])
    assert "for want of paraffin" in memories
    log, far = _live(T25, ELIAS)
    assert len(log) == len(as_run)
    assert not any("paraffin" in row["missing"] for row in log)
    for i in for_paraffin:
        row, live = log[i], as_run[i]
        assert row["from_s"] == live["from_s"], row["doing"][:40]  # nothing fetched, nothing priced
        if live["missing"] == ["paraffin"]:
            assert (row["outcome"], row["reason"], row["missing"]) == ("done", None, [])
        else:
            assert (row["reason"], row["missing"]) == (itin.REASON_NOT_HELD, ["lamp tools"])
    assert far["room"] == "lamp_room"


def test_a_fixture_another_room_holds_never_fails_a_stretch():
    """A turn later the keeper's tea in the kitchen named a "wood stove", and
    the decision model read it as the hall's stove: a fixture is used where
    it stands, so the tea fails for nothing -- it is `not_known` only for
    the player it is had with (`with`). Live, it failed `not_held`."""
    assert _picks(T26, ELIAS)["wood stove"] == HALL_STOVE
    as_run = T26["minds"][ELIAS]["log_as_run"]
    assert (as_run[4]["room"], as_run[4]["reason"], as_run[4]["missing"]) == \
        ("kitchen", itin.REASON_NOT_HELD, ["wood stove"])
    log, _far = _live(T26, ELIAS)
    tea = log[4]
    assert tea["doing"].startswith("Comes down the tower stair into the kitchen")
    assert T26["minds"][ELIAS]["itinerary"][4]["with"] == [RHONA]
    assert (tea["outcome"], tea["reason"], tea["missing"]) == \
        (itin.OUTCOME_NOT_KNOWN, None, [])


def test_what_no_body_carries_is_never_missing_on_the_map_or_off_it():
    """The rule in the engine's terms: a fixture, a thing too big to carry
    and a vessel never fail the holding check -- from another room, off the
    map, or with the vessel on the far side of the water. A thing a body can
    carry (`portable`, or carried by a body now, or inside such a thing) is
    missing where the world holds it out of reach."""
    scene = _scene(T25)
    under_way = itin.journeys(scene, T25["span"]["from_s"])
    reach = itin.Reach(scene, ELIAS, journeys=under_way)
    never = {"paraffin": {PILE}, "the lamp": {LAMP}, "the stove": {HALL_STOVE},
             "the range": {KITCHEN_RANGE}, "the Mary Ann": {MARY_ANN}}
    for room, away in (("kitchen", None), ("rock_landing", None), (None, "the harbour")):
        assert reach.missing(list(never), never, room, away, T25["span"]["from_s"]) == [], room
    assert not any(reach.can_carry(k) for k in (PILE, LAMP, HALL_STOVE, MARY_ANN))
    carried = {"the crate": {PARAFFIN_CRATE}, "the letter": {LETTER},
               "the kit roll": {TOOLKIT}}
    assert all(reach.can_carry(k) for keys in carried.values() for k in keys)
    assert reach.missing(list(carried), carried, None, "the harbour") == list(carried)
    # A thing a body carries now is one a body can carry, whatever its flag.
    scene["entities"][TOOLKIT]["portable"] = False
    assert itin.Reach(scene, ELIAS).can_carry(TOOLKIT)
    # Words that may name a store or a crate are never missing: one reading
    # of them is used where it stands.
    both = {"paraffin": {PILE, PARAFFIN_CRATE}}
    assert reach.missing(["paraffin"], both, None, "the harbour") == []
    # A thing a body can carry that the world places nowhere -- no room, no
    # body, no vessel -- is not held out of reach: nothing shows it missing.
    scene["entities"]["spare_wick"] = {"name": "a spare wick", "kind": "object",
                                       "portable": True}
    reach = itin.Reach(scene, ELIAS)
    assert reach.can_carry("spare_wick") and not reach.held_somewhere("spare_wick")
    assert reach.missing(["a spare wick"], {"a spare wick": {"spare_wick"}}, "kitchen") == []


# --------------------------------------------------------------------------
# 2. A vessel named off the map is a matter of place
# --------------------------------------------------------------------------

def test_the_mary_ann_named_off_the_map_is_never_missing():
    """The boatman's day at "the harbour" was read as no place the world
    holds while the Mary Ann docked at the mainland: every stretch that named
    her failed "for want of the Mary Ann". A vessel is boarded or worked
    where it lies, never carried: none of them fails for her, and a stretch
    at a place off the map nobody simulates is `not_known`."""
    assert T25["minds"][PELL]["decided"]["places"]["the harbour"]["room"] is None
    as_run = T25["minds"][PELL]["log_as_run"]
    for_her = [i for i, r in enumerate(as_run) if r["missing"] == ["the Mary Ann"]]
    assert for_her == [0, 1, 3, 5, 7, 10]
    log, _far = _live(T25, PELL)
    assert len(log) == len(as_run)
    assert not any("the Mary Ann" in row["missing"] for row in log)
    for i in for_her:
        assert (log[i]["away"], log[i]["outcome"], log[i]["reason"]) == \
            ("the harbour", itin.OUTCOME_NOT_KNOWN, None), log[i]["doing"][:40]
    assert itin.short_of(log) == []
    log26, _far = _live(T26, PELL)
    assert not any("the Mary Ann" in row["missing"] for row in log26)


def test_dinner_never_fails_for_want_of_a_boat():
    """Turn 26: "Sit down to a proper dinner at the lodging ... and then back
    down to the Mary Ann" failed `not_held` for want of her, and the
    decision model's no (0.09) kept it failed. It is never asked now: there
    is nothing it went without."""
    as_run = T26["minds"][PELL]["log_as_run"]
    assert as_run[1]["doing"].startswith("Sit down to a proper dinner")
    assert (as_run[1]["reason"], as_run[1]["missing"]) == (itin.REASON_NOT_HELD, ["the Mary Ann"])
    assert _verdict(T26, PELL, as_run[1]["doing"]) == 0.09
    log, _far = _live(T26, PELL)
    dinner = log[1]
    assert (dinner["outcome"], dinner["reason"], dinner["missing"]) == \
        (itin.OUTCOME_NOT_KNOWN, None, [])
    assert 1 not in itin.short_of(log)


# --------------------------------------------------------------------------
# 3. No answer never invents a failure
# --------------------------------------------------------------------------

def test_no_answer_from_the_judgement_is_not_known_never_failed():
    """A row a thing not to hand failed, which the decision model does not
    answer about -- no entry, an unreadable one, or no request at all -- is
    told as far as it went: `not_known`, `missing` kept, no reason. Only a
    no keeps it failed."""
    log, _far = _live(T26, ELIAS)
    short = itin.short_of(log)
    assert short == [0, 1]
    unanswered = copy.deepcopy(log)
    assert itin.judge_without(unanswered, {}) == short
    for i in short:
        assert (unanswered[i]["outcome"], unanswered[i]["reason"], unanswered[i]["missing"]) == \
            (itin.OUTCOME_NOT_KNOWN, None, log[i]["missing"])
    unreadable = copy.deepcopy(log)
    assert itin.judge_without(unreadable, {"without:0": {"type": "noul"},
                                           "without:1": {"error": "timeout"}}) == short
    said_no = copy.deepcopy(log)
    assert itin.judge_without(said_no, {"without:0": {"type": "noul", "noul": 0.24},
                                        "without:1": {"type": "noul", "noul": 0.09}}) == []
    assert [said_no[i]["outcome"] for i in short] == [itin.OUTCOME_FAILED] * 2
    assert not itin.answered(None) and not itin.answered({"type": "noul"})
    assert itin.answered({"type": "noul", "noul": 0.0})
    assert itin.answered({"type": "choice", "choice": itin.NONE_OPTION})


def test_a_request_that_fails_leaves_the_rows_not_known(monkeypatch):
    """The stage's one request per mind over its short rows: where it fails
    outright, every row it would have asked about is `not_known`, and the
    record says why."""
    from agents import skip_stage
    from llm import decisions

    def down(state, questions):
        raise decisions.DecisionError("jev down")

    monkeypatch.setattr(decisions, "OVERRIDE", down)
    log, _far = _live(T26, ELIAS)
    record = skip_stage.judge_what_was_missing(ELIAS, log)
    assert "jev_failed" in record and record["without"] == [0, 1]
    assert [log[i]["outcome"] for i in (0, 1)] == [itin.OUTCOME_NOT_KNOWN] * 2
    assert _failed(log) == []


def test_a_place_left_unanswered_never_fails_a_crossing():
    """Beside the Mary Ann in the channel, bound for the mainland, a stretch
    the journey still carries him through names a place: read as no place
    the world holds, it is a way out of the water he cannot make (`too_far`,
    as before); never answered, it invents nothing -- he rides on where the
    journey carries him, `not_known`, the words kept in `meant`. Where an
    unanswered place leads off ordinary ground, the mind still goes there."""
    scene = _scene(T25)
    span_from = T25["span"]["from_s"]
    journey = itin.journeys(scene, span_from)[MARY_ANN]
    assert scene["positions"][PELL] == "the_channel" == journey["route"]
    stretch = {"from_s": span_from, "until_s": journey["until_s"] - 600.0, "room": None,
               "away": "the harbour mouth", "where_text": "the harbour mouth",
               "doing": "Keeps her head to the swell", "asleep": False, "with": [],
               "why": "", "uses": []}
    answered_none, _far = _live(T25, PELL, stretches=[stretch])
    assert (answered_none[0]["outcome"], answered_none[0]["reason"]) == \
        (itin.OUTCOME_FAILED, itin.REASON_TOO_FAR)
    log, _far = _live(T25, PELL, stretches=[dict(stretch, unplaced=True)])
    row = log[0]
    assert (row["outcome"], row["reason"], row["room"], row["meant"]) == \
        (itin.OUTCOME_NOT_KNOWN, None, "the_channel", "the harbour mouth")
    assert row["where_text"] == "the channel"
    # On ordinary ground an unanswered place is still where the mind goes.
    ashore = dict(stretch, unplaced=True, from_s=0.0, until_s=600.0)
    log, far = itin.live_through([ashore], scene=scene, start_room="kitchen")
    assert (log[0]["away"], log[0]["outcome"], far["away"]) == \
        ("the harbour mouth", itin.OUTCOME_NOT_KNOWN, "the harbour mouth")


def test_resolve_mind_marks_the_places_left_unanswered(monkeypatch):
    """`resolve_mind` keeps a place the decision model was asked about and
    did not answer apart from one it answered "none of these": both are
    off-map labels, and only the first is `unplaced`."""
    from agents import skip_stage
    from llm import decisions
    scene = _scene(T25)
    stretches = [{"from_s": 0.0, "until_s": 600.0, "room": None, "away": None,
                  "where_text": words, "doing": "waits", "asleep": False, "with": [],
                  "why": "", "uses": [], "kind": itin.KIND_PLAN}
                 for words in ("the harbour", "the harbour mouth")]

    def half(state, questions):
        return {"place:0": {"type": "choice", "choice": itin.NONE_OPTION,
                            "probabilities": {itin.NONE_OPTION: 0.8}}}

    monkeypatch.setattr(decisions, "OVERRIDE", half)
    placed, _holding, record = skip_stage.resolve_mind(
        PELL, stretches, scene, {}, "the_channel", {}, under_way={}, ways=_ways(T25, scene))
    assert [(s["away"], bool(s.get("unplaced"))) for s in placed] == [
        ("the harbour", False), ("the harbour mouth", True)]
    assert record["unplaced"] == ["the harbour mouth"]
    assert "unplaced" not in itin.as_stretch(placed[1])


# --------------------------------------------------------------------------
# 4. After a ride, a mind leaves the map by where the journey brought it
# --------------------------------------------------------------------------

def test_left_from_after_a_ride_is_where_the_journey_brought_the_mind():
    """The boatman began the span beside the Mary Ann in the channel; her
    journey put him ashore on the mainland and his day went on to "the
    harbour", off the map. He left the map by the mainland -- the live
    whereabouts said the channel, the journey's route room, so the next skip
    would bring him back through the water."""
    assert T25["minds"][PELL]["far_end_as_run"]["left_from"] == "the_channel"
    assert T26["whereabouts"][PELL]["left_from"] == "the_channel"
    log, far = _live(T25, PELL)
    journey = itin.journeys(_scene(T25), T25["span"]["from_s"])[MARY_ANN]
    assert journey["room"] == "the_mainland"
    assert (far["room"], far["away"], far["left_from"]) == (None, "the harbour", "the_mainland")
    assert not any(row["room"] == "the_mainland" for row in log)   # never a row there
    # A body that ends on the map left it by nothing.
    _log, far = _live(T25, ELIAS)
    assert far["left_from"] is None


# --------------------------------------------------------------------------
# 5. What must still fail
# --------------------------------------------------------------------------

def test_the_letter_on_the_rock_still_fails_the_post_office():
    """Turn 26, at the harbour off the map: the sealed letter lies in the
    hall on the rock, a thing a body carries, across the water. The post
    office goes without it, and the decision model's no keeps it failed."""
    assert _picks(T26, PELL)["Rhona Carrick's sealed letter"] == LETTER
    assert T26["scene"]["positions"][LETTER] == "tower_hall"
    log, _far = _live(T26, PELL)
    posting = log[0]
    assert posting["doing"].startswith("Walk up to Harrow Street by the post office")
    assert (posting["reason"], posting["missing"]) == \
        (itin.REASON_NOT_HELD, ["Rhona Carrick's sealed letter"])
    assert itin.short_of(log) == [0, 2]                  # the letter, and the post bag
    itin.judge_without(log, _answers(T26, PELL, log))
    assert (log[0]["outcome"], log[0]["reason"]) == (itin.OUTCOME_FAILED, itin.REASON_NOT_HELD)
    assert (log[2]["outcome"], log[2]["missing"]) == (itin.OUTCOME_NOT_KNOWN, ["the post bag"])
    assert _failed(log) == [0]


def test_the_tools_in_rhonas_hands_still_go_to_the_judgement():
    """The clockmaker's toolkit is carried by the player: every row of the
    keeper's that meant to use it is asked about, and the answer decides --
    the inspection and the side-by-side told as far as they went, the
    mechanism work failed."""
    scene = _scene(T25)
    assert scene["contained"][TOOLKIT]["in"] == RHONA
    log, _far = _live(T25, ELIAS)
    short = itin.short_of(log)
    assert short == [0, 4, 5, 6, 10, 11]
    assert all(_picks(T25, ELIAS)[m] == TOOLKIT for i in short for m in log[i]["missing"])
    itin.judge_without(log, _answers(T25, ELIAS, log))
    assert _failed(log) == [5, 6]
    assert all(log[i]["outcome"] == itin.OUTCOME_NOT_KNOWN and log[i]["missing"]
               for i in (0, 4, 10, 11))
    log26, _far = _live(T26, ELIAS)
    itin.judge_without(log26, _answers(T26, ELIAS, log26))
    assert _failed(log26) == [0, 1]


def test_the_crossings_still_fail():
    """Off the map at the harbour, his runs out across the channel and up
    onto the landing are crossings a body cannot make: they fail
    `no_crossing`, and they are all that fails of his turn-25 day."""
    log, _far = _live(T25, PELL)
    itin.judge_without(log, _answers(T25, PELL, log))
    assert _failed(log) == [4, 9, 11, 12]
    assert all(log[i]["reason"] == itin.REASON_NO_CROSSING for i in (4, 9, 11, 12))
    assert [log[i]["meant"] for i in (4, 9, 11, 12)] == [
        "the channel", "the channel", "the channel", "the landing at the rock"]


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


def _decide_as_recorded(turn):
    """The decision model as the live run answered it: each place and thing
    by the words asked about, each `without` by the row's doing."""
    rooms, entities = turn["scene"]["rooms"], turn["scene"]["entities"]

    def decide(state, questions):
        mind = state.get("mind")
        decided = turn["minds"][mind]["decided"]
        out = {}
        for key, question in questions.items():
            words = question["instructions"]
            if key.startswith("without:"):
                noul = next((w["noul"] for w in decided["without"]
                             if f'"{w["doing"]}"' in words), None)
                if noul is not None:
                    out[key] = {"type": "noul", "noul": noul}
                continue
            table = decided["places"] if key.startswith("place:") else decided["things"]
            said = words[words.index('means by "') + len('means by "'):]
            said = said[:said.index('"')]
            pick = (table.get(said) or {}).get("room" if key.startswith("place:") else "key")
            label = None
            if pick and key.startswith("place:"):
                label = rooms[pick]["name"]
            elif pick and pick in entities:
                label = entities[pick]["name"]
            elif pick:
                label = pick.rsplit(":", 1)[-1].replace("_", " ")
            choice = next((k for k, v in question["criteria"].items()
                           if label and (v == label or str(v).startswith(label + " ("))),
                          itin.NONE_OPTION)
            out[key] = {"type": "choice", "choice": choice, "probabilities": {choice: 0.9}}
        return out

    return decide


def test_the_stage_fails_only_what_is_truly_missing(temp_db, monkeypatch):
    """The whole stage on turn 25's world, the live answers and the live
    decision model's own picks and verdicts: of the keeper's twelve rows only
    the two whose work wants the toolkit in the player's hands fail (live:
    six), of the boatman's thirteen only his four crossings (live: ten),
    the record the memories are written from names paraffin and the Mary Ann
    in no failure, and the boatman left the map by the mainland."""
    from agents import skip_stage
    from core.db import q
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from llm import decisions
    from mind import skip_memories as sm
    from story.scene import active_cast
    chat, turn = _turn25_chat(temp_db)
    answers = {name: T25["minds"][name]["answer"] for name in (ELIAS, PELL)}
    monkeypatch.setattr(skip_stage, "ask", lambda ctx, row, span, nonce=0: (
        copy.deepcopy(answers[skip_stage._row_name(row)]), None))
    monkeypatch.setattr(decisions, "OVERRIDE", _decide_as_recorded(T25))
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
    elias, pell = out["minds"][ELIAS], out["minds"][PELL]
    assert [len(T25["minds"][n]["log_as_run"]) for n in (ELIAS, PELL)] == \
        [len(elias["log"]), len(pell["log"])]
    assert sum(r["outcome"] == "failed" for r in T25["minds"][ELIAS]["log_as_run"]) == 6
    assert sum(r["outcome"] == "failed" for r in T25["minds"][PELL]["log_as_run"]) == 10
    assert _failed(elias["log"]) == [5, 6]
    assert all(elias["log"][i]["missing"] for i in (5, 6))
    assert _failed(pell["log"]) == [4, 9, 11, 12]
    assert all(pell["log"][i]["reason"] == itin.REASON_NO_CROSSING for i in (4, 9, 11, 12))
    assert pell["far_end"]["away"] == "the harbour"
    assert pell["far_end"]["left_from"] == "the_mainland"
    for name, mind in ((ELIAS, elias), (PELL, pell)):
        record = sm.record_rows(mind["log"], span_from=T25["span"]["from_s"], anchor=15.75,
                                length=24.0, name=name)
        failed = " ".join(r.get("how_it_went") or "" for r in record
                          if r["outcome"] == "failed")
        assert "paraffin" not in failed and "Mary Ann" not in failed


def test_a_stage_that_cannot_judge_invents_no_failure(temp_db, monkeypatch):
    """Where judging what a mind went without breaks outright, the stage
    says so and tells every such row as far as it went: on turn 25 the
    keeper's toolkit rows are all `not_known`, what they lacked kept, and the
    boatman fails only his crossings."""
    from agents import skip_stage
    from core.db import q
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from llm import decisions
    from story.scene import active_cast
    chat, turn = _turn25_chat(temp_db)
    answers = {name: T25["minds"][name]["answer"] for name in (ELIAS, PELL)}
    monkeypatch.setattr(skip_stage, "ask", lambda ctx, row, span, nonce=0: (
        copy.deepcopy(answers[skip_stage._row_name(row)]), None))
    monkeypatch.setattr(decisions, "OVERRIDE", _decide_as_recorded(T25))

    def broken(name, log, language=None):
        raise RuntimeError("judging broke")

    monkeypatch.setattr(skip_stage, "judge_what_was_missing", broken)
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
    assert _failed(elias) == []
    assert all(elias[i]["outcome"] == itin.OUTCOME_NOT_KNOWN and elias[i]["missing"]
               for i in (0, 4, 5, 6, 10, 11))
    assert _failed(out["minds"][PELL]["log"]) == [4, 9, 11, 12]
    assert any("could not be judged" in w for w in ctx.warnings)
