"""The gap generator answers in ids, degrades honestly, and gets read.

Every property here is pinned against a defect already on the record:
`background_presences` keyed 'A Dalek' / 'Dalek' / 'The Dalek' as three
beings (ids, not display names); the one `offscreen_log` row ever written
put its actor in "a quiet office", a room the scene graph does not contain
(node ids, never prose); and the abort path once made a crash and a closed
tab indistinguishable (a gap that cannot be produced says why, never
nothing). The reader tests exist because `offscreen_log` was written for
months and read by nothing -- a generator without a consumer is exactly the
built-and-never-fired class the fire-rate work keeps finding.
"""

from __future__ import annotations

import inspect
import json
import time

import pytest

import gaps
from gaps import LAST_SEEN_KEY, gap_for, interim_for, last_seen_update


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _attach_character(db, chat_id, name, uid=None, tier=None):
    sheet = {"identity": {"name": name}}
    if uid:
        sheet["identity"]["uid"] = uid
    if tier:
        sheet["simulation"] = {"tier": tier}
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
        (name, json.dumps(sheet), time.time()),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
        (chat_id, char_id),
    )
    return char_id


SID = "elyndra_succubus"


def _scene(room="hall"):
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []},
                  "garden": {"name": "Garden", "adjacent": []}},
        "entities": {},
        "positions": {"Elyndra": room},
    }


def _seen(db, cid, sid=SID, turn=2, room="garden", seconds=100.0):
    db.wset(cid, LAST_SEEN_KEY,
            {sid: {"turn": turn, "room": room, "elapsed_seconds": seconds}})


def _no_model(monkeypatch):
    def _refuse(*a, **k):
        raise AssertionError("the low rung made a model call")
    monkeypatch.setattr(gaps, "chat_complete", _refuse)


class TestSubjectIdentityOnTheRecord:
    def test_a_display_name_in_is_an_id_on_the_record(self, temp_db, monkeypatch):
        """`offscreen_log` keys actors by display name and that is the live
        Guinan defect: name-keyed rows break on rename and join to nothing."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        rec = gap_for(cid, "character", "Elyndra", 1, 5, scene=_scene())
        assert rec["subject"]["id"] == SID
        assert rec["subject"]["display"] == "Elyndra"

    def test_a_spelling_no_ledger_owns_is_unavailable_with_the_reason(
            self, temp_db, monkeypatch):
        """Property 3. Silence is how add_lore ran without a model stamp for
        months; the resolver's own reason must ride the record."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        rec = gap_for(cid, "character", "Nobody", 1, 5, scene={})
        assert rec["basis"] == "unavailable"
        assert rec["reason"]

    def test_an_empty_window_is_refused_not_answered(self, temp_db, monkeypatch):
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        rec = gap_for(cid, "character", SID, 5, 5, scene=_scene())
        assert rec["basis"] == "unavailable"
        assert "empty window" in rec["reason"]


