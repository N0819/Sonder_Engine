"""A tracked person the story has not named draws ONE permanent name.

J2/J2a: the presence ledger keeps people the story never named (an id-shaped
string standing where a name should). The generator (`story/naming.py`) mints
a name from the story's OWN naming law -- authored profile, Charter laws, or
names harvested from cast and lorebook -- never from a fixed default table,
and the mint is a WRITE performed by the ledger's one writer
(`_mint_missing_presence_names` in persist/commit_background.py): minted
once, stored on the record, read thereafter. These tests pin the contract:

- a minted name persists across beats;
- a second mention of the same presence does not mint again;
- a replacement (a new body, a new record) draws a NEW name, and the old
  name stays with the old presence;
- the generator follows the story's configured convention -- authored
  format/pools, or the harvested vocabulary -- and mints NOTHING when the
  story yields no law (the engine never invents a culture);
- the mint is deterministic in (chat, presence uid), so replaying a
  rolled-back commit lands the same name for the same person;
- only a person is named: a thing, or an undecided presence, stays unnamed.
"""

from __future__ import annotations

import copy
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import (
    _mint_missing_presence_names,
    _mint_presence_uid,
    presence_display_name,
    presence_is_unnamed,
    presence_record_for,
    track_background_presences,
)
from story.naming import (
    harvested_naming_profile,
    minted_presence_name,
    story_naming_lanes,
)

# 16-hex strings the shape a raw entity id takes when it lands where a name
# belongs (the ledger measured three of these tracked as "names").
ID_SHAPED_A = "3f9ac2d47b1e5a08"
ID_SHAPED_B = "8c1d2e3f4a5b6c7d"

PROFILE = {
    "given": ["Aster", "Brin", "Coll", "Dara"],
    "family": ["Moor", "Vane"],
}


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


def _scene(entities=None):
    entities = entities or {}
    return {
        "location": "x", "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {eid: "hall" for eid in entities},
        "entities": {eid: dict(edef) for eid, edef in entities.items()},
        "attire": {}, "overlays": {},
    }


def _speaker_beat(speaker, line="A line."):
    return {
        "resolved_event": "Someone speaks.",
        "dialogue_log": [{"speaker": speaker, "line": line}],
        "state_diff": {},
    }


def _pool_tokens():
    return {t.casefold() for t in PROFILE["given"] + PROFILE["family"]}


def _only_record(presences):
    assert len(presences) == 1, presences
    return next(iter(presences.items()))


# ---------------------------------------------------------------------------
# the mint is a write: it persists, and a second mention never re-mints
# ---------------------------------------------------------------------------

