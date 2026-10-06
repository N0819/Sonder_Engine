"""Who an older memory had in it, backfilled (`persist/about_backfill.py`).

Rows minted before v43 carry no `memories.about`, so a ponder by a name the
mind learned later cannot reach them -- the row of a first meeting reads "the
young woman" (docs/experiments/CHARACTER_LOOKUPS_2026_10_05.md §4). The
backfill tags them by the mint's own rule, fed from what the turn left
behind, and puts the tags back after a checkpoint restore.
"""

from __future__ import annotations

import json
import time

import pytest

from story.character_schema import default_character_data


def _char(temp_db, chat_id, name):
    sheet = default_character_data(name)
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
                         (name, json.dumps(sheet), "{}", time.time(), sheet["identity"]["uid"]))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", "{}"))
    return char_id


@pytest.fixture
def story(temp_db):
    persona = temp_db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                         ("Hinami", json.dumps({"name": "Hinami"}), "{}"))
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
                         ("Shrine", "", time.time(), persona))
    mara, oren, vell = (_char(temp_db, chat_id, n) for n in ("Mara", "Oren", "Vell"))
    temp_db.wset(chat_id, "known", {"Mara": ["Oren", "Hinami"]})
    return {"chat": chat_id, "mara": mara, "oren": oren, "vell": vell}


def _turn(temp_db, s, idx, positions, *, dialogue=(), view="", conditions=()):
    """Turn `idx`: the world as it begins (checkpoint `idx`), its stored
    resolve and outcome steps."""
    from agents.storage import save_step
    from persist.checkpoints import ensure_checkpoint, snapshot_blob
    temp_db.wset(s["chat"], "scene", {"rooms": {"hall": {"name": "Hall"}, "yard": {"name": "Yard"}},
                                      "positions": dict(positions)})
    temp_db.qi("DELETE FROM world_conditions WHERE chat_id=?", (s["chat"],))
    for n, (subject, payload) in enumerate(conditions):
        temp_db.qi("INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,started_at,payload,active) "
                   "VALUES(?,?,?,?,?,?,1)", (f"c{idx}{n}", s["chat"], subject, "physical_disguise",
                                              float(n), json.dumps(payload)))
    ensure_checkpoint(s["chat"], idx, blob=snapshot_blob(s["chat"]))
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                         (s["chat"], idx, "", time.time()))
    save_step(turn_id, "director_resolve", "resolve", 1, {"dialogue_log": list(dialogue)})
    save_step(turn_id, "perception_outcome", "outcome", 2, {"views": {str(s["mara"]): view}})
    return turn_id


def _row(temp_db, s, turn_id, idx, kind, content, key):
    from mind.memory import add_memories_batch
    add_memories_batch([{"chat_id": s["chat"], "char_id": s["mara"], "turn_id": turn_id, "turn_idx": idx,
                         "kind": kind, "category": "episode" if kind == "episodic" else kind,
                         "provenance": "witnessed", "salience": 0.6, "content": content,
                         "event_key": key, "encoded_at_seconds": float(idx) * 60}])


def _about(temp_db, key):
    return json.loads(temp_db.q("SELECT about FROM memories WHERE event_key=?", (key,), one=True)["about"] or "null")


def test_rows_are_tagged_by_the_mint_rule_from_what_the_turn_left(temp_db, story):
    from persist.about_backfill import backfill_chat
    s = story
    call = {"speaker": "Hinami", "intended_target": "Mara", "exact_quote": '"Come out!"'}
    t0 = _turn(temp_db, s, 0, {"Mara": "hall", "Oren": "hall", "Hinami": "yard"},
               dialogue=[call], view='A voice calls "Come out!" from the yard.')
    _row(temp_db, s, t0, 0, "episodic", 'I heard the young woman call "Come out!"', "e0")
    _row(temp_db, s, t0, 0, "dialogue", 'The young woman said "Come out!" to me', "d0")
    _row(temp_db, s, t0, 0, "inference", "The man by the fire is waiting for someone.", "i0")
    t1 = _turn(temp_db, s, 1, {"Mara": "hall", "Oren": "yard", "Hinami": "yard"})
    _row(temp_db, s, t1, 1, "episodic", "I sat alone in the hall.", "e1")
    counts = backfill_chat(s["chat"])
    # Who stood in her room and was seen. The voice from the yard is heard and
    # not seen: never a face the mind can tie to the name it learns (the
    # mint's rule since 2026-10-06, `world.spatial.sighted_level`).
    assert _about(temp_db, "e0") == ["Oren"]
    assert _about(temp_db, "d0") == ["Oren"]
    assert _about(temp_db, "i0") == ["Oren"]
    # Nobody else there is an answer too, written once.
    assert _about(temp_db, "e1") == []
    assert counts == {"tagged": 3, "nobody": 1, "skipped": 0}
    assert backfill_chat(s["chat"]) == {"tagged": 0, "nobody": 0, "skipped": 0}


