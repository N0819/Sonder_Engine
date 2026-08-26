"""Approach C floor: public surfaces move only inside physical holders."""

from __future__ import annotations

import json
import time
import types

from world import crowds


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
    from story.carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["public_surfaces"] == 1
    assert result["carrier_opportunities"] == result["acquired"] == 1
    mora = _state(temp_db, cid, chars[0][0])["carried_reports"][0]
    assert mora["claim"] == "the warning bell rang twice"
    assert "hidden mechanism" not in json.dumps(mora)
    assert _state(temp_db, cid, chars[1][0]).get("carried_reports") is None


def test_firsthand_surface_replaces_an_older_hearsay_copy(temp_db):
    from story.carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    temp_db.qi(
        "UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
        (json.dumps({"carried_reports": [{
            "world_event_id": "world_bell", "claim": "a bell may have rung",
            "kind": "consequence", "occurred_at": 50.0,
            "acquired_location": "square", "current_location": "square",
            "route": ["square"], "hops": 0, "retellings": 2,
            "told_by": "a passerby", "provenance": "told",
        }]}), cid, chars[0][0]))

    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
    report = _state(temp_db, cid, chars[0][0])["carried_reports"][0]
    assert report["claim"] == "the warning bell rang twice"
    assert report["provenance"] == "witnessed_surface"
    assert report["retellings"] == 0 and report["told_by"] == ""


def test_an_unwitnessed_event_emits_nothing(temp_db):
    from story.carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db)
    temp_db.qi("UPDATE world_events SET payload='{}' WHERE chat_id=?", (cid,))
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["public_surfaces"] == result["acquired"] == 0
    assert _state(temp_db, cid, chars[0][0]).get("carried_reports") is None


def test_information_physics_is_not_disabled_by_the_legacy_setting(temp_db):
    from story.carriers import advance_carriers

    cid, chars, scene, ctx = _world(temp_db, enabled=False)
    result = advance_carriers(
        ctx, scene, {"events": [{"event_id": "world_bell"}]})
    assert result["enabled"] is True and result["acquired"] == 1
    assert _state(temp_db, cid, chars[0][0])["carried_reports"][0][
        "world_event_id"] == "world_bell"


def test_the_envelope_moves_with_its_holder_and_is_not_broadcast(temp_db):
    from story.carriers import advance_carriers

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
    from story.carriers import advance_carriers
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint

    cid, chars, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
    acquired = _state(temp_db, cid, chars[0][0])
    ensure_checkpoint(cid, 4)
    scene["positions"]["Mora"] = "road"
    advance_carriers(ctx, scene, {"events": []})
    restore_checkpoint(cid, 4)
    assert _state(temp_db, cid, chars[0][0]) == acquired


def test_private_projection_is_bounded_and_has_no_hidden_payload():
    from story.carriers import PAYLOAD_CAP, reports_for_state

    rows = [{"world_event_id": f"e{i}", "claim": f"surface {i}",
             "secret": "never project"} for i in range(PAYLOAD_CAP + 3)]
    projected = reports_for_state({"carried_reports": rows})
    assert len(projected) == PAYLOAD_CAP
    assert [r["world_event_id"] for r in projected] == ["e3", "e4", "e5", "e6"]
    assert all("secret" not in row for row in projected)


def _crowd_telling_world(db):
    """A crowd in the square holding the bell, and Mora standing in it."""
    cid, chars, scene, ctx = _world(db)
    crowd = crowds.new_crowd(cid, "square", band="a throng",
                             composition="market traders", since_turn=1)
    crowd = crowds.add_hearsay(crowd, {
        "world_event_id": "world_bell", "source_event_id": "",
        "claim": "the warning bell rang twice", "kind": "consequence",
        "occurred_at": 50.0, "retellings": 0})
    db.wset(cid, "crowds", [crowd])
    scene["positions"]["Mora"] = "square"
    ctx.director_resolve = {"dialogue_log": []}
    ctx.director_establish = None
    return cid, chars, scene, ctx, crowd["uid"]


