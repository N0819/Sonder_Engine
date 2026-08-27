"""The presence ledger keys on a minted uid; the name is an attribute.

`background_presences` was keyed by display name, so two people sharing a
name were ONE RECORD (one memory, one dialogue history, silently merged), a
rename minted a stranger, and a raw entity id stored where a name belongs
was indistinguishable from one. Measured over the live corpus 2026-08-26,
91 records across 37 chats already carried every one of those failure
modes. These tests pin the re-keyed contract:

- two presences sharing a display name stay two records;
- a renamed presence stays ONE record (a rename is a field update);
- the load-time migration preserves every legacy record, deterministically
  and idempotently, merging only what id agreement proves;
- a reader that used to look up by name still resolves, through the
  permanent `presence_record_for` seam (names, former spellings, uids and
  entity ids all resolve; ambiguity refuses).
"""

from __future__ import annotations

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import (
    _fold_duplicate_presences,
    _mint_presence_uid,
    _resolve_or_mint_presence,
    is_presence_uid,
    presence_display_name,
    presence_is_unnamed,
    presence_name_items,
    presence_record_for,
    promotable_background_presences,
    promote_background_character,
    track_background_presences,
)


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _ctx(db, chat_id, turn_idx, director_resolve, player_input=""):
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, player_input, time.time()),
    )
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input, director_resolve=director_resolve,
    )


def _scene(entities):
    return {
        "location": "x", "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {eid: "hall" for eid in entities},
        "entities": {eid: {"name": name, "kind": "person"}
                     for eid, name in entities.items()},
        "attire": {}, "overlays": {},
    }


# ---------------------------------------------------------------------------
# two people, one name
# ---------------------------------------------------------------------------

