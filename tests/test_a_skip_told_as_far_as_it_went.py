"""A skip told as far as it went: when an offer is for, what a ride is, what a
missing thing fails, what makes an outcome unknown, what a routine uses, and
one memory an occasion (`agents/skip_stage.py`, `world/skip_itinerary.py`,
`world/charter_skip.py`'s outcome, `mind/skip_memories.py`, the
`character_skip` card and the skip decision questions).

THE LIVE EVIDENCE is the lighthouse replayed a SECOND time, on add08c91
(chat 3): turn 25 (idx 8, "Two days later the wind gets up from the west
...") and turn 26 (idx 9, "That night, when Elias comes down from the first
watch and sits across the table from her with his tea ..."). Each turn's
world before it, its offers, every mind's answer, itinerary, log as run and
far end, the `skip` block each was asked under and the memories the job
wrote are `tests/data/skip_live_lighthouse_2.json`. Six defects:

  1. AN OFFER HAS NO TIME. Offered "comes down the tower stair into the
     kitchen with a mug of tea and sits ... across from Rhona Carrick", the
     keeper took it up as his plan's first stretch (morning to midday) and
     was upstairs on the night watch when the story took up again.
  2. A RIDE IS A CROSSING MADE. The boatman began the span beside the Mary
     Ann in the channel, bound for the mainland; his "Run the Mary Ann east
     ..." in "the channel" failed `no_crossing` while the journey carried
     him across it.
  3. AN INCIDENTAL THING FAILED A WHOLE STRETCH: "Log the failure ... sit
     with the logbook" failed `not_held` for want of the new clockwork,
     which stood one floor up.
  4. "NOT KNOWN" ON ROUTINE: a stretch naming `uses` was `not_known`, so the
     keeper's watches read "did not know what came of it".
  5. THE LETTER POSTED AGAIN: turn 26's routine posted a letter that lay on
     the rock -- a routine entry had no `uses` to check.
  6. DUPLICATE MEMORIES: two of the boatman's three memories of turn 25 were
     one occasion, both written from his first row.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from world import skip_itinerary as itin

ROOT = Path(__file__).resolve().parent.parent
LIVE = json.loads((ROOT / "tests" / "data" / "skip_live_lighthouse_2.json")
                  .read_text(encoding="utf-8"))["turns"]
T25, T26 = LIVE["25"], LIVE["26"]

ELIAS, PELL, RHONA = "Elias Thorne", "Pell Hardacre", "Rhona Carrick"

TOOLKIT = "0fe5091370dd4ef8"        # "clockmaker's toolkit", in Rhona's hands
LETTER = "1c40b9d46a854194"         # "a sealed letter", in the hall on the rock
CLOCKWORK = "00321d079f5e4cc3"      # "the new clockwork", in the lamp room
LAMP = "4614f4829c9a474b"           # "the tower lamp", in the lamp room
MUG = "ba53eeac816a4e51"            # "a mug of tea", in the kitchen
PARAFFIN = "ee2184aa135f4380"       # "paraffin crate", in the hall
STATION_LOG = "station_log"         # "the station log", in the kitchen (turn 26)
MARY_ANN = "3b4a011bf21e4686"       # "The Mary Ann", under way in the channel

#: The offer turn 26's interpret made the keeper, word for word.
OFFER = T26["authorial_offers"][0]["proposition"]

#: The things each mind's words name, as the stage resolves them: exactly
#: where a thing's own name is the words, else the decision model's pick --
#: stubbed here with the pick the live run made where its trace shows it
#: (the screwdriver and the clockmaker's tools to the toolkit, the letter to
#: the sealed letter, the station log, the mug), else a reader's pick -- else
#: nothing the world holds. With these picks the add08c91 executor gives the
#: live LOG's every `missing` (`test_the_picks_reproduce_the_live_logs`).
PICKS = {
    ELIAS: {"screwdriver": TOOLKIT, "the new clockwork in the Board's crate": CLOCKWORK,
            "the old lamp mechanism": LAMP, "clockmaker's tools from the kit on the shelf":
            TOOLKIT, "the new clockwork mechanism": CLOCKWORK, "station log": STATION_LOG,
            "mug of tea": MUG, "clockmaker's tools from the shelf": TOOLKIT,
            "new mechanism parts": CLOCKWORK, "clockmaker's tools": TOOLKIT,
            "paraffin lamp": LAMP, "clockwork mechanism": CLOCKWORK, "paraffin": PARAFFIN},
    PELL: {"Rhona Carrick's letter in the inside pocket": LETTER,
           "Rhona Carrick's letter": LETTER},
}

#: The decision model's answer to "can {name} do '{doing}' without
#: {missing}?" -- a reader's answer, by the doing's first words. Yes where
#: what was missing is incidental to it; no where it is what the doing is
#: done with, done to, or for.
WITHOUT = {
    "Pick up the brass shim": 0.9,          # inspecting needs no screwdriver
    "Light the lamp and set": 0.9,          # set by hand, the tools aside
    "Log the failure": 0.9,                 # the log, not the mechanism
    "Run the Mary Ann east": 0.9,           # the letter rides in a pocket
    "Tie up at the harbour": 0.05,          # posting needs the letter
    "Walk up to Harrow Street": 0.05,       # posting needs the letter
    "Climbs to the lamp room": 0.9,         # examining needs no tools
    "Works on the mechanism": 0.1,          # the swap is done with tools
    "Sits at the table and writes": 0.9,    # the log, not the paraffin
}


def _scene(turn):
    return copy.deepcopy(turn["scene"])


def _stubs(turn):
    return {stub: spec["frontier_of"]["room"] for stub, spec in turn["provisional"].items()}


def _named(turn, name, reach, stretches=None):
    named = {}
    for stretch in stretches if stretches is not None else turn["minds"][name]["itinerary"]:
        for thing in stretch.get("uses") or ():
            named[thing] = reach.named(thing) or (
                {PICKS[name][thing]} if thing in PICKS[name] else set())
    return named


def _live(turn, name, stretches=None, scene=None, here=None):
    """The executor over one mind's itinerary, as the stage runs it."""
    scene = scene or _scene(turn)
    stretches = copy.deepcopy(stretches if stretches is not None
                              else turn["minds"][name]["itinerary"])
    ways = itin.Ways(scene, joins=itin.frontier_joins(_stubs(turn)))
    under_way = itin.journeys(scene, turn["span"]["from_s"])
    here = here or scene["positions"][name]
    reach = itin.Reach(scene, name, journeys=under_way)
    named = _named(turn, name, reach, stretches)
    log, far = itin.live_through(
        stretches, scene=scene, start_room=here, ways=ways,
        missing_from=lambda uses, room, away=None, t=None:
            reach.missing(uses, named, room, away, t),
        journey=itin.journey_under_way(scene, here, under_way, ways))
    return itin.place_words(log, scene), far