def test_carrier_floor_has_no_model_or_provider_call(temp_db, monkeypatch):
    """THE PROVIDER SEAM, NOT THE SPELLING OF IT.

    This asserted that the strings "chat_complete" and "providers" do not
    appear in the module's source -- which passes for any spelling that avoids
    those two substrings: an aliased import, a call through
    `llm.llm_quality.complete_validated_json`, or a provider reached through
    one of the modules `carriers.py` already imports (`world.degradation`,
    `world.living_world`, `story.scene`). The property is "this floor makes no
    model call"; the assertion was about text.

    So the doors refuse instead, and the whole carrier path is driven across
    them: acquisition, movement, and a telling.
    """
    from story.carriers import advance_carriers, apply_tellings

    def refuse(*a, **kw):
        raise AssertionError("the carrier floor made a model call")

    import llm.llm_quality as llm_quality
    import llm.providers as providers
    monkeypatch.setattr(providers, "chat_complete", refuse)
    monkeypatch.setattr(providers, "chat_stream", refuse, raising=False)
    monkeypatch.setattr(llm_quality, "complete_validated_json", refuse)

    cid, chars, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
    scene["positions"]["Mora"] = "road"
    advance_carriers(ctx, scene, {"events": []})
    scene["positions"]["Mora"] = "road"
    scene["positions"]["Tavi"] = "road"
    ctx.director_resolve = {"dialogue_log": [
        {"speaker": "Mora", "text": "The bell rang twice."}]}
    ctx.director_establish = None
    applied, _rejected = apply_tellings(
        ctx, scene, [{"speaker": "Mora", "listener": "Tavi",
                      "world_event_id": "world_bell"}])
    assert applied == 1


def test_what_a_mind_is_handed_is_the_bounded_projection_of_its_own_state(
        temp_db):
    """The other half of the deleted assertion, which read
    `agents/character.py`'s source for two literal expressions. What matters
    is that the payload is `reports_for_state` of THAT character's stored
    state -- bounded, and holding nothing of anybody else's."""
    from story.carriers import advance_carriers, reports_for_state

    cid, chars, scene, ctx = _world(temp_db)
    advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})

    mora = reports_for_state(_state(temp_db, cid, chars[0][0]))
    tavi = reports_for_state(_state(temp_db, cid, chars[1][0]))
    assert [r["claim"] for r in mora] == ["the warning bell rang twice"]
    assert tavi == []
    # The event's private half never leaves the ledger it was written in.
    assert "hidden mechanism" not in json.dumps(mora)


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

    def test_a_crowd_is_exempt_from_the_dialogue_check_and_nothing_else(
            self, temp_db):
        """A crowd murmurs continuously — that IS its speech, so there is no
        line in `dialogue_log` to point at. Every other refusal still applies,
        because catching a rumor in a market has to stay knowledge by a beat
        that said so rather than knowledge by proximity.

        Driven rather than read. This asserted four literal source spellings,
        one of them through `body[body.index("said nothing this beat")]` --
        which indexes a string with an int, so the `gate` it bound was a
        single character and was never read again. Extracting the condition
        into a named predicate failed that test; deleting the runtime effect
        and leaving the string passed it.
        """
        from story.carriers import apply_tellings

        cid, _chars, scene, ctx, throng = _crowd_telling_world(temp_db)
        assert ctx.director_resolve["dialogue_log"] == []   # nobody spoke

        applied, rejected = apply_tellings(
            ctx, scene, [{"speaker": throng, "listener": "Mora",
                          "world_event_id": "world_bell"}])
        assert (applied, rejected) == (1, [])

        # ... and nothing else is waived. A crowd in another room is not in
        # the room.
        cid, _chars, scene, ctx, throng = _crowd_telling_world(temp_db)
        scene["positions"]["Mora"] = "road"
        applied, rejected = apply_tellings(
            ctx, scene, [{"speaker": throng, "listener": "Mora",
                          "world_event_id": "world_bell"}])
        assert applied == 0
        assert any("same room" in r for r in rejected)

        # ... and a crowd cannot pass on what it does not hold.
        cid, _chars, scene, ctx, throng = _crowd_telling_world(temp_db)
        applied, rejected = apply_tellings(
            ctx, scene, [{"speaker": throng, "listener": "Mora",
                          "world_event_id": "never_happened"}])
        assert applied == 0
        assert any("cannot pass it on" in r for r in rejected)


