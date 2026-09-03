"""A charter crowd is a read-time projection, never persisted.

``docs/design/DESIGN_BACKGROUND_PRESENTATION.md`` Part B. The stored crowds
ledger holds Director-authored people who exist ONLY as a band; charter
bodies are fully simulated people who need a cheaper presentation, and
storing a band, composition or membership for them would drift the moment
`charter_move.errands` walks a body elsewhere — the `wearing`/`state`/
`regions` scar `world/crowds.py`'s own module note is written after. So
everything here asserts the absence of storage as hard as it asserts the
presence of the view.

Measured on this branch, 2026-08-27 (twin_towns(40), 120 simulated hours):
the busiest room held 6 unpresented bodies, derived as "a handful" in
0.5ms on a cold memo and 0.007ms warm, with the stored crowds ledger empty
throughout; emerge/absorb round-tripped the membership 6 -> 5 -> 6 with the
charter's own stores untouched.
"""

from __future__ import annotations

import copy
import time

from world import charter_crowd, crowds


def _slice(**over):
    """A charter slice in `agents.common.chatter_inputs`' shape."""
    base = {
        "key": "guild",
        "bodies": {
            "b1": {"key": "b1", "name": "Marn", "place": "square"},
            "b2": {"key": "b2", "name": "Etta", "place": "square"},
            "b3": {"key": "b3", "name": "Sable", "place": "square"},
            "b4": {"key": "b4", "name": "Vane", "place": "square"},
            "b5": {"key": "b5", "name": "Odo", "place": "annex"},
        },
        "watch": {"warden": "b1"},
        "posts": {"warden": {"place": "square", "serves": []}},
        "naming": None,
        "figures": {},
        "known_bodies": frozenset(),
        "bindings": frozenset(),
        "feel": {},
    }
    base.update(over)
    return base


class TestTheCountMeetsTheBandOnce:
    """`count_band` is the ONE place an integer meets the band vocabulary,
    and it points the safe direction: integer -> word is a projection, and
    the reverse arithmetic still never happens anywhere."""

    def test_the_words_keep_their_plain_meanings(self):
        assert crowds.count_band(3) == "a handful"
        assert crowds.count_band(7) == "a handful"
        assert crowds.count_band(8) == "a dozen or so"
        assert crowds.count_band(19) == "a dozen or so"
        assert crowds.count_band(20) == "a few dozen"
        assert crowds.count_band(59) == "a few dozen"
        assert crowds.count_band(60) == "a throng"

    def test_the_projection_is_monotone(self):
        """More people may never read as fewer."""
        ranks = [crowds.band_rank(crowds.count_band(n)) for n in range(200)]
        assert ranks == sorted(ranks)

    def test_garbage_reads_as_the_fewest_people(self):
        """The same direction `normalize_band` falls: over-claiming puts
        bodies in a room nothing verified."""
        assert crowds.count_band(None) == crowds.BANDS[0]
        assert crowds.count_band(-4) == crowds.BANDS[0]


class TestTheUidIsIdentityNotMembership:
    def test_stable_across_beats_without_storage(self):
        """The material is the charter and the room — the same institution's
        people in the same place are the same crowd however many of them
        this window holds, which is what makes it mintable at every read."""
        assert (crowds.charter_crowd_uid(3, "guild", "square")
                == crowds.charter_crowd_uid(3, "guild", "square"))

    def test_a_different_charter_or_room_is_a_different_crowd(self):
        one = crowds.charter_crowd_uid(3, "guild", "square")
        assert one != crowds.charter_crowd_uid(3, "guild", "annex")
        assert one != crowds.charter_crowd_uid(3, "watch", "square")

    def test_recognisable_by_construction(self):
        """`apply_ops`' refusal hangs on the prefix, so the prefix is law."""
        assert crowds.is_charter_crowd_uid(
            crowds.charter_crowd_uid(3, "guild", "square"))
        assert not crowds.is_charter_crowd_uid(
            crowds.crowd_uid(3, "square", 1, "dockworkers"))