class TestTheDeterministicSkeleton:
    def test_the_move_is_the_endpoint_delta_in_node_ids(self, temp_db, monkeypatch):
        """No ledger records positions per turn, so the honest claim is one
        move -- was there at since, is here by until -- in room ids."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene(room="hall"))
        assert rec["moves"] == [{"turn": 6, "from_room": "garden",
                                 "to_room": "hall", "basis": "deterministic"}]

    def test_staying_put_asserts_no_move(self, temp_db, monkeypatch):
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid, room="hall")
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene(room="hall"))
        assert rec["moves"] == []

    def test_a_prose_room_in_the_ledger_is_dropped_and_said(
            self, temp_db, monkeypatch):
        """Property 2: 'a quiet office' is the row this refuses to repeat.
        A stored defect re-emitted is a defect with a second life."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid, room="a quiet office")
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene(room="hall"))
        assert rec["moves"] == []
        assert any("a quiet office" in n for n in rec["inputs"]["notes"])

    def test_a_fired_scheduled_event_arrives_with_its_real_id(
            self, temp_db, monkeypatch):
        """The proposal's shape says {turn, event_id, summary}; nothing ever
        writes `world_events`, so `scheduled_events` is the one ledger with
        real ids and they must be carried, not re-minted."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        temp_db.wset(cid, "simulation_clock",
                     {"elapsed_seconds": 500.0, "display": "later"})
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            ("ev_market_close", cid, 300.0, "transit_arrival", "hall",
             "{}", "s", "fired"),
        )
        temp_db.wset(cid, LAST_SEEN_KEY,
                     {"hall": {"turn": 2, "room": "hall",
                               "elapsed_seconds": 100.0}})
        rec = gap_for(cid, "room", "hall", 2, 6, scene=_scene())
        assert [e["event_id"] for e in rec["events"]] == ["ev_market_close"]

    def test_without_a_clock_anchor_the_clock_ledger_is_skipped_and_said(
            self, temp_db, monkeypatch):
        """`scheduled_events` fires on seconds, the window is turns, and only
        the last-seen stamp joins them. Guessing the join would window events
        into the wrong absence; skipping silently would look like an empty
        world. So: skip, and say so."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid, turn=2)
        rec = gap_for(cid, "character", SID, 3, 6, scene=_scene())
        assert any("no clock" in n for n in rec["inputs"]["notes"])

    def test_offscreen_ticks_in_the_window_surface_with_their_turn(
            self, temp_db, monkeypatch):
        """`offscreen_log` is written at commit.py:4241 and read by nothing
        -- the mechanism ran once in a whole live corpus and its one row was
        invisible. The gap is its first reader."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        # Seeded-rung shape: `basis`/`disposition` prove provenance -- a row
        # without them is the old omniscient rung's prose and (since the
        # boundary audit) may not deliver; tests/test_gap_boundaries.py owns
        # that gate.
        temp_db.wset(cid, "offscreen_log", [
            {"turn": 4, "seed": "s", "events": [
                {"actor": "Elyndra", "tick": "kept to the archives",
                 "basis": "deterministic", "disposition": "provisional"}]},
            {"turn": 9, "seed": "s", "events": [
                {"actor": "Elyndra", "tick": "outside the window",
                 "basis": "deterministic", "disposition": "provisional"}]},
        ])
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        ticks = [e for e in rec["events"] if e["event_id"] is None]
        assert [e["turn"] for e in ticks] == [4]
        assert "archives" in ticks[0]["summary"]

    def test_the_low_rung_never_pays_for_a_model(self, temp_db, monkeypatch):
        """Section 1.2: low is assembled from state the engine already has
        with NO model call -- the difference between free for the whole cast
        and affordable for six of them."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert rec["basis"] == "deterministic"

    def test_the_record_is_reproducible(self, temp_db, monkeypatch):
        """Seeded and logged, so a reroll re-derives the same gap instead of
        quietly producing a second history."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        first = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        second = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert first == second
        assert first["seed"] == f"gap:{cid}:character:{SID}:2:6"

    def test_no_rung_built_here_may_emit_a_consequence(self, temp_db, monkeypatch):
        """Section 1.0.1's line: a rung that cannot express a consequence
        cannot smuggle one. `deltas` stays empty below the full agent."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert rec["deltas"] == {}


class TestResolutionIsDerivedNotObeyed:
    def test_a_caller_cannot_buy_the_expensive_tier_for_a_minor_subject(
            self, temp_db, monkeypatch):
        """'A caller that can pick the expensive tier is a caller that will'
        -- section 1.2's exact words. `resolution` may lower, never raise."""
        _no_model(monkeypatch)  # raises if medium runs
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID, tier="bg")
        _seen(temp_db, cid)
        rec = gap_for(cid, "character", SID, 2, 6,
                      resolution="medium", scene=_scene())
        assert rec["resolution"] == "low"

    def test_a_major_subject_derives_medium_and_low_caps_it(
            self, temp_db, monkeypatch):
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID, tier="major")
        _seen(temp_db, cid)
        rec = gap_for(cid, "character", SID, 2, 6,
                      resolution="low", scene=_scene())
        assert rec["resolution"] == "low"
        assert rec["basis"] == "deterministic"


