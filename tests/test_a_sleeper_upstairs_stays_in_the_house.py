"""A BODY THE STORY SAYS IS ASLEEP BEGINS ASLEEP, AND THE BUILDING THE PLAYER
IS IN IS ONE BUBBLE (2026-10-20).

The house probe (Hallow Farm, a stone farmhouse at night). The scenario and
Agnes Hale's card have her asleep in the room directly above the kitchen; she
sleeps lightly and wakes to her name. `tests/data/house_opening_establish.json`
is that opening's recorded `director_establish` output -- the fields the model
wrote, as the variant stored them. The opening placed her right (her room is
`over` the kitchen, a timber floor) and then:

  (a) wrote no awareness condition: `DirectorEstablish` had no `conditions`
      field and the establish card said nothing of a body that begins asleep,
      so she was posed "asleep on her back under the blankets" and gated by
      nothing;
  (b) the first commit's bubble detector found her past the radius of rooms
      walked from the player -- kitchen, back kitchen, the stair, the landing,
      her room -- and split her into "Bubble -- Agnes Hale": her own frame and
      her own input-less beats, in which she was called as a speaker, awake,
      and said "Nell." to nobody. Out of the kitchen's air, so no dropped pan
      and no name called up the stair could reach her.

The owner, when the radius replaced the zone rule (2026-10-13): "same building
should probably be the same bubble", then "maybe it should be a radius of
rooms?" Only the second sentence was built.

Two classes, each failing first:

  1. A BODY THE OPENING FINDS NOT AWAKE BEGINS SO: the opening can write the
     engine's awareness condition, its card asks for it as a class, and the
     commit writes it -- so the mind is gated from the first beat and costs no
     character call.
  2. THE RANGE OF THE PLAYER'S BUBBLE INCLUDES THE BUILDING THEY ARE IN: a walk
     that never goes out under the sky (`weather.room_exposure` not `open`)
     reaches every room of it whatever its room count; outside it the radius
     decides as before, and a thread the radius alone opened rejoins.
"""

from __future__ import annotations

import json
import os
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data

_HERE = os.path.dirname(os.path.abspath(__file__))

PLAYER = "Ash Penrose"
SLEEPER = "Agnes Hale"
SCENARIO = (
    "A stone farmhouse on a moor road, two storeys under a slate roof, timber "
    "floors upstairs. A traveller caught by the weather, Ash Penrose, has been "
    "given the box bed in the kitchen for the night by the farmer, Gideon Hale. "
    "Gideon's mother, old Mrs Hale, is asleep in the room directly above the "
    "kitchen; she sleeps lightly and wakes to her name. Gideon's daughter "
    "Nell, nineteen, is still up, mending by the fire. Outside a wind is "
    "rising and rain has begun; there is a full moon behind the cloud. The "
    "clock on the kitchen wall ticks loudly.")
# The cast as the probe's cards name them: sheet name and identity uid.
CAST = (("Gideon Hale", "gideon_hale"), ("Nell Hale", "nell_hale"),
        (SLEEPER, "agnes_hale"))
# What the model writes under the clause: keyed by her uid, the way the
# recorded opening keyed her entity (`agnes_hale`).
ASLEEP = {"agnes_asleep": [{"condition_id": "agnes_asleep",
                            "subject_id": "agnes_hale", "kind": "awareness",
                            "state": {"level": "asleep",
                                      "cause": "asleep for the night"}}]}


def _recorded():
    with open(os.path.join(_HERE, "data", "house_opening_establish.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _house(temp_db):
    """The probe's chat before its opening: the persona, the three Hales and
    the scenario, in an empty world."""
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        (PLAYER, json.dumps(persona), "{}", persona["identity"]["uid"]))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Hallow Farm, by night", persona_id, SCENARIO, time.time()))
    ids = {}
    for name, uid in CAST:
        sheet = default_character_data(name)
        sheet["identity"]["uid"] = uid
        ids[name] = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(),
             "%s_%d" % (uid, time.time_ns())))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, ids[name], "active", "{}"))
    # Who knows whom, as the probe launched: the family know each other, the
    # traveller knows Gideon and Nell from this evening.
    temp_db.wset(chat_id, "known", {
        "Gideon Hale": [PLAYER, "Nell Hale", SLEEPER],
        "Nell Hale": [PLAYER, "Gideon Hale", SLEEPER],
        SLEEPER: ["Gideon Hale", "Nell Hale"],
        PLAYER: ["Gideon Hale", "Nell Hale"]})
    return chat_id, persona_id, ids


