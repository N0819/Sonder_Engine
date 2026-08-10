"""The living world's settings surface and the deterministic floors of
approaches B (scheduled consequence) and D (places that owe a history).

What is being prevented, per class, is named on the class — but the whole
file exists because of one measured family of failures: mechanisms assumed
live that never ran (disputes 0/181, the claims lane 0/29, a "seeded" tick
whose seed nothing consumed), and knowledge held without a route that
delivered it (chat 65: a character explaining coins he was not present to
see). The floors landed here are deterministic, and every knowledge
surface is a contact surface — these tests pin both halves.
"""

from __future__ import annotations

import json
import time

import pytest

import living_world
from living_world import (
    LIVING_WORLD_APPROACHES, LIVING_WORLD_BUILT, LIVING_WORLD_DEPTHS,
    LIVING_WORLD_DESCRIPTIONS, effective_depth, living_world_allows,
    living_world_levels, mint_consequences, normalize_living_world,
    owed_history, record_obligations,
)


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _add_place(db, chat_id, title, entry_uid):
    book_id = db.qi(
        "INSERT INTO lorebooks(name,chat_id) VALUES(?,?)",
        ("Canon", chat_id),
    )
    db.qi(
        "INSERT INTO chat_lorebooks(chat_id,lorebook_id) VALUES(?,?)",
        (chat_id, book_id),
    )
    db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,category,title,"
        "aliases,entry_uid) VALUES(?,?,?,?,?,?,?)",
        (book_id, "", "text", "location", title, "[]", entry_uid),
    )


SCENE = {"rooms": {"tavern_main": {"name": "The Brass Tankard tavern",
                                   "adjacent": []}},
         "positions": {}}


class TestTheLadder:
    """The declared/built split is the engine's own statement, not a menu's
    memory — the OFFSCREEN_LIFE_BUILT idiom, extended to five approaches."""

    def test_every_approach_is_declared_priced_and_marked(self):
        """A rung with three rich fields and one empty reads as complete
        and is not (the persona_warnings lesson): every approach must carry
        a label, both depth descriptions, and a cost, or the settings UI
        renders a feature nobody can evaluate."""
        for approach in LIVING_WORLD_APPROACHES:
            desc = LIVING_WORLD_DESCRIPTIONS[approach]
            for field in ("label", "floor", "ceiling", "cost"):
                assert str(desc.get(field) or "").strip(), (approach, field)
            assert LIVING_WORLD_BUILT[approach] <= set(LIVING_WORLD_DEPTHS)
            assert "off" not in LIVING_WORLD_BUILT[approach]

    def test_c_and_es_built_depths_stay_honest(self):
        """C exposes only a holder's witnessed surfaces and its artifact
        ceiling stays off. E's adaptive ceiling is now built — the full
        `character_agent` tick (`offscreen.schedule_agent_ticks`) — and a
        built-set that still called it unbuilt would clamp every story that
        asked for it back to the floor, silently."""
        assert LIVING_WORLD_BUILT["rumor_ledger"] == frozenset({"floor"})
        assert LIVING_WORLD_BUILT["antagonist_ladder"] == frozenset(
            {"floor", "ceiling"})

    def test_the_default_is_off_for_everything(self):
        """The engine never did any of this before the setting existed; a
        merge must not silently change a running story (the inversion of
        the reasoning that made 'stochastic' the offscreen default)."""
        assert normalize_living_world({}) == {
            a: "off" for a in LIVING_WORLD_APPROACHES}

    def test_unknown_values_fall_to_off_not_to_a_guess(self):
        cfg = normalize_living_world(
            {"routine_residue": "MAXIMUM", "telepathy": "floor",
             "scheduled_consequence": None})
        assert cfg["routine_residue"] == "off"
        assert cfg["scheduled_consequence"] == "off"
        assert "telepathy" not in cfg

    def test_an_unbuilt_ceiling_runs_as_the_floor(self):
        """The character_agent convention: setting an unbuilt tier marks
        the story as wanting it and behaves as the highest built tier
        below, so landing the ceiling later is opt-in on a chat that
        already asked rather than a surprise."""
        cfg = {"scheduled_consequence": "ceiling"}
        assert effective_depth(cfg, "scheduled_consequence") == "floor"
        assert effective_depth({"rumor_ledger": "ceiling"},
                               "rumor_ledger") == "floor"
        assert effective_depth({"antagonist_ladder": "ceiling"},
                               "antagonist_ladder") == "floor"

    def test_allows_is_ordered_and_fails_closed(self):
        cfg = {"routine_residue": "floor"}
        assert living_world_allows(cfg, "routine_residue", "floor")
        assert not living_world_allows(cfg, "routine_residue", "ceiling")
        assert not living_world_allows({}, "routine_residue", "floor")
        assert not living_world_allows(cfg, "weather_control", "floor")
        assert not living_world_allows(cfg, "routine_residue", "maximum")

    def test_levels_serve_what_is_on_what_it_costs_what_is_declared(self):
        levels = living_world_levels({"place_obligations": "ceiling"})
        by_key = {row["approach"]: row for row in levels}
        assert set(by_key) == set(LIVING_WORLD_APPROACHES)
        row = by_key["place_obligations"]
        assert row["value"] == "ceiling" and row["effective"] == "floor"
        assert row["cost"]
        built_flags = {d["value"]: d["built"] for d in row["depths"]}
        assert built_flags == {"floor": True, "ceiling": False}


