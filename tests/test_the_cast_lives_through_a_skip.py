"""The cast live through a time skip (`agents/skip_stage.py`,
`world/skip_itinerary.py`, `persist/commit_skip.py`).

`docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md`. The defect (probe finding
F16, the lighthouse story, control chat 2 idx 8): "Two days later the wind
gets up from the west ..." moved the clock two days and nobody else moved --
the keeper stood in the lamp room through the whole span, the boatman sat in
the channel for 77.7 story hours, and nobody was asked anything. The next
input's "That night, when Elias comes down from the first watch ..." found
him upstairs.

The world below is that story's shape: a keeper in the lamp room, a boatman
dormant on the mainland, a sleeper in the spare room, and the player in the
kitchen. The model's answers are the probe's REAL answers
(`tests/data/skip_probe_answers.json`), stubbed in where the model would be.
"""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from world import skip_itinerary as itin

ROOT = Path(__file__).resolve().parent.parent
PROBE = json.loads((ROOT / "tests" / "data" / "skip_probe_answers.json")
                   .read_text(encoding="utf-8"))["answers"]

PLAYER = "Rhona Carrick"
ELIAS, PELL, NELL = "Elias Thorne", "Pell Hardacre", "Nell Hale"
MARA, OTTO = "Mara Quill", "Otto Bray"

#: The probe story's clock at idx 8: 78466 s elapsed, anchored so the day
#: stands at 13:32 in the afternoon.
CLOCK = {"elapsed_seconds": 78466.0, "anchor_hour": 15.75,
         "day_length_hours": 24.0, "display": "afternoon"}
HOUR0 = (15.75 + 78466.0 / 3600.0) % 24.0


def _edge(to, barrier="open"):
    return {"to": to, "barrier": barrier}


def _rooms():
    return {
        "landing": {"name": "The Landing", "exposure": "open",
                    "adjacent": [_edge("stair"), _edge("mainland")]},
        "stair": {"name": "The Steps", "exposure": "open",
                  "adjacent": [_edge("landing"), _edge("hall", "open_door")]},
        "hall": {"name": "The Hall", "exposure": "enclosed",
                 "adjacent": [_edge("stair", "open_door"), _edge("kitchen", "open_door"),
                              _edge("store", "locked_door")]},
        "kitchen": {"name": "The Kitchen", "exposure": "enclosed",
                    "adjacent": [_edge("hall", "open_door"),
                                 _edge("bedroom_elias", "closed_door"),
                                 _edge("spare_room", "closed_door"),
                                 _edge("lamp_room")]},
        "lamp_room": {"name": "The Lamp Room", "exposure": "enclosed",
                      "adjacent": [_edge("kitchen")]},
        "bedroom_elias": {"name": "Elias's Room", "exposure": "enclosed",
                          "adjacent": [_edge("kitchen", "closed_door")]},
        "spare_room": {"name": "The Spare Room", "exposure": "enclosed",
                       "adjacent": [_edge("kitchen", "closed_door")]},
        "store": {"name": "The Store", "exposure": "enclosed",
                  "adjacent": [_edge("hall", "locked_door")]},
        "mainland": {"name": "The Mainland", "exposure": "open",
                     "adjacent": [_edge("landing")]},
        "skerry": {"name": "The Skerry", "exposure": "open", "adjacent": []},
    }


def _scene():
    return {
        "location": "the lighthouse", "time_of_day": "afternoon",
        "rooms": _rooms(),
        "positions": {PLAYER: "kitchen", ELIAS: "lamp_room", NELL: "spare_room",
                      PELL: "mainland", OTTO: "hall"},
        "stations": {ELIAS: {"at": None, "near": [], "cell": [1, 1]}},
        "poses": {ELIAS: {"posture": "kneeling", "support": "floor",
                          "relative_to": "", "relation": "", "constraint": "",
                          "detail": "at the clockwork"}},
        "following": {ELIAS: {"target": PLAYER, "since_turn": 2, "reason": ""}},
        "entities": {"logbook": {"name": "the station log", "kind": "document"}},
        "contained": {"logbook": {"in": ELIAS, "mode": "carried"}},
        "attire": {ELIAS: {"wearing": ["oilskin coat", "a brass key on a cord"]}},
        "overlays": {}, "orientation": {}, "contacts": [],
        "weather": {"sky": "pewter overcast", "air": "clear", "cloud": "covered",
                    "electrical": False, "precipitation": "spray",
                    "precipitation_kind": "liquid", "intensity": "heavy",
                    "wind": "gale", "temperature": "cold", "moon": "none",
                    "wind_from": "w", "drift_step": 21},
    }


def _graph(*rooms):
    names = _rooms()
    return {"place_graph": {"nodes": {r: {"name": names[r]["name"]} for r in rooms},
                            "edges": {}}}


def _sheet(name, tier):
    from story.character_schema import default_character_data
    sheet = default_character_data(name)
    sheet.setdefault("simulation", {})["tier"] = tier
    return sheet


@pytest.fixture
def story(temp_db):
    """The lighthouse at idx 8, with the input's two-day skip kept."""
    from core.db import qi, wset
    from story.character_schema import default_persona_data
    now = time.time()
    persona = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                 (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat = qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
              ("The Lamp Room", "", now, persona))
    ids = {}
    states = {ELIAS: _graph("landing", "stair", "hall", "kitchen", "lamp_room"),
              PELL: _graph("landing", "mainland"),
              NELL: _graph("kitchen", "spare_room"),
              MARA: {}, OTTO: {}}
    statuses = {ELIAS: "active", PELL: "dormant", NELL: "active",
                MARA: "dormant", OTTO: "active"}
    tiers = {ELIAS: "major", PELL: "mid", NELL: "mid", MARA: "mid", OTTO: "bg"}
    for name in (ELIAS, PELL, NELL, MARA, OTTO):
        sheet = _sheet(name, tiers[name])
        ids[name] = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                       "VALUES(?,?,?,?,?)",
                       (name, json.dumps(sheet), "{}", now,
                        "uid_" + name.split()[0].casefold()))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
           (chat, ids[name], statuses[name], json.dumps(states[name])))
    # Mara is out in a causality bubble of her own: her frame keeps its clock.
    bubble = qi("INSERT INTO frames(chat_id,label,ordinal,kind,created,parent_frame_id) "
                "VALUES(?,?,?,?,?,?)", (chat, "Bubble — Mara", 0, "spatial", now, None))
    qi("INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) "
       "VALUES(?,?,?,?,?)", (chat, ids[MARA], bubble, "active", "{}"))
    wset(chat, "scene", _scene())
    wset(chat, "simulation_clock", dict(CLOCK))
    wset(chat, "known", {ELIAS: [PLAYER, PELL, NELL], PELL: [PLAYER, ELIAS],
                         NELL: [ELIAS], PLAYER: [ELIAS, PELL]})
    # Nell went to sleep three hours before the skip; Otto is sedated.
    for subject, level, started in ((NELL, "asleep", 78466.0 - 3 * 3600.0),
                                    (OTTO, "sedated", 78000.0)):
        cond = {"condition_id": f"c_{subject.split()[0]}", "subject_id": subject,
                "kind": "awareness", "state": {"level": level, "cause": "test"},
                "started_at_seconds": started, "active": 1}
        qi("INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
           "started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)",
           (cond["condition_id"], chat, subject, "awareness", started, None, None,
            json.dumps(cond), 1))
    prev = qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (chat, 7, "By the middle of the afternoon ...", now))
    turn = qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (chat, 8, "Two days later the wind gets up from the west ...", now))
    from agents.storage import save_step
    save_step(prev, "perception_outcome", "Perception", 6, {
        "views": {str(ids[ELIAS]): "Rhona stands at the foot of the stair, looking up."},
        "observations": {str(ids[ELIAS]): []}})

    def context(interp=None):
        from story.scene import active_cast
        ctx = PipelineContext(
            chat=ChatData(id=chat, name="The Lamp Room", persona_id=persona,
                          lorebook_id=None, scenario="", created=now),
            turn=TurnData(id=turn, chat_id=chat, idx=8,
                          player_input="Two days later ...", created=now),
            cast=active_cast(chat), input="Two days later ...")
        ctx.director_interpret = interp if interp is not None else _interp(ids)
        return ctx

    return {"chat": chat, "ids": ids, "turn": turn, "context": context}


