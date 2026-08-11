"""Approach C floor: public surfaces move only inside physical holders."""

from __future__ import annotations

import inspect
import json
import time
import types

import crowds


class _Chat(dict):
    """A chat with both `.id` and `.get`, as the real `ChatData` has.

    The bare `SimpleNamespace(id=cid)` every other test in this file uses has
    no `.get`, so `persona_of` cannot resolve a persona from it and the player
    stays out of the carrier list — the safe direction, and the reason those
    tests are untouched by the player becoming a carrier.
    """

    @property
    def id(self):
        return self["id"]


def _world(db, *, enabled=True, persona=""):
    persona_id = None
    if persona:
        persona_id = db.qi(
            "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
            (persona, json.dumps({"name": persona}), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Carrier story", "", time.time(), persona_id))
    chars = []
    for name, uid in (("Mora", "mora_uid"), ("Tavi", "tavi_uid")):
        sheet = json.dumps({"identity": {"name": name, "uid": uid}})
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, sheet, "{}", time.time()))
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars.append((char_id, sheet))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 3, "", time.time()))
    db.wset(cid, "living_world", {
        "rumor_ledger": "floor" if enabled else "off"})
    scene = {
        "rooms": {"square": {"name": "Square", "adjacent": ["road"]},
                  "road": {"name": "Road", "adjacent": ["square"]}},
        "positions": {"Mora": "square", "Tavi": "road"},
    }
    db.qi(
        "INSERT INTO world_events(event_id,chat_id,turn_id,frame_id,"
        "occurred_at,duration_seconds,kind,location_id,payload,seed,committed) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("world_bell", cid, turn_id, None, 50.0, 0.0, "consequence", "square",
         json.dumps({"what": "the hidden mechanism failed",
                     "witnessed": "the warning bell rang twice",
                     "source_event_id": "scheduled_bell"}),
         "seed", time.time()))
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    ctx = types.SimpleNamespace(
        chat=(_Chat(id=cid, persona_id=persona_id) if persona
              else types.SimpleNamespace(id=cid)),
        turn=types.SimpleNamespace(id=turn_id, idx=3, frame_id=None),
    )
    return cid, chars, scene, ctx


def _state(db, cid, char_id):
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (cid, char_id), one=True)
    return json.loads(row["state"] or "{}")