def _without_judge(requests=None):
    """The decision model for `without:` questions, by `WITHOUT`; every
    request recorded."""
    def judge(state, questions):
        if requests is not None:
            requests.append((copy.deepcopy(state), copy.deepcopy(questions)))
        out = {}
        for key, question in questions.items():
            if not key.startswith("without:"):
                continue
            yes = next((p for start, p in WITHOUT.items()
                        if f'"{start}' in question["instructions"]), None)
            if yes is not None:
                out[key] = {"type": "noul", "noul": yes}
        return out
    return judge


def _span(turn):
    clock = turn["clock"]
    hour0 = (clock["anchor_hour"] + clock["elapsed_seconds"] / 3600.0) % 24.0
    return itin.Span(turn["span"]["from_s"], turn["span"]["until_s"], hour0, 24.0)


def _assert_the_picks_reproduce_the_live_logs():
    """The stubs stand for the live run: these picks give every `missing`
    the live LOG has, where its rows stood."""
    for turn, name in ((T25, ELIAS), (T25, PELL), (T26, ELIAS)):
        as_run = turn["minds"][name]["log_as_run"]
        missing = [r["missing"] for r in as_run if r["missing"]]
        assert missing, (turn["idx"], name)
        scene = _scene(turn)
        reach = itin.Reach(scene, name, journeys=itin.journeys(scene, turn["span"]["from_s"]))
        named = _named(turn, name, reach)
        for row, stretch in zip(as_run, turn["minds"][name]["itinerary"]):
            if row["missing"]:
                assert reach.missing(stretch["uses"], named, row["room"], row["away"],
                                     row["from_s"]) == row["missing"]


# --------------------------------------------------------------------------
# 1. An offer is for when the stretch ends
# --------------------------------------------------------------------------

