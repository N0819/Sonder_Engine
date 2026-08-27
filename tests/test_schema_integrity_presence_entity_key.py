"""MASTER-039 / docs/UNBUILT.md 1.17: a background presence that acquires a
proper name mid-story must keep its history.

``background_presences`` was keyed by the prose string; the ledger now keys
each record on a minted presence uid with the name as an attribute, so a
rename is a field update rather than a new person. The identity questions
these tests pin are unchanged: the article fold (`_presence_identity`) heals
"A Dalek"/"The Dalek", but ``_presence_identity("mara") !=
_presence_identity("the guard")`` -- so when the scene entity the presence
belongs to is renamed ("the guard" becomes "Mara"), only the ``entity_id``
binding can connect the spellings (an id denotes exactly one body; folding
by it is unconditional), with the name as fallback for entity-less
presences (a voice through a door). Former spellings ride in ``aka`` so
mentions of the old name keep counting.

The crowd guard is deliberately preserved: binding a name to an entity id
requires the scene to answer UNAMBIGUOUSLY (exactly one body with that
identity). With two Daleks in the room nothing binds and nothing merges --
an over-merge welds two characters into one, which is worse than a split.
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import (
    _fold_duplicate_presences,
    _resolve_or_mint_presence,
    presence_name_items,
    presence_record_for,
    promote_background_character,
    track_background_presences,
)
from story import importers


def _rec(presences, name):
    return presence_record_for(presences, name)[1]


def _names(presences):
    return {n for n, _ in presence_name_items(presences)}


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


def _scene(entity_names_by_id):
    rooms = {"hall": {"name": "Hall", "adjacent": []}}
    positions = {eid: "hall" for eid in entity_names_by_id}
    positions["Hinami"] = "hall"
    return {
        "location": "Keep", "time": "night",
        "rooms": rooms, "positions": positions,
        "entities": {
            eid: {"name": name, "kind": "person",
                  "description": f"{name}, standing in the hall."}
            for eid, name in entity_names_by_id.items()
        },
        "attire": {}, "overlays": {},
    }


class TestFoldFollowsTheBody:
    def test_a_renamed_entity_keeps_its_history(self):
        """The record was bound to entity e1 while it was still 'the guard';
        the entity now answers to Mara. One fold pass re-keys the record to
        the body's current name, history intact, old spelling in aka."""
        scene = _scene({"e1": "Mara"})
        presences = {
            "the guard": {
                "first_turn": 0, "last_turn": 4, "entity_id": "e1",
                "dialogue_turns": [0, 1], "mention_turns": [3],
                "addressed_turns": [1],
                "sketch": {"role_hint": "A wary gate guard."},
            },
        }
        folded = _fold_duplicate_presences(presences, scene)
        assert len(folded) == 1 and _names(folded) == {"Mara"}
        rec = _rec(folded, "Mara")
        assert rec["dialogue_turns"] == [0, 1]
        assert rec["mention_turns"] == [3]
        assert rec["addressed_turns"] == [1]
        assert rec["sketch"]["role_hint"] == "A wary gate guard."
        assert "the guard" in rec.get("aka", [])

    def test_a_rename_split_ledger_merges_into_one_record(self):
        """The live failure: the renamed body already has a fresh record
        under the new name while the orphan keeps the history. Both are
        bound to the same entity id, so the fold merges them
        unconditionally -- one body, one record."""
        scene = _scene({"e1": "Mara"})
        presences = {
            "the guard": {
                "first_turn": 0, "last_turn": 4, "entity_id": "e1",
                "dialogue_turns": [0, 1], "mention_turns": [],
                "blurb": {"manner": "Clipped, watchful."},
            },
            "Mara": {
                "first_turn": 5, "last_turn": 6, "entity_id": "e1",
                "dialogue_turns": [5], "mention_turns": [6],
            },
        }
        folded = _fold_duplicate_presences(presences, scene)
        assert len(folded) == 1 and _names(folded) == {"Mara"}
        rec = _rec(folded, "Mara")
        assert sorted(rec["dialogue_turns"]) == [0, 1, 5]
        assert rec["mention_turns"] == [6]
        # The earliest record's frozen blurb survives.
        assert rec["blurb"]["manner"] == "Clipped, watchful."
        assert "the guard" in rec.get("aka", [])

    def test_an_unbound_record_binds_when_the_scene_answers_unambiguously(
        self,
    ):
        scene = _scene({"e9": "Dalek"})
        folded = _fold_duplicate_presences(
            {"The Dalek": {"first_turn": 0, "last_turn": 0,
                           "dialogue_turns": [], "mention_turns": []}},
            scene,
        )
        (rec,) = folded.values()
        assert rec.get("entity_id") == "e9"

    def test_two_bodies_never_bind_and_never_merge(self):
        """The crowd guard survives the entity keying: with two Daleks in
        the room, neither spelling can be bound to a body, so nothing
        merges and nothing collects the other's history."""
        scene = _scene({"e1": "Dalek", "e2": "Dalek"})
        presences = {
            "A Dalek": {"first_turn": 0, "last_turn": 2,
                        "dialogue_turns": [0], "mention_turns": []},
            "The Dalek": {"first_turn": 1, "last_turn": 2,
                          "dialogue_turns": [1], "mention_turns": []},
        }
        folded = _fold_duplicate_presences(presences, scene)
        assert len(folded) == 2
        assert _names(folded) == {"A Dalek", "The Dalek"}
        assert not _rec(folded, "A Dalek").get("entity_id")
        assert not _rec(folded, "The Dalek").get("entity_id")

    def test_a_voice_through_a_door_still_folds_by_name_alone(self):
        """The fallback the design note names: no entity, so the article
        fold is all there is, and it still works."""
        scene = _scene({})
        presences = {
            "A Whisper": {"first_turn": 0, "last_turn": 1,
                          "dialogue_turns": [0], "mention_turns": []},
            "The Whisper": {"first_turn": 2, "last_turn": 3,
                            "dialogue_turns": [2], "mention_turns": []},
        }
        folded = _fold_duplicate_presences(presences, scene)
        assert len(folded) == 1 and _names(folded) == {"A Whisper"}
        assert sorted(_rec(folded, "A Whisper")["dialogue_turns"]) == [0, 2]