def test_only_the_colocated_character_acquires_the_public_surface(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["public_surfaces"] == 1
    assert result["carrier_opportunities"] == result["acquired"] == 1
    mora = _state(temp_db, cid, chars[0][0])["carried_reports"][0]
    assert mora["claim"] == "the warning bell rang twice"
    assert "hidden mechanism" not in json.dumps(mora)
    assert _state(temp_db, cid, chars[1][0]).get("carried_reports") is None


def test_an_unwitnessed_event_emits_nothing(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    temp_db.qi("UPDATE world_events SET payload='{}' WHERE chat_id=?", (cid,))
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["public_surfaces"] == result["acquired"] == 0
    assert _state(temp_db, cid, chars[0][0]).get("carried_reports") is None


def test_the_setting_gates_acquisition(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db, enabled=False)
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["enabled"] is False and result["acquired"] == 0
    assert _state(temp_db, cid, chars[0][0]).get("carried_reports") is None


def test_the_envelope_moves_with_its_holder_and_is_not_broadcast(temp_db):
    from carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
    scene["positions"]["Mora"] = "road"
    result = advance_carriers(ctx, scene, {"events": []})
    report = _state(temp_db, cid, chars[0][0])["carried_reports"][0]
    assert result["carriers_moved"] == 1
    assert report["route"] == ["square", "road"] and report["hops"] == 1
    # Tavi sharing the destination does not learn by proximity or timer.
    assert _state(temp_db, cid, chars[1][0]).get("carried_reports") is None


def test_checkpoint_restore_rewinds_acquisition_and_route(temp_db):
    from carriers import advance_carriers
    from checkpoints import ensure_checkpoint, restore_checkpoint

    cid, chars, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
    acquired = _state(temp_db, cid, chars[0][0])
    ensure_checkpoint(cid, 4)
    scene["positions"]["Mora"] = "road"
    advance_carriers(ctx, scene, {"events": []})
    restore_checkpoint(cid, 4)
    assert _state(temp_db, cid, chars[0][0]) == acquired


def test_private_projection_is_bounded_and_has_no_hidden_payload():
    from carriers import PAYLOAD_CAP, reports_for_state

    rows = [{"world_event_id": f"e{i}", "claim": f"surface {i}",
             "secret": "never project"} for i in range(PAYLOAD_CAP + 3)]
    projected = reports_for_state({"carried_reports": rows})
    assert len(projected) == PAYLOAD_CAP
    assert [r["world_event_id"] for r in projected] == ["e3", "e4", "e5", "e6"]
    assert all("secret" not in row for row in projected)


def test_carrier_floor_has_no_model_or_provider_call():
    import carriers
    import agents.character as character

    source = inspect.getsource(carriers)
    assert "chat_complete" not in source and "providers" not in source
    character_source = inspect.getsource(character.character_step)
    assert 'payload["carried_reports"]' in character_source
    assert "reports_for_state(stored_state)" in character_source


# ---- crowds as anonymous carriers --------------------------------------
#
# Item 2 of the completion roadmap left one line open — "crowds should also
# become possible information carriers" — and item 3 asks for anonymous
# carriers. The same object closes both, and needs no new travel machinery:
# `crowds.advance_crowds` already walks the one graph everybody walks, so talk
# moves because the market moves.


class TestACrowdCarriesTalk:
    def _crowd(self):
        return crowds.new_crowd(1, "square", band="a throng",
                                composition="market traders", since_turn=1)

    def test_a_crowd_is_never_quoted_by_name(self):
        """Five ledgers already key beings by display name. A crowd has no
        name by construction, and "talk among the market traders" is a source
        a mind can weigh — obviously hearsay, and obviously not a person who
        could be asked."""
        voice = crowds.crowd_voice(self._crowd())
        assert voice == "talk among the market traders"
        assert "crowd:" not in voice

    def test_an_unnamed_crowd_still_has_a_voice(self):
        assert crowds.crowd_voice({}) == "talk going round"

    def test_a_crowd_holds_what_it_was_told(self):
        crowd = crowds.add_hearsay(
            self._crowd(), {"world_event_id": "e1", "claim": "the gate fell"})
        assert [r["claim"] for r in crowds.crowd_hearsay(crowd)] == \
            ["the gate fell"]

    def test_it_does_not_hear_the_same_thing_twice(self):
        crowd = self._crowd()
        for _ in range(3):
            crowd = crowds.add_hearsay(
                crowd, {"world_event_id": "e1", "claim": "the gate fell"})
        assert len(crowds.crowd_hearsay(crowd)) == 1

    def test_a_crowd_is_not_an_archive(self):
        """It is what people are saying right now. The oldest talk stops
        being repeated rather than accumulating forever."""
        crowd = self._crowd()
        for i in range(crowds.CROWD_REPORT_CAP + 3):
            crowd = crowds.add_hearsay(
                crowd, {"world_event_id": "e%d" % i, "claim": "story %d" % i})
        assert len(crowds.crowd_hearsay(crowd)) == crowds.CROWD_REPORT_CAP

    def test_a_crowd_is_exempt_from_the_dialogue_check_and_nothing_else(self):
        """A crowd murmurs continuously — that IS its speech, so there is no
        line in `dialogue_log` to point at. Every other refusal still applies,
        because catching a rumor in a market has to stay knowledge by a beat
        that said so rather than knowledge by proximity."""
        import inspect

        import carriers
        body = inspect.getsource(carriers.apply_tellings)
        gate = body[body.index("said nothing this beat")]
        assert 'speaker.get("crowd") is None and speaker_key not in spoke' \
            in body
        # The co-location, holding and fan-out guards are not conditioned on
        # being a person.
        for guard in ("not in the same room", "cannot pass it on",
                      "has told %d people"):
            after = body[body.index("said nothing this beat"):]
            assert guard in after


class TestALieTravelsLikeTheTruth:
    """Malicious and invented claims enter through the same carrier physics.

    The point is what a listener CANNOT do. A mind that could tell a lie from a
    fact by inspecting its own memory is not a mind that can be deceived, and
    being deceivable is the entire reason this engine keeps objective truth,
    perception, memory and belief in separate layers.
    """

    def test_an_invented_claim_never_reaches_objective_history(self):
        """`world_events` is the ledger of what happened. It must not acquire
        rows for things that did not, so an invented claim is keyed `claim:`
        and lives only in the minds that hold it."""
        import inspect
        import types

        import carriers
        ctx = types.SimpleNamespace(chat=types.SimpleNamespace(id=1),
                                    turn=types.SimpleNamespace(idx=3))
        made_up = carriers._invented_claim("the duke is dead", ctx,
                                           {"name": "Rem", "room": "hall"})
        assert made_up["world_event_id"].startswith("claim:")
        assert made_up["kind"] == "claim"
        # Nothing on the telling path writes objective history.
        assert "INSERT INTO world_events" not in \
            inspect.getsource(carriers.apply_tellings)

    def test_the_liar_knows_and_the_listener_cannot(self):
        """The asymmetry exists at the source ONLY. The speaker's own row says
        `invented`; the copy handed on is shaped exactly like a copy of the
        truth, because a difference a listener could inspect would be a
        deception the fiction cannot support."""
        import inspect

        import carriers
        source = inspect.getsource(carriers.apply_tellings)
        # The copy handed to a listener is built in exactly one place, and it
        # is the same dict whether the claim is true or invented.
        assert source.count('"provenance": "told"') == 1
        assert '"provenance": "invented"' not in source

    def test_a_crowd_does_not_start_things(self):
        """A crowd repeats what reaches it. Letting one ORIGINATE a claim
        would make anonymous talk a source of new facts with nobody behind
        it — an assertion no mind can be held to and no player can chase."""
        import inspect

        import carriers
        assert "a crowd repeats what it heard; it does not start things" \
            in inspect.getsource(carriers.apply_tellings)

    def test_an_invented_claim_can_be_referred_to_later(self):
        """Its id is minted from the text and the speaker, so it can be passed
        on, disputed and recognised like any other. A lie that could not be
        referred to could not be caught out, and being caught out is the only
        interesting thing that ever happens to one."""
        import types

        import carriers
        ctx = types.SimpleNamespace(
            chat={"id": 1}, turn=types.SimpleNamespace(idx=3))
        ctx.chat = types.SimpleNamespace(id=1)
        speaker = {"name": "Rem", "room": "hall"}
        first = carriers._invented_claim("the duke is dead", ctx, speaker)
        again = carriers._invented_claim("the duke is dead", ctx, speaker)
        other = carriers._invented_claim("the duke lives", ctx, speaker)
        assert first["world_event_id"] == again["world_event_id"]
        assert first["world_event_id"] != other["world_event_id"]
        assert first["retellings"] == 0 and first["told_by"] == ""


class TestAftermathIsMetOnArrival:
    """A public surface used to be offered ONLY on the beat it fired.

    Consequences fire off-screen on a clock, in rooms chosen precisely because
    nobody is standing in them — so a witness path that required being present
    at the exact instant could essentially never fire. Measured on a 20-beat
    drive: one public surface emitted, zero acquisitions, and a character
    walked into that room the following turn, looked directly at the barred
    gate, and learned nothing. Forever.

    The design already had the answer: consequences "are met as state when
    someone next stands where they landed".
    """

    def test_a_body_reads_what_is_still_standing_in_the_room(self):
        import inspect

        import carriers
        body = inspect.getsource(carriers.advance_carriers)
        assert "standing_rows" in body
        assert "event_rows + here" in body

    def test_it_is_arrival_and_not_archaeology(self):
        """Walking in and seeing the barred gate, not inheriting every event
        the room has ever hosted."""
        import carriers

        assert carriers.ARRIVAL_SURFACES <= 3

    def test_only_a_public_surface_is_readable(self):
        """A concealed act emits no witnessed surface, so arriving later must
        teach nothing — the firewall is structural, not instructed."""
        import inspect

        import carriers
        body = inspect.getsource(carriers.advance_carriers)
        gathered = body[body.index("standing_rows = []"):body.index("public_surfaces =")]
        assert "if witnessed:" in gathered


class TestTimeDoesNotRunBackwards:
    """`end_seconds` is an ABSOLUTE position on the story clock.

    A model emitting `start_seconds: 0` on every beat — an entirely natural
    reading of a field called "start" — reset world time to the length of its
    own beat, over and over. Measured on a fifty-beat quest with several
    explicit hour-long skips: the clock finished at 30.0 seconds while its own
    `display` read "an hour and a half".

    Everything windowed on seconds went silent with it. Routine residue never
    fired once, because the gap between a room's last sighting and now was
    always zero — so the mechanism that tells a returning player how a place
    changed while they were away could not run at all.
    """

    def test_the_clock_never_moves_backward(self):
        import inspect

        import commit
        body = inspect.getsource(commit)
        assert "if claimed < was:" in body
        assert "ran backwards" in body

    def test_a_backward_beat_still_gets_its_duration(self):
        """The elapsed time is the part the fiction actually asserted. A beat
        that took an hour advances the clock by an hour, rather than being
        discarded for disagreeing about where it started."""
        import inspect

        import commit
        body = inspect.getsource(commit)
        guard = body[body.index("if claimed < was:"):]
        assert "duration_seconds" in guard.split("clock[")[0]


class TestACrowdWitnessesItsOwnRoom:
    """A crowd standing where a public surface lands takes it up.

    The crowds module could hold hearsay and `apply_tellings` could make one
    retell — but nothing ever put anything IN a crowd, so across a played
    fifty-beat quest two throngs stood in eventful rooms for forty beats and
    finished holding nothing. The anonymous-carrier layer the roadmap calls
    built was reachable only through an explicit Director telling that no
    beat ever wrote.
    """

    def _crowd_in(self, db, cid, room):
        crowd = crowds.new_crowd(cid, room, band="a throng",
                                 composition="market traders", since_turn=1)
        db.wset(cid, "crowds", [crowd])
        return crowd

    def test_the_colocated_crowd_takes_up_the_public_surface(self, temp_db):
        from carriers import advance_carriers

        cid, _chars, scene, ctx = _world(temp_db)
        self._crowd_in(temp_db, cid, "square")
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["crowd_opportunities"] == result["crowd_acquired"] == 1
        held = crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0])
        assert [r["claim"] for r in held] == ["the warning bell rang twice"]
        # Verbatim at the source: the square contains eyewitnesses, and a
        # crowd wrong about what it watched together would be the engine
        # being wrong, not a rumour being a rumour.
        assert held[0]["retellings"] == 0
        assert held[0]["provenance"] == "witnessed_surface"

    def test_a_crowd_elsewhere_learns_nothing(self, temp_db):
        """Same physics as a body: no timer, no broadcast — co-location with
        the surface or silence."""
        from carriers import advance_carriers

        cid, _chars, scene, ctx = _world(temp_db)
        self._crowd_in(temp_db, cid, "road")
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["crowd_acquired"] == 0
        assert crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0]) == []

    def test_it_does_not_take_the_same_surface_twice(self, temp_db):
        """A rerun or a later beat over the same standing surface must fold,
        not stack — the same stable-id discipline every commit writer keeps."""
        from carriers import advance_carriers

        cid, _chars, scene, ctx = _world(temp_db)
        self._crowd_in(temp_db, cid, "square")
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        again = advance_carriers(ctx, scene, {"events": []})
        assert again["crowd_acquired"] == 0
        held = crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0])
        assert len(held) == 1

    def test_the_setting_gates_crowd_acquisition_too(self, temp_db):
        from carriers import advance_carriers

        cid, _chars, scene, ctx = _world(temp_db, enabled=False)
        self._crowd_in(temp_db, cid, "square")
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0]) == []


