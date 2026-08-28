"""A crowd is one object with many people in it.

A market square with forty people cannot be represented today: `max_managed`
defaults to 6 and is hard-capped at 8, so a populous place either eats the
whole manager budget or is silently absent. Chat 57 spent three of those six
slots on ONE Dalek, split three ways by its article. `scene.py` has said the
answer in prose since before this module existed — "past that, a crowd is
better represented as one chorus presence than as several individually-voiced
extras" — and never had an object.

These pin the three decisions everything else rests on: the count is a band,
the density is derived, and the id is not a name.
"""

from __future__ import annotations

import pytest

from world import crowds


class TestTheCountIsABand:
    def test_an_unknown_band_reads_as_fewer_people_not_more(self):
        """Over-claiming a throng puts bodies in a room nothing authored. The
        engine should under-populate when it cannot tell."""
        assert crowds.normalize_band("forty-ish") == crowds.BANDS[0]
        assert crowds.normalize_band(None) == crowds.BANDS[0]

    def test_a_band_the_model_words_differently_is_still_that_band(self):
        """`band` is a free string with its vocabulary in a schema comment,
        so exact equality against four fixed phrases is a coin flip per
        wording. Measured by execution before the fix: "dozens", "a crowd",
        "a throng of dockworkers" -- all of them -- folded to "a handful"."""
        assert crowds.normalize_band("a throng of dockworkers") == "a throng"
        assert crowds.normalize_band("dozens of market-goers") == "a few dozen"
        assert crowds.normalize_band("a few dozen fishmongers") == "a few dozen"
        assert crowds.normalize_band("two dozen pilgrims") == "a dozen or so"
        assert crowds.normalize_band("a mob") == "a throng"
        assert crowds.normalize_band("a handful of guards") == "a handful"

    def test_re_describing_a_crowd_cannot_shrink_it(self):
        """The under-populate rule is right on a MINT, where there is nothing
        to lose. On an EDIT there is a standing band, and replacing a throng
        with a handful because the wording changed is a bigger invention than
        keeping what was there. A word this vocabulary cannot read is not
        evidence that people left."""
        assert crowds.normalize_band("milling about", "a throng") == "a throng"
        assert crowds.normalize_band("", "a throng") == "a throng"

    def test_splitting_is_band_preserving_not_count_preserving(self):
        """"A few dozen" toward two exits gives "a dozen or so" twice. No
        arithmetic, so no conservation bookkeeping and no drift — the moment
        two sources disagree about whether 37 became 34 there is a
        contradiction with no resolution."""
        assert crowds.split_band("a few dozen") == "a dozen or so"
        assert crowds.split_band("a throng") == "a few dozen"

    def test_the_smallest_band_does_not_divide(self):
        """A handful that splits is two things the story has no word for."""
        assert crowds.split_band("a handful") is None


class TestDensityIsDerivedFromTheRoom:
    def test_the_room_releases_you_not_the_crowd(self):
        """The property worth having. The same crowd is a crush in a gate
        passage and loose in the square beyond — the escape that was
        impossible becomes available because the geometry changed and nothing
        else did."""
        assert crowds.density("a few dozen", "small") == crowds.CRUSH
        assert crowds.density("a few dozen", "large") == crowds.LOOSE

    def test_equal_ranks_are_packed(self):
        assert crowds.density("a few dozen", "medium") == crowds.PACKED

    def test_an_unsized_room_is_medium_not_missing(self):
        """66 of the live corpus's rooms leave `size` unset, and an unsized
        room is the commonest room. A crowd that vanished in one would be a
        worse answer than a crowd of ordinary density."""
        assert crowds.density("a few dozen", None) == \
            crowds.density("a few dozen", "medium")

    def test_density_is_never_stored_on_the_object(self):
        """A stored density is a second source of truth that drifts the moment
        the crowd moves — the `wearing`/`state`/`regions` scar, which this
        module is written after rather than before."""
        crowd = crowds.new_crowd(1, "square", band="a throng",
                                 composition="dockworkers", since_turn=3)
        assert "density" not in crowd

    def test_the_travel_cost_table_is_not_a_size_rank(self):
        """`spatial._ROOM_COST` looks like this rank and is not: it collapses
        tiny, small, "" and medium all to 1 because it prices WALKING. Reusing
        it would make a crush in a broom cupboard read like one in a hall."""
        from world.spatial import _ROOM_COST
        assert _ROOM_COST["tiny"] == _ROOM_COST["medium"]
        assert crowds.room_size_rank("tiny") != crowds.room_size_rank("medium")