def test_an_offer_sits_under_the_stretchs_end():
    """The live block put the keeper's offer beside the stretch's START
    (`skip.offers`, top level, the morning); it sits under `until` -- day
    0, night -- the moment the story takes up again."""
    from agents.skip_stage import skip_block
    as_asked = T26["minds"][ELIAS]["skip_as_asked"]
    assert as_asked["offers"] == [OFFER] and as_asked["now"] == "morning"
    block = skip_block(_span(T26), asleep_now=False, where_you_are="The Kitchen",
                       offers=[OFFER])
    assert block["until"] == {"day": 0, "part_of_day": "night", "offers": [OFFER]}
    assert "offers" not in block
    empty = skip_block(_span(T26), asleep_now=False, where_you_are="The Mainland",
                       offers=[])
    assert empty["until"]["offers"] == []


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_card_says_an_offer_is_taken_up_at_the_end(language):
    """The card names the offers where the block puts them and says where
    one taken up goes -- the class, no instance."""
    from llm.prompts import get_prompt
    card = get_prompt("character_skip", language=language)
    assert "`skip.until.offers`" in card
    assert "`skip.offers`" not in card
    offer = next(line for line in card.split("\n") if "`skip.until.offers`" in line)
    sentence = offer[offer.index("`skip.until.offers`"):]
    assert "`at_the_end`" in sentence
    assert "Rhona" not in card and "Elias" not in card and "tea" not in card.casefold()


def _validated(answer):
    from llm.schemas import validate_llm_output
    return validate_llm_output("character_skip", copy.deepcopy(answer))[0]


def test_an_offer_taken_up_at_the_end_is_where_the_far_end_finds_the_mind():
    """`at_the_end` is the stretch that carries a taken-up offer: laid over
    the span's last moments, it is the far end. The keeper's turn-26 answer,
    his last entry the offer taken up as the card now asks: through the
    schema, his itinerary ends in the kitchen with Rhona and his tea, and the
    far end finds him there, awake. The schema used to drop `with` and
    `uses` from `at_the_end`."""
    answer = copy.deepcopy(T26["minds"][ELIAS]["answer"])
    answer["at_the_end"] = {
        "where": "The Kitchen", "asleep": False, "with": [RHONA], "uses": ["mug of tea"],
        "doing": "Comes down the stair from the first watch with a mug of tea and sits "
                 "at the kitchen table across from Rhona Carrick",
        "why": "the watch is set and she is still up"}
    kept = _validated(answer)
    assert kept["at_the_end"]["with"] == [RHONA]
    assert kept["at_the_end"]["uses"] == ["mug of tea"]
    stretches = itin.expand_itinerary(kept, _span(T26))
    last = stretches[-1]
    assert last["kind"] == itin.KIND_END
    assert (last["until_s"], last["with"], last["uses"]) == (
        T26["span"]["until_s"], [RHONA], ["mug of tea"])
    placed = itin.place_stretches(stretches, {"The Kitchen": "kitchen",
                                              "The Lamp Room": "lamp_room"})
    log, far = _live(T26, ELIAS, stretches=placed)
    assert log[-1]["doing"].startswith("Comes down the stair")
    assert (far["room"], far["asleep"]) == ("kitchen", False)
    as_run = T26["minds"][ELIAS]["far_end_as_run"]
    assert as_run["room"] == "lamp_room"         # the live far end: upstairs


# --------------------------------------------------------------------------
# 2. A ride is a crossing made
# --------------------------------------------------------------------------

def test_the_boatmans_run_across_the_channel_is_the_ride_and_not_a_crossing():
    """Beside the Mary Ann in the channel, bound for the mainland, his
    first stretch is placed in the channel: the ride. It is lived from the
    span's first moment in the channel until the journey ends, and he steps
    off on the mainland -- a row of its own, nothing declared. The live run
    failed it `no_crossing` and began it on the mainland when the journey
    was done. His last stretch, the run back west after the journey ended,
    is a crossing of his own, and still fails."""
    as_run = T25["minds"][PELL]["log_as_run"]
    assert (as_run[0]["outcome"], as_run[0]["reason"], as_run[0]["meant"]) == \
        ("failed", "no_crossing", "the channel")
    log, far = _live(T25, PELL)
    journey = itin.journeys(_scene(T25), T25["span"]["from_s"])[MARY_ANN]
    ride, landed = log[0], log[1]
    assert ride["doing"].startswith("Run the Mary Ann east")
    assert (ride["from_s"], ride["until_s"]) == (T25["span"]["from_s"], journey["until_s"])
    assert (ride["room"], ride["where_text"]) == ("the_channel", "the channel")
    # Not a way it failed to make: only the letter it meant to carry, which
    # lies on the rock, is not to hand (the decision model's, below).
    assert (ride["reason"], ride["meant"]) == (itin.REASON_NOT_HELD, None)
    assert ride["missing"] == ["Rhona Carrick's letter in the inside pocket"]
    assert (landed["from_s"], landed["until_s"]) == (journey["until_s"], 94500.0)
    assert (landed["room"], landed["doing"], landed["outcome"]) == ("the_mainland", "", "done")
    assert not any(r["reason"] == itin.REASON_NO_CROSSING for r in log[:-1])
    assert (log[-1]["reason"], log[-1]["meant"]) == (itin.REASON_NO_CROSSING, "the channel")
    assert far["room"] == "the_mainland"


