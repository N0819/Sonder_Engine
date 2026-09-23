"""A body touching itself owns both parts.

Playerless Aldermill round 6 (2026-09-23), idx 16 and 21: "You feel you's
fingertips" and "you's trouser leg" reached Emory's view, and his memory kept
them as "me's".
"""
from world.spatial import contact_sensation


def test_a_hand_on_your_own_leg_is_your_leg():
    contact = {"actor": "Emory Vane", "actor_part": "fingertips",
               "target": "Emory Vane", "target_part": "trouser leg",
               "manner": "rest"}
    felt = contact_sensation(contact, you="Emory Vane",
                             label_for=lambda name: "the stranger")
    assert "you's" not in felt and "Emory" not in felt
    assert "your trouser leg" in felt and "your fingertips" in felt


def test_another_body_is_still_named_by_the_floor():
    contact = {"actor": "Master Fenstonwell", "actor_part": "hand",
               "target": "Emory Vane", "target_part": "shoulder",
               "manner": "rest"}
    felt = contact_sensation(contact, you="Emory Vane",
                             label_for=lambda name: "the heavy-framed miller")
    assert "the heavy-framed miller's hand" in felt
