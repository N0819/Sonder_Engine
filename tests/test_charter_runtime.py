"""The production seam for institutions: JSON, causality, landing, aperture."""

from __future__ import annotations

import json
import threading
import time
import types

from world.charter import normalize_charter, seed_needs, seed_roster, step
from world.charter_runtime import (
    apply_presence_conduct,
    advance_snapshot,
    background_presence_records,
    cross_charter_gossip,
    land_snapshot,
    normalize_registry,
    place_view,
    presence_view,
    registry_for,
    registry_revision,
    registry_warnings,
    residue_facts,
    save_registry,
    schedule_charter_ticks,
    charter_speaker_records,
)
from world.mechanics import mechanics_sweep


def _chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Charter runtime", "", time.time()),
    )


def _working_pair():
    charter = normalize_charter({
        "key": "works",
        "upkeeps": {
            "safe": {"place": "room_a", "level": 1.0, "floor": 0.2,
                     "drift_per_hour": 0.0, "service_per_hour": 1.0},
            "fail": {"place": "room_b", "level": 0.21, "floor": 0.2,
                     "drift_per_hour": 0.1, "service_per_hour": 0.0},
        },
        "posts": {
            "safe_post": {"place": "room_a", "serves": ["safe"],
                          "requires": {"safe_skill": 1}},
            "fail_post": {"place": "room_b", "serves": ["fail"],
                          "requires": {"fail_skill": 1}},
        },
        "bodies": {
            "alice": {"place": "room_a",
                      "competence": {"safe_skill": 1}},
            "bob": {"place": "room_b",
                    "competence": {"fail_skill": 1}},
        },
        "priority": ["safe", "fail"],
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def test_blame_follows_the_post_that_serves_the_failed_upkeep():
    after, events = step(_working_pair(), hours=1.0)

    assert [e["upkeep"] for e in events
            if e["kind"] == "upkeep_out_of_band"] == ["fail"]
    assert after["politics"]["blame"] == {"bob": 1}


def test_a_political_charter_is_json_round_trippable():
    charter = _working_pair()
    charter["politics"] = {"regard": {("alice", "bob"): 0.8}}

    after, _ = step(charter, hours=1.0)
    encoded = json.dumps(after)
    restored = normalize_charter(json.loads(encoded))

    assert restored["politics"] == after["politics"]


def test_the_registry_is_frame_scoped(temp_db):
    cid = _chat(temp_db)
    first = save_registry(cid, {"first": _working_pair()}, frame_id=11)
    second_state = _working_pair()
    second_state["key"] = "second"
    save_registry(cid, {"second": second_state}, frame_id=12)

    assert registry_for(cid, 11) == first
    assert set(registry_for(cid, 12)["items"]) == {"second"}
    assert registry_for(cid, None)["items"] == {}


def test_charter_speakers_keep_authored_titles_and_colour_seeds(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"watch": {
        "key": "watch",
        "naming": {"titles": {"ranks": {"captain": "Captain"}}},
        "bodies": {"ysra": {"name": "Ysra Vale", "rank": "captain",
                             "place": "gate",
                             "dialogue_color": "#4A90E2"}},
    }})

    assert charter_speaker_records(cid) == [{
        "name": "Captain Ysra Vale", "charter": "watch", "body": "ysra",
        "aliases": ["Ysra Vale", "Captain Ysra Vale"],
        "seed": "charter:watch:ysra", "color": "#4A90E2",
        "place": "gate",
    }]


def test_identity_authoring_warnings_name_bad_colours_and_collisions():
    warnings = registry_warnings({"watch": {
        "key": "watch",
        "bodies": {
            "one": {"name": "Same", "dialogue_color": "blue"},
            "two": {"name": "Same"},
        },
    }})
    assert any("unreadable dialogue_color" in warning for warning in warnings)
    assert any("belongs to multiple bodies" in warning for warning in warnings)


def test_the_registry_refuses_a_second_event_ledger():
    normalized = normalize_registry({
        "items": {"works": {"state": _working_pair()}},
        "recent_events": [{"kind": "legacy_duplicate"}],
    })

    # The guarantee is that no SECOND event ledger survives -- incidents have
    # one durable home, scheduled_events -> world_events. `people` joined the
    # registry on 2026-08-27 when a person stopped being owned by the
    # institution that employs them, and is not an event ledger.
    assert "recent_events" not in normalized
    assert set(normalized) == {"version", "items", "people"}


def test_different_charters_trade_only_news_through_colocated_bodies():
    first = _working_pair()
    first["bodies"]["alice"]["name"] = "Alice North"
    first["minds"]["alice"] = {
        "report:gate": {
            "kind": "news", "body": "report:gate",
            "event_kind": "claim", "about": "the gate",
            "claim_text": "the north gate is shut", "place": "room_a",
            "happened_at": 1.0, "strength": 1.0, "as_of_hours": 1.0,
            "heard_from": None, "world_event_id": "gate",
            "retellings": 0, "provenance": "witnessed_surface",
        },
        # A private belief about a person is not gossip on this bridge.
        "bob": {"body": "bob", "believed_available": False,
                "strength": 1.0, "as_of_hours": 1.0},
    }
    second = _working_pair()
    second["key"] = "visitors"
    second["bodies"]["alice"]["name"] = "Vela South"
    second["bodies"]["alice"]["place"] = "room_a"
    registry = normalize_registry({"home": first, "visitors": second})

    assert cross_charter_gossip(registry) == 1
    heard = registry["items"]["visitors"]["state"]["minds"]["alice"]
    assert heard["report:gate"]["heard_from"] == "Alice North"
    assert "bob" not in heard


def test_cross_charter_gossip_requires_the_same_place():
    first = _working_pair()
    first["minds"]["alice"] = {
        "report:gate": {
            "kind": "news", "body": "report:gate", "event_kind": "claim",
            "about": "gate", "claim_text": "the gate is shut",
            "place": "room_a", "happened_at": 1.0, "strength": 1.0,
            "as_of_hours": 1.0, "heard_from": None,
        }}
    second = _working_pair()
    second["key"] = "visitors"
    second["bodies"]["alice"]["place"] = "room_b"
    registry = normalize_registry({"home": first, "visitors": second})

    cross_charter_gossip(registry)
    assert "report:gate" not in registry["items"]["visitors"]["state"][
        "minds"].get("alice", {})


def test_catchup_lands_state_and_stable_consequences(temp_db):
    cid = _chat(temp_db)
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, 1, "", time.time(), None))
    temp_db.wset(cid, "offscreen_epoch", {"epoch_id": "epoch-1"})
    registry = normalize_registry({
        "items": {"works": {"state": _working_pair(),
                              "last_elapsed_seconds": 0.0,
                              "window_hours": 1.0}}
    })

    advanced, rows, produced = advance_snapshot(
        registry, elapsed_seconds=3600.0, epoch_id="epoch-1", base_turn=1,
        cid=cid, frame_id=None,
        scene={"rooms": {"room_a": {}, "room_b": {}}, "positions": {}},
    )
    result = land_snapshot(
        cid, None, 1, "epoch-1", advanced, rows, produced)

    assert result["events"] >= 1
    assert registry_for(cid)["items"]["works"]["state"]["politics"][
        "blame"] == {"bob": 1}
    stored = temp_db.q(
        "SELECT * FROM scheduled_events WHERE chat_id=?", (cid,))
    assert stored
    payload = json.loads(stored[0]["payload"])
    assert payload["origin"]["charter"] == "works"
    assert payload["disposition"] == "resolved_fact"

    _, ops, notices, counts = mechanics_sweep(
        {"rooms": {"room_a": {}, "room_b": {}}, "positions": {}},
        {"elapsed_seconds": 3600.0}, None, [dict(row) for row in stored],
        turn_idx=2, player_room="room_b",
    )
    assert counts["consequences_fired"] == len(stored)
    assert {op[2] for op in ops if op[0] == "status"} == {"fired"}
    assert notices  # the player learns only because one lands where they are

    # A repeated landing is harmless: stable ids meet INSERT OR IGNORE.
    land_snapshot(cid, None, 1, "epoch-1", advanced, rows, produced)
    assert len(temp_db.q(
        "SELECT * FROM scheduled_events WHERE chat_id=?", (cid,))) == len(stored)


