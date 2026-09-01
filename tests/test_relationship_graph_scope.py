"""The relationship graph in a character payload is NOT scoped by presence.

Measured on 2026-09-01 against the live corpus (86 graphs): the whole graph is
422 bytes at the median and 1,070 at its largest -- five targets -- so a
presence filter buys ~100 tokens on a payload that also carries retrieved
memory, world knowledge and the rendered view. The trim it would be imitating,
`scene_compact_attire`, saved 618 tokens by itself.

What it would cost is the point of these tests. The absent target is routinely
the load-bearing one (chat 59: The Doctor's familiarity-1.00 tie is Hinami, a
floor above him), and `character._known_pronouns` reads the graph's key set as
its RECOGNITION set -- so narrowing the graph by who is standing here would
silently withdraw an absent person's pronouns as well, putting the character
back on guessing gender from a name.

These pin the decision so the trim is not re-derived as an obvious win. If a
future change genuinely needs to bound this structure, the axis is the clock
(a tie 128 beats stale in an abandoned arc is a real defect) and not the
doorway.
"""

import inspect

from core.db import qi
from mind.memory import (
    RelationshipGraph,
    relationships_for_payload,
    save_relationships,
)
from agents.character import _known_pronouns

HE = {"subject": "he", "object": "him", "possessive": "his"}


def test_payload_builder_takes_no_scene_and_so_cannot_filter_by_presence():
    """The signature is the guard: where a relationship stands is a question
    about two minds, and nothing about a room is an input to it."""
    params = list(inspect.signature(relationships_for_payload).parameters)
    assert params == ["chat_id", "char_id"]


def test_every_known_target_reaches_the_payload_wherever_they_are(temp_db):
    chat_id = qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("relationship scope", "", 0.0))
    graph = RelationshipGraph()
    # The shape of chat 59: the strongest tie in the graph is the player, and
    # she is not in the room.
    graph.update("Hinami", familiarity=1.0, trust=0.8,
                 last_interaction_turn=165)
    graph.update("Tamamo", familiarity=0.63, last_interaction_turn=166)
    save_relationships(chat_id, 35, graph)

    out = relationships_for_payload(chat_id, 35)

    assert set(out) == {"Hinami", "Tamamo"}
    assert out["Hinami"]["familiarity"] == 1.0


def test_narrowing_the_graph_would_withdraw_an_absent_persons_pronouns():
    """Why a presence filter is not a local change. `_known_pronouns` is
    handed `set(relationships) | set(mind_models)` and treats it as the set of
    people this mind may know at all."""
    cast = [{"sheet": '{"identity": {"name": "The Doctor", "pronouns": '
                      '{"subject": "he", "object": "him", '
                      '"possessive": "his"}}}'}]
    persona = {"identity": {"name": "Hinami", "pronouns": HE}}

    whole = _known_pronouns(cast, persona, {"The Doctor", "Hinami"},
                            exclude=["Tamamo"])
    assert whole == {"The Doctor": HE, "Hinami": HE}

    # The same call with an absent person filtered out of the graph: the
    # character is now guessing, and nothing warns.
    present_only = _known_pronouns(cast, persona, {"The Doctor"},
                                   exclude=["Tamamo"])
    assert "Hinami" not in present_only
