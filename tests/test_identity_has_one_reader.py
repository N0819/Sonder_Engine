"""One reader for a character sheet's identity (review 2026-09-07 B12).

A stored sheet is only REPAIRED for whoever normalizes it.
`repair_character_shape` lifts a name, an alias list or a pronoun set that a
model parked at top level (or nested inside another section) back into
`identity`, and the legacy branch synthesizes the whole block from a legacy
card -- so every reader that reached into the stored blob for
`sheet["identity"]` saw the hollow sheet while every reader that normalized saw
the repaired one. The measured pair the finding names: `scene.cast_scene_context`
handed the director and mapping payloads an EMPTY alias list for exactly the
cards `agents.common.character_scene_keys` and `carriers._carriers` were
resolving BY alias.

The rule, in the engine's own vocabulary: identity -- name, aliases, pronouns --
is read through `character_schema.character_identity`, which normalizes. The uid
alone is read as authored -- from wherever the card authored it, identity block
or top level -- because normalization MINTS a fresh `char_<hex>` for a sheet
that has none and a minted uid is a different answer every call
(`cast_entity_id` owns the stable fallback).
"""

from __future__ import annotations

import json
import time

import pytest

from agents.character import _known_pronouns
from agents.common import character_scene_keys
from agents.narration import _cast_pronouns
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story import carriers
from story.character_schema import (
    character_identity,
    character_identity_from_text,
    default_character_data,
    default_persona_data,
)
from story.scene import cast_scene_context
from world import gaps, subjects


def _repaired_card(name="Kessa"):
    """A native card whose identity block a model left hollow.

    One member of the class, not the specification: the aliases and pronouns
    sit at top level, which is what `repair_character_shape` exists to lift
    back. A legacy card (no `identity` block at all) is the same defect by the
    other route and is covered below.
    """
    sheet = default_character_data(name)
    sheet["identity"].pop("aliases", None)
    sheet["identity"]["pronouns"] = {}
    sheet["aliases"] = ["The Ninth Bell", "Kess"]
    sheet["pronouns"] = {"subject": "she", "object": "her", "possessive": "her"}
    return sheet


def _legacy_card(name="Orren"):
    return {"name": name, "aliases": ["The Courier"],
            "pronouns": {"subject": "he", "object": "him", "possessive": "his"},
            "appearance": "A person of unremarkable appearance."}


def _row(sheet, row_id=1):
    return {"id": row_id, "sheet": json.dumps(sheet), "cstate": "{}"}


def _attach(db, sheet, name="Kessa"):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Test", "", time.time()))
    char_id = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                    (name, json.dumps(sheet), time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
          (cid, char_id))
    return cid, char_id


# --- the reader ------------------------------------------------------------

def test_the_reader_recovers_what_the_repair_lifted():
    ident = character_identity(_repaired_card())
    assert ident["aliases"] == ["The Ninth Bell", "Kess"]
    assert ident["pronouns"]["subject"] == "she"


def test_the_reader_recovers_a_legacy_card():
    ident = character_identity(_legacy_card())
    assert ident["aliases"] == ["The Courier"]
    assert ident["name"] == "Orren"


def test_the_uid_is_read_as_authored_never_minted():
    """Normalization mints a fresh uid per call; a minted one is a second
    spelling for one being that changes every time anything asks."""
    hollow = {"identity": {"name": "X"}, "psychology": {}}
    assert character_identity(hollow)["uid"] == ""
    assert character_identity(
        {"identity": {"name": "X", "uid": "kessa_9"}, "psychology": {}}
    )["uid"] == "kessa_9"


def test_aliases_arrive_as_a_list_of_strings():
    """A card that wrote a bare alias still arrives as a list: every caller
    folds or iterates this, and normalization keeps a native sheet's value
    verbatim."""
    sheet = default_character_data("Kessa")
    sheet["identity"]["aliases"] = "Kess"
    assert character_identity(sheet)["aliases"] == ["Kess"]