def _skip_block(hours=None):
    """`{days: 2, until_phase: morning}`, solved as interpret solves it."""
    from world.day_cycle import seconds_until
    if hours is not None:
        return {"duration_seconds": hours * 3600.0}
    return {"days": 2, "until_phase": "morning",
            "duration_seconds": seconds_until(HOUR0, phase="morning", days=2)}


def _interp(ids, block=None, offers=None, player_placed_before=False):
    block = block or _skip_block()
    steps = [{"chrono_id": 1, "stage": "interpret", "patch": {"time": dict(block)}},
             {"chrono_id": 2, "stage": "interpret",
              "patch": {"positions": {PLAYER: "kitchen"}}}]
    if player_placed_before:
        steps = [{"chrono_id": 1, "stage": "interpret",
                  "patch": {"positions": {PLAYER: "lamp_room"}}},
                 {"chrono_id": 2, "stage": "interpret", "patch": {"time": dict(block)}}]
    return {
        "state_assertions": {"time": dict(block), "causal_steps": steps,
                             "positions": {PLAYER: "kitchen"}},
        "onset_state_assertions": {"positions": {PLAYER: "kitchen"}},
        "causal_ledger": [{"chrono_id": 1, "seconds": 0.0, "commitment": "asserted"},
                          {"chrono_id": 2, "seconds": 120.0, "commitment": "asserted"}],
        "flow": {"reactors": [], "tom_triggers": []},
        "authorial_offers": offers if offers is not None else [
            {"subject_id": ids[ELIAS], "source": "player",
             "proposition": "you come down from the first watch and sit across "
                            "the kitchen table from Rhona with your tea"}],
    }


def _answers(by_name):
    """A stub of the model seam: each asked mind answers with the probe's
    real answer for it, and every call is recorded."""
    calls = []

    def model(role, step_key, system, payload, **kwargs):
        name = payload["self"]["name"]
        calls.append({"role": role, "step_key": step_key, "name": name,
                      "system": system, "payload": copy.deepcopy(payload)})
        answer = by_name.get(name)
        if answer is None:
            raise RuntimeError("no answer")
        return copy.deepcopy(answer)

    return model, calls


def _jev(picks):
    """The decision model, made deterministic: a place or thing question
    whose quoted words are a key of `picks` gets that option, any other
    `none`, and every other question nothing (each caller fails open)."""
    asked = []

    def override(state, questions):
        asked.append(sorted(k for k in questions if k.startswith(("place:", "thing:"))))
        out = {}
        for key, question in questions.items():
            if not key.startswith(("place:", "thing:")):
                continue
            pick = "none"
            for words, option in picks.items():
                if f'"{words}"' in question["instructions"]:
                    pick = next((k for k, v in question["criteria"].items()
                                 if v == option), "none")
            out[key] = {"type": "choice", "choice": pick,
                        "probabilities": {pick: 0.9}}
        return out

    return override, asked


ELIAS_PICKS = {"bedroom": "Elias's Room", "lamp room": "The Lamp Room",
               "lamp room and kitchen": "The Lamp Room",
               "lamp room and hall": "The Lamp Room", "hall and store": "The Hall",
               "hall and lamp room": "The Hall", "kitchen": "The Kitchen",
               "kitchen and lamp room": "The Kitchen"}


def _run_stage(story, monkeypatch, by_name=None, picks=None, interp=None):
    from agents import skip_stage as skip_lives
    from llm import decisions
    model, calls = _answers(by_name if by_name is not None else {
        ELIAS: PROBE["elias_two_days"]["answer"],
        PELL: PROBE["pell_three_days"]["answer"],
        NELL: PROBE["nell_night"]["answer"]})
    override, asked = _jev(picks if picks is not None else ELIAS_PICKS)
    monkeypatch.setattr(skip_lives, "_agent_json", model)
    monkeypatch.setattr(decisions, "OVERRIDE", override)
    ctx = story["context"](interp)
    out = skip_lives.skip_lives(ctx, 0)
    return ctx, out, calls, asked


# --------------------------------------------------------------------------
# When the stage runs
# --------------------------------------------------------------------------

def _plan_keys(interp, **kwargs):
    from agents.runtime import build_plan
    return [key for key, _ in build_plan(interp, [], **kwargs)]


def test_the_stage_is_planned_only_for_a_kept_skip_of_an_hour_or_more():
    """`skip_lives` sits between the compiler and onset perception when the
    input's KEPT skip passes at least `SKIP_LIVED_SECONDS`; never for a
    shorter one, a block that places the beat on the clock instead of
    passing time, an input that passed none, or a bubble's own beat."""
    ids = {ELIAS: 1}
    keys = _plan_keys(_interp(ids))
    assert keys[:4] == ["director_interpret", "compile_world_context",
                        "skip_lives", "perception_act"]
    short = _interp(ids, block={"duration_seconds": itin.SKIP_LIVED_SECONDS - 1})
    assert "skip_lives" not in _plan_keys(short)
    exact = _interp(ids, block={"duration_seconds": itin.SKIP_LIVED_SECONDS})
    assert "skip_lives" in _plan_keys(exact)
    placed = _interp(ids)
    placed["state_assertions"]["time"] = {"elapsed_seconds": 90000.0,
                                         "duration_seconds": 7200.0}
    assert "skip_lives" not in _plan_keys(placed)
    assert "skip_lives" not in _plan_keys({"flow": {"reactors": []}})
    assert "skip_lives" not in _plan_keys(_interp(ids), offscreen=True)


# --------------------------------------------------------------------------
# a. Ask
# --------------------------------------------------------------------------

def test_one_call_per_asked_mind_and_the_player_is_never_asked(story, monkeypatch):
    """Every registered cast member of the frame is asked -- active, asleep
    and dormant alike -- one call each on its own tier role, with its
    ordinary payload plus the `skip` block; never the player, never a mind
    in a bubble of its own, never a body the story holds sedated."""
    _ctx, out, calls, _asked = _run_stage(story, monkeypatch)
    by_name = {c["name"]: c for c in calls}
    assert sorted(by_name) == sorted([ELIAS, PELL, NELL])
    assert all(c["step_key"] == "character_skip" for c in calls)
    assert len(calls) == 3
    assert {by_name[ELIAS]["role"], by_name[PELL]["role"]} == {
        "character_major", "character_mid"}
    payload = by_name[ELIAS]["payload"]
    # The ordinary payload, whole: who it is, what it remembers, what last
    # reached it -- and not the beat's own decision block.
    assert {"self", "memory", "perception", "skip"} <= set(payload)
    assert "decision" not in payload
    skip = payload["skip"]
    assert skip["length"] == {"days": 1, "hours": 17}
    assert skip["now"] == "afternoon"
    # The offers sit under the stretch's END: the account's events happen at
    # the far end (fix lane B3, the second replay's turn 26).
    assert skip["until"] == {"day": 2, "part_of_day": "morning", "offers": [
        "you come down from the first watch and sit across the kitchen table "
        "from Rhona with your tea"]}
    assert "offers" not in skip
    assert skip["parts_of_day"][0] == "night" and "evening" in skip["parts_of_day"]
    assert by_name[PELL]["payload"]["skip"]["until"]["offers"] == []
    assert by_name[NELL]["payload"]["skip"]["asleep_now"] is True
    assert skip["asleep_now"] is False
    assert skip["where_you_are"] == "The Lamp Room"
    assert "{name}" not in by_name[ELIAS]["system"] and ELIAS in by_name[ELIAS]["system"]
    assert sorted(out["minds"]) == sorted([ELIAS, PELL, NELL])
    assert PLAYER not in out["minds"]


