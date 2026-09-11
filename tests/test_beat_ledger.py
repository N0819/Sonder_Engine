"""The beat's events, written into the world and read back by perception.

The owner's chain: "shouldn't it go character -> director -> recompiler ->
world -> perception?", and the rule for what the world keeps: "just because a
majority of these are temporary actions and dialogues, does not mean they
shouldn't be rendered in the world. The world just renders them in the order
declared and what isn't permanent is gone after perception rolls."

Three layers, tested in that order: what the recompiler hands over, what the
world keeps, and what perception does with it.
"""
from types import SimpleNamespace

from agents import director, perception
from world.beat_ledger import (beat_event_order, beat_events,
                               record_beat_events)


def _ctx(idx):
    return SimpleNamespace(turn=SimpleNamespace(idx=idx))


class TestWhatTheRecompilerHandsOver:
    """`beat_event_ledger` -- the author's ordered list, each row paired with
    the declaration it cites."""

    def test_the_surface_comes_from_the_citation_not_the_intent(self):
        """THREE descriptions of one act exist, and the row must take the
        middle one. The player declares `attempt` in his own words, which
        routinely carry purpose; `observable` is the intent-free outward form
        an onlooker is entitled to; the author's prose is a third description
        again. Measured on the join that motivated the citation."""
        res = {"sequence": [{
            "actor": "Corin", "attempt": "works at the windowsill",
            "category": "objects", "note": "runes",
            "from_declaration": "turn:1:player:0:action"}]}
        interp = {"sequence": [{
            "type": "action", "event_id": "turn:1:player:0:action",
            "attempt": "scratch runes of slow and soften",
            "observable": "crouches over the sill"}]}
        row, = director.beat_event_ledger(res, interp, [])
        assert row["surface"] == "crouches over the sill"
        assert row["declared"] == "turn:1:player:0:action"
        assert "runes of slow" not in row["surface"]

    def test_an_uncited_row_takes_the_authors_words_and_says_so(self):
        """`from_declaration` is empty exactly when NOBODY declared the act --
        a consequence, a thing the world did back -- so there is no actor's
        purpose to strip, and the empty `declared` is how a reader tells the
        engine's outward form from a description of it."""
        res = {"sequence": [{"actor": "", "attempt": "the sill cracks"}]}
        row, = director.beat_event_ledger(res, {}, [])
        assert row["surface"] == "the sill cracks"
        assert row["declared"] == ""

    def test_every_element_becomes_a_row_not_only_the_categorized_ones(self):
        """"The world just renders them in the order declared" -- a glance
        that settles nothing is still something that happened. Work items are
        the categorized SUBSET of the beat, never the whole of it."""
        res = {"sequence": [
            {"actor": "Mara", "attempt": "glances at the door"},
            {"actor": "Mara", "attempt": "bolts it",
             "category": "spatial", "note": "shut"}]}
        rows = director.beat_event_ledger(res, {}, [])
        assert [r["order"] for r in rows] == [0, 1]
        assert [r["category"] for r in rows] == ["", "spatial"]

    def test_a_characters_declaration_is_cited_the_same_way(self):
        """The character half needs no new machinery: a character DECLARES and
        the Director categorizes and cites, so the same join covers it."""
        res = {"sequence": [{
            "actor": "Mara", "attempt": "crosses the room",
            "from_declaration": "turn:9:character:4:0:action"}]}
        decls = [{"name": "Mara", "sequence": [{
            "type": "action", "event_id": "turn:9:character:4:0:action",
            "attempt": "get to the lever before he does",
            "observable": "crosses to the console"}]}]
        row, = director.beat_event_ledger(res, {}, decls)
        assert row["surface"] == "crosses to the console"
        assert row["actor"] == "Mara"

    def test_a_communication_reaches_the_world_with_a_surface(self):
        """A TYPED COMMUNICATIVE ACT HAS NO `observable`. Its outward form is
        the rendered verb over the proposition the author supplied, and asking
        only `observable_action_text` put the player's spoken beat into the
        world with nothing said about it.

        The real element, from the long-beat run's beat 2 order 14: the player
        wrote "ask Sera whether she has seen the reeve today ... tell her I
        will have the hinge done before dark", and the world recorded an event
        with an empty surface. An event in the world's record of the beat with
        no description of what happened is the ledger failing at the one thing
        it is for."""
        res = {"sequence": [{
            "actor": "Corin",
            "attempt": "asks Sera if reeve came by and promises hinge done",
            "from_declaration": "turn:2:player:14:communication"}]}
        interp = {"sequence": [{
            "type": "communication", "act": "ask",
            "event_id": "turn:2:player:14:communication",
            "content": "whether the reeve came by today"}]}
        row, = director.beat_event_ledger(res, interp, [])
        assert row["surface"], "a communication reached the world with no surface"
        assert "reeve came by today" in row["surface"]
        assert row["kind"] == "communication"

    def test_a_communication_is_never_quoted_into_a_surface(self):
        """`content` is what the act was ABOUT, not words the engine may put
        in a mouth -- so the surface is indirect speech, never a quotation."""
        res = {"sequence": [{
            "actor": "Corin", "attempt": "asks about the reeve",
            "from_declaration": "d1"}]}
        interp = {"sequence": [{
            "type": "communication", "act": "ask", "event_id": "d1",
            "content": "whether the reeve came by"}]}
        row, = director.beat_event_ledger(res, interp, [])
        assert '"' not in row["surface"]
        assert row["text"] == ""