class TestTheFuseMint:
    """Approach B's write path. Minting is deterministic validation of an
    adjudicated declaration; what it refuses is as load-bearing as what it
    accepts, because a stored invented location outlives the turn that
    made it (the 'quiet office' row)."""

    def test_the_cap_is_a_cap_and_says_what_it_dropped(self, temp_db):
        cid = _make_chat(temp_db)
        decls = [{"what": f"thing {i}", "where": "tavern_main",
                  "due_seconds": 7200} for i in range(4)]
        rows, warnings = mint_consequences(
            cid, SCENE, None, 11, 5, 1000.0, decls)
        assert len(rows) == 2
        assert any("cap" in w for w in warnings)

    def test_a_location_the_world_does_not_contain_is_refused(self, temp_db):
        """The quiet-office gate, applied at the earliest stage the data
        could become wrong: a fuse at an unresolvable location would fire
        into a room no ledger owns."""
        cid = _make_chat(temp_db)
        rows, warnings = mint_consequences(
            cid, SCENE, None, 11, 5, 1000.0,
            [{"what": "the office is ransacked", "where": "a quiet office",
              "due_seconds": 7200}])
        assert rows == []
        assert any("quiet office" in w for w in warnings)

    def test_dues_are_clamped_and_the_declared_value_kept(self, temp_db):
        """A consequence due in thirty seconds is this beat's business and
        one due in a year is a plot; both land at the nearest honest bound,
        visibly, rather than vanishing or being trusted."""
        cid = _make_chat(temp_db)
        rows, _ = mint_consequences(
            cid, SCENE, None, 11, 5, 1000.0,
            [{"what": "the door is repaired", "where": "tavern_main",
              "due_seconds": 30}])
        assert rows[0]["due_at"] == 1000.0 + living_world.DUE_MIN_SECONDS
        payload = json.loads(rows[0]["payload"])
        assert payload["declared_due_seconds"] == 30

    def test_the_payload_is_a_carrier_pickup_surface(self, temp_db):
        """Phase 2 moves information by carriers along routes; a rumour's
        record must be able to say who started it, where, and when, or the
        antagonist case can never be built on it. The fuse payload carries
        that surface from birth — subject, location, time, origin,
        originator, witnessed surface, and provenance tier."""
        cid = _make_chat(temp_db)
        rows, _ = mint_consequences(
            cid, SCENE, None, 11, 5, 1000.0,
            [{"what": "the patrol is doubled", "where": "tavern_main",
              "due_seconds": 7200, "witnessed": "guards seen mustering",
              "originator": "Sheriff Ito"}],
            player_room="tavern_main")
        payload = json.loads(rows[0]["payload"])
        assert payload["what"] == "the patrol is doubled"
        assert payload["where"] == "tavern_main"
        assert payload["origin"] == {"room": "tavern_main", "turn": 5,
                                     "elapsed_seconds": 1000.0}
        assert payload["witnessed"] == "guards seen mustering"
        # No cast answers to the name, so the id stays honestly empty and
        # the display rides along rather than being minted into an id.
        assert payload["originator"] == ""
        assert payload["originator_display"] == "Sheriff Ito"
        assert payload["disposition"] == "resolved_fact"
        assert payload["base_turn"] == 5

    def test_nothing_about_the_subject_buys_priority(self, temp_db):
        """The author's anti-protagonist rule: propagation priority must be
        a function of the event, never of its subject — so the fuse record
        has no priority, importance, or reputation field for anyone to
        privilege the player through."""
        cid = _make_chat(temp_db)
        rows, _ = mint_consequences(
            cid, SCENE, None, 11, 5, 1000.0,
            [{"what": "word spreads of the brawl", "where": "tavern_main",
              "due_seconds": 7200}])
        payload = json.loads(rows[0]["payload"])
        for field in ("priority", "importance", "reputation", "significance"):
            assert field not in payload, field

    def test_a_rerun_mints_the_same_ids(self, temp_db):
        cid = _make_chat(temp_db)
        args = (cid, SCENE, None, 11, 5, 1000.0,
                [{"what": "x", "where": "tavern_main", "due_seconds": 7200}])
        first, _ = mint_consequences(*args)
        second, _ = mint_consequences(*args)
        assert first[0]["event_id"] == second[0]["event_id"]

    def test_a_place_fuse_lands_on_the_entry_uid(self, temp_db):
        """Amendment 8: an ungenerated lorebook place is keyed on its lore
        entry — a fuse aimed there must resolve to that key, or the
        obligation it becomes hangs off a spelling no ledger owns."""
        cid = _make_chat(temp_db)
        _add_place(temp_db, cid, "The Sunken Library", "entry_cd34")
        rows, _ = mint_consequences(
            cid, SCENE, None, 11, 5, 1000.0,
            [{"what": "the garrison there is doubled",
              "where": "The Sunken Library", "due_seconds": 7200}])
        payload = json.loads(rows[0]["payload"])
        assert payload["where"] == "entry_cd34"
        assert payload["where_kind"] == "place"
        assert rows[0]["location_id"] == "entry_cd34"


