"""A role word two managed presences share addresses neither of them on the
scene-manager path.

The commit gate learned it first (review 2026-11-01, persist_background_memory
F2; `tests/test_a_role_word_addresses_nobody_precisely.py`): a line aimed at
"the trader" in a market of traders matched every trader through the
title-stripped ref, and each became a precise addressee forced past the
reactor cap. The scene manager keeps its own demand gate
(`background._demanded_presences`), and it asked `_character_address_of`
without the story's shared name words -- so the same whisper made every
managed trader a `character_address`: exempt from the hearing test, counted
toward the widening past `max_managed`, each handed to the voice call as the
line's addressee. It now passes `shared=` as the commit gate does. A word the
tracked names hold in common singles nobody out; the full name still does.
"""

from __future__ import annotations

from agents import background
from tests.test_a_role_word_addresses_nobody_precisely import (
    TRADERS, WHISPER, _ctx)


def _demanded(temp_db, line, ceiling=1):
    """`(names, why)`: the manager's demand set for a beat whose one line is
    `line`, over the populace the manager is really handed."""
    ctx = _ctx(temp_db, line)
    managed, _p_room = background.managed_presences(ctx, None)
    assert sorted(t[1] for t in managed) == sorted(TRADERS), managed
    out = background._demanded_presences(
        ctx, ctx.director_resolve, managed, ceiling)
    return [t[1] for t in out], ctx["_manager_demand_why"]


def test_a_whisper_to_the_trader_demands_no_managed_trader(temp_db):
    names, why = _demanded(temp_db, WHISPER)
    assert not any("character_address" in reasons
                   for reasons in why.values()), why
    assert len(names) <= 1, names


def test_the_full_name_still_demands_its_body(temp_db):
    names, why = _demanded(temp_db, dict(WHISPER, intended_target="Trader Tate"))
    assert names == ["Trader Tate"], (names, why)
    assert "character_address" in why["Trader Tate"]
