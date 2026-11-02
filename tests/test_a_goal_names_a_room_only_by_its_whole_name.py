"""A goal names a room by the room's WHOLE name, the longest one where two
overlap -- in both readers that ask the question.

`agents.character._destination_from_goals` (routing) and
`mind.affect._last_named_room` (the commit's goal stamps and project
service) both found a room in goal prose with a bare `rfind`, under
docstrings calling it "exact node-NAME matching ... identifier
recognition". Measured (review 2026-11-01, agents_character_background F10
and mind_affect_psychology F6): over {Study, Hall, Inn, Kitchen} "Keep the
beginning of the story straight" named the Inn, "who left the hallway lamp
burning" the Hall, and "Walk to the Great Hall" the Hall (the shorter name
starts later and won). Both now read through one matcher on
`language_runtime.find_names`: whole names, by each name's own script, the
longest at any position, the last in the text winning.
"""

from __future__ import annotations

from agents.character import _destination_from_goals
from mind.affect import _last_named_room

NODES = {"rStudy": "Study", "rHall": "Hall", "rInn": "Inn",
         "rKitchen": "Kitchen", "rGreat": "Great Hall",
         "rDai": "台所", "rHoru": "ホール"}
NAMED = {name.casefold(): rid for rid, name in NODES.items()}


def _graph():
    return {"nodes": {rid: {"basis": "walked", "name": name}
                      for rid, name in NODES.items()}, "edges": {}}


def _dest(goal):
    found = _destination_from_goals({"active_state": {"goal": goal}}, _graph())
    return found["rid"] if found else None


CASES = [
    ("Keep the beginning of the story straight", None),
    ("who left the hallway lamp burning", None),
    ("Walk to the Great Hall", "rGreat"),
    ("Ask the cook what she saw", None),
    ("Study the carvings on the far wall", "rStudy"),
    ("From the Inn head for the Kitchen", "rKitchen"),
    ("Go back to the Inn's stable yard", "rInn"),
    ("台所へ行って水を汲む", "rDai"),
    ("ホールケーキを買う", None),
    ("ホールに戻る", "rHoru"),
]


def test_the_routing_reader_matches_whole_names_only():
    for goal, want in CASES:
        assert _dest(goal) == want, goal


def test_the_commit_reader_agrees_with_the_routing_reader():
    for goal, want in CASES:
        assert _last_named_room(goal, NAMED) == want, goal


def test_a_room_named_last_is_the_one_a_text_goes_to():
    assert _last_named_room("from the Hall to the Study", NAMED) == "rStudy"
    assert _last_named_room("", NAMED) is None
    assert _last_named_room("the Hall", {}) is None