def test_aboard_the_ride_is_spent_aboard_and_lands_with_the_vessel():
    """Aboard the Mary Ann under way, a stretch placed on her way is the
    ride: spent aboard, never failed. It failed `too_far` before -- no walk
    out of the vessel into the water. When her journey ends, her door opens
    onto the mainland and the next stretch walks ashore."""
    scene = _scene(T25)
    scene["positions"][PELL] = "mary_ann_interior"
    span_from = T25["span"]["from_s"]
    stretches = [
        dict(itin.as_stretch(T25["minds"][PELL]["itinerary"][0]), uses=[]),
        {"from_s": 94500.0, "until_s": 99900.0, "room": "the_mainland", "away": None,
         "where_text": "The Mainland", "doing": "Ties up and squares the lines",
         "asleep": False, "with": [], "why": "", "uses": []}]
    log, far = _live(T25, PELL, stretches=stretches, scene=scene, here="mary_ann_interior")
    assert [(r["room"], r["outcome"], r["reason"]) for r in log] == [
        ("mary_ann_interior", "done", None), ("the_mainland", "done", None)]
    assert log[0]["from_s"] == span_from
    assert far["room"] == "the_mainland"


def test_a_stretch_with_no_place_of_its_own_is_the_ride_too():
    """"Where I stand", while the journey carries the body, is the journey's
    way: the default day's stretch the boatman left unsaid is lived from its
    first moment in the channel, and he steps off on the mainland when the
    journey ends -- where the ride's hours used to vanish from the log, his
    stretch beginning only once she was in."""
    span_from = T25["span"]["from_s"]
    journey = itin.journeys(_scene(T25), span_from)[MARY_ANN]
    unsaid = [{"from_s": span_from, "until_s": 94500.0, "room": None, "away": None,
               "where_text": "", "doing": "", "asleep": False, "with": [], "why": "",
               "uses": []}]
    log, far = _live(T25, PELL, stretches=unsaid)
    assert [(r["from_s"], r["until_s"], r["room"]) for r in log] == [
        (span_from, journey["until_s"], "the_channel"),
        (journey["until_s"], 94500.0, "the_mainland")]
    assert far["room"] == "the_mainland"


def test_rides_reads_the_journeys_way_and_its_vessels_rooms():
    journey = itin.journeys(_scene(T25), T25["span"]["from_s"])[MARY_ANN]
    assert journey["route"] == "the_channel"
    assert itin.rides(journey, "the_channel") and itin.rides(journey, "mary_ann_interior")
    assert not itin.rides(journey, "the_mainland") and not itin.rides(None, "the_channel")


# --------------------------------------------------------------------------
# 3. A missing thing fails a stretch only where it cannot be done without it
# --------------------------------------------------------------------------