# --------------------------------------------------------------------------
# b. The itinerary
# --------------------------------------------------------------------------

def _span_two_days():
    from world.day_cycle import seconds_until
    return itin.Span(78466.0, 78466.0 + seconds_until(HOUR0, phase="morning", days=2),
                     HOUR0, 24.0)


def test_a_plan_that_runs_past_its_span_ends_where_the_span_does():
    """Asked only "until morning", the probe's farm daughter planned the
    whole of the next day. The stretches are clipped to the span: nothing
    she planned after it is in her itinerary, and her night is all there."""
    from world.day_cycle import seconds_until
    start_hour = 23.0
    span = itin.Span(1000.0, 1000.0 + seconds_until(start_hour, phase="morning"),
                     start_hour, 24.0)
    stretches = itin.expand_itinerary(PROBE["nell_night"]["answer"], span)
    assert stretches[0]["from_s"] == span.from_s
    assert stretches[-1]["until_s"] == span.until_s
    assert all(span.from_s <= s["from_s"] < s["until_s"] <= span.until_s
               for s in stretches)
    # Her plan's forenoon, dinner and evening -- the overrun -- are gone.
    doings = " ".join(s["doing"] for s in stretches)
    assert "forenoon" not in doings and "Dinner for whoever is in" not in doings
    # ...and the last thing she does is where she said the stretch leaves her.
    assert stretches[-1]["where_text"] == "Hallow Farm — the kitchen"
    assert "morning fire" in stretches[-1]["doing"]


def test_the_routine_repeats_each_day_and_the_plan_lays_over_it():
    """One ordinary day, repeated across the span; each plan entry laid over
    what it covers; `at_the_end` over the last moments; and every moment of
    the span covered once. The keeper's routine is the probe's; his plan is
    written as a mind told the hour writes it, by day and part of the day."""
    span = _span_two_days()
    answer = copy.deepcopy(PROBE["elias_two_days"]["answer"])
    answer["plan"] = [
        {"day": 0, "from": "dusk", "until": "evening", "where": "lamp room",
         "doing": "evening round with Carrick present for the first time",
         "why": "this is where he will see what she knows", "with": ["Rhona Carrick"]},
        {"day": 1, "from": "morning", "until": "midday", "where": "lamp room and hall",
         "doing": "continue examining the new mechanism alongside the old",
         "why": "he wants it judged on its merits"}]
    stretches = itin.expand_itinerary(answer, span)
    for a, b in zip(stretches, stretches[1:]):
        assert a["until_s"] == pytest.approx(b["from_s"])
    sleeps = [s for s in stretches if s["asleep"]]
    assert len(sleeps) == 2 and all(s["where_text"] == "bedroom" for s in sleeps)
    round_ = [s for s in stretches if s["doing"].startswith("evening round")]
    assert len(round_) == 1 and span.day_of(round_[0]["from_s"]) == 0
    assert span.phase_at(round_[0]["from_s"]) == "dusk"
    day1_morning = [s for s in stretches
                    if span.day_of(s["from_s"]) == 1 and span.phase_at(s["from_s"]) == "morning"]
    assert day1_morning and day1_morning[0]["doing"].startswith(
        "continue examining the new mechanism")
    assert day1_morning[0]["why"]
    # The routine's evening round on day 0 was laid over by the plan's.
    assert not [s for s in stretches if span.day_of(s["from_s"]) == 0
                and span.phase_at(s["from_s"]) == "dusk" and s is not round_[0]]
    assert stretches[-1]["where_text"] == "kitchen"
    assert stretches[-1]["until_s"] == span.until_s
    assert stretches[-1]["until_s"] - stretches[-1]["from_s"] == pytest.approx(
        itin.AT_THE_END_SECONDS)


def test_a_plan_is_read_in_its_own_order_against_the_day():
    """The stretch asked about lies AHEAD, and a plan is written in order.
    Asked in the small hours, the farm daughter wrote every entry as day 0
    and ran round from "sit up by the fire" to "night until dawn: sleep" --
    her bedtime is the NEXT night, not the night she was asked in, and the
    pre-dawn she rises in is the one a few hours off."""
    from world.day_cycle import seconds_until
    hour = (1.25 + 212.0 / 3600.0) % 24.0          # the house story's clock
    span = itin.Span(212.0, 212.0 + seconds_until(hour, phase="morning"), hour, 24.0)
    stretches = itin.expand_itinerary(PROBE["nell_night"]["answer"], span)
    first = stretches[0]
    assert first["from_s"] == span.from_s and not first["asleep"]
    assert first["doing"].startswith("Sit up by the fire")
    pre_dawn = [s for s in stretches if span.phase_at(s["from_s"]) == "pre-dawn"]
    assert pre_dawn and pre_dawn[0]["doing"].startswith("Wake before the house")
    assert not any(s["asleep"] for s in stretches)


def test_an_answer_that_says_nothing_is_the_default_day():
    """Silence is sleep: asleep through the resting parts of the day where
    it stands, and otherwise awake where it stands."""
    from world.day_cycle import RESTING_PHASES
    span = _span_two_days()
    assert itin.expand_itinerary(None, span) == []
    assert itin.expand_itinerary({"routine": [], "plan": []}, span) == []
    day = itin.default_day(span)
    assert day[0]["from_s"] == span.from_s and day[-1]["until_s"] == span.until_s
    for stretch in day:
        middle = (stretch["from_s"] + stretch["until_s"]) / 2.0
        assert stretch["asleep"] == (span.phase_at(middle) in RESTING_PHASES)
        assert stretch["where_text"] == ""
    assert [s["asleep"] for s in day] == [False, True, False, True, False]


def test_a_long_skip_is_laid_out_over_its_last_days_only():
    """BOUNDED BY CONSTRUCTION: "years later" is not lived hour by hour. The
    span's last `SKIP_DAYS_LAID` days are laid out day by day -- at most one
    stretch per part of the day -- and what came before them is one stretch
    where the mind stood. A routine, the default day and a runaway plan alike."""
    from world.day_cycle import PHASE_NAMES
    years = itin.Span(0.0, 10 * 365 * 86400.0, 13.5, 24.0)
    bound = (itin.SKIP_DAYS_LAID + 2) * len(PHASE_NAMES) + 4
    day = itin.default_day(years)
    assert len(day) <= bound and day[-1]["until_s"] == years.until_s
    assert day[0]["from_s"] == 0.0 and day[0]["until_s"] == pytest.approx(
        years.until_s - itin.SKIP_DAYS_LAID * 86400.0)
    answer = copy.deepcopy(PROBE["isolde_week"]["answer"])
    answer["plan"] = answer["plan"] * 400
    stretches = itin.expand_itinerary(answer, years)
    assert len(stretches) <= bound + itin.SKIP_ENTRIES_READ
    assert stretches[0]["from_s"] == 0.0 and stretches[-1]["until_s"] == years.until_s
    for a, b in zip(stretches, stretches[1:]):
        assert a["until_s"] == pytest.approx(b["from_s"])


def test_a_failed_ask_lives_the_default_day(story, monkeypatch):
    _ctx, out, _calls, _asked = _run_stage(story, monkeypatch, by_name={
        ELIAS: PROBE["elias_two_days"]["answer"], PELL: {}})
    assert out["minds"][PELL]["source"] == "default"
    assert out["minds"][NELL]["source"] == "default"      # the model raised
    assert out["minds"][NELL]["answer"] is None
    nell = out["minds"][NELL]
    # She stands where she was -- asleep in the spare room -- and sleeps
    # through each night of the span.
    assert {row["room"] for row in nell["log"]} == {"spare_room"}
    assert nell["log"][0]["asleep"] is False or nell["log"][0]["asleep"] is True
    assert any(row["asleep"] for row in nell["log"])
    assert out["minds"][ELIAS]["source"] == "asked"


