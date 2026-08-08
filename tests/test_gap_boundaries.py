"""The gap is a payload channel, and a channel is gated or it is a leak.

`while_you_were_offscreen` hands a mind prose somebody else wrote -- the old
model-driven offscreen rung, the omniscient mapping model, another room's
scheduled event, another frame's ledger. The audit found four seams where
that prose crossed with no gate at all; each test here pins one shut. The
rule is AGENTS.md's: a mind may know anything it has a channel to; what it
may not do is acquire a fact that reached it through no channel.
"""

from __future__ import annotations

import inspect
import json
import time

import gaps
from gaps import LAST_SEEN_KEY, gap_for


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _attach_character(db, chat_id, name, uid=None):
    sheet = {"identity": {"name": name}}
    if uid:
        sheet["identity"]["uid"] = uid
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


class TestOffscreenLogProvenance:
    def test_a_legacy_omniscient_row_does_not_deliver_its_prose(
            self, temp_db, monkeypatch):
        """Chat 9's ledger holds rows the OLD model-driven rung wrote --
        "unaware of the Kalvoss cruiser's arrival", a fact ABOUT the
        subject's ignorance, phrased with knowledge the subject lacks. A
        tick that cannot prove its provenance (no basis/disposition: the
        pre-seeded-rung writer) delivered that prose into the subject's own
        gap on next contact. Provenance-less prose must be dropped, said,
        and never delivered; a seeded-rung tick still arrives."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        temp_db.wset(cid, "offscreen_log", [
            {"turn": 4, "seed": "s", "events": [
                {"actor": "Elyndra",
                 "tick": "unaware of the Kalvoss cruiser's arrival"},
                {"disposition": "provisional",
                 "subject": {"kind": "character", "id": SID},
                 "basis": "deterministic", "actor": SID,
                 "actor_display": "Elyndra",
                 "tick": "Elyndra keeps quietly at it: waiting"},
            ]},
        ])
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        ticks = [e for e in rec["events"] if e["event_id"] is None]
        assert len(ticks) == 1
        assert "keeps quietly" in ticks[0]["summary"]
        assert not any("Kalvoss" in e["summary"] for e in ticks)
        assert any("provenance" in n for n in rec["inputs"]["notes"])

    def test_the_structured_subject_outranks_the_legacy_actor_spelling(
            self, temp_db, monkeypatch):
        """A seeded-rung tick names its owner in `subject.id`; when that id
        belongs to somebody else, a stray `actor` spelling matching this
        subject must not re-attribute the tick -- the structured field is
        the provenance, the loose one is the defect it replaced."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        temp_db.wset(cid, "offscreen_log", [
            {"turn": 4, "seed": "s", "events": [
                {"disposition": "provisional",
                 "subject": {"kind": "character", "id": "reyet_solan"},
                 "basis": "deterministic", "actor": "Elyndra",
                 "tick": "planted the ledger in the archive"},
            ]},
        ])
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert [e for e in rec["events"] if e["event_id"] is None] == []


class TestScheduledEventAttribution:
    def test_a_payload_that_merely_mentions_the_subject_is_not_their_event(
            self, temp_db, monkeypatch):
        """Attribution went by substring over payload prose + location id,
        so another room's event whose text NAMED the subject rode into
        their gap -- other rooms' happenings and room ids delivered to the
        wrong character. Attribution must be structured (`entity_id`) or
        nothing; a mention is somebody else's event."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        temp_db.wset(cid, "simulation_clock",
                     {"elapsed_seconds": 500.0, "display": "later"})
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            ("ev_denounced", cid, 300.0, "news_arrival", "plaza_west",
             json.dumps({"summary": "Elyndra is denounced in the plaza"}),
             "s", "fired"))
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            ("ev_arrival", cid, 310.0, "transit_arrival", "hall",
             json.dumps({"entity_id": SID, "destination_room": "hall"}),
             "s", "fired"))
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert [e["event_id"] for e in rec["events"]
                if e["event_id"]] == ["ev_arrival"]


class TestTheFrameGate:
    def test_another_frames_event_stays_in_its_frame(
            self, temp_db, monkeypatch):
        """scene.recent_events treats a cross-frame read as an information
        boundary leak, and scheduled_events carries its frame in the
        payload (mechanics._fire_due_events' own convention) -- but the gap
        query read every frame's rows. A row minted by another era must not
        surface in this era's gap."""
        _no_model(monkeypatch)
        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        _seen(temp_db, cid)
        temp_db.wset(cid, "simulation_clock",
                     {"elapsed_seconds": 500.0, "display": "later"})
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            ("ev_elsewhen", cid, 300.0, "transit_arrival", "hall",
             json.dumps({"entity_id": SID, "frame_id": 7}), "s", "fired"))
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene())
        assert rec["events"] == []

    def test_an_explicit_frame_ask_windows_by_that_frames_clock(
            self, temp_db, monkeypatch):
        """`simulation_clock` is a frame-scoped key resolved through the
        contextvar, so an explicit frame_id ask windowed the clock ledger
        by whatever frame the CALLING THREAD happened to have active --
        the present one, on a producer thread -- and the frame's own fired
        events silently vanished from its gaps."""
        _no_model(monkeypatch)
        from db import wset_for_frame

        cid = _make_chat(temp_db)
        _attach_character(temp_db, cid, "Elyndra", uid=SID)
        wset_for_frame(cid, LAST_SEEN_KEY,
                       {SID: {"turn": 2, "room": "garden",
                              "elapsed_seconds": 100.0}}, 7)
        wset_for_frame(cid, "simulation_clock",
                       {"elapsed_seconds": 500.0, "display": "later"}, 7)
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
            "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            ("ev_in_frame", cid, 300.0, "transit_arrival", "hall",
             json.dumps({"entity_id": SID, "frame_id": 7}), "s", "fired"))
        rec = gap_for(cid, "character", SID, 2, 6, scene=_scene(),
                      frame_id=7)
        assert [e["event_id"] for e in rec["events"]
                if e["event_id"]] == ["ev_in_frame"]


class TestTheIdentityFloor:
    def test_the_gap_passes_through_the_observer_name_scrub(self):
        """The gap record is prose somebody else wrote -- offscreen ticks
        and the mapping_commit model, both of which write canonical names.
        Every neighboring payload field that hands a mind such prose routes
        through observer_name_scrub/scrub_names_deep with the same `known`
        map (world_knowledge at agents/character.py's own comment); the
        gap was injected raw, so a character could meet their interval
        pre-identified with names they never learned."""
        import agents.character as character

        src = inspect.getsource(character.character_step)
        assert "scrub_names_deep(_interim" in src