def test_a_body_the_mind_could_not_recognise_stays_out_of_the_tag(temp_db, story):
    """The mint's rule: a masked stranger is never linked to the face under
    the mask -- by the disguise active at that turn, not today's."""
    from persist.about_backfill import backfill_chat
    s = story
    mask = {"presented_appearance": "a hooded traveller", "conceals_identity": True}
    t0 = _turn(temp_db, s, 0, {"Mara": "hall", "Vell": "hall", "Oren": "hall"},
               conditions=[("Vell", mask)])
    _row(temp_db, s, t0, 0, "episodic", "A hooded traveller sat with us.", "e0")
    _turn(temp_db, s, 1, {"Mara": "hall", "Vell": "hall"})      # the disguise is gone now
    backfill_chat(s["chat"])
    assert _about(temp_db, "e0") == ["Oren"]


def test_the_tag_is_where_people_stood_as_the_beat_began(temp_db, story):
    """Measured on the owner's db: the mint's people match the checkpoint the
    turn began with in 106 of 106 rows, the one after it in 104 of 110."""
    from persist.about_backfill import backfill_chat
    s = story
    t0 = _turn(temp_db, s, 0, {"Mara": "hall", "Oren": "hall"})
    _row(temp_db, s, t0, 0, "episodic", "Oren was here, then he left.", "e0")
    _turn(temp_db, s, 1, {"Mara": "hall", "Oren": "yard"})
    backfill_chat(s["chat"])
    assert _about(temp_db, "e0") == ["Oren"]


def test_seeded_prehistory_and_tagged_rows_are_left_alone(temp_db, story):
    from persist.about_backfill import backfill_chat
    s = story
    t0 = _turn(temp_db, s, 0, {"Mara": "hall", "Oren": "hall"})
    _row(temp_db, s, None, 0, "episodic", "Long ago, on another shore.", "greeting_seed:abc")
    _row(temp_db, s, t0, 0, "episodic", "Already tagged.", "e0")
    temp_db.qi("UPDATE memories SET about=? WHERE event_key='e0'", (json.dumps(["Someone"]),))
    backfill_chat(s["chat"])
    assert temp_db.q("SELECT about FROM memories WHERE event_key='greeting_seed:abc'", one=True)["about"] == ""
    assert _about(temp_db, "e0") == ["Someone"]


def test_a_restore_puts_the_tags_back_before_anything_recalls(temp_db, story):
    """A restore puts rows back as the snapshot held them -- untagged, for a
    snapshot older than the tag -- and a rerun recalls the moment it returns."""
    from persist.about_backfill import backfill_chat
    from persist.checkpoints import restore_checkpoint
    s = story
    t0 = _turn(temp_db, s, 0, {"Mara": "hall", "Oren": "hall"})
    _row(temp_db, s, t0, 0, "episodic", "Oren by the fire.", "e0")
    _turn(temp_db, s, 1, {"Mara": "hall", "Oren": "hall"})     # checkpoint 1 holds e0 untagged
    backfill_chat(s["chat"])
    assert _about(temp_db, "e0") == ["Oren"]
    restore_checkpoint(s["chat"], 1)
    assert _about(temp_db, "e0") == ["Oren"]


def test_the_whole_database_in_one_pass(temp_db, story):
    from persist.about_backfill import backfill_all
    s = story
    t0 = _turn(temp_db, s, 0, {"Mara": "hall", "Oren": "hall"})
    _row(temp_db, s, t0, 0, "episodic", "Oren by the fire.", "e0")
    done = backfill_all()
    assert done["chats"] == 1 and done["tagged"] == 1
    assert backfill_all()["chats"] == 0


def test_a_body_shut_in_a_wardrobe_is_never_tagged_for_a_mind_that_did_not_see_it(temp_db, story):
    from persist.about_backfill import backfill_chat
    from persist.checkpoints import ensure_checkpoint, snapshot_blob
    from agents.storage import save_step
    s = story
    temp_db.wset(s["chat"], "scene", {"rooms": {"hall": {"name": "Hall"}},
                                      "positions": {"Mara": "hall", "Oren": "hall", "wardrobe": "hall"},
                                      "contained": {"Oren": {"in": "wardrobe", "mode": "inside"}}})
    ensure_checkpoint(s["chat"], 0, blob=snapshot_blob(s["chat"]))
    t0 = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                    (s["chat"], 0, "", time.time()))
    save_step(t0, "director_resolve", "resolve", 1, {"dialogue_log": []})
    _row(temp_db, s, t0, 0, "episodic", "I undressed and went to bed.", "e0")
    backfill_chat(s["chat"])
    assert _about(temp_db, "e0") == ["wardrobe"], "the wardrobe was seen; the man in it was not"