def _fuse_row(event_id="event:aa", due_at=100.0, frame_id=None,
              where="tavern_main", what="the patrol is doubled",
              base_turn=3, where_kind="room"):
    return {"event_id": event_id, "kind": "consequence", "due_at": due_at,
            "payload": json.dumps({
                "frame_id": frame_id, "what": what, "where": where,
                "where_kind": where_kind, "base_turn": base_turn,
                "origin": {"room": "tavern_main", "turn": base_turn,
                           "elapsed_seconds": 10.0},
                "originator": "", "witnessed": "",
                "disposition": "resolved_fact"})}


class TestTheFiring:
    """Approach B's clock. Layer 1 of the author's final constraint: the
    event is REAL — it fires whether or not anyone is there — and layer 2,
    anyone LEARNING of it, happens only at contact."""

    def test_a_fuse_fires_with_nobody_there(self):
        """An event with no witness still happened. A world that only
        moves where the player is looking is a stage set, and the truth a
        later rumour distorts must exist before the rumour does."""
        from mechanics import _fire_due_events

        ops, notices, counts, _ = _fire_due_events(
            {}, 200.0, None, [_fuse_row()], turn_idx=5, player_room=None)
        assert ("status", "event:aa", "fired") in ops
        assert counts["consequences_fired"] == 1
        assert notices == []

    def test_the_notice_needs_the_player_standing_there(self):
        """The one legitimate tell-surface is walking in on it (§0.2's
        in-progress event). Anywhere else, a notice would be the engine
        narrating an offscreen event — the exact class the design kills."""
        from mechanics import _fire_due_events

        _, notices_elsewhere, _, _ = _fire_due_events(
            {}, 200.0, None, [_fuse_row()], turn_idx=5,
            player_room="somewhere_else")
        assert notices_elsewhere == []
        _, notices_here, _, _ = _fire_due_events(
            {}, 200.0, None, [_fuse_row()], turn_idx=5,
            player_room="tavern_main")
        assert len(notices_here) == 1
        assert "the patrol is doubled" in notices_here[0]

    def test_an_undue_fuse_stays_pending(self):
        from mechanics import _fire_due_events

        ops, _, counts, _ = _fire_due_events(
            {}, 50.0, None, [_fuse_row(due_at=100.0)], turn_idx=5,
            player_room=None)
        assert ops == [] and counts["consequences_fired"] == 0

    def test_another_frames_fuse_does_not_fire_on_this_clock(self):
        from mechanics import _fire_due_events

        ops, _, _, _ = _fire_due_events(
            {}, 200.0, 7, [_fuse_row(frame_id=3)], turn_idx=5,
            player_room=None)
        assert ops == []

    def test_the_base_revision_check_cancels_an_orphaned_fuse(self):
        """The consequence that ignored the week: a fuse whose minting turn
        the story no longer contains describes a future whose cause
        un-happened. Cancelled loudly at fire time — the
        land_profile_ticks discipline, applied to the delay line."""
        from mechanics import _fire_due_events

        ops, notices, counts, _ = _fire_due_events(
            {}, 200.0, None, [_fuse_row(base_turn=9)], turn_idx=5,
            player_room="tavern_main")
        assert ("status", "event:aa", "cancelled") in ops
        assert counts["consequences_fired"] == 0
        assert notices == []