# --------------------------------------------------------------------------
# b. The places
# --------------------------------------------------------------------------

def test_places_resolve_exactly_then_by_one_decision_request_then_off_the_map(monkeypatch):
    """A written place is the room it names EXACTLY among the places the
    mind knows; failing that, ONE decision-model request per mind over those
    same places plus "none of these"; failing both, an off-map label -- its
    own words, a place the world does not hold. The keeper never stood in
    his own bedroom this story, and still names it: the building he stands
    in is a place he knows."""
    from agents import skip_stage as skip_lives
    from llm import decisions
    override, asked = _jev({"bedroom": "Elias's Room"})
    monkeypatch.setattr(decisions, "OVERRIDE", override)
    scene = _scene()
    state = _graph("landing", "stair", "hall", "kitchen", "lamp_room")
    known = skip_lives.known_places(scene, state, "lamp_room")
    assert "bedroom_elias" in known and "store" in known
    assert "mainland" not in known and "skerry" not in known
    stretches = [itin._stretch(0, 10, {"where": w}, itin.KIND_PLAN) for w in (
        "The Kitchen", "bedroom", "the harbour pub", "the kitchen")]
    placed, _held, record = skip_lives.resolve_mind(
        ELIAS, stretches, scene, state, "lamp_room", {})
    assert [(s["room"], s["away"]) for s in placed] == [
        ("kitchen", None), ("bedroom_elias", None), (None, "the harbour pub"),
        ("kitchen", None)]
    # One request, asking only what exact matching left.
    assert asked == [["place:0", "place:1"]]
    assert record["exact"] == {"The Kitchen": "kitchen", "the kitchen": "kitchen"}


def test_a_place_named_whole_is_known_and_words_beyond_a_name_are_read(monkeypatch):
    """A room the world holds whose whole name stands in the mind's own
    words is a place it KNOWS, though its map never saw it: the probe's quay
    hand ends his night "Saltreach quay, among the stacked cargo and the
    bollards", and the world's Saltreach Quay -- two doors from the tavern
    his story opened in -- is offered, where off the map would make him
    vanish from a quay that holds him. But words that carry a name and MORE
    are read by the decision model, never matched by the name: they may be
    that room, either of two, or somewhere in or beside it the world does
    not hold ("Gull and Anchor, rented room upstairs" put a lodger to sleep
    at a taproom table when the name alone was read -- offline, the tavern
    night). Only a whole name is matched; and the inside of a thing is no
    place its name puts a body: the boatman's "the Mary Ann loaded and made
    fast" is not his boat's cabin."""
    from agents import skip_stage as skip_lives
    from llm import decisions
    texts = ["Saltreach quay, among the stacked cargo and the bollards",
             "The Kitchen, the larder behind it", "from the hall to the kitchen",
             "The quay, harbour town -- the Mary Ann loaded and made fast",
             "Saltreach Quay"]
    override, asked = _jev({texts[0]: "Saltreach Quay"})
    monkeypatch.setattr(decisions, "OVERRIDE", override)
    scene = _scene()
    scene["rooms"]["quay"] = {"name": "Saltreach Quay", "exposure": "open",
                              "adjacent": [_edge("landing")]}
    scene["rooms"]["boat_cabin"] = {"name": "The Mary Ann", "parent_entity": "mary_ann",
                                    "adjacent": [_edge("landing")]}
    stretches = [itin._stretch(0, 10, {"where": t}, itin.KIND_PLAN) for t in texts]
    placed, _h, record = skip_lives.resolve_mind(
        PELL, stretches, scene, _graph("landing"), None, {})
    assert placed[0]["room"] == "quay"                    # read, and the quay
    assert (placed[1]["room"], placed[1]["away"]) == (None, texts[1])
    assert placed[2]["room"] is None and placed[3]["room"] is None
    assert placed[4]["room"] == "quay"                    # a whole name: matched
    assert {"quay", "kitchen", "hall"} <= set(record["known"])
    assert "boat_cabin" not in record["known"]
    assert asked == [["place:0", "place:1", "place:2", "place:3"]]


def test_a_planned_rooms_purpose_rides_beside_its_name(monkeypatch):
    """What a room is FOR is how a mind's own word for it is read: the
    decision model is offered "Elias's Room" with the plan's purpose beside
    it, so "bedroom" has something to meet."""
    from agents import skip_stage as skip_lives
    from llm import decisions
    offered = []

    def override(state, questions):
        offered.extend(q["criteria"] for q in questions.values())
        return {}
    monkeypatch.setattr(decisions, "OVERRIDE", override)
    scene = _scene()
    scene["rooms"]["bedroom_elias"]["purpose"] = (
        "One of the tower's two narrow bedrooms, off the kitchen: a bunk, a "
        "chest and a small window.")
    stretch = itin._stretch(0, 10, {"where": "bedroom"}, itin.KIND_ROUTINE)
    skip_lives.resolve_mind(ELIAS, [stretch], scene,
                            _graph("kitchen", "lamp_room"), "lamp_room", {})
    (criteria,) = offered
    assert any(v.startswith("Elias's Room (One of the tower's two narrow bedrooms")
               for v in criteria.values())
    assert "The Kitchen" in criteria.values() and "none" in criteria


def test_a_weak_or_failed_decision_leaves_the_place_off_the_map(monkeypatch):
    from agents import skip_stage as skip_lives
    from llm import decisions

    def weak(state, questions):
        return {k: {"type": "choice", "choice": "p0", "probabilities": {"p0": 0.3}}
                for k in questions}
    monkeypatch.setattr(decisions, "OVERRIDE", weak)
    stretch = itin._stretch(0, 10, {"where": "upstairs"}, itin.KIND_PLAN)
    placed, _h, _r = skip_lives.resolve_mind(ELIAS, [stretch], _scene(),
                                             _graph("kitchen"), "kitchen", {})
    assert placed[0]["away"] == "upstairs" and placed[0]["room"] is None

    def down(state, questions):
        raise decisions.DecisionError("unreachable")
    monkeypatch.setattr(decisions, "OVERRIDE", down)
    placed, _h, record = skip_lives.resolve_mind(ELIAS, [stretch], _scene(),
                                                 _graph("kitchen"), "kitchen", {})
    assert placed[0]["away"] == "upstairs" and "jev_failed" in record


# --------------------------------------------------------------------------
# c. The executor
# --------------------------------------------------------------------------

def _placed(start, end, room=None, away=None, **fields):
    entry = {"where": fields.pop("where", room or away or ""), **fields}
    out = itin._stretch(start, end, entry, fields.get("kind", itin.KIND_ROUTINE))
    out.update(room=room, away=away)
    return out


def test_a_walk_takes_its_time_from_the_start_of_the_stretch_it_walks_to():
    """Between rooms the mind walks the route a person walks, and each leg's
    edge seconds (`charter_move.edge_seconds`) come out of the start of the
    stretch it walks to."""
    from world.charter_move import edge_seconds
    scene = _scene()
    stretches = [_placed(0.0, 3600.0, room="kitchen"),
                 _placed(3600.0, 7200.0, room="stair")]
    log, far = itin.live_through(stretches, scene=scene, start_room="lamp_room")
    first = edge_seconds(scene, "lamp_room", "kitchen")
    second = edge_seconds(scene, "kitchen", "hall") + edge_seconds(scene, "hall", "stair")
    assert log[0]["from_s"] == pytest.approx(first) and log[0]["room"] == "kitchen"
    assert log[1]["from_s"] == pytest.approx(3600.0 + second)
    assert first > 0 and second > first
    assert far == {"room": "stair", "away": None, "asleep": False,
                   "asleep_since_s": None, "left_from": None}