class TestMembershipIsASubtraction:
    """A charter body is ground exactly when nothing this beat presents it
    individually — the presentation boundary, not a headcount."""

    def test_bound_and_already_met_bodies_are_not_in_the_crowd(self):
        held = _slice(bindings=frozenset({"b3"}),
                      known_bodies=frozenset({"b2"}))
        assert charter_crowd.members_of(held, "square") == ["b1", "b4"]

    def test_membership_is_room_scoped_and_stable(self):
        assert charter_crowd.members_of(_slice(), "annex") == ["b5"]
        assert charter_crowd.members_of(_slice(), "") == []

    def test_below_the_floor_is_figures_not_a_crowd(self):
        """Two unvoiced bodies are two figures the existing overlay path can
        carry; `crowd_for` refuses to call them a crowd."""
        held = _slice(bindings=frozenset({"b3", "b4"}))
        assert len(charter_crowd.members_of(held, "square")) \
            == crowds.CHARTER_CROWD_FLOOR - 1
        assert charter_crowd.crowd_for(3, held, "square") is None
        assert charter_crowd.crowd_for(3, _slice(), "square") is not None


class TestTheDerivedFieldsComeFromWhatTheCharterOwns:
    def test_the_row_is_the_stored_shape_with_no_birthday(self):
        crowd = charter_crowd.crowd_for(3, _slice(), "square")
        assert crowd["band"] == "a handful"
        assert crowd["derived"] is True
        assert crowd["heading"] is None
        assert "since_turn" not in crowd, "a projection has no birthday"
        # The membership count died inside: band only, no integer out.
        assert not any(isinstance(v, int) and not isinstance(v, bool)
                       for v in crowd.values())

    def test_composition_is_the_dominant_role_nouns(self):
        """Posts are authored per charter, so the string is genre-correct
        without the module knowing any genre; slot disambiguators
        (`patrol_a`/`patrol_b` are two slots, one kind of person) do not
        leak into the noun."""
        held = _slice(watch={"patrol_a": "b1", "patrol_b": "b2"},
                      posts={"patrol_a": {"place": "square"},
                             "patrol_b": {"place": "square"}})
        assert charter_crowd.composition_of(
            ["b1", "b2", "b3"], held) == "patrols"

    def test_an_institution_of_none_is_people(self):
        """The ambient charter has no posts and no upkeeps; its crowd is
        `describe`'s own default made explicit rather than an invented
        collective noun."""
        held = _slice(watch={}, posts={})
        assert charter_crowd.composition_of(["b2", "b3", "b4"], held) \
            == "people"

    def test_mood_is_the_aggregate_strain_banded(self):
        """Mean over ALL members: ten fresh hands beside one exhausted one
        are not a weary crowd."""
        worn = {k: {"stress": {"strain": 0.9}} for k in
                ("b1", "b2", "b3", "b4")}
        assert charter_crowd.mood_of(["b1", "b2", "b3", "b4"], worn) \
            == "worn thin"
        assert charter_crowd.mood_of(["b1", "b2", "b3", "b4"],
                                     {"b1": {"stress": {"strain": 0.9}}}) \
            == ""
        assert charter_crowd.mood_of(["b1", "b2"], {}) == ""


class TestOpsOnADerivedCrowdAreRefused:
    """`move`, `split`, `disperse` and `set` on a derived crowd would make
    `crowd_ops` a second writer on where charter bodies stand — the scar
    again. `apply_ops` already refuses uids it did not mint; a charter uid
    is recognisable by construction and refused by name."""

    def test_every_rewriting_op_is_refused_and_nothing_is_minted(self):
        uid = crowds.charter_crowd_uid(1, "guild", "square")
        for op in ("move", "split", "disperse", "set"):
            standing, rejected = crowds.apply_ops(
                [], [{"op": op, "crowd_id": uid, "room": "square",
                      "heading": "square", "composition": "anyone"}],
                chat_id=1, turn=2, known_rooms=["square"])
            assert standing == []
            assert len(rejected) == 1 and "derived" in rejected[0], (op, rejected)

    def test_a_misrouted_emerge_fails_closed(self):
        """The commit seam routes charter emerges out before this fold runs;
        one landing here is a caller that forgot, and the pure fold cannot
        reach the registry, so it refuses rather than guessing."""
        uid = crowds.charter_crowd_uid(1, "guild", "square")
        standing, rejected = crowds.apply_ops(
            [], [{"op": "emerge", "crowd_id": uid, "who": "Etta"}],
            chat_id=1, turn=2, known_rooms=["square"])
        assert standing == []
        assert rejected and "commit seam" in rejected[0]