class TestALieTravelsLikeTheTruth:
    """Malicious and invented claims enter through the same carrier physics.

    The point is what a listener CANNOT do. A mind that could tell a lie from a
    fact by inspecting its own memory is not a mind that can be deceived, and
    being deceivable is the entire reason this engine keeps objective truth,
    perception, memory and belief in separate layers.
    """

    def test_an_invented_claim_never_reaches_objective_history(self, temp_db):
        """`world_events` is the ledger of what happened. It must not acquire
        rows for things that did not, so an invented claim is keyed `claim:`
        and lives only in the minds that hold it.

        Counted rather than grepped: the old version asserted that the string
        "INSERT INTO world_events" is absent from one function's source, which
        says nothing about the helpers it calls.
        """
        import types

        from story import carriers

        ctx = types.SimpleNamespace(chat=types.SimpleNamespace(id=1),
                                    turn=types.SimpleNamespace(idx=3))
        made_up = carriers._invented_claim("the duke is dead", ctx,
                                           {"name": "Rem", "room": "hall"})
        assert made_up["world_event_id"].startswith("claim:")
        assert made_up["kind"] == "claim"

        cid, _chars, scene, ctx = _world(temp_db)
        scene["positions"]["Tavi"] = "square"
        ctx.director_resolve = {"dialogue_log": [
            {"speaker": "Mora", "text": "The duke is dead."}]}
        ctx.director_establish = None
        before = temp_db.q("SELECT COUNT(*) AS n FROM world_events "
                           "WHERE chat_id=?", (cid,), one=True)["n"]
        applied, _rejected = carriers.apply_tellings(
            ctx, scene, [{"speaker": "Mora", "listener": "Tavi",
                          "claim": "the duke is dead"}])
        after = temp_db.q("SELECT COUNT(*) AS n FROM world_events "
                          "WHERE chat_id=?", (cid,), one=True)["n"]
        assert applied == 1 and after == before

    def test_the_liar_knows_and_the_listener_cannot(self, temp_db):
        """The asymmetry exists at the source ONLY. The speaker's own row says
        `invented`; the copy handed on is shaped exactly like a copy of the
        truth, because a difference a listener could inspect would be a
        deception the fiction cannot support.

        Compared rather than counted: this asserted that the literal
        `"provenance": "told"` appears exactly once in the function's source,
        which is a fact about how the dict is written and not about what a
        listener receives.
        """
        from story.carriers import advance_carriers, apply_tellings

        # A lie.
        cid, chars, scene, ctx = _world(temp_db)
        scene["positions"]["Tavi"] = "square"
        ctx.director_resolve = {"dialogue_log": [
            {"speaker": "Mora", "text": "The duke is dead."}]}
        ctx.director_establish = None
        apply_tellings(ctx, scene, [{"speaker": "Mora", "listener": "Tavi",
                                     "claim": "the duke is dead"}])
        liar = _state(temp_db, cid, chars[0][0])["carried_reports"][-1]
        lie_heard = _state(temp_db, cid, chars[1][0])["carried_reports"][-1]

        # The truth, told the same way.
        cid, chars, scene, ctx = _world(temp_db)
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        scene["positions"]["Tavi"] = "square"
        ctx.director_resolve = {"dialogue_log": [
            {"speaker": "Mora", "text": "The bell rang twice."}]}
        ctx.director_establish = None
        apply_tellings(ctx, scene, [{"speaker": "Mora", "listener": "Tavi",
                                     "world_event_id": "world_bell"}])
        truth_heard = _state(temp_db, cid, chars[1][0])["carried_reports"][-1]

        # The speaker knows what they did.
        assert liar["provenance"] == "invented"
        # The listener holds the same SHAPE either way, and nothing in it
        # says which one this was.
        assert set(lie_heard) == set(truth_heard)
        assert lie_heard["provenance"] == truth_heard["provenance"] == "told"
        assert "invent" not in json.dumps(lie_heard)

    def test_a_crowd_does_not_start_things(self, temp_db):
        """A crowd repeats what reaches it. Letting one ORIGINATE a claim
        would make anonymous talk a source of new facts with nobody behind
        it — an assertion no mind can be held to and no player can chase.

        Refused in the running code, not asserted as a comment present in the
        source: the previous version passed on the strength of the sentence
        alone, and would have gone on passing with the `continue` deleted.
        """
        from story.carriers import apply_tellings

        cid, chars, scene, ctx, throng = _crowd_telling_world(temp_db)
        applied, rejected = apply_tellings(
            ctx, scene, [{"speaker": throng, "listener": "Mora",
                          "claim": "the duke is dead"}])

        assert applied == 0
        assert any("does not start things" in r for r in rejected)
        assert _state(temp_db, cid, chars[0][0]).get("carried_reports") is None
        held = crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0])
        assert [r["claim"] for r in held] == ["the warning bell rang twice"]

    def test_an_invented_claim_can_be_referred_to_later(self):
        """Its id is minted from the text and the speaker, so it can be passed
        on, disputed and recognised like any other. A lie that could not be
        referred to could not be caught out, and being caught out is the only
        interesting thing that ever happens to one."""
        import types

        from story import carriers
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

    def test_a_body_reads_what_is_still_standing_in_the_room(self, temp_db):
        """Driven, not read. The old version asserted two identifiers appear
        in the function's source, which stays true if the rows they gather
        are never offered to anybody."""
        from story.carriers import advance_carriers

        cid, chars, scene, ctx = _world(temp_db)
        scene["positions"]["Mora"] = "road"
        # The bell rings in the square while Mora is elsewhere.
        assert advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})["acquired"] == 0
        # She walks in on a later beat that emits nothing of its own.
        scene["positions"]["Mora"] = "square"
        result = advance_carriers(ctx, scene, {"events": []})

        assert result["public_surfaces"] == 0 and result["acquired"] == 1
        held = _state(temp_db, cid, chars[0][0])["carried_reports"]
        assert [r["claim"] for r in held] == ["the warning bell rang twice"]

    def test_it_is_arrival_and_not_archaeology(self):
        """Walking in and seeing the barred gate, not inheriting every event
        the room has ever hosted."""
        from story import carriers

        assert carriers.ARRIVAL_SURFACES <= 3

    def test_only_a_public_surface_is_readable(self, temp_db):
        """A concealed act emits no witnessed surface, so arriving later must
        teach nothing — the firewall is structural, not instructed.

        The event's private half is what the old assertion could not see: it
        checked that `if witnessed:` appears inside a slice of the function's
        text, which says nothing about what the arriver ends up holding.
        """
        from story.carriers import advance_carriers

        cid, chars, scene, ctx = _world(temp_db)
        temp_db.qi("UPDATE world_events SET payload=? WHERE chat_id=?",
                   (json.dumps({"what": "the hidden mechanism failed",
                                "witnessed": ""}), cid))
        scene["positions"]["Mora"] = "road"
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        scene["positions"]["Mora"] = "square"
        result = advance_carriers(ctx, scene, {"events": []})

        assert result["acquired"] == 0
        assert _state(temp_db, cid, chars[0][0]).get("carried_reports") is None


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
        """Answered by the function, not by its text. Both halves of this
        used to be substring searches over source -- one of them over a
        DIFFERENT function's source, so it went on passing while the guard it
        named moved packages twice.
        """
        from persist.commit import _monotonic_elapsed

        elapsed, backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0},
            {"start_seconds": 0, "duration_seconds": 0, "end_seconds": 30})
        assert elapsed >= 5400.0
        assert backwards == (30.0, 5400.0)   # and the caller is told

    def test_a_backward_beat_still_gets_its_duration(self):
        """The elapsed time is the part the fiction actually asserted. A beat
        that took an hour advances the clock by an hour, rather than being
        discarded for disagreeing about where it started."""
        from persist.commit import _monotonic_elapsed

        elapsed, _backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0},
            {"start_seconds": 0, "duration_seconds": 3600, "end_seconds": 3600})
        assert elapsed == 9000.0


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
        from story.carriers import advance_carriers

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
        from story.carriers import advance_carriers

        cid, _chars, scene, ctx = _world(temp_db)
        self._crowd_in(temp_db, cid, "road")
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["crowd_acquired"] == 0
        assert crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0]) == []

    def test_it_does_not_take_the_same_surface_twice(self, temp_db):
        """A rerun or a later beat over the same standing surface must fold,
        not stack — the same stable-id discipline every commit writer keeps."""
        from story.carriers import advance_carriers

        cid, _chars, scene, ctx = _world(temp_db)
        self._crowd_in(temp_db, cid, "square")
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        again = advance_carriers(ctx, scene, {"events": []})
        assert again["crowd_acquired"] == 0
        held = crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0])
        assert len(held) == 1

    def test_legacy_setting_cannot_disable_crowd_witnessing(self, temp_db):
        from story.carriers import advance_carriers

        cid, _chars, scene, ctx = _world(temp_db, enabled=False)
        self._crowd_in(temp_db, cid, "square")
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert crowds.crowd_hearsay(temp_db.wget(cid, "crowds", [])[0])[0][
            "world_event_id"] == "world_bell"


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
        from story.carriers import apply_tellings

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
        from story.carriers import apply_tellings

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
        from persist.commit import _monotonic_elapsed

        elapsed, backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0},
            {"start_seconds": 0, "duration_seconds": 30, "end_seconds": 30})
        assert elapsed == 5430.0
        assert backwards == (30.0, 5400.0)

    def test_an_honest_claim_is_taken_at_its_word(self):
        from persist.commit import _monotonic_elapsed

        elapsed, backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0},
            {"duration_seconds": 3600, "end_seconds": 9000})
        assert (elapsed, backwards) == (9000.0, None)

    def test_a_diff_with_no_claim_holds_the_clock(self):
        from persist.commit import _monotonic_elapsed

        elapsed, backwards = _monotonic_elapsed(
            {"elapsed_seconds": 5400.0}, {"display_advance": "later"})
        assert (elapsed, backwards) == (5400.0, None)

    def test_the_memory_seam_reads_through_the_same_helper(self):
        """One rule, one spelling: a second reader with its own arithmetic is
        how the two disagreed in the first place.

        STILL A SOURCE ASSERTION, and the last one in this file. Every other
        one here has been driven instead; this one needs a seam
        `prepare_memory_commit` does not offer -- there is no way to observe
        which clock it stamped without running a commit -- and inventing one
        belongs to whoever owns `persist/`.
        """
        import inspect

        from persist import commit
        body = inspect.getsource(commit.prepare_memory_commit)
        # The spelling gained the floor flag when a silent beat started
        # costing the clock: this seam stamps affect, strain and belief
        # windows, so it must charge exactly what the scene commit charges
        # or a story's psychology runs ten seconds behind its world on
        # every timeless beat (130 of 2,614 resolved turns, measured
        # 2026-08-25). The pin's intent is unchanged -- one helper, no
        # local arithmetic.
        assert "_monotonic_elapsed(" in body
        assert "_clock, _time_diff" in body
        assert "floor=" in body
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
        from story.carriers import PERSONA_STATE_KEY

        return (db.wget(cid, PERSONA_STATE_KEY, {}) or {}).get(
            "carried_reports") or []

    def test_the_player_witnesses_their_own_room(self, temp_db):
        from story.carriers import advance_carriers

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
        from story.carriers import advance_carriers

        cid, _chars, scene, ctx = self._played(temp_db)
        result = advance_carriers(ctx, scene, {"events": []})
        assert result["public_surfaces"] == 0 and result["acquired"] == 1
        assert self._held(temp_db, cid)[0]["claim"] == \
            "the warning bell rang twice"

    def test_the_envelope_moves_because_the_player_walked(self, temp_db):
        from story.carriers import advance_carriers

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
        from story.carriers import advance_carriers

        cid, _chars, scene, ctx = self._played(temp_db, at="road",
                                               others="square")
        result = advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})
        assert result["acquired"] == 1          # Mora, in the square
        assert self._held(temp_db, cid) == []

    def test_the_same_surface_is_not_taken_twice(self, temp_db):
        from story.carriers import advance_carriers

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
        from story.carriers import advance_carriers
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint

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
        from story.carriers import PERSONA_STATE_KEY, advance_carriers

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
        from story.carriers import PERSONA_STATE_KEY, advance_carriers

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
        from story.carriers import advance_carriers
        from story.couriers import run_couriers

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