class TestIdentity:
    def test_the_id_is_not_a_display_name(self):
        """Five ledgers already key beings by display name and it is one
        defect, not five. A new writer into the wrong key space is exactly
        what subject identity exists to stop."""
        crowd = crowds.new_crowd(1, "square", band="a throng",
                                 composition="dockworkers", since_turn=3)
        assert crowd["uid"].startswith("crowd:")
        assert "dockworkers" not in crowd["uid"]

    def test_the_same_crowd_mints_the_same_id(self):
        args = dict(band="a throng", composition="dockworkers", since_turn=3)
        assert crowds.new_crowd(1, "square", **args)["uid"] == \
            crowds.new_crowd(1, "square", **args)["uid"]

    def test_a_different_room_is_a_different_crowd(self):
        args = dict(band="a throng", composition="dockworkers", since_turn=3)
        assert crowds.new_crowd(1, "square", **args)["uid"] != \
            crowds.new_crowd(1, "gate", **args)["uid"]


def test_overhearing_nothing_is_not_overhearing_everything():
    """`crowd_hearsay(crowd)[-max(0, int(cap)):]` -- in Python `-0 == 0`, so
    the slice is `[0:]` and asking for nothing returned the whole ledger.
    `cap=0` is the natural spelling of "this observer overhears nothing"."""
    crowd = {"uid": "c1", "composition": "dockworkers"}
    for i in range(3):
        crowd = crowds.add_hearsay(crowd, {"claim": "rumour %d" % i,
                                           "world_event_id": "we%d" % i})
    assert crowds.talk_view(crowd, 0) == []
    assert crowds.talk_view(crowd, -1) == []
    assert len(crowds.talk_view(crowd, 2)) == 2


def test_a_crowd_murmurs_and_does_not_speak():
    """Anyone who speaks has emerged and is no longer part of the crowd, so
    the description is a phrase an observer registers — never a line."""
    crowd = crowds.new_crowd(1, "gate", band="a few dozen",
                             composition="dockworkers and ferry passengers",
                             since_turn=3, mood="restless")
    text = crowds.describe(crowd, "small")
    assert "a few dozen dockworkers" in text
    assert "shoulder to shoulder" in text  # small room -> crush
    assert "restless" in text
    assert '"' not in text


def test_crowds_in_room_is_stable_and_scoped():
    a = crowds.new_crowd(1, "square", band="a throng", composition="x", since_turn=1)
    b = crowds.new_crowd(1, "gate", band="a handful", composition="y", since_turn=1)
    assert [c["uid"] for c in crowds.crowds_in_room([a, b], "square")] == [a["uid"]]
    assert crowds.crowds_in_room([a, b], "") == []


# --- the perception surface --------------------------------------------------

class TestACrowdIsVisibleWithoutCostingASlot:
    """The whole reason the object exists. `max_managed` defaults to 6 and is
    hard-capped at 8; a crowd that consumed one of those slots would have
    solved nothing.
    """

    def _story(self, temp_db):
        import time
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Crowd", "", time.time()))
        scene = {
            "location": "Priestella",
            "rooms": {"gate": {"name": "Watergate", "size": "small"},
                      "square": {"name": "Square", "size": "large"},
                      "office": {"name": "Back Office", "size": "small"}},
            "positions": {},
        }
        crowd = crowds.new_crowd(cid, "gate", band="a few dozen",
                                 composition="dockworkers", since_turn=1,
                                 mood="restless")
        temp_db.wset(cid, "crowds", [crowd])
        return cid, scene

    def test_an_observer_in_the_room_registers_it(self, temp_db):
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        seen = crowds_for_room(cid, scene, "gate")
        assert len(seen) == 1
        assert "dockworkers" in seen[0]["what"]

    def test_someone_in_a_back_office_learns_nothing_of_the_square(self, temp_db):
        """Per observer and room-scoped. A scene-wide list would hand someone
        behind a closed door the state of the crowd outside."""
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        assert crowds_for_room(cid, scene, "office") == []

    def test_density_follows_the_room_the_crowd_is_in_now(self, temp_db):
        """Recomputed at read, never read back from the object — the crowd may
        have walked into a different room since it was minted."""
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        assert crowds_for_room(cid, scene, "gate")[0]["density"] == crowds.CRUSH
        stored = temp_db.wget(cid, "crowds", [])
        stored[0]["room_uid"] = "square"
        temp_db.wset(cid, "crowds", stored)
        assert crowds_for_room(cid, scene, "square")[0]["density"] == crowds.LOOSE

    def test_the_ledger_is_frame_scoped(self):
        """A branch that never went to the market must not inherit its throng."""
        from core.db import FRAME_SCOPED_WORLD_KEYS
        assert "crowds" in FRAME_SCOPED_WORLD_KEYS

    def test_a_crowd_is_not_a_managed_presence(self, temp_db):
        """It must not appear in the presence ledger the manager budget counts."""
        cid, _scene = self._story(temp_db)
        assert not (temp_db.wget(cid, "background_presences", {}) or {})