def test_a_thing_not_to_hand_fails_a_stretch_only_where_it_cannot_be_done_without():
    """Each row a thing not to hand failed is asked about once: told as far
    as it went (`not_known`, `missing` kept, no reason) where it can be done
    without -- the keeper's log entry without the new clockwork -- and
    failed where it cannot: the boatman's walk to post a letter that lies
    on the rock. A row answered no stays failed; one not answered at all is
    told as far as it went (fix lane B5, the owner's ruling of 2026-10-22:
    no answer never invents a failure)."""
    _assert_the_picks_reproduce_the_live_logs()
    elias, _ = _live(T25, ELIAS)
    pell, _ = _live(T25, PELL)
    short = {name: [log[i]["doing"][:22] for i in itin.short_of(log)]
             for name, log in ((ELIAS, elias), (PELL, pell))}
    assert short == {ELIAS: ["Pick up the brass shim", "Light the lamp and set",
                             "Log the failure — reco"],
                     PELL: ["Run the Mary Ann east ", "Tie up at the harbour,"]}
    unanswered = copy.deepcopy(pell)
    assert itin.judge_without(unanswered, {}) == itin.short_of(pell)
    assert all(unanswered[i]["outcome"] == "not_known" and unanswered[i]["missing"]
               for i in itin.short_of(pell))
    said_no = copy.deepcopy(pell)
    no = {"type": "noul", "noul": 0.2}
    assert itin.judge_without(said_no, {f"without:{i}": no for i in itin.short_of(pell)}) == []
    assert said_no == pell
    for name, log in ((ELIAS, elias), (PELL, pell)):
        questions = itin.without_questions(name, log)
        assert sorted(questions) == sorted(f"without:{i}" for i in itin.short_of(log))
        assert itin.judge_without(log, _without_judge()(None, questions))
    logging = elias[2]
    assert logging["doing"].startswith("Log the failure")
    assert (logging["outcome"], logging["reason"], logging["missing"]) == \
        ("not_known", None, ["the new clockwork mechanism"])
    posting = pell[2]
    assert posting["doing"].startswith("Tie up at the harbour")
    assert (posting["outcome"], posting["reason"], posting["missing"]) == \
        ("failed", "not_held", ["Rhona Carrick's letter"])
    ride = pell[0]
    assert (ride["outcome"], ride["reason"], ride["missing"]) == \
        ("not_known", None, ["Rhona Carrick's letter in the inside pocket"])


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_question_names_the_doing_and_what_was_missing(language):
    log, _ = _live(T25, PELL)
    question = itin.without_questions(PELL, log, language)["without:2"]
    assert question["type"] == "noul"
    text = question["instructions"]
    assert PELL in text and "Rhona Carrick's letter" in text
    assert log[2]["doing"][:40] in text and "{" not in text


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
    ids = {}
    for name in (ELIAS, PELL):
        ids[name] = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                       "VALUES(?,?,?,?,?)", (name, json.dumps(default_character_data(name)),
                                             "{}", now, "uid_" + name.split()[0].casefold()))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
           (chat, ids[name], "active", "{}"))
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
    return chat, turn, ids


def test_the_stage_asks_once_per_mind_over_its_short_rows(temp_db, monkeypatch):
    """The whole stage on turn 25's world and answers: each mind's places
    and things in its one request, then ONE more request per mind over the
    rows a thing not to hand failed -- never for a mind with none -- and the
    log the far end and the memories read is the judged one."""
    from agents import skip_stage
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from llm import decisions
    from story.scene import active_cast
    chat, turn, _ids = _turn25_chat(temp_db)
    answers = {name: T25["minds"][name]["answer"] for name in (ELIAS, PELL)}
    rooms = {name: {s["where_text"]: s["room"] for s in T25["minds"][name]["itinerary"]}
             for name in (ELIAS, PELL)}
    monkeypatch.setattr(skip_stage, "ask", lambda ctx, row, span, nonce=0: (
        copy.deepcopy(answers[skip_stage._row_name(row)]), None))
    scene_rooms = T25["scene"]["rooms"]
    entities = T25["scene"]["entities"]
    requests = []
    without = _without_judge()

    def decide(state, questions):
        requests.append(sorted({key.split(":")[0] for key in questions}))
        mind = state.get("mind")
        out = without(state, questions)
        for key, question in questions.items():
            pick = None
            words = question["instructions"]
            if key.startswith("place:"):
                for where, room in rooms[mind].items():
                    if room and f'"{where}"' in words:
                        name = scene_rooms[room]["name"]
                        pick = next((k for k, v in question["criteria"].items()
                                     if v == name or str(v).startswith(name + " (")), None)
            elif key.startswith("thing:"):
                for thing, key_ in PICKS[mind].items():
                    if f'"{thing}"' in words:
                        name = entities[key_]["name"]
                        pick = next((k for k, v in question["criteria"].items()
                                     if v == name or str(v).startswith(name + " (")), None)
            else:
                continue
            pick = pick or "none"
            out[key] = {"type": "choice", "choice": pick, "probabilities": {pick: 0.9}}
        return out

    monkeypatch.setattr(decisions, "OVERRIDE", decide)
    from core.db import q
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
    assert requests.count(["without"]) == 2           # one per mind, each its own
    elias, pell = out["minds"][ELIAS]["log"], out["minds"][PELL]["log"]
    inspecting = next(r for r in elias if r["doing"].startswith("Pick up the brass shim"))
    assert (inspecting["outcome"], inspecting["missing"]) == ("not_known", ["screwdriver"])
    # The new clockwork lies one floor up from the log entry, and the keeper
    # fetches it inside the stretch (fix lane B4, `Reach.fetch`): nothing is
    # missing, and the row begins when he is back down with it.
    logging = next(r for r in elias if r["doing"].startswith("Log the failure"))
    assert (logging["outcome"], logging["missing"]) == ("not_known", [])   # `with` Rhona
    down = itin.walk_seconds(T25["scene"], ["lamp_room", "kitchen"])
    up = itin.walk_seconds(T25["scene"], ["kitchen", "lamp_room"])
    assert logging["from_s"] == pytest.approx(99900.0 + down + up + down)
    posting = next(r for r in pell if r["doing"].startswith("Tie up at the harbour"))
    assert (posting["outcome"], posting["reason"]) == ("failed", "not_held")
    assert pell[0]["room"] == "the_channel" and pell[0]["outcome"] == "not_known"
    watch = next(r for r in elias if r["doing"].startswith("Night watch — monitor"))
    assert (watch["outcome"], watch["reason"]) == ("done", None)