class TestAMintedNamePersistsAcrossBeats:
    def test_an_unnamed_speaker_is_named_from_the_authored_law(self, temp_db):
        """An id-shaped dialogue speaker is tracked as a person with no name;
        the commit writer mints one from the authored pools and WRITES it."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        temp_db.wset(chat_id, "scene", _scene())

        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        key, record = _only_record(presences)
        assert not presence_is_unnamed(key, record)
        name = presence_display_name(key, record)
        assert name and name != ID_SHAPED_A
        assert {t.casefold() for t in name.split()} <= _pool_tokens()
        # every pre-mint spelling still resolves to the record
        k2, r2 = presence_record_for(presences, ID_SHAPED_A)
        assert k2 == key
        k3, r3 = presence_record_for(presences, name)
        assert k3 == key

    def test_the_name_survives_the_next_beat_unchanged(self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        temp_db.wset(chat_id, "scene", _scene())
        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)
        key, record = _only_record(
            temp_db.wget(chat_id, "background_presences", {}))
        first_name = presence_display_name(key, record)

        # a beat this presence takes no part in
        track_background_presences(
            _ctx(temp_db, chat_id, 2, {
                "resolved_event": "The rain keeps falling.",
                "dialogue_log": [], "state_diff": {},
            }), nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        key2, record2 = _only_record(presences)
        assert key2 == key
        assert presence_display_name(key2, record2) == first_name


class TestASecondMentionDoesNotMintAgain:
    def test_the_same_speaker_again_is_one_record_one_name(self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        temp_db.wset(chat_id, "scene", _scene())
        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)
        key, record = _only_record(
            temp_db.wget(chat_id, "background_presences", {}))
        first_name = presence_display_name(key, record)

        # the same channel hands the same raw spelling back
        track_background_presences(
            _ctx(temp_db, chat_id, 2, _speaker_beat(ID_SHAPED_A)), nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        key2, record2 = _only_record(presences)
        assert key2 == key
        assert presence_display_name(key2, record2) == first_name
        assert record2.get("dialogue_turns") == [1, 2]

    def test_a_mention_by_the_minted_name_reaches_the_same_record(
            self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        temp_db.wset(chat_id, "scene", _scene())
        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)
        key, record = _only_record(
            temp_db.wget(chat_id, "background_presences", {}))
        name = presence_display_name(key, record)

        track_background_presences(
            _ctx(temp_db, chat_id, 2, {
                "resolved_event": "%s wipes down the counter." % name,
                "dialogue_log": [], "state_diff": {},
            }), nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        key2, record2 = _only_record(presences)
        assert key2 == key
        assert presence_display_name(key2, record2) == name
        assert 2 in (record2.get("mention_turns") or [])


# ---------------------------------------------------------------------------
# a replacement is a new person, never a rename
# ---------------------------------------------------------------------------

class TestAReplacementDrawsANewName:
    def test_new_body_new_record_new_name_old_name_stays(self, temp_db):
        """The one legitimate 'rename' is not a rename: a new body takes the
        vacated post as a NEW record with its own name, and the old name
        stays with the old presence."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        temp_db.wset(
            chat_id, "scene",
            _scene({"e1": {"name": ID_SHAPED_A, "kind": "person"}}))
        track_background_presences(
            _ctx(temp_db, chat_id, 1, {
                "resolved_event": "A figure stands the watch.",
                "dialogue_log": [],
                "state_diff": {"entities": {
                    "e1": {"kind": "person", "name": ID_SHAPED_A}}},
            }), nonce=0)
        presences = temp_db.wget(chat_id, "background_presences", {})
        old_key, old_record = _only_record(presences)
        old_name = presence_display_name(old_key, old_record)
        assert old_name and not presence_is_unnamed(old_key, old_record)

        # the watch changes: the old body is gone, a new one stands the post
        temp_db.wset(
            chat_id, "scene",
            _scene({"e2": {"name": ID_SHAPED_B, "kind": "person"}}))
        track_background_presences(
            _ctx(temp_db, chat_id, 2, {
                "resolved_event": "A different figure takes over.",
                "dialogue_log": [],
                "state_diff": {"entities": {
                    "e2": {"kind": "person", "name": ID_SHAPED_B}}},
            }), nonce=0)

        presences = temp_db.wget(chat_id, "background_presences", {})
        assert len(presences) == 2
        new_key = next(k for k in presences if k != old_key)
        new_name = presence_display_name(new_key, presences[new_key])
        assert new_name and new_name != old_name
        assert presence_display_name(old_key, presences[old_key]) == old_name
        assert presences[old_key].get("entity_id") == "e1"
        assert presences[new_key].get("entity_id") == "e2"


# ---------------------------------------------------------------------------
# the configured convention, not a fixed default
# ---------------------------------------------------------------------------

