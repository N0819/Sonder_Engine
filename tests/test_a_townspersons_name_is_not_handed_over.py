"""A body without a card is still somebody whose name must be earned.

Playerless Aldermill round 6 (2026-09-23), idx 2: Emory's own orientation
frame (`perception.spatial_frame.ahead_entity`) named the man in front of him
"Master Leofelric Fenstonwell". He had never been told it -- not in his view,
his observations, his memories, or his `known` ledger -- and his next want was
"Answer Master Fenstonwell". `observer_label_fn` gated only bodies with a
character card and waved every other name through as a prop, and a charter
townsperson (or any person the Director minted) is a body with no card.
"""
import json
import time

from agents.common import observer_label_fn


def _chat(db, known=None):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Aldermill", "", time.time()))
    if known is not None:
        db.wset(cid, "known", known)
    return {"id": cid, "persona_id": None}


SCENE = {
    "rooms": {"mill_floor": {"name": "Mill Floor"}},
    "positions": {"Emory Vane": "mill_floor",
                  "Master Leofelric Fenstonwell": "mill_floor",
                  "grain_hopper": "mill_floor"},
    "entities": {
        "Master Leofelric Fenstonwell": {
            "name": "Master Leofelric Fenstonwell", "kind": "person",
            "charter_ref": {"charter": "aldermill_mill",
                            "body": "master_miller:0001"}},
        "grain_hopper": {"name": "grain hopper", "kind": "fixture"}},
}


def test_a_townsperson_he_has_not_met_is_labelled_not_named(temp_db):
    chat = _chat(temp_db)
    label = observer_label_fn(chat, "Emory Vane", [], scene=SCENE)
    seen_as = label("Master Leofelric Fenstonwell")
    assert "Fenstonwell" not in seen_as and "Leofelric" not in seen_as
    assert seen_as.strip()


def test_a_prop_is_left_as_it_is(temp_db):
    chat = _chat(temp_db)
    label = observer_label_fn(chat, "Emory Vane", [], scene=SCENE)
    assert label("grain_hopper") == "grain_hopper"


def test_a_townsperson_he_knows_keeps_his_name(temp_db):
    chat = _chat(temp_db, known={"Emory Vane": ["Master Leofelric Fenstonwell"]})
    label = observer_label_fn(chat, "Emory Vane", [], scene=SCENE)
    assert label("Master Leofelric Fenstonwell") == "Master Leofelric Fenstonwell"


def test_the_label_is_the_look_the_view_uses(temp_db):
    """The presence ledger's look, the one perception labels him from, so the
    frame and the view describe one man in one way."""
    chat = _chat(temp_db)
    temp_db.wset(chat["id"], "background_presences", {"p_1": {
        "name": "Master Leofelric Fenstonwell",
        "sketch": {"appearance": "a seasoned heavy-framed miller, dust about the eyes"}}})
    label = observer_label_fn(chat, "Emory Vane", [], scene=SCENE)
    assert "heavy-framed" in label("Master Leofelric Fenstonwell")


def test_a_name_used_as_a_key_is_scrubbed_like_one_used_as_a_value():
    """`scrub_names_deep` rewrote every string VALUE and left every KEY, so a
    section keyed by who it was about handed the name over whole."""
    from agents.common import scrub_names_deep
    scrub = lambda text: text.replace("Leofelric Fenstonwell", "the miller")
    out = scrub_names_deep({"Leofelric Fenstonwell": {"said": "Leofelric Fenstonwell nods"},
                            "the miller": {"said": "a second body"}}, scrub)
    assert "Leofelric Fenstonwell" not in str(out)
    assert out["the miller"] == {"said": "a second body"} or \
        out["the miller"] == {"said": "the miller nods"}
    assert len(out) == 2