# --------------------------------------------------------------------------
# 4. What a stretch uses never makes it unknown
# --------------------------------------------------------------------------

def test_what_a_stretch_uses_never_makes_it_unknown():
    """`not_known` is the world's to judge -- another's response, a world off
    the map -- and a stretch that partly failed; never a mind's own work with
    its own things. The keeper's night watch (the station log, a telescope)
    was `not_known` live, and is `done`."""
    rule = itin.stretch_outcome
    assert rule({"uses": ["the station log"]}) == "done"
    assert rule({"uses": ["the station log"], "with": [RHONA]}) == "not_known"
    assert rule({"uses": ["a pint"]}, away="the harbour pub") == "not_known"
    assert rule({"uses": ["the station log"]}, partial=True) == "not_known"
    assert rule({"asleep": True, "uses": ["a blanket"]}) == "done"
    assert rule({"uses": ["x"]}, reason=itin.REASON_NOT_HELD) == "failed"
    as_run = T25["minds"][ELIAS]["log_as_run"]
    log, _ = _live(T25, ELIAS)
    watch = next(i for i, r in enumerate(as_run) if r["doing"].startswith("Night watch — mon"))
    assert as_run[watch]["outcome"] == "not_known"
    assert (log[watch]["outcome"], log[watch]["reason"]) == ("done", None)
    # Every row of his that is not failed and names nobody is done.
    for row, stretch in zip(log, T25["minds"][ELIAS]["itinerary"]):
        if row["outcome"] != "failed" and not stretch["with"]:
            assert row["outcome"] == "done", row["doing"]


def test_the_towns_executor_writes_the_same_rule():
    """The charter's row for a stretch it ran, reached, with things it uses
    and nobody to answer it: `done`, as the stage's own executor says it."""
    from world import charter_skip
    run = charter_skip._TownRun.__new__(charter_skip._TownRun)
    run.samples = [{"mind": {"place": "forge"}},
                   {"mind": {"place": "forge"}, "simulated": True}]
    run._seen = lambda windows, labels: []
    stretch = {"from_s": 0.0, "until_s": 3600.0, "room": "forge", "away": None,
               "where_text": "the forge", "doing": "shoes the mare", "asleep": False,
               "with": [], "uses": ["the hammer"], "why": ""}
    assert run._stretch_row(stretch, [0], None)["outcome"] == "done"
    assert run._stretch_row(dict(stretch, **{"with": [RHONA]}), [0], None)["outcome"] == \
        "not_known"
    assert run._stretch_row(stretch, [], None)["outcome"] == "not_known"   # unrun


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_outcome_words_read_as_a_persons_memory(language):
    """`done` says the mind did it; `not_known` that it set about it and the
    rest was out of its hands; a row that went without things not to hand
    names them -- none of them a note about the record."""
    from mind import skip_memories as sm
    done = sm.how_it_went(ELIAS, "done", language=language)
    unknown = sm.how_it_went(ELIAS, "not_known", language=language)
    without = sm.how_it_went(ELIAS, "not_known", missing=["the new clockwork mechanism"],
                             language=language)
    for words in (done, unknown, without):
        assert ELIAS in words
        assert "record" not in words and "記録" not in words
        assert "what came of it" not in words and "何がどうなったか" not in words
    assert "the new clockwork mechanism" in without and without not in (done, unknown)
    assert done != unknown
    failed = sm.how_it_went(ELIAS, "failed", "not_held", missing=["the letter"],
                            language=language)
    assert failed != without