class TestADormantBodyCanBeTold:
    """Being dormant is a decision about engine spend, not a claim that the
    body left the world.

    `_cast_index` read only the active cast, so a dormant character standing
    in the room was unaddressable as a LISTENER: a messenger could reach the
    villain's own hall, speak, and have the telling refused as "names someone
    unregistered". The acquisition path had already been widened to the extant
    cast for exactly this reason; the telling path had not, and the asymmetry
    made the one remote mind the agent rung exists for untellable.
    """

    def _story(self, db):
        import time
        cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("Telling", "", time.time()))
        chars = {}
        for name, uid, status in (("Mora", "mora_uid", "active"),
                                  ("Maelor", "maelor_uid", "dormant")):
            sheet = json.dumps({"identity": {"name": name, "uid": uid}})
            char_id = db.qi(
                "INSERT INTO characters(name,sheet,source,created) "
                "VALUES(?,?,?,?)", (name, sheet, "{}", time.time()))
            db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                  "VALUES(?,?,?,'{}')", (cid, char_id, status))
            chars[name] = char_id
        db.wset(cid, "living_world", {"rumor_ledger": "floor"})
        scene = {"rooms": {"hall": {"name": "Hall"}},
                 "positions": {"Mora": "hall", "Maelor": "hall"}}
        state = {"carried_reports": [{
            "world_event_id": "world_bell", "source_event_id": "",
            "claim": "the warning bell rang twice", "kind": "consequence",
            "occurred_at": 50.0, "retellings": 0}]}
        db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
              (json.dumps(state), cid, chars["Mora"]))
        ctx = types.SimpleNamespace(
            chat=types.SimpleNamespace(id=cid),
            turn=types.SimpleNamespace(idx=5, frame_id=None),
            director_resolve={"dialogue_log": [
                {"speaker": "Mora", "text": "The bell rang twice."}]},
            director_establish=None)
        return cid, chars, scene, ctx

    def test_a_dormant_listener_in_the_room_receives_the_copy(self, temp_db):
        from carriers import apply_tellings

        cid, chars, scene, ctx = self._story(temp_db)
        applied, rejected = apply_tellings(
            ctx, scene, [{"speaker": "Mora", "listener": "Maelor",
                          "world_event_id": "world_bell"}])
        assert (applied, rejected) == (1, [])
        held = _state(temp_db, cid, chars["Maelor"])["carried_reports"]
        assert held[0]["provenance"] == "told"
        assert held[0]["told_by"] == "Mora"
        assert held[0]["retellings"] == 1

    def test_a_dormant_speaker_still_cannot_tell(self, temp_db):
        """The widening is listener-side only by construction: a dormant mind
        the engine did not run said nothing, so the spoke-this-beat gate — 
        which reads the dialogue_log — has no line to find."""
        from carriers import apply_tellings

        cid, chars, scene, ctx = self._story(temp_db)
        applied, rejected = apply_tellings(
            ctx, scene, [{"speaker": "Maelor", "listener": "Mora",
                          "world_event_id": "world_bell"}])
        assert applied == 0
        assert any("said nothing this beat" in r for r in rejected)