def test_an_epoch_change_discards_the_whole_landing(temp_db):
    cid = _chat(temp_db)
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, 1, "", time.time(), None))
    temp_db.wset(cid, "offscreen_epoch", {"epoch_id": "new-edge"})
    registry = normalize_registry({"works": _working_pair()})

    result = land_snapshot(cid, None, 1, "old-edge", registry, [], [])

    assert result["advanced"] == 0
    assert registry_for(cid)["items"] == {}


def test_an_author_edit_while_a_tick_runs_wins(temp_db):
    cid = _chat(temp_db)
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, 1, "", time.time(), None))
    temp_db.wset(cid, "offscreen_epoch", {"epoch_id": "same-edge"})
    source = save_registry(cid, {"items": {"works": {
        "state": _working_pair(), "last_elapsed_seconds": 0.0}}})
    source_revision = registry_revision(source)
    advanced, rows, produced = advance_snapshot(
        source, elapsed_seconds=3600.0, epoch_id="same-edge", base_turn=1,
        cid=cid, frame_id=None,
        scene={"rooms": {"room_a": {}, "room_b": {}}, "positions": {}},
    )
    edited = _working_pair()
    edited["priority"] = ["fail", "safe"]
    save_registry(cid, {"edited": edited})

    result = land_snapshot(
        cid, None, 1, "same-edge", advanced, rows, produced,
        expected_revision=source_revision)

    assert result["reason"] == "registry_changed"
    assert set(registry_for(cid)["items"]) == {"edited"}
    assert temp_db.q(
        "SELECT * FROM scheduled_events WHERE chat_id=?", (cid,)) == []