class TestTheObligationLedger:
    """Approach D's floor. The single most important structural property,
    per the author's final constraint: a place's history is REAL
    accumulated state, existing before anyone asks — if it were minted at
    arrival, a rumour about the place would have nothing to be a
    distortion of, and arrival could never contradict the rumour."""

    def test_obligations_accumulate_before_anyone_arrives(self, temp_db):
        from db import wget

        cid = _make_chat(temp_db)
        record_obligations(cid, [_fuse_row(where="entry_cd34",
                                           where_kind="place",
                                           due_at=500.0)])
        ledger = wget(cid, living_world.OBLIGATION_KEY, {})
        assert "entry_cd34" in ledger
        row = ledger["entry_cd34"][0]
        assert row["what"] == "the patrol is doubled"
        assert row["elapsed_seconds"] == 500.0
        assert row["disposition"] == "resolved_fact"
        # Carrier pickup surface, preserved through the fold (phase 2).
        assert row["origin"]["room"] == "tavern_main"

    def test_a_rerun_folds_instead_of_stacking(self, temp_db):
        from db import wget

        cid = _make_chat(temp_db)
        row = _fuse_row(where="entry_cd34", where_kind="place")
        record_obligations(cid, [row])
        record_obligations(cid, [row])
        assert len(wget(cid, living_world.OBLIGATION_KEY, {})["entry_cd34"]) == 1

    def test_a_room_fuse_is_not_an_obligation(self, temp_db):
        """Rooms deliver their history through re-entry residue; only the
        ungenerated (amendment 8's `place`) bank against the lore entry.
        Both at once would honour the same event twice at arrival."""
        from db import wget

        cid = _make_chat(temp_db)
        record_obligations(cid, [_fuse_row()])
        assert wget(cid, living_world.OBLIGATION_KEY, {}) == {}

    def test_the_store_cap_forgets_oldest_first(self, temp_db):
        cid = _make_chat(temp_db)
        for i in range(living_world.OBLIGATION_STORE_CAP + 3):
            record_obligations(cid, [_fuse_row(
                event_id=f"event:{i:02d}", what=f"happening {i}",
                where="entry_cd34", where_kind="place", due_at=float(i))])
        owed = owed_history(cid, "entry_cd34",
                            cap=living_world.OBLIGATION_STORE_CAP + 3)
        assert len(owed) == living_world.OBLIGATION_STORE_CAP
        assert owed[0]["what"].endswith(
            str(living_world.OBLIGATION_STORE_CAP + 2))

    def test_owed_history_is_capped_and_recent_first(self, temp_db):
        """The room that recites its homework: generation under fourteen
        obligations reads like a briefing. The honour cap ranks by recency
        and lets the rest silently expire as things that turned out not to
        matter."""
        cid = _make_chat(temp_db)
        for i in range(6):
            record_obligations(cid, [_fuse_row(
                event_id=f"event:h{i}", what=f"happening {i}",
                where="entry_cd34", where_kind="place", due_at=float(i))])
        owed = owed_history(cid, "entry_cd34")
        assert len(owed) == living_world.OBLIGATION_HONOR_CAP
        assert owed[0]["what"] == "happening 5"