class TestWhatTheWorldKeeps:
    """`world/beat_ledger.py` -- the beat number IS the lifetime."""

    def test_the_record_answers_only_its_own_beat(self):
        scene = {}
        record_beat_events(scene, 7, [{"order": 0, "actor": "Mara",
                                       "surface": "crosses"}])
        assert len(beat_events(scene, 7)) == 1
        assert beat_events(scene, 8) == []
        assert beat_events(scene, None) == []

    def test_nothing_has_to_sweep_it(self):
        """A sweep is a second thing that must run on every path forever, and
        the path it misses is the one that renders a stale event as though it
        had just happened. A reader that proves the beat cannot be wrong that
        way -- so a scene carried into the next beat by a crash, a resume, a
        reroll or a branch answers empty with nobody having touched it."""
        scene = {}
        record_beat_events(scene, 7, [{"order": 0, "actor": "Mara",
                                       "surface": "crosses"}])
        carried_forward = dict(scene)
        assert beat_events(carried_forward, 8) == []
        assert beat_event_order(carried_forward, 8) == {}

    def test_an_empty_beat_still_writes_a_record(self):
        """"This beat had no events" and "no beat has spoken" are different
        answers; keeping the older beat's list would let the second be read as
        the first."""
        scene = {}
        record_beat_events(scene, 7, [{"order": 0, "actor": "Mara",
                                       "surface": "crosses"}])
        record_beat_events(scene, 8, [])
        assert beat_events(scene, 8) == []
        assert beat_events(scene, 7) == []

    def test_a_beat_the_caller_cannot_name_writes_nothing(self):
        scene = {"beat_events": {"beat": 7, "events": []}}
        assert record_beat_events(scene, None, [{"order": 0, "actor": "A",
                                                 "surface": "x"}]) == []
        assert scene["beat_events"]["beat"] == 7

    def test_only_the_projected_fields_reach_the_scene(self):
        """A strict projection, not a passthrough: the author's element holds
        `attempt`, the actor's own intent-bearing words, and copying the
        element wholesale would put those into the world for every observer."""
        scene = {}
        record_beat_events(scene, 1, [{
            "order": 0, "actor": "Corin", "surface": "crouches over the sill",
            "attempt": "scratch runes of slow and soften"}])
        row, = beat_events(scene, 1)
        assert "attempt" not in row
        assert row["surface"] == "crouches over the sill"

    def test_an_absurd_beat_is_kept_whole(self):
        """"Hypothetically the director should be able to hand and render
        quite an absurd amount of events per beat" -- which follows from the
        thesis the recompiler exists for: "a system that can decipher any
        arbitrarily long series of events ... and resolve it properly with
        proper respect to chronology and space". Arbitrarily long and
        at-most-N cannot both be true.

        A cap of 64 stood here for one commit. The premise was false: the
        author's whole sequence is already persisted at full length in the
        `director_resolve` variant row and this record MIRRORS it, so capping
        the mirror prevented no blob and only let the world's record disagree
        with the Director's about what happened -- by dropping the TAIL of a
        long beat, the half a reader is least likely to miss."""
        scene = {}
        rows = [{"order": i, "actor": "A", "surface": "step %d" % i}
                for i in range(500)]
        record_beat_events(scene, 1, rows)
        kept = beat_events(scene, 1)
        assert len(kept) == 500
        assert kept[0]["surface"] == "step 0"
        assert kept[-1]["surface"] == "step 499"
        assert [r["order"] for r in kept] == list(range(500))

    def test_an_absurd_beat_still_orders_whole(self):
        """The chronology has to survive the size too -- a long beat is
        exactly the one whose order a reader cannot reconstruct by eye."""
        scene = {}
        record_beat_events(scene, 1, [
            {"order": i, "actor": "A", "surface": "step %d" % i,
             "declared": "d:%d" % i} for i in range(500)])
        order = beat_event_order(scene, 1)
        assert len(order) == 500
        assert order["d:499"] == 499

    def test_the_order_map_is_keyed_on_the_declaration(self):
        """The join perception makes: its stream is keyed on declarations, and
        the ledger's rows cite the declaration each describes."""
        scene = {}
        record_beat_events(scene, 3, [
            {"order": 0, "actor": "Corin", "surface": "a",
             "declared": "turn:3:player:0:action"},
            {"order": 1, "actor": "Mara", "surface": "b"},
            {"order": 2, "actor": "Mara", "surface": "c",
             "declared": "turn:3:character:4:0:speech"}])
        assert beat_event_order(scene, 3) == {
            "turn:3:player:0:action": 0,
            "turn:3:character:4:0:speech": 2}