def _ctx(temp_db, chat_id, persona_id, idx):
    from story.scene import active_cast

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Hallow Farm, by night",
                      persona_id=persona_id, lorebook_id=None,
                      scenario=SCENARIO, created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx, player_input="",
                      created=time.time()),
        cast=active_cast(chat_id, None), input="")


def _open_the_house(temp_db, monkeypatch, conditions=None):
    """The probe's opening, replayed: its recorded establish output (plus
    `conditions` as the model would write them) through the strict schema,
    the establish tail and the opening's perception, then the commit's
    scene, entity and spatial domains in `commit_all`'s order. No model
    call: the model's answer is the recording."""
    import agents.director as director
    from agents.perception import perception_establish
    from llm.schemas import validate_llm_output_strict
    from persist.commit import (commit_scene, commit_world_entities,
                                prepare_scene_commit)
    from world import spatial_frames

    chat_id, persona_id, ids = _house(temp_db)
    ctx = _ctx(temp_db, chat_id, persona_id, 0)
    answer = _recorded()
    if conditions is not None:
        answer["conditions"] = conditions

    def model(role, step_key, system, payload, **kwargs):
        assert step_key == "director_establish"
        report = validate_llm_output_strict(step_key, json.loads(json.dumps(answer)))
        assert report.valid, report.errors
        return report.output

    monkeypatch.setattr(director, "_agent_json", model)
    ctx.director_establish = director.director_establish(ctx, nonce=0)
    views = perception_establish(ctx, "n0")["views"]
    prepared = prepare_scene_commit(ctx)
    commit_scene(ctx, 0, prepared=prepared)
    commit_world_entities(ctx, 0, prepared=prepared)
    spatial = spatial_frames.detect_and_reconcile(ctx, 0)
    return {"ctx": ctx, "chat_id": chat_id, "persona_id": persona_id,
            "ids": ids, "views": views, "spatial": spatial}


def _scene(**positions):
    """The house as its opening drew it -- every room, edge and exposure the
    recording holds -- with bodies placed where a test says."""
    recorded = _recorded()
    placed = dict(recorded["positions"])
    placed.update(positions)
    return {"rooms": json.loads(json.dumps(recorded["rooms"])),
            "positions": placed, "entities": {}, "comms": {}}


def _decide(scene, cast, radius):
    from world.spatial_bubbles import bubble_split_decision

    return bubble_split_decision(scene, party_names=[PLAYER],
                                 cast_names=list(cast), radius=radius)


# --- 1. a body the opening finds not awake begins so -------------------------

def test_the_opening_can_say_a_body_is_not_awake():
    """The field the clause asks the model to write is on the output schema,
    in the shape `StateDiff.conditions` carries -- and a lone entry written
    without its list, or the table written as a list, is read, not dropped."""
    from llm.schemas import DirectorEstablish, validate_llm_output_strict

    assert "conditions" in (getattr(DirectorEstablish, "model_fields", None)
                            or DirectorEstablish.__fields__)
    base = {"location": "Hallow Farm", "positions": {SLEEPER: "hallow_agnes_room"},
            "rooms": {"hallow_agnes_room": {"name": "old Mrs Hale's room"}}}
    entry = ASLEEP["agnes_asleep"][0]
    for written in (ASLEEP, {"agnes_asleep": entry}, [entry]):
        report = validate_llm_output_strict("director_establish",
                                            dict(base, conditions=written))
        assert report.valid, report.errors
        assert report.output["conditions"] == {"agnes_asleep": [entry]}, written


def test_the_card_states_the_class_in_both_packs():
    """ONE clause, en + ja: a body the opening finds not awake begins so, as
    the engine's awareness condition, stated as the class -- what the record
    does and the bar every beat keeps, never a list of ways to go under. The
    printed shape carries the field, and the example the model repairs to
    shows it."""
    from language_runtime import raw_card
    from llm.schemas import OUTPUT_EXAMPLES

    en = raw_card("en")["prompts"]["director_establish"]
    assert "A BODY THE OPENING FINDS NOT AWAKE BEGINS SO" in en
    assert "The engine takes a mind out of the scene on this record and on nothing else" in en
    assert "a body that could answer a question put to it is awake, whatever its posture" in en
    assert "The player's own character begins under only when the player's seed says so" in en
    shape = en.split("Output STRICT JSON", 1)[1]
    assert "conditions:{condition_id:[{condition_id,subject_id,kind:'awareness'" in shape
    ja = raw_card("ja")["prompts"]["director_establish"]
    assert "冒頭で目覚めていない身体はそのまま始まります" in ja
    assert "エンジンはこの記録によってのみ心を場面から外します" in ja
    assert "問いかけられて答えられる身体は、どんな姿勢であれ起きています" in ja
    assert "conditions:{condition_id:[{condition_id,subject_id,kind:'awareness'" in ja
    assert "conditions" in OUTPUT_EXAMPLES["director_establish"]