class TestReadTimeOnly:
    """The falsifier the design names: any reproduction of a stale band or
    composition proves something got stored, and the fix is deletion of the
    storage, not reconciliation."""

    def _story(self, temp_db, *, bind=None, ledger=None):
        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Bridge", "", time.time()))
        scene = {
            "location": "Low Town",
            "rooms": {"square": {"name": "Square", "size": "large"},
                      "office": {"name": "Back Office", "size": "small"}},
            "positions": {"Aldous": "square"},
        }
        state = {
            "key": "guild", "upkeeps": {}, "priority": [],
            "posts": {"warden": {"place": "square", "serves": [],
                                 "requires": {}}},
            "bodies": {
                "b1": {"name": "Marn", "place": "square", "available": True,
                       "competence": {}},
                "b2": {"name": "Etta", "place": "square", "available": True,
                       "competence": {}},
                "b3": {"name": "Sable", "place": "square", "available": True,
                       "competence": {}},
                "b4": {"name": "Vane", "place": "square", "available": True,
                       "competence": {}},
                "b5": {"name": "Odo", "place": "annex", "available": True,
                       "competence": {}},
            },
            "watch": {"warden": "b1"},
            "figures": {"Aldous": {"place": "square"}},
        }
        if bind:
            state["bindings"] = {key: {"char_id": 7, "name": name}
                                 for key, name in bind.items()}
        temp_db.wset(cid, "charters", {"items": {"guild": {"state": state}}})
        if ledger:
            temp_db.wset(cid, "background_presences", ledger)
        return cid, scene

    def test_the_derived_crowd_stands_beside_the_authored_one(self, temp_db):
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        authored = crowds.new_crowd(cid, "square", band="a few dozen",
                                    composition="dockworkers", since_turn=1)
        temp_db.wset(cid, "crowds", [authored])
        seen = crowds_for_room(cid, scene, "square")
        assert len(seen) == 2
        assert seen[0]["uid"] == authored["uid"]
        assert crowds.is_charter_crowd_uid(seen[1]["uid"])
        assert seen[1]["derived"] is True
        # One view shape for two species: every key the composer and the
        # payloads read is present on both rows.
        for key in ("uid", "what", "density", "terrain", "drift", "emerged",
                    "talk"):
            assert key in seen[0] and key in seen[1], key

    def test_reading_persists_nothing_and_replays_identically(self, temp_db):
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        first = crowds_for_room(cid, scene, "square")
        assert first and first[0]["derived"] is True
        assert temp_db.wget(cid, "crowds", []) == [], \
            "a derived crowd occupied a ledger row"
        assert not (temp_db.wget(cid, "background_presences", {}) or {})
        assert crowds_for_room(cid, scene, "square") == first

    def test_a_live_presence_record_removes_its_body_from_the_ground(
            self, temp_db):
        """The overlay record IS the emergence record: no `emerged` list is
        stored, membership just excludes the body at the next read."""
        from agents.common import charter_crowds_for_room
        ledger = {"p_x": {"name": "Etta", "nature": "person",
                          "dialogue_turns": [], "mention_turns": [],
                          "addressed_turns": [],
                          "charter_refs": [{"charter": "guild",
                                            "body": "b2"}]}}
        cid, scene = self._story(temp_db, ledger=ledger)
        crowd = charter_crowds_for_room(cid, scene, "square")[0]
        # Four bodies in the square minus the one already met: a handful of
        # three, exactly at the floor.
        assert crowd["band"] == "a handful"
        from world.charter_crowd import members_of
        from agents.common import chatter_inputs
        held = chatter_inputs(cid, scene)["charters"][0]
        assert members_of(held, "square") == ["b1", "b3", "b4"]

    def test_the_authored_ceiling_is_not_spent_on_derived_crowds(
            self, temp_db):
        """`MAX_CROWDS` is a coherence limit on the Director populating
        rooms nobody is standing in; a derived crowd is the opposite case —
        people who verifiably ARE standing there — and occupies no row, so
        the full ledger neither hides it nor is widened by it."""
        from agents.common import crowds_for_room
        cid, scene = self._story(temp_db)
        full = [crowds.new_crowd(cid, "office", band="a handful",
                                 composition="clerks lot %d" % n,
                                 since_turn=n)
                for n in range(crowds.MAX_CROWDS)]
        temp_db.wset(cid, "crowds", full)
        seen = crowds_for_room(cid, scene, "square")
        assert [c for c in seen if c.get("derived")], \
            "a full authored ledger hid the derived crowd"
        assert len(temp_db.wget(cid, "crowds", [])) == crowds.MAX_CROWDS