# --- fixtures: the rule that separates them from emergences ------------------

class TestAFixtureMayBeReMet:
    """docs/design/DESIGN_CROWDS.md §3a's fixture, after Part C.

    The at-post signal that used to re-offer a barkeep on every quiet visit
    ("a fixture may be re-met") was co-presence as a qualifier, and
    DESIGN_BACKGROUND_PRESENTATION §C1 removed exactly that class: the
    demand gate voices only whom an authored mind's conduct calls on --
    addressed, owed, acting, emerged. The fixture is still re-met, through
    the tiers built for it: a charter body with a post here stands in the
    derived crowd (§B3's amendment -- a fixture IS a charter body with a
    post), the room hums through the chatter seam, and the moment the
    player turns to the barkeep, the address forces the pick from any room
    within the heard-in-FULL bar `_character_address_of` still holds.
    """

    def test_co_presence_is_no_longer_a_qualifying_signal(self):
        """§C1's subtraction, pinned at the source so a re-added at-post (or
        any renamed spelling of "standing where you work qualifies") fails
        loudly rather than quietly re-widening the budget."""
        import inspect

        from persist import commit
        body = inspect.getsource(commit.pick_voice_demand)
        assert "at_post" not in body
        assert "_at_post_within_earshot" not in body
        assert not hasattr(commit, "_at_post_within_earshot")

    def test_the_demand_gate_qualifies_on_exactly_four_triggers(self):
        """addressed / owed / acting / emerged, nothing else -- mentioned
        (prose salience) and dialogue_turns (tenure) are gone with at-post."""
        import inspect

        from persist import commit
        body = inspect.getsource(commit.pick_voice_demand)
        gate = body[body.index("if not (addressed_any"):].split("continue")[0]
        assert "or owed or acting or emerged)" in gate
        assert "mentioned" not in gate
        assert "dialogue_turns" not in gate
        assert "at_post" not in body

    def test_an_addressee_sorts_first_in_the_overflow_order(self):
        """§C3: addressed > owed > acting > emerged. A crowd member with a
        grievance (entanglement tie-break) must not outrank someone the
        player just spoke to."""
        import inspect

        from persist import commit
        body = inspect.getsource(commit.pick_voice_demand)
        priority = body[body.index("priority = ["):body.index("candidates.append")]
        # The address term is graded (2 precise / 1 loose / 0), not a bool:
        # fuzzy shared-word matches must rank below the person actually named.
        order = ["addressed_precise", "bool(owed)", "bool(acting)",
                 "bool(emerged)"]
        positions = [priority.index(term) for term in order]
        assert positions == sorted(positions)


class TestDensityIsTerrain:
    """§5a. A crowd you can be caught in is not set dressing, it is terrain.

    Both halves of the split are pinned here: the spatial layer answers
    "may I" deterministically, and the Director answers "what happened".
    """

    def test_a_loose_crowd_is_ground_with_people_on_it(self):
        """Forty across a market square is walkable. Treating every crowd as
        an obstacle would make a busy street impassable, which is not what a
        busy street is."""
        assert crowds.terrain("a dozen or so", "large") == "open"

    def test_a_crush_is_the_barrier_word_spatial_already_has(self):
        """No new passability class. `membrane` is already passable and
        already absent from `_SIGHT_BARRIERS` — push through, cannot see
        across — and its own comment glosses it as "a body's soft wall"."""
        from world import spatial

        assert crowds.terrain("a few dozen", "small") == "membrane"
        assert crowds.terrain("a throng", "large") == "membrane"
        assert "membrane" in spatial._VALID_BARRIERS
        assert "membrane" not in spatial._SIGHT_BARRIERS

    def test_the_room_releases_you_rather_than_the_crowd_deciding_to(self):
        """The property worth having: a crush that reaches open ground thins
        because the geometry changed and nothing else did."""
        gateway = crowds.terrain("a few dozen", "small")
        square = crowds.terrain("a few dozen", "huge")
        assert gateway == "membrane" and square == "open"


