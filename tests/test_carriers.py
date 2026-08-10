"""Approach C floor: public surfaces move only inside physical holders."""

from __future__ import annotations

import inspect
import json
import time
import types

import crowds


def _world(db, *, enabled=True):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Carrier story", "", time.time()))
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
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
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