# --- the crowd roster belongs to an era too ---------------------------------
#
# `_crowd_index(cid, scene, frame_id)` read neither `scene` nor `frame_id`.
# Its body was one `wget`, which is frame-scoped only INCIDENTALLY -- `crowds`
# is in `db.FRAME_SCOPED_WORLD_KEYS`, so the read redirects on the ambient
# `active_frame_id` contextvar that a pipeline run happens to have set. Any
# caller outside a pipeline run, or one whose turn belongs to a different
# frame than the ambient one, got the wrong era's crowds while passing the
# right frame in.

class TestCrowdIndexIsFrameScoped:
    def test_the_frame_passed_in_is_the_frame_read(self, temp_db):
        from core.db import wset_for_frame
        from story import carriers
        from web import app

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Crowds", "", time.time()))
        past = app.frames_create(cid, {"label": "Past", "ordinal": -10, "kind": "past"})
        future = app.frames_create(cid, {"label": "Future", "ordinal": 10, "kind": "future"})
        wset_for_frame(cid, crowds.CROWDS_WORLD_KEY,
                       [{"uid": "market_throng", "room_uid": "square"}], past["id"])
        wset_for_frame(cid, crowds.CROWDS_WORLD_KEY,
                       [{"uid": "funeral_crowd", "room_uid": "square"}], future["id"])

        assert set(carriers._crowd_index(cid, past["id"])) == {"market_throng"}
        assert set(carriers._crowd_index(cid, future["id"])) == {"funeral_crowd"}

    def test_no_frame_still_reads_the_present(self, temp_db):
        from core.db import wset
        from story import carriers

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Crowds", "", time.time()))
        wset(cid, crowds.CROWDS_WORLD_KEY,
             [{"uid": "market_throng", "room_uid": "square"}])

        assert set(carriers._crowd_index(cid, None)) == {"market_throng"}