def test_the_record_tells_a_row_as_far_as_it_went():
    from mind import skip_memories as sm
    row = {"from_s": 99900.0, "until_s": 108900.0, "room": "kitchen", "away": None,
           "where_text": "The Kitchen", "doing": "Log the failure", "asleep": False,
           "seen": [], "weather": None, "outcome": "not_known", "reason": None,
           "missing": ["the new clockwork mechanism"], "meant": None}
    record = sm.record_rows([row], span_from=78466.0, anchor=15.75, length=24.0,
                            name=ELIAS)[0]
    assert record["outcome"] == "not_known"
    assert record["how_it_went"] == (
        "Elias Thorne did it as far as it would go without the new clockwork mechanism: "
        "neither on Elias Thorne nor within reach.")
    # A row that set about nothing -- the moments after the ride put the
    # boatman ashore -- has no doing to tell, and no words.
    landed = dict(row, doing="", where_text="The Mainland", room="the_mainland",
                  outcome="done", missing=[])
    record = sm.record_rows([landed], span_from=78466.0, anchor=15.75, length=24.0,
                            name=PELL)[0]
    assert record["outcome"] == "done" and "how_it_went" not in record


def test_a_row_told_without_its_things_carries_them_to_the_far_end_call(monkeypatch):
    """The far end's own call reads the row as it went: `not_known`, with
    the things it went without -- `missing` rode only on a failed row."""
    from agents import skip_stage
    log, far = _live(T25, ELIAS)
    itin.judge_without(log, _without_judge()(None, itin.without_questions(ELIAS, log)))
    output = {"span": dict(T25["span"]), "minds": {ELIAS: {"log": log, "far_end": far}}}
    ctx = SimpleNamespace(chat=SimpleNamespace(id=None),
                          get=lambda key, default=None: output if key == "skip_lives" else default)
    monkeypatch.setattr(skip_stage, "span_of_output", lambda chat_id, out: _span(T25))
    monkeypatch.setattr(skip_stage, "_stored_scene", lambda chat_id: _scene(T25))
    rows = skip_stage.stretch_for_payload(ctx, ELIAS)
    logging = next(r for r in rows if r["doing"].startswith("Log the failure"))
    assert logging["outcome"] == "not_known" and "reason" not in logging
    assert logging["missing"] == ["the new clockwork mechanism"]


# --------------------------------------------------------------------------
# 5. Every entry of an answer says what it uses
# --------------------------------------------------------------------------

def test_every_entry_of_an_answer_keeps_with_uses_and_why():
    """The routine's entries and `at_the_end` keep `with`, `uses` and `why`
    as the plan's do: a routine day uses things as surely as a plan. The
    schema kept them on the plan alone."""
    kept = _validated({
        "routine": [{"from": "midday", "until": "afternoon", "where": "The Mainland",
                     "doing": "Walks up to the post office and posts the letter",
                     "uses": ["Rhona Carrick's letter"], "with": [], "why": "a promise"}],
        "plan": [],
        "at_the_end": {"where": "The Mainland", "doing": "asleep", "asleep": True,
                       "uses": ["a blanket"], "with": [], "why": "tired"}})
    assert kept["routine"][0]["uses"] == ["Rhona Carrick's letter"]
    assert kept["routine"][0]["why"] == "a promise"
    assert kept["at_the_end"]["uses"] == ["a blanket"]
    assert kept["at_the_end"]["why"] == "tired"


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_cards_answer_shape_gives_every_entry_with_uses_and_why(language):
    from llm.prompts import get_prompt
    card = get_prompt("character_skip", language=language)
    start = card.index('{"routine"')
    shape = json.loads(card[start:card.index("\n", start)])
    for entry in (shape["routine"][0], shape["plan"][0], shape["at_the_end"]):
        assert {"with", "uses", "why"} <= set(entry), entry


def test_the_boatmans_routine_post_fails_for_the_letter_on_the_rock():
    """Turn 26's boatman posted the letter in his ROUTINE, and nothing could
    check it: a routine entry had no `uses`. His answer as the card now asks
    for it -- the routine's post naming the letter it uses -- fails
    `not_held`: the letter lies in the hall on the rock, and posting cannot
    be done without it. The live row was `done`, and his memory says "the
    letter in the box with me own hand"."""
    as_run = T26["minds"][PELL]["log_as_run"]
    assert as_run[1]["doing"].startswith("Walk up to Harrow Street")
    assert (as_run[1]["outcome"], as_run[1]["reason"]) == ("done", None)
    assert "in the box with me own hand" in T26["memories_as_written"][PELL][0]["content"]
    answer = copy.deepcopy(T26["minds"][PELL]["answer"])
    answer["routine"][1]["uses"] = ["Rhona Carrick's letter"]
    stretches = itin.expand_itinerary(_validated(answer), _span(T26))
    placed = itin.place_stretches(stretches, {"The Mainland": "the_mainland"})
    log, far = _live(T26, PELL, stretches=placed)
    posting = next(i for i, r in enumerate(log) if r["doing"].startswith("Walk up to Harrow"))
    assert (log[posting]["reason"], log[posting]["missing"]) == \
        (itin.REASON_NOT_HELD, ["Rhona Carrick's letter"])
    itin.judge_without(log, _without_judge()(None, itin.without_questions(PELL, log)))
    assert (log[posting]["outcome"], log[posting]["reason"]) == ("failed", "not_held")
    assert far["room"] == "the_mainland"


