"""A garment is a thing with an identity, not a string.

Two findings from the campaign-3 play runs of 2026-09-05, both in the seam
between the wardrobe ledger and the scene entity a removal mints.

* **PS15** (Salt Terraces, turn 0). Goggles the player was wearing were
  projected as SHED onto the haul road on the opening beat, by nobody, as
  `tinted_glass_goggles_pushed_up_on_the_hat_brim_mireille_adjani` with
  `state: {clothing, worn_by, shed: true}` -- and were gone from
  `attire.wearing` for the rest of the story. Nothing removed them. Two
  writes could each do it on their own and both are closed here: the
  sanitiser struck *"tinted glass goggles"* out of the wearing list for
  carrying the word `glass` while the regions still held them, so the
  reconcile read them as omitted; and an opening's `wearing` list is a
  STATEMENT of a wardrobe rather than a change to one, so a garment it does
  not mention has not been taken off by anybody.
* **PX10** (the masque, turns 6-7). The mask came off and minted
  `a_plain_black_half_mask_of_moulded_leather_..._ivo_sarn`; the next beat put
  it back on as `"black leather half-mask"`, a new garment matched by text,
  while the old object went on following the player from room to room. At turn
  20 the story contained two masks. PS15's second half is the same seam losing
  an article ("a wide straw hat" back as "wide straw hat").
"""

from __future__ import annotations

import time

from persist import commit
from story import attire
from core.pipeline_context import ChatData, PipelineContext, TurnData

_MASK = ("a plain black half-mask of moulded leather, covering brow, nose "
         "and cheekbones")
_COAT = "a borrowed dark green evening coat"


def _ctx(temp_db, *, idx=1, player_input="", resolved="", opening=False):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Identity", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, player_input, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Identity", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx,
                      player_input=player_input, created=time.time()),
        cast=[], input=player_input)
    if opening:
        ctx.director_establish = {"resolved_event": resolved}
    else:
        ctx.director_resolve = {"resolved_event": resolved}
    return ctx


def _result(ctx):
    return ctx.director_establish or ctx.director_resolve


def test_a_garment_is_not_struck_out_for_a_word_inside_its_name(temp_db):
    """PS15, the first of the two writes: `tinted glass goggles` carries the
    word `glass`, and the sanitiser read it as crockery."""
    goggles = "tinted glass goggles, pushed up on the hat brim"
    assert attire.sanitize_attire_items([goggles]) == [goggles]
    # ...and the refusal it exists for still refuses.
    assert attire.sanitize_attire_items(
        ["a wide straw hat", "the wooden chair", "a glass"]) \
        == ["a wide straw hat"]


def test_an_opening_that_omits_a_garment_has_not_taken_it_off(temp_db):
    """PS15. Turn 0, Salt Terraces: the establish's `wearing` list left the
    goggles out and they were shed onto the road by nobody."""
    goggles = "tinted glass goggles, pushed up on the hat brim"
    sc = {"positions": {"Mireille Adjani": "haul_road_head"},
          "entities": {},
          "attire": {"Mireille Adjani": attire.authored_entry(
              ["a wide straw hat", goggles, "a canvas coat"], [], None)}}
    ctx = _ctx(temp_db, idx=0, opening=True,
               resolved="Mireille stands on the haul road in hat and coat, "
                        "the light flat off the salt.")
    commit.apply_attire_diff(
        sc, {"attire": {"Mireille Adjani": {
            "wearing": ["a wide straw hat", "a canvas coat"]}}},
        ctx, _result(ctx))

    entry = sc["attire"]["Mireille Adjani"]
    assert goggles in entry["wearing"]
    assert not [eid for eid, ent in sc["entities"].items()
                if (ent.get("state") or {}).get("shed")]
    assert not [key for key in sc["positions"] if "goggle" in key]


def test_a_beat_that_names_the_garment_still_takes_it_off(temp_db):
    """The failure direction this must not have: a real removal still lands."""
    sc = {"positions": {"Ivo Sarn": "reception_room"},
          "entities": {},
          "attire": {"Ivo Sarn": attire.authored_entry([_MASK, _COAT],
                                                       [], None)}}
    ctx = _ctx(temp_db, resolved="Ivo lifts the half-mask away from his face.")
    commit.apply_attire_diff(
        sc, {"attire": {"Ivo Sarn": {"remove": [_MASK]}}}, ctx, _result(ctx))

    entry = sc["attire"]["Ivo Sarn"]
    assert _MASK not in entry["wearing"]
    shed = [ent for ent in sc["entities"].values()
            if (ent.get("state") or {}).get("shed")]
    assert len(shed) == 1
    assert shed[0]["state"]["garment"] == _MASK


def test_a_garment_taken_off_and_put_back_on_is_one_garment(temp_db):
    """PX10. The mask comes off at turn 6 and goes back on at turn 7 under a
    two-word paraphrase; the story must hold ONE mask."""
    sc = {"positions": {"Ivo Sarn": "reception_room"},
          "entities": {},
          "attire": {"Ivo Sarn": attire.authored_entry([_MASK, _COAT],
                                                       [], None)}}
    off = _ctx(temp_db, resolved="Ivo lifts the half-mask away from his face.")
    commit.apply_attire_diff(
        sc, {"attire": {"Ivo Sarn": {"remove": [_MASK]}}}, off, _result(off))
    assert len(sc["entities"]) == 1

    on = _ctx(temp_db, idx=2,
              resolved="He settles the black leather half-mask back over his "
                       "face.")
    commit.apply_attire_diff(
        sc, {"attire": {"Ivo Sarn": {"add": ["black leather half-mask"]}}},
        on, _result(on))

    entry = sc["attire"]["Ivo Sarn"]
    assert _MASK in entry["wearing"], entry["wearing"]
    assert "black leather half-mask" not in entry["wearing"]
    assert sc["entities"] == {}
    assert not [key for key in sc["positions"] if "mask" in key]


def test_a_different_garment_with_the_same_head_noun_is_not_the_shed_one(
        temp_db):
    """The loose tier is bounded: shedding one coat and putting on another
    leaves two coats, not one renamed one."""
    sc = {"positions": {"Ivo Sarn": "reception_room"},
          "entities": {},
          "attire": {"Ivo Sarn": attire.authored_entry([_MASK, _COAT],
                                                       [], None)}}
    off = _ctx(temp_db, resolved="Ivo shrugs out of the borrowed evening "
                                 "coat.")
    commit.apply_attire_diff(
        sc, {"attire": {"Ivo Sarn": {"remove": [_COAT]}}}, off, _result(off))
    shed_ids = list(sc["entities"])
    assert len(shed_ids) == 1

    on = _ctx(temp_db, idx=2,
              resolved="He takes a grey travelling coat from the peg and puts "
                       "it on.")
    commit.apply_attire_diff(
        sc, {"attire": {"Ivo Sarn": {"add": ["a grey travelling coat"]}}},
        on, _result(on))

    entry = sc["attire"]["Ivo Sarn"]
    assert "a grey travelling coat" in entry["wearing"]
    assert _COAT not in entry["wearing"]
    assert list(sc["entities"]) == shed_ids
