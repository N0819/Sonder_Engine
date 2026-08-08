"""The two axes, the seeded draw, and the out-of-band producer.

Steps 3, 3a and 4 of docs/PROPOSAL_2026-08-06.md section 1.2, plus the
section 1.0.2 producer. Every test names what broke or what it prevents;
the recurring theme is the proposal's own: resolution decides SPEND, so it
must be trivially testable, and a rung that claims to be seeded must
re-derive identically or a reroll quietly writes a second history.
"""

from __future__ import annotations

import time

from offscreen import (
    IMPORTANCE_LEVELS,
    OVERRIDE_FIELD,
    TICK_CADENCE_TURNS,
    derived_importance,
    importance_for,
    resolution_for,
    stochastic_ticks,
    subject_distance,
    tick_due,
)


def scene_with_rooms():
    """Three rooms in a walkable line, one severed by a wall."""

    return {
        "rooms": {
            "bar": {"adjacent": [{"to": "hall", "barrier": "open"}]},
            "hall": {"adjacent": [{"to": "cellar", "barrier": "closed_door"}]},
            "cellar": {"adjacent": []},
            "vault": {"adjacent": [{"to": "cellar", "barrier": "wall"}]},
        },
    }


class TestImportanceFollowsWhatTheEngineKnows:
    """Section 1.2 step 3: importance derives from cast membership, the
    sheet, psychology and memory — not from a new field somebody must
    maintain. The chat-level `offscreen_life` ceiling could previously only
    make EVERYTHING richer or poorer at once."""

    def test_no_cast_row_or_no_sheet_is_background(self):
        """The lazy rung already covers the whole background cast at zero
        standing cost; ticking furniture is O(cast x turns), the exact shape
        the design refuses."""
        assert derived_importance(is_cast=False, has_sheet=False, tier="major") == "background"
        assert derived_importance(is_cast=True, has_sheet=False, tier="major") == "background"

    def test_the_tier_ledger_is_the_engines_own_line(self):
        assert derived_importance(is_cast=True, has_sheet=True, tier="major") == "major"
        assert derived_importance(is_cast=True, has_sheet=True, tier="bg") == "background"

    def test_a_stub_sheet_does_not_earn_supporting(self):
        """An auto-promoted near-blank sheet is furniture wearing a sheet.
        Without this, every promotion inflates the bounded tick budget."""
        assert derived_importance(
            is_cast=True, has_sheet=True, tier="mid",
            psychology_authored=False, has_memories=False) == "background"
        assert derived_importance(
            is_cast=True, has_sheet=True, tier="mid",
            psychology_authored=True, has_memories=False) == "supporting"
        assert derived_importance(
            is_cast=True, has_sheet=True, tier="mid",
            psychology_authored=False, has_memories=True) == "supporting"

    def test_the_override_sits_on_top_of_the_default_never_instead(self):
        """The proposal's open question 1, answered as asked: an innkeeper
        who became the plot deserves major and nothing structural knows it.
        The override is one more dial, not a field everyone must fill."""
        assert importance_for("supporting", "major") == "major"
        assert importance_for("major", "background") == "background"
        assert importance_for("supporting", None) == "supporting"

    def test_an_unreadable_override_falls_to_the_derived_default(self):
        """Never to the floor — a typo must not silently demote the villain.
        Same rule as scene.normalize_offscreen_life, same reason."""
        assert importance_for("major", "extremely important") == "major"
        assert importance_for("major", "") == "major"

    def test_the_override_field_is_not_the_permission_ladder(self):
        """BehaviorController answers what a character MAY do; importance
        answers how much they MATTER. One vocabulary answering two questions
        is the flow.reactors defect (79% wrong, section 2D) re-minted."""
        from schemas import BehaviorController

        assert OVERRIDE_FIELD == "offscreen_importance"
        for level in IMPORTANCE_LEVELS:
            assert level not in {c.value for c in BehaviorController}