class TestEveryClockReaderSharesTheMonotonicRule:
    """The guard lived only in the scene commit; `prepare_memory_commit` read
    the raw `end_seconds` beside it.

    Same class of defect one seam over: a beat whose clock claim the scene
    commit had just refused still stamped affect decay, strain windows and
    belief provenance with the backwards value — psychology windowed on a
    clock the world itself did not keep.
    """

    def test_a_backwards_claim_advances_by_its_duration(self):
        from commit import _monotonic_elapsed

        elapsed, backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0},
            {"start_seconds": 0, "duration_seconds": 30, "end_seconds": 30})
        assert elapsed == 5430.0
        assert backwards == (30.0, 5400.0)

    def test_an_honest_claim_is_taken_at_its_word(self):
        from commit import _monotonic_elapsed

        elapsed, backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0},
            {"duration_seconds": 3600, "end_seconds": 9000})
        assert (elapsed, backwards) == (9000.0, None)

    def test_a_diff_with_no_claim_holds_the_clock(self):
        from commit import _monotonic_elapsed

        elapsed, backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0}, {"display_advance": "later"})
        assert (elapsed, backwards) == (5400.0, None)

    def test_the_memory_seam_reads_through_the_same_helper(self):
        """One rule, one spelling: a second reader with its own arithmetic is
        how the two disagreed in the first place."""
        import inspect

        import commit
        body = inspect.getsource(commit.prepare_memory_commit)
        assert "_monotonic_elapsed(_clock, _time_diff)" in body
        assert 'get("end_seconds"' not in body