class TestTheGeneratorFollowsTheConfiguredConvention:
    def test_a_family_first_format_is_honoured(self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", {
            "given": ["Tam", "Ren", "Sova"],
            "family": ["Kesh"],
            "name_format": "{family} {given}",
        })
        temp_db.wset(chat_id, "scene", _scene())
        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)
        key, record = _only_record(
            temp_db.wget(chat_id, "background_presences", {}))
        name = presence_display_name(key, record)
        parts = name.split()
        assert parts[0] == "Kesh"
        assert parts[1] in {"Tam", "Ren", "Sova"}

    def test_without_an_authored_law_the_harvest_speaks(self, temp_db):
        """No authored profile, no Charter: the law is the story's own
        names -- the registered cast's given/family vocabulary -- and the
        minted name is made of those parts without duplicating anyone."""
        chat_id = _make_chat(temp_db)
        cast_names = ["Alden Rook", "Mira Senn", "Petra Volk"]
        for cast_name in cast_names:
            char_id = temp_db.qi(
                "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                (cast_name, "{}", time.time()))
            temp_db.qi(
                "INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)",
                (chat_id, char_id))
        temp_db.wset(chat_id, "scene", _scene())

        lanes, source = story_naming_lanes(chat_id)
        assert source == "harvested"

        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)
        key, record = _only_record(
            temp_db.wget(chat_id, "background_presences", {}))
        name = presence_display_name(key, record)
        assert name and name != ID_SHAPED_A
        harvested = {t.casefold() for cn in cast_names for t in cn.split()}
        assert {t.casefold() for t in name.split()} <= harvested
        assert name not in cast_names

    def test_no_law_means_no_mint_and_the_person_is_still_kept(
            self, temp_db):
        """The engine never invents a culture: with nothing to draw on, the
        presence stays unnamed -- but tracked, with full state (one
        population, not a lesser class)."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "scene", _scene())
        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)
        presences = temp_db.wget(chat_id, "background_presences", {})
        key, record = _only_record(presences)
        assert presence_is_unnamed(key, record)
        assert record.get("dialogue_turns") == [1]

    def test_an_exhausted_pool_stays_honestly_unnamed(self, temp_db):
        """Every candidate the law can produce is already somebody: minting
        nothing beats minting a collision or a disambiguated non-name."""
        chat_id = _make_chat(temp_db)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("Alden Rook", "{}", time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)",
                   (chat_id, char_id))
        temp_db.wset(chat_id, "naming_profile",
                     {"given": ["Alden"], "family": ["Rook"]})
        temp_db.wset(chat_id, "scene", _scene())
        track_background_presences(
            _ctx(temp_db, chat_id, 1, _speaker_beat(ID_SHAPED_A)), nonce=0)
        key, record = _only_record(
            temp_db.wget(chat_id, "background_presences", {}))
        assert presence_is_unnamed(key, record)

    def test_charter_law_is_a_lane_and_authored_outranks_it(self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "charters", {"items": {"hall": {
            "state": {"naming": {"given": ["Ori", "Ude"],
                                 "family": ["Ket"]}}}}})
        lanes, source = story_naming_lanes(chat_id)
        assert source == "charters"
        assert lanes[0]["given"] == ["Ori", "Ude"]

        temp_db.wset(chat_id, "naming_profile", PROFILE)
        lanes, source = story_naming_lanes(chat_id)
        assert source == "authored"
        assert lanes[0]["given"] == PROFILE["given"]

    def test_harvest_rejects_phrases_keys_and_ids(self, temp_db):
        """Evidence hygiene: a role phrase, a digit-bearing key and a raw id
        contribute nothing; honorifics and appended roles are shed."""
        chat_id = _make_chat(temp_db)
        for cast_name in ("Dr. Elena Voss — Resident Psychiatrist",
                          "The Keeper of the Gate",
                          "unit_7_drone", ID_SHAPED_A,
                          "Marcus Boyle"):
            char_id = temp_db.qi(
                "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                (cast_name, "{}", time.time()))
            temp_db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)",
                       (chat_id, char_id))
        profile = harvested_naming_profile(chat_id)
        assert profile["given"] == ["Elena", "Marcus"]
        assert profile["family"] == ["Boyle", "Voss"]


# ---------------------------------------------------------------------------
# determinism, and who may be named at all
# ---------------------------------------------------------------------------

class TestTheMintIsDeterministic:
    def test_replaying_the_same_ledger_lands_the_same_names(self, temp_db):
        """A rolled-back commit replayed, or a reroll, must agree with the
        write it replaces: the candidate is a function of (chat, uid)."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        scene = _scene()
        key = _mint_presence_uid("entity:e7")
        ledger = {key: {"uid": key, "name": ID_SHAPED_A,
                        "dialogue_turns": [1]}}
        first = _mint_missing_presence_names(
            chat_id, copy.deepcopy(ledger), scene)
        second = _mint_missing_presence_names(
            chat_id, copy.deepcopy(ledger), scene)
        assert first and first == second

    def test_different_presences_draw_different_names(self, temp_db):
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        a = minted_presence_name(chat_id, _mint_presence_uid("entity:e1"))
        b = minted_presence_name(chat_id, _mint_presence_uid("entity:e2"),
                                 used=[a])
        assert a and b and a != b


class TestOnlyAPersonIsNamed:
    def test_a_thing_and_an_undecided_presence_stay_unnamed(self, temp_db):
        """A name is a person's to carry. An inert entity's record and an
        undecided one (a kind neither animate nor inert) both stay unnamed
        until the story -- or blurb_mint's `nature` -- settles what they
        are."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        scene = _scene({
            "e1": {"name": "", "kind": "furniture"},
            "e2": {"name": "", "kind": "device"},
        })
        k1 = _mint_presence_uid("entity:e1")
        k2 = _mint_presence_uid("entity:e2")
        ledger = {
            k1: {"uid": k1, "name": "", "entity_id": "e1"},
            k2: {"uid": k2, "name": "", "entity_id": "e2"},
        }
        minted = _mint_missing_presence_names(chat_id, ledger, scene)
        assert minted == {}
        assert presence_is_unnamed(k1, ledger[k1])
        assert presence_is_unnamed(k2, ledger[k2])

    def test_a_role_named_presence_is_never_renamed(self, temp_db):
        """A presence the story named by role keeps that name: renaming it
        would be the engine reaching for the field, the act permanence
        forbids."""
        chat_id = _make_chat(temp_db)
        temp_db.wset(chat_id, "naming_profile", PROFILE)
        scene = _scene({"e1": {"name": "night porter", "kind": "person"}})
        key = _mint_presence_uid("entity:e1")
        ledger = {key: {"uid": key, "name": "night porter",
                        "entity_id": "e1"}}
        minted = _mint_missing_presence_names(chat_id, ledger, scene)
        assert minted == {}
        assert ledger[key]["name"] == "night porter"