class TestArrivalIsTheEarningEvent:
    """Approach D's epistemic boundary. A place's accumulated history is
    true, and truth is not a channel (chat 65's Kadoman explained coins he
    was not present to see): no mind may hold an obligation merely because
    it is real. The ledger's one consumer is the mapping seam, where the
    place itself is generated."""

    def test_no_mind_reads_the_ledger(self):
        """Structural, not instructed: the modules that assemble any
        character's, director's, perceiver's, or narrator's view must not
        name the obligation ledger. The mapping stage — where a place
        becomes rooms — is the single legitimate reader."""
        import pathlib

        agents_dir = pathlib.Path(__file__).resolve().parent.parent / "agents"
        for module in ("character.py", "director.py", "perception.py",
                       "narration.py", "background.py", "loops.py"):
            src = (agents_dir / module).read_text(encoding="utf-8")
            assert "place_obligations" not in src, module
            assert "owed_history" not in src, module
        mapping_src = (agents_dir / "mapping.py").read_text(encoding="utf-8")
        assert "owed_history" in mapping_src

    def test_the_surface_is_gated_by_the_setting(self, temp_db):
        """Truth accumulates regardless (record_obligations is ungated);
        the SURFACE is what the setting owns. Off means the mapping payload
        carries no debt, not that the debt stopped existing."""
        from living_world import attach_owed_history

        cid = _make_chat(temp_db)
        record_obligations(cid, [_fuse_row(where="entry_cd34",
                                           where_kind="place")])
        hits = [{"entry_uid": "entry_cd34", "category": "location",
                 "content": "x"}]
        off = attach_owed_history(cid, hits, config={})
        assert "owed_history" not in off[0]
        on = attach_owed_history(
            cid, hits, config={"place_obligations": "floor"})
        assert on[0]["owed_history"][0]["what"] == "the patrol is doubled"

    def test_a_place_without_debt_is_not_annotated(self, temp_db):
        from living_world import attach_owed_history

        cid = _make_chat(temp_db)
        hits = [{"entry_uid": "entry_zz99", "category": "location"},
                {"entry_uid": "entry_ff11", "category": "faction"}]
        out = attach_owed_history(
            cid, hits, config={"place_obligations": "floor"})
        assert all("owed_history" not in h for h in out)