class TestEmergeIsTheExistingOverlay:
    """§B3: emergence resolves the body into the presence ledger through
    `with_charter_presences`, identity-carefully, and the derived crowd
    excludes it from membership on the next read. No `emerged` list, no
    second identity space, and the band does not move."""

    def _story(self, temp_db, **kw):
        return TestReadTimeOnly()._story(temp_db, **kw)

    def test_a_named_body_steps_out_and_the_record_is_the_record(
            self, temp_db):
        from persist.commit import emerge_from_charter_crowd
        from agents.common import charter_crowds_for_room
        cid, scene = self._story(temp_db)
        name, reason = emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=7)
        assert name == "Etta" and not reason
        ledger = temp_db.wget(cid, "background_presences", {})
        assert len(ledger) == 1
        record = next(iter(ledger.values()))
        assert {"charter": "guild", "body": "b2"} in record["charter_refs"]
        assert record["first_turn"] == 7
        # Next read: she is figure, not ground — and the band did not move,
        # because subtracting a person from a word is the arithmetic bands
        # exist to refuse.
        crowd = charter_crowds_for_room(cid, scene, "square")[0]
        assert crowd["band"] == "a handful"
        from agents.common import chatter_inputs
        from world.charter_crowd import members_of
        held = chatter_inputs(cid, scene)["charters"][0]
        assert "b2" not in members_of(held, "square")

    def test_the_same_person_is_there_next_visit(self, temp_db):
        """The superseded rule, asserted from the charter side: the body
        persists in Charter with its ties and diary, so the person who
        stepped out last visit IS there — as the presence record, not as a
        second copy the crowd could produce again."""
        from persist.commit import emerge_from_charter_crowd
        cid, scene = self._story(temp_db)
        assert emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=7)[0]
        again, reason = emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=9)
        assert not again and "nobody" in reason.casefold() or "names nobody" in reason
        assert len(temp_db.wget(cid, "background_presences", {})) == 1

    def test_a_bound_body_cannot_be_emerged(self, temp_db):
        """A cast member coming out of the extras is a canon write nobody
        authored; the resolver excludes bound bodies, so naming one resolves
        to nobody and fails closed."""
        from persist.commit import emerge_from_charter_crowd
        cid, scene = self._story(temp_db, bind={"b1": "Marn"})
        name, reason = emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Marn", turn_idx=7)
        assert not name and reason
        assert not (temp_db.wget(cid, "background_presences", {}) or {})

    def test_the_engine_picks_the_member_with_a_reason(self, temp_db):
        """When `who` is empty, the selector ranks members by entanglement
        with whoever is present — served_beside history here — so the person
        who steps out of the crowd is the one with a reason to, and a replay
        picks the same one."""
        from persist.commit import emerge_from_charter_crowd
        cid, scene = self._story(temp_db)
        held = temp_db.wget(cid, "charters", {})
        held["items"]["guild"]["state"]["served_beside"] = {
            "b4": {"Aldous": 6}}
        temp_db.wset(cid, "charters", held)
        name, reason = emerge_from_charter_crowd(
            cid, scene, "guild", "square", present=["Aldous"], turn_idx=7)
        assert name == "Vane", reason