def test_the_house_opening_commits_her_asleep_and_she_costs_no_call(
        temp_db, monkeypatch):
    """The house's own opening, the condition written as the model would --
    under her uid. The tail spells it as `positions` spells her, her opening
    view is the sleeper's residue, the commit writes the row, and from then
    on no reader plans a character step for her or calls her in the loop."""
    from agents import loops
    from agents.runtime import build_plan
    from story.scene import awareness_map, awareness_of

    opened = _open_the_house(temp_db, monkeypatch, conditions=ASLEEP)
    ctx, chat_id, ids = opened["ctx"], opened["chat_id"], opened["ids"]

    written = ctx.director_establish["state_diff"]["conditions"]
    assert written["agnes_asleep"][0]["subject_id"] == SLEEPER
    assert opened["views"][str(ids[SLEEPER])] == "You are under, below waking."
    assert awareness_of(awareness_map(chat_id), SLEEPER) == "asleep"

    beat = _ctx(temp_db, chat_id, opened["persona_id"], 1)
    reactors = [ids[SLEEPER], ids["Nell Hale"]]
    assert loops._drop_non_awake(beat, reactors) == [ids["Nell Hale"]]
    # autonomy 0 names each reactor as its own step, so the plan shows who
    # would be called (tests/test_reactors_are_narrowed_to_presence.py).
    temp_db.wset(chat_id, "dialogue_config", {"autonomy": 0})
    keys = [key for key, _ in build_plan(
        {"flow": {"reactors": reactors, "resolution_flags": {}}},
        beat.cast, chat_id=chat_id)]
    assert f"character:{ids[SLEEPER]}" not in keys
    assert f"character:{ids['Nell Hale']}" in keys


# --- 2. the building the player is in is one bubble ---------------------------

def test_the_house_opening_keeps_her_in_the_kitchen_s_thread(temp_db, monkeypatch):
    """The same opening through the commit's spatial domain opens no thread:
    she stands in her room in the player's own scene and is active in the
    player's frame. (The recording carries no plan, so its stair is two rooms
    and she is five rooms walked from the kitchen.)"""
    from core.db import q
    from story.scene import active_cast, get_scene

    opened = _open_the_house(temp_db, monkeypatch)
    chat_id = opened["chat_id"]

    assert not opened["spatial"].get("bubble"), opened["spatial"]
    assert q("SELECT id FROM frames WHERE chat_id=?", (chat_id,)) == []
    assert get_scene(chat_id)["positions"][SLEEPER] == "hallow_agnes_room"
    assert SLEEPER in [row["name"] for row in active_cast(chat_id, None)]


def test_a_body_anywhere_in_the_building_is_in_range_at_any_radius():
    """Every room of the house is reached from the kitchen without going out
    under the sky -- the back kitchen, both flights of the stair, the landing
    and every bedroom -- so nobody in it gets a thread, at the smallest radius
    a story may set and at the default; the yard and the road are not in it."""
    from world.spatial import rooms_under_one_roof

    roof = set(rooms_under_one_roof(_scene(), {"hallow_kitchen"}))
    assert roof == {
        "hallow_kitchen", "hallow_back_kitchen",
        "hallow_back_kitchen__hallow_landing_stair_0",
        "hallow_back_kitchen__hallow_landing_stair_1", "hallow_landing",
        "hallow_agnes_room", "hallow_nell_room", "hallow_gideon_room"}
    scene = _scene(**{"Nell Hale": "hallow_nell_room",
                      "Gideon Hale": "hallow_gideon_room"})
    for radius in (1, 2, 3):
        assert _decide(scene, [SLEEPER, "Nell Hale", "Gideon Hale"], radius) is None, radius


def test_a_body_across_the_yard_is_decided_by_the_radius():
    """Outside the building nothing changed. The byre stands across the open
    yard, two rooms walked: a radius of one gives Gideon a thread of his own,
    a radius of two keeps him -- exactly as before the building rule."""
    scene = _scene()
    assert _decide(scene, ["Gideon Hale"], 1)["characters"] == ["Gideon Hale"]
    assert _decide(scene, ["Gideon Hale"], 2) is None