class TestDriftIsAnOfferAndNotAnArrival:
    def test_a_crowd_going_nowhere_has_no_current(self):
        """A stationary crush is a wall with good prose. Pushing bodies
        around a room for no reason anyone could point at is worse than
        nothing."""
        still = crowds.new_crowd(1, "gate", band="a throng",
                                 composition="pilgrims", since_turn=1)
        assert crowds.drift(still, "small") is None

    def test_a_crush_carries_and_a_packed_crowd_only_pulls(self):
        """The difference between packed and a crush is the current, not the
        wall — both are a membrane."""
        moving = crowds.new_crowd(1, "gate", band="a few dozen",
                                  composition="pilgrims", since_turn=1,
                                  heading="yard")
        assert crowds.drift(moving, "small")["strength"] == crowds.CARRY
        assert crowds.drift(moving, "medium")["strength"] == crowds.PULL

    def test_a_loose_crowd_does_not_move_anyone(self):
        """You can walk against a thin stream of people."""
        moving = crowds.new_crowd(1, "square", band="a handful",
                                  composition="idlers", since_turn=1,
                                  heading="gate")
        assert crowds.drift(moving, "large") is None

    def test_drift_names_where_and_never_puts_anyone_there(self):
        """`_guard_approach_is_not_arrival` exists because conflating approach
        with placement wrote positions nobody declared. A crowd carrying
        someone is exactly an undeclared arrival, so this returns an offer the
        Director resolves — it never edits a position."""
        import inspect

        moving = crowds.new_crowd(1, "gate", band="a throng",
                                  composition="pilgrims", since_turn=1,
                                  heading="yard")
        before = dict(moving)
        assert crowds.drift(moving, "small")["toward"] == "yard"
        assert moving == before, "drift moved a crowd it was only asked about"
        assert "room_uid" not in inspect.getsource(crowds.drift)


class TestOnlyTheEngineMintsAnId:
    def test_an_unknown_crowd_id_is_refused_rather_than_created(self):
        """Five ledgers already key beings by display name and it is one
        defect, not five. A crowd is a new writer, and minting under a
        model-authored key is that defect acquiring a sixth."""
        standing, rejected = crowds.apply_ops(
            [], [{"op": "set", "crowd_id": "the market crowd", "room": "square",
                  "composition": "traders"}],
            chat_id=1, turn=3, known_rooms=["square"])
        assert standing == []
        assert any("refusing to mint" in r for r in rejected)

    def test_an_empty_crowd_id_is_how_a_new_crowd_is_asked_for(self):
        standing, rejected = crowds.apply_ops(
            [], [{"op": "set", "room": "square", "band": "a throng",
                  "composition": "traders and hawkers"}],
            chat_id=1, turn=3, known_rooms=["square"])
        assert len(standing) == 1 and rejected == []
        assert standing[0]["uid"].startswith("crowd:")
        assert "traders" not in standing[0]["uid"]


class TestOpsRefuseWhatWouldBeInvisible:
    def test_a_crowd_in_an_unauthored_room_is_refused(self):
        """Perception is room-scoped, so a crowd in a room nobody authored
        would occupy a slot and be seen by no one — a silent no-op, which is
        worse than a rejection somebody can read."""
        standing, rejected = crowds.apply_ops(
            [], [{"op": "set", "room": "the docks", "composition": "sailors"}],
            chat_id=1, turn=1, known_rooms=["square"])
        assert standing == [] and rejected

    def test_a_crowd_with_no_composition_is_refused(self):
        """Composition is the whole atmospheric payload. A crowd of nobody in
        particular is a sentence of prose that cost a row."""
        standing, _ = crowds.apply_ops(
            [], [{"op": "set", "room": "square"}],
            chat_id=1, turn=1, known_rooms=["square"])
        assert standing == []

    def test_a_bad_heading_does_not_sink_the_crowd_riding_on_it(self):
        """Where the crowd IS was declared; where it is drifting is a
        flourish. Losing the flourish is cheaper than losing the crowd."""
        standing, rejected = crowds.apply_ops(
            [], [{"op": "set", "room": "square", "composition": "traders",
                  "heading": "the moon"}],
            chat_id=1, turn=1, known_rooms=["square"])
        assert len(standing) == 1
        assert standing[0]["heading"] is None
        assert any("heading" in r for r in rejected)

    def test_the_ceiling_stops_at_a_countable_number(self):
        ops = [{"op": "set", "room": "square", "composition": "group %d" % i}
               for i in range(crowds.MAX_CROWDS + 3)]
        standing, rejected = crowds.apply_ops(
            [], ops, chat_id=1, turn=1, known_rooms=["square"])
        assert len(standing) == crowds.MAX_CROWDS
        assert len(rejected) == 3