class TestTheMediumRung:
    def _major(self, db, cid):
        _attach_character(db, cid, "Elyndra", uid=SID, tier="major")
        _seen(db, cid)

    def test_a_failed_call_falls_to_the_rung_below_and_says_so(
            self, temp_db, monkeypatch):
        """Section 1.0.3: reject and regenerate once, then fall back -- a
        deterministic 'she was elsewhere' over a plausible lie. And the
        record must SAY it fell, or a dead model reads as a quiet world."""
        cid = _make_chat(temp_db)
        self._major(temp_db, cid)

        def _down(*a, **k):
            raise RuntimeError("no provider configured")
        monkeypatch.setattr(gaps, "chat_complete", _down)
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert rec["basis"] == "deterministic"
        assert rec["resolution"] == "low"
        assert "fell_back_from" in rec["inputs"]

    def test_an_invented_room_is_refused_both_times_then_fallen_back(
            self, temp_db, monkeypatch):
        """The location gate at this rung's write path: one tick, one
        invented location is the measured history of the whole offscreen
        mechanism, and it must be structurally impossible here."""
        cid = _make_chat(temp_db)
        self._major(temp_db, cid)
        calls = []

        def _liar(*a, **k):
            calls.append(1)
            return json.dumps({"summary": "She slipped away.",
                               "rooms": ["a_quiet_office"]})
        monkeypatch.setattr(gaps, "chat_complete", _liar)
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert len(calls) == 2
        assert rec["basis"] == "deterministic"
        assert "outside the world" in rec["inputs"]["fell_back_from"]

    def test_a_clean_summary_lands_as_model_basis_over_the_skeleton(
            self, temp_db, monkeypatch):
        cid = _make_chat(temp_db)
        self._major(temp_db, cid)

        def _fine(*a, **k):
            return json.dumps({"summary": "She kept to the garden, then "
                               "crossed to the hall.", "rooms": ["garden", "hall"]})
        monkeypatch.setattr(gaps, "chat_complete", _fine)
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert rec["basis"] == "model"
        assert rec["resolution"] == "medium"
        assert rec["moves"], "the deterministic trail must survive the overlay"


class TestTheLastSeenLedger:
    def test_sightings_are_keyed_by_id_never_by_the_positions_spelling(self):
        """The five name-keyed ledgers are one defect; this is the first
        ledger born in id space, and the positions key (a display name, by
        the cast convention) must not leak in as the key."""
        cast = [{"id": 7, "sheet": json.dumps(
            {"identity": {"name": "Elyndra", "uid": SID}})}]
        sc = _scene(room="hall")
        sc["positions"]["Player"] = "hall"
        out = last_seen_update(sc, cast, "Player", 6, 42.0)
        assert SID in out and "Elyndra" not in out
        assert out[SID] == {"turn": 6, "room": "hall", "elapsed_seconds": 42.0}

    def test_the_player_is_not_a_subject_of_their_own_absence(self):
        sc = _scene(room="hall")
        sc["positions"]["Player"] = "hall"
        out = last_seen_update(sc, [], "Player", 6, 0.0)
        assert not any(k.casefold() == "player" for k in out)

    def test_a_name_keyed_presence_is_skipped_not_minted_for(self):
        """An unregistered presence has no id in any ledger; stamping one
        here would mint the second spelling 0c exists to refuse."""
        sc = _scene(room="hall")
        sc["positions"]["Player"] = "hall"
        sc["positions"]["Mot the Barber"] = "hall"
        out = last_seen_update(sc, [], "Player", 6, 0.0)
        assert not any("mot" in k.casefold() for k in out)

    def test_the_room_itself_is_stamped(self):
        """A room has no position row, so without its own stamp a room
        subject could never anchor the clock and 'the market closed' -- the
        gap rooms tell best -- would always skip the clock ledger."""
        sc = _scene(room="hall")
        sc["positions"]["Player"] = "hall"
        out = last_seen_update(sc, [], "Player", 6, 42.0)
        assert out["hall"]["turn"] == 6

    def test_a_subject_elsewhere_is_not_stamped(self):
        cast = [{"id": 7, "sheet": json.dumps(
            {"identity": {"name": "Elyndra", "uid": SID}})}]
        sc = _scene(room="garden")
        sc["positions"]["Player"] = "hall"
        out = last_seen_update(sc, cast, "Player", 6, 0.0)
        assert SID not in out