class TestWhatPerceptionDoesWithIt:
    """`_world_ordered_stream` -- the concatenation was a GUESS at chronology
    and the world can now say."""

    def test_the_world_reorders_the_beat_the_declarations_guessed(self):
        """The stream is assembled player-first, then each character's. Live,
        that renders a player who speaks, walks out and is answered as though
        the answer came before he left."""
        scene = {}
        record_beat_events(scene, 2, [
            {"order": 0, "actor": "Corin", "surface": "speaks",
             "declared": "p:speech"},
            {"order": 1, "actor": "Mara", "surface": "answers",
             "declared": "c:speech"},
            {"order": 2, "actor": "Corin", "surface": "walks out",
             "declared": "p:move"}])
        stream = [
            {"kind": "speech", "declared": "p:speech"},
            {"kind": "action", "declared": "p:move"},
            {"kind": "speech", "declared": "c:speech"}]
        out = perception._world_ordered_stream(scene, _ctx(2), stream)
        assert [e["declared"] for e in out] == [
            "p:speech", "c:speech", "p:move"]

    def test_an_unnamed_entry_stays_attached_to_what_it_followed(self):
        """An unbound dialogue row, a background presence's beat and a minted
        silence are appended after the declared stream and the world cites
        none of them. Each takes the position of the last NAMED entry before
        it, so it stays where it was put."""
        scene = {}
        record_beat_events(scene, 2, [
            {"order": 0, "actor": "Corin", "surface": "speaks",
             "declared": "p:speech"},
            {"order": 1, "actor": "Mara", "surface": "answers",
             "declared": "c:speech"}])
        stream = [
            {"kind": "speech", "declared": "c:speech"},
            {"kind": "speech", "declared": "p:speech"},
            {"kind": "action", "id": "background"},
            {"kind": "silence", "id": "unanswered"}]
        out = perception._world_ordered_stream(scene, _ctx(2), stream)
        assert [e.get("declared") or e.get("id") for e in out] == [
            "p:speech", "c:speech", "background", "unanswered"]

    def test_a_ledger_that_names_nothing_changes_nothing(self):
        scene = {}
        record_beat_events(scene, 2, [
            {"order": 0, "actor": "Mara", "surface": "crosses"}])
        stream = [{"kind": "action", "id": "a"}, {"kind": "action", "id": "b"}]
        assert perception._world_ordered_stream(
            scene, _ctx(2), stream) == stream

    def test_one_named_entry_cannot_disagree_about_an_order(self):
        """Two named entries are the minimum that can; reordering on one would
        only be the fallback rule moving everything around a single anchor."""
        scene = {}
        record_beat_events(scene, 2, [
            {"order": 5, "actor": "Mara", "surface": "crosses",
             "declared": "c:move"}])
        stream = [{"kind": "action", "id": "a"},
                  {"kind": "action", "declared": "c:move"},
                  {"kind": "action", "id": "b"}]
        assert perception._world_ordered_stream(
            scene, _ctx(2), stream) == stream

    def test_another_beats_record_orders_nothing(self):
        """The lifetime rule reaching the reader that matters."""
        scene = {}
        record_beat_events(scene, 1, [
            {"order": 0, "actor": "Corin", "surface": "a",
             "declared": "p:speech"},
            {"order": 1, "actor": "Mara", "surface": "b",
             "declared": "c:speech"}])
        stream = [{"kind": "speech", "declared": "c:speech"},
                  {"kind": "speech", "declared": "p:speech"}]
        assert perception._world_ordered_stream(
            scene, _ctx(2), stream) == stream