class TestSplittingKeepsTwoCrowdsApart:
    def _throng(self):
        return crowds.apply_ops(
            [], [{"op": "set", "room": "square", "band": "a few dozen",
                  "composition": "market traders"}],
            chat_id=1, turn=1, known_rooms=["square", "gate"])[0]

    def test_a_split_gives_both_halves_the_same_band(self):
        """Band-preserving, not count-preserving. No arithmetic, no
        conservation bookkeeping, and therefore no drift."""
        before = self._throng()
        standing, _ = crowds.apply_ops(
            before, [{"op": "split", "crowd_id": before[0]["uid"],
                      "heading": "gate"}],
            chat_id=1, turn=2, known_rooms=["square", "gate"])
        assert len(standing) == 2
        assert [c["band"] for c in standing] == ["a dozen or so"] * 2

    def test_the_two_halves_do_not_share_one_id(self):
        """Two crowds where there was one. Identical band, composition and
        room make the uid material identical but for the recorded origin —
        which is exactly the collision this guards."""
        before = self._throng()
        standing, _ = crowds.apply_ops(
            before, [{"op": "split", "crowd_id": before[0]["uid"],
                      "heading": "gate"}],
            chat_id=1, turn=1, known_rooms=["square", "gate"])
        assert standing[0]["uid"] != standing[1]["uid"]
        assert standing[1]["from_uid"] == standing[0]["uid"]

    def test_a_handful_stays_whole(self):
        """Two smaller things the story has no word for. It stays whole and
        the Director may move it instead."""
        before = crowds.apply_ops(
            [], [{"op": "set", "room": "square", "band": "a handful",
                  "composition": "idlers"}],
            chat_id=1, turn=1, known_rooms=["square", "gate"])[0]
        standing, rejected = crowds.apply_ops(
            before, [{"op": "split", "crowd_id": before[0]["uid"],
                      "heading": "gate"}],
            chat_id=1, turn=2, known_rooms=["square", "gate"])
        assert len(standing) == 1 and rejected


class TestACrowdWalksTheGraphEveryoneElseWalks:
    def test_it_moves_one_room_along_and_spends_its_heading(self):
        """A heading that survived the beat would move the crowd twice for
        one declaration."""
        standing = [crowds.new_crowd(1, "square", band="a throng",
                                     composition="traders", since_turn=1,
                                     heading="gate")]
        moved, log = crowds.advance_crowds(standing, {"square": {"gate"}})
        assert moved[0]["room_uid"] == "gate"
        assert moved[0]["heading"] is None
        assert log == [{"uid": standing[0]["uid"], "from": "square",
                        "to": "gate"}]

    def test_it_does_not_walk_through_a_wall_that_appeared(self):
        """The scene is edited between beats. A crowd should not honour a
        heading into a room that is no longer next door."""
        standing = [crowds.new_crowd(1, "square", band="a throng",
                                     composition="traders", since_turn=1,
                                     heading="vault")]
        moved, log = crowds.advance_crowds(standing, {"square": {"gate"}})
        assert moved[0]["room_uid"] == "square"
        assert moved[0]["heading"] is None and log == []

    def test_there_is_no_second_pathfinder(self):
        """§5 asks for exactly one graph. `spatial.passable_neighbors` is it,
        and `passable_route_exists` was refactored onto the same function so
        the two can never disagree about what is adjacent."""
        import inspect

        from world import spatial
        assert "passable_neighbors(scene)" in \
            inspect.getsource(spatial.passable_route_exists)