def test_a_committed_epoch_schedules_and_lands_out_of_band(
        temp_db, monkeypatch):
    cid = _chat(temp_db)
    temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, 3, "", time.time(), None))
    temp_db.wset(cid, "dialogue_config", {
        "offscreen_life": "deterministic"})
    temp_db.wset(cid, "offscreen_epoch", {"epoch_id": "epoch-job"})
    temp_db.wset(cid, "scene", {
        "rooms": {"room_a": {}, "room_b": {}}, "positions": {}})
    save_registry(cid, {"items": {"works": {
        "state": _working_pair(), "last_elapsed_seconds": 0.0,
        "window_hours": 1.0,
    }}})
    submitted = {}

    def immediate_submit(chat_id, key, fn, base_turn=None):
        job = types.SimpleNamespace(cancelled=threading.Event())
        submitted.update(chat_id=chat_id, key=key, base_turn=base_turn,
                         result=fn(job))
        return job

    monkeypatch.setattr("world.charter_runtime.jobs.submit", immediate_submit)
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(idx=3, frame_id=None),
    )

    job = schedule_charter_ticks(ctx, {
        "opportunity": True, "epoch_id": "epoch-job",
        "elapsed_seconds": 3600.0,
    })

    assert job is not None
    assert submitted["key"] == "charter:epoch-job"
    assert submitted["base_turn"] == 3
    assert submitted["result"]["events"] >= 1
    assert registry_for(cid)["items"]["works"]["last_epoch_id"] == "epoch-job"


def test_the_presence_aperture_excludes_the_register(temp_db):
    cid = _chat(temp_db)
    state = _working_pair()
    state["active_places"] = ["room_b"]
    save_registry(cid, {"works": state})

    whole = place_view(cid, "room_b")
    own = presence_view(cid, "room_b", "bob")

    assert whole and own
    assert "roster" not in own[0]["presence"]
    assert "minds" not in own[0]["presence"]
    # THIS ALLOWLIST IS ASSERTED, and that is the check rather than a
    # formality. The discrete tie (`RESEARCH.md` §1.7.6 item 3) rides INSIDE
    # `knows_here`, beside the `regard` number it summarizes, so it widened no
    # key here -- a new field that had needed this set to grow would have been
    # a field placed outside the per-other slice it belongs in.
    #
    # `marks` (§1.7.6 item 4) DID widen it, and had to: a temporary status is
    # a fact about this body rather than about this body's view of another, so
    # there is no per-other slice for it to ride in. What keeps it honest is
    # scope: `charter_mark.mark_view` filters by `BODY_MARKS`, so the
    # institution's own `disgraced` -- attributed off the watch the charter
    # BELIEVED it had arranged, and reaching the blamed through no channel --
    # cannot appear on this surface however the caller asks.
    assert set(own[0]["presence"]) <= {
        "competence", "able", "condition", "strain", "standing_post",
        "temperament",
            "watches_stood", "can_bring_up", "knows_here", "strangers_here",
            "blamed", "knows_it_is_blamed", "social_judgments",
            "commitments", "institutional", "marks",
        }
    for presence in (row["presence"] for row in own):
        for row in presence.get("marks") or ():
            assert row["mark"] != "disgraced"
            assert set(row) <= {"mark", "by", "hours_ago"}
    # And nothing in the slice says how anybody holds THIS body back.
    for presence in (row["presence"] for row in own):
        for entry in (presence.get("knows_here") or {}).values():
            assert set(entry) <= {"firsthand", "believes_present", "regard",
                                  "figure", "tie"}
            assert "mutual" not in entry and "held_by" not in entry


