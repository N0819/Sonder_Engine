"""A held project is always among the aims the read-back offers.

`character_bare.holding_from` appended the drive, then the steering
intentions, then the projects, and cut the list at `jev.MAX_AIMS` -- so a
mind holding its drive and the `ordinary` rung's four steering intentions
was never offered its project: it could not be chosen for `want:serves` /
`held_back:serves`, nor asked how the beat touched it, and a probationary
project could not earn its serving beats and lapsed (review 2026-11-01,
mind_affect_psychology F8, reproduced). The cut is now
`jev.aims_offered` (L9): the cap is kept, and filled around the projects.
"""

from __future__ import annotations

from agents.character_bare import holding_from
from mind import character_jev as jev
from story.character_schema import default_character_data


def test_a_project_survives_a_full_ledger_of_steering_intentions():
    sheet = default_character_data("Ilse")
    sheet["psychology"]["drive"] = {"essence": "keep the harbour safe",
                                    "expression": "", "taboo": ""}
    intents = [{"id": f"i{k}", "intent": f"check the {w}", "status": "active"}
               for k, w in enumerate(("nets", "moorings", "lamps", "tide board"), 1)]
    payload = {"self": {
        "intentions": intents,
        "steering_intention_ids": [i["id"] for i in intents],
        "projects": [{"id": "p1", "project": "chart the shoals before winter"}],
    }}
    h = holding_from("Ilse", sheet, payload, [], {}, {})
    ids = [a["id"] for a in h.aims]
    assert "p1" in ids
    assert len(h.aims) == jev.MAX_AIMS
    assert ids[0] == "drive"