class TestAbsorbLosesOnlyThePresentation:
    """§B3: nothing happens to the body's simulation, because it never had a
    separate simulation to lose — Charter simulates every unbound body every
    window whether or not anyone is looking. Absorption is only the presence
    record being removed, and only while nothing durable names the person."""

    def _story(self, temp_db, **kw):
        return TestReadTimeOnly()._story(temp_db, **kw)

    def test_a_never_engaged_emergence_goes_back_to_ground(self, temp_db):
        from persist.commit import (absorb_into_charter_crowd,
                                    emerge_from_charter_crowd)
        cid, scene = self._story(temp_db)
        before = copy.deepcopy(temp_db.wget(cid, "charters", {}))
        assert emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=7)[0]
        handled, reason = absorb_into_charter_crowd(cid, "Etta")
        assert handled and not reason
        assert not (temp_db.wget(cid, "background_presences", {}) or {})
        # NOTHING ELSE changed: the charter's own stores are untouched,
        # because crowd membership is a lens.
        assert temp_db.wget(cid, "charters", {}) == before

    def test_anyone_durably_named_cannot_be_deleted_back(self, temp_db):
        """The one-way rule with its original test — "does anything durable
        now name them" — answered by deterministic code, never a model."""
        from persist.commit import absorb_into_charter_crowd
        ledger = {"p_x": {"name": "Etta", "nature": "person",
                          "dialogue_turns": [12], "mention_turns": [],
                          "addressed_turns": [],
                          "charter_refs": [{"charter": "guild",
                                            "body": "b2"}]}}
        cid, scene = self._story(temp_db, ledger=ledger)
        handled, reason = absorb_into_charter_crowd(cid, "Etta")
        assert handled and "cannot be deleted" in reason
        assert "p_x" in temp_db.wget(cid, "background_presences", {})

    def test_speaking_this_beat_is_already_durable(self, temp_db):
        from persist.commit import (absorb_into_charter_crowd,
                                    emerge_from_charter_crowd)
        cid, scene = self._story(temp_db)
        assert emerge_from_charter_crowd(
            cid, scene, "guild", "square", who="Etta", turn_idx=7)[0]
        handled, reason = absorb_into_charter_crowd(
            cid, "Etta", spoken=["Etta"])
        assert handled and "has spoken" in reason
        assert temp_db.wget(cid, "background_presences", {})

    def test_a_name_that_is_no_charter_body_is_not_this_seams_op(
            self, temp_db):
        """(False, "") hands the op back to `crowds.absorb`, which owns the
        authored ledger's emerged lists."""
        from persist.commit import absorb_into_charter_crowd
        cid, _scene = self._story(temp_db)
        assert absorb_into_charter_crowd(cid, "a rope-seller") == (False, "")

    def test_a_charter_body_never_presented_absorbs_as_a_no_op(
            self, temp_db):
        """The overlay record was simply never persisted — which is what
        absorption of a never-engaged body IS."""
        from persist.commit import absorb_into_charter_crowd
        cid, _scene = self._story(temp_db)
        assert absorb_into_charter_crowd(cid, "Etta") == (True, "")


class TestTheDirectorIsShownWhatItMayActOn:
    """The uid-never-delivered defect class, guarded for the derived
    species: `emerge` requires a crowd_id the Director has seen, so
    `_crowds_view` carries derived rows with their uids and the `derived`
    mark whose law the prompt states."""

    def test_the_view_carries_the_derived_crowd_with_its_uid(self, temp_db):
        from agents.director import _crowds_view
        cid, scene = TestReadTimeOnly()._story(temp_db)
        rows = _crowds_view(cid, scene)
        derived = [r for r in rows if r.get("derived")]
        assert derived and crowds.is_charter_crowd_uid(
            derived[0]["crowd_id"])
        assert derived[0]["room"] == "square"

    def test_the_prompt_states_the_derived_law(self):
        from llm.prompts import DEFAULT_PROMPTS
        sheet = DEFAULT_PROMPTS["director_social"]
        assert "crowd:charter:" in sheet


class TestReceiptRidesTheExistingSeam:
    """No new percept kind and no new door: a derived crowd is one more row
    in the `crowds` view, so `room_content_percepts` renders it and
    `observations_from_render` makes character receipt legitimate exactly as
    it does for an authored crowd."""

    def test_the_derived_crowd_is_rendered_and_re_derived(self, temp_db):
        from agents import composer
        from agents.common import crowds_for_room
        cid, scene = TestReadTimeOnly()._story(temp_db)
        percepts = composer.room_content_percepts(
            crowds_for_room(cid, scene, "square"))
        assert percepts, "the derived crowd produced no percept"
        rendered = composer.render_view(percepts, mode="character",
                                        full_render=True)
        assert "a handful" in rendered.text
        obs = composer.observations_from_render("player", rendered)
        assert any("a handful" in str(o) for o in obs)