class TestDistanceIsBeatsToContact:
    """Not metres (section 1.2 step 3). Crude buckets are enough because
    the decision they feed has two outcomes: spend a model call or not."""

    def test_the_three_buckets(self):
        sc = scene_with_rooms()
        assert subject_distance(sc, "bar", "bar") == "same_room"
        assert subject_distance(sc, "cellar", "bar") == "same_region"
        assert subject_distance(sc, "vault", "bar") == "elsewhere"

    def test_a_wall_is_not_a_route(self):
        """Counting a wall edge would put a subject one beat away through
        solid stone — the same phantom-edge shape UNBUILT section 1.6
        measured in the place graph, refused here at birth."""
        sc = scene_with_rooms()
        assert subject_distance(sc, "vault", "cellar") == "elsewhere"

    def test_a_closed_door_is_one_beat_not_a_severance(self):
        """A dormant subject behind a closed door is exactly the person you
        are about to walk in on."""
        sc = scene_with_rooms()
        assert subject_distance(sc, "cellar", "hall") == "same_region"

    def test_an_unknown_room_is_elsewhere(self):
        """Never-seen means no anchor; guessing nearness would spend model
        calls on ghosts."""
        sc = scene_with_rooms()
        assert subject_distance(sc, None, "bar") == "elsewhere"
        assert subject_distance(sc, "atlantis", "bar") == "elsewhere"

    def test_an_intention_aimed_at_the_player_pulls_one_step_closer(self):
        """'Whether a standing intention points at where the player is' —
        consequences walking toward the player are near whatever the map
        says. One step only, and never further away."""
        sc = scene_with_rooms()
        assert subject_distance(sc, "vault", "bar",
                                intention_at_player=True) == "same_region"
        assert subject_distance(sc, "bar", "bar",
                                intention_at_player=True) == "same_room"


class TestResolutionIsAPureSpendDecision:
    """The function that decides spend must be trivially testable — that is
    the proposal's stated reason for keeping it pure."""

    def test_the_matrix(self):
        assert resolution_for("background", "same_room") == "inert"
        assert resolution_for("background", "elsewhere") == "inert"
        assert resolution_for("major", "same_room") == "medium"
        assert resolution_for("major", "same_region") == "medium"
        assert resolution_for("major", "elsewhere") == "low"
        assert resolution_for("supporting", "same_room") == "medium"
        assert resolution_for("supporting", "same_region") == "low"
        assert resolution_for("supporting", "elsewhere") == "low"

    def test_unknown_inputs_fail_toward_not_spending(self):
        """A spend decision that fails open is a budget with a hole in it."""
        assert resolution_for("celebrity", "same_room") == "inert"
        assert resolution_for("major", "nearby-ish") == "low"

    def test_the_villain_sharpens_as_you_approach_without_anyone_editing_a_setting(self):
        """Section 1.0 reason 1: resolution is recomputed, not stored. The
        same subject scores differently as only their distance moves."""
        sc = scene_with_rooms()
        far = resolution_for("major", subject_distance(sc, "vault", "bar"))
        near = resolution_for("major", subject_distance(sc, "hall", "bar"))
        assert (far, near) == ("low", "medium")