def test_the_text_keyed_reader_hands_back_a_private_copy():
    """The memo is shared; what a caller receives is theirs."""
    text = json.dumps(_repaired_card())
    first = character_identity_from_text(text)
    first["aliases"].append("mutated")
    assert character_identity_from_text(text)["aliases"] == \
        ["The Ninth Bell", "Kess"]


# --- the two representations agree -----------------------------------------

def test_the_dossier_and_the_scene_keys_agree_on_the_aliases():
    """The finding: `cast_scene_context` read the aliases off the stored blob
    while `character_scene_keys` read them normalized, so the director's own
    dossier denied every alias the rest of the turn was resolving by."""
    sheet = _repaired_card()
    dossier = cast_scene_context([_row(sheet)])[0]
    keys = character_scene_keys(sheet)
    assert dossier["aliases"] == ["The Ninth Bell", "Kess"]
    for alias in dossier["aliases"]:
        assert alias in keys


def test_the_dossier_reads_a_legacy_card_the_same_way():
    dossier = cast_scene_context([_row(_legacy_card())])[0]
    assert dossier["aliases"] == ["The Courier"]


def test_the_dossier_keeps_the_stable_entity_id():
    """The uid stays a RAW read: a uid-less card must keep the stable
    `character:<row id>` fallback, never a per-call mint."""
    sheet = _repaired_card()
    sheet["identity"].pop("uid", None)
    rows = [_row(sheet, row_id=7)]
    assert cast_scene_context(rows)[0]["entity_id"] == "character:7"
    assert cast_scene_context(rows)[0]["entity_id"] == \
        cast_scene_context(rows)[0]["entity_id"]


def test_the_carrier_ledger_answers_to_the_same_aliases(temp_db):
    """The other representation the finding names: a report lands in a body
    the carrier list found by alias."""
    sheet = _repaired_card()
    cid, _char_id = _attach(temp_db, sheet)
    scene = {"rooms": {"hall": {"name": "Hall"}},
             "positions": {"Kessa": "hall"}}
    entries = carriers._carriers(cid, None, scene)
    assert [e["aliases"] for e in entries if e.get("name") == "Kessa"] == \
        [["The Ninth Bell", "Kess"]]
    assert cast_scene_context([_row(sheet)])[0]["aliases"] == \
        ["The Ninth Bell", "Kess"]


def test_the_sighting_index_claims_every_alias():
    """`gaps.last_seen_update` indexes a co-present body by every spelling it
    answers to; a position keyed by an alias is otherwise skipped outright."""
    sheet = _repaired_card()
    sheet["identity"]["uid"] = "kessa_9"
    scene = {"rooms": {"hall": {"name": "Hall"}},
             "positions": {"Player": "hall", "The Ninth Bell": "hall"}}
    seen = gaps.last_seen_update(
        scene, [_row(sheet, row_id=3)], "Player", 1, 0.0)
    assert "kessa_9" in seen


def test_a_subject_resolves_by_a_recovered_alias(temp_db):
    sheet = _repaired_card()
    sheet["identity"]["uid"] = "kessa_9"
    cid, _char_id = _attach(temp_db, sheet)
    res = subjects.resolve_subject(cid, {}, "character", "The Ninth Bell")
    assert res and res.subject.id == "kessa_9"


def test_a_known_body_keeps_its_pronouns_in_both_payloads():
    """The character agent and the narrator each read pronouns off the same
    identity; a repaired card used to hand both of them nothing."""
    rows = [_row(_repaired_card())]
    known = _known_pronouns(rows, None, recognized=["Kessa"])
    assert known["Kessa"]["subject"] == "she"
    assert _cast_pronouns(rows)["Kessa"]["subject"] == "she"


def test_the_uid_survives_a_flattened_card():
    """A top-level uid is authored too. `repair_character_shape` rescues it
    into `identity` exactly like a top-level name or alias, so reading the
    identity block alone would drop the uid of the same flattened card this
    reader exists to rescue -- the uid `carriers._carriers` recovered by
    normalizing before there was one reader."""
    flat = {"uid": "char_deadbeef", "name": "Kess",
            "aliases": ["The Ninth Bell"],
            "appearance": "A person of unremarkable appearance."}
    assert "uid" not in (flat.get("identity") or {})
    assert character_identity(flat)["uid"] == "char_deadbeef"