class TestResolveFollowsTheBody:
    def test_a_new_spelling_files_under_the_bound_record(self):
        scene = _scene({"e1": "Mara"})
        presences = {
            "the guard": {"first_turn": 0, "last_turn": 4,
                          "entity_id": "e1", "dialogue_turns": [0]},
        }
        bound = presences["the guard"]
        key = _resolve_or_mint_presence("Mara", presences, scene)
        assert presences[key] is bound


class TestTrackingSurvivesARename(object):
    def test_history_and_new_dialogue_land_on_one_record(self, temp_db):
        """End to end: the guard spoke on beats 0-1, the Director renamed
        the entity to Mara, and Mara speaks on beat 2. One record, keyed by
        the current name, carrying all three dialogue turns -- and no
        orphan left behind to react beside her."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _scene({"e1": "Mara"}))
        temp_db.wset(chat_id, "background_presences", {
            "the guard": {
                "first_turn": 0, "last_turn": 1, "entity_id": "e1",
                "dialogue_turns": [0, 1], "mention_turns": [],
                "sketch": {"role_hint": "A wary gate guard.",
                           "station_room": "hall"},
            },
        })

        ctx = _ctx(temp_db, chat_id, 2, {
            "resolved_event": "Mara lowers her spear and answers.",
            "dialogue_log": [{"speaker": "Mara",
                              "exact_quote": "State your business."}],
            "state_diff": {},
        })
        track_background_presences(ctx, nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert len(presences) == 1 and _names(presences) == {"Mara"}
        rec = _rec(presences, "Mara")
        assert sorted(rec["dialogue_turns"]) == [0, 1, 2]
        assert rec["sketch"]["role_hint"] == "A wary gate guard."
        assert "the guard" in rec.get("aka", [])

    def test_a_fresh_harvest_binds_to_its_scene_body(self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _scene({"e7": "Old Tom"}))

        ctx = _ctx(temp_db, chat_id, 1, {
            "resolved_event": "Old Tom waves from the hall.",
            "dialogue_log": [{"speaker": "Old Tom",
                              "exact_quote": "Evenin'."}],
            "state_diff": {},
        })
        track_background_presences(ctx, nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert _rec(presences, "Old Tom").get("entity_id") == "e7"

    def test_mentions_of_the_former_name_accrue_to_the_renamed_record(
        self, temp_db
    ):
        """The prose will not switch spellings overnight; 'the guard' in a
        later resolved_event still means her."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _scene({"e1": "Mara"}))
        temp_db.wset(chat_id, "background_presences", {
            "Mara": {
                "first_turn": 0, "last_turn": 4, "entity_id": "e1",
                "dialogue_turns": [0], "mention_turns": [],
                "aka": ["the guard"],
            },
        })

        ctx = _ctx(temp_db, chat_id, 5, {
            "resolved_event": "The guard watches the gate in silence.",
            "dialogue_log": [],
            "state_diff": {},
        })
        track_background_presences(ctx, nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert 5 in _rec(presences, "Mara")["mention_turns"]


class TestPromotionSweepsEverySpellingOfTheBody:
    def test_promoting_the_new_name_removes_the_orphan(
        self, temp_db, monkeypatch
    ):
        """The failure the re-key exists to prevent: promotion under the new
        name must not leave the old-spelling record behind as a tracked
        passer-by that can be picked to react against its own sheet. The
        orphan shares no string identity with "Mara" -- only the entity
        binding (and the aka trail) connects them."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _scene({"e1": "Mara"}))
        temp_db.wset(chat_id, "background_presences", {
            "Mara": {"first_turn": 5, "last_turn": 9, "entity_id": "e1",
                     "dialogue_turns": [5, 7, 9], "mention_turns": [],
                     "aka": ["the guard"]},
            "the guard": {"first_turn": 0, "last_turn": 4, "entity_id": "e1",
                          "dialogue_turns": [0, 1], "mention_turns": []},
        })

        def fake_draft(cid, presence_name):
            return {"sheet": {"identity": {"name": "Mara"}},
                    "memory_seeds": [], "evidence_turns": [5]}

        monkeypatch.setattr(importers, "draft_promoted_character", fake_draft)

        promote_background_character(chat_id, "Mara")

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert _rec(presences, "Mara") is None
        assert _rec(presences, "the guard") is None
        assert "Mara" not in _names(presences)
        assert "the guard" not in _names(presences)