def test_charter_bodies_are_derived_background_people_with_stable_refs(temp_db):
    cid = _chat(temp_db)
    state = _working_pair()
    state["bodies"]["bob"]["name"] = "Bob Vale"
    state["watch"] = {"fail_post": "bob"}
    save_registry(cid, {"works": state})

    records = background_presence_records(cid, places={"room_b"})

    assert set(records) == {"Bob Vale"}
    assert records["Bob Vale"]["nature"] == "person"
    assert records["Bob Vale"]["charter_refs"] == [
        {"charter": "works", "body": "bob"}]
    assert records["Bob Vale"]["sketch"] == {
        "role_hint": "fail_post", "station_room": "room_b"}


def test_presence_packet_carries_temperament_and_exact_scene_affordances(temp_db):
    cid = _chat(temp_db)
    state = _working_pair()
    state["bodies"]["bob"]["name"] = "Bob Vale"
    save_registry(cid, {"works": state})

    view = presence_view(
        cid, "room_b", "Bob Vale", figures=["the traveller"])[0]

    assert set(view["presence"]["temperament"]) == {
        "pain_sensitivity", "pleasure_sensitivity",
        "baseline_reactivity", "recovery_rate", "overload_threshold",
    }
    greet = next(row for row in view["action_instances"]
                 if row["act"] == "greet" and row["other"] == "the traveller")
    landed = apply_presence_conduct(
        cid, "Bob Vale", {"act": "greet", "other": "the traveller"},
        record={"charter_refs": [{"charter": "works", "body": "bob"}]},
        allowed=[greet], place="room_b")

    assert landed["line"] == "bob greeted the traveller"
    state_after = registry_for(cid)["items"]["works"]["state"]
    assert state_after["minds"]["bob"]["the traveller"]["kind"] == "figure"
    assert "the traveller" not in state_after["figures"]

    before = registry_revision(registry_for(cid))
    refused = apply_presence_conduct(
        cid, "Bob Vale", {"act": "accuse", "other": "the traveller"},
        record={"charter_refs": [{"charter": "works", "body": "bob"}]},
        allowed=[greet], place="room_b")
    assert refused["refused"] == "not_offered_to_scene_life"
    assert registry_revision(registry_for(cid)) == before


def test_promoted_body_is_an_institutional_projection_not_a_second_mind(temp_db):
    cid = _chat(temp_db)
    state = _working_pair()
    state["bindings"] = {
        "bob": {"char_id": 9, "name": "Bob Vale", "entity_id": "char_bob"}}
    state["bodies"]["bob"]["name"] = "Bob Vale"
    state["bodies"]["bob"]["place"] = "room_a"  # away from fail_post
    state["minds"]["bob"] = {"alice": {"body": "alice", "strength": 1.0}}
    state["feel"]["bob"] = {"stress": {"strain": 0.8}}

    after, events = step(state, hours=1.0)

    assert after["bodies"]["bob"]["place"] == "room_a"
    assert "bob" not in after["minds"]
    assert "bob" not in after["needs"]
    assert "bob" not in after["feel"]
    assert any(e["kind"] == "post_believed_filled"
               and e["body"] == "bob" for e in events)


def test_an_unfilled_post_is_visible_at_its_own_room(temp_db):
    cid = _chat(temp_db)
    state = _working_pair()
    state["posts"]["fail_post"]["place"] = "control_room"
    state["reported"] = {
        "post_unfilled": {"fail_post": "no qualified body in reach"},
        "post_believed_filled": {},
    }
    save_registry(cid, {"works": state})

    assert residue_facts(cid, "control_room") == [
        "The fail_post duty remains unfilled (no qualified body in reach)."
    ]