class TestAStraySeparatorIsNotPartOfAName:
    """Found by fuzzing, and it is the same complaint one branch earlier:

        'body'   ->  body
        'body,'  ->  NOTHING

    A trailing comma defeated the routing outright. The split yields ONE part
    ("body"), the "fewer than two parts" branch handed back the RAW string,
    and `body,` is not a category anybody answers to -- so a hand name the
    engine owns was lost to a keystroke. A leading or trailing separator is an
    entirely ordinary thing for a model to emit.
    """

    def test_a_trailing_or_leading_separator_does_not_cost_the_name(self):
        for raw in ("body,", ",body", "body;", "body|", " body , ",
                    "body,,", ",,body"):
            assert director._category_names(raw) == ["body"], raw

    def test_it_survives_all_the_way_to_a_hand(self):
        out = director._span_items({"sequence": [
            {"actor": "C", "attempt": "x", "note": "n", "category": "body,"}]})
        assert director.span_owners(out[0]) == ["body"]

    def test_separators_alone_recover_nothing_and_say_so(self):
        """There is no name in ",", "and" or "  ,  ,  " to recover, so the raw
        value stands and the unrouted report shows what was written rather
        than an empty string."""
        for raw in (",", "and", "  ,  ,  ", ";;"):
            assert director._category_names(raw) == [raw], raw

    def test_a_value_with_no_separator_is_unchanged(self):
        """The branch may only strip punctuation -- a string that splits to
        itself must come back as itself, prose included."""
        for raw in ("objects", "wardrobe", "the belt comes off"):
            assert director._category_names(raw) == [raw], raw


