"""A witness keeps whom a line was aimed at only as it saw them.

`evidence_claim` relabelled the ACTOR to the witnesses' label and copied
`target` -- the engine's canonical name of the addressee -- verbatim, so a
barmaid who overheard the player tell Hinami "The well is poisoned" held
`target: "Hinami"` and `scene_ledger` offered it to her voice next day with
Hinami nowhere in the room (audit world_charter_behaviours F2). The actor
and the addressee are relabelled alike: through the beat's labels where the
addressee was standing there to be seen, and not at all where it was not."""
from world.charter import normalize_charter
from world.charter_log import scene_ledger
from world.charter_observe import evidence_claim, plan_public_evidence


_EVIDENCE = {"source_id": "s1", "kind": "speech", "actor": "Sarah Moon",
             "target": "Hinami", "exact_quote": '"The well is poisoned."',
             "speech_acts": [{"kind": "warning", "target": "Hinami",
                              "content": "The well is poisoned"}]}


def test_an_unshown_addressee_is_not_held_by_name():
    claim = evidence_claim(dict(_EVIDENCE), 7, 0.0, "taproom",
                           label="the slight woman")
    licensed = claim["public_evidence"]
    assert licensed["actor"] == "the slight woman"
    assert "Hinami" not in str(licensed)
    assert "Sarah Moon" not in str(licensed)


def test_a_shown_addressee_is_held_by_the_label_it_was_shown_under():
    claim = evidence_claim(dict(_EVIDENCE), 7, 0.0, "taproom",
                           label="the slight woman",
                           target_label="the girl in the grey coat")
    licensed = claim["public_evidence"]
    assert licensed["target"] == "the girl in the grey coat"
    assert "Hinami" not in str(licensed)


def test_the_voice_slice_of_an_overheard_line_names_nobody_unmet():
    charter = normalize_charter({
        "key": "inn", "upkeeps": {}, "posts": {},
        "bodies": {"tam": {"place": "taproom", "name": "Tam"}}})
    scene = {"rooms": {"taproom": {"name": "Taproom", "adjacent": []}},
             "positions": {"Sarah Moon": "taproom", "Hinami": "taproom"},
             "entities": {}}
    plan = plan_public_evidence(
        charter, [dict(_EVIDENCE)], scene, 7,
        labels={"Sarah Moon": "the slight woman",
                "Hinami": "the girl in the grey coat"})
    minds = {}
    for body_key, subject, claim in plan["inserts"]:
        minds.setdefault(body_key, {})[subject] = claim
    charter["minds"] = minds
    # Next day, in the yard: Hinami is nowhere near.
    ledger = scene_ledger(charter, "taproom")
    text = str(ledger["presences"]["tam"]["can_bring_up"])
    assert "Hinami" not in text and "Sarah Moon" not in text
    assert "the girl in the grey coat" in text
