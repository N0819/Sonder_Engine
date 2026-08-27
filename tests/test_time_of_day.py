"""One field held two kinds of statement, so it held neither.

`scene.time` was written by four places and read by six, and every reader
wanted the same thing: the standing TIME OF DAY, the world's own answer to
"what time is it". Only one of the four writers produced that. The other
three produced a PER-BEAT PASSAGE PHRASE -- "moments later", "a few seconds
pass" -- which is not an answer to that question at all; it is an answer to
"how long did this beat take", and it won on almost every beat because it was
written by every resolve while the time of day was written once by the
opening.

Two kinds of statement, one field, and the wrong one on top. Measured
read-only against the author's 81-chat corpus 2026-08-25:

* 63 of 80 openings named a time of day a reader could act on.
* 6 live scenes still held one. 57 stories had theirs overwritten.
* Chat 34's `scene.time` is the bare boolean `False`.
* Chat 95 (fresh, instrumented, 20 beats) is the mechanism end to end: the
  opening named `dusk`, nineteen beats carried no `state_diff.time` at all
  and left it standing, and turn 18 carried `display_advance: ""` -- a beat
  saying it had no phrase for its own passage -- which ERASED the time of
  day. Final `scene.time` is the empty string.
* `simulation_clock.display` is the same field's other half. Its only
  per-beat writer was that same passage phrase, so after beat 0 it could hold
  a duration phrase or the `wget` default and nothing else. Chats 95 and 96
  read "now" on every call to every role, for 20 and 15 beats.

The split: `scene.time_of_day` holds the standing property, every reader
moves to it, `simulation_clock.display` becomes its label, and the passage
phrase gets NO field -- it reaches no reader anywhere in the tree and stays
the beat's own words on its persisted resolve variant.

These tests are the class, not chat 95: a beat's phrase must never be able to
overwrite or erase a standing world property, whatever either of them says.
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData


def _make_chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Test", None, "", time.time()))


def _scene():
    return {
        "location": "Kessler Tower", "time_of_day": "dusk",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "entities": {},
        "positions": {"The Stranger": "hall"},
        "attire": {}, "overlays": {},
    }


def _ctx(temp_db, chat_id, *, turn_idx, resolve=None, establish=None):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "wait", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="wait", created=time.time()),
        cast=[], input="wait",
    )
    if establish is not None:
        ctx.director_establish = establish
    if resolve is not None:
        ctx.director_resolve = {"resolved_event": "Time passes.",
                                "dialogue_log": [], "state_diff": resolve}
    return ctx


def _commit(temp_db, chat_id, ctx):
    from persist.commit import commit_scene, prepare_scene_commit

    commit_scene(ctx, 0, prepared=prepare_scene_commit(ctx))
    return (temp_db.wget(chat_id, "scene", {}),
            temp_db.wget(chat_id, "simulation_clock", {}))


def _beat(temp_db, chat_id, diff, *, clock=None, scene=None, turn_idx=1):
    temp_db.wset(chat_id, "scene", scene or _scene())
    temp_db.wset(chat_id, "simulation_clock",
                 clock or {"elapsed_seconds": 100.0, "display": "dusk"})
    return _commit(temp_db, chat_id,
                   _ctx(temp_db, chat_id, turn_idx=turn_idx, resolve=diff))


# --- the opening is where a story's time of day comes from -----------------


class TestTheOpeningSetsATimeOfDay:

    def test_establish_writes_the_scene_and_the_clock_from_one_value(
            self, temp_db):
        """Both homes, one statement. Before the split the opening's time
        reached `scene.time` only: on an establish turn no clock was built at
        all, so the opening's own `simulation_clock` -- filled in 80 of 80
        corpus openings -- was never committed anywhere."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", {})
        ctx = _ctx(temp_db, chat_id, turn_idx=0, establish={
            "location": "The Pier", "scene_description": "Cold planks.",
            "time": "before dawn",
            "rooms": {"pier": {"name": "Pier", "desc": "Planks."}},
            "positions": {}, "entities": {},
        })
        scene, clock = _commit(temp_db, chat_id, ctx)
        assert scene["time_of_day"] == "before dawn"
        assert clock["display"] == "before dawn"

    def test_the_clocks_own_label_is_read_when_the_two_disagree(
            self, temp_db):
        """The establish `simulation_clock` was an ORPHAN -- solicited by the
        schema, filled by 80 of 80 corpus openings, read by nothing. It says
        the same thing `time` says, and where the two disagree it is `time`
        that drifts into circumstance: 17 corpus openings pair an `Immediate
        aftermath of a containment breach` with an `08:42:15 AM`."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", {})
        ctx = _ctx(temp_db, chat_id, turn_idx=0, establish={
            "location": "Site", "scene_description": "Corridor.",
            "time": "Immediate aftermath of the breach",
            "simulation_clock": {"elapsed_seconds": 0.0,
                                 "display": "08:42:15 AM"},
            "rooms": {"hall": {"name": "Hall", "desc": "A hall."}},
            "positions": {}, "entities": {},
        })
        scene, clock = _commit(temp_db, chat_id, ctx)
        assert scene["time_of_day"] == "08:42:15 AM"
        assert clock["display"] == "08:42:15 AM"

    def test_an_opening_that_names_no_time_claims_none(self, temp_db):
        """"now" was the default on both keys, and a word that reads as an
        answer while carrying none is what every role in a fresh story was
        told for its whole life. Silence stays silence."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", {})
        ctx = _ctx(temp_db, chat_id, turn_idx=0, establish={
            "location": "Nowhere", "scene_description": "A room.",
            "rooms": {"hall": {"name": "Hall", "desc": "A hall."}},
            "positions": {}, "entities": {},
        })
        scene, _clock = _commit(temp_db, chat_id, ctx)
        assert scene["time_of_day"] == ""

    def test_an_opening_inherits_what_the_greeting_already_read(self, temp_db):
        """The greeting path reads a time out of the greeting's own passage
        and seeds the clock's label with it before turn 0 runs. An opening
        that names none of its own must not blank that."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", {})
        temp_db.wset(chat_id, "simulation_clock",
                     {"elapsed_seconds": 0.0, "display": "first light",
                      "time_scale": "scene"})
        ctx = _ctx(temp_db, chat_id, turn_idx=0, establish={
            "location": "Nowhere", "scene_description": "A room.",
            "rooms": {"hall": {"name": "Hall", "desc": "A hall."}},
            "positions": {}, "entities": {},
        })
        scene, clock = _commit(temp_db, chat_id, ctx)
        assert scene["time_of_day"] == "first light"
        assert clock["display"] == "first light"

    def test_no_surface_defaults_the_field_to_a_word(self):
        """"now" was the default in six places at once -- two schemas, the
        establish normalizer, the commit's `wget`, the read helper and the
        character payload -- so the placeholder was the answer a fresh story
        got at every one of them."""
        from llm.schemas import DirectorEstablish, GreetingInterpret

        assert DirectorEstablish().time == ""
        assert GreetingInterpret().time == ""
        assert DirectorEstablish().simulation_clock == {}


# --- a beat may not overwrite or erase it ----------------------------------


class TestABeatsPassagePhraseCannotTouchIt:

    def test_a_phrase_does_not_become_the_time_of_day(self, temp_db):
        """The overwrite half. "moments later" is a statement about this
        beat's length; it is not what time it is, and it has nowhere to go."""
        chat_id = _make_chat(temp_db)
        scene, clock = _beat(temp_db, chat_id, {
            "time": {"start_seconds": 100, "duration_seconds": 25,
                     "end_seconds": 125, "display_advance": "moments later"}})
        assert scene["time_of_day"] == "dusk"
        assert clock["display"] == "dusk"
        assert clock["elapsed_seconds"] == 125.0

    def test_an_empty_phrase_does_not_erase_it(self, temp_db):
        """The erasure half, and the live mechanism: chat 95 turn 18 carried
        `display_advance: ""` beside a perfectly ordinary span, and the scene
        lost `dusk` after nineteen beats of holding it."""
        chat_id = _make_chat(temp_db)
        scene, clock = _beat(temp_db, chat_id, {
            "time": {"start_seconds": 170, "duration_seconds": 12,
                     "end_seconds": 182, "mode": "action", "explicit": False,
                     "display_advance": ""}})
        assert scene["time_of_day"] == "dusk"
        assert clock["display"] == "dusk"
        assert clock["elapsed_seconds"] == 182.0

    def test_nineteen_silent_beats_leave_it_standing(self, temp_db):
        """The other nineteen beats of the same run. A beat that says nothing
        about time must change nothing about the time of day, while the
        NUMBER still moves -- the unclaimed-beat floor is untouched by this
        split."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _scene())
        temp_db.wset(chat_id, "simulation_clock",
                     {"elapsed_seconds": 0.0, "display": "dusk"})
        for idx in range(1, 20):
            scene, clock = _commit(
                temp_db, chat_id,
                _ctx(temp_db, chat_id, turn_idx=idx, resolve={}))
        assert scene["time_of_day"] == "dusk"
        assert clock["display"] == "dusk"
        assert clock["elapsed_seconds"] > 0.0

    def test_the_display_a_mind_receives_is_not_the_default(self, temp_db):
        """What the finding was actually about: across three instrumented
        runs `simulation_clock.display` read "now" on every call to every
        role. A mind is told what time it is or the field should not exist.
        """
        chat_id = _make_chat(temp_db)
        _scene_row, clock = _beat(temp_db, chat_id, {
            "time": {"duration_seconds": 30, "display_advance": "moments"}},
            clock={"elapsed_seconds": 0.0, "display": "now"})
        assert clock["display"] == "dusk"


class TestABeatMayStillCHANGETheTimeOfDay:

    def test_a_bare_string_time_channel_moves_it(self, temp_db):
        """The one writer that always meant a time of day, and the only way a
        beat may move it: an explicit statement, not a side effect."""
        chat_id = _make_chat(temp_db)
        scene, clock = _beat(temp_db, chat_id, {"time": "deep night"})
        assert scene["time_of_day"] == "deep night"
        assert clock["display"] == "deep night"

    def test_an_empty_string_is_not_a_statement(self, temp_db):
        chat_id = _make_chat(temp_db)
        scene, clock = _beat(temp_db, chat_id, {"time": "   "})
        assert scene["time_of_day"] == "dusk"
        assert clock["display"] == "dusk"

    def test_a_value_that_is_not_written_language_is_refused(self, temp_db):
        """Chat 34 holds the bare boolean `False` in this field. Whatever a
        non-string means, it is not something a room, an image prompt or a
        mind can be told."""
        from world.mechanics import normalize_time_of_day

        assert normalize_time_of_day(False) == ""
        assert normalize_time_of_day(True) == ""
        assert normalize_time_of_day(None) == ""
        assert normalize_time_of_day(1430) == ""
        assert normalize_time_of_day("  dusk  ") == "dusk"

        chat_id = _make_chat(temp_db)
        scene, _clock = _beat(temp_db, chat_id, {"time": False})
        assert scene["time_of_day"] == "dusk"


# --- every reader is on the new field --------------------------------------


class TestTheReadersMoved:

    def test_the_scenery_readers_bucket_the_standing_field(self):
        from dressing.ambience import room_soundscape
        from dressing.backdrops import room_projection, visual_signature

        scene = _scene()
        scene["time_of_day"] = "night"
        assert room_projection(scene, "hall")["time"] == "night"
        assert room_soundscape(scene, "hall")["time"] == "night"
        lit = visual_signature(scene, "hall")
        scene["time_of_day"] = "high noon"
        assert visual_signature(scene, "hall") != lit

    def test_a_clock_reading_is_a_time_of_day_too(self):
        """The synonym table is closed, so it could not read a story that
        tells time in digits -- 12 of the 17 corpus openings it could not
        bucket said the time that way, one whole story line among them.

        The three guards each come from a live string: a countdown is not a
        time, a year is not a time, and 18:93 is not a time."""
        from dressing.backdrops import time_bucket

        assert time_bucket("09:42") == "morning"
        assert time_bucket("14:32 hours") == "day"
        assert time_bucket("08:42:15 AM") == "morning"
        assert time_bucket("1430 hours") == "day"
        assert time_bucket("0830") == "morning"
        assert time_bucket("23:47") == "night"
        assert time_bucket("09:42 PM") == "night"

        assert time_bucket("Cycle-End -01:45:00") == ""
        assert time_bucket("Spring 1830") == ""
        assert time_bucket("1893") == ""
        # The word table still wins where both could read: a named phase of
        # the day is a better answer than a number sitting beside it.
        assert time_bucket("Late night, 2026") == "night"

    def test_the_director_is_shown_the_standing_time_under_its_own_name(self):
        """Both Director payloads sent `scene.time` -- last beat's duration
        phrase, and the SAME string the `simulation_clock` beside it carried
        as `display` -- to the one hand that owns the `time` channel. A
        payload teaching the model to write the defect back."""
        import inspect

        from agents import director

        for fn in (director.director_interpret, director.director_resolve):
            src = inspect.getsource(fn)
            assert '"time": sc.get("time")' not in src
            assert '"time_of_day": sc.get("time_of_day")' in src

    def test_a_background_presence_is_told_the_time_of_day(self, temp_db):
        """`_place_block`'s own docstring: "every field is something anyone
        standing in the room trivially has". A duration phrase is not that,
        and this is the only path that hands the raw scene time to a
        fictional mind."""
        from agents.background import _place_block

        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _scene())
        block = _place_block(
            _ctx(temp_db, chat_id, turn_idx=1, resolve={}), "hall")
        assert block["time_of_day"] == "dusk"
        assert "time" not in block

    def test_nothing_reads_the_old_field(self):
        """The split is only worth anything if the corrupt name is gone. A
        reader left on `scene.time` would keep getting the old semantics in
        silence, which is exactly how this survived."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent
        offenders = []
        for package in ("agents", "core", "dressing", "llm", "mind",
                        "persist", "story", "web", "world"):
            for path in (root / package).rglob("*.py"):
                for lineno, line in enumerate(
                        path.read_text().splitlines(), 1):
                    if 'scene.get("time")' in line or 'sc.get("time")' in line:
                        offenders.append(f"{path.name}:{lineno}")
        assert offenders == []


