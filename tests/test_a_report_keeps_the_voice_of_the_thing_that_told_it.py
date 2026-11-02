"""A report read off a notice, or heard from a crowd or a rider, keeps its
source's own voice; only a PERSON who told it passes the identity floor.

`tellers_as_known` relabels `told_by` for the mind holding a carried report
(the floor, playerless Aldermill round 8: a hostler's full name reached Sal
through `told_by`). It relabelled EVERY source the floor did not recognise --
and the floor recognises no notice, rider or crowd, since none is a body --
so "a wanted bill nailed to the post" (`artifacts.artifact_voice`, provenance
`read`), "a rider" (`couriers.courier_voice`) and "the crowd in the square"
(`crowds.crowd_voice`) all reached the mind as "the unfamiliar person": a
paper on a wall became a stranger who spoke (review 2026-11-01,
story_room_carriers F10, by snippet). Those voices are written "NEVER a name"
by construction; the report now says what kind of source told it
(`told_by_kind`, from the writer, which knows) or, for a read copy, its
provenance does -- never a guess from the string.
"""

from __future__ import annotations

from agents.character import tellers_as_known

from tests.test_background_character_reply import _setup

HOSTLER = "Hostler Gidoton Barrelfielder"


def _held(**fields):
    return {"world_event_id": "w1", "claim": "the mill burned", **fields}


def test_a_read_copy_keeps_the_thing_it_was_read_from(temp_db):
    _cid, ctx = _setup(temp_db)
    out = tellers_as_known(ctx.chat, "Sal", [], {}, [
        _held(told_by="a wanted bill nailed to the post", provenance="read")])
    assert out[0]["told_by"] == "a wanted bill nailed to the post"


def test_a_crowd_or_a_rider_keeps_its_voice_where_the_writer_said_what_it_is(temp_db):
    _cid, ctx = _setup(temp_db)
    out = tellers_as_known(ctx.chat, "Sal", [], {}, [
        _held(told_by="talk among the dockworkers", provenance="told",
              told_by_kind="crowd"),
        _held(told_by="a rider", provenance="told", told_by_kind="courier")])
    assert [r["told_by"] for r in out] == ["talk among the dockworkers", "a rider"]
    assert all("told_by_kind" not in r for r in out), "the engine's word stays the engine's"


def test_a_person_who_told_it_is_still_named_as_she_knows_him(temp_db):
    _cid, ctx = _setup(temp_db)
    out = tellers_as_known(ctx.chat, "Sal", [], {}, [
        _held(told_by=HOSTLER, provenance="told"),
        _held(told_by=HOSTLER, provenance="told", told_by_kind="person")])
    assert all(HOSTLER not in r["told_by"] for r in out)
