"""The repair merge, the diff normaliser and the manifest are derived from
the schema, and a mint in a KNOWN empty room binds to nobody.

Review 2026-09-07 A6/A7/A42.
"""
from agents.director import (_bind_minted_entities_to_present_figures,
                             _manifest_items, _merge_repair_into_diff,
                             _normalize_diff_shape, _state_diff_channels)


def test_every_container_channel_is_normalised():
    sd = _normalize_diff_shape({})
    for channel in ("scales", "containment", "vitals", "sensory_events",
                    "comms_ops", "courier_ops", "charter_ops",
                    "ratified_claims", "contradicted_claims", "artifact_ops"):
        assert channel in sd, channel
    assert set(sd) >= (_state_diff_channels() - {"destruction", "weather",
                                                 "location", "time"})


def test_a_repair_in_a_formerly_dropped_channel_reaches_the_diff():
    sd = _normalize_diff_shape({"positions": {"Aurel": "landing"}})
    _merge_repair_into_diff(sd, _normalize_diff_shape({
        "scales": {"Hinami": 0.05},
        "sensory_events": [{"kind": "sound", "room": "riser"}],
        "destruction": {"door": {"state": "buckled"}},
        "positions": {"Aurel": "riser"},          # add-only: the move stands
        "weather": {"sky": "storm"},
    }))
    assert sd["scales"] == {"Hinami": 0.05}
    assert sd["sensory_events"] == [{"kind": "sound", "room": "riser"}]
    assert sd["destruction"] == {"door": {"state": "buckled"}}
    assert sd["positions"] == {"Aurel": "landing"}
    assert sd["weather"] == {"sky": "storm"}


def test_the_manifest_is_not_clamped():
    out = {"changes_asserted": [
        {"category": "entities", "subject": f"thing{i}", "change": f"c{i}"}
        for i in range(12)]}
    items = _manifest_items(out)
    assert len(items) == 12
    assert [i["event_id"] for i in items] == list(range(1, 13))


def test_a_known_empty_room_binds_a_mint_to_nobody():
    figures = [{"name": "Innkeeper Tam Ashwell", "role": "innkeeper",
                "posts": ["ford_innkeeper"], "room": "ford_inn_common",
                "charter": "ford_inn", "body": "b1"}]
    sd = {"entities": {"keeper_x": {"name": "the innkeeper", "kind": "person",
                                    "aliases": ["innkeeper"]}},
          "positions": {"keeper_x": "empty_square"}}
    sc = {"rooms": {"empty_square": {}, "ford_inn_common": {}}, "entities": {}}
    bound = _bind_minted_entities_to_present_figures(sc, sd, figures)
    assert bound == [], "a room with no figures is an answer, not an unknown"
    sd2 = {"entities": {"keeper_x": {"name": "the innkeeper", "kind": "person",
                                     "aliases": ["innkeeper"]}},
           "positions": {}}
    bound = _bind_minted_entities_to_present_figures(sc, sd2, figures)
    assert bound and bound[0]["bound_to"] == "Innkeeper Tam Ashwell", \
        "an unknown room still widens"