def test_a_stretch_the_world_cannot_carry_out_fails_with_its_reason():
    """No way there: `no_route`, and the mind stays where it stood -- its row
    says where it meant to be in `meant`, and leaves `where_text` for
    `place_words` to say where it WAS. A way only past a fastened door:
    `shut_way`. A thing the stretch uses that the mind does not have on it:
    `not_held` -- it went, and the thing was not on it, named in
    `missing`. A thing it has: `done` (what a stretch uses never makes it
    unknown, fix lane B3)."""
    scene = _scene()
    stretches = [_placed(0.0, 100.0, room="skerry", kind=itin.KIND_PLAN),
                 _placed(100.0, 200.0, room="store", kind=itin.KIND_PLAN),
                 _placed(200.0, 300.0, room="hall", kind=itin.KIND_PLAN,
                         uses=["the sealed letter"]),
                 _placed(300.0, 400.0, room="hall", kind=itin.KIND_PLAN,
                         uses=["the station log"])]
    held = {"logbook": "the station log"}
    log, far = itin.live_through(
        stretches, scene=scene, start_room="kitchen",
        uses_held=lambda thing: itin.held_exactly(thing, held))
    assert [(r["outcome"], r["reason"], r["room"]) for r in log] == [
        ("failed", "no_route", "kitchen"),
        ("failed", "shut_way", "kitchen"),
        ("failed", "not_held", "hall"),
        ("done", None, "hall")]
    assert log[0]["meant"] == "skerry" and log[0]["where_text"] == ""
    assert itin.place_words(log, scene)[0]["where_text"] == "The Kitchen"
    assert log[2]["missing"] == ["the sealed letter"] and log[2]["meant"] is None
    assert far["room"] == "hall"


def test_a_way_longer_than_its_stretch_is_too_far_and_ends_on_the_way():
    """A walk the stretch runs out before fails `too_far` -- the town
    charter's word for a way so long the stretch was spent walking it -- and
    leaves the body as far along the way as the stretch carried it; the next
    stretch walks on from there."""
    from world.charter_move import edge_seconds
    scene = _scene()
    first = edge_seconds(scene, "kitchen", "hall")
    second = first + edge_seconds(scene, "hall", "stair")
    short = (first + second) / 2.0
    stretches = [_placed(0.0, short, room="landing"),
                 _placed(short, short + 3600.0, room="landing")]
    log, far = itin.live_through(stretches, scene=scene, start_room="kitchen")
    assert [(r["outcome"], r["reason"], r["room"]) for r in log] == [
        ("failed", "too_far", "hall"), ("done", None, "landing")]
    assert log[1]["from_s"] == pytest.approx(
        short + edge_seconds(scene, "hall", "stair")
        + edge_seconds(scene, "stair", "landing"))
    assert far["room"] == "landing"


def test_one_outcome_rule_and_one_reason_vocabulary_for_both_executors():
    """`failed` with its reason; else a sleep is `done`; else a stretch whose
    success waits on somebody (`with`) or on a world off the map nobody
    simulates is `not_known`; else `done` -- what it uses never makes it
    unknown (fix lane B3) -- the rule the town charter's executor writes
    (`world/charter_skip`), whose reasons are all the stage's too."""
    from world import charter_skip
    scene = _scene()
    stretches = [_placed(0.0, 100.0, room="kitchen", kind=itin.KIND_PLAN),
                 _placed(100.0, 200.0, room="kitchen", **{"with": [PLAYER]}),
                 _placed(200.0, 300.0, room="kitchen", uses=["the kettle"]),
                 _placed(300.0, 400.0, room="kitchen", asleep=True,
                         **{"with": [PLAYER]}),
                 _placed(400.0, 500.0, away="the harbour pub"),
                 _placed(500.0, 600.0, away="my rooms", asleep=True),
                 _placed(600.0, 700.0)]          # where it stands: still away
    log, far = itin.live_through(stretches, scene=scene, start_room="kitchen")
    assert [r["outcome"] for r in log] == [
        "done", "not_known", "done", "done", "done", "done", "done"]   # away never makes a mind's own doing unknown (2026-10-22)
    assert far == {"room": None, "away": "my rooms", "asleep": False,
                   "asleep_since_s": None, "left_from": "kitchen"}
    assert set(charter_skip.FAILURE_REASONS) <= set(itin.FAILURE_REASONS)


def test_the_towns_rows_carry_what_only_the_stage_knows(story, monkeypatch):
    """Where a town charter holds the body, its own run lives the stretch
    (`world.charter_skip.live_in_charter`), asked first for every mind with
    the chat, the mind's itinerary and the span; its log and far end are
    that mind's -- ONE log, with what only this stage knows laid over the
    town's rows: the weather where each row stood, the holding check, the
    player and the other asked minds beside the town's residents in `seen`,
    and a sleep's true start. A mind it answers None for is lived by the
    stage's own executor."""
    from world import charter_skip
    calls = []

    def runner(cid, scene, name, itinerary, span):
        calls.append((cid, name, [dict(s) for s in itinerary], dict(span)))
        if name == ELIAS:
            rows = [{"from_s": s["from_s"], "until_s": s["until_s"],
                     "room": s["room"], "away": s["away"],
                     "where_text": s["where_text"], "doing": s["doing"],
                     "asleep": s["asleep"],
                     "seen": [{"who": "a fisherman", "doing": "passing through"}],
                     "weather": None, "outcome": "done", "reason": None}
                    for s in itinerary]
            return rows, {"room": rows[-1]["room"], "away": rows[-1]["away"],
                          "asleep": rows[-1]["asleep"], "asleep_since_s": None}
        if name == NELL:
            return ([{"from_s": span["from_s"], "until_s": span["until_s"],
                      "room": "spare_room", "away": None, "where_text": "",
                      "doing": "", "asleep": True, "seen": [], "weather": None,
                      "outcome": "done", "reason": None}],
                    {"room": "spare_room", "away": None, "asleep": True,
                     "asleep_since_s": span["from_s"]})
        return None
    monkeypatch.setattr(charter_skip, "live_in_charter", runner)
    # A lantern the world holds, locked away in the store: out of reach on
    # the landing (a thing the world holds nowhere is never missing), and a
    # thing a body carries (only such a thing is ever missing, fix lane B5).
    from core.db import wget, wset
    scene = wget(story["chat"], "scene")
    scene["entities"]["lantern"] = {"name": "a storm lantern", "kind": "light",
                                    "portable": True}
    scene["positions"]["lantern"] = "store"
    wset(story["chat"], "scene", scene)
    answer = {"plan": [
        {"day": 0, "from": "afternoon", "until": "dusk", "where": "The Landing",
         "doing": "watches the channel", "uses": ["a storm lantern"]},
        {"day": 0, "from": "dusk", "until": "evening", "where": "The Lamp Room",
         "doing": "lights the lamp"}]}
    _ctx, out, _calls, _asked = _run_stage(
        story, monkeypatch, interp=_interp(story["ids"], player_placed_before=True),
        by_name={ELIAS: answer, PELL: PROBE["pell_three_days"]["answer"],
                 NELL: PROBE["nell_night"]["answer"]})
    assert {name for _c, name, _i, _s in calls} == set(out["minds"])
    assert {c for c, *_ in calls} == {story["chat"]}
    for _c, name, itinerary, span in calls:
        assert itinerary == out["minds"][name]["itinerary"] and span == out["span"]
    elias = out["minds"][ELIAS]["log"]
    landing = [r for r in elias if r["room"] == "landing"]
    # The decision model answers no `without` question here (`_jev`), and no
    # answer never invents a failure (fix lane B5): the rows are told as far
    # as they went, what they lacked kept.
    assert landing and all((r["outcome"], r["reason"]) == ("not_known", None)
                           and r["missing"] == ["a storm lantern"] for r in landing)
    assert all(r["weather"] for r in landing)          # the sky it stood under
    lamp = [r for r in elias if r["room"] == "lamp_room"]
    assert lamp and all({"who": "a fisherman", "doing": "passing through"} in r["seen"]
                        and {"who": PLAYER, "doing": ""} in r["seen"] for r in lamp)
    assert all(r["where_text"] for r in elias if r["room"])
    nell = out["minds"][NELL]["far_end"]
    assert nell["asleep"] and nell["asleep_since_s"] == pytest.approx(78466.0 - 3 * 3600.0)
    assert len(out["minds"][PELL]["log"]) > 1          # its own executor