def _porch_scene(exposure):
    """A kitchen whose only way to the wash-house wing is a porch, and a
    body four rooms walked down that wing."""
    def room(name, *exits, exposure="enclosed"):
        return {"name": name, "exposure": exposure,
                "adjacent": [{"to": to, "barrier": "closed_door"} for to in exits]}

    rooms = {
        "kitchen": room("the kitchen", "porch"),
        "porch": room("the porch", "kitchen", "wash_house", exposure=exposure),
        "wash_house": room("the wash-house", "porch", "dairy"),
        "dairy": room("the dairy", "wash_house", "cheese_loft"),
        "cheese_loft": room("the cheese loft", "dairy"),
    }
    return {"rooms": rooms, "comms": {}, "entities": {},
            "positions": {PLAYER: "kitchen", "Nell Hale": "cheese_loft"}}


def test_a_covered_porch_is_inside_and_an_open_yard_is_not():
    """Sheltered is not the sky: a covered porch between the kitchen and the
    wash-house wing leaves them one building, so Nell four rooms down it stays
    in the kitchen's thread. The same doorway opening onto open ground makes
    the wing a building of its own, and the radius gives her a thread."""
    assert _decide(_porch_scene("sheltered"), ["Nell Hale"], 3) is None
    assert _decide(_porch_scene("open"), ["Nell Hale"], 3)["characters"] == ["Nell Hale"]


def test_a_thread_the_radius_alone_opened_rejoins(temp_db, monkeypatch):
    """The probe's database as it stands: the radius split her off at the
    opening. Under the building rule she is in range again, so the player's
    next beat brings her back before its interpret (`bubbles_the_beat_
    reaches`) and its commit would (`detect_merge`); the merge leaves her in
    her room in the player's scene, active in the player's frame."""
    from story.scene import active_cast, get_scene
    from world.spatial_frames import (bubbles_the_beat_reaches, detect_merge,
                                      perform_merge, perform_split)

    opened = _open_the_house(temp_db, monkeypatch)
    chat_id = opened["chat_id"]
    child = perform_split(chat_id, None, 0, bubble=True, away_names=[SLEEPER],
                          away_rooms=["hallow_agnes_room"])
    assert SLEEPER not in get_scene(chat_id)["positions"]

    assert bubbles_the_beat_reaches(chat_id, None, ["hallow_kitchen"],
                                    party_names=[PLAYER]) == [child]
    assert detect_merge(chat_id, None, played=True) == (None, child)

    perform_merge(chat_id, None, child, 1)
    assert get_scene(chat_id)["positions"][SLEEPER] == "hallow_agnes_room"
    assert SLEEPER in [row["name"] for row in active_cast(chat_id, None)]


# --- what reaches her, now that she is in the kitchen's air -------------------

def test_her_name_called_below_wakes_her_and_a_whisper_does_not(temp_db, monkeypatch):
    """The point of keeping her in the kitchen's thread (DESIGN_SOUND_FIELD
    § 13): asleep over the kitchen, she wakes to her name called loud below,
    sleeps through a whisper, and a crash on the kitchen's flags reaches her
    through the floor. In the thread the radius gave her none of it could.

    A `loud` impact in the kitchen does NOT reach her, and is not asserted
    here: a one-beat impact is priced as airborne sound through the floor
    (72 dB at its cell, the kitchen's flood level about 54, a timber floor
    30 -- some 24 dB in her room), and impact transmission through a floor is
    not built (DESIGN_SOUND_FIELD § 12.4)."""
    import agents.perception as perception

    opened = _open_the_house(temp_db, monkeypatch, conditions=ASLEEP)
    chat_id, ids = opened["chat_id"], opened["ids"]
    beats = iter(range(1, 10))

    def beat(lines=(), events=()):
        ctx = _ctx(temp_db, chat_id, opened["persona_id"], next(beats))
        ctx["_player_room"] = "hallow_kitchen"
        ctx.director_interpret = {"sequence": [], "flow": {"reactors": []}}
        ctx.director_resolve = {"resolved_event": "In the kitchen.",
                                "dialogue_log": list(lines),
                                "state_diff": {"sensory_events": list(events)}}
        out = perception.perception_outcome(ctx, nonce=0)
        return out, out["views"].get(str(ids[SLEEPER]))

    def nell(quote, volume):
        return {"speaker": "Nell Hale", "exact_quote": quote, "volume": volume,
                "intended_target": None}

    out, view = beat([nell("Agnes! Gran!", "loud")])
    assert out.get("woken") == {SLEEPER: {"by": "name"}}
    assert view.startswith("Someone says your name")

    out, view = beat([nell("Hush, Gran's asleep.", "whisper")])
    assert not out.get("woken")
    assert view == "You are under, below waking."

    out, view = beat(events=[{"kind": "sound", "source_room": "hallow_kitchen",
                              "level": "deafening",
                              "detail": "the dresser goes over onto the flags"}])
    assert out.get("woken") or "huge and wordless" in view, view