# --- the stories that already lost theirs ----------------------------------


def _story_with_a_lost_time(temp_db, *, establish, scene_time,
                            frame_id=None, chat_id=None):
    chat_id = chat_id or _make_chat(temp_db)
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (chat_id, 0, "", time.time(), frame_id))
    step_id = temp_db.qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,?)",
        (turn_id, "director_establish", "Establish", 0, 0))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) "
        "VALUES(?,?,?,?)",
        (step_id, json.dumps(establish), time.time(), 1))
    scene = _scene()
    scene.pop("time_of_day")
    scene["time"] = scene_time
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": 192.0, "display": "moments later"})
    return chat_id


class TestTheRecoveryOfExistingStories:
    """80 of the author's 81 chats still hold the opening that named their
    time of day, as an active non-stale `director_establish` variant -- so
    what the passage phrase overwrote comes back with one join. Measured on a
    copy of the live corpus: 7 of 84 scene rows carried a readable time of day
    before, 81 of 84 after."""

    def test_the_opening_is_recovered_over_the_phrase(self, temp_db):
        from core.db import recover_scene_time_of_day

        chat_id = _story_with_a_lost_time(
            temp_db,
            establish={"time": "Late autumn afternoon",
                       "simulation_clock": {"elapsed_seconds": 0.0,
                                            "display": "Late afternoon"}},
            scene_time="moments later")
        recover_scene_time_of_day(chat_id)
        assert temp_db.wget(chat_id, "scene", {})["time_of_day"] == (
            "Late afternoon")
        clock = temp_db.wget(chat_id, "simulation_clock", {})
        assert clock["display"] == "Late afternoon"
        # The number the whole engine windows against is not this pass's
        # business and is not touched.
        assert clock["elapsed_seconds"] == 192.0

    def test_the_erased_case_is_recovered_too(self, temp_db):
        """Chat 95's ending state: the field is not merely wrong, it is
        empty, and an empty field is indistinguishable from a story that
        never said."""
        from core.db import recover_scene_time_of_day

        chat_id = _story_with_a_lost_time(
            temp_db, establish={"time": "dusk"}, scene_time="")
        recover_scene_time_of_day(chat_id)
        assert temp_db.wget(chat_id, "scene", {})["time_of_day"] == "dusk"

    def test_the_corrupt_field_does_not_survive_beside_its_replacement(
            self, temp_db):
        from core.db import recover_scene_time_of_day

        chat_id = _story_with_a_lost_time(
            temp_db, establish={"time": "dusk"}, scene_time="moments later")
        recover_scene_time_of_day(chat_id)
        assert "time" not in temp_db.wget(chat_id, "scene", {})

    def test_a_story_with_no_opening_gets_the_key_and_no_answer(
            self, temp_db):
        """One corpus chat is an import and has no establish step at all.
        The key is still written, because its ABSENCE is what this pass
        keys on -- without it the join is re-run on every open forever."""
        from core.db import recover_scene_time_of_day

        chat_id = _make_chat(temp_db)
        scene = _scene()
        scene.pop("time_of_day")
        scene["time"] = "moments later"
        temp_db.wset(chat_id, "scene", scene)
        recover_scene_time_of_day(chat_id)
        assert temp_db.wget(chat_id, "scene", {})["time_of_day"] == ""

    def test_it_never_drags_a_story_back_to_its_opening(self, temp_db):
        """Idempotent, and keyed on the KEY rather than the value: a story
        that has since moved from dawn to midnight must not be pulled back
        the next time the database is opened."""
        from core.db import recover_scene_time_of_day

        chat_id = _story_with_a_lost_time(
            temp_db, establish={"time": "dawn"}, scene_time="moments later")
        recover_scene_time_of_day(chat_id)
        scene = temp_db.wget(chat_id, "scene", {})
        scene["time_of_day"] = "midnight"
        temp_db.wset(chat_id, "scene", scene)
        recover_scene_time_of_day(chat_id)
        assert temp_db.wget(chat_id, "scene", {})["time_of_day"] == "midnight"

    def test_an_eras_own_scene_row_is_recovered_from_its_own_opening(
            self, temp_db):
        """Frame-scoped scenes are real rows under a separator-suffixed key,
        and an era is recovered from THE OPENING THAT RAN IN IT."""
        from core.db import _FRAME_KEY_SEP, recover_scene_time_of_day

        chat_id = _make_chat(temp_db)
        era = temp_db.qi(
            "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
            "VALUES(?,?,?,?,?)", (chat_id, "Era", 1, "other", time.time()))
        chat_id = _story_with_a_lost_time(
            temp_db, establish={"time": "dusk"}, scene_time="moments later",
            frame_id=era, chat_id=chat_id)
        scene = _scene()
        scene.pop("time_of_day")
        scene["time"] = "a few seconds"
        temp_db.wset(chat_id, f"scene{_FRAME_KEY_SEP}{era}", scene)
        recover_scene_time_of_day(chat_id)
        assert temp_db.wget(
            chat_id, f"scene{_FRAME_KEY_SEP}{era}", {})["time_of_day"] == "dusk"

    def test_an_era_that_ran_no_opening_of_its_own_is_told_nothing(
            self, temp_db):
        """It used to inherit the story's earliest opening, and that is where
        a plot countdown from one era became three other eras' standing time
        of day -- measured at 3 of 3 frame-scoped rows in the corpus, onto
        clocks whose elapsed_seconds were 2143 / 1630 / 1975 / 142.

        A frame is a different moment by construction. The one thing another
        era's opening cannot supply is when THIS one is, so it supplies
        nothing, which is the same rule this change applies when it refuses to
        call an unstated hour "now".
        """
        from core.db import _FRAME_KEY_SEP, recover_scene_time_of_day

        chat_id = _story_with_a_lost_time(
            temp_db, establish={"time": "dusk"}, scene_time="moments later")
        scene = _scene()
        scene.pop("time_of_day")
        scene["time"] = "a few seconds"
        temp_db.wset(chat_id, f"scene{_FRAME_KEY_SEP}7", scene)
        recover_scene_time_of_day(chat_id)
        assert temp_db.wget(
            chat_id, f"scene{_FRAME_KEY_SEP}7", {}).get("time_of_day", "") == ""