class TestTheDirectorCanActuallySayIt:
    """The `project_ops` scar: a field the prompt asks for by name, that
    validation silently drops, fires zero times forever and looks like a model
    problem. Every link in the chain is asserted here rather than assumed."""

    def test_crowd_ops_survive_state_diff_validation(self):
        """Pydantic drops what the model has no field for. `project_ops` is
        promised in the character prompt, absent from `CharacterOutput`, and
        has been held by 0 of 26 characters ever."""
        from llm.schemas import StateDiff

        diff = StateDiff(**{"crowd_ops": [
            {"op": "set", "room": "square", "band": "a throng",
             "composition": "market traders", "mood": "restless",
             "heading": "gate"}]})
        kept = diff.dict()["crowd_ops"]
        assert len(kept) == 1
        assert kept[0]["composition"] == "market traders"
        assert kept[0]["heading"] == "gate"

    def test_the_shape_the_prompt_shows_is_the_shape_the_reader_opens(self):
        """The lore generator shipped `entry_ops` in the prompt and `entries`
        in the reader, and alpha 7.2 users got "no usable entries". The same
        drift is checked here on the field this feature depends on."""
        from llm import prompts

        text = prompts.DEFAULT_PROMPTS["director_offscreen"]
        assert "crowd_ops" in text
        assert "state_diff.crowd_ops" in text

    def test_the_normalizer_knows_crowd_ops_is_a_list(self):
        """A model returning a string where a list belongs kills the beat.
        Every other ops field is in this tuple; one that is not is a beat
        waiting to die."""
        from agents.director import _normalize_diff_shape

        assert _normalize_diff_shape({"crowd_ops": "a throng"})["crowd_ops"] == []
        assert _normalize_diff_shape({})["crowd_ops"] == []

    def test_the_example_the_repair_attempt_is_shown_carries_the_field(self):
        """The `required_json_example` is handed to the repair attempt too. A
        field described in prose and absent from the example is one a repair
        can never converge on — `state_diff.time` died that way.

        Asked of the hand that OWNS the channel. `crowd_ops` belongs to the
        offscreen specialist, and the prose author's example carries only its
        own four channels: showing it a delegated one asks it to spend the
        beat writing into a diff the owner replaces in the same fan-out."""
        from llm import schemas

        assert "crowd_ops" in schemas.SPECIALIST_CHANNELS["director_offscreen"]
        assert "crowd_ops" in schemas.OUTPUT_EXAMPLES["director_offscreen"]
        assert "crowd_ops" not in (
            schemas.OUTPUT_EXAMPLES["director_resolve"]["state_diff"])

    def test_commit_writes_them_under_the_one_key_perception_reads(self):
        """Two spellings of one world key is the whole `wearing`/`state` scar
        in miniature. There is one constant and both sides import it."""
        import inspect

        from persist import commit
        from agents.common import CROWDS_KEY

        assert CROWDS_KEY == crowds.CROWDS_WORLD_KEY
        body = inspect.getsource(commit.commit_crowds)
        assert "CROWDS_WORLD_KEY" in body
        assert "advance_crowds" in body

    def test_a_crowd_never_takes_a_managed_presence_slot(self):
        """If it does it has solved nothing — that is the entire reason the
        object exists."""
        import inspect

        from persist import commit
        body = inspect.getsource(commit.commit_crowds)
        assert "background_presences" not in body
        assert "max_managed" not in body

    def test_last_beats_flow_is_spent_before_this_beats_declaration(self):
        """The ordering defect `tools/crowd_drive.py` found on its first run.

        Applying ops and THEN advancing spends a heading inside the very
        commit that declared it, so the crowd arrives before anyone sees it
        leave — and `crowds_for_room` reports `drift: None` on every turn that
        will ever be perceived. The Director is told to resolve a press it can
        never be shown, and the whole terrain layer reads correct at every
        line and cannot fire.
        """
        import inspect

        from persist import commit
        body = inspect.getsource(commit.commit_crowds)
        assert body.index("advance_crowds") < body.index("apply_ops")

    def test_the_commit_counts_the_crowds_that_had_somewhere_to_be(self):
        """`fire_rates` read "a crowd moved on the graph" as moves over every
        standing crowd, so a fifty-one beat story where nobody ever declared a
        heading reported 0/78 -- a healthy mechanism looking stuck, which is
        this project's most expensive recurring discovery with its sign
        flipped. A crowd with no heading was never a chance to move. The count
        has to be taken from the state BEFORE `advance_crowds` spends them.
        """
        import inspect

        from persist import commit
        body = inspect.getsource(commit.commit_crowds)
        assert '"headed":' in body
        assert body.index("headed = ") < body.index("advance_crowds(")

    def test_a_heading_lives_exactly_one_beat_of_perception(self):
        """Long enough to be seen and resolved, short enough that one
        declaration moves the crowd once."""
        standing = [crowds.new_crowd(1, "square", band="a throng",
                                     composition="traders", since_turn=1,
                                     heading="gate")]
        first, moves = crowds.advance_crowds(standing, {"square": {"gate"}})
        assert moves and first[0]["heading"] is None
        second, again = crowds.advance_crowds(first, {"square": {"gate"}})
        assert again == [], "one declaration moved the crowd twice"


