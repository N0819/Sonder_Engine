"""Review 2026-09-07 A23/A24's sibling: `medium` is a declared field, so a
comm line keeps its channel through validation; `far_path_gain` tells a
shout that dies from rooms no chain of edges joins.
"""
from llm.schemas import DialogueLogEntry
from world.spatial import far_path_gain


def test_medium_survives_validation_and_is_casefolded():
    entry = DialogueLogEntry(speaker="Picard", exact_quote="Energize.",
                             medium="Comm")
    assert entry.medium == "comm"
    assert DialogueLogEntry(speaker="a", exact_quote="b").medium == ""


def test_unjoined_rooms_have_no_path_gain_while_far_joined_rooms_have_zero():
    chain = {"rooms": {
        "a": {"adjacent": [{"to": "b", "barrier": "wall"}]},
        "b": {"adjacent": [{"to": "a", "barrier": "wall"},
                           {"to": "c", "barrier": "wall"}]},
        "c": {"adjacent": [{"to": "b", "barrier": "wall"}]},
        "orbit": {"adjacent": []},
    }, "positions": {}}
    assert far_path_gain(chain, "a", "orbit") is None
    assert far_path_gain(chain, "a", "c") is not None
