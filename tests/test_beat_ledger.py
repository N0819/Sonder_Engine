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
from world.beat_ledger import (MAX_BEAT_EVENTS, beat_event_order, beat_events,
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

    def test_the_cap_keeps_the_first_events(self):
        """The rows past the cap are the ones a runaway wrote."""
        scene = {}
        rows = [{"order": i, "actor": "A", "surface": "step %d" % i}
                for i in range(MAX_BEAT_EVENTS + 20)]
        record_beat_events(scene, 1, rows)
        kept = beat_events(scene, 1)
        assert len(kept) == MAX_BEAT_EVENTS
        assert kept[0]["surface"] == "step 0"

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