class TestACharterEmploysPeopleItDoesNotOwn:
    """A person used to live inside the blob of the institution that employed
    them, addressed as `(charter_key, body_key)`. Two things followed that are
    plainly wrong: a hermit the Director invented needed an institution to
    exist in, and anybody moving town, joining a crew or transferring ship had
    to be re-keyed across two blobs dragging thirteen person-scoped stores
    behind them -- `bodies`, `minds`, `needs`, `feel`, `experiences`,
    `served_beside`, `stood`, `judgments`, `ties`, `marks`, `habit_runs`,
    `travelled`, `heard_blame`. Anything that missed one lost that part of the
    person silently. See `docs/UNBUILT.md` 1.99d.
    """

    @staticmethod
    def _two_houses():
        import copy as _copy
        from charter_fixtures import ABBEY, SHIP
        return normalize_registry({"items": {
            "ship": {"state": _copy.deepcopy(SHIP)},
            "abbey": {"state": _copy.deepcopy(ABBEY)}}})

    def test_the_stored_shape_holds_a_person_once(self):
        """On disk a person is stored at registry level and an institution
        records only who it employs. The working shape stays joined, so the
        two hundred readers in this package did not have to move."""
        from world.charter_runtime import _stored_shape

        joined = self._two_houses()
        stored = _stored_shape(joined)

        assert set(stored) == {"version", "items", "people"}
        assert "bodies" not in stored["items"]["ship"]["state"]
        assert stored["items"]["ship"]["state"]["members"]
        assert normalize_registry(stored) == joined, "round trip"

    def test_a_person_may_be_employed_nowhere(self):
        """The hermit. Not an institution of one -- a person with no
        membership, which is what having no institution actually means."""
        from world.charter_runtime import _stored_shape

        stored = _stored_shape(self._two_houses())
        stored["people"]["hermit"] = {"bodies": {
            "key": "hermit", "name": "Hermit", "place": "hill",
            "available": True, "competence": {}}}

        back = normalize_registry(stored)

        assert "hermit" in back["people"]
        assert all("hermit" not in (item["state"].get("members") or ())
                   for item in back["items"].values())

    def test_a_transfer_carries_the_whole_person(self):
        """Joining another crew is a membership change. What they remember,
        who they served beside and how they hold people are the same objects
        before and after, because they were never the institution's."""
        from world.charter_runtime import transfer_person

        registry = self._two_houses()
        ship = registry["items"]["ship"]["state"]
        ship["experiences"]["vega"] = [
            {"id": "e1", "kind": "encounter", "at_hours": 4.0,
             "other": "chief"}]
        ship["served_beside"]["vega"] = {"chief": 312}
        remembered = [dict(row) for row in ship["experiences"]["vega"]]

        transfer_person(registry, "vega", "abbey", place="choir")

        ship = registry["items"]["ship"]["state"]
        abbey = registry["items"]["abbey"]["state"]
        assert "vega" not in ship["bodies"] and "vega" not in ship["members"]
        assert "vega" in abbey["bodies"] and "vega" in abbey["members"]
        assert abbey["experiences"]["vega"] == remembered
        assert abbey["served_beside"]["vega"] == {"chief": 312}, (
            "three hundred watches beside a former shipmate are still theirs")
        assert abbey["bodies"]["vega"]["place"] == "choir"

    def test_leaving_every_institution_is_not_ceasing_to_exist(self):
        from world.charter_runtime import transfer_person

        registry = self._two_houses()

        transfer_person(registry, "vega", None)

        assert "vega" in registry["people"]
        assert all("vega" not in (item["state"].get("bodies") or {})
                   for item in registry["items"].values())

    def test_two_institutions_may_mint_the_same_body_key(self):
        """WHY A PERSON ID IS QUALIFIED. Body keys are minted per institution,
        so two independently generated charters in one story both produce
        `tech:0001`. A flat person store keyed by body alone has the second
        silently overwrite the first -- measured the moment it was tried: a
        second generated location came back with every person store empty and
        its clock at zero, and the presim that produced it was discarded by
        the revision guard rather than failing loudly.
        """
        from world.charter_runtime import _stored_shape

        def _house(key, place):
            return normalize_charter({
                "key": key,
                "posts": {"tech": {"place": place, "serves": []}},
                "bodies": {"tech:0001": {"place": place, "competence": {}}},
            })

        joined = normalize_registry({"items": {
            "crew": {"state": _house("crew", "engine_room")},
            "crew_2": {"state": _house("crew_2", "aft_bay")}}})
        joined["items"]["crew"]["state"]["stood"]["tech:0001"] = {"tech": 9}

        stored = _stored_shape(joined)

        assert len(stored["people"]) == 2, "two people, not one overwritten"
        assert set(stored["people"]) == {"crew/tech:0001", "crew_2/tech:0001"}
        back = normalize_registry(stored)
        assert back["items"]["crew"]["state"]["stood"]["tech:0001"] == {"tech": 9}
        assert not back["items"]["crew_2"]["state"]["stood"], (
            "the other crew's identically-keyed body is a different person")
        # Compared through a re-normalize, not against `joined` directly: the
        # item is authoritative within a session and `people` only on disk, so
        # the mutation above deliberately left the in-memory mirror stale.
        assert back["items"] == normalize_registry(joined)["items"]
