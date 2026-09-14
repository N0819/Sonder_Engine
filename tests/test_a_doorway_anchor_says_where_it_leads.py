"""An implicit doorway anchor in a hand's vocabulary says where it leads.

Three rooms' `door:<room>` anchors all read "the doorway" in one payload, and
the contact hand set a shoulder against `door:passage` for a body leaning on
the scullery's back door (scratch play 2026-09-14, chat 4 turn 11). The
edge's authored name wins; otherwise the barrier phrase names the far room.
"""
from agents.director import _anchor_payload_desc

SC = {"rooms": {
    "scullery": {"name": "Scullery", "adjacent": [
        {"to": "yard", "barrier": "closed_door",
         "name": "the back door to the yard"},
        {"to": "kitchen", "barrier": "open_door"}]},
    "yard": {"name": "Farmyard", "adjacent": [
        {"to": "scullery", "barrier": "closed_door"}]},
    "kitchen": {"name": "Kitchen", "adjacent": [
        {"to": "scullery", "barrier": "open_door"}]},
}}


def test_the_edges_own_name_is_the_description():
    assert _anchor_payload_desc(
        SC, "scullery", "door:yard", {"desc": "the doorway", "implicit": True}
    ) == "the back door to the yard"


def test_an_unnamed_doorway_names_the_room_it_opens_onto():
    assert _anchor_payload_desc(
        SC, "scullery", "door:kitchen",
        {"desc": "the open doorway", "implicit": True}
    ) == "the open doorway to Kitchen"


def test_an_authored_anchor_is_left_alone():
    assert _anchor_payload_desc(
        SC, "scullery", "copper", {"desc": "A brick-encased wash copper."}
    ) == "A brick-encased wash copper."
    assert _anchor_payload_desc(SC, "scullery", "hand_pump", {}) == "hand pump"