class TestTwoPresencesSharingANameStayTwo:
    def test_distinct_bodies_with_one_display_name_are_two_records(
        self, temp_db,
    ):
        """Two scene entities carrying the same display name, each proven by
        its own id in the beat's harvest, must land as two records -- the
        exact silent-merge the name key produced."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene",
                     _scene({"e1": "Attendant", "e2": "Attendant"}))
        ctx = _ctx(temp_db, chat_id, 1, {
            "resolved_event": "Two attendants take up posts.",
            "dialogue_log": [],
            "state_diff": {"entities": {
                "e1": {"kind": "person", "name": "Attendant"},
                "e2": {"kind": "person", "name": "Attendant"},
            }},
        })
        track_background_presences(ctx, nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert len(presences) == 2
        bindings = {rec.get("entity_id") for rec in presences.values()}
        assert bindings == {"e1", "e2"}
        for rec in presences.values():
            assert rec.get("name") == "Attendant"

    def test_records_bound_to_different_bodies_never_fold(self):
        scene = _scene({"e1": "Attendant", "e2": "Attendant"})
        a, b = _mint_presence_uid("entity:e1"), _mint_presence_uid("entity:e2")
        folded = _fold_duplicate_presences({
            a: {"uid": a, "name": "Attendant", "entity_id": "e1",
                "dialogue_turns": [1]},
            b: {"uid": b, "name": "Attendant", "entity_id": "e2",
                "dialogue_turns": [2]},
        }, scene)
        assert len(folded) == 2

    def test_a_name_two_records_answer_to_refuses_to_resolve(self):
        """Guessing hands one person the other's history; minting a third
        invents a stranger. Ambiguity is its own answer."""
        scene = _scene({"e1": "Attendant", "e2": "Attendant"})
        a, b = _mint_presence_uid("entity:e1"), _mint_presence_uid("entity:e2")
        presences = {
            a: {"uid": a, "name": "Attendant", "entity_id": "e1"},
            b: {"uid": b, "name": "Attendant", "entity_id": "e2"},
        }
        assert presence_record_for(presences, "Attendant", scene) == (None, None)
        # ...while each record's own handles still resolve exactly.
        assert presence_record_for(presences, a, scene)[0] == a
        assert presence_record_for(presences, "e2", scene)[0] == b

    def test_unattributable_conduct_warns_and_files_nothing(self, temp_db):
        chat_id = _make_chat(temp_db)
        scene = _scene({"e1": "Attendant", "e2": "Attendant"})
        temp_db.wset(chat_id, "scene", scene)
        a, b = _mint_presence_uid("entity:e1"), _mint_presence_uid("entity:e2")
        temp_db.wset(chat_id, "background_presences", {
            a: {"uid": a, "name": "Attendant", "entity_id": "e1",
                "first_turn": 0, "last_turn": 0,
                "dialogue_turns": [], "mention_turns": []},
            b: {"uid": b, "name": "Attendant", "entity_id": "e2",
                "first_turn": 0, "last_turn": 0,
                "dialogue_turns": [], "mention_turns": []},
        })
        ctx = _ctx(temp_db, chat_id, 3, {
            "resolved_event": "One of them speaks.",
            "dialogue_log": [{"speaker": "Attendant",
                              "exact_quote": "This way, please."}],
            "state_diff": {},
        })
        track_background_presences(ctx, nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert len(presences) == 3 - 1  # no third record minted
        for rec in presences.values():
            assert 3 not in (rec.get("dialogue_turns") or [])
        assert any("not attributed" in str(w) for w in ctx.warnings)

    def test_promoting_an_ambiguous_name_raises(self, temp_db):
        """Promotion under a shared name would seed one person's sheet and
        first-person memories from both people's lines -- the weld that
        becomes permanent. It must refuse, not guess."""
        import pytest

        chat_id = _make_chat(temp_db)
        scene = _scene({"e1": "Attendant", "e2": "Attendant"})
        temp_db.wset(chat_id, "scene", scene)
        a, b = _mint_presence_uid("entity:e1"), _mint_presence_uid("entity:e2")
        temp_db.wset(chat_id, "background_presences", {
            a: {"uid": a, "name": "Attendant", "entity_id": "e1"},
            b: {"uid": b, "name": "Attendant", "entity_id": "e2"},
        })
        with pytest.raises(ValueError, match="[Mm]ore than one"):
            promote_background_character(chat_id, "Attendant")

    def test_promoting_one_of_two_by_id_leaves_the_other(
        self, temp_db, monkeypatch,
    ):
        from story import importers

        chat_id = _make_chat(temp_db)
        scene = _scene({"e1": "Attendant", "e2": "Attendant"})
        temp_db.wset(chat_id, "scene", scene)
        a, b = _mint_presence_uid("entity:e1"), _mint_presence_uid("entity:e2")
        temp_db.wset(chat_id, "background_presences", {
            a: {"uid": a, "name": "Attendant", "entity_id": "e1",
                "dialogue_turns": [1]},
            b: {"uid": b, "name": "Attendant", "entity_id": "e2",
                "dialogue_turns": [2]},
        })

        def fake_draft(cid, presence_name):
            return {"sheet": {"identity": {"name": "Attendant"}},
                    "memory_seeds": [], "evidence_turns": [1]}

        monkeypatch.setattr(importers, "draft_promoted_character", fake_draft)
        promote_background_character(chat_id, a)

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert set(presences) == {b}, "the other body's record survives"


# ---------------------------------------------------------------------------
# a rename is a field update
# ---------------------------------------------------------------------------

class TestARenamedPresenceStaysOne:
    def test_rename_updates_the_name_and_keeps_the_key(self):
        """The record was bound to its body while it wore the old name; the
        body's current display name wins the attribute, the key survives,
        and the old spelling stays hearable in aka."""
        old_scene = _scene({"e1": "the porter"})
        ledger = _fold_duplicate_presences({
            "the porter": {"first_turn": 0, "last_turn": 2,
                           "dialogue_turns": [1], "mention_turns": []},
        }, old_scene)
        (key,) = ledger
        assert is_presence_uid(key)
        assert ledger[key]["entity_id"] == "e1"

        new_scene = _scene({"e1": "Harrow"})
        folded = _fold_duplicate_presences(ledger, new_scene)
        assert set(folded) == {key}, "same key: same person"
        rec = folded[key]
        assert rec["name"] == "Harrow"
        assert "the porter" in rec.get("aka", [])
        assert rec["dialogue_turns"] == [1]

    def test_the_old_spelling_still_resolves_to_the_record(self):
        scene = _scene({"e1": "Harrow"})
        key = _mint_presence_uid("entity:e1")
        presences = {key: {"uid": key, "name": "Harrow", "entity_id": "e1",
                           "aka": ["the porter"]}}
        assert presence_record_for(presences, "the porter", scene)[0] == key
        assert presence_record_for(presences, "Harrow", scene)[0] == key

    def test_a_new_spelling_of_a_bound_body_files_under_its_record(self):
        scene = _scene({"e1": "Harrow"})
        key = _mint_presence_uid("entity:e1")
        presences = {key: {"uid": key, "name": "the porter",
                           "entity_id": "e1"}}
        assert _resolve_or_mint_presence("Harrow", presences, scene) == key
        assert len(presences) == 1


# ---------------------------------------------------------------------------
# the migration
# ---------------------------------------------------------------------------

class TestMigrationPreservesEveryRecord:
    def test_a_legacy_bank_converts_without_losing_anyone(self):
        """A bank shaped like the live corpus: a charter-bound record, a
        record bound to a scene entity, a bare positions name with no entity
        anywhere, a raw entity id stored as a name, and an underscore
        spelling of an entity key. Every person survives; only what id
        agreement PROVES merges."""
        scene = _scene({"desk_clerk": "Reya", "e9": "Old Tom"})
        legacy = {
            "Foreman Aldis": {
                "first_turn": 0, "last_turn": 9, "dialogue_turns": [2],
                "charter_refs": [{"charter": "works", "body": "foreman"}],
            },
            "Old Tom": {"first_turn": 1, "last_turn": 8,
                        "dialogue_turns": [1, 5]},
            "night porter": {"first_turn": 2, "last_turn": 7,
                             "dialogue_turns": [3]},   # no entity anywhere
            "e9": {"first_turn": 4, "last_turn": 6,
                   "mention_turns": [4]},              # raw id as a name
            "desk clerk": {"first_turn": 0, "last_turn": 9,
                           "dialogue_turns": [0]},     # entity-key respelling
        }
        folded = _fold_duplicate_presences(
            {k: dict(v) for k, v in legacy.items()}, scene)

        # Every key is a minted uid now, and no history was lost.
        assert all(is_presence_uid(k) for k in folded)
        names = {n for n, _ in presence_name_items(folded)}
        assert {"Foreman Aldis", "night porter", "Reya"} <= names
        # `e9` (the raw id) and `Old Tom` proved the same binding: one body,
        # one record, both histories.
        tom = presence_record_for(folded, "Old Tom", scene)[1]
        assert tom["dialogue_turns"] == [1, 5]
        assert tom["mention_turns"] == [4]
        # The respelled entity key adopted the body's display name.
        reya = presence_record_for(folded, "Reya", scene)[1]
        assert reya["entity_id"] == "desk_clerk"
        assert reya["dialogue_turns"] == [0]
        # Distinct people stayed distinct: nothing merged the porter, the
        # foreman or Reya into each other.
        assert len(folded) == 4

    def test_the_migration_is_deterministic_and_idempotent(self):
        """Two independent loads of the same bank agree on every key --
        pre-commit readers and the commit writer must find the same records
        -- and a second pass over a migrated bank changes nothing."""
        scene = _scene({"e9": "Old Tom"})
        legacy = {
            "Old Tom": {"first_turn": 1, "dialogue_turns": [1]},
            "night porter": {"first_turn": 2, "dialogue_turns": [3]},
        }
        once = _fold_duplicate_presences(
            json.loads(json.dumps(legacy)), scene)
        again = _fold_duplicate_presences(
            json.loads(json.dumps(legacy)), scene)
        assert once == again
        third = _fold_duplicate_presences(json.loads(json.dumps(once)), scene)
        assert third == once

    def test_two_spellings_merge_only_on_shared_binding(self):
        """The live pair: a bare positions spelling and the entity key it
        respells both bind to one body, so they merge -- as id agreement,
        never string similarity. A pair sharing nothing provable stays
        split, per the settled doctrine."""
        scene = _scene({"station_engineer": "Reya"})
        folded = _fold_duplicate_presences({
            "station engineer": {"first_turn": 0, "dialogue_turns": [1]},
            "station_engineer": {"first_turn": 3, "dialogue_turns": [4]},
        }, scene)
        assert len(folded) == 1
        (rec,) = folded.values()
        assert sorted(rec["dialogue_turns"]) == [1, 4]

        # No shared binding, no merge: same-ish names, no scene entity.
        split = _fold_duplicate_presences({
            "Taira Hiroshi": {"first_turn": 0, "dialogue_turns": [1]},
            "Taira Mika": {"first_turn": 1, "dialogue_turns": [2]},
        }, _scene({}))
        assert len(split) == 2


# ---------------------------------------------------------------------------
# name lookup still works
# ---------------------------------------------------------------------------

class TestAReaderThatLookedUpByNameStillResolves:
    def test_every_handle_reaches_the_record(self):
        scene = _scene({"e1": "Harrow"})
        key = _mint_presence_uid("entity:e1")
        old = _mint_presence_uid("legacy:the porter")
        presences = {key: {"uid": key, "name": "Harrow", "entity_id": "e1",
                           "aka": ["the porter"], "former_uids": [old]}}
        for handle in ("Harrow", "harrow", "The Porter", key, old, "e1"):
            got_key, got = presence_record_for(presences, handle, scene)
            assert got_key == key, handle
            assert got is presences[key], handle

    def test_a_legacy_name_keyed_bank_reads_through_unmigrated(self):
        """Raw readers (payload builders) may see a bank a beat before any
        fold runs; a name-keyed entry must still answer to its key."""
        presences = {"Doran": {"first_turn": 0, "dialogue_turns": [1]}}
        assert presence_record_for(presences, "Doran")[0] == "Doran"
        assert presence_display_name("Doran", presences["Doran"]) == "Doran"
        assert [n for n, _ in presence_name_items(presences)] == ["Doran"]

    def test_an_untracked_name_is_a_miss_not_an_error(self):
        assert presence_record_for({}, "nobody") == (None, None)
        assert presence_record_for(None, "") == (None, None)


# ---------------------------------------------------------------------------
# what the key does NOT fix needs its own guard
# ---------------------------------------------------------------------------

class TestAnIdShapedNameIsNotAName:
    def test_id_shaped_names_read_as_unnamed(self):
        key = _mint_presence_uid()
        assert presence_is_unnamed(key, {"uid": key,
                                         "name": "a23653c914bf40a8"})
        assert presence_is_unnamed(key, {"uid": key, "name": ""})
        assert not presence_is_unnamed(key, {"uid": key, "name": "Harrow"})
        # A uid-keyed record with no name attribute has no name at all.
        assert presence_display_name(key, {"uid": key}) == ""
        assert presence_is_unnamed(key, {"uid": key})

    def test_an_unnamed_presence_is_listed_but_never_offered(self, temp_db):
        """J3: an unnamed presence is the same population -- tracked, with
        full state -- but promotion writes the name into a permanent
        identity, so the offer waits for a real one."""
        chat_id = _make_chat(temp_db)
        key = _mint_presence_uid("entity:e77")
        temp_db.wset(chat_id, "background_presences", {
            key: {"uid": key, "name": "635a740debcd433f", "entity_id": "e77",
                  "first_turn": 0, "last_turn": 9,
                  "dialogue_turns": [1, 2, 3, 4], "mention_turns": []},
        })
        rows = promotable_background_presences(chat_id)
        (row,) = [r for r in rows if r["id"] == key]
        assert row["promotable"] is False

    def test_promoting_an_unnamed_presence_raises(self, temp_db):
        import pytest

        chat_id = _make_chat(temp_db)
        key = _mint_presence_uid("entity:e77")
        temp_db.wset(chat_id, "background_presences", {
            key: {"uid": key, "name": "635a740debcd433f",
                  "entity_id": "e77", "dialogue_turns": [1, 2, 3]},
        })
        with pytest.raises(ValueError, match="no real name"):
            promote_background_character(chat_id, key)


class TestPromotableRowsCarryTheId:
    def test_rows_carry_id_and_name(self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "background_presences", {
            "Doran": {"first_turn": 0, "last_turn": 3,
                      "dialogue_turns": [1, 2], "mention_turns": []},
        })
        rows = promotable_background_presences(chat_id)
        (row,) = rows
        assert row["name"] == "Doran"
        assert is_presence_uid(row["id"])