class TestTheRoute:
    """The settings must be reachable: background_config shipped with no
    route once, and scene_life was only settable by hand-editing world KV
    in both live demo runs."""

    @pytest.fixture
    def client(self, temp_db):
        import guest_access as guest
        from fastapi.testclient import TestClient

        import app as app_module

        guest.reset_host_account()
        with TestClient(app_module.app) as c:
            r = c.post("/api/auth/setup",
                       json={"username": "host", "password": "pw12345"})
            assert r.status_code == 200, r.text
            yield c
        guest.reset_host_account()

    @pytest.fixture
    def chat_id(self, temp_db):
        return _make_chat(temp_db)

    def test_get_serves_the_ladder_with_built_flags(self, client, chat_id):
        out = client.get(f"/api/chats/{chat_id}/living_world").json()
        assert out["living_world"] == {
            a: "off" for a in LIVING_WORLD_APPROACHES}
        by_key = {row["approach"]: row for row in out["approaches"]}
        assert by_key["rumor_ledger"]["depths"][0]["built"] is True
        assert by_key["routine_residue"]["depths"][0]["built"] is True
        assert by_key["routine_residue"]["cost"]

    def test_put_normalizes_and_returns_what_stuck(self, client, chat_id):
        out = client.put(
            f"/api/chats/{chat_id}/living_world",
            json={"living_world": {"routine_residue": "floor",
                                   "rumor_ledger": "warp speed"}}).json()
        assert out["living_world"]["routine_residue"] == "floor"
        assert out["living_world"]["rumor_ledger"] == "off"
        again = client.get(f"/api/chats/{chat_id}/living_world").json()
        assert again["living_world"]["routine_residue"] == "floor"


