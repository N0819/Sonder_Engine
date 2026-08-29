"""The lore's named people arrive as people, and a model decides which they are.

Wanted, in the owner's words: canon cast may show up as charter characters as
long as their personality and rank/station match the lore, and their names are
never pool material for generics. Those are two different lanes and this is the
first: an individual the lore names becomes a PERSON at a POST.

A model does the reading because a parser cannot. Measured 2026-08-28 on a real
lorebook: a watch rotation and a set of standing orders were both filed under
the `character` category, and a person's entry was titled "<name>, <role>" so
that splitting on the comma got the name and not splitting got neither. Both
are obvious to a reader and invisible to a rule.
"""
from __future__ import annotations

from world.charter_generate import lore_cast_residents

ENTRIES = [
    {"id": 1, "title": "Miles O'Brien, transporter chief",
     "content": "Enlisted, practical, married to a botanist aboard."},
    {"id": 2, "title": "Gamma shift, standing complement",
     "content": "The thin watch runs 2400 to 0800."},
    {"id": 3, "title": "Jean-Luc Picard",
     "content": "The captain. Reserved, archaeological by inclination."},
]


def _reader(residents):
    def call(system, payload):
        call.payload = payload
        return {"residents": residents}
    return call


def test_a_named_individual_becomes_a_placement_seed():
    call = _reader([{"entry_id": 1, "name": "Miles O'Brien",
                     "post": "transporter chief", "rank": "chief petty officer"}])

    seeds = lore_cast_residents(ENTRIES, ["Sabine Oyelaran"], model_call=call)

    assert len(seeds) == 1
    assert seeds[0]["seed_id"] == "lore:1"
    assert seeds[0]["name"] == "Miles O'Brien"
    assert seeds[0]["post"] == "transporter chief"


def test_the_registered_cast_is_offered_so_it_can_be_excluded():
    """The story's own minds are already present; the model is told who they
    are rather than left to infer it from the lore."""
    call = _reader([])
    lore_cast_residents(ENTRIES, ["Jean-Luc Picard", "Data"], model_call=call)

    assert call.payload["registered"] == ["Data", "Jean-Luc Picard"]


def test_a_reading_that_fails_costs_the_location_nothing():
    def boom(system, payload):
        raise RuntimeError("provider down")

    assert lore_cast_residents(ENTRIES, [], model_call=boom) == []


def test_an_entry_the_reader_invented_is_dropped():
    """Placement evidence is grounded in an entry that exists. A resident
    naming no known entry is not placed, however plausible the name."""
    call = _reader([{"entry_id": 99, "name": "Somebody Entirely New",
                     "post": "cook", "rank": ""}])

    assert lore_cast_residents(ENTRIES, [], model_call=call) == []


def test_one_person_is_placed_once():
    call = _reader([{"entry_id": 1, "name": "Miles O'Brien", "post": "chief"},
                    {"entry_id": 3, "name": "miles o'brien", "post": "chief"}])

    assert len(lore_cast_residents(ENTRIES, [], model_call=call)) == 1


def test_a_lorebook_with_no_people_yields_no_residents():
    call = _reader([])
    assert lore_cast_residents(ENTRIES, [], model_call=call) == []
    assert lore_cast_residents([], [], model_call=call) == []