# --- the player's envelope belongs to an era too (STORY-F27) ----------------
#
# Every other carrier home is per-era: a cast member's reports ride
# `chat_chars.state`/`chat_char_frames.state`, and `crowds`, `couriers` and
# `artifacts` are all in `db.FRAME_SCOPED_WORLD_KEYS`. The PLAYER's was the
# one that was not, so `persona_carrier_state` was a single row every era of
# a story read and wrote. What the player learned in one era survived a
# rewind or a branch, and could be told onward by `couriers.run_couriers` in
# an era that never produced it -- a channel where the design says there is
# none.

class TestThePlayersEnvelopeBelongsToAnEra:
    def _framed(self, db):
        from web import app

        cid, _chars, scene, ctx = _world(db, persona="Corin")
        scene["positions"] = {"Mora": "road", "Tavi": "road", "Corin": "square"}
        # Spelled as edges so a courier has a door to walk through.
        scene["rooms"]["square"]["adjacent"] = [{"to": "road", "barrier": "open"}]
        scene["rooms"]["road"]["adjacent"] = [{"to": "square", "barrier": "open"}]
        past = app.frames_create(
            cid, {"label": "Past", "ordinal": -10, "kind": "past"})["id"]
        future = app.frames_create(
            cid, {"label": "Future", "ordinal": 10, "kind": "future"})["id"]
        db.qi("UPDATE world_events SET frame_id=? WHERE chat_id=?", (past, cid))
        db.qi("UPDATE turns SET frame_id=? WHERE chat_id=?", (past, cid))
        ctx.turn.frame_id = past
        return cid, scene, ctx, past, future

    def test_the_key_is_declared_frame_scoped(self):
        from core.db import FRAME_SCOPED_WORLD_KEYS
        from story.carriers import PERSONA_STATE_KEY

        assert PERSONA_STATE_KEY in FRAME_SCOPED_WORLD_KEYS

    def test_what_one_era_witnessed_is_not_held_in_another(self, temp_db):
        from core.db import wget_for_frame
        from story.carriers import PERSONA_STATE_KEY, advance_carriers

        cid, scene, ctx, past, future = self._framed(temp_db)
        assert advance_carriers(
            ctx, scene, {"events": [{"event_id": "world_bell"}]})["acquired"] == 1

        held = (wget_for_frame(cid, PERSONA_STATE_KEY, past, {}) or {}).get(
            "carried_reports") or []
        assert [r["claim"] for r in held] == ["the warning bell rang twice"]
        assert wget_for_frame(cid, PERSONA_STATE_KEY, future, {}) == {}

    def test_the_frame_passed_in_is_the_frame_read(self, temp_db):
        """`persona_entry` read through a bare `wget`, so it answered with
        whatever era the ambient `active_frame_id` happened to name -- the
        same defect `_crowd_index` was repaired for one function above."""
        from story import carriers

        cid, scene, ctx, past, future = self._framed(temp_db)
        advance_carriers = carriers.advance_carriers
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})

        in_past = carriers.persona_entry(cid, ctx.chat, scene, frame_id=past)
        in_future = carriers.persona_entry(cid, ctx.chat, scene, frame_id=future)
        assert (in_past["state"].get("carried_reports") or [])
        assert in_future["state"] == {}

    def test_the_player_cannot_send_on_what_another_era_witnessed(self, temp_db):
        """The leak with a mouth attached. `run_couriers` checks the sender
        holds the report, and before this the check passed in an era that
        never saw the bell."""
        from story.carriers import advance_carriers
        from story.couriers import run_couriers

        cid, scene, ctx, past, future = self._framed(temp_db)
        advance_carriers(ctx, scene, {"events": [{"event_id": "world_bell"}]})

        ctx.turn.frame_id = future
        metrics, rejected = run_couriers(ctx, scene, [{
            "op": "send", "sender": "Corin", "to_room": "road",
            "world_event_id": "world_bell", "method": "word",
            "pace": "riding", "description": "a boy on a borrowed pony"}])
        assert metrics["dispatched"] == 0
        assert rejected and "world_bell" in json.dumps(rejected)