class TestTheReader:
    def test_contact_after_an_absence_yields_the_gap(self, temp_db, monkeypatch):
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid, turn=2, room="garden")
        rec = interim_for(cid, _scene(room="hall"), "character", SID, 6)
        assert rec and rec["moves"]

    def test_a_subject_never_recorded_gets_no_interval_not_the_whole_story(
            self, temp_db, monkeypatch):
        """With no since-turn, the only window is 'since turn zero', which
        would dump the entire story on first contact. The ledger records
        forward from its first commit; before that, no gap."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        assert interim_for(cid, _scene(), "character", SID, 6) is None

    def test_a_subject_seen_last_beat_has_no_gap(self, temp_db, monkeypatch):
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid, turn=5, room="hall")
        assert interim_for(cid, _scene(room="hall"), "character", SID, 6) is None

    def test_an_empty_gap_is_not_injected(self, temp_db, monkeypatch):
        """A payload key saying 'nothing happened' is noise wearing tokens;
        the character payload is a budget, not a log."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid, turn=2, room="hall")
        assert interim_for(cid, _scene(room="hall"), "character", SID, 6) is None

    def test_the_reader_asks_for_the_free_rung(self, temp_db, monkeypatch):
        """The reader runs ON the turn path; section 1.0.2 puts model-priced
        rungs out of band. A major character must not cost a call here."""
        _no_model(monkeypatch)  # raises if any model call happens
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID, tier="major")
        _seen(temp_db, cid, turn=2, room="garden")
        rec = interim_for(cid, _scene(room="hall"), "character", SID, 6)
        assert rec and rec["resolution"] == "low"

    def test_character_step_wires_the_gap_into_its_own_payload(self):
        """The generator is worthless until something surfaces it --
        `offscreen_log` proved that for months. The character payload is the
        cheapest useful consumer, and strictly for the mind's OWN gap: a gap
        about somebody else handed to a mind is a perception bypass."""
        import agents.character as character
        src = inspect.getsource(character.character_step)
        assert "interim_for(" in src
        assert "while_you_were_offscreen" in src
        assert 'cast_entity_id(sh, row["id"])' in src


class TestTheCommitRecorder:
    def test_commit_scene_records_sightings_inside_the_scene_domain(self):
        """`last_seen` is the one new piece of state the bottom rung needs
        (section 1.2 step 2), and a recorder nothing calls is the
        built-and-never-fired class. It must run where the final merged
        scene exists: commit_scene."""
        import commit
        src = inspect.getsource(commit.commit_scene)
        assert "_record_subject_last_seen" in src

    def test_the_recorder_merges_rather_than_replaces(self, temp_db):
        """A subject away this beat must keep their older stamp -- replacing
        the ledger each turn would erase exactly the absences the gap
        generator exists to describe."""
        import types

        import commit
        cid = _make_chat(temp_db)
        temp_db.wset(cid, LAST_SEEN_KEY,
                     {"away_one": {"turn": 1, "room": "garden",
                                   "elapsed_seconds": 5.0}})
        sc = _scene(room="hall")
        sc["positions"]["The Stranger"] = "hall"
        cast = [{"id": 7, "sheet": json.dumps(
            {"identity": {"name": "Elyndra", "uid": SID}})}]
        ctx = types.SimpleNamespace(
            chat={"id": cid, "persona_id": None},
            cast=cast,
            turn=types.SimpleNamespace(idx=6),
            add_warning=lambda *_: pytest.fail("recorder warned"),
        )
        # ctx.chat needs .id attribute access too, matching commit's usage.
        class _Chat(dict):
            @property
            def id(self):
                return self["id"]
        ctx.chat = _Chat(ctx.chat)
        commit._record_subject_last_seen(ctx, sc, {"elapsed_seconds": 9.0})
        ledger = temp_db.wget(cid, LAST_SEEN_KEY, {})
        assert ledger["away_one"]["turn"] == 1
        assert ledger[SID]["turn"] == 6
