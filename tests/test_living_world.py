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

from world import living_world
from world.living_world import (
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
        from world.mechanics import _fire_due_events

        ops, notices, counts, _ = _fire_due_events(
            {}, 200.0, None, [_fuse_row()], turn_idx=5, player_room=None)
        assert ("status", "event:aa", "fired") in ops
        assert counts["consequences_fired"] == 1
        assert notices == []

    def test_the_notice_needs_the_player_standing_there(self):
        """The one legitimate tell-surface is walking in on it (§0.2's
        in-progress event). Anywhere else, a notice would be the engine
        narrating an offscreen event — the exact class the design kills."""
        from world.mechanics import _fire_due_events

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
        from world.mechanics import _fire_due_events

        ops, _, counts, _ = _fire_due_events(
            {}, 50.0, None, [_fuse_row(due_at=100.0)], turn_idx=5,
            player_room=None)
        assert ops == [] and counts["consequences_fired"] == 0

    def test_another_frames_fuse_does_not_fire_on_this_clock(self):
        from world.mechanics import _fire_due_events

        ops, _, _, _ = _fire_due_events(
            {}, 200.0, 7, [_fuse_row(frame_id=3)], turn_idx=5,
            player_room=None)
        assert ops == []

    def test_the_base_revision_check_cancels_an_orphaned_fuse(self):
        """The consequence that ignored the week: a fuse whose minting turn
        the story no longer contains describes a future whose cause
        un-happened. Cancelled loudly at fire time — the
        land_profile_ticks discipline, applied to the delay line."""
        from world.mechanics import _fire_due_events

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
        from core.db import wget

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
        from core.db import wget

        cid = _make_chat(temp_db)
        row = _fuse_row(where="entry_cd34", where_kind="place")
        record_obligations(cid, [row])
        record_obligations(cid, [row])
        assert len(wget(cid, living_world.OBLIGATION_KEY, {})["entry_cd34"]) == 1

    def test_a_room_fuse_is_not_an_obligation(self, temp_db):
        """Rooms deliver their history through re-entry residue; only the
        ungenerated (amendment 8's `place`) bank against the lore entry.
        Both at once would honour the same event twice at arrival."""
        from core.db import wget

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
        """Structural, not instructed: no module that assembles any
        character's, director's, perceiver's or narrator's view may name the
        obligation ledger. The mapping stage — where a place becomes rooms —
        is the single legitimate reader.

        Enumerated from the package rather than hand-listed. The six names
        this replaces were the payload assemblers `agents/` had when the rule
        was written; the package has since grown `director_views.py`,
        `director_fanout.py`, `composer.py` and the rest, and a leak into any
        of them was invisible to a list nobody was going to remember to
        extend. Every file except the allowed reader is now checked, so a new
        assembler is covered on the day it lands."""
        import pathlib

        agents_dir = pathlib.Path(__file__).resolve().parent.parent / "agents"
        allowed = {"mapping.py"}
        checked = 0
        for path in sorted(agents_dir.rglob("*.py")):
            if path.name in allowed:
                continue
            src = path.read_text(encoding="utf-8")
            assert "place_obligations" not in src, path
            assert "owed_history" not in src, path
            checked += 1
        assert checked > 6, "the package enumeration found nothing to check"
        mapping_src = (agents_dir / "mapping.py").read_text(encoding="utf-8")
        assert "owed_history" in mapping_src

    def test_the_surface_is_no_longer_a_setting(self, temp_db):
        """Truth always accumulated (`record_obligations` is ungated) and the
        SURFACE used to be a switch. It is not one any more (2026-09-20): a
        place you have never been owes what happened there whether or not a menu
        says so, and the switch only ever decided whether anybody was told --
        the same shape of thing the `scheduled_consequence` surface gate was.
        So the debt is annotated whatever the config says, including none."""
        from world.living_world import attach_owed_history

        cid = _make_chat(temp_db)
        record_obligations(cid, [_fuse_row(where="entry_cd34",
                                           where_kind="place")])
        hits = [{"entry_uid": "entry_cd34", "category": "location",
                 "content": "x"}]
        for config in ({}, None, {"place_obligations": "off"}):
            out = attach_owed_history(cid, hits, config=config)
            assert out[0]["owed_history"][0]["what"] == "the patrol is doubled", \
                config

    def test_a_place_without_debt_is_not_annotated(self, temp_db):
        from world.living_world import attach_owed_history

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
        from web import guest_access as guest
        from fastapi.testclient import TestClient

        from web import app as app_module

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

    def test_the_route_survives_an_empty_ladder(self, client, chat_id):
        """The ladder has no approaches left (2026-09-20): Charter, the Writers'
        Room and causality bubbles superseded the whole of it. The ROUTE stays,
        because an extension may still call it and must get a shape rather than
        a 500 -- it now serves nothing to set."""
        out = client.get(f"/api/chats/{chat_id}/living_world").json()
        assert out["living_world"] == {}
        assert out["approaches"] == []

    def test_a_put_of_a_retired_approach_sticks_to_nothing(self, client,
                                                          chat_id):
        """A story configured before the retirement, or an extension still
        publishing against the old contract, is answered rather than obeyed:
        the name is dropped and nothing is stored under it, so no retired rung
        can come back and gate a mechanism that is now unconditional."""
        out = client.put(
            f"/api/chats/{chat_id}/living_world",
            json={"living_world": {"routine_residue": "floor",
                                   "antagonist_ladder": "ceiling",
                                   "rumor_ledger": "warp speed"}}).json()
        assert out["living_world"] == {}
        again = client.get(f"/api/chats/{chat_id}/living_world").json()
        assert again["living_world"] == {}

# TestTheLadder and TestOneAuthorityCeiling were removed on 2026-09-20 with the
# thing they pinned. The four-approach ladder and the off-screen cognition
# CEILING over it are retired: `routine_residue` and `scheduled_consequence`
# are unconditional (a world whose fires do not burn down and whose causes do
# not land is not coherent at any setting -- the argument that retired rumour
# transport before them), `place_obligations` had no live reader at all, and the
# cognition ladder is superseded by Charter and the Writers' Room
# (`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md`). What a story now says about
# how much runs beside it is `max_bubbles`
# (`tests/test_a_story_says_how_many_threads_it_carries.py`).
#
# `antagonist_ladder` KEPT its rung and its coverage below: retiring it was
# tried the same day and measured -- reactive plans fire off plans it authors,
# so cutting it silently ended the race-you-can-lose mechanism, which is what
# §4.3 of that doc warned about.