class TestTheCausalFloorOutranksTheWorldsOrder:
    """`_outcome_event_stream` defers a dependent player phase so the beat
    reads onset -> response -> continuation: "a dependent player phase occurs
    only after present minds had the chance to answer its prerequisite". That
    is a causal invariant the engine enforces deterministically, off the
    player's own `depends_on`/`phase`.

    The ledger is a MODEL's account of the chronology, and it could pull the
    continuation back in front of the answer it waits for. Measured: the
    long-beat run's turn 1 listed all eleven of the player's acts before any
    character's, which is exactly that shape. Where a failure would be the
    engine's fault, the deterministic floor stays.
    """

    def _scene(self):
        from world.beat_ledger import record_beat_events
        scene = {}
        record_beat_events(scene, 1, [
            {"order": 0, "actor": "Corin", "surface": "onset",
             "declared": "p:onset"},
            {"order": 1, "actor": "Corin", "surface": "cont",
             "declared": "p:cont"},
            {"order": 2, "actor": "Mara", "surface": "answers",
             "declared": "c:answer"}])
        return scene

    def _ctx(self):
        from types import SimpleNamespace
        return SimpleNamespace(turn=SimpleNamespace(idx=1))

    def test_a_continuation_never_precedes_the_answer_it_waits_for(self):
        stream = [
            {"kind": "action", "declared": "p:onset"},
            {"kind": "speech", "declared": "c:answer"},
            {"kind": "action", "declared": "p:cont", "deferred": True}]
        out = perception._world_ordered_stream(
            self._scene(), self._ctx(), stream)
        where = [e["declared"] for e in out]
        assert where.index("p:cont") > where.index("c:answer")

    def test_the_world_still_orders_everything_the_floor_has_no_view_on(self):
        """The floor is not a veto on the whole beat -- only on what it
        actually decided. Two ordinary entries the ledger disagrees with are
        still put right."""
        stream = [
            {"kind": "speech", "declared": "c:answer"},
            {"kind": "action", "declared": "p:onset"},
            {"kind": "action", "declared": "p:cont", "deferred": True}]
        out = perception._world_ordered_stream(
            self._scene(), self._ctx(), stream)
        assert [e["declared"] for e in out] == [
            "p:onset", "c:answer", "p:cont"]

    def test_the_builder_marks_what_it_deferred(self):
        """A floor that only holds in a hand-built test is no floor: the flag
        has to be stamped by the builder on every branch that can defer."""
        import inspect
        src = inspect.getsource(perception._outcome_event_stream)
        assert src.count('"deferred": _deferred') == 3
        assert "destination = deferred_stream if _deferred else stream" in src


class TestTheAnswerLandsWhereItWasAnswered:
    """The shape the whole feature exists for, taken from the long-beat run's
    beat 2: Corin works, ASKS a question, Sera and Wren answer, and then Corin
    RESUMES with the file.

    The concatenation could never render that. It appends every one of the
    player's acts, then each character's in the order the loops ran -- so his
    last two acts were shown before the answers to the line that preceded
    them, and the page read as though nobody had replied until he had finished
    doing everything else.
    """

    def _scene(self):
        from world.beat_ledger import record_beat_events
        scene = {}
        record_beat_events(scene, 2, [
            {"order": 13, "actor": "Corin", "surface": "sets the hinge down",
             "declared": "p:13"},
            {"order": 14, "actor": "Corin", "surface": "asks about the reeve",
             "declared": "p:14"},
            {"order": 16, "actor": "Sera", "surface": "No reeve came by.",
             "declared": "c:sera"},
            {"order": 18, "actor": "Wren", "surface": "The reeve stays...",
             "declared": "c:wren"},
            {"order": 19, "actor": "Corin", "surface": "picks up a file",
             "declared": "p:19"},
            {"order": 20, "actor": "Corin", "surface": "draws it twice",
             "declared": "p:20"}])
        return scene

    def _ctx(self):
        from types import SimpleNamespace
        return SimpleNamespace(turn=SimpleNamespace(idx=2))

    #: What the concatenation builds: all of his, then all of theirs.
    CONCATENATED = [{"declared": d} for d in
                    ("p:13", "p:14", "p:19", "p:20", "c:sera", "c:wren")]

    def test_his_resume_follows_the_answers_to_his_question(self):
        out = perception._world_ordered_stream(
            self._scene(), self._ctx(), list(self.CONCATENATED))
        assert [e["declared"] for e in out] == [
            "p:13", "p:14", "c:sera", "c:wren", "p:19", "p:20"]

    def test_the_concatenation_really_did_get_it_wrong(self):
        """Pinned so the test above cannot quietly become a tautology if the
        stream builder's own ordering changes."""
        order = [e["declared"] for e in self.CONCATENATED]
        assert order.index("p:19") < order.index("c:sera")

    def test_reordering_is_idempotent(self):
        once = perception._world_ordered_stream(
            self._scene(), self._ctx(), list(self.CONCATENATED))
        twice = perception._world_ordered_stream(
            self._scene(), self._ctx(), once)
        assert once == twice

    def test_nothing_is_gained_or_lost(self):
        out = perception._world_ordered_stream(
            self._scene(), self._ctx(), list(self.CONCATENATED))
        assert len(out) == len(self.CONCATENATED)
        assert sorted(e["declared"] for e in out) == sorted(
            e["declared"] for e in self.CONCATENATED)