class TestThePersonaEnvelopeMigratesIntoItsEra:
    """v29 -> v30, the data half of the same repair.

    Every persona envelope already written is one bare row per chat holding
    whatever every era of that story put in it. The era is recoverable rather
    than guessed: a report records the turn it was `acquired_turn` on, and a
    turn records its frame.
    """

    def _at_v29(self, db):
        """A database holding rows written under the pre-frame-scoped key."""
        db.init()
        cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    ("Migrating", "", time.time()))
        frames = {}
        for label, ordinal, kind in (("Past", -10, "past"),
                                     ("Future", 10, "future")):
            frames[label] = db.qi(
                "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
                "VALUES(?,?,?,?,?)", (cid, label, ordinal, kind, time.time()))
        for idx, frame_id in ((0, None), (1, frames["Past"]),
                              (2, frames["Future"])):
            db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
                  "VALUES(?,?,?,?,?)", (cid, idx, "", time.time(), frame_id))
        db.qi("INSERT INTO world(chat_id,key,value) VALUES(?,?,?)",
              (cid, "persona_carrier_state", json.dumps({"carried_reports": [
                  {"world_event_id": "now", "claim": "the present",
                   "acquired_turn": 0},
                  {"world_event_id": "then", "claim": "the past",
                   "acquired_turn": 1},
                  {"world_event_id": "soon", "claim": "the future",
                   "acquired_turn": 2},
                  {"world_event_id": "gone", "claim": "a rewound turn",
                   "acquired_turn": 99},
              ]})))
        self._rewind_version(db)
        return cid, frames

    def _rewind_version(self, db):
        db.qi("INSERT INTO schema_meta(key,value) VALUES('version','29') "
              "ON CONFLICT(key) DO UPDATE SET value='29'")
        db.close_connection()

    def _claims(self, db, cid, frame_id):
        from story.carriers import PERSONA_STATE_KEY

        held = db.wget_for_frame(cid, PERSONA_STATE_KEY, frame_id, {}) or {}
        return [r["claim"] for r in held.get("carried_reports") or []]

    def test_each_report_lands_in_the_era_that_acquired_it(self):
        from core import db
        from tests.helpers import remove_scratch_db, scratch_db_path

        path = scratch_db_path()
        old_path = db.DB
        db.configure(path)
        try:
            cid, frames = self._at_v29(db)
            db.init()

            assert self._claims(db, cid, frames["Past"]) == ["the past"]
            assert self._claims(db, cid, frames["Future"]) == ["the future"]
            # NULL frame_id is the present, whose storage key is the bare one:
            # what the present witnessed stays, and so does a report whose turn
            # a rewind has since deleted.
            assert self._claims(db, cid, None) == ["the present",
                                                   "a rewound turn"]
        finally:
            db.close_connection()
            db.configure(old_path)
            remove_scratch_db(path)

    def test_a_malformed_envelope_survives_untouched(self):
        """A migration that raised on one story's junk would refuse to open
        every other story on the same install."""
        from core import db
        from tests.helpers import remove_scratch_db, scratch_db_path

        path = scratch_db_path()
        old_path = db.DB
        db.configure(path)
        try:
            cid, _frames = self._at_v29(db)
            db.qi("UPDATE world SET value='not json at all' "
                  "WHERE chat_id=? AND key='persona_carrier_state'", (cid,))
            self._rewind_version(db)
            db.init()

            row = db.q("SELECT value FROM world WHERE chat_id=? AND key=?",
                       (cid, "persona_carrier_state"), one=True)
            assert row["value"] == "not json at all"
        finally:
            db.close_connection()
            db.configure(old_path)
            remove_scratch_db(path)