class TestTheSeededDraw:
    """Step 4. The shipped 'stochastic' rung rode a model call and its
    tick_seed seeded nothing — no RNG in commit.py ever consumed it. The
    architecture's rule is 'seeded, logged, replayable; stochastic-unlogged
    ticks forbidden', and a rung that costs a model call prices low
    resolution for six characters instead of free for the cast."""

    ACTORS = [
        {"id": "guinan_7f3a", "display": "Guinan"},
        {"id": "character:9", "display": "Reyet Solan"},
        {"id": "mora_11ab", "display": "Mora"},
    ]
    INTENTIONS = [
        {"who": "Guinan", "intent": "reopen the bar in Ten Forward"},
        "Reyet Solan means to reach the northern garrison",
    ]

    def test_same_seed_same_inputs_same_ticks_byte_for_byte(self):
        """A reroll must re-derive the same offscreen history rather than
        quietly becoming a second one."""
        a = stochastic_ticks("tick:59:165", self.ACTORS, self.INTENTIONS, 3)
        b = stochastic_ticks("tick:59:165", self.ACTORS, self.INTENTIONS, 3)
        assert a == b

    def test_a_different_seed_may_draw_differently(self):
        """Not asserted per-tick (a draw may coincide); asserted across a
        spread of seeds, where identical output would mean the seed is
        decoration — which is exactly what tick_seed was."""
        outputs = {
            str(stochastic_ticks(f"tick:59:{i}", self.ACTORS, self.INTENTIONS, 3))
            for i in range(12)
        }
        assert len(outputs) > 1

    def test_no_model_is_consulted(self):
        """The whole point of the step. The draw is importable and runnable
        with no provider configured and no database."""
        import inspect

        import offscreen

        src = inspect.getsource(offscreen.stochastic_ticks)
        assert "chat_complete" not in src
        assert "complete_validated_json" not in src

    def test_ticks_are_keyed_by_subject_id_from_birth(self):
        """offscreen_log's name-keyed `actor` is the live section 2A defect
        (the one row ever written keys 'Picard' by display name). Ticks
        minted here carry the id in `actor` and the name only as prose."""
        ticks = stochastic_ticks("tick:59:165", self.ACTORS, self.INTENTIONS, 3)
        for t in ticks:
            assert t["actor"] == t["subject"]["id"]
            assert t["actor"] in {a["id"] for a in self.ACTORS}

    def test_an_actor_without_an_id_gets_no_tick(self):
        """Minting identity in a tick writer would be 0c's defect from the
        other side."""
        ticks = stochastic_ticks(
            "s", [{"display": "A Dalek"}], [], 3)
        assert ticks == []

    def test_a_matching_intention_seeds_the_tick_text(self):
        """The draw is AGAINST standing intentions, not beside them: a
        dormant actor with a recorded aim ticks toward that aim, and the
        intention rides the record so a reader can see what it drew from."""
        found = []
        for i in range(24):
            for t in stochastic_ticks(f"s{i}", self.ACTORS, self.INTENTIONS, 3):
                if t["actor"] == "guinan_7f3a" and t["intention"]:
                    found.append(t)
        assert found, "24 seeds never once drew the recorded intention"
        assert any("Ten Forward" in t["tick"] for t in found)

    def test_a_tick_describes_and_cannot_commit(self):
        """Section 1.0.1: the record shape differs by rung — a rung that
        cannot express a consequence cannot smuggle one. No deltas, no
        standing-intention writes, no position moves (a position change has
        no warrant check — UNBUILT section 1.20 — and an offscreen writer
        would build the missing third warrant by accident)."""
        from canon_provenance import validate_provisional

        for t in stochastic_ticks("tick:59:165", self.ACTORS, self.INTENTIONS, 3):
            assert "deltas" not in t
            assert "standing_intentions" not in t
            assert "positions" not in t
            result = validate_provisional({**t, "base_turn": 165})
            assert result.ok, result.errors

    def test_the_cap_is_a_cap(self):
        many = [{"id": f"actor_{i}", "display": f"A{i}"} for i in range(20)]
        assert len(stochastic_ticks("s", many, [], 3)) <= 3
        assert stochastic_ticks("s", many, [], 0) == []


class TestTheLogHasOneDoor:
    """Two writers doing wget/append/wset independently is a lost-update
    race the moment the producer lands mid-turn. Both the commit path and
    the producer go through offscreen.append_offscreen_log."""

    def test_commit_writes_through_the_helper(self):
        import inspect

        import commit

        src = inspect.getsource(commit.commit_mapping)
        assert "append_offscreen_log" in src
        assert 'wset(cid, "offscreen_log"' not in src

    def test_a_refused_record_is_dropped_with_a_note_not_stored(self, temp_db):
        """A stored invented room outlives the turn that made it — the
        'quiet office' row is the argument, and the write path is where the
        gate belongs (section 1.0.3)."""
        from db import wget
        from offscreen import append_offscreen_log

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        bad = {
            "disposition": "provisional",
            "subject": {"kind": "character", "id": "guinan_7f3a"},
            "basis": "deterministic",
            "actor": "guinan_7f3a", "tick": "she waited",
            "room": "a quiet office",
        }
        good = {
            "disposition": "provisional",
            "subject": {"kind": "character", "id": "mora_11ab"},
            "basis": "deterministic",
            "actor": "mora_11ab", "tick": "she carried on",
        }
        kept = append_offscreen_log(cid, 7, "tick:1:7", [bad, good])
        assert [e["actor"] for e in kept] == ["mora_11ab"]
        log = wget(cid, "offscreen_log", [])
        assert len(log) == 1
        assert [e["actor"] for e in log[0]["events"]] == ["mora_11ab"]

    def test_a_batch_with_nothing_left_writes_no_batch(self, temp_db):
        """An empty batch row is noise wearing a turn stamp."""
        from db import wget
        from offscreen import append_offscreen_log

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        bad = {
            "disposition": "provisional",
            "subject": {"kind": "character", "id": "guinan_7f3a"},
            "basis": "deterministic", "actor": "guinan_7f3a",
            "tick": "x", "room": "a quiet office",
        }
        assert append_offscreen_log(cid, 7, "s", [bad]) == []
        assert wget(cid, "offscreen_log", []) == []