class TestOneAuthorityCeiling:
    """scene.py's off-screen ladder and this module's mechanisms were two
    dropdowns on one question, composed nowhere: a user could set approach
    E to ceiling under a ladder at `deterministic` and nothing said which
    governed — and B's built floor minted fuses that genuinely fired while
    the ladder said `inert`, "nothing happens off screen". The ladder is
    now the single authority ceiling (``LIVING_WORLD_REQUIRES``), composed
    at read time; these tests pin the rule, the fold, the purity of the
    stored config, and the merged settings surface."""

    def test_the_ceiling_caps_what_a_mechanism_may_run(self):
        """What broke: ``living_world_allows`` answered from its own axis
        only, so a story at `inert` still minted scheduled consequences —
        off-screen work with real authority under a setting that promised
        none. The effective depth must honour the ceiling, falling the
        same visible way an unbuilt tier falls, never silently running."""
        cfg = {"scheduled_consequence": "floor", "offscreen_life": "inert"}
        assert effective_depth(cfg, "scheduled_consequence") == "off"
        assert not living_world_allows(cfg, "scheduled_consequence", "floor")
        cfg["offscreen_life"] = "deterministic"
        assert effective_depth(cfg, "scheduled_consequence") == "floor"
        assert living_world_allows(cfg, "scheduled_consequence", "floor")

    def test_a_config_without_a_ceiling_reads_as_the_ladder_default(self):
        """No running story may change behaviour on merge: every stored
        ceiling in the live database was absent or `stochastic` (the
        ladder default), and one live chat plays with the A, B and D
        floors on at that default — so an absent ceiling must read as the
        default, under which every built floor and every
        unbuilt-ceiling-as-floor runs exactly as before composition
        existed. And every depth of every approach must name a real rung,
        or a mechanism would be ungoverned the moment it is built."""
        import scene
        from living_world import LIVING_WORLD_REQUIRES

        for approach in ("routine_residue", "scheduled_consequence",
                         "place_obligations"):
            assert effective_depth({approach: "floor"}, approach) == "floor"
            assert effective_depth({approach: "ceiling"}, approach) == "floor"
        assert set(LIVING_WORLD_REQUIRES) == set(LIVING_WORLD_APPROACHES)
        for approach, depths in LIVING_WORLD_REQUIRES.items():
            assert set(depths) == {"floor", "ceiling"}
            for rung in depths.values():
                assert rung in scene.OFFSCREEN_LIFE_LADDER

    def test_e_uses_the_two_plan_rungs_by_name(self):
        """The design doc names E's rungs `reactive` and `character_agent`
        outright — E is that rung wearing the mechanism vocabulary. Gating
        it lower would let a plan advance under a ladder that never
        granted plans; and the DEFAULT ladder level must not include it,
        so E landing built stays opt-in twice: the mechanism switched on,
        the ceiling deliberately raised."""
        from scene import OFFSCREEN_LIFE_DEFAULT, offscreen_life_allows
        from living_world import LIVING_WORLD_REQUIRES

        assert LIVING_WORLD_REQUIRES["antagonist_ladder"] == {
            "floor": "reactive", "ceiling": "character_agent"}
        assert offscreen_life_allows(OFFSCREEN_LIFE_DEFAULT, "reactive")
        assert not offscreen_life_allows(OFFSCREEN_LIFE_DEFAULT,
                                         "character_agent")

    def test_the_ceiling_folds_in_on_the_way_in(self, temp_db):
        """A composition helper every gate must remember to call would be
        forgotten (the canonical_url rule): the config the gates already
        fetch must carry the chat's own ceiling, so commit's mint gate and
        the Director's residue gate compose both axes without changing."""
        from living_world import living_world_config

        cid = _make_chat(temp_db)
        temp_db.wset(cid, "living_world", {"scheduled_consequence": "floor"})
        temp_db.wset(cid, "dialogue_config", {"offscreen_life": "inert"})
        cfg = living_world_config(cid)
        assert cfg["offscreen_life"] == "inert"
        assert not living_world_allows(cfg, "scheduled_consequence", "floor")
        temp_db.wset(cid, "dialogue_config",
                     {"offscreen_life": "stochastic"})
        assert living_world_allows(living_world_config(cid),
                                   "scheduled_consequence", "floor")

    def test_the_stored_config_never_gains_the_ceiling(self, temp_db):
        """Two durable spellings of one ceiling is the five-defect
        identity failure waiting: a stale copy under the living_world key
        would shadow the live dialogue_config. The write path must strip
        it however it arrives."""
        import app
        from living_world import OFFSCREEN_CEILING_KEY

        cid = _make_chat(temp_db)
        app.living_world_put(cid, {"living_world": {
            "scheduled_consequence": "floor",
            OFFSCREEN_CEILING_KEY: "inert"}})
        stored = temp_db.wget(cid, "living_world", {})
        assert OFFSCREEN_CEILING_KEY not in stored
        assert stored["scheduled_consequence"] == "floor"

    def test_levels_name_the_clamp_they_will_apply(self):
        """A mechanism set above the ceiling must display as clamped, not
        silently ignored: the payload carries each depth's required rung
        and whether the current ceiling permits it, so the menu renders
        the engine's clamp rather than a copy that drifts."""
        levels = living_world_levels({"scheduled_consequence": "ceiling",
                                      "offscreen_life": "deterministic"})
        row = {r["approach"]: r for r in levels}["scheduled_consequence"]
        assert row["effective"] == "floor"
        depths = {d["value"]: d for d in row["depths"]}
        assert depths["floor"]["requires"] == "deterministic"
        assert depths["floor"]["permitted"] is True
        assert depths["ceiling"]["requires"] == "stochastic"
        assert depths["ceiling"]["permitted"] is False
        levels = living_world_levels({"scheduled_consequence": "floor",
                                      "offscreen_life": "inert"})
        row = {r["approach"]: r for r in levels}["scheduled_consequence"]
        assert row["effective"] == "off"
        assert all(not d["permitted"] for d in row["depths"])

    def test_the_ui_is_one_card_with_the_ceiling_first(self):
        """Two cards carried the two axes with the composition left to the
        reader. One card now shows the ceiling once, first, and each
        mechanism's clamp live (the ``requires`` rung mirrored
        client-side), so a depth past the ceiling reads as capped the
        moment either dropdown moves."""
        from pathlib import Path

        js = (Path(__file__).resolve().parents[1]
              / "static/js/settings.js").read_text(encoding="utf-8")
        assert '"World simulation"' in js
        assert '"Living world"' not in js  # the second card is gone
        block = js[js.index('"World simulation"'):
                   js.index('"Background life"')]
        assert block.index("offLife") < block.index("lwRows")
        assert "d.requires" in js and "refreshLw" in js
