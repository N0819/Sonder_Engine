"""A structured field may not hand over an identity the prose is withholding.

Found in a 10-turn live run. Séverine asked the person across the desk for her
name twice, in dialogue -- "To whom do I have the pleasure of speaking this
evening?", then "Your name and the precise nature of your oversight here would
be most helpful" -- and was never answered. Her view said "the auditor". Her
memories said "the auditor". Her own relationship and mind-model claims said
"the auditor".

`perception.spatial_frame.ahead_entity` said "Auditor Dana Rennick", from beat
three. `spatial_digest` reads `scene.positions`, which is keyed by canonical
name, and nothing gated it. By beat eight she used the surname aloud.

Every other channel was checked and was clean -- perception views and
observations, the event summaries `recent_events_for_observer` returns,
memories, relationships, mind_models, `_known_pronouns`, `private_knowledge_for`.
The leak was the one field in the spatial payload that names a body rather than
a room.
"""
from __future__ import annotations

import json
import time

import pytest

from agents.common import observer_label_fn
from spatial import spatial_digest


PERSONA = {
    "identity": {"name": "Auditor Dana Rennick"},
    "embodiment": {"visible": {"summary":
        "A lean sharp-eyed woman in a pressed charcoal uniform."}},
}
CHAR = {
    "identity": {"name": "Séverine Moreau"},
    "embodiment": {"visible": {"summary": "A poised woman in dark travelling clothes."}},
}
SCENE = {
    "rooms": {"office": {"name": "Customs Office", "desc": "One lamp.",
                         "adjacent": []}},
    # Keyed by CANONICAL name, which is the convention and the reason the gate
    # has to exist somewhere.
    "positions": {"Séverine Moreau": "office", "Auditor Dana Rennick": "office"},
    "orientation": {"Séverine Moreau": {
        "came_from": None,
        "focus": {"kind": "entity", "ref": "Auditor Dana Rennick"}}},
}


def _fixture(temp_db, known=None):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("T", "", time.time()))
    pid = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                     ("Auditor Dana Rennick", json.dumps(PERSONA), "{}"))
    temp_db.qi("UPDATE chats SET persona_id=? WHERE id=?", (pid, cid))
    ch = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Séverine Moreau", json.dumps(CHAR), "{}", time.time()))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
               (cid, ch))
    temp_db.wset(cid, "known", known or {})
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    cast = [dict(r) for r in temp_db.q("SELECT * FROM characters WHERE id=?", (ch,))]
    return chat, cast


def _ahead(temp_db, known=None):
    chat, cast = _fixture(temp_db, known)
    label = observer_label_fn(chat, "Séverine Moreau", cast)
    return spatial_digest(SCENE, "Séverine Moreau", label_for=label).get("ahead_entity")


def test_a_stranger_ahead_is_described_not_named(temp_db):
    ahead = _ahead(temp_db)
    assert ahead, "the body ahead must still be reported -- she can SEE her"
    assert "Rennick" not in ahead
    assert "Dana" not in ahead
    assert ahead == "the lean sharp-eyed woman"


def test_someone_she_knows_is_named(temp_db):
    """The gate withholds an identity she has no way to have. It must not
    withhold one she does."""
    ahead = _ahead(temp_db, {"Séverine Moreau": ["Auditor Dana Rennick"]})
    assert ahead == "Auditor Dana Rennick"


def test_the_ungated_call_still_names_canonically(temp_db):
    """`label_for` is optional: internal geometry and the narrator's own frame
    (where the player's recognition is decided elsewhere) call it without one,
    and must keep the canonical key."""
    assert spatial_digest(SCENE, "Séverine Moreau").get("ahead_entity") \
        == "Auditor Dana Rennick"


def test_the_labeller_leaves_non_bodies_alone(temp_db):
    """A lamp is not an identity. Inventing a description for one would be a
    worse failure than the one being fixed."""
    chat, cast = _fixture(temp_db)
    label = observer_label_fn(chat, "Séverine Moreau", cast)
    assert label("lamp") == "lamp"
    assert label("ledger") == "ledger"
    assert label("") == ""


def test_the_observer_is_never_relabelled(temp_db):
    chat, cast = _fixture(temp_db)
    label = observer_label_fn(chat, "Séverine Moreau", cast)
    assert label("Séverine Moreau") == "Séverine Moreau"


def test_the_character_payload_passes_the_gate_in():
    """The wiring, not just the helper. `spatial_digest` defaults to ungated,
    so the fix is only real if the character stage supplies a labeller."""
    import inspect
    import agents.character as character
    src = inspect.getsource(character.character_step)
    assert "observer_label_fn" in src and "label_for=" in src, \
        "the character payload must gate spatial_digest's ahead_entity"