class TestEmergenceProducesStrangers:
    """§4. The part that writes rows outliving the scene, which is why it
    landed last."""

    def _square(self):
        return crowds.apply_ops(
            [], [{"op": "set", "room": "square", "band": "a throng",
                  "composition": "market traders"}],
            chat_id=1, turn=1, known_rooms=["square"])[0]

    def test_a_crowd_may_never_emerge_a_named_character(self):
        """A cast member coming out of the extras is indistinguishable in the
        record from one who was always there — a canon write nobody authored.
        If the Director wants Wilhelm in the square, he arrives."""
        before = self._square()
        standing, rejected = crowds.apply_ops(
            before, [{"op": "emerge", "crowd_id": before[0]["uid"],
                      "who": "Wilhelm van Astrea"}],
            chat_id=1, turn=2, known_rooms=["square"],
            roster=["Wilhelm van Astrea", "Mora"])
        assert standing[0].get("emerged") in (None, [])
        assert any("stranger" in r for r in rejected)

    def test_a_stranger_steps_out_and_the_crowd_remembers_it(self):
        before = self._square()
        standing, rejected = crowds.apply_ops(
            before, [{"op": "emerge", "crowd_id": before[0]["uid"],
                      "who": "a rope-seller"}],
            chat_id=1, turn=2, known_rooms=["square"], roster=["Mora"])
        assert standing[0]["emerged"] == ["a rope-seller"]
        assert rejected == []

    def test_the_band_does_not_move(self):
        """A throng minus one is a throng. Bands are coarse precisely so that
        nothing has to do arithmetic on them."""
        before = self._square()
        standing, _ = crowds.apply_ops(
            before, [{"op": "emerge", "crowd_id": before[0]["uid"],
                      "who": "a rope-seller"}],
            chat_id=1, turn=2, known_rooms=["square"])
        assert standing[0]["band"] == "a throng"

    def test_someone_who_only_moved_may_go_back(self):
        """Stepped aside, looked up, made room. Nothing durable names them."""
        before = self._square()
        out, _ = crowds.apply_ops(
            before, [{"op": "emerge", "crowd_id": before[0]["uid"],
                      "who": "a man with a basket"}],
            chat_id=1, turn=2, known_rooms=["square"])
        standing, rejected = crowds.apply_ops(
            out, [{"op": "absorb", "who": "a man with a basket"}],
            chat_id=1, turn=2, known_rooms=["square"], spoken=["Mora"])
        assert standing[0]["emerged"] == [] and rejected == []

    def test_emergence_is_one_way_for_anyone_who_speaks(self):
        """`dialogue_log` outlives the scene, mentions are already being
        counted, and an owed reply may be keyed to the name. Re-absorbing them
        would delete a person the record still points at."""
        before = self._square()
        out, _ = crowds.apply_ops(
            before, [{"op": "emerge", "crowd_id": before[0]["uid"],
                      "who": "a rope-seller"}],
            chat_id=1, turn=2, known_rooms=["square"])
        standing, rejected = crowds.apply_ops(
            out, [{"op": "absorb", "who": "a rope-seller"}],
            chat_id=1, turn=2, known_rooms=["square"],
            spoken=["Mora", "a rope-seller"])
        assert standing[0]["emerged"] == ["a rope-seller"]
        assert any("cannot go back" in r for r in rejected)

    def test_commit_decides_who_spoke_rather_than_asking(self):
        """The test is "does anything durable now name them", which is a
        question deterministic code can answer and a model cannot be trusted
        to answer about itself."""
        import inspect

        from persist import commit
        body = inspect.getsource(commit.commit_crowds)
        assert "dialogue_log" in body
        assert "_registered_name_roster" in body

    def test_the_person_is_not_given_a_second_identity_space(self):
        """`track_background_presences` already discovers anyone the Director
        gives a line or an entity def to. A second writer for the same person
        would be a sixth ledger keyed by display name."""
        import inspect

        assert "characters" not in inspect.getsource(crowds.emerge)
        assert "chat_chars" not in inspect.getsource(crowds.emerge)

    def test_an_opening_beat_can_put_people_in_the_square(self):
        """`director_establish` AUTHORS the first scene, and "the square is
        packed" is part of what that scene is — but establish carries no
        `state_diff`, so a crowd could not be declared until the second beat
        and a story that opened in a market opened in an empty one.

        Found by playing turns (`tools/story_drive.py`), not by reading code:
        the opening crowd op was silently absent from a shape that has no
        field for it, and every op afterwards referred to a crowd that was
        never raised.
        """
        import inspect

        from persist import commit
        from llm.schemas import DirectorEstablish

        kept = DirectorEstablish(**{"crowd_ops": [
            {"op": "set", "room": "square", "band": "a throng",
             "composition": "market traders"}]}).dict()["crowd_ops"]
        assert kept and kept[0]["composition"] == "market traders"
        # And commit reads BOTH shapes, or the field would be another
        # promised-and-dropped one.
        body = inspect.getsource(commit.commit_crowds)
        assert 'resolved.get("crowd_ops")' in body