# --- the pronoun readers, all of them --------------------------------------

def _pronoun_ctx(temp_db):
    """One repaired cast member, one player, one room.

    The card parks its pronouns at top level, which is the shape
    `repair_character_shape` exists to lift back -- so every reader that
    reaches into the stored blob for `identity.pronouns` gets nothing.
    """
    persona = default_persona_data("Hinami")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Hinami", json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Identity", "", time.time(), persona_id))
    sheet = _repaired_card()
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Kessa", json.dumps(sheet), "{}", time.time(), "char_kessa"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {"Hinami": "hall", "Kessa": "hall"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    temp_db.wset(chat_id, "known", {"Kessa": ["Hinami"]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Identity", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_establish = {"state_diff": {}, "entity_states": {},
                              "sensory_events": []}
    ctx.director_interpret = {
        "action": {"attempt": "waits", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [], "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    ctx.director_resolve = {"resolved_event": "The hall stands quiet.",
                            "state_diff": {}, "dialogue_log": [],
                            "dialogue_order": []}
    return ctx, char_id


def _perceivers_handed_to(monkeypatch, composer):
    """Capture the perceiver roster a perception stage hands its composer.

    Patched on `agents.perception`, which both DEFINES the composer and reads
    it -- the stage resolves the name in its own module globals.
    """
    import agents.perception as perception
    seen = []

    def fake(*a, **k):
        for value in list(a) + list(k.values()):
            if (isinstance(value, list) and value
                    and isinstance(value[0], dict) and "pronouns" in value[0]):
                seen.append(value)
                break
        return {"views": {}, "warnings": []}

    monkeypatch.setattr(perception, composer, fake)
    return seen


@pytest.mark.parametrize("stage,composer", [
    ("perception_establish", "_composer_establish"),
    ("perception_act", "_composer_act"),
    ("perception_outcome", "_composer_outcome"),
])
def test_the_perception_view_carries_a_repaired_bodys_pronouns(
        temp_db, monkeypatch, stage, composer):
    """The view the narrator falls back on is built HERE. Fixing the
    narrator's own reader while this one stayed raw would leave the two
    representations of one body's pronouns free to disagree."""
    import agents.perception as perception
    ctx, _char_id = _pronoun_ctx(temp_db)
    seen = _perceivers_handed_to(monkeypatch, composer)
    getattr(perception, stage)(ctx, nonce="n")
    assert seen, f"{stage} built no perceiver roster"
    kessa = [p for p in seen[0] if p.get("name") == "Kessa"]
    assert kessa, f"{stage} left the cast member out of the roster"
    assert kessa[0]["pronouns"].get("subject") == "she", (
        f"{stage} read pronouns off the stored blob: {kessa[0]['pronouns']!r}")


def test_the_director_roster_carries_a_repaired_bodys_pronouns(
        temp_db, monkeypatch):
    """`director_resolve`'s `_body_pronouns` roster exists because a pronoun
    was continued onto a he/him body across the room (PM22, 2026-09-05). A
    body the roster holds no paradigm for is that defect again."""
    import agents.director as director
    ctx, _char_id = _pronoun_ctx(temp_db)
    rosters = []

    # Patched on `agents.director`: the caller binds the guard by name at
    # import, so that is the module resolving it (patching `agents.common`,
    # where it is defined, would be inert here).
    def fake_check(resolved_event, silent_names, all_names, pronouns=None):
        rosters.append(dict(pronouns or {}))
        return []

    monkeypatch.setattr(director, "_check_character_speech_authority",
                        fake_check)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {
        "resolved_event": "The hall stands quiet.", "dialogue_log": []})
    director.director_resolve(ctx, nonce=0)

    assert rosters, "the speech-authority guard was never handed a roster"
    assert rosters[0].get("Kessa", {}).get("subject") == "she", (
        f"the roster read pronouns off the stored blob: {rosters[0]!r}")