def test_company_reaches_each_observer_as_its_doing_never_its_why():
    """Two minds in one room -- or at one off-map label, each naming the
    other in its own `with` -- over time that overlaps each receive the
    other's `doing`, named as the OBSERVER knows them; never the other's
    `why`; and nobody reaches a mind asleep. (The label alone was enough
    until 2026-11-01; world_offscreen_time F1 measured two minds each "home"
    told each other's doings, so D and E now name each other.)"""
    def row(start, end, room=None, away=None, doing="", why="", asleep=False):
        return {"from_s": start, "until_s": end, "room": room, "away": away,
                "where_text": room or away or "", "doing": doing, "why": why,
                "asleep": asleep, "seen": [], "weather": None,
                "outcome": "done", "reason": None}
    logs = {"A": [row(0, 100, room="kitchen", doing="pours the tea",
                      why="to steady her")],
            "B": [row(50, 150, room="kitchen", doing="reads the log",
                      why="looking for the March entry")],
            "C": [row(0, 100, room="hall", doing="sweeps")],
            "D": [dict(row(0, 100, away="The Harbour Pub", doing="drinks"),
                       **{"with": ["E"]})],
            "E": [dict(row(0, 100, away="the harbour pub", doing="listens"),
                       **{"with": ["D"]}),
                  row(100, 200, room="kitchen", asleep=True, doing="sleeps")]}
    known = {"A": {"B"}, "B": set(), "D": {"E"}, "E": set()}
    itin.share_company(logs, lambda o, other: other if other in known.get(o, ())
                       else "the stranger")
    assert logs["A"][0]["seen"] == [{"who": "B", "doing": "reads the log"}]
    # A sleeper is seen where it sleeps; it sees nobody.
    assert logs["B"][0]["seen"] == [{"who": "the stranger", "doing": "pours the tea"},
                                    {"who": "the stranger", "doing": "sleeps"}]
    assert logs["C"][0]["seen"] == []
    assert logs["D"][0]["seen"] == [{"who": "E", "doing": "listens"}]
    assert logs["E"][0]["seen"] == [{"who": "the stranger", "doing": "drinks"}]
    assert logs["E"][1]["seen"] == []
    assert "steady" not in json.dumps(logs["B"]) .split('"seen"')[1]


def _two_in_the_kitchen():
    """Elias and Nell keep the kitchen through the evening; Elias waits on
    the boatman by name, and Pell and Nell both drink at the harbour pub."""
    return {
        ELIAS: {"plan": [{"day": 0, "from": "dusk", "until": "night",
                          "where": "kitchen", "with": [PLAYER],
                          "doing": "sits at the table, watching the door for Pell Hardacre",
                          "why": "he means to have it out with Rhona tonight"}],
                "at_the_end": {"where": "kitchen", "doing": "tea", "asleep": False}},
        NELL: {"plan": [{"day": 0, "from": "dusk", "until": "night",
                         "where": "the kitchen", "doing": "mends a sock by the fire",
                         "why": "she will not go up while he is still down"},
                        {"day": 1, "from": "evening", "until": "night",
                         "where": "the harbour pub", "doing": "nurses a cider"}],
               "at_the_end": {"where": "the kitchen", "doing": "lays the fire",
                              "asleep": False}},
        PELL: {"plan": [{"day": 1, "from": "evening", "until": "night",
                         "where": "the harbour pub", "doing": "plays dominoes"}]},
    }


def test_the_stage_shares_company_by_each_observers_recognition(story, monkeypatch):
    _ctx, out, _calls, _asked = _run_stage(story, monkeypatch, by_name=_two_in_the_kitchen())
    elias = out["minds"][ELIAS]["log"]
    nell = out["minds"][NELL]["log"]
    pell = out["minds"][PELL]["log"]
    # Elias knows Nell; Nell knows Elias -- and not the boatman he names.
    seen_by_elias = [s for r in elias for s in r["seen"]]
    assert {"who": NELL, "doing": "mends a sock by the fire"} in seen_by_elias
    seen_by_nell = [s for r in nell for s in r["seen"]]
    by_elias = [s for s in seen_by_nell if s["who"] == ELIAS]
    assert by_elias and all("Pell" not in s["doing"] for s in by_elias)
    assert all("have it out" not in json.dumps(r["seen"]) for r in nell)
    # At the harbour pub, an off-map label, Pell and Nell are strangers who
    # never named each other: the same words for a place the world does not
    # hold are no evidence they stood in one place (world_offscreen_time F1,
    # 2026-11-01 -- this asserted the label rule, under which two minds each
    # "home" were told each other's doings).
    pub = [s for r in nell if r["away"] == "the harbour pub" for s in r["seen"]]
    assert pub == []
    assert not any(s["doing"] == "nurses a cider"
                   for r in pell for s in r["seen"])
    # The player is not placed by this account, so "with Rhona" is Elias's
    # own side of it: she is in nobody's log.
    assert all(s["who"] != PLAYER for r in elias for s in r["seen"])


def test_the_player_is_placed_only_where_the_account_places_them(story, monkeypatch):
    """The account's typed events, at or before the step that passes over
    the time, place the player through it; then, and only then, a mind
    sharing the room sees them."""
    interp = _interp(story["ids"], player_placed_before=True)
    _ctx, out, _calls, _asked = _run_stage(
        story, monkeypatch, by_name=_two_in_the_kitchen(), interp=interp)
    # The account put Rhona in the lamp room before the two days passed;
    # Elias's own day takes him through the lamp room each dawn.
    answer = {"routine": [{"from": "dawn", "until": "morning", "where": "lamp room",
                           "doing": "trims the wick"}]}
    _ctx, out, _calls, _asked = _run_stage(
        story, monkeypatch, by_name={ELIAS: answer}, interp=interp)
    seen = [s for r in out["minds"][ELIAS]["log"] if r["room"] == "lamp_room"
            for s in r["seen"]]
    assert {"who": PLAYER, "doing": ""} in seen
    assert PLAYER not in out["minds"]


# --------------------------------------------------------------------------
# d. The far end
# --------------------------------------------------------------------------

def _commit(ctx):
    from agents.skip_stage import far_end_for, onset_preview
    from core.db import transaction
    from persist.commit import commit_scene, commit_skip_lives, prepare_scene_commit
    ctx.director_resolve = {"state_diff": {}, "dialogue_log": [],
                            "resolved_event": "", "sequence": []}
    with onset_preview(far_end_for(ctx)):
        prepared = prepare_scene_commit(ctx)
    with transaction():
        commit_scene(ctx, 0, prepared=prepared)
        return commit_skip_lives(ctx, 0)


def test_the_far_end_is_committed(story, monkeypatch):
    """Each mind ends where its last stretch left it -- a move of its own,
    seated one pace inside the door it came by, its old pose, follow and
    station gone; a mind whose day ends off the map is AWAY: dormant, its
    whereabouts typed and kept; and a sleep it woke from is ended."""
    from core.db import q, wget
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch)
    ctx.skip_lives = out
    wrote = _commit(ctx)
    scene = wget(story["chat"], "scene")
    assert scene["positions"][ELIAS] == "kitchen"
    assert scene["stations"][ELIAS]["cell"] != [1, 1]
    assert ELIAS not in (scene.get("poses") or {})
    assert ELIAS not in (scene.get("following") or {})
    assert PELL not in scene["positions"]
    assert scene["positions"]["logbook"] == "kitchen"      # it went with him
    whereabouts = wget(story["chat"], "whereabouts")
    assert whereabouts[PELL]["kind"] == "off_map"
    assert whereabouts[PELL]["label"].startswith("The quay, harbour town")
    assert whereabouts[PELL]["char_id"] == story["ids"][PELL]
    status = {r["char_id"]: r["status"] for r in q("SELECT char_id,status FROM chat_chars")}
    assert status[story["ids"][PELL]] == "dormant"
    assert status[story["ids"][ELIAS]] == "active"
    rows = {r["condition_id"]: r for r in q("SELECT * FROM world_conditions")}
    assert rows["c_Nell"]["active"] == 0            # she woke inside the span
    assert rows["c_Otto"]["active"] == 1            # nobody wakes a sedative
    assert wrote["away"][PELL].startswith("The quay")