class TestTheRecoveryIsWiredToSomethingThatRuns:
    """`recover_scene_time_of_day` is correct and was called from two places
    that NOTHING TESTED. Every recovery test called the function by hand and
    passed the wiring in itself, so both call sites deleted with a fully green
    9,817-test suite -- and the entire "existing stories get theirs back" half
    of this change rests on exactly those two lines.

    These assert the CALL, through the entry points a user actually reaches.
    """

    def test_opening_a_database_repairs_the_scenes_already_in_it(self, temp_db):
        """`db.init()` is the only live caller of the migration's recovery."""
        chat_id = _story_with_a_lost_time(
            temp_db, establish={"time": "dusk"}, scene_time="moments later")
        scene = _scene()
        scene.pop("time_of_day")
        scene["time"] = "moments later"
        temp_db.wset(chat_id, "scene", scene)

        temp_db.init()

        assert temp_db.wget(chat_id, "scene", {})["time_of_day"] == "dusk", (
            "db.init() no longer repairs stored scenes; the migration's only "
            "live caller is gone and every existing story keeps a passage "
            "phrase where its time of day belongs")

    def test_importing_an_archive_repairs_the_chat_that_arrived(self, temp_db):
        """An archive written before the split carries the old shape, and the
        import is where it becomes this database's problem."""
        from web import app

        chat_id = _story_with_a_lost_time(
            temp_db, establish={"time": "dusk"}, scene_time="moments later")
        service = app._chat_archive_service
        payload = json.loads(json.dumps(service.export_chat(chat_id),
                                        default=str))

        # Put the pre-split shape back. The export runs after the repair, so
        # what a genuinely old archive carries has to be reconstructed here.
        stripped = False
        world = payload.get("world")
        rows = world.items() if isinstance(world, dict) else (
            (r.get("key"), r) for r in (world or []))
        for key, holder in list(rows):
            if key != "scene":
                continue
            value = holder if isinstance(world, dict) else holder.get("value")
            if isinstance(value, str):
                value = json.loads(value)
            value.pop("time_of_day", None)
            value["time"] = "moments later"
            if isinstance(world, dict):
                world["scene"] = value
            else:
                holder["value"] = value
            stripped = True
        assert stripped, "could not find the scene row in the export"

        result = service.import_chat({"data": payload})
        new_chat_id = (result.get("chat_id") or result.get("id")
                       or result.get("chat", {}).get("id"))
        assert new_chat_id, f"import returned no chat id: {sorted(result)}"
        assert "time_of_day" in temp_db.wget(new_chat_id, "scene", {}), (
            "an imported archive kept the pre-split shape; the import's "
            "recovery call is gone")