class TestThePlayerStandsWhereItLands:
    """The player was the one body in the room that could not learn.

    `0bed7cf` made the player a SENDER; acquisition is the other half, and
    until now it iterated `extant_cast` rows and wrote `set_char_state`, so a
    persona had neither the row to be found by nor the column to be written
    to. Corin could stand in the square while the warning bell rang, beside
    an NPC who acquired it, and hold nothing — forever, and without the
    metrics recording that a chance had been declined, because the loop never
    counted an opportunity it could not see.

    It is the same widening this loop already took once from `active_cast` to
    `extant_cast`, one ring further out: a body standing in the room where
    something happened learns it.
    """

    def _played(self, db, *, at="square", others="road"):
        cid, chars, scene, ctx = _world(db, persona="Corin")
        scene["positions"] = {"Mora": others, "Tavi": "road", "Corin": at}
        # Spelled as edges so a courier has a door to walk through; the
        # acquisition tests do not care either way.
        scene["rooms"]["square"]["adjacent"] = [{"to": "road",
                                                 "barrier": "open"}]
        scene["rooms"]["road"]["adjacent"] = [{"to": "square",
                                               "barrier": "open"}]
        return cid, chars, scene, ctx

    def _held(self, db, cid):
        from carriers import PERSONA_STATE_KEY

        return (db.wget(cid, PERSONA_STATE_KEY, {}) or {}).get(
            "carried_reports") or []

    def test_the_player_witnesses_their_own_room(self, temp_db):
        from carriers import advance_carriers

        cid, _chars, scene, ctx = self._played(temp_db)
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["carrier_opportunities"] == result["acquired"] == 1
        held = self._held(temp_db, cid)
        assert [r["claim"] for r in held] == ["the warning bell rang twice"]
        # The same terms as anyone else's: an eyewitness has been told
        # nothing, so nothing is degraded and nobody is credited.
        assert held[0]["provenance"] == "witnessed_surface"
        assert (held[0]["retellings"], held[0]["hops"]) == (0, 0)
        assert held[0]["route"] == ["square"]

    def test_the_player_reads_what_was_still_standing_on_arrival(self, temp_db):
        """The arrival window is shared code, not a second one: the surfaces
        `standing_rows` gathers and the `ARRIVAL_SURFACES` slice that bounds
        them are the same objects the cast is offered."""
        from carriers import advance_carriers

        cid, _chars, scene, ctx = self._played(temp_db)
        result = advance_carriers(ctx, scene, {"events": []})
        assert result["public_surfaces"] == 0 and result["acquired"] == 1
        assert self._held(temp_db, cid)[0]["claim"] == \
            "the warning bell rang twice"

    def test_the_envelope_moves_because_the_player_walked(self, temp_db):
        from carriers import advance_carriers

        cid, _chars, scene, ctx = self._played(temp_db)
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        scene["positions"]["Corin"] = "road"
        result = advance_carriers(ctx, scene, {"events": []})
        report = self._held(temp_db, cid)[0]
        assert result["carriers_moved"] == 1
        assert report["route"] == ["square", "road"] and report["hops"] == 1

    def test_the_player_elsewhere_learns_nothing(self, temp_db):
        """No timer and no broadcast for the player either: co-location with
        the surface, or silence."""
        from carriers import advance_carriers

        cid, _chars, scene, ctx = self._played(temp_db, at="road",
                                               others="square")
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["acquired"] == 1          # Mora, in the square
        assert self._held(temp_db, cid) == []

    def test_the_same_surface_is_not_taken_twice(self, temp_db):
        from carriers import advance_carriers

        cid, _chars, scene, ctx = self._played(temp_db)
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        again = advance_carriers(ctx, scene, {"events": []})
        assert again["acquired"] == 0
        assert len(self._held(temp_db, cid)) == 1

    def test_the_players_acquisition_rewinds_with_the_story(self, temp_db):
        """The other home has to rewind too. A cast member's reports ride the
        `chat_chars` snapshot; the player's ride the `world` one, and a
        restore that rewound only the first would leave the player holding a
        report of an event the story has un-happened."""
        from carriers import advance_carriers
        from checkpoints import ensure_checkpoint, restore_checkpoint

        cid, _chars, scene, ctx = self._played(temp_db)
        ensure_checkpoint(cid, 4)
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert self._held(temp_db, cid)
        restore_checkpoint(cid, 4)
        assert self._held(temp_db, cid) == []

    def test_a_chat_with_no_resolvable_persona_is_untouched(self, temp_db):
        """Failing toward fewer carriers is the safe direction. `_world`
        without a persona builds the chat object the rest of this file uses,
        and the beat must land exactly as it did before."""
        from carriers import PERSONA_STATE_KEY, advance_carriers

        cid, chars, scene, ctx = _world(temp_db)
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["carrier_opportunities"] == result["acquired"] == 1
        assert _state(temp_db, cid, chars[0][0])["carried_reports"]
        assert temp_db.wget(cid, PERSONA_STATE_KEY, {}) == {}

    def test_a_cast_member_of_the_same_name_is_the_more_specific_body(
            self, temp_db):
        """A registered body with a row wins the name — the preference
        `_cast_index` already encodes with `setdefault`. Folded here at the
        one place carriers are enumerated, because a player admitted beside
        their namesake would acquire the surface twice, into two homes, and
        count the room's one opportunity as two."""
        from carriers import PERSONA_STATE_KEY, advance_carriers

        cid, _chars, scene, ctx = _world(temp_db, persona="Mora")
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["carrier_opportunities"] == result["acquired"] == 1
        assert temp_db.wget(cid, PERSONA_STATE_KEY, {}) == {}

    def test_the_player_sends_on_what_the_player_witnessed(self, temp_db):
        """The two halves meeting, which is the whole point of either. What
        Corin saw in the square is held where a persona can hold it, and
        `run_couriers` finds it there through the same `_hold_report` a
        registered sender is checked with."""
        from carriers import advance_carriers
        from couriers import run_couriers

        cid, _chars, scene, ctx = self._played(temp_db)
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        metrics, rejected = run_couriers(ctx, scene, [{
            "op": "send", "sender": "Corin", "to_room": "road",
            "world_event_id": "world_bell", "method": "word",
            "pace": "riding", "description": "a boy on a borrowed pony"}])
        assert rejected == []
        assert metrics["dispatched"] == 1
        rider = (temp_db.wget(cid, "couriers", []) or [])[0]
        assert rider["report"]["claim"] == "the warning bell rang twice"
        # What rides away is a retelling, as it would be from any other
        # mouth; the eyewitness row stays verbatim in the player's own hands.
        assert rider["report"]["provenance"] == "told"
        assert self._held(temp_db, cid)[0]["provenance"] == "witnessed_surface"
