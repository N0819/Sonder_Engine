"""A look is read off the declaration the interpret writes, and off nothing
no stage writes.

`_explicit_look_intent` returned True for any `location_query`, a field no
prompt in either pack asks for and no code has written since 2026-09-27 --
the Director only defaults it to None and clears it (audit agents_perception
F11, 2026-11-01). A branch on a field nothing writes is a reader that can
only ever be wrong: the day something writes it, it re-renders the player's
whole standing state on an input nobody designed for that. The declared look
(`look: around`) and the pack's look verbs carry the behaviour.
"""

from agents import perception


def test_a_location_query_alone_is_no_look():
    assert perception._explicit_look_intent(
        {"location_query": "the far shelf"}) is False


def test_a_declared_look_is_a_look():
    assert perception._explicit_look_intent({"sequence": [
        {"type": "action", "look": "around",
         "attempt": "turns slowly in place"}]}) is True