class TestTheProducer:
    """Section 1.0.2: produce on a cadence, out of band, in parallel with
    turns — and a turn starting must never cancel an in-flight tick, because
    that makes the world's progress depend on player idleness (amendment 4)."""

    def test_the_cadence_is_a_pure_function_of_the_turn_index(self):
        """No wall clock, no unseeded RNG: rerun-from-stage and reroll must
        not silently change whether the world was alive (BACKGROUND_LIFE
        section 5's rule, applied to this cadence)."""
        assert not tick_due(0)
        assert [i for i in range(1, 10) if tick_due(i)] == [
            i for i in range(1, 10) if i % TICK_CADENCE_TURNS == 0]
        assert not tick_due(None)
        assert not tick_due("soon")

    def test_the_producer_is_wired_at_the_commit_tail(self):
        """jobs.py had zero production consumers — a queue with no producer.
        The hook sits where the turn's facts are already durable, beside the
        other post-transaction work whose failure is a warning."""
        import inspect

        import commit

        src = inspect.getsource(commit._commit_all_locked)
        assert "schedule_profile_ticks" in src

    def test_nothing_cancels_jobs_on_turn_start(self):
        """The user's one explicit rule for this producer. jobs.cancel
        exists for authored teardown; the pipeline must not call it."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1]
        for name in ("commit.py", "app.py"):
            src = (root / name).read_text(encoding="utf-8")
            assert "jobs.cancel" not in src, name
        runtime = (root / "agents" / "runtime.py").read_text(encoding="utf-8")
        assert "jobs.cancel" not in runtime

    def test_a_tick_landing_after_a_rollback_is_discarded(self, temp_db):
        """Section 1.0.2 hazard 2: a tick computed against turn N describes
        a future that no longer happens once the player rolls back past N.
        base_turn is what makes that decidable; the landing check is what
        acts on it. The engine's own precedent is the checkpoint restore
        that silently undid a completed embedding rebuild."""
        from db import wget
        from offscreen import land_profile_ticks

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        # The story is at turn 3; the tick was computed against turn 9.
        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (cid, 3, "", time.time()))
        events = [{"disposition": "provisional",
                   "subject": {"kind": "character", "id": "guinan_7f3a"},
                   "basis": "model", "actor": "guinan_7f3a",
                   "tick": "she waited"}]
        assert land_profile_ticks(cid, 9, events) == {"written": 0,
                                                      "discarded": 1}
        assert wget(cid, "offscreen_log", []) == []

    def test_a_tick_landing_in_a_live_story_is_written(self, temp_db):
        """The guard must not eat legitimate work: base_turn at or behind
        the story's head lands."""
        from db import wget
        from offscreen import land_profile_ticks

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (cid, 9, "", time.time()))
        events = [{"disposition": "provisional",
                   "subject": {"kind": "character", "id": "guinan_7f3a"},
                   "basis": "model", "actor": "guinan_7f3a",
                   "tick": "she waited"}]
        assert land_profile_ticks(cid, 9, events) == {"written": 1}
        log = wget(cid, "offscreen_log", [])
        assert len(log) == 1 and log[0]["rung"] == "profile"


class TestTheProfileRung:
    """Step 3a: one call, no psychology run, no adjudication, structurally
    unable to emit a consequence. This is the rung most characters will
    actually use."""

    def test_the_profile_surface_excludes_psychology(self):
        """'No psychology run' is the rung's definition. A drive leaking
        into a cheap cadenced call would make the honest full-agent rung
        indistinguishable from this sketch."""
        from offscreen import _profile_surface

        sheet = {
            "identity": {"name": "Guinan"},
            "psychology": {"drive": {"essence": "listen to everyone",
                                     "expression": "", "taboo": ""}},
            "initial_state": {"goals": ["reopen the bar"]},
        }
        surface = _profile_surface(sheet)
        assert surface["name"] == "Guinan"
        assert "listen to everyone" not in str(surface)
        assert "reopen the bar" in surface["standing_goals"]

    def test_the_output_shape_has_nowhere_to_put_an_alliance(self):
        """Section 1.0.1's enforcement is the record shape, not a prompt
        clause: the record a profile tick writes is the provisional tier's,
        and validate_provisional refuses consequences on it."""
        import inspect

        import offscreen

        src = inspect.getsource(offscreen.profile_summary_record)
        assert '"deltas"' not in src
        assert "ratified_claims" not in src

    def test_a_failed_call_falls_back_to_the_deterministic_record(self, temp_db, monkeypatch):
        """A deterministic 'she was elsewhere' is worth more than a
        plausible lie (section 1.0.3), and a fallen-back record says what it
        fell from rather than wearing the model basis silently."""
        import offscreen

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))

        def _boom(*a, **k):
            raise RuntimeError("provider down")

        import providers

        monkeypatch.setattr(providers, "chat_complete", _boom)
        record = offscreen.profile_summary_record(
            cid, {"rooms": {}}, {"kind": "character", "id": "guinan_7f3a"},
            {}, 3, 9)
        assert record["basis"] in ("deterministic", "unavailable")
        assert record.get("summary") in (None, "")
        if record["basis"] == "deterministic":
            assert "fell_back_from" in (record.get("inputs") or {})