class TestABareCommaEndsADeclarationUnit:
    """A long beat COMPRESSES, and until the comma was a boundary the omission
    detector could not see it.

    Measured on paragraphs of hand-counted acts, all confined to one room:
    12 acts dissected to 11 elements and 20 to 18, near 1:1 -- but 31
    collapsed to 11 compound elements and lost all three declared speech acts
    (`{'action': 11}`, where the 20-act beat gave
    `{'action': 16, 'communication': 2}`). `_uncovered_declarations` reported
    ZERO for it.

    The reason was structural rather than a threshold. `_CLAUSE_SPLIT_RE` broke
    on sentence boundaries and on coordination -- ". ; ! ?", ", and", ", then",
    " and " -- but NOT on a bare comma, so a comma-chained paragraph was 2
    units for 31 acts. The detector then asked whether each coarse unit's
    significant tokens were present, and compression that KEEPS THE NOUNS
    while dropping the acts passed it cleanly.

    THE RISK WAS REAL AND WAS MEASURED BEFORE SHIPPING, because more units
    means more chances to fire the bounded self-repair on an interpretation
    that was already complete -- the "guards that fire on valid output" class.
    Across 171 stored interpret beats: declaration units rise 261 -> 311
    (+19%), beats that fire the repair rise from 0 to 2 (1.2%), and all FOUR
    newly-reported units are real drops, not false positives:

      * "tell her she can't hear me now" -- an input declaring two speech acts
        whose interpretation carried one;
      * the three speech acts of the 31-act beat, whose sequence held none.
    """

    def _units(self, raw):
        return director._declaration_units(raw)

    def test_a_comma_chained_paragraph_is_no_longer_two_units(self):
        """The measured beat, shortened. Its 2 units could never localise a
        dropped act; one unit per clause can."""
        raw = ("I put the file down, pick up the broom leaning against the "
               "wall, sweep the scale away from the anvil, set the broom "
               "back where it was, take the bellows handle, tell Sera the "
               "glove has finally gone, pick the file back up")
        assert len(self._units(raw)) >= 6

    def test_the_speech_act_that_was_lost_is_now_its_own_unit(self):
        """The detector can only report what the splitter separated, so the
        act has to survive as a unit of its own before anything else matters.
        This is the exact clause from the long-beat run."""
        raw = ("I take the hinge off the bench, tell Sera the glove has "
               "finally gone, ask her to fetch the spare pair from the chest")
        units = self._units(raw)
        assert any("glove has finally gone" in u for u in units)
        assert any("spare pair" in u for u in units)

    def test_the_tardis_line_separates_from_the_acts_around_it(self):
        """items.db turn 1, and the owner's own example: an input declaring
        two speech acts whose interpretation carried one. The line that goes
        unheard is the dramatically load-bearing one."""
        raw = ("I tell Sera to wait here, then I step into the tardis, pull "
               "the door shut behind me, tell her she can't hear me now, and "
               "pull the levers on the console")
        units = self._units(raw)
        assert any("hear me now" in u for u in units)
        assert any("wait here" in u for u in units)

    def test_a_short_ordinary_beat_is_unchanged(self):
        """171 stored beats were measured and 169 of them fire nothing. A
        change to the detector that moved ordinary play would not be worth
        the drop it catches."""
        for raw in ("I wait", "I ask Sera whether she has seen the reeve",
                    "I walk out of the forge and shut the door behind me"):
            assert len(self._units(raw)) <= 3, raw

    def test_a_unit_still_needs_two_significant_tokens(self):
        """The conservative floor is untouched: comma-splitting produces short
        fragments, and a fragment with too little signal to judge must not be
        reported as a dropped declaration."""
        assert self._units("I nod, yes, ok") == []