def test_the_turn_commit_writes_the_far_end_in_its_transaction(story, monkeypatch):
    """The whole commit, as a turn runs it: the far end lands in the scene
    domain's write and in the skip domain of its own, reported on the turn's
    results; and the beat's memories are queued from the step this stage
    filled (`persist/commit_memory_write.schedule_skip_memories` reads the
    context's `skip_lives`). Background work is held back -- it is queued,
    never run."""
    from core import jobs
    from core.db import q, wget
    from persist.commit import commit_all
    queued = []
    monkeypatch.setattr(jobs, "submit", lambda cid, key, *a, **k: queued.append(key))
    monkeypatch.setattr(jobs, "submit_latest", lambda *a, **k: None)
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch)
    ctx.skip_lives = out
    ctx.director_resolve = {"state_diff": {}, "dialogue_log": [],
                            "resolved_event": "", "sequence": []}
    results = commit_all(ctx, 0)
    results = results.get("results", results)
    assert results["skip_lives"]["away"][PELL].startswith("The quay")
    assert results["skip_lives"]["woke"] == [NELL] or NELL in results["skip_lives"]["away"]
    assert wget(story["chat"], "scene")["positions"][ELIAS] == "kitchen"
    assert PELL in wget(story["chat"], "whereabouts")
    status = {r["char_id"]: r["status"] for r in q("SELECT char_id,status FROM chat_chars")}
    assert status[story["ids"][PELL]] == "dormant"
    assert "skip_memories:%s" % story["turn"] in queued


def _asleep_at_the_end():
    return {ELIAS: {"routine": [{"from": "night", "until": "morning",
                                 "where": "bedroom", "doing": "sleeps in his bunk",
                                 "asleep": True}],
                    "at_the_end": {"where": "bedroom", "doing": "asleep",
                                   "asleep": True}},
            NELL: {"plan": [{"day": 0, "from": "afternoon", "until": "dusk",
                             "where": "the kitchen", "doing": "peels potatoes"}]},
            PELL: {"at_the_end": {"where": "The Mainland", "doing": "mends a net"}}}


def test_a_mind_asleep_at_the_far_end_is_asleep_from_when_its_sleep_began(story, monkeypatch):
    """Asleep at the far end is an awareness row starting when that sleep
    began, so the natural waking floor counts from the right hour; the gates
    read it, so the mind runs no step; and a dormant mind whose day ends in a
    room the world holds is home, active."""
    from agents.runtime import build_plan
    from core.db import q, wget
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch, by_name=_asleep_at_the_end())
    span = _span_two_days()
    far = out["minds"][ELIAS]["far_end"]
    assert far["room"] == "bedroom_elias" and far["asleep"] is True
    night = span.day_start(1) + span.offset_hours("night") * 3600.0
    assert far["asleep_since_s"] == pytest.approx(night)
    # The planner's gate at the far end: named by the Director, he sleeps.
    # (Autonomy 0 plans one step per reactor, so the plan names them.)
    from core.db import wset
    wset(story["chat"], "dialogue_config", {"autonomy": 0})
    interp = dict(ctx.director_interpret, flow={"reactors": [story["ids"][ELIAS]]})
    from agents import skip_stage as skip_lives
    cast = skip_lives.cast_at_far_end(story["chat"], None, ctx.cast, out)
    keys = [k for k, _ in build_plan(interp, cast, chat_id=story["chat"],
                                     turn_idx=8, skip=out)]
    assert "character:%d" % story["ids"][ELIAS] not in keys
    # Nell's day leaves her awake in the kitchen with the player: she is in it.
    assert "character:%d" % story["ids"][NELL] in keys
    assert "character:%d" % story["ids"][ELIAS] in [k for k, _ in build_plan(
        interp, cast, chat_id=story["chat"], turn_idx=8)]
    ctx.skip_lives = out
    ctx.cast = cast
    wrote = _commit(ctx)
    row = q("SELECT * FROM world_conditions WHERE condition_id=?",
            ("skip:%s:elias_thorne:asleep" % story["turn"],), one=True)
    assert row is not None and row["active"] == 1
    assert row["started_at"] == pytest.approx(night)
    assert json.loads(row["payload"])["state"]["level"] == "asleep"
    assert wrote["asleep"] == [ELIAS]
    assert wrote["back"] == [PELL]
    status = {r["char_id"]: r["status"] for r in q("SELECT char_id,status FROM chat_chars")}
    assert status[story["ids"][PELL]] == "active"
    assert wget(story["chat"], "scene")["positions"][PELL] == "mainland"
    assert PELL not in (wget(story["chat"], "whereabouts") or {})


def test_a_sleep_that_runs_on_through_the_stretch_keeps_its_row():
    from agents.skip_stage import FarEnd
    stored = [{"condition_id": "c1", "subject": NELL, "level": "asleep",
               "started_at_seconds": 100.0, "payload": {}}]
    output = {"minds": {NELL: {"far_end": {"room": "spare_room", "away": None,
                                           "asleep": True, "asleep_since_s": 100.0},
                               "log": []}}}
    assert FarEnd(1, output, 9).awareness_changes(stored) == ([], [])
    output["minds"][NELL]["far_end"]["asleep_since_s"] = 5000.0
    ended, started = FarEnd(1, output, 9).awareness_changes(stored)
    assert [r["condition_id"] for r in ended] == ["c1"]
    assert started[0]["started_at_seconds"] == 5000.0
    output["minds"][NELL]["far_end"].update(asleep=False, asleep_since_s=None)
    ended, started = FarEnd(1, output, 9).awareness_changes(stored)
    assert [r["condition_id"] for r in ended] == ["c1"] and started == []


# --------------------------------------------------------------------------
# d. The onset preview
# --------------------------------------------------------------------------

def test_perception_and_the_reactor_gates_read_the_far_end(story, monkeypatch):
    """Onset perception, every character call and the planner's gates read
    the world at the far end -- the keeper in the kitchen with the player --
    while the stored scene still holds him in the lamp room until the
    commit; and the beat plans his turn at the far end."""
    from agents import skip_stage as skip_lives
    from agents.runtime import build_plan, compute_step
    from core.db import wget
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch)
    elias = str(story["ids"][ELIAS])
    before = compute_step("perception_act", ctx, 0)
    assert "The Lamp Room" in before["views"][elias].split(".")[0]
    ctx.skip_lives = out
    ctx.cast = skip_lives.cast_at_far_end(story["chat"], None, ctx.cast, out)
    after = compute_step("perception_act", ctx, 0)
    assert after["views"][elias].startswith("You are in The Kitchen")
    assert any(c["name"] == PLAYER for c in after["company"][elias])
    assert wget(story["chat"], "scene")["positions"][ELIAS] == "lamp_room"
    interp = ctx.director_interpret
    without = [k for k, _ in build_plan(interp, ctx.cast, chat_id=story["chat"], turn_idx=8)]
    at_far_end = [k for k, _ in build_plan(interp, ctx.cast, chat_id=story["chat"],
                                           turn_idx=8, skip=out)]
    assert "interaction_loop" not in without and "interaction_loop" in at_far_end
    # ...and the same plan comes back from the store, as a replay rebuilds it.
    assert at_far_end == [k for k, _ in build_plan(
        copy.deepcopy(interp), ctx.cast, chat_id=story["chat"], turn_idx=8,
        skip=copy.deepcopy(out))]