class TestTheProfileRungEmitsState:
    """The rung's model call was legitimate (out of band, bounded); its
    OUTPUT SHAPE was not. It produced a 1-2 sentence prose summary, and
    offscreen events have no player-legitimate prose surface (the design's
    rule 0.2: ticks produce state; prose is authored at contact by the
    machinery already being paid for). The model now fills bounded
    attribute fields, anything sentence-shaped is refused on the write
    path, and the stored `tick` string is composed by CODE from the fields
    so it asserts exactly what they assert."""

    @staticmethod
    def _trail(monkeypatch):
        import gaps

        def _gap(cid, kind, sid, since, until, resolution=None, scene=None,
                 frame_id=None):
            return {"subject": {"kind": "character", "id": sid},
                    "moves": [], "events": [], "seed": "s",
                    "basis": "deterministic"}

        monkeypatch.setattr(gaps, "gap_for", _gap)

    def test_state_fields_land_and_no_summary_does(self, monkeypatch):
        import json as _json

        import offscreen
        import providers

        self._trail(monkeypatch)
        monkeypatch.setattr(
            providers, "chat_complete",
            lambda *a, **k: _json.dumps({"doing": "mending nets",
                                         "at": "quay_1",
                                         "manner": "unhurried"}))
        record = offscreen.profile_summary_record(
            1, {"rooms": {"quay_1": {}}},
            {"kind": "character", "id": "guinan_7f3a"}, {}, 3, 9)
        assert record["basis"] == "model"
        assert record["state"] == {"doing": "mending nets", "at": "quay_1",
                                   "manner": "unhurried"}
        assert "summary" not in record

    def test_narration_cannot_ride_an_attribute_field(self, monkeypatch):
        """A field long enough to hold a sentence will be handed one: a
        `doing` past the word bound is narration wearing a field name, and
        it falls back to the deterministic record saying exactly why."""
        import json as _json

        import offscreen
        import providers

        self._trail(monkeypatch)
        monkeypatch.setattr(
            providers, "chat_complete",
            lambda *a, **k: _json.dumps({
                "doing": "spending the evening arguing with the "
                         "quartermaster about the missing shipment",
                "at": "", "manner": ""}))
        record = offscreen.profile_summary_record(
            1, {"rooms": {}}, {"kind": "character", "id": "guinan_7f3a"},
            {}, 3, 9)
        assert record["basis"] == "deterministic"
        assert "state" not in record
        assert "state.doing" in record["inputs"]["fell_back_from"]

    def test_a_room_outside_the_world_is_refused(self, monkeypatch):
        """The same location gate every other rung has: `at` must name a
        room the world contains, or the record falls back rather than
        storing a 'quiet office'."""
        import json as _json

        import offscreen
        import providers

        self._trail(monkeypatch)
        monkeypatch.setattr(
            providers, "chat_complete",
            lambda *a, **k: _json.dumps({"doing": "reading",
                                         "at": "a quiet office",
                                         "manner": ""}))
        record = offscreen.profile_summary_record(
            1, {"rooms": {"quay_1": {}}},
            {"kind": "character", "id": "guinan_7f3a"}, {}, 3, 9)
        assert record["basis"] == "deterministic"
        assert "state.at" in record["inputs"]["fell_back_from"]

    def test_the_prompt_no_longer_asks_for_sentences(self):
        """The earliest stage the data could go wrong is the ask itself: a
        prompt requesting '1-2 sentences' gets sentences whatever the
        record shape does with them."""
        import inspect

        import offscreen

        src = inspect.getsource(offscreen.profile_summary_record)
        assert "1-2 sentences" not in src
        assert '"doing"' in src

    def test_the_tick_string_is_composed_by_code(self):
        """Deterministic composition, not model prose: the stored legacy
        `tick` asserts the fields and nothing more, so the log cannot
        smuggle a sentence past the state shape."""
        from offscreen import compose_tick

        assert compose_tick("Guinan", {"doing": "mending nets",
                                       "at": "quay_1",
                                       "manner": "unhurried"}) == \
            "Guinan — mending nets, unhurried (at quay_1)"
        assert compose_tick("Guinan", {"doing": "mending nets"}) == \
            "Guinan — mending nets"
        assert compose_tick("Guinan", {}) == \
            "Guinan — about their own business"