# --------------------------------------------------------------------------
# 6. One memory an occasion
# --------------------------------------------------------------------------

def _pell_25_memories():
    """The boatman's three live memories of turn 25, as the writer's answer:
    memories 0 and 1 both end at row 0's end (94,500 s) -- built from his
    first row alone -- and memory 2 at the span's (rows 2-6)."""
    from mind import skip_memories as sm
    label = sm.linguistic("mind.skip_memories", "_SKIP_MEMORY_LABELS", "en")["afterwards"]
    out = []
    for row, rows in zip(T25["memories_as_written"][PELL], ([0], [0], [2, 3, 4, 5, 6])):
        memory, _sep, consequence = row["content"].partition(" " + label + " ")
        out.append({"index": None, "rows": rows, "when": "", "where": "",
                    "memory": memory, "consequence": consequence,
                    "valence": row["valence"], "arousal": row["arousal"]})
    assert [r["encoded_at_seconds"] for r in T25["memories_as_written"][PELL]] == \
        [94500.0, 94500.0, 225900.0]
    return out


def _payload():
    from mind import skip_memories as sm
    log = [dict(r, seen=[], weather=None) for r in T25["minds"][PELL]["log_as_run"]]
    record = sm.record_rows(log, span_from=T25["span"]["from_s"], anchor=15.75,
                            length=24.0, name=PELL)
    return sm.writer_payload({"name": PELL}, {}, record, {"hours": 41.5})


def test_two_memories_of_one_occasion_are_one_and_the_better_checked_is_kept(monkeypatch):
    """After the mend, the boatman's memories 0 and 1 -- one occasion, both
    built from row 0, the second flagged and rewritten into a near copy of
    the first -- are one memory: the one that passed as written stays."""
    from llm import decisions
    from mind import skip_memories as sm
    episodes = _pell_25_memories()
    flagged = episodes[1]["memory"]

    def judge(state, questions):
        hit = state.get("memory", "").startswith(flagged[:40]) and "past" not in questions
        return {key: {"type": "noul", "noul": 0.9 if hit and key == "outcome" else 0.05}
                for key in questions}

    monkeypatch.setattr(decisions, "OVERRIDE", judge)
    rewritten = dict(episodes[1], index=1, memory=episodes[0]["memory"] + " Again.")
    monkeypatch.setattr(sm, "chat_complete", lambda *a, **k: json.dumps(
        {"episodes": [rewritten]}))
    kept, report = sm.check_and_mend(PELL, 3, _payload(), episodes)
    assert report["rewritten"] == [1] and report["merged"] == [1]
    assert [m["memory"] for m in kept] == [episodes[0]["memory"], episodes[2]["memory"]]
    assert sm.summary_of(dict(report, status="written"))["merged"] == [1]
    # Memories of other rows, or naming none, are each their own.
    a, b, c, d = ({"rows": [0], "memory": "a"}, {"rows": [0, 1], "memory": "b"},
                  {"rows": [], "memory": "c"}, {"rows": [], "memory": "d"})
    assert sm.one_memory_per_occasion(
        [(m, (0, 0, i), i) for i, m in enumerate((a, b, c, d))]) == ([a, b, c, d], [])


def test_the_better_checked_wins_whichever_comes_first(monkeypatch):
    """Where the first of two memories of one occasion kept only what
    survived the drop and the second passed as written, the second stays."""
    from llm import decisions
    from mind import skip_memories as sm
    episodes = _pell_25_memories()
    first = sm.sentences(episodes[0]["memory"])[0]

    def judge(state, questions):
        out = {}
        for key, question in questions.items():
            hit = (key == "outcome" and state.get("memory", "").startswith(first)) or \
                (re.fullmatch(r"o\d+", key) is not None and first in question["instructions"])
            out[key] = {"type": "noul", "noul": 0.9 if hit else 0.05}
        return out

    monkeypatch.setattr(decisions, "OVERRIDE", judge)
    monkeypatch.setattr(sm, "chat_complete", lambda *a, **k: json.dumps({"episodes": []}))
    kept, report = sm.check_and_mend(PELL, 3, _payload(), episodes)
    assert report["dropped_sentences"] and report["merged"] == [0]
    assert [m["memory"] for m in kept] == [episodes[1]["memory"], episodes[2]["memory"]]