def test_the_loop_answers_the_plan_it_was_given_at_the_far_end(story, monkeypatch):
    """The planner gave the keeper the loop because his day left him in the
    kitchen with the player; the loop, which reads the Director's list for
    itself, must reach him too and not stop on "no reactors" (the rejoined
    widening's lesson, scratch story 166 idx 13)."""
    import agents.character as character
    from agents.runtime import compute_step
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch)
    ctx.skip_lives = out
    ctx.cast = __import__("agents.skip_stage", fromlist=["x"]).cast_at_far_end(
        story["chat"], None, ctx.cast, out)
    ctx.perception_act = compute_step("perception_act", ctx, 0)
    asked = []

    def model(role, step_key, system, payload, **kwargs):
        asked.append(payload["self"]["name"])
        return {"sequence": [{"do": "sets down the mug", "why": "habit"}], "notebook": []}

    monkeypatch.setattr(character, "_agent_json", model)
    loop = compute_step("interaction_loop", ctx, 0)
    assert loop.get("stop_reason") != "no reactors"
    assert ELIAS in asked


def test_a_resume_plans_the_beat_at_the_far_end(story, monkeypatch):
    """`resume_key_for_turn` rebuilds the plan from the stored steps, the
    skip's included: the step the far end asks for is the one it resumes at."""
    from agents.runtime import resume_key_for_turn
    from agents.storage import save_step
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch)
    for ordn, (key, content) in enumerate((
            ("director_interpret", ctx.director_interpret),
            ("compile_world_context", {"relevant_lore": []}),
            ("skip_lives", out), ("perception_act", {"views": {}}))):
        save_step(story["turn"], key, key, ordn, content)
    assert resume_key_for_turn(story["turn"], story["chat"]) == "interaction_loop"


# --------------------------------------------------------------------------
# e. The far-end payload
# --------------------------------------------------------------------------

def test_a_mind_at_the_far_end_carries_its_own_stretch_as_payload(story, monkeypatch):
    """Each asked mind's call in the skip beat carries its own log as
    `the_stretch_just_passed` -- payload, not memory -- in its own terms
    (the day and the parts of the day, no engine seconds), and the card
    says what it is."""
    import agents.character as character
    from agents import skip_stage as skip_lives
    from agents.runtime import compute_step
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch, by_name=_two_in_the_kitchen())
    ctx.skip_lives = out
    ctx.cast = skip_lives.cast_at_far_end(story["chat"], None, ctx.cast, out)
    captured = {}

    def model(role, step_key, system, payload, **kwargs):
        captured.update(system=system, payload=copy.deepcopy(payload))
        return {"sequence": [{"do": "looks up", "why": "the door"}], "notebook": []}

    monkeypatch.setattr(character, "_agent_json", model)
    compute_step("character:%d" % story["ids"][ELIAS], ctx, 0)
    rows = captured["payload"]["the_stretch_just_passed"]
    assert rows and rows[-1]["where"] == "The Kitchen"
    assert {"day", "from", "until", "where", "doing", "asleep", "seen",
            "weather", "outcome"} <= set(rows[0])
    assert "from_s" not in json.dumps(rows) and "until_s" not in json.dumps(rows)
    assert any(s["who"] == NELL for r in rows for s in r["seen"])
    assert "THE STRETCH JUST PASSED" in captured["system"]
    # A mind the skip did not carry gets none.
    assert skip_lives.stretch_for_payload(ctx, PLAYER) is None


# --------------------------------------------------------------------------
# The step's shape (build spec), and the record's round trips
# --------------------------------------------------------------------------

STRETCH_KEYS = {"from_s", "until_s", "room", "away", "where_text", "doing",
                "asleep", "with", "why", "uses"}
LOG_KEYS = {"from_s", "until_s", "room", "away", "where_text", "doing",
            "asleep", "seen", "weather", "outcome", "reason", "missing", "meant"}


def test_the_step_output_has_the_build_specs_shape(story, monkeypatch):
    """Lane C's memory job reads `minds[*].log` and `span` from the committed
    step: the shape is fixed, and it survives a JSON round trip."""
    _ctx, out, _calls, _asked = _run_stage(story, monkeypatch)
    assert set(out) == {"span", "minds"}
    assert set(out["span"]) == {"from_s", "until_s"}
    assert out["span"]["from_s"] == 78466.0
    assert out["span"]["until_s"] - out["span"]["from_s"] == pytest.approx(
        _skip_block()["duration_seconds"])
    for name, mind in out["minds"].items():
        # ...and what its own work changed (`agents/skip_work.py`): None for a
        # mind with no row to tell, else what was told, what it typed, and
        # what was set aside. The memory job reads none of it.
        assert set(mind) == {"source", "answer", "itinerary", "log", "far_end", "worked"}
        assert mind["worked"] is None or set(mind["worked"]) == {"told", "changes", "record"}
        assert mind["source"] in ("asked", "default")
        assert all(set(s) == STRETCH_KEYS for s in mind["itinerary"])
        assert all(set(r) == LOG_KEYS for r in mind["log"])
        assert all(set(s) == {"who", "doing"} for r in mind["log"] for s in r["seen"])
        assert all(r["outcome"] in ("done", "failed", "not_known") for r in mind["log"])
        assert set(mind["far_end"]) == {"room", "away", "asleep", "asleep_since_s",
                                        "left_from"}
    assert json.loads(json.dumps(out)) == out
    # ...and the memory job's own reader takes it as it stands
    # (`mind/skip_memories`): every mind with a log is one to remember, and
    # every stretch spent somewhere says where IN WORDS -- the mind's own,
    # else the name its view gives the room it stood in, never the id. The
    # writer holds no scene to name a room by.
    from mind.skip_memories import minds_to_remember, record_rows
    remembered = dict(minds_to_remember(out))
    assert set(remembered) == {n for n, m in out["minds"].items() if m["log"]}
    rooms, filled = _rooms(), 0
    for name, mind in remembered.items():
        for stretch, row in zip(mind["itinerary"], mind["log"]):
            if row["room"] and not stretch["where_text"]:
                assert row["where_text"] == rooms[row["room"]]["name"], (name, row)
                filled += 1
        record = record_rows(mind["log"], span_from=out["span"]["from_s"],
                             anchor=CLOCK["anchor_hour"], length=24.0)
        placed = [r for r, row in zip(record, mind["log"]) if row["room"] or row["away"]]
        assert placed and all(r.get("where") for r in placed), (name, record)
    assert filled                       # the default day's gaps had no words


def test_whereabouts_ride_the_checkpoint_and_the_archive(story, monkeypatch):
    """The whereabouts record is a world key of the era -- frame-scoped, and
    one row every bubble of the era reads, since a mind off the map is off
    it for all of them: the checkpoint snapshots it and a restore takes it
    back, and a chat's archive carries it to the imported copy
    (`docs/guides/DATABASE.md`)."""
    from core.db import ERA_WORLD_KEYS, FRAME_SCOPED_WORLD_KEYS, wget, wset
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    assert "whereabouts" in FRAME_SCOPED_WORLD_KEYS and "whereabouts" in ERA_WORLD_KEYS
    ctx, out, _calls, _asked = _run_stage(story, monkeypatch)
    ctx.skip_lives = out
    _commit(ctx)
    kept = wget(story["chat"], "whereabouts")
    assert PELL in kept
    ensure_checkpoint(story["chat"], 9)
    wset(story["chat"], "whereabouts", {})
    restore_checkpoint(story["chat"], 9)
    assert wget(story["chat"], "whereabouts") == kept
    imported = app.chat_import({"data": app.chat_export(story["chat"])})
    assert wget(imported["id"], "whereabouts") == kept