class TestTheMurmurIsAboutSomething:
    """A crowd held rumours no payload ever showed.

    `crowd_hearsay` existed, `apply_tellings` could copy it onward — and the
    player standing in a market whose crowd held a rumour was told nothing,
    because neither the perception surface nor the Director's crowd view ever
    delivered what the crowd holds. The Director, told by its prompt to write
    `telling_ops` from a crowd, was asked for world_event_ids it had never
    seen — the exact defect the crowd uid and the carried-report id each had
    in turn: a field that exists and is never delivered.
    """

    def _crowd_with_talk(self):
        crowd = crowds.new_crowd(1, "square", band="a throng",
                                 composition="market traders", since_turn=1)
        return crowds.add_hearsay(crowd, {
            "world_event_id": "world_bell",
            "claim": "the warning bell rang twice", "retellings": 0})

    def test_talk_is_attributed_to_talk_and_never_to_a_name(self):
        view = crowds.talk_view(self._crowd_with_talk())
        assert view == [{"source": "talk among the market traders",
                         "gist": "the warning bell rang twice",
                         "world_event_id": "world_bell",
                         "retellings": 0}]

    def test_a_quiet_crowd_has_no_talk_entry(self):
        assert crowds.talk_view(crowds.new_crowd(
            1, "square", band="a handful", composition="x", since_turn=1)) == []

    def test_talk_is_now_not_an_archive(self):
        crowd = self._crowd_with_talk()
        for i in range(4):
            crowd = crowds.add_hearsay(crowd, {
                "world_event_id": "e%d" % i, "claim": "story %d" % i})
        assert len(crowds.talk_view(crowd)) == 2  # newest first, capped

    def test_an_observer_standing_in_the_room_overhears_the_gist(self, temp_db):
        """Own-room only by construction: every perception call site passes
        the observer's own room, so a crowd seen across a doorway stays a
        shape and a sound — words do not cross a room boundary."""
        import time

        from agents.common import crowds_for_room

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("Talk", "", time.time()))
        scene = {"rooms": {"square": {"name": "Square", "size": "large"}}}
        crowd = crowds.new_crowd(cid, "square", band="a throng",
                                 composition="market traders", since_turn=1)
        crowd = crowds.add_hearsay(crowd, {
            "world_event_id": "world_bell",
            "claim": "the warning bell rang twice"})
        temp_db.wset(cid, "crowds", [crowd])
        seen = crowds_for_room(cid, scene, "square")
        assert seen[0]["talk"][0]["gist"] == "the warning bell rang twice"
        assert seen[0]["talk"][0]["source"] == "talk among the market traders"

    def test_the_director_view_carries_the_ids_telling_ops_need(self, temp_db):
        import time

        from agents.director import _crowds_view

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("Talk", "", time.time()))
        scene = {"rooms": {"square": {"name": "Square", "size": "large"}}}
        crowd = crowds.new_crowd(cid, "square", band="a throng",
                                 composition="market traders", since_turn=1)
        crowd = crowds.add_hearsay(crowd, {
            "world_event_id": "world_bell",
            "claim": "the warning bell rang twice"})
        temp_db.wset(cid, "crowds", [crowd])
        view = _crowds_view(cid, scene)
        assert view[0]["talk"][0]["world_event_id"] == "world_bell"


class TestOneAnswerToHowBigTheRoomIs:
    """`crowds.room_size_rank` reads the authored `size` string and falls to
    `medium` for anything else; `spatial_geometry.effective_room_size` answers
    the same question with a name/desc keyword hint that promotes hall,
    warehouse, plaza, courtyard, atrium, cathedral, hangar and ten more to
    `large`. `crowds_for_room` was handing it the raw string.

    So an unsized "Great Hall" was `large` for proximity grading and `medium`
    for crowd density -- and `density("a throng", ...)` returns PACKED under
    one and CRUSH under the other. CRUSH is what `terrain` turns into a
    `membrane` you cannot see across, and what `drift` turns into CARRY.
    """

    def test_an_unsized_hall_is_the_same_size_to_both_layers(self, temp_db):
        import time

        from agents.common import crowds_for_room
        from world.spatial import effective_room_size

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("Hall", "", time.time()))
        scene = {"rooms": {"hall": {"name": "The Great Hall"}}}
        assert effective_room_size(scene, "hall") == "large"

        crowd = crowds.new_crowd(cid, "hall", band="a throng",
                                 composition="petitioners", since_turn=1)
        temp_db.wset(cid, "crowds", [crowd])
        seen = crowds_for_room(cid, scene, "hall")
        assert seen[0]["density"] == crowds.density("a throng", "large")

    def test_an_authored_size_still_wins(self, temp_db):
        import time

        from agents.common import crowds_for_room

        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("Hall", "", time.time()))
        scene = {"rooms": {"hall": {"name": "The Great Hall", "size": "small"}}}
        crowd = crowds.new_crowd(cid, "hall", band="a throng",
                                 composition="petitioners", since_turn=1)
        temp_db.wset(cid, "crowds", [crowd])
        seen = crowds_for_room(cid, scene, "hall")
        assert seen[0]["density"] == crowds.density("a throng", "small")
